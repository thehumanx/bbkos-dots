"""Palette generation via matugen (palette engine only; never writes configs)."""
import json
import re
import subprocess
from pathlib import Path

FALLBACK = "#7aa2f7"
MAX_IMAGE_BYTES = 40 * 1024 * 1024
DEFAULT_CONFIG = Path.home() / ".config/bbkos/matugen.toml"

MATERIAL = ("surface", "surface_container", "on_surface", "on_surface_variant",
            "primary", "tertiary", "error", "outline", "outline_variant")
# palette role -> matugen colour name
CUSTOM = {"warn": "warn", "ansi_red": "red", "ansi_green": "green",
          "ansi_yellow": "yellow", "ansi_blue": "blue",
          "ansi_magenta": "magenta", "ansi_cyan": "cyan"}
SCHEME_ROLES = MATERIAL + tuple(CUSTOM)      # read from matugen's scheme colours; the rest of ROLES is derived below

# Tints and shades of the wallpaper: tones of matugen's primary tonal palette (`palettes.primary.<tone>`), which does not
# collapse toward white when the contrast setting is high, unlike the scheme colours. role -> (palette, dark tone, light
# tone). `tone_primary` is the accent tint; `soft_primary` its deep shade (a container-like background). The other two
# tints are hue rotations of these in render.tokens (matugen's own secondary and tertiary tones are nearly grey).
TONES = {"tone_primary": ("primary", 80, 40), "soft_primary": ("primary", 30, 90)}
# Every key of a palette. A palette.json missing any of them (written before the tones existed) is regenerated.
ROLES = SCHEME_ROLES + tuple(TONES) + ("surface_high",)

_HEX = re.compile(r"^#[0-9a-f]{6}$")


class PaletteError(Exception):
    pass


def build_command(image, *, mode, scheme, source_index, contrast, config):
    """Full argv, memory-capped and time-limited. image None -> colour source."""
    if mode not in ("dark", "light"):
        raise PaletteError(f"bad mode: {mode!r}")
    if not scheme.startswith("scheme-"):
        scheme = "scheme-" + scheme
    contrast = max(-1.0, min(1.0, float(contrast)))
    src = ["image", str(image)] if image is not None else ["color", "hex", FALLBACK]
    return (["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryMax=1G",
             "timeout", "20", "matugen"] + src +
            ["--json", "hex", "-m", mode, "-t", scheme,
             "--source-color-index", str(int(source_index)),
             "--fallback-color", FALLBACK, f"--contrast={contrast}",
             "--dry-run", "--config", str(config)])


def _default_runner(argv):
    try:
        res = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        # No user systemd bus (first install from a bare TTY, ssh without a session, a chroot): run uncapped, still
        # time-limited, rather than fail to theme the desktop at all.
        if argv[0] == "systemd-run" and res.returncode != 0 and "Failed to connect" in res.stderr:
            return subprocess.run(argv[6:], capture_output=True, text=True, timeout=30)
        return res
    except FileNotFoundError as e:
        if argv[0] == "systemd-run" and e.filename == "systemd-run":
            return subprocess.run(argv[6:], capture_output=True, text=True, timeout=30)
        raise PaletteError(f"cannot run {e.filename}: not installed") from e
    except subprocess.TimeoutExpired as e:
        raise PaletteError("matugen timed out") from e
    except OSError as e:
        raise PaletteError(f"cannot run matugen: {e}") from e


_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_CHAIN = re.compile(r"^\d+:\s*")  # color-eyre cause chain: "   0: message"


def _first_line(text):
    """First informative stderr line: no ANSI colour, no systemd-run banner,
    no bare "Error:" header (matugen's color-eyre report), no "0: " prefix."""
    for line in _ANSI.sub("", text or "").splitlines():
        line = _CHAIN.sub("", line.strip())
        if line and line != "Error:" and not line.startswith("Running as unit"):
            return line
    return ""


def generate(image, *, mode, scheme, source_index, contrast, runner=None, config=None):
    if image is not None:
        image = Path(image).absolute()
        try:
            size = image.stat().st_size
        except OSError as e:
            raise PaletteError(f"cannot read image: {e.strerror or e}") from e
        if size > MAX_IMAGE_BYTES:
            raise PaletteError(f"image too large ({size} bytes, cap {MAX_IMAGE_BYTES})")
    run = runner or _default_runner

    def attempt(index):
        return run(build_command(image, mode=mode, scheme=scheme, source_index=index,
                                 contrast=contrast, config=config or DEFAULT_CONFIG))

    res = attempt(source_index)
    if res.returncode == 1 and image is not None and int(source_index) != 0:
        # An image with fewer distinct colours than source_index has no such
        # source colour; use the dominant one rather than failing.
        res = attempt(0)
    if res.returncode != 0 or not (res.stdout or "").strip():
        msg = _first_line(res.stderr) or (
            "matugen timed out" if res.returncode == 124 else f"matugen failed (rc {res.returncode})")
        raise PaletteError(msg)
    try:
        data = json.loads(res.stdout)
        colors = data["colors"]
    except (ValueError, KeyError, TypeError) as e:
        raise PaletteError("matugen output is not valid palette JSON") from e
    out = {}
    for role in SCHEME_ROLES:
        name = CUSTOM.get(role, role)
        try:
            val = colors[name][mode]["color"]
        except (KeyError, TypeError) as e:
            raise PaletteError(f"matugen output missing role {name!r}") from e
        if not isinstance(val, str) or not _HEX.match(val.lower()):
            raise PaletteError(f"matugen role {name!r} has bad value {val!r}")
        out[role] = val.lower()
    palettes = data.get("palettes") if isinstance(data, dict) else None
    for role, (name, dark, light) in TONES.items():
        out[role] = _tone(palettes, name, light if mode == "light" else dark, out["primary"])
    out["surface_high"] = _scheme_color(colors, "surface_container_high", mode, out["surface_container"])
    return out


def _scheme_color(colors, name, mode, fallback):
    try:
        val = colors[name][mode]["color"]
    except (KeyError, TypeError):
        return fallback
    return val.lower() if isinstance(val, str) and _HEX.match(val.lower()) else fallback


def _tone(palettes, name, tone, fallback):
    """One tone of a tonal palette, or `fallback` when matugen's output has no such palette (an older matugen)."""
    try:
        val = palettes[name][str(tone)]["color"]
    except (KeyError, TypeError):
        return fallback
    return val.lower() if isinstance(val, str) and _HEX.match(val.lower()) else fallback
