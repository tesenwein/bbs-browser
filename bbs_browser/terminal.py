"""Retro terminal: colors, typing effect, frames, modem handshake."""

import sys
import time

from .constants import AMBER, BOLD, DIM, INVERT, RESET, CLEAR, screen_width
from .i18n import t
from . import wordmark


def banner():
    """Die Wortmarke plus Mailbox-Zeile — dieselben Zeichen wie assets/logo.svg.

    Auf schmalen Terminals steht nur "BBS", sonst risse die Marke um und die
    Blockschrift waere unlesbar."""
    room = screen_width()
    art = wordmark.FULL if room >= wordmark.width(wordmark.FULL) + 2 else wordmark.COMPACT
    return "\n" + wordmark.render(art) + "\n\n   " + t("terminal.banner_tagline") + "\n"


def signoff():
    """Kurzmarke beim Auflegen — das Gegenstueck zum Intro, damit der Anruf
    mit demselben Zeichen endet, mit dem er begonnen hat."""
    return "\n" + wordmark.render(wordmark.COMPACT) + "\n"


def __getattr__(name):
    """Still allows `from .terminal import BANNER` (e.g. in tests) —
    returns the banner in the currently configured language."""
    if name == "BANNER":
        return banner()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Full speed (baud=0) identifies itself as the fastest modem of the era.
DEFAULT_DIAL_BAUD = 28800


def dial_sequence(baud=0):
    """Modem chatter during connection setup — real Hayes commands and
    result codes, using the actually configured baud rate."""
    rate = baud or DEFAULT_DIAL_BAUD
    return [
        ("ATZ", 0.25, None),
        ("OK", 0.20, None),
        ("ATDT 0,555-0100", 0.45, "dial"),
        ("", 0.10, None),
        ("RINGING...", 0.55, "ring"),
        (f"CARRIER {rate}", 0.30, "answer"),
        ("PROTOCOL: LAP-M / V.42BIS", 0.25, "handshake"),
        ("COMPRESSION: CLASS 5", 0.25, "train"),
        (f"CONNECT {rate}/ARQ/V42BIS", 0.45, "connect"),
    ]


DIAL_SEQUENCE = dial_sequence()


class Terminal:
    def __init__(self, color=AMBER, fast=False, baud=0, sound=False):
        self.color = color
        self.fast = fast
        self.baud = baud      # 0 = full speed, otherwise e.g. 2400/9600
        self.sound = sound
        self.skip = False     # Ctrl+C pressed: print the rest of the screen immediately
        self.interrupts = 0   # consecutive Ctrl+C at the prompt (2 = hang up)
        self.skippable = False  # dial-in running: a keystroke ends the effects
        self._status_on = False    # a transient status line is on screen
        self._status_text = None   # its text — redrawn after regular output

    def check_skip(self):
        """True once the sequence should run without effects.

        During the dial-in any keystroke — Enter, as impatient callers used
        to press it — counts as 'skip'. Outside of it nothing is read, so
        typed-ahead commands stay in the buffer."""
        if self.skip or not self.skippable:
            return self.skip
        from . import keys
        try:
            if sys.stdin.isatty() and keys.wait_key(0):
                keys.drain()
                self.skip = True
        except (OSError, ValueError):
            pass
        return self.skip

    def sleep(self, seconds):
        """Pause that ends early as soon as the caller skips the sequence."""
        if self.check_skip() or seconds <= 0:
            return
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.check_skip():
                return
            time.sleep(min(0.05, remaining))

    # -- Transient status line -------------------------------------------
    #
    # One dimmed line that overwrites itself: progress that nobody needs
    # to keep (tool calls, probing, verify pages) shows only its LATEST
    # step. It is sticky: regular output lifts it briefly, prints, and
    # redraws it below — so the line stays visible even while tools print
    # their own output. Only prompt(), clear() and status_clear() end it.

    def status(self, text):
        """Shows `text` on the transient status line (replacing the
        previous one). Falls back to a normal line without a TTY."""
        if not sys.stdout.isatty():
            if text != self._status_text:
                self.type_out(text, delay=0.001)
            self._status_text = text
            return
        self._status_text = text
        self._status_draw()

    def _status_draw(self):
        sys.stdout.write("\r\x1b[2K" + self.color + DIM
                         + self._status_text[:screen_width() - 1] + RESET)
        sys.stdout.flush()
        self._status_on = True

    def status_clear(self):
        """Ends the status line: wipes it and forgets its text."""
        self._status_text = None
        self._status_wipe()

    def _status_wipe(self):
        """Takes the line off screen without forgetting it — regular
        output calls this first so the status never mixes into it."""
        if self._status_on:
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()
            self._status_on = False

    def _status_redraw(self):
        """Puts the sticky line back after regular output."""
        if self._status_text and sys.stdout.isatty():
            self._status_draw()

    def emit(self, styled_text):
        """Prints an already-styled line — throttled when baud is set, as if
        it were coming through the modem (ANSI codes cost no time)."""
        self._status_wipe()
        if not self.baud or self.skip:
            print(styled_text)
            self._status_redraw()
            return
        delay = 10.0 / self.baud
        in_esc = False
        for idx, ch in enumerate(styled_text):
            sys.stdout.write(ch)
            if ch == "\x1b":
                in_esc = True
                continue
            if in_esc:
                if ch.isalpha():
                    in_esc = False
                continue
            sys.stdout.flush()
            try:
                time.sleep(delay)
            except KeyboardInterrupt:
                self.skip = True
                sys.stdout.write(styled_text[idx + 1:])
                break
        print()
        self._status_redraw()

    def tone(self, section):
        """A piece of modem sound — only when sound is enabled. Returns an
        event that signals the actual start of the tone (None if silent)."""
        if not self.sound or self.skip:
            return None
        from . import modem
        return modem.play(section)

    def tone_secs(self, section):
        """How long the section sounds — 0 if nothing is currently playing."""
        if not self.sound or self.skip:
            return 0.0
        from . import modem
        if not modem.available():
            return 0.0
        return modem.duration(section)

    def beep(self, n=1):
        if not self.sound:
            return
        for _ in range(n):
            sys.stdout.write("\a")
            sys.stdout.flush()
            time.sleep(0.12)

    def type_out(self, text, delay=0.006, newline=True):
        self._status_wipe()
        if self.fast or self.skip or delay <= 0:
            print(self.color + text + RESET, end="\n" if newline else "")
            sys.stdout.flush()
            if newline:
                self._status_redraw()
            return
        for idx, ch in enumerate(text):
            sys.stdout.write(self.color + ch + RESET)
            sys.stdout.flush()
            try:
                if self.skippable:
                    self.sleep(delay)
                else:
                    time.sleep(delay)
            except KeyboardInterrupt:
                self.skip = True
            if self.skip:
                sys.stdout.write(self.color + text[idx + 1:] + RESET)
                break
        if newline:
            print()
            self._status_redraw()

    def markdown(self, text, prefix=None, image=None):
        """Prints an AI markdown block, rendered by rich in phosphor tone.

        `prefix` (e.g. a handle like 'ACE>') is prepended to the first line.
        `image` is an optional callback (url, alt) -> image payload (as
        images.fetch_image returns it); with it, markdown images in the text
        are typeset as character art, exactly like the pictures on a page.
        Without it the image markup stays plain markdown.
        If rich is missing, the raw text comes out instead. Escape sequences
        survive the baud effect (emit); the per-character typing effect
        would break them apart."""
        from .markdown import render, split_images

        self._status_wipe()
        lines = []
        for segment in split_images(text) if image else [("text", text)]:
            if segment[0] == "text":
                lines.extend(render(segment[1], self.color))
            else:
                lines.extend(self._image_lines(image, segment[2], segment[1]))
        if not lines:
            if prefix:
                print(self.color + prefix + RESET)
            self._status_redraw()
            return
        if prefix:
            lines = [self.color + prefix + lines[0]] + lines[1:]
        for line in lines:
            if self.baud and not self.skip:
                self.emit(line + RESET)
            else:
                print(line + RESET)
        self._status_redraw()

    def _image_lines(self, image, url, alt):
        """Character art for one markdown image — label plus picture, in the
        same shape a page uses. Falls back to the bare label if the picture
        can't be fetched or images are switched off."""
        from .i18n import t
        from .images import halfblock_lines

        art = None
        try:
            art = image(url, alt)
        except Exception:
            art = None
        label = self.color + BOLD + t("render.image_label", alt=alt or url) + RESET
        if not art:
            return [label]
        if art.get("rgb"):
            from .images import rgb_halfblock_lines

            body = rgb_halfblock_lines(art["rgb"])
        elif art.get("luma"):
            body = halfblock_lines(art["luma"], self.color)
        else:
            body = [self.color + DIM + line[:screen_width()] for line in art["lines"]]
        return [label] + body + [""]

    def line(self, char="=", n=None):
        self._status_wipe()
        print(self.color + char * (screen_width() if n is None else n) + RESET)
        self._status_redraw()

    def rule(self, label="", char="─"):
        self._status_wipe()
        if label:
            deco = f"{char * 3}[ {label} ]"
            print(self.color + deco + char * max(0, screen_width() - len(deco)) + RESET)
        else:
            print(self.color + char * screen_width() + RESET)
        self._status_redraw()

    def box(self, rows):
        self._status_wipe()
        inner = screen_width() - 4
        print(self.color + "╔" + "═" * (screen_width() - 2) + "╗" + RESET)
        for row in rows:
            print(self.color + "║ " + BOLD + row[:inner].ljust(inner) + RESET + self.color + " ║" + RESET)
        print(self.color + "╚" + "═" * (screen_width() - 2) + "╝" + RESET)
        self._status_redraw()

    def clear(self):
        # The screen wipe takes the line with it — and ends it for good.
        self._status_on = False
        self._status_text = None
        print(CLEAR, end="")

    def status_bar(self, text):
        self._status_wipe()
        print(self.color + INVERT + text[:screen_width()].ljust(screen_width()) + RESET)
        self._status_redraw()

    def prompt(self, label=None):
        if label is None:
            label = t("terminal.default_prompt")
        self.status_clear()
        self.skip = False  # next screen is allowed to animate again
        try:
            text = input(self.color + BOLD + label + RESET + self.color).strip()
            self.interrupts = 0
            return text
        except KeyboardInterrupt:
            self.on_interrupt()
            return ""
        except UnicodeDecodeError:
            # Undecodable bytes on stdin: drop the line instead of crashing.
            print()
            return ""
        finally:
            sys.stdout.write(RESET)

    def on_interrupt(self):
        """Ctrl+C at the prompt: once cancels the input, twice in a row
        hangs up and exits the program."""
        self.interrupts += 1
        print()
        if self.interrupts >= 2:
            self.type_out("\n+++ATH", delay=0.003)
            self.type_out("NO CARRIER", delay=0.003)
            self.type_out(signoff(), delay=0.0005)
            raise SystemExit(0)
        self.type_out(t("terminal.interrupt_hint"), delay=0.001)

    def error(self, text):
        self.beep()
        self.type_out(f"\n*** {text} ***\n", delay=0.003)

    def pause(self, label=None):
        """Leave the message on screen until the caller presses a key —
        otherwise the next bar menu would immediately draw over it."""
        from . import keys
        if label is None:
            label = t("terminal.pause_hint")
        if not keys.available():
            return
        print(self.color + DIM + label + RESET)
        try:
            with keys.raw_mode():
                keys.read_key()
        except (KeyboardInterrupt, EOFError, OSError):
            pass


def modem_handshake(term):
    """Connection setup like on a real Hayes modem: AT commands,
    dialing pulses, carrier tone, protocol negotiation — then the logo."""
    term.clear()
    term.skippable = True
    rate = getattr(term, "baud", 0) or DEFAULT_DIAL_BAUD
    print(term.color + DIM + t("terminal.modem_id", baud=rate) + RESET)
    if term.sound:
        from . import modem
        modem.prerender()
    # The sound sections run sequentially in the background; audio_done
    # tracks when the current one ends, so the next screen step doesn't
    # appear before its sound.
    audio_done = time.monotonic()

    def cue(section):
        nonlocal audio_done
        lag = audio_done - time.monotonic()
        if lag > 0:
            term.sleep(lag)
        started = term.tone(section)
        # Wait for the actual start of the tone instead of estimating it —
        # otherwise every startup delay would shift into the rest as an offset.
        if started is not None and not term.skip:
            started.wait(timeout=3.0)
        audio_done = time.monotonic() + term.tone_secs(section)

    try:
        for text, pause, kind in dial_sequence(getattr(term, "baud", 0)):
            if kind == "dial":
                # Dial tone first, then dial: the digits tick through the
                # line one by one, in time with the DTMF tones.
                cue("dialtone")
                sys.stdout.write(term.color + text)
                sys.stdout.flush()
                cue("dtmf")
                step = max(term.tone_secs("dtmf") / 6, 0.18)
                for _ in range(6):
                    sys.stdout.write(".")
                    sys.stdout.flush()
                    term.sleep(step)
                print(RESET)
            elif kind == "connect":
                cue("connect")
                term.type_out(text, delay=0.012)
                term.beep(2)
            else:
                if kind:
                    cue(kind)
                term.type_out(text, delay=0.012)
                if kind == "answer":
                    term.beep()
            term.sleep(pause)
        # Terminal detection, as every mailbox used to do when dialing in.
        for probe, answer in (
            (t("terminal.probe_terminal"), "ANSI-BBS"),
            (t("terminal.probe_screen"), f"{screen_width()}x24"),
            (t("terminal.probe_charset"), "CP437"),
        ):
            sys.stdout.write(term.color + DIM + f"{probe} ..." + RESET)
            sys.stdout.flush()
            term.sleep(0.2)
            print(term.color + f" {answer}" + RESET)
        term.sleep(0.35)
    except KeyboardInterrupt:
        term.skip = True
        from . import modem
        modem.stop()
    term.clear()
    term.type_out(banner(), delay=0.0005)
