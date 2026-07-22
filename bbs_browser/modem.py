"""The sound of dialing in — synthesized, without a single sound file.

Dial tone, DTMF digits, ringback, and the screech of the carrier handshake
are computed here as PCM (8 kHz, 16-bit, mono), written to a temporary WAV
file, and handed to the first available player on the system:
``aplay``/``paplay``/``pw-play`` on Linux, ``afplay`` on macOS,
``powershell.exe`` on Windows and WSL.

Everything runs in a background thread, so the text keeps ticking along. If
no player is found, it simply stays silent — dialing in then looks just
like always.
"""

import array
import atexit
import math
import os
import random
import shutil
import subprocess
import tempfile
import threading
import wave

# 8 kHz would be the real telephone rate, but a 2400 Hz tone only has about
# three samples per period in that — what cheap resamplers make of that
# screeches.
RATE = 22050
BAND = (300, 3400)  # Passband of the line

# Peak level per phase, taken from a real dial-in recording. The handshake
# tones are noticeably quiet in it, the training loud — exactly this
# gradient is what makes the difference from a signal generator.
PEAKS = {
    "dialtone": 0.09,
    "dtmf": 0.17,
    "ring": 0.12,
    "answer": 0.06,
    "handshake": 0.07,
    "train": 0.20,
    "connect": 0.10,
}
_player = None      # None = not yet searched, [] = none found

# DTMF: (low, high) in Hz — exactly the tones the exchange expected.
DTMF = {
    "1": (697, 1209), "2": (697, 1336), "3": (697, 1477),
    "4": (770, 1209), "5": (770, 1336), "6": (770, 1477),
    "7": (852, 1209), "8": (852, 1336), "9": (852, 1477),
    "*": (941, 1209), "0": (941, 1336), "#": (941, 1477),
}


# -- Sound building blocks --------------------------------------------------

def _tone(freqs, secs, amp=0.35):
    """Sum of several sine waves with a short fade in/out (otherwise it clicks)."""
    n = int(RATE * secs)
    fade = min(int(RATE * 0.005), n // 2) or 1
    out = array.array("h")
    for i in range(n):
        value = sum(math.sin(2 * math.pi * f * i / RATE) for f in freqs)
        value *= amp / max(len(freqs), 1)
        if i < fade:
            value *= i / fade
        elif i > n - fade:
            value *= (n - i) / fade
        out.append(int(max(-1.0, min(1.0, value)) * 32767))
    return out


def _silence(secs):
    return array.array("h", [0] * int(RATE * secs))


def _biquad(kind, fc, q):
    """One second-order section (RBJ cookbook), returned as normalized
    coefficients."""
    w0 = 2 * math.pi * fc / RATE
    cosw, alpha = math.cos(w0), math.sin(w0) / (2 * q)
    if kind == "lp":
        b0, b1, b2 = (1 - cosw) / 2, 1 - cosw, (1 - cosw) / 2
    else:
        b0, b1, b2 = (1 + cosw) / 2, -(1 + cosw), (1 + cosw) / 2
    a0, a1, a2 = 1 + alpha, -2 * cosw, 1 - alpha
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


# The line as the reference recording shows it: flat from 300 to 3400 Hz,
# then a wall — the measurement falls by more than 30 dB within 700 Hz above
# it. A single two-pole low-pass leaves far too much up there, and that
# residue is exactly what sounds like digital hiss instead of copper. Hence
# a 6th-order Butterworth (three sections, Q per the Butterworth table)
# below and a 2nd-order high-pass above.
_LINE = [_biquad("lp", BAND[1], q) for q in (0.5176, 0.7071, 1.9319)] \
    + [_biquad("hp", BAND[0], 0.7071)]


def _telephone(samples):
    """As heard through the line: steep bandpass 300–3400 Hz. Without it,
    noise and sweeps sit right up to the Nyquist limit and sound digitally
    harsh instead of like copper."""
    values = [s / 32768.0 for s in samples]
    for b0, b1, b2, a1, a2 in _LINE:
        x1 = x2 = y1 = y2 = 0.0
        for i, x0 in enumerate(values):
            y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, x0
            y2, y1 = y1, y0
            values[i] = y0
    return array.array("h", [int(max(-1.0, min(1.0, v)) * 32767)
                             for v in values])


def _line_noise(samples, level=0.006):
    """Baseline line noise, measurable even in the gaps in the reference
    recording. Without it the tones sit in absolute silence and sound like
    a signal generator instead of a handset. Passed through the same
    bandpass."""
    hiss = _telephone(_noise(len(samples) / RATE, amp=1.0))
    top = max((abs(s) for s in hiss), default=0) or 1
    gain = level * 32767 / top
    return array.array("h", [max(-32767, min(32767, s + int(hiss[i] * gain)))
                             for i, s in enumerate(samples)])


def _normalize(samples, peak):
    """Pull to a target level. The bandpass costs a different amount
    depending on the phase — without normalizing, the tones would be
    unevenly loud."""
    top = max((abs(s) for s in samples), default=0)
    if not top:
        return samples
    gain = peak * 32767 / top
    return array.array("h", [int(s * gain) for s in samples])


def _noise(secs, amp=0.18):
    """Broadband noise — the data mush of the training phase. The line
    filter gives it its color; pre-colored it would sound muffled instead
    of like a modem."""
    return array.array("h", [int(random.uniform(-1.0, 1.0) * amp * 32767)
                             for _ in range(int(RATE * secs))])


def _swirl(secs, amp=0.3, floor=0.45, tilt=(-4.0, 2.0)):
    """Noise that lives: the level heaves in slow beats, and the timbre
    drifts independently of that.

    The measurement of the reference shows the training phase to be
    virtually flat across the whole passband — it only leans by a few dB,
    and that lean drifts: in one section it falls gently above 1 kHz, in
    another it rises to a maximum around 3 kHz. `tilt` is that lean in dB
    at the band edges, which the timbre beat drifts between. Anything
    steeper turns the mush into hiss."""
    n = int(RATE * secs)
    fade = min(int(RATE * 0.02), n // 2) or 1
    out = array.array("h")
    # Crossover in the middle of the band: the noise is split into a dark
    # and a bright half, and the lean is just their mixing ratio.
    split = 1.0 - math.exp(-2 * math.pi * 1200 / RATE)
    low = 0.0
    for i in range(n):
        t = i / RATE
        # Three inharmonic beat frequencies — nothing repeats audibly.
        wave = (math.sin(2 * math.pi * 0.7 * t)
                + math.sin(2 * math.pi * 1.9 * t + 1.3)
                + math.sin(2 * math.pi * 3.1 * t + 2.7)) / 3.0
        env = floor + (1.0 - floor) * (0.5 + 0.5 * wave)
        # Separate beat for the timbre, otherwise level and tone would move
        # in lockstep and the whole thing would sound like a plain tremolo.
        turn = (math.sin(2 * math.pi * 0.43 * t + 0.6)
                + math.sin(2 * math.pi * 1.27 * t + 2.1)) / 2.0
        lean = tilt[0] + (tilt[1] - tilt[0]) * (0.5 + 0.5 * turn)
        gain = 10 ** (lean / 20.0)        # dB of the bright half over the dark
        white = random.uniform(-1.0, 1.0)
        low += split * (white - low)
        value = (low + gain * (white - low)) * amp * env
        if i < fade:
            value *= i / fade
        elif i > n - fade:
            value *= (n - i) / fade
        out.append(int(max(-1.0, min(1.0, value)) * 32767))
    return out


def _fsk(mark, space, secs, baud=300, amp=0.3):
    """V.21 data channel: 300 baud, each bit switches between mark and
    space. Exactly the chirping a dial-in is recognized by — measured in
    the reference as 980/1180 Hz (channel 1) and 1650/1850 Hz (channel 2).
    The phase keeps running across bit boundaries, otherwise every switch
    clicks."""
    n = int(RATE * secs)
    bit = max(int(RATE / baud), 1)
    fade = min(int(RATE * 0.005), n // 2) or 1
    out = array.array("h")
    phase, freq = 0.0, mark
    for i in range(n):
        if i % bit == 0:
            freq = mark if random.getrandbits(1) else space
        phase += 2 * math.pi * freq / RATE
        value = math.sin(phase) * amp
        if i < fade:
            value *= i / fade
        elif i > n - fade:
            value *= (n - i) / fade
        out.append(int(max(-1.0, min(1.0, value)) * 32767))
    return out


# -- The phases of dialing in ----------------------------------------------

def _dial_tone():
    return _tone((350, 440), 0.7)


def _dtmf(number):
    # Length and gap follow the reference recording: ~140 ms tone, ~50 ms gap.
    out = array.array("h")
    for ch in number:
        if ch in DTMF:
            out += _tone(DTMF[ch], 0.14, amp=0.45) + _silence(0.05)
        else:
            out += _silence(0.04)      # Separators like ',' and '-'
    return out


def _ringing(count=2):
    out = array.array("h")
    for _ in range(count):
        out += _tone((440, 480), 0.8, amp=0.3) + _silence(0.45)
    return out


def _answer():
    """The remote end's answer tone — 2098 Hz in the reference, i.e. the
    2100 Hz from the standard, steady and held long."""
    return _tone((2100,), 0.8, amp=0.3)


def _handshake():
    """V.8 negotiation: the two FSK channels chirp their capabilities to
    each other, the lower one first, then the upper. In the recording
    that's a good two seconds — shortened here."""
    return _fsk(980, 1180, 0.55) + _fsk(1650, 1850, 0.55) + _fsk(980, 1180, 0.2)


def _train():
    """Equalizer training: the long, heaving data mush, then the tone pair
    right before it locks in (2203/2379 Hz in the reference). There the
    section lasts 6.4 s and falls into two halves with drifting timbre —
    shortened here, but with the same motion."""
    return _swirl(1.7, amp=0.5, tilt=(-5.0, 0.0)) \
        + _swirl(1.3, amp=0.3, floor=0.6, tilt=(-1.0, 4.0)) \
        + _tone((2200, 2380), 0.4, amp=0.3)


def _connect():
    """Brief lock-in, then silence — the line is up."""
    return _tone((1200,), 0.12, amp=0.25) + _silence(0.08) + _tone((2400,), 0.1, amp=0.2)


# One phase per on-screen step of dialing in, in exactly this order — so
# each line has its own sound instead of one block spanning several.
SECTIONS = {
    "dialtone": _dial_tone,
    "dtmf": lambda: _dtmf("0,555-0100"),
    "ring": _ringing,
    "answer": _answer,
    "handshake": _handshake,
    "train": _train,
    "connect": _connect,
}

# Length of each section in seconds — the screen times its pauses by this,
# so text and sound stay in the same rhythm. Computed once, since the
# duration doesn't depend on the random noise.
_durations = {}


def duration(section):
    build = SECTIONS.get(section)
    if not build:
        return 0.0
    if section not in _durations:
        _durations[section] = len(build()) / RATE
    return _durations[section]


# -- Playback ---------------------------------------------------------------

def _find_player():
    """Command of the first usable player — [] if none is available."""
    global _player
    if _player is None:
        for cmd, args in (
            ("paplay", ["paplay"]),
            ("aplay", ["aplay", "-q"]),
            ("pw-play", ["pw-play"]),
            ("afplay", ["afplay"]),
        ):
            if shutil.which(cmd):
                _player = args
                break
        else:
            _player = ["powershell.exe"] if shutil.which("powershell.exe") else []
    return _player


def available():
    return bool(_find_player())


def _win_path(path):
    """Under WSL, PowerShell needs a Windows path."""
    if shutil.which("wslpath"):
        try:
            return subprocess.run(["wslpath", "-w", path], capture_output=True,
                                  text=True, timeout=5).stdout.strip() or path
        except Exception:
            return path
    return path


def _play_file(path):
    player = _find_player()
    if not player:
        return
    if player[0] == "powershell.exe":
        cmd = player + ["-NoProfile", "-Command",
                        f"(New-Object Media.SoundPlayer '{_win_path(path)}').PlaySync()"]
    else:
        cmd = player + [path]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=30)
    except Exception:
        pass


def _write_wav(samples):
    fd, path = tempfile.mkstemp(prefix="bbs-modem-", suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(RATE)
        fh.writeframes(samples.tobytes())
    return path


_queue_lock = threading.Lock()   # Keeps the sections in order
_render_lock = threading.Lock()  # Only one section is computed at a time
_files = {}                      # Section -> finished WAV file
_stopped = False


def _cleanup():
    for path in _files.values():
        try:
            os.unlink(path)
        except OSError:
            pass


def _render(section):
    """WAV file of the section — computed once, then reused."""
    with _render_lock:
        path = _files.get(section)
        if path:
            return path
        build = SECTIONS.get(section)
        if not build:
            return None
        if not _files:
            atexit.register(_cleanup)
        path = _write_wav(_line_noise(
            _normalize(_telephone(build()), PEAKS.get(section, 0.15))))
        _files[section] = path
        return path


def prerender():
    """Compute all sections ahead of time, in dial-in order. Without this,
    the compute time falls between the on-screen step and the sound — the
    text would race ahead of the sound."""
    if not available():
        return
    threading.Thread(target=lambda: [_render(s) for s in SECTIONS],
                     daemon=True).start()


def play(section):
    """Play a section in the background — sections run one after another,
    not overlapping. Errors stay silent.

    Returns an event that's set as soon as the sound actually starts (or
    it's certain that it won't). The caller times the text by this."""
    started = threading.Event()
    if section not in SECTIONS or not available():
        started.set()
        return started

    def run():
        try:
            path = _render(section)
            with _queue_lock:          # Played in order
                if _stopped or not path:
                    return
                started.set()
                _play_file(path)
        except Exception:
            pass
        finally:
            started.set()

    threading.Thread(target=run, daemon=True).start()
    return started


def stop():
    """Discard any sections still waiting (Ctrl+C during dial-in)."""
    global _stopped
    _stopped = True
