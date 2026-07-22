#!/usr/bin/env bash
#
# BBS Browser 1985 — Ein-Zeilen-Installer.
#
#   curl -fsSL https://raw.githubusercontent.com/tesenwein/bbs-browser/main/install.sh | bash
#
# Laedt das neueste Release-Wheel von GitHub und installiert das Kommando 'bbs'
# — bevorzugt ueber pipx, sonst in ein eigenes venv unter
# ~/.local/share/bbs-browser mit Symlink nach ~/.local/bin. Beide Wege bringen
# das KI-SDK ([ai]-Extra bzw. 'pipx inject anthropic') gleich mit, genau wie
# 'make install' und der browserinterne Befehl 'up'.
#
# Kein git und kein Checkout noetig — es genuegt python3 und Netzzugang.

set -euo pipefail

REPO="${BBS_REPO:-tesenwein/bbs-browser}"
API="https://api.github.com/repos/${REPO}/releases/latest"
PREFIX="${BBS_PREFIX:-$HOME/.local/share/bbs-browser}"
BINDIR="${BBS_BINDIR:-$HOME/.local/bin}"

say()  { printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }
die()  { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

say "CARRIER 2400 — BBS Browser 1985 Installer"

# --- Voraussetzungen -------------------------------------------------------
find_python() {
    for cand in python3 python; do
        if have "$cand"; then PYTHON="$cand"; return 0; fi
    done
    return 1
}

# Python fehlt: ueber den jeweiligen System-Paketmanager nachinstallieren.
# Braucht ggf. sudo (Linux) — auf macOS reicht Homebrew ohne Root.
install_python() {
    say "python3 nicht gefunden — versuche Installation ..."
    case "$(uname -s)" in
        Darwin)
            if have brew; then
                brew install python3
            else
                die "Homebrew nicht gefunden — bitte von https://brew.sh installieren, dann erneut versuchen (oder Python direkt von https://python.org laden)."
            fi
            ;;
        Linux)
            if have apt-get; then
                sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
            elif have dnf; then
                sudo dnf install -y python3 python3-pip
            elif have pacman; then
                sudo pacman -Sy --noconfirm python python-pip
            elif have apk; then
                sudo apk add --no-cache python3 py3-pip
            elif have zypper; then
                sudo zypper install -y python3 python3-pip
            else
                die "kein bekannter Paketmanager gefunden — bitte Python 3.9+ manuell installieren."
            fi
            ;;
        *)
            die "unbekanntes Betriebssystem — bitte Python 3.9+ manuell installieren."
            ;;
    esac
}

PYTHON=""
if ! find_python; then
    install_python
    find_python || die "Python-Installation fehlgeschlagen — bitte Python 3.9+ manuell installieren."
fi

have curl || have wget || die "weder curl noch wget gefunden."

fetch() {  # fetch <url> -> stdout
    if have curl; then curl -fsSL "$1"
    else wget -qO- "$1"; fi
}
download() {  # download <url> <zieldatei>
    if have curl; then curl -fsSL -o "$2" "$1"
    else wget -qO "$2" "$1"; fi
}

# --- Neueste Release ermitteln ---------------------------------------------
say "Frage neueste Version bei GitHub an ..."
RELEASE_JSON="$(fetch "$API")" || die "GitHub-Releases-API nicht erreichbar."

TAG="$(printf '%s' "$RELEASE_JSON" \
    | grep -m1 '"tag_name"' | sed -E 's/.*"tag_name"[^"]*"([^"]+)".*/\1/')"
WHEEL_URL="$(printf '%s' "$RELEASE_JSON" \
    | grep -oE '"browser_download_url"[^"]*"[^"]+\.whl"' \
    | head -n1 | sed -E 's/.*"(https[^"]+)".*/\1/')"

[ -n "$TAG" ] || die "keine Release gefunden (Repo $REPO)."
[ -n "$WHEEL_URL" ] || die "Release $TAG enthaelt kein Wheel."

WHEEL_NAME="${WHEEL_URL##*/}"
say "Neueste Version: $TAG"

# --- Wheel herunterladen ---------------------------------------------------
TMPDIR="$(mktemp -d "${TMPDIR:-/tmp}/bbs-install.XXXXXX")"
trap 'rm -rf "$TMPDIR"' EXIT
WHEEL_PATH="$TMPDIR/$WHEEL_NAME"

say "Lade $WHEEL_NAME ..."
download "$WHEEL_URL" "$WHEEL_PATH" || die "Download fehlgeschlagen."

# --- Installieren: pipx bevorzugt, sonst eigenes venv ----------------------
# Chromium fuer das JS-Rendering. Das pip-Paket bringt nur die Bindings — das
# Browser-Binary (~150 MB) muss separat geladen werden. Schlaegt das fehl,
# laeuft der Browser trotzdem, nur eben ohne JS.
# Wichtig: den Download mit GENAU dem Python anstossen, in dem playwright
# installiert wurde — die Browser-Builds sind an die Playwright-Version
# gebunden, ein fremdes 'playwright' laedt sonst den falschen Build.
install_chromium() {  # install_chromium <python>
    say "Lade Chromium fuer JS-Rendering (~150 MB) ..."
    "$1" -m playwright install chromium \
        || warn "Hinweis: Chromium-Download fehlgeschlagen — Seiten mit JS bleiben leer, bis 'playwright install chromium' laeuft."
}

if have pipx; then
    say "Installiere mit pipx (inkl. KI-SDK) ..."
    pipx install --force "$WHEEL_PATH"
    pipx inject --force bbs-browser anthropic openai pyfiglet rich || warn "Hinweis: 'anthropic'/'openai'/'pyfiglet'/'rich' nicht nachgezogen — KI-SysOp bleibt aus, bis 'pipx inject bbs-browser anthropic openai pyfiglet rich' laeuft."
    PIPX_PY="${PIPX_HOME:-$HOME/.local/share/pipx}/venvs/bbs-browser/bin/python"
    if [ -x "$PIPX_PY" ]; then
        install_chromium "$PIPX_PY"
    else
        warn "Hinweis: pipx-venv nicht gefunden — JS-Rendering erst nach 'playwright install chromium'."
    fi
    BIN="$(command -v bbs || true)"
else
    say "pipx nicht gefunden — installiere nach $PREFIX ..."
    "$PYTHON" -m venv --clear "$PREFIX"
    "$PREFIX/bin/pip" install -q --upgrade pip
    # Extras lassen sich direkt aus dem Wheel-Pfad ziehen: KI-SDK kommt mit.
    "$PREFIX/bin/pip" install -q "${WHEEL_PATH}[ai]"
    install_chromium "$PREFIX/bin/python"
    mkdir -p "$BINDIR"
    ln -sf "$PREFIX/bin/bbs" "$BINDIR/bbs"
    BIN="$BINDIR/bbs"
    case ":$PATH:" in
        *":$BINDIR:"*) ;;
        *) warn "Hinweis: $BINDIR liegt nicht in PATH — Zeile in ~/.profile o.ae. ergaenzen:"
           warn "         export PATH=\"$BINDIR:\$PATH\"" ;;
    esac
fi

say ""
say "CONNECT — 'bbs' installiert${BIN:+ ($BIN)}."
say "Loslegen:  bbs            (Hauptmenue)"
say "           bbs heise.de   (Seite direkt anwaehlen)"
