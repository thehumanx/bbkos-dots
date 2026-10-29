"""Accessibility rules for the generated theme (WCAG 2.2): which colour sits on which surface, and the contrast floor each
pair must clear. render.tokens() enforces them when it builds the tokens; `bbkos-theme contrast` and bbkos-check measure
the generated files against the same table.

Floors: 4.5:1 for text (SC 1.4.3, also the terminal and the small 11-13 px shell text) and 3:1 for the parts of a control
and the focus ring (SC 1.4.11, 2.4.11). The surfaces are the ones Theme.qml derives at run time from colors.json and the
tint setting, so surfaces() must stay the same maths as Theme.popupBg, Theme.inset, Theme.control and Theme.pillBg.
"""
import subprocess

from . import contrast

TEXT = 4.5
UI = 3.0

# Surfaces each colour role is drawn on. `fg` is the text colour, `dim` the secondary text.
FG_ON = ("bg", "surface", "popup", "inset", "control", "pill", "surfaceHigh", "accentSoft")
DIM_ON = ("bg", "surface", "popup", "inset", "control", "pill", "surfaceHigh")
ACCENT_TEXT_ON = ("bg", "popup", "inset", "control", "pill")      # accent and its two hue turns, used as text or glyphs
SIGNAL_ON = ("bg", "popup", "inset", "control")                   # warn and crit, used as text
TERMINAL_ANSI = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)   # 0 is the background itself


def surfaces(bg, container, accent_soft, surface_high, fg, tint):
    """The backgrounds text sits on, as Theme.qml derives them. `bg` is the window colour (Theme.bg), `container` the raised
    base (Theme.surface), `tint` shell.tint. Qt.tint(base, c at a) is blend(base, c, a)."""
    popup = contrast.blend(container, accent_soft, tint * 0.5)
    return {"bg": bg, "surface": container, "popup": popup, "inset": contrast.blend(popup, bg, 0.55),
            "control": contrast.blend(popup, fg, 0.12), "pill": contrast.blend(container, accent_soft, tint * 0.45),
            "surfaceHigh": surface_high, "accentSoft": accent_soft}


def token_surfaces(t, tint):
    return surfaces(t["bg"], t["surface"], t["accentSoft"], t["surfaceHigh"], t["fg"], tint)


def pairs(t, tint):
    """[(name, ratio, floor)] for the generated tokens `t` (render.tokens output or colors.json) at shell.tint `tint`."""
    s = token_surfaces(t, tint)
    out = []

    def add(name, fg, bg, floor):
        out.append((name, contrast.ratio(fg, bg), floor))

    for b in FG_ON:
        add(f"text on {b}", t["fg"], s[b], TEXT)
    for b in DIM_ON:
        add(f"dim text on {b}", t["dim"], s[b], TEXT)
    for name, label in (("accent", "accent"), ("secondary", "accent 2"), ("tertiary", "accent 3")):
        for b in ACCENT_TEXT_ON:
            add(f"{label} text on {b}", t[name], s[b], TEXT)
    for name in ("warn", "crit"):
        for b in SIGNAL_ON:
            add(f"{name} text on {b}", t[name], s[b], TEXT)
    add("text on accent fill", t["bg"], t["accent"], TEXT)
    add("accent glyph on accent-soft", t["accent"], s["accentSoft"], UI)
    add("accent fill on popup", t["accent"], s["popup"], UI)
    add("accent fill on inset", t["accent"], s["inset"], UI)
    add("crit edge on popup", t["crit"], s["popup"], UI)
    add("switch outline on popup", contrast.blend(s["popup"], t["fg"], 0.55), s["popup"], UI)
    add("switch knob on inset", contrast.blend(s["inset"], t["fg"], 0.85), s["inset"], UI)
    add("focus border on bg", t["borderActive1"], t["bg"], UI)
    add("focus border 2 on bg", t["borderActive2"], t["bg"], UI)
    for i in TERMINAL_ANSI:
        add(f"terminal colour {i}", t["ansi"][i], t["bg"], TEXT)
    return out


def failures(t, tint):
    return [p for p in pairs(t, tint) if p[1] + 1e-9 < p[2]]


# ---- lock screen -------------------------------------------------------------------------------------------------------
# hyprlock draws light text over the blurred wallpaper, dimmed by `brightness`. A bright wallpaper would leave the clock and
# the password field unreadable whatever the palette says, so the brightness is capped to what the wallpaper allows.
LOCK_GRID = (64, 36)                      # the wallpaper is sampled at this size
LOCK_TEXT_AREA = (16, 48, 5, 31)          # columns and rows (from, to) around the screen centre where the lock elements sit
LOCK_TEXT_ALPHA = 0.8                     # the date label is the faintest text (80% of the text colour)
LOCK_FIELD_ALPHA = 0.14                   # the password field is white at this opacity over the wallpaper
LOCK_MIN_BRIGHTNESS = 0.2                 # the lowest value of the lock.brightness setting


def measure_wallpaper(path, run=subprocess.run):
    """The colour (r, g, b, 0-255) that the lock text area is brightest at: the 95th percentile of luminance over the
    centre of the wallpaper, sampled with ffmpeg (one frame, scaled down). None when it cannot be measured (no ffmpeg, not
    an image ffmpeg reads): the lock then keeps the brightness setting."""
    w, h = LOCK_GRID
    try:
        res = run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}:flags=area", "-frames:v", "1",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    data = res.stdout if res.returncode == 0 else b""
    if len(data) != w * h * 3:
        return None
    c0, c1, r0, r1 = LOCK_TEXT_AREA
    cells = [tuple(data[(y * w + x) * 3:(y * w + x) * 3 + 3]) for y in range(r0, r1) for x in range(c0, c1)]
    cells.sort(key=lambda c: contrast.luminance("#%02x%02x%02x" % c))
    return cells[min(len(cells) - 1, int(len(cells) * 0.95))]


def lock_brightness(setting, cell, text_hex):
    """The brightness to write to hyprlock: `setting`, or less when `cell` (measure_wallpaper) dimmed by `setting` would
    leave the text below 4.5:1. The check is the hardest case: the faintest text over the password field's lighter backing.
    Only light text needs this (dark text on a dark wallpaper is a choice of the owner); returns `setting` unchanged then."""
    if cell is None or contrast.luminance(text_hex) < 0.5:
        return setting

    def ok(b):
        backdrop = contrast.blend("#%02x%02x%02x" % tuple(round(c * b) for c in cell), "#ffffff", LOCK_FIELD_ALPHA)
        shown = contrast.blend(backdrop, text_hex, LOCK_TEXT_ALPHA)
        return contrast.ratio(shown, backdrop) >= TEXT

    if ok(setting):
        return setting
    if not ok(LOCK_MIN_BRIGHTNESS):
        return LOCK_MIN_BRIGHTNESS
    lo, hi = LOCK_MIN_BRIGHTNESS, setting          # lo passes, hi fails
    for _ in range(20):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return max(LOCK_MIN_BRIGHTNESS, int(lo * 100) / 100)
