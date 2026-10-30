"""Tell running consumers to pick up the generated files.

Each step is skipped quietly when its target is absent (no Hyprland session,
no hyprctl, no kitty, no generated file). Failures become warnings, never
errors: the files are already in place and load at the next start.
"""
import hashlib
import os
import pwd
import re
import shutil
import signal
import subprocess
from pathlib import Path

from . import render

TIMEOUT = 5


def lua_quote(s):
    """A Lua double-quoted string literal for s."""
    s = (s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
         .replace("\r", "\\r").replace("\0", "\\0"))
    return f'"{s}"'


def _first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _hyprctl(hyprctl, args, env):
    return subprocess.run([hyprctl, *args], env=env, capture_output=True, text=True,
                          timeout=TIMEOUT, stdin=subprocess.DEVNULL)


def reload_hyprland(state_dir, env):
    lua = Path(state_dir).absolute() / "hypr-theme.lua"
    if not lua.is_file() or not env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return []
    hyprctl = shutil.which("hyprctl", path=env.get("PATH", os.defpath))
    if not hyprctl:
        return []
    try:
        # A full reload, not a re-evaluation of hypr-theme.lua: a gesture added by an earlier eval cannot be removed
        # that way (a swipe set back to "none" would stay active), and the reload reads hypr-theme.lua again anyway.
        res = _hyprctl(hyprctl, ["reload"], env)
        if res.returncode != 0:
            return [f"hyprctl reload failed: {_first_line(res.stderr or res.stdout) or res.returncode}"]
        res = _hyprctl(hyprctl, ["configerrors"], env)
    except (OSError, subprocess.SubprocessError) as e:
        return [f"hyprctl failed: {e}"]
    errors = _first_line(res.stdout)
    if errors:
        return [f"Hyprland config errors: {errors}"]
    # hyprland.lua loads the generated files under pcall, which keeps their errors out of configerrors; it records them
    # next to the state dir instead, rewritten before `hyprctl reload` returns.
    try:
        failed = [l for l in (Path(state_dir).absolute().parent / "hypr-load-errors").read_text(
            encoding="utf-8", errors="replace").splitlines() if l.strip()]
    except OSError:
        failed = []
    if failed:
        return [f"Hyprland could not load {len(failed)} generated file(s): {failed[0].strip()[:300]}"]
    return []


def kitty_pids(proc_root="/proc", comm="kitty"):
    """PIDs of the current user's processes whose /proc comm is exactly `comm`.
    Matches the kernel's process name only, never command-line text."""
    proc_root = Path(proc_root)
    me = os.getuid()
    out = []
    try:
        entries = list(proc_root.iterdir())
    except OSError:
        return out
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if os.stat(entry).st_uid != me:
                continue
            name = (entry / "comm").read_text(encoding="utf-8", errors="replace").rstrip("\n")
        except OSError:
            continue  # exited meanwhile, or not ours to read
        if name == comm:
            out.append(int(entry.name))
    return sorted(out)


def reload_kitty(state_dir, proc_root="/proc", comm="kitty", kill=os.kill):
    if not (Path(state_dir) / "kitty-theme.conf").is_file():
        return []
    for pid in kitty_pids(proc_root, comm):
        try:
            kill(pid, signal.SIGUSR1)
        except (ProcessLookupError, PermissionError):
            pass
    return []


def reload_hypridle(state_dir, env, which=shutil.which, real_home=None):
    """Restart hypridle when the generated hypridle.conf is not the one it was started with (bbkos-idle copies it to
    hypridle-active.conf on start). A restart restarts the idle timers, so nothing happens while the file is unchanged.
    Skipped when HOME is not the user's real home (a test or a dry run): the unit is the live session's, and the test suite
    once restarted it six times in five seconds until systemd refused to start it again (2026-10-24)."""
    state = Path(state_dir).absolute()
    conf = state / "hypridle.conf"
    if not conf.is_file():
        return []
    if real_home is None:
        real_home = pwd.getpwuid(os.getuid()).pw_dir
    if not env.get("HOME") or os.path.realpath(env["HOME"]) != os.path.realpath(real_home):
        return []
    systemctl = which("systemctl", path=env.get("PATH", os.defpath))
    if not systemctl:
        return []
    try:
        if (state / "hypridle-active.conf").read_text(encoding="utf-8") == conf.read_text(encoding="utf-8"):
            return []
    except OSError:
        pass                                   # no copy yet: hypridle runs the old file, or is not running
    try:
        if subprocess.run([systemctl, "--user", "is-active", "--quiet", "hypridle.service"], env=env,
                          timeout=TIMEOUT, stdin=subprocess.DEVNULL).returncode != 0:
            return []                          # not running (a test, or no session): it reads the file at its next start
        res = subprocess.run([systemctl, "--user", "restart", "hypridle.service"], env=env, capture_output=True,
                             text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return [f"hypridle restart failed: {e}"]
    return [f"hypridle restart failed: {_first_line(res.stderr) or res.returncode}"] if res.returncode else []


def _write(path, text):
    """Atomic write (temp file in the same directory, then rename). Returns True when the content changed."""
    path = Path(path)
    try:
        if path.read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return True


def _marker(css, name):
    m = re.search(r"/\* " + name + r": ([^ ]+) \*/", css)
    return m.group(1) if m else ""


GTK_THEMES = ("bbkos-a", "bbkos-b")     # two names: GTK reloads a theme only when the name changes


def reload_gtk(state_dir, env, which=shutil.which, system_themes="/usr/share/themes",
               system_icons="/usr/share/icons/Adwaita", real_home=None):
    """Point GTK at the generated colours. GTK 3: write the theme bbkos-a or bbkos-b (adw-gtk3 light or dark, then the
    colours, render.render_gtk3_theme) and switch gtk-theme to it, so open GTK 3 apps (Thunar) recolour at once; the
    two names alternate because GTK only reloads on a new name, and nothing is switched while the colours are the same.
    Also color-scheme (GTK 4 / libadwaita read it), and the folder icon theme (render.recolour_folder_svg). Skipped when
    adw-gtk3 is not installed: the stock Adwaita ignores the overrides, and when HOME is not the user's real home
    (a test or a dry run with a temp HOME): gsettings would still reach the live session and point it at a theme that
    exists only in the temp HOME (it did, 2026-10-23)."""
    css = Path(state_dir).absolute() / "gtk.css"
    if not css.is_file():
        return []
    gsettings = which("gsettings", path=env.get("PATH", os.defpath))
    if not gsettings:
        return []
    home = Path(env.get("HOME", ""))
    if real_home is None:
        real_home = pwd.getpwuid(os.getuid()).pw_dir
    if not env.get("HOME") or os.path.realpath(home) != os.path.realpath(real_home):
        return []
    themes = [home / ".local/share/themes", Path(system_themes)]
    try:
        text = css.read_text(encoding="utf-8")
    except OSError:
        return []
    dark = "mode: light" not in text
    variant = "adw-gtk3-dark" if dark else "adw-gtk3"
    parent = next((d / variant / "gtk-3.0/gtk.css" for d in themes if (d / variant / "gtk-3.0/gtk.css").is_file()), None)
    if parent is None:
        return []
    warns = []

    def gget(key):
        return subprocess.run([gsettings, "get", "org.gnome.desktop.interface", key], env=env, capture_output=True,
                              text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL).stdout.strip().strip("'")

    def gset(key, value):
        subprocess.run([gsettings, "set", "org.gnome.desktop.interface", key, value], env=env,
                       capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)

    stamp = hashlib.sha256((str(parent) + text).encode()).hexdigest()[:16]
    theme_text = render.render_gtk3_theme(parent, css, stamp)
    try:
        cur = gget("gtk-theme")
        cur_file = themes[0] / cur / "gtk-3.0/gtk.css"
        if not (cur in GTK_THEMES and cur_file.is_file() and cur_file.read_text(encoding="utf-8") == theme_text):
            nxt = GTK_THEMES[1] if cur == GTK_THEMES[0] else GTK_THEMES[0]
            _write(themes[0] / nxt / "gtk-3.0/gtk.css", theme_text)
            _write(themes[0] / nxt / "index.theme",
                   f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={nxt}\nComment=bbkOS: adw-gtk3 in the wallpaper's "
                   "colours (generated by bbkos-theme)\n")
            gset("gtk-theme", nxt)
        scheme = "prefer-dark" if dark else "prefer-light"
        if gget("color-scheme") != scheme:
            gset("color-scheme", scheme)
    except (OSError, subprocess.SubprocessError) as e:
        warns.append(f"gtk theme: {e}")
    warns += _reload_folder_icons(text, home, system_icons, gget, gset)
    return warns


ICON_THEMES = ("bbkos-icons-a", "bbkos-icons-b")     # alternate like GTK_THEMES: GTK reloads icons only on a new name


def _reload_folder_icons(css_text, home, system_icons, gget, gset):
    """~/.local/share/icons/bbkos-icons-{a,b}: Adwaita's folder icons in the accent's hue, the icon theme while
    colors.folderIcons is on (the `folders` marker in gtk.css). Open apps do not notice rewritten icon files (tried: a
    running Thunar kept the old folders), so new icons go into the other name and the icon theme switches to it;
    unchanged icons switch nothing. Off: back to Adwaita."""
    want = _marker(css_text, "folders") == "on"
    accent = _marker(css_text, "accent")
    root = home / ".local/share/icons"
    try:
        cur = gget("icon-theme")
        if not want or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent) or not Path(system_icons, FOLDER_PROBE).is_file():
            if cur in ICON_THEMES:
                gset("icon-theme", "Adwaita")
            return []
        files = {rel: render.recolour_folder_svg(Path(system_icons, "scalable", rel).read_text(encoding="utf-8"), accent)
                 for rel in render.FOLDER_ICONS if Path(system_icons, "scalable", rel).is_file()}

        def same(name):
            try:
                return all((root / name / "scalable" / rel).read_text(encoding="utf-8") == text
                           for rel, text in files.items())
            except OSError:
                return False
        if cur in ICON_THEMES and same(cur):
            return []
        nxt = ICON_THEMES[1] if cur == ICON_THEMES[0] else ICON_THEMES[0]
        for rel, text in files.items():
            _write(root / nxt / "scalable" / rel, text)
        _write(root / nxt / "index.theme", render.render_icon_index(nxt))
        gset("icon-theme", nxt)
    except (OSError, subprocess.SubprocessError) as e:
        return [f"folder icons: {e}"]
    return []


FOLDER_PROBE = "scalable/places/folder.svg"


def reload_cursor(state_dir, env, settings, which=shutil.which, real_home=None):
    """Change the cursor theme and size of what is already running: `hyprctl setcursor` for Hyprland and the apps on its
    cursor protocol, gsettings for GTK. Only when the choice differs from the one applied last (cursor-active in state_dir).
    New apps get the environment from hypr-theme.lua. Skipped without a Hyprland session, and gsettings only for the real
    HOME (a test or dry run must never change the live session; see reload_gtk)."""
    if not settings or not env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return []
    theme, size = settings["cursor"]["theme"], settings["cursor"]["size"]
    want = f"{theme} {size}\n"
    marker = Path(state_dir).absolute() / "cursor-active"
    try:
        if marker.read_text(encoding="utf-8") == want:
            return []
    except OSError:
        pass
    if real_home is None:
        real_home = pwd.getpwuid(os.getuid()).pw_dir
    if not env.get("HOME") or os.path.realpath(env["HOME"]) != os.path.realpath(real_home):
        return []
    warns = []
    path = env.get("PATH", os.defpath)
    try:
        hyprctl = which("hyprctl", path=path)
        if hyprctl:
            res = _hyprctl(hyprctl, ["setcursor", theme, str(size)], env)
            if res.returncode != 0:
                warns.append(f"hyprctl setcursor failed: {_first_line(res.stderr or res.stdout) or res.returncode}")
        gsettings = which("gsettings", path=path)
        if gsettings:
            for key, value in (("cursor-theme", theme), ("cursor-size", str(size))):
                subprocess.run([gsettings, "set", "org.gnome.desktop.interface", key, value], env=env,
                               capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        _write(marker, want)
    except (OSError, subprocess.SubprocessError) as e:
        warns.append(f"cursor: {e}")
    return warns


def reload_nightlight(state_dir, env, settings, which=shutil.which, real_home=None):
    """Night light: hyprsunset.service runs (enabled for the next login) while the mode is on or schedule, and is stopped and
    disabled when it is off. hyprsunset reads ~/.config/hypr/hyprsunset.conf only at start, so a change of that file restarts
    it (nightlight-active.conf in state_dir is the file it was started with). Skipped without hyprsunset or systemctl, and
    when HOME is not the real home (a test or dry run): the unit is the live session's."""
    if not settings:
        return []
    if real_home is None:
        real_home = pwd.getpwuid(os.getuid()).pw_dir
    if not env.get("HOME") or os.path.realpath(env["HOME"]) != os.path.realpath(real_home):
        return []
    path = env.get("PATH", os.defpath)
    systemctl = which("systemctl", path=path)
    if not systemctl or not which("hyprsunset", path=path):
        return []
    conf = Path(env["HOME"]) / ".config/hypr/hyprsunset.conf"
    marker = Path(state_dir).absolute() / "nightlight-active.conf"

    def ctl(*args):
        return subprocess.run([systemctl, "--user", *args], env=env, capture_output=True, text=True, timeout=TIMEOUT,
                              stdin=subprocess.DEVNULL)
    try:
        active = ctl("is-active", "--quiet", "hyprsunset.service").returncode == 0
        if settings["nightlight"]["mode"] == "off":
            if active or ctl("is-enabled", "--quiet", "hyprsunset.service").returncode == 0:
                res = ctl("disable", "--now", "hyprsunset.service")
                marker.unlink(missing_ok=True)
                return [f"hyprsunset stop failed: {_first_line(res.stderr) or res.returncode}"] if res.returncode else []
            return []
        text = conf.read_text(encoding="utf-8")
        try:
            same = marker.read_text(encoding="utf-8") == text
        except OSError:
            same = False
        if active and same:
            return []
        res = ctl("enable", "hyprsunset.service")
        res = ctl("restart" if active else "start", "hyprsunset.service") if res.returncode == 0 else res
        if res.returncode:
            return [f"hyprsunset start failed: {_first_line(res.stderr) or res.returncode}"]
        _write(marker, text)
    except (OSError, subprocess.SubprocessError) as e:
        return [f"night light: {e}"]
    return []


# The generated files Hyprland reads (hyprland.lua loads them) and the one kitty reads.
HYPR_FILES = frozenset({"hypr-theme.lua", "hypr-binds.lua"})
KITTY_FILES = frozenset({"kitty-theme.conf"})


def reload_all(state_dir, *, env=None, proc_root="/proc", kitty_comm=None, kill=os.kill, settings=None, changed=None):
    """Reload Hyprland and kitty from state_dir. Returns warnings. `changed`: the generated file names whose text changed
    in this apply; Hyprland and kitty are reloaded only when one of their files is among them (a full `hyprctl reload`
    re-applies every window, which flashed them for a bar setting, 2026-10-31). None reloads everything (an explicit apply).
    The other steps already do nothing when their choice is unchanged."""
    env = dict(os.environ if env is None else env)
    comm = kitty_comm or env.get("BBKOS_KITTY_COMM") or "kitty"
    warns = reload_hyprland(state_dir, env) if changed is None or HYPR_FILES & set(changed) else []
    if changed is None or KITTY_FILES & set(changed):
        warns += reload_kitty(state_dir, proc_root, comm, kill)
    warns += reload_gtk(state_dir, env)
    warns += reload_hypridle(state_dir, env)
    warns += reload_cursor(state_dir, env, settings)
    warns += reload_nightlight(state_dir, env, settings)
    return warns
