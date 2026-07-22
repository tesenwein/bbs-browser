#!/usr/bin/env python3
"""Version tool — one source of truth, a few small operations.

The version lives in pyproject.toml and is mirrored in bbs_browser/__init__.py.
This script reads, bumps, and writes it. The CI uses it like this:

    NEXT="$(python tools/bump_version.py --next "$BASE")"   # X.Y.Z -> X.Y.(Z+1)
    python tools/bump_version.py --set "$NEXT"               # into both files

Other invocations:
    python tools/bump_version.py --current   # print current version
    python tools/bump_version.py             # bump patch AND write it
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "bbs_browser" / "__init__.py"

PYPROJECT_RE = re.compile(r'^(version\s*=\s*")([^"]+)(")', re.M)
INIT_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.M)


def read_version():
    m = PYPROJECT_RE.search(PYPROJECT.read_text(encoding="utf-8"))
    if not m:
        sys.exit("Keine Version in pyproject.toml gefunden")
    return m.group(2)


def bump_patch(version):
    parts = str(version).lstrip("vV").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        sys.exit(f"Version '{version}' ist nicht im Format X.Y.Z")
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts)


def _sub(path, pattern, new_version):
    text = path.read_text(encoding="utf-8")
    new_text, n = pattern.subn(rf"\g<1>{new_version}\g<3>", text)
    if n:
        path.write_text(new_text, encoding="utf-8")
    return n


def write_version(version):
    _sub(PYPROJECT, PYPROJECT_RE, version)
    _sub(INIT, INIT_RE, version)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--current", action="store_true", help="aktuelle Version ausgeben")
    g.add_argument("--next", metavar="BASE", nargs="?", const="",
                   help="naechste Patch-Version von BASE ausgeben (ohne Schreiben)")
    g.add_argument("--set", metavar="VERSION", help="VERSION in beide Dateien schreiben")
    args = ap.parse_args()

    if args.current:
        print(read_version())
    elif args.next is not None:
        base = args.next or read_version()
        print(bump_patch(base))
    elif args.set:
        version = args.set.lstrip("vV")
        write_version(version)
        print(version)
    else:
        # No argument: local convenience — bump the patch and write it.
        new_version = bump_patch(read_version())
        write_version(new_version)
        print(new_version)


if __name__ == "__main__":
    main()
