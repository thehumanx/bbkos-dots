"""WCAG contrast ratio and lightness nudging."""
import math


def _rgb(h):
    h = h.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad hex colour: {h!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h):
    r, g, b = (_lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    if a < b:
        a, b = b, a
    return (a + 0.05) / (b + 0.05)


def _to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_lin(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def to_oklch(h):
    """Hex -> (L, C, hue in degrees), OKLCH."""
    r, g, b = (_to_lin(c / 255) for c in _rgb(h))
    l = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def _lin_rgb(L, C, hue):
    a, b = C * math.cos(math.radians(hue)), C * math.sin(math.radians(hue))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)


def from_oklch(L, C, hue):
    """OKLCH -> hex. Out-of-gamut colours lose chroma (binary search) at fixed
    L and hue; channels are never clipped, which would shift the hue."""
    L = max(0.0, min(1.0, L))
    fits = lambda c: all(-1e-4 <= v <= 1 + 1e-4 for v in _lin_rgb(L, c, hue))
    if not fits(C):
        lo, hi = 0.0, C
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if fits(mid) else (lo, mid)
        C = lo
    return _hex(round(max(0.0, min(1.0, _from_lin(max(0.0, min(1.0, v))))) * 255)
                for v in _lin_rgb(L, C, hue))


def set_oklch_lightness(h, L, chroma=None):
    """Same hue and chroma (or `chroma`), OKLCH lightness set to L."""
    _, c, hue = to_oklch(h)
    return from_oklch(L, c if chroma is None else chroma, hue)


def ensure_contrast(fg, bg, floor):
    """Return fg (lowercased) if ratio(fg, bg) >= floor, else the closest
    lightness-shifted variant that meets it (same OKLCH hue and chroma, chroma
    reduced only to stay in gamut). Lightens on a dark bg, darkens on a light
    one; stops at white/black."""
    fg = _hex(_rgb(fg))
    if ratio(fg, bg) >= floor:
        return fg
    L, c, hue = to_oklch(fg)
    # Crossover luminance where white and black give equal contrast.
    lighten = luminance(bg) <= 0.1791
    end = 1.0 if lighten else 0.0
    far = from_oklch(end, c, hue)
    if ratio(far, bg) < floor:
        return far
    lo, hi = L, end  # lo fails, hi passes
    for _ in range(40):
        mid = (lo + hi) / 2
        if ratio(from_oklch(mid, c, hue), bg) >= floor:
            hi = mid
        else:
            lo = mid
    return from_oklch(hi, c, hue)


def blend(base, over, alpha):
    """`over` laid on `base` at `alpha` (0-1), in sRGB like Qt.tint and a normal source-over paint. Hex in, hex out."""
    b, o = _rgb(base), _rgb(over)
    return _hex(round(b[i] * (1 - alpha) + o[i] * alpha) for i in range(3))


def ensure_all(fg, checks):
    """Like ensure_contrast, but one colour that must clear several floors at once. `checks` is a list of
    (bg, floor) or (bg, floor, alpha): with an alpha, the colour is painted over bg at that opacity and the result must
    clear the floor against bg (an outline drawn at 55% of the text colour, say). The colour moves along OKLCH lightness
    only (same hue and chroma), towards white on dark backgrounds and black on light ones. Returns the closest colour
    that passes everything, or the far end (white or black) when nothing can."""
    checks = [(c[0], c[1], c[2] if len(c) > 2 else 1.0) for c in checks]

    def ok(c):
        return all(ratio(c if a >= 1 else blend(bg, c, a), bg) >= floor for bg, floor, a in checks)

    fg = _hex(_rgb(fg))
    if ok(fg):
        return fg
    L, chroma, hue = to_oklch(fg)
    lighten = sum(luminance(bg) for bg, _, _ in checks) / len(checks) <= 0.1791
    end = 1.0 if lighten else 0.0
    far = from_oklch(end, chroma, hue)
    if not ok(far):
        return far
    lo, hi = L, end
    for _ in range(40):
        mid = (lo + hi) / 2
        if ok(from_oklch(mid, chroma, hue)):
            hi = mid
        else:
            lo = mid
    return from_oklch(hi, chroma, hue)
