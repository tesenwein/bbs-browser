"""Render images as ASCII art.

The path from pixel to character in four steps:

  1. Load    — orientation from EXIF, transparency flattened onto white, grayscale
  2. Enhance — autocontrast, gamma, light sharpening
  3. Scale   — area averaging (LANCZOS), characters are taller than wide
  4. Map     — Floyd-Steinberg onto the character ramp, or half-blocks

Step 2 is by far the biggest win: most web images only use part of the
value range, and without autocontrast half the ramp goes unused and
everything looks uniformly gray.
"""

import colorsys
import os
from bisect import bisect
from io import BytesIO

import requests
from PIL import Image, ImageFilter, ImageOps

from .colors import phosphor_rgb
from .constants import (
    ASCII_RAMP, LOGO_MAX_LINES, LOGO_RAMP, LOGO_WIDTH, MAX_IMAGE_BYTES,
    RESET, USER_AGENT,
)

# Pre-filter: which images aren't worth showing?
SKIP_URL_PATTERNS = (
    "logo", "icon", "sprite", "pixel", "tracker", "tracking", "spacer",
    "avatar", "badge", "button", "bullet", "1x1", "blank", ".svg", "favicon",
    "emoji", "smiley", "counter",
)
MIN_SOURCE_W = 100      # smaller = icon/pixel, don't show
MIN_SOURCE_H = 60
MAX_ASPECT = 6.0        # skip extremely wide/narrow banner strips
MIN_STDDEV = 18.0       # near-uniform areas produce empty ASCII art

ASPECT = 0.5            # a character cell is roughly twice as tall as wide
WORK_FACTOR = 4         # working size = target grid x4 (headroom for edges)
LOGO_MIN_WIDTH = 16     # narrower than this and every logo turns into a blob
IMG_MIN_WIDTH = 24      # below this width a capped image turns into a blob
LOGO_INK_LEVEL = 24     # below this a pixel of the ink mask counts as empty
GAMMA = 0.75            # character density isn't linear to perception
AUTOCONTRAST_CUTOFF = 2  # percent per end — clips outliers, not the image
HALF_BLOCK = "▀"

_GAMMA_LUT = [min(255, int((i / 255.0) ** GAMMA * 255 + 0.5)) for i in range(256)]
_UNSHARP = ImageFilter.UnsharpMask(radius=2, percent=90, threshold=3)


# -- Pre-selection -------------------------------------------------------

def worth_fetching(src, alt="", attr_w=None, attr_h=None):
    """Pre-check without downloading: filters out icons, logos, pixels, etc."""
    haystack = (src + " " + alt).lower()
    if any(p in haystack for p in SKIP_URL_PATTERNS):
        return False
    try:
        if attr_w is not None and int(attr_w) < MIN_SOURCE_W:
            return False
        if attr_h is not None and int(attr_h) < MIN_SOURCE_H:
            return False
    except (ValueError, TypeError):
        pass
    return True


def _worth_showing(img, orig_size):
    """After download: too small, extreme aspect ratio, or too little contrast?
    Size and aspect ratio are measured on the original — the working copy
    is deliberately downscaled and wouldn't be a valid reference here."""
    w, h = orig_size
    if w < MIN_SOURCE_W or h < MIN_SOURCE_H:
        return False
    aspect = w / h if h else 99
    if aspect > MAX_ASPECT or aspect < 1 / MAX_ASPECT:
        return False
    # Check contrast on a downscaled copy (fast enough)
    pw, ph = img.size
    probe = img.resize((min(64, pw), min(64, ph)))
    pixels = list(probe.getdata())
    mean = sum(pixels) / len(pixels)
    variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
    return variance ** 0.5 >= MIN_STDDEV


# -- Loading and enhancing -----------------------------------------------

def _flatten(img):
    """Flatten transparency onto white. Without this, every cut-out area
    turns pitch black — for logos, exactly the part meant to stay empty."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img)
    return img


def _work_box(width, rows_per_char=1):
    """Working size: a multiple of the target grid. No need for anything
    finer — in the end it's one character per cell anyway."""
    return (width * WORK_FACTOR, round(width * ASPECT * rows_per_char) * WORK_FACTOR)


def _load(img_bytes, box=None):
    """Bytes -> (upright grayscale image, original size), or (None, None).

    Downscales to the working size right at load time: running autocontrast,
    gamma, and an unsharp mask on a 4000-pixel original costs a multiple of
    that and doesn't change the result. For JPEG, draft() lets the decoder
    handle it, saving most of the work.

    The original size travels along because the suitability check needs it —
    it should judge the real image, not our working copy."""
    try:
        img = Image.open(BytesIO(img_bytes))
        orig_size = img.size
        if box:
            img.draft("L", box)          # JPEG only, no effect otherwise
        img.load()
        img = ImageOps.exif_transpose(img) or img
        img = _flatten(img).convert("L")
        if box and (img.size[0] > box[0] or img.size[1] > box[1]):
            img.thumbnail(box, Image.LANCZOS)
    except Exception:
        return None, None
    return (img, orig_size) if img.size[0] and img.size[1] else (None, None)


def _enhance(img, sharpen=True):
    img = ImageOps.autocontrast(img, cutoff=AUTOCONTRAST_CUTOFF)
    img = img.point(_GAMMA_LUT)
    # Sharpen before the heavy downscale: otherwise the edges blur, and
    # they're later the only cue for a character's shape.
    return img.filter(_UNSHARP) if sharpen else img


def _scaled(img, width, rows_per_char=1):
    """Downscale to the character grid. LANCZOS averages correctly — the
    default interpolation used previously left aliasing at a 20:1 factor."""
    w, h = img.size
    new_h = max(1, round(h / w * width * ASPECT * rows_per_char))
    return img.resize((width, new_h), Image.LANCZOS)


# -- Mapping onto characters ---------------------------------------------

def _dither(pixels, w, h, levels):
    """Floyd-Steinberg in a serpentine pass: spreads the quantization error
    to the neighbors, producing intermediate tones that a ramp with only a
    handful of levels doesn't have on its own. Serpentine instead of
    row-by-row, otherwise visible diagonal stripes appear."""
    buf = [float(p) for p in pixels]
    step = 255.0 / (levels - 1)
    out = [0] * (w * h)
    for y in range(h):
        forward = y % 2 == 0
        ahead = 1 if forward else -1
        for x in (range(w) if forward else range(w - 1, -1, -1)):
            i = y * w + x
            level = min(levels - 1, max(0, round(buf[i] / step)))
            out[i] = level
            err = buf[i] - level * step
            if 0 <= x + ahead < w:
                buf[i + ahead] += err * 7 / 16
            if y + 1 < h:
                j = i + w
                if 0 <= x - ahead < w:
                    buf[j - ahead] += err * 3 / 16
                buf[j] += err * 5 / 16
                if 0 <= x + ahead < w:
                    buf[j + ahead] += err * 1 / 16
    return out


def _ascii_lines(img, width, ramp=ASCII_RAMP, dither=True):
    img = _scaled(img, width)
    w, h = img.size
    data = list(img.getdata())
    levels = (_dither(data, w, h, len(ramp)) if dither
              else [min(len(ramp) - 1, p * len(ramp) // 256) for p in data])
    return ["".join(ramp[v] for v in levels[r * w:(r + 1) * w]) for r in range(h)]


def _luma_rows(img, width):
    """Half-block mode: two image rows per text line, i.e. double the
    vertical resolution. Returns raw luminance values — coloring happens
    only at render time, once the page's phosphor tone is known."""
    img = _scaled(img, width, rows_per_char=2)
    w, h = img.size
    h -= h % 2                      # an odd last row would have no partner
    data = list(img.getdata())
    return [data[y * w:(y + 1) * w] for y in range(h)]


def halfblock_lines(luma_rows, term_color):
    """Luminance grid -> ▀ lines in the terminal's phosphor tone.
    The upper image row colors the foreground, the lower one the background.

    Only a terminal that COLORTERM says supports it gets 24-bit color. All
    others (Apple Terminal, tmux without Tc, older emulators) silently round
    every 38;2 sequence down to their 256-color palette — turning smooth
    gradients into coarse stripes across the image. For those we build our
    own palette ramp for the phosphor tone, dithered instead of striped."""
    base = phosphor_rgb(term_color)
    if not _truecolor():
        return _halfblock_lines_256(luma_rows, base)
    out = []
    for y in range(0, len(luma_rows) - 1, 2):
        parts, prev = [], None
        for top, bottom in zip(luma_rows[y], luma_rows[y + 1]):
            # Quantize to 32 levels: an imperceptibly fine difference, but
            # noticeably fewer escape-sequence changes per line.
            key = (top >> 3, bottom >> 3)
            if key != prev:
                fr, fg, fb = _tint(base, key[0] * 8 + 4)
                br, bg, bb = _tint(base, key[1] * 8 + 4)
                parts.append(f"\033[38;2;{fr};{fg};{fb}m\033[48;2;{br};{bg};{bb}m")
                prev = key
            parts.append(HALF_BLOCK)
        out.append("".join(parts) + RESET)
    return out


def _truecolor():
    """Can the terminal do 24-bit color? The de facto signal is COLORTERM —
    set by every emulator that can actually render 38;2 sequences."""
    return os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")


def _halfblock_lines_256(luma_rows, base):
    """Same image for terminals with a 256-color palette. There, a phosphor
    tone's ramp only has a handful of levels — without dithering every
    gradient would fall apart into stripes, so Floyd-Steinberg spreads the
    error instead."""
    if not luma_rows:
        return []
    ramp = _ramp256(base)
    idx = [i for _, i in ramp]
    levels = _dither_targets(luma_rows, [v for v, _ in ramp])
    w = len(luma_rows[0])
    out = []
    for y in range(0, len(luma_rows) - 1, 2):
        parts, prev = [], None
        for x in range(w):
            key = (levels[y * w + x], levels[(y + 1) * w + x])
            if key != prev:
                parts.append(f"\033[38;5;{idx[key[0]]}m\033[48;5;{idx[key[1]]}m")
                prev = key
            parts.append(HALF_BLOCK)
        out.append("".join(parts) + RESET)
    return out


# 256-color cube: the six channel steps used by xterm and all its imitators.
_CUBE_STEPS = (0, 95, 135, 175, 215, 255)
_RAMP_CACHE = {}


def _ramp256(base):
    """Luminance ramp of a phosphor tone in the 256-color palette, as an
    ascending list of (luminance 0..255, color index).

    A candidate is any cube entry whose hue and saturation lie close to the
    phosphor — not simply the nearest match per luminance level: that would
    pick up a red or olive tint at dark tones, and outliers like that would
    then discolor whole regions of the image. Better to have fewer levels
    that stay true to the tone; dithering bridges the gaps between them."""
    if base not in _RAMP_CACHE:
        base_h, base_s, _ = colorsys.rgb_to_hsv(*(c / 255 for c in base))
        full = _luminance(base) or 1.0
        ramp = [(0, 16)]                      # black belongs to every ramp
        for n in range(216):
            rgb = (_CUBE_STEPS[n // 36], _CUBE_STEPS[n // 6 % 6], _CUBE_STEPS[n % 6])
            h, s, _ = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            value = round(255 * _luminance(rgb) / full)
            if (min(abs(h - base_h), 1 - abs(h - base_h)) > 0.05
                    or abs(s - base_s) > 0.38 or not 0 < value <= 255):
                continue
            ramp.append((value, 16 + n))
        ramp.sort()
        # Same luminance twice (rounding): one level is enough.
        _RAMP_CACHE[base] = [entry for i, entry in enumerate(ramp)
                             if not i or entry[0] > ramp[i - 1][0]]
    return _RAMP_CACHE[base]


def _luminance(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _dither_targets(rows, targets):
    """Floyd-Steinberg in a serpentine pass like _dither, but against an
    irregular list of levels — the palette ramp doesn't have even spacing.
    Returns: level index per pixel, flattened row by row."""
    w, h = len(rows[0]), len(rows)
    buf = [float(p) for row in rows for p in row]
    out = [0] * (w * h)
    for y in range(h):
        forward = y % 2 == 0
        ahead = 1 if forward else -1
        for x in (range(w) if forward else range(w - 1, -1, -1)):
            i = y * w + x
            k = bisect(targets, buf[i])
            if k and (k == len(targets) or buf[i] - targets[k - 1] <= targets[k] - buf[i]):
                k -= 1
            out[i] = k
            err = buf[i] - targets[k]
            if 0 <= x + ahead < w:
                buf[i + ahead] += err * 7 / 16
            if y + 1 < h:
                j = i + w
                if 0 <= x - ahead < w:
                    buf[j - ahead] += err * 3 / 16
                buf[j] += err * 5 / 16
                if 0 <= x + ahead < w:
                    buf[j + ahead] += err * 1 / 16
    return out


def _tint(rgb, level):
    return tuple(int(c * level / 255) for c in rgb)


# -- Public interface -----------------------------------------------------

def render_image(img_bytes, width=60, mode="blocks", max_lines=None):
    """Image bytes -> block payload for the page, or None.

    ascii  -> {"lines": [...]}
    blocks -> {"luma": [[...]]} — coloring happens later, at render time

    max_lines caps the image height in text lines: a tall image at full
    width would otherwise be taller than a screen page, and the MORE prompt
    would cut right through it (instead of cleanly before it). As with the
    logo (render_logo), the cap reduces the width until the height fits —
    the line count scales linearly with width because the aspect ratio is
    fixed.
    """
    rows_per_char = 2 if mode == "blocks" else 1
    img, orig_size = _load(img_bytes, box=_work_box(width, rows_per_char))
    if img is None or not _worth_showing(img, orig_size):
        return None
    img = _enhance(img)
    if max_lines:
        w, h = img.size
        # Text lines at full width — round(h/w * width * ASPECT) in both modes:
        # half-block mode works at double the image resolution, but folds the
        # two image rows back into a single text line.
        text_lines = max(1, round(h / w * width * ASPECT))
        if text_lines > max_lines:
            width = max(IMG_MIN_WIDTH, int(width * max_lines / text_lines))
    if mode == "blocks":
        rows = _luma_rows(img, width)
        return {"luma": rows} if rows else None
    return {"lines": _ascii_lines(img, width)}


def _get(url):
    """Fetch an image — with a hard cap. It used to be truncated bluntly at
    MAX_IMAGE_BYTES; but a half-downloaded JPEG stream can't be decoded, so
    the image would silently drop out. Better not to load it at all than
    to load it broken."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10, stream=True)
    resp.raise_for_status()
    buf = bytearray()
    for chunk in resp.iter_content(65536):
        buf += chunk
        if len(buf) > MAX_IMAGE_BYTES:
            return None
    return bytes(buf)


_RENDER_CACHE = {}          # (url, width, mode) -> rendered image
_RENDER_CACHE_MAX = 64


def fetch_image(url, width=60, mode="blocks", max_lines=None):
    """Fetch an image and typeset it in characters. The result is cached
    in-process: a page gets built twice on the style-profile path (once
    plain, once profiled) — without the cache each image would be fetched
    over the wire twice for that."""
    key = (url, width, mode, max_lines)
    if key in _RENDER_CACHE:
        return _RENDER_CACHE[key]
    try:
        data = _get(url)
        art = render_image(data, width=width, mode=mode, max_lines=max_lines) if data else None
    except Exception:
        return None
    if len(_RENDER_CACHE) >= _RENDER_CACHE_MAX:
        _RENDER_CACHE.pop(next(iter(_RENDER_CACHE)))
    _RENDER_CACHE[key] = art
    return art


# -- Logos ------------------------------------------------------------------

def _autocrop(img):
    """Crop away margins with no content. Logo files almost always come
    with generous whitespace around them — left uncropped, the header
    would show a postage-stamp-sized logo in a lot of nothing."""
    mask = img.point(lambda p: 255 if p > 40 else 0)
    box = mask.getbbox()
    return img.crop(box) if box else img


def _ink_mask(img_bytes, box):
    """Logo -> grayscale image where LIGHT is the mark and DARK is the
    background. Exactly the reverse of a photo, because the character
    ramp leaves dark areas empty — and here that should be the background.

    Two candidates compete, and the one with more internal detail wins:
    * Luminance — a light border means a dark mark on a light background,
      so it gets inverted. Carries internal shapes (letters in a wordmark).
    * Coverage (alpha channel) — the pure silhouette. Unbeatable for a
      multicolor wordmark like python.org's, which nearly disappears in
      grayscale; useless for a touch icon whose alpha only traces the
      rounded tile and swallows the mark inside it."""
    try:
        img = Image.open(BytesIO(img_bytes))
        img.draft("L", box)
        img.load()
        img = ImageOps.exif_transpose(img) or img
        if img.size[0] > box[0] or img.size[1] > box[1]:
            img.thumbnail(box, Image.LANCZOS)
    except Exception:
        return None
    if not (img.size[0] and img.size[1]):
        return None

    gray = ImageOps.autocontrast(_flatten(img).convert("L"), cutoff=1)
    candidates = [ImageOps.invert(gray) if _border_is_bright(gray) else gray]
    if _has_alpha(img):
        alpha = img.convert("RGBA").getchannel("A")
        # A uniformly opaque alpha channel carries no information.
        if alpha.getextrema()[0] < 250:
            candidates.append(ImageOps.autocontrast(alpha, cutoff=1))
    return max(candidates, key=_structure)


def _has_alpha(img):
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)


def _structure(mask):
    """How much internal detail does the mask carry? A bare silhouette has
    only an outline, while a real logo also has edges inside it — and
    that's exactly what makes the difference between a logo and a blob."""
    w, h = mask.size
    if w < 3 or h < 3:
        return 0.0
    # An edge filter's border pixels are undefined, so crop them off.
    edges = mask.filter(ImageFilter.FIND_EDGES).crop((1, 1, w - 1, h - 1))
    data = edges.getdata()
    return sum(data) / len(data)


def render_logo(img_bytes, width=LOGO_WIDTH, max_lines=LOGO_MAX_LINES, mode="blocks"):
    """Logo -> payload for the page header, or None.

    ascii  -> {"lines": [...]}
    blocks -> {"luma": [[...]]} — half-blocks, i.e. double the vertical
              resolution; coloring happens only in the header (halfblock_lines).
              A wordmark's legibility hinges exactly on this: over ten
              lines, twenty image rows are the difference between readable
              text and a blob.

    The logo pre-processing stays the same in both cases, which is why this
    doesn't just call render_image: a mark needs the ink mask (light =
    mark), cropping down to that mark, and the ink check that filters out
    meaningless silhouettes."""
    # More generous working size than for a photo: only after cropping to
    # the mark itself is it clear how much of the image actually remains.
    img = _ink_mask(img_bytes, _work_box(width * 2, 2))
    if img is None:
        return None
    img = _autocrop(img)
    w, h = img.size
    if not w or not h:
        return None
    rows_per_char = 2 if mode == "blocks" else 1
    # Height caps the width: a square logo at full width would otherwise
    # be taller than the whole banner.
    lines_at_full = max(1, round(h / w * width * ASPECT))
    if lines_at_full > max_lines:
        width = max(LOGO_MIN_WIDTH, int(width * max_lines / lines_at_full))
    img = img.filter(_UNSHARP)

    if mode != "blocks":
        lines = _ascii_lines(img, width, ramp=LOGO_RAMP, dither=False)
        if not lines or not _logo_has_substance(
            sum(1 for ln in lines for ch in ln if ch != " "),
            len(lines) * len(lines[0]),
        ):
            return None
        return {"lines": _trim_blank(lines, max_lines)}

    rows = _luma_rows(img, width)
    if not rows:
        return None
    # Same ink check as above, just on the luminance grid: what counted as
    # "not empty" for a character here means "not dark".
    lit = sum(1 for row in rows for p in row if p > LOGO_INK_LEVEL)
    if not _logo_has_substance(lit, len(rows) * len(rows[0])):
        return None
    return {"luma": _trim_blank_rows(rows, max_lines)}


def _logo_has_substance(ink, area):
    """A logo that's nearly empty or nearly solid says nothing. Measured
    over the full grid area — not just between the first and last
    character of each line, otherwise every line would count as full."""
    return 0.05 < ink / max(1, area) < 0.9


def _trim_blank(lines, max_lines):
    """Strip blank lines top/bottom but keep the grid width: trimming on
    the right would make the header center each line individually and
    distort the logo."""
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines[:max_lines]


def _trim_blank_rows(rows, max_lines):
    """Same thing for the luminance grid — but always in pairs, since two
    image rows share one text line."""
    def dark(row):
        return all(p <= LOGO_INK_LEVEL for p in row)

    while len(rows) >= 2 and dark(rows[0]) and dark(rows[1]):
        del rows[:2]
    while len(rows) >= 2 and dark(rows[-1]) and dark(rows[-2]):
        del rows[-2:]
    return rows[:max_lines * 2]


def _border_is_bright(img):
    """Average brightness of the image border — a logo's background."""
    w, h = img.size
    probe = img.resize((min(32, w), min(32, h)))
    pw, ph = probe.size
    px = probe.load()
    edge = ([px[x, 0] for x in range(pw)] + [px[x, ph - 1] for x in range(pw)]
            + [px[0, y] for y in range(ph)] + [px[pw - 1, y] for y in range(ph)])
    return sum(edge) / len(edge) > 127


def fetch_logo(url, width=LOGO_WIDTH, max_lines=LOGO_MAX_LINES, mode="blocks"):
    try:
        data = _get(url)
        return render_logo(data, width=width, max_lines=max_lines, mode=mode) if data else None
    except Exception:
        return None
