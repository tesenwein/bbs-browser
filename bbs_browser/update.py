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


def _install(term, pkg):
    """Installs the downloaded package — pipx preferred, otherwise pip."""
    if _have("pipx"):
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

    if not _install(term, path):
        term.error(t("update.install_failed"))
        term.rule()
        return

    term.type_out(t("update.done", version=tag), delay=0.003)
    term.type_out(t("update.restart_hint"), delay=0.003)
    term.rule()
