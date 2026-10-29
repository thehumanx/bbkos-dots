#!/usr/bin/env python3
"""Generate modules/emoji/emoji.json (the emoji picker's data) from the official Unicode emoji list.

Source: emoji-test.txt from unicode.org (or a local copy: the `unicode-emoji` package puts it in /usr/share/unicode/emoji/).
Kept: fully-qualified emoji, without the five skin-tone variants of each (hundreds of near-duplicates; the base emoji stays) and
without the "Component" group. Emoji the installed Noto Color Emoji cannot draw (new in a newer Unicode than the font) are left out, so the picker never shows an
empty box; run this again after the font package updates. Output: {"version": "...", "groups": [names], "emoji": [[emoji, name, groupIndex], ...]}, in
the Unicode order, which is also the order the picker shows. Run: python3 scripts/build-emoji-data.py [path-to-emoji-test.txt]
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

URL = "https://unicode.org/Public/emoji/latest/emoji-test.txt"
OUT = Path(__file__).resolve().parent.parent / "dotfiles/quickshell/.config/quickshell/modules/emoji/emoji.json"
LOCAL = Path("/usr/share/unicode/emoji/emoji-test.txt")
SKIN_TONES = ("light skin tone", "medium-light skin tone", "medium skin tone", "medium-dark skin tone", "dark skin tone")


def source(argv):
    if len(argv) > 1:
        return Path(argv[1]).read_text(encoding="utf-8")
    if LOCAL.exists():
        return LOCAL.read_text(encoding="utf-8")
    with urllib.request.urlopen(URL, timeout=30) as r:
        return r.read().decode("utf-8")


def font_codepoints(family="Noto Color Emoji"):
    """The codepoints the installed emoji font can draw (fontconfig), or None when it cannot be read."""
    try:
        path = subprocess.run(["fc-match", family, "--format", "%{file}"], capture_output=True, text=True).stdout
        charset = subprocess.run(["fc-query", "--format", "%{charset}", path], capture_output=True, text=True).stdout.split()
    except OSError:
        return None
    have = set()
    for r in charset:
        a, _, b = r.partition("-")
        have.update(range(int(a, 16), int(b or a, 16) + 1))
    return have or None


def drawable(char, have):
    """False when a base codepoint of the emoji is missing from the font (the newest emoji after a Unicode update)."""
    skip = {0xFE0F, 0x200D}
    return all(ord(c) in have for c in char if ord(c) not in skip and not 0x1F3FB <= ord(c) <= 0x1F3FF)


def parse(text, have=None):
    version = re.search(r"^# Version: (\S+)", text, re.M)
    groups, emoji = [], []
    line_re = re.compile(r"^[0-9A-F ]+;\s*fully-qualified\s*#\s*(\S+)\s+E[0-9.]+\s+(.*)$")
    for line in text.splitlines():
        if line.startswith("# group:"):
            groups.append(line.split(":", 1)[1].strip())
            continue
        m = line_re.match(line)
        if not m or groups[-1] == "Component":
            continue
        char, name = m.group(1), m.group(2).strip()
        if any(t in name for t in SKIN_TONES):
            continue
        if have is not None and not drawable(char, have):
            continue
        emoji.append([char, name, len([g for g in groups if g != "Component"]) - 1])
    return {"version": version.group(1) if version else "?", "groups": [g for g in groups if g != "Component"], "emoji": emoji}


if __name__ == "__main__":
    have = font_codepoints()
    data = parse(source(sys.argv), have)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(data['emoji'])} emoji in {len(data['groups'])} groups, Unicode emoji {data['version']} -> {OUT}")
