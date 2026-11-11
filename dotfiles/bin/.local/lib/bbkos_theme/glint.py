"""The About window (docs/modules/branding.md): fastfetch with the branding logo, and a glint that sweeps across the logo
every few seconds (the idea of Omarchy's About screen: fastfetch has no animation of its own, so the logo's own cells are
repainted). The frames only touch logo cells and hand every one back in its base colour; a logo with double-width
characters, a blank logo and NO_COLOR stay still, because a sweep over them would land on the wrong cells or add colour."""
import os
import re
import select
import signal
import subprocess
import sys
import termios
import tty

from bbkos_theme import branding

GLINT_SGR = "\x1b[1;96m"      # bold bright cyan: palette colour 14, so the terminal theme sets the hue
BAND = 3                      # half width of the lit band, in diagonal units (a row counts for two columns)
STEP = 2                      # how far the band moves each frame
FRAME_SECONDS = 0.03
REST_SECONDS = 4.0
ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _cells(logo, width):
    """[(row_index, col_index, char)] of the visible characters, clipped to width columns."""
    return [(r, c, ch) for r, line in enumerate(logo.splitlines()) for c, ch in enumerate(line)
            if ch != " " and c < width]


def frames(logo, row, col, base_sgr, width, no_color=None):
    """ANSI strings, one per animation frame; [] when the logo cannot be animated. row and col are the screen cell
    (1-based) of the logo's first character."""
    if no_color is None:
        no_color = bool(os.environ.get("NO_COLOR"))
    if no_color or not branding.is_single_width(logo):
        return []
    cells = _cells(logo, width)
    if not cells:
        return []
    diag = {(r, c): c + 2 * r for r, c, _ in cells}
    top = max(diag.values())
    out = []
    for pos in range(-BAND - STEP, top + BAND + 2 * STEP + 1, STEP):
        touched = [(r, c, ch) for r, c, ch in cells if abs(diag[(r, c)] - pos) <= BAND + STEP]
        if not touched:
            continue
        parts = []
        run = None                                    # (row, first col, sgr, [chars])
        for r, c, ch in touched:                      # cells are in row order, then column order
            sgr = GLINT_SGR if abs(diag[(r, c)] - pos) <= BAND else base_sgr
            if run and run[0] == r and run[1] + len(run[3]) == c and run[2] == sgr:
                run[3].append(ch)
                continue
            if run:
                parts.append(run)
            run = (r, c, sgr, [ch])
        parts.append(run)
        out.append("".join(f"\x1b[{row + r};{col + c}H{sgr}{''.join(chs)}" for r, c, sgr, chs in parts) + "\x1b[0m")
    return out


def locate(plain, logo):
    """(row, col), 1-based, where fastfetch drew the logo in its plain output, or None. The longest logo line is the
    landmark, and its position in the logo is taken off the row."""
    lines = logo.splitlines()
    if not any(l.strip() for l in lines):
        return None
    index = max(range(len(lines)), key=lambda i: len(lines[i].rstrip()))
    needle = lines[index].rstrip()
    for n, line in enumerate(plain.splitlines(), 1):
        at = line.find(needle)
        if at >= 0 and n - index >= 1:
            return n - index, at + 1
    return None


def _fastfetch(*extra):
    return subprocess.run(["fastfetch", "--pipe", "false", *extra], capture_output=True, text=True, timeout=30).stdout


def _logo_args(logo):
    """fastfetch reads the logo from a file; the user's file may be missing (then branding falls back to the default) or
    blank, so it is written out from branding.read() into the runtime directory."""
    if not logo.strip():
        return ["--logo-type", "none"]
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "bbkos-about-logo.txt")
    with open(path, "w") as f:
        f.write(logo)
    return ["--logo-type", "file-raw", "--logo", path]


def _wait(seconds):
    """True when a key was pressed (About closes) within the time."""
    ready, _, _ = select.select([sys.stdin], [], [], seconds)
    if ready:
        sys.stdin.read(1)
    return bool(ready)


def run():
    """The window's loop: draw fastfetch, then a glint, a rest, again; any key closes it, a resize redraws."""
    resized = False

    def on_winch(*_):
        nonlocal resized
        resized = True
    signal.signal(signal.SIGWINCH, on_winch)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\x1b[?25l")
        while True:
            resized = False
            logo = branding.read("about")
            rendered = _fastfetch(*_logo_args(logo))
            sys.stdout.write("\x1b[2J\x1b[H" + rendered)
            sys.stdout.flush()
            spot = locate(ANSI.sub("", rendered), logo)
            width = os.get_terminal_size().columns
            seq = frames(logo, spot[0], spot[1], "\x1b[0m", width - spot[1] + 1) if spot else []
            while not resized:
                for frame in seq:
                    if resized:
                        break
                    sys.stdout.write(frame)
                    sys.stdout.flush()
                    if _wait(FRAME_SECONDS):
                        return 0
                if _wait(REST_SECONDS if seq else 0.5):
                    return 0
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h")


def main(argv):
    """bbkos-about-window: open the About window in a floating kitty; `--render` is what runs inside it."""
    if argv[:1] == ["--render"]:
        return run()
    subprocess.Popen(["kitty", "--class", "org.bbkos.about", "-o", "confirm_os_window_close=0",
                      sys.argv[0], "--render"], start_new_session=True)
    return 0
