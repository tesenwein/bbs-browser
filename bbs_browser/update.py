"""Self-update: fetch and install the latest release from GitHub.

The 'up' command queries the GitHub releases API for the latest
release, compares its version to the running one, and if needed
reinstalls the bundled wheel — preferably via pipx, otherwise via pip.
No git required; a network connection is enough.

This module also keeps a small cache in the state file (section
"update") so the main menu can show without delay whether a newer
version is available — the network query runs in the background.

Releases are created automatically: on every merge to main, the CI
(.github/workflows/version-bump.yml) builds a wheel and publishes it as
a release, which this command downloads.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from .constants import RELEASES_API
from .i18n import t
from .state import load_section, save_section

# How long a cache entry counts as fresh before it's re-queried in the
# background (seconds). Six hours — the retro look should stay, after all.
_CACHE_TTL = 6 * 3600


def _have(tool):
    return shutil.which(tool) is not None


def _run(cmd):
    """Runs a command and returns (success, output)."""
    try:
        proc = subprocess.run(
            cmd, check=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
        return proc.returncode == 0, (proc.stdout or "").strip()
    except FileNotFoundError:
        return False, t("update.tool_missing", tool=cmd[0])
    except Exception as exc:  # pragma: no cover - OS error
        return False, str(exc)


def _ver_tuple(value):
    """Turns 'v2.5.10' into (2, 5, 10) for a robust version comparison."""
    parts = []
    for chunk in str(value).lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(candidate, current):
    """True if `candidate` is a higher version than `current`."""
    return _ver_tuple(candidate) > _ver_tuple(current)


def _latest_release():
    """Queries the GitHub API for the latest release.

    Returns (tag, download_url, filename) — prefers the wheel, otherwise a
    source archive. On network/API errors, (None, None, None)."""
    try:
        import requests

        resp = requests.get(
            RELEASES_API, timeout=15,
            headers={"Accept": "application/vnd.github+json"},
        )
        if resp.status_code != 200:
            return None, None, None
        data = resp.json()
        tag = data.get("tag_name") or ""
        assets = data.get("assets", []) or []
        for suffixes in ((".whl",), (".tar.gz", ".zip")):
            for asset in assets:
                name = asset.get("name", "")
                if name.endswith(suffixes):
                    return tag, asset.get("browser_download_url"), name
        return tag, None, None
    except Exception:
        return None, None, None


# --- Cache & background check for the main menu --------------------------

def _cache():
    return load_section("update")


def cached_latest():
    """Last known release version from the cache ('' if none)."""
    return _cache().get("latest", "")


def refresh_latest_async():
    """Kicks off a background network query — if the cache is stale.

    Runs as a daemon thread, so it doesn't block startup, and swallows any
    error. The result lands in the cache and becomes visible on the next
    main menu."""
    cache = _cache()
    if time.time() - cache.get("checked", 0) < _CACHE_TTL:
        return

    def worker():
        tag, _, _ = _latest_release()
        data = _cache()
        data["checked"] = int(time.time())
        if tag:
            data["latest"] = tag
        save_section("update", data)

    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception:
        pass


def update_hint(current):
    """Returns the newer version from the cache, or '' — for the UI."""
    latest = cached_latest()
    return latest if latest and is_newer(latest, current) else ""


# --- Installation ----------------------------------------------------------

def _download(url, name):
    """Downloads a file into a temp directory. -> path or None."""
    try:
        import requests

        target = os.path.join(tempfile.mkdtemp(prefix="bbs-update-"), name)
        with requests.get(url, stream=True, timeout=60) as resp:
            if resp.status_code != 200:
                return None
            with open(target, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
        return target
    except Exception:
        return None


def _emit(term, output):
    """Prints collected command output line by line."""
    for ln in (output or "").splitlines():
        term.type_out("  " + ln, delay=0.001)


def _install_detached_windows(term, pkg, use_pipx):
    """Hands the install to a detached console window.

    On Windows the running 'bbs.exe' launcher is locked by the OS, so an
    in-process 'pip install --upgrade' uninstalls the old distribution and
    then fails to write the new one — leaving no importable bbs_browser at
    all (pipx --force has the same problem, it recreates the same venv).
    The helper script therefore waits until this process (and the launcher
    that started it) is gone before it lets the installer touch anything.
    Returns True if the helper could be started."""
    pids = [os.getpid()]
    try:
        parent = os.getppid()
        if parent and parent not in pids:
            pids.append(parent)
    except Exception:  # pragma: no cover - not every platform has getppid
        pass

    lines = [
        "@echo off",
        "title BBS Browser Update",
        "echo Warte, bis BBS Browser geschlossen ist / waiting for BBS Browser to close ...",
        ":wait",
    ]
    for pid in pids:
        lines += [
            # CSV quotes the PID field, so find matches the exact PID and not
            # a longer PID or a memory figure that merely contains the digits.
            'tasklist /FI "PID eq %d" /NH /FO CSV 2>nul | find """%d""" >nul' % (pid, pid),
            "if not errorlevel 1 (",
            "  ping -n 2 127.0.0.1 >nul",
            "  goto wait",
            ")",
        ]
    if use_pipx:
        install = 'pipx install --force "%s"' % pkg
        extras = [
            "pipx inject bbs-browser anthropic openai pyfiglet rich",
        ]
        # We are running out of that very venv, so sys.executable is the right
        # interpreter even before pipx has rebuilt it.
        chromium = _pipx_python() or sys.executable
    else:
        # --force-reinstall: a previous half-finished update may have left the
        # metadata behind, and pip would then consider the version installed.
        install = '"%s" -m pip install --upgrade --force-reinstall "%s"' % (
            sys.executable, pkg)
        extras = ['"%s" -m pip install --upgrade anthropic openai' % sys.executable]
        chromium = sys.executable

    lines += [
        # A moment of grace: the launcher releases its handles only after exit.
        "ping -n 3 127.0.0.1 >nul",
        "echo Installiere / installing ...",
        # Up to three attempts: a virus scanner or an Explorer window can hold
        # a handle for a moment, and a failed run must not leave a half
        # uninstalled package behind.
        "set BBS_TRY=0",
        ":install",
        "set /a BBS_TRY+=1",
        install,
        "if not errorlevel 1 goto ok",
        "if %BBS_TRY% GEQ 3 goto failed",
        "echo Erneuter Versuch / retrying ...",
        "ping -n 4 127.0.0.1 >nul",
        "goto install",
        ":ok",
    ]
    lines += extras
    if chromium:
        lines.append('"%s" -m playwright install chromium' % chromium)
    lines += [
        "echo.",
        "echo OK - jetzt 'bbs' neu starten / start 'bbs' again.",
        "pause",
        "exit /b 0",
        ":failed",
        "echo.",
        "echo FEHLER / ERROR - Installation fehlgeschlagen.",
        "pause",
        "exit /b 1",
    ]

    try:
        script = os.path.join(tempfile.mkdtemp(prefix="bbs-update-"), "finish-update.cmd")
        # cmd.exe parses batch files in the console's OEM codepage — with
        # plain ASCII an umlaut in the path (C:\Users\Müller\...) would be
        # mangled to '?' and the install commands would point nowhere.
        encoding = "oem" if os.name == "nt" else "ascii"
        with open(script, "w", encoding=encoding, errors="replace") as f:
            f.write("\r\n".join(lines) + "\r\n")
        # DETACHED from our console, but with its own window so the user sees
        # the progress after hanging up.
        new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        try:
            subprocess.Popen(["cmd", "/c", script],
                             creationflags=new_console | breakaway,
                             close_fds=True)
        except OSError:
            # Some hosts (Windows Terminal, CI) run us in a job object that
            # forbids breakaway — then a plain new console still outlives us,
            # only a killed job would take the helper down with it.
            subprocess.Popen(["cmd", "/c", script],
                             creationflags=new_console, close_fds=True)
        return True
    except Exception as exc:
        _emit(term, str(exc))
        return False


def _install(term, pkg):
    """Installs the downloaded package — pipx preferred, otherwise pip."""
    pipx = _have("pipx")

    if os.name == "nt":
        # Windows locks the running launcher — see _install_detached_windows.
        term.type_out(
            t("update.installing_pipx" if pipx else "update.installing_pip"),
            delay=0.003,
        )
        return "detached" if _install_detached_windows(term, pkg, pipx) else False

    if pipx:
        term.type_out(t("update.installing_pipx"), delay=0.003)
        ok, out = _run(["pipx", "install", "--force", pkg])
        _emit(term, out)
        if ok:
            # Pull in the AI SDKs (as in the Makefile) — failure is not fatal.
            _, inj_out = _run(["pipx", "inject", "bbs-browser", "anthropic", "openai"])
            _emit(term, inj_out)
            _install_chromium()
        return ok

    term.type_out(t("update.installing_pip"), delay=0.003)
    ok, out = _run([sys.executable, "-m", "pip", "install", "--upgrade", pkg])
    _emit(term, out)
    if ok:
        _run([sys.executable, "-m", "pip", "install", "--upgrade", "anthropic", "openai"])
        _install_chromium()
    return ok


def _install_chromium():
    """Pulls in Chromium for JS rendering. If it's already there, the call
    takes seconds; if not, it downloads ~150 MB. A failure is not fatal —
    fetching then falls back to plain HTTP.

    The pipx case deliberately invokes the same Python: the browser builds
    are tied to the Playwright version, a foreign 'playwright' would fetch
    the wrong one."""
    python = _pipx_python() if _have("pipx") else sys.executable
    if not python:
        return
    _run([python, "-m", "playwright", "install", "chromium"])


def _pipx_python():
    """Interpreter of bbs-browser's pipx venv, if present."""
    home = os.environ.get("PIPX_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share", "pipx")
    venv = os.path.join(home, "venvs", "bbs-browser")
    # POSIX venvs put the interpreter in bin/, Windows venvs in Scripts/.
    for rel in (("bin", "python"), ("Scripts", "python.exe")):
        path = os.path.join(venv, *rel)
        if os.path.exists(path):
            return path
    return None


def _remember(tag):
    """Keeps the cache current after a query, so the hint stays accurate."""
    data = _cache()
    data["checked"] = int(time.time())
    data["latest"] = tag
    save_section("update", data)


def run_update(term):
    """Entry point for the 'up' command."""
    from .nostalgia import version

    term.rule(t("update.title"))
    current = version()
    term.type_out(t("update.current", version=current), delay=0.003)
    term.type_out(t("update.checking"), delay=0.003)

    tag, url, name = _latest_release()
    if not tag:
        term.error(t("update.no_release"))
        term.rule()
        return
    _remember(tag)

    if not is_newer(tag, current):
        term.type_out(t("update.up_to_date", version=current), delay=0.003)
        term.rule()
        return

    if not url:
        term.error(t("update.no_asset", version=tag))
        term.rule()
        return

    term.type_out(t("update.found", version=tag), delay=0.003)
    term.type_out(t("update.downloading", name=name), delay=0.003)
    path = _download(url, name)
    if not path:
        term.error(t("update.download_failed"))
        term.rule()
        return

    result = _install(term, path)
    if not result:
        term.error(t("update.install_failed"))
        term.rule()
        return

    if result == "detached":
        # Nothing is installed yet: the helper waits for us to hang up.
        term.type_out(t("update.pending_windows", version=tag), delay=0.003)
        term.rule()
        return

    term.type_out(t("update.done", version=tag), delay=0.003)
    term.type_out(t("update.restart_hint"), delay=0.003)
    term.rule()
