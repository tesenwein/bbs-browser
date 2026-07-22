"""Colors, layout, and parser constants."""

import re
import shutil
import sqlite3

AMBER = "\033[38;5;214m"
GREEN = "\033[38;5;46m"
CYAN = "\033[38;5;51m"
DIM = "\033[2m"
BOLD = "\033[1m"
INVERT = "\033[7m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

# Source for self-updates (the 'up' command): 'up' queries the GitHub
# releases API for the latest release and installs the bundled wheel.
REPO_SLUG = "tesenwein/bbs-browser"
RELEASES_API = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"


_cached_cap = None


def invalidate_layout():
    """Call after changing ui.width: the next screen_width() call will
    read the cap fresh from the database."""
    global _cached_cap
    _cached_cap = None


def _width_cap():
    """Defaults to 80 columns (retro look); a higher ui.width value in the
    database raises the cap. ui.width = 0 means fullscreen: the cap is
    dropped, and only the terminal width counts.

    The result is cached because screen_width() is called very frequently
    by the renderer, and every lookup would otherwise hit the database."""
    global _cached_cap
    if _cached_cap is None:
        try:
            from .db import get_section
            raw = get_section("ui").get("width")
            if raw is None:
                _cached_cap = 80
            else:
                value = int(raw)
                _cached_cap = 10_000 if value <= 0 else max(80, value)
        except (ValueError, TypeError, AttributeError, sqlite3.Error):
            _cached_cap = 80
    return _cached_cap


def screen_width():
    """Current layout width in columns. Deliberately a function and not a
    constant: this way a width change (setting or window resize) takes
    effect immediately, without a restart."""
    return min(shutil.get_terminal_size((80, 24)).columns, _width_cap())


def screen_lines():
    """Usable lines per page (terminal height minus header/footer)."""
    return max(10, shutil.get_terminal_size((80, 24)).lines - 6)

BLOCK_TAGS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "td", "th", "pre", "dt", "dd"]
HEADING_TAGS = {"h1", "h2", "h3"}
NOISE_ROLES = {"navigation", "banner", "contentinfo", "complementary", "search", "dialog", "menu", "menubar"}
SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "#", "data:")
MARKER_RE = re.compile(r"\[\d+\]")

# Character ramp from "empty" to "full". Longer = finer gradation; the
# order must increase monotonically in coverage, otherwise brightness
# gradients invert.
ASCII_RAMP = " .,:;-~=+*oaOX%#@"
# Logos are graphics, not photos: a short, high-contrast ramp with no midtones.
LOGO_RAMP = " .:*#@"

IMG_MODES = ("ascii", "blocks")   # blocks = half-block ▀, double the row resolution
IMG_SETTINGS = ("blocks", "ascii", "off")   # image setting: half-blocks / ASCII / off
HEADER_MODES = ("logo", "banner", "off")    # page header: real logo / random banner / off
LOGO_WIDTH = 48                   # character width of a logo in the header
LOGO_MAX_LINES = 10               # above this the banner turns into a poster

# A link without a block tag counts as a teaser (headline) rather than a
# menu item once it reaches this many characters — below it, every
# "More"/"Contact" would become a paragraph.
TEASER_MIN_CHARS = 25

MAX_IMAGES = 6
MAX_IMAGE_BYTES = 3_000_000
MAX_LINKS = 200

USER_AGENT = "Mozilla/5.0 (BBS-Browser; +retro)"

# Consent-management platforms. These containers NEVER carry page content —
# so they're stripped out without the half-page brake otherwise applied,
# both in the static parser and in Chromium. The list is rounded out with
# two generic patterns that catch homegrown banners.
#
# Deliberately, nothing is clicked away and nothing is consented to: the
# banner is removed, not operated. Whoever doesn't consent isn't tracked either.
CONSENT_SELECTORS = (
    # OneTrust
    "#onetrust-consent-sdk", "#onetrust-banner-sdk", "#ot-sdk-container",
    ".onetrust-pc-dark-filter",
    # Cookiebot
    "#CybotCookiebotDialog", "#CybotCookiebotDialogBodyUnderlay",
    # Usercentrics
    "#usercentrics-root", "#uc-banner-container", "#uc-center-container",
    # Sourcepoint
    '[id^="sp_message_container" i]', '[class^="sp_veil" i]',
    # Quantcast
    ".qc-cmp2-container", ".qc-cmp2-bg", ".qc-cmp-ui-container",
    # Didomi
    "#didomi-host", "#didomi-popup",
    # TrustArc
    "#truste-consent-track", ".truste_overlay", ".truste_box_overlay",
    # Borlabs (WordPress)
    "#BorlabsCookieBox", "#BorlabsCookieBoxWrap",
    # Complianz, CookieYes, cookie-law-info (WordPress)
    "#cmplz-cookiebanner-container", ".cky-consent-container", ".cky-overlay",
    "#cookie-law-info-bar", "#cookie-law-info-again",
    # consentmanager.net
    "#cmpbox", "#cmpbox2", "#cmpwrapper",
    # Google Funding Choices
    ".fc-consent-root", ".fc-dialog-overlay",
    # Osano / cookieconsent
    ".osano-cm-window", ".osano-cm-dialog", ".cc-window", ".cc-banner",
    # Iubenda, Termly, Klaro, CookieScript, tarteaucitron, Axeptio, CookieFirst
    "#iubenda-cs-banner", ".iubenda-cs-container",
    "#termly-code-snippet-support", ".termly-styles-root",
    ".klaro .cookie-modal", ".klaro .cookie-notice",
    "#cookiescript_injected", "#cookiescript_wrapper",
    "#tarteaucitronRoot", "#axeptio_overlay", "#cookiefirst-root",
    # Meta
    '[data-testid="cookie-policy-manage-dialog"]',
    # Homegrown: whole words in id/class, so "content" doesn't match
    '[id*="cookie-banner" i]', '[class*="cookie-banner" i]',
    '[id*="cookie-consent" i]', '[class*="cookie-consent" i]',
    '[id*="cookie-notice" i]', '[class*="cookie-notice" i]',
    '[id*="cookiebanner" i]', '[class*="cookiebanner" i]',
    '[aria-label*="cookie consent" i]', '[aria-describedby*="cookie" i]',
)
