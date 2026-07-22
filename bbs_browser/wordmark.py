"""Die Wortmarke "BBS-BROWSER" als ANSI-Shadow-Blockschrift.

Eine Quelle, zwei Ausgaben: dieselben Zeichen ergeben die Blockschrift fuers
Terminal und — ueber tools/make_logo.py — das Logo und das App-Icon in
assets/. Wer die Marke aendert, aendert damit automatisch beides.

Die Schrift ist der FIGlet-Font "ansi_shadow" — dieselbe Intro-Schrift, in der
bigtext.py die Plakat-Titel setzt: gefuellte Bloecke, dahinter eine nach unten
rechts versetzte Konturlinie als Schlagschatten. Das Ergebnis steht hier
woertlich statt aus pyfiglet erzeugt, denn die Marke soll Zeichen fuer Zeichen
feststehen: make_logo.py rastert genau das, was das Terminal druckt, und eine
neue Schriftversion kann das Logo nicht mehr unter der Hand verschieben.

Die volle Marke steht zweizeilig — einzeilig braeuchte "BBS-BROWSER" 89
Spalten und passte auf kein 80-Zeichen-Terminal mehr.
"""

FILL = "\u2588"                       # Vollblock: der Buchstabenkoerper
SHADOW = "\u2550\u2551\u2554\u2557\u255a\u255d"          # Rahmenlinien: der Schlagschatten dahinter

FULL = (
    "██████╗ ██████╗ ███████╗",
    "██╔══██╗██╔══██╗██╔════╝",
    "██████╔╝██████╔╝███████╗",
    "██╔══██╗██╔══██╗╚════██║",
    "██████╔╝██████╔╝███████║",
    "╚═════╝ ╚═════╝ ╚══════╝",
    "",
    "██████╗ ██████╗  ██████╗ ██╗    ██╗███████╗███████╗██████╗",
    "██╔══██╗██╔══██╗██╔═══██╗██║    ██║██╔════╝██╔════╝██╔══██╗",
    "██████╔╝██████╔╝██║   ██║██║ █╗ ██║███████╗█████╗  ██████╔╝",
    "██╔══██╗██╔══██╗██║   ██║██║███╗██║╚════██║██╔══╝  ██╔══██╗",
    "██████╔╝██║  ██║╚██████╔╝╚███╔███╔╝███████║███████╗██║  ██║",
    "╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚══╝╚══╝ ╚══════╝╚══════╝╚═╝  ╚═╝",
)

COMPACT = (
    "██████╗ ██████╗ ███████╗",
    "██╔══██╗██╔══██╗██╔════╝",
    "██████╔╝██████╔╝███████╗",
    "██╔══██╗██╔══██╗╚════██║",
    "██████╔╝██████╔╝███████║",
    "╚═════╝ ╚═════╝ ╚══════╝",
)

def width(art=None):
    """Spaltenbedarf der Marke."""
    return max(len(line) for line in (art or FULL))


def height(art=None):
    """Zeilenbedarf der Marke."""
    return len(art or FULL)


def render(art=None, indent=1):
    """Die Marke als Textblock.

    Bewusst ohne Farbcodes: der Aufrufer faerbt die ganze Ausgabe, und der
    Hauptbildschirm rechnet mit den Zeilen weiter, wofuer sichtbare Breite
    gleich Zeichenanzahl sein muss.
    """
    pad = " " * indent
    return "\n".join((pad + line).rstrip() for line in (art or FULL))


def cells(art=None):
    """Die Marke als Raster: (fuellzellen, schattenzellen, spalten, zeilen).

    Die Fuellzellen sind (x, y)-Paare, die Schattenzellen zusaetzlich mit dem
    Rahmenzeichen — make_logo.py zeichnet daraus die passenden Linienstuecke.
    """
    art = art or FULL
    fill, shadow = set(), []
    for y, line in enumerate(art):
        for x, ch in enumerate(line):
            if ch == FILL:
                fill.add((x, y))
            elif ch in SHADOW:
                shadow.append((x, y, ch))
    return fill, shadow, width(art), height(art)
