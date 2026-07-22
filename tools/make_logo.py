"""Zeichnet Logo und App-Icon im Stil des Intro-Banners.

Die Zeichen stammen aus bbs_browser/wordmark.py — dieselbe Blockschrift, die
das Terminal beim Logon druckt. Der Vollblock wird zum gefuellten Rechteck,
die Rahmenzeichen dahinter zu Linienstuecken: das ist der Schlagschatten der
alten ANSI-Logos.

Eine Zelle ist doppelt so hoch wie breit — so steht das Logo in denselben
Proportionen wie im Terminal, wo genau das die Zeichenzelle ist.

Das SVG ist die einzige Quelle; die PNGs werden daraus gerastert, damit beide
Formate nie auseinanderlaufen koennen.

Aufruf: python3 tools/make_logo.py  ->  schreibt nach assets/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Eine Quelle fuer Terminal und Grafik: die Marke kommt aus dem Paket, damit
# Blockschrift und Logo nie auseinanderlaufen.
from bbs_browser.wordmark import COMPACT, FULL, cells  # noqa: E402

AMBER = "#F0A93C"
INK = "#1D1D20"

TAGLINE = "\u00b7:\u00b7 E L E C T R O N I C   M A I L B O X \u00b7:\u00b7 since 1985 \u00b7:\u00b7"

# Welche Linienstuecke ein Rahmenzeichen in seiner Zelle zieht, in Anteilen
# der Zellbreite/-hoehe. Die Mitte ist (0.5, 0.5) — dort treffen sich Ecken.
SEGMENTS = {
    "\u2550": (((0, .5), (1, .5)),),
    "\u2551": (((.5, 0), (.5, 1)),),
    "\u2554": (((.5, 1), (.5, .5)), ((.5, .5), (1, .5))),
    "\u2557": (((.5, 1), (.5, .5)), ((0, .5), (.5, .5))),
    "\u255a": (((.5, 0), (.5, .5)), ((.5, .5), (1, .5))),
    "\u255d": (((.5, 0), (.5, .5)), ((0, .5), (.5, .5))),
}


def wordmark(art, cw, sx, sy):
    """Die Marke als SVG-Gruppe; gibt (svg, breite, hoehe) zurueck."""
    fill, shadow, cols, rows = cells(art)
    ch = cw * 2                       # Zeichenzelle: hoch wie zwei Breiten
    stroke = max(1.0, cw * 0.34)

    parts = [f'<g transform="translate({sx},{sy})" shape-rendering="crispEdges">']
    parts.append(f'<g fill="{AMBER}">')
    for x, y in sorted(fill):
        parts.append(f'<rect x="{x * cw:g}" y="{y * ch:g}" '
                     f'width="{cw:g}" height="{ch:g}"/>')
    parts.append("</g>")
    parts.append(f'<g stroke="{AMBER}" stroke-width="{stroke:g}" fill="none">')
    for x, y, mark in shadow:
        for (ax, ay), (bx, by) in SEGMENTS[mark]:
            parts.append(f'<path d="M{(x + ax) * cw:g} {(y + ay) * ch:g}'
                         f'L{(x + bx) * cw:g} {(y + by) * ch:g}"/>')
    parts.append("</g></g>")
    return "\n".join(parts), cols * cw, rows * ch


def logo(cw=14, pad=48):
    """Breites Wortmarken-Logo mit der Mailbox-Zeile darunter."""
    art, art_w, art_h = wordmark(FULL, cw, pad, pad)
    w = art_w + 2 * pad
    baseline = pad + art_h + round(cw * 2.4)
    h = baseline + pad
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" '
        f'viewBox="0 0 {w:g} {h:g}">',
        f'<rect width="{w:g}" height="{h:g}" fill="{INK}"/>',
        art,
        f'<text x="{w / 2:g}" y="{baseline:g}" fill="{AMBER}" text-anchor="middle" '
        f'xml:space="preserve" '
        f'font-family="Menlo, DejaVu Sans Mono, Consolas, monospace" '
        f'font-size="{round(cw * 1.5)}" '
        f'letter-spacing="{round(cw * 0.2)}">{TAGLINE}</text>',
        "</svg>",
    ])


def icon(size=512):
    """Quadratisches App-Icon: das Kuerzel in einem Terminalrahmen.

    Die volle Marke waere hier nicht mehr lesbar — ein Icon steht am Ende als
    16x16-Kachel in der Taskleiste."""
    inset = round(size * 0.07)
    frame = round(size * 0.05)
    margin = round(size * 0.055)
    inner = size - 2 * (inset + frame + margin)
    cols = cells(COMPACT)[2]
    cw = inner / cols

    _, art_w, art_h = wordmark(COMPACT, cw, 0, 0)
    sx, sy = (size - art_w) / 2, (size - art_h) / 2
    art, _, _ = wordmark(COMPACT, cw, sx, sy)

    r = round(size * 0.18)
    fw = size - 2 * inset
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}">',
        f'<rect width="{size}" height="{size}" rx="{r}" fill="{INK}"/>',
        f'<rect x="{inset + frame / 2:g}" y="{inset + frame / 2:g}" '
        f'width="{fw - frame:g}" height="{fw - frame:g}" rx="{round(r * 0.55)}" '
        f'fill="none" stroke="{AMBER}" stroke-width="{frame}"/>',
        art,
        "</svg>",
    ])


def main():
    root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    os.makedirs(root, exist_ok=True)

    written = []
    for name, svg in (("logo", logo()), ("icon", icon())):
        path = os.path.join(root, name + ".svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg + "\n")
        written.append(path)

    try:
        import cairosvg
    except ImportError:
        print("cairosvg fehlt — nur SVG geschrieben (pip install cairosvg)")
        return
    from PIL import Image

    cairosvg.svg2png(url=os.path.join(root, "logo.svg"),
                     write_to=os.path.join(root, "logo.png"), scale=2)
    cairosvg.svg2png(url=os.path.join(root, "icon.svg"),
                     write_to=os.path.join(root, "icon.png"),
                     output_width=512, output_height=512)
    icon_png = Image.open(os.path.join(root, "icon.png")).convert("RGBA")
    icon_png.resize((256, 256), Image.LANCZOS).save(
        os.path.join(root, "icon-256.png"))
    icon_png.save(os.path.join(root, "icon.ico"),
                  sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("assets/ geschrieben:", sorted(os.listdir(root)))


if __name__ == "__main__":
    main()
