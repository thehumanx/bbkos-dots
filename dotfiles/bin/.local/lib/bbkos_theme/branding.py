"""Branding files (docs/modules/branding.md): the ASCII logo of the About window (about.txt) and of the screensaver
(screensaver.txt) in ~/.config/bbkos/branding/. A missing file falls back to the tracked default in
share/bbkos/branding/; a file that exists but is blank means "show nothing"."""
import os
import sys
import unicodedata
from pathlib import Path

KINDS = ("about", "screensaver")
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "share/bbkos/branding"

_FONT_SRC = {
    "A": " ### |#   #|#####|#   #|#   #", "B": "#### |#   #|#### |#   #|#### ",
    "C": " ####|#    |#    |#    | ####", "D": "#### |#   #|#   #|#   #|#### ",
    "E": "#####|#    |#### |#    |#####", "F": "#####|#    |#### |#    |#    ",
    "G": " ####|#    |#  ##|#   #| ####", "H": "#   #|#   #|#####|#   #|#   #",
    "I": "###| # | # | # |###", "J": "  ###|    #|    #|#   #| ### ",
    "K": "#   #|#  # |###  |#  # |#   #", "L": "#    |#    |#    |#    |#####",
    "M": "#   #|## ##|# # #|#   #|#   #", "N": "#   #|##  #|# # #|#  ##|#   #",
    "O": " ### |#   #|#   #|#   #| ### ", "P": "#### |#   #|#### |#    |#    ",
    "Q": " ### |#   #|# # #|#  # | ## #", "R": "#### |#   #|#### |#  # |#   #",
    "S": " ####|#    | ### |    #|#### ", "T": "#####|  #  |  #  |  #  |  #  ",
    "U": "#   #|#   #|#   #|#   #| ### ", "V": "#   #|#   #|#   #| # # |  #  ",
    "W": "#   #|#   #|# # #|## ##|#   #", "X": "#   #| # # |  #  | # # |#   #",
    "Y": "#   #| # # |  #  |  #  |  #  ", "Z": "#####|   # |  #  | #   |#####",
}
FONT = {k: v.replace("#", "█").split("|") for k, v in _FONT_SRC.items()}


def _path(kind, home):
    if kind not in KINDS:
        raise ValueError(f"unknown branding file {kind!r}, expected one of {', '.join(KINDS)}")
    return Path(home) / ".config/bbkos/branding" / f"{kind}.txt"


def default(kind):
    _path(kind, "/")
    return (DEFAULT_DIR / f"{kind}.txt").read_text()


def read(kind, home=None):
    """The logo text; the default when the user's file does not exist; '' when it is blank."""
    p = _path(kind, home or Path.home())
    try:
        text = p.read_text()
    except FileNotFoundError:
        return default(kind)
    except OSError:
        return ""
    return text if text.strip() else ""


def _write(kind, text, home):
    p = _path(kind, home or Path.home())
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, p)


def set_text(kind, source, home=None):
    _write(kind, Path(source).read_text(), home)


def reset(kind, home=None):
    _write(kind, default(kind), home)


def words(text):
    """Block letters, five rows tall. Letters and spaces only; anything else is dropped and named on stderr."""
    dropped = [c for c in text if c != " " and c.upper() not in FONT]
    if dropped:
        print("dropped (letters and spaces only): " + " ".join(dict.fromkeys(dropped)), file=sys.stderr)
    glyphs = [FONT[c.upper()] if c != " " else ["   "] * 5 for c in text if c == " " or c.upper() in FONT]
    return "\n".join(" ".join(g[row] for g in glyphs) for row in range(5)) + "\n"


def is_single_width(text):
    """True when every character takes one terminal column (the glint moves cells and needs that)."""
    for ch in text:
        if ch in "\n\t":
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F") or unicodedata.category(ch) == "So" and ord(ch) > 0x1F000:
            return False
    return True


def main(argv):
    usage = "usage: bbkos-branding show|reset about|screensaver | set-text KIND FILE | words KIND TEXT..."
    try:
        cmd, kind, *rest = argv
        if cmd == "show":
            sys.stdout.write(read(kind))
        elif cmd == "reset":
            reset(kind)
        elif cmd == "set-text" and len(rest) == 1:
            set_text(kind, rest[0])
        elif cmd == "words" and rest:
            _write(kind, words(" ".join(rest)), None)
        else:
            raise ValueError(usage)
    except (ValueError, OSError) as e:
        print(f"bbkos-branding: {e}" if str(e) != usage else usage, file=sys.stderr)
        return 2
    return 0
