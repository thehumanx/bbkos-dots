"""bbkos-display command line: per-monitor scale, mode and layout, persisted and applied live.

Hand-parsed like cli.py. State: displays.json (the user's choices), hypr-monitors.lua (generated, loaded by
hyprland.lua), displays-prev.json (the state before a change nobody has confirmed with `keep` yet).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import brightness as BR
from . import displays as D
from .reload import lua_quote
from .settings import _atomic_write

USAGE = """\
usage: bbkos-display COMMAND
  status                                        monitors, modes, layout as JSON
  set-scale NAME SCALE                          e.g. set-scale eDP-1 1.25
  set-mode NAME WxH@R                           e.g. set-mode eDP-1 1920x1200@60
  layout extend|mirror|only [--primary NAME] [--position left|right|above|below]
  brightness NAME [PERCENT | --step DELTA | --key up|down]   read, set or step one monitor's brightness (JSON);\n                                                NAME @cursor = the monitor under the pointer
  keep                                          accept the last change
  revert                                        undo the last unconfirmed change
  apply [--lid open|closed]                     re-apply the saved state (hotplug, lid, session start)
environment: BBKOS_DISPLAYS, BBKOS_STATE_DIR override the paths; BBKOS_LID_STATE=open|closed the lid"""

TIMEOUT = 5


class UsageError(Exception):
    pass


class DisplayError(Exception):
    pass


def paths(env):
    home = Path.home()
    return (Path(env.get("BBKOS_DISPLAYS") or home / ".config/bbkos/displays.json"),
            Path(env.get("BBKOS_STATE_DIR") or home / ".local/state/bbkos/theme"))


def _first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _hypr(env, args):
    exe = shutil.which("hyprctl", path=env.get("PATH", os.defpath))
    if not exe:
        raise DisplayError("hyprctl not found")
    try:
        return subprocess.run([exe, *args], env=env, capture_output=True, text=True,
                              timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        raise DisplayError(f"hyprctl failed: {e}")


def mode_str(m):
    return f"{m['width']}x{m['height']}@{round(m['refreshRate'])}"


def modes_of(m):
    """'1920x1200@60.00Hz' -> '1920x1200@60', deduplicated, in Hyprland's order."""
    out = []
    for raw in m.get("availableModes") or []:
        try:
            size, rate = raw.removesuffix("Hz").split("@")
            s = f"{size}@{round(float(rate))}"
        except ValueError:
            continue
        if s not in out:
            out.append(s)
    return out


def read_monitors(env):
    res = _hypr(env, ["monitors", "all", "-j"])
    if res.returncode != 0:
        raise DisplayError(_first_line(res.stderr or res.stdout) or "hyprctl monitors failed")
    try:
        mons = json.loads(res.stdout)
        for m in mons:
            m["name"], m["width"], m["height"], m["refreshRate"], m["scale"]
    except (ValueError, KeyError, TypeError):
        raise DisplayError("unexpected hyprctl monitors output")
    return mons


def lid_closed(env):
    """True when the lid is closed (BBKOS_LID_STATE overrides /proc/acpi/button/lid/*/state)."""
    forced = env.get("BBKOS_LID_STATE")
    if forced:
        return forced == "closed"
    for f in sorted(Path("/proc/acpi/button/lid").glob("*/state")):
        try:
            return "closed" in f.read_text()
        except OSError:
            pass
    return False


def load_strict(dp):
    """The saved state, or an error when the file is unusable or partly invalid: writing it back would silently
    drop the user's entries, so nothing is changed until it is fixed or removed."""
    data, warns = D.load(dp)
    if warns:
        raise DisplayError(f"{_first_line(warns[0])}; fix or remove {dp} (nothing was changed)")
    return data


def _read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _restore(path, text):
    if text is None:
        try:
            os.unlink(os.path.realpath(path))
        except OSError:
            pass
    else:
        _atomic_write(path, text)


def _apply_live(env, lua):
    before = _hypr(env, ["configerrors"]).stdout.strip()
    res = _hypr(env, ["eval", f"dofile({lua_quote(str(lua))})"])
    if res.returncode != 0:
        raise DisplayError(_first_line(res.stderr or res.stdout) or "hyprctl eval failed")
    after = _hypr(env, ["configerrors"]).stdout.strip()
    if after and after != before:
        raise DisplayError(f"Hyprland config errors: {_first_line(after)}")


FALLBACK_RULE = 'hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })'


def _reapply_restored(env, lua, old_lua):
    """The failed eval may already have changed Hyprland (rc 0 with new config errors, or a rule list cut short):
    put the live state back too. Best effort; the original error is what gets reported."""
    try:
        _hypr(env, ["eval", f"dofile({lua_quote(str(lua))})" if old_lua is not None else FALLBACK_RULE])
    except DisplayError:
        pass


def commit(env, displays_path, state_dir, data, mons, make_prev=True):
    """Write displays.json and the Lua, apply live; on any failure put everything back."""
    lua = state_dir / "hypr-monitors.lua"
    prev = state_dir / "displays-prev.json"
    text = D.render_lua(D.resolve(data, mons, lid_closed(env)))
    old_disp, old_lua = _read_text(displays_path), _read_text(lua)
    created_prev = False
    evaled = False
    try:
        if make_prev and not prev.exists():
            _atomic_write(prev, json.dumps(D.load(displays_path)[0], indent=2) + "\n")
            created_prev = True
        D.save_atomic(displays_path, data)
        _atomic_write(lua, text)
        evaled = True
        _apply_live(env, lua)
    except BaseException:
        _restore(displays_path, old_disp)
        _restore(lua, old_lua)
        if created_prev:
            _restore(prev, None)
        if evaled:
            _reapply_restored(env, lua, old_lua)
        raise


def _find(mons, name):
    for m in mons:
        if m["name"] == name:
            return m
    raise DisplayError(f"unknown monitor: {name}")


def _entry(m, key, data):
    saved = data["monitors"].get(key)
    return dict(saved) if saved else {"scale": float(m["scale"]), "mode": mode_str(m)}


def _status(args, env, dp, sd):
    if args:
        raise UsageError("status takes no arguments")
    data, warns = D.load(dp)
    mons = read_monitors(env)
    keys = [D.monitor_key(m, mons) for m in mons]
    out = []
    for m, k in zip(mons, keys):
        w, h = D.mode_size(m, data["monitors"].get(k) or {})
        mirror = m.get("mirrorOf")
        out.append({"name": m["name"], "description": m.get("description", ""), "key": k,
                    "width": m["width"], "height": m["height"], "scale": m["scale"], "x": m.get("x", 0),
                    "y": m.get("y", 0), "disabled": bool(m.get("disabled")),
                    "mirrorOf": None if mirror in (None, "", "none") else mirror,
                    "brightness": BR.kind(m["name"], D.is_internal(m), env),
                    "mode": mode_str(m), "modes": modes_of(m), "scaleOptions": D.scale_options(w, h)})
    layout = None
    if len(mons) == 2:
        saved = data["layouts"].get(D.combo_key(keys)) or {"mode": "extend", "position": "right", "primary": keys[0]}
        names = dict(zip(keys, (m["name"] for m in mons)))
        layout = {"mode": saved["mode"], "position": saved["position"],
                  "primary": names.get(saved["primary"], mons[0]["name"])}
    print(json.dumps({"monitors": out, "layout": layout, "pending": (sd / "displays-prev.json").exists()}))
    return warns


def _set_scale(args, env, dp, sd):
    if len(args) != 2:
        raise UsageError("set-scale needs NAME SCALE")
    try:
        scale = float(args[1])
    except ValueError:
        raise UsageError(f"not a number: {args[1]!r}")
    data, warns = load_strict(dp), []
    mons = read_monitors(env)
    m = _find(mons, args[0])
    key = D.monitor_key(m, mons)
    entry = _entry(m, key, data)
    w, h = D.mode_size(m, entry)
    opts = D.scale_options(w, h)
    if round(scale, 2) not in opts:
        raise DisplayError(f"scale {args[1]} not valid for {w}x{h} (one of {', '.join(str(o) for o in opts)})")
    entry["scale"] = round(scale, 2)
    data["monitors"][key] = entry
    commit(env, dp, sd, data, mons)
    return warns


def _set_mode(args, env, dp, sd):
    if len(args) != 2:
        raise UsageError("set-mode needs NAME WxH@R")
    data, warns = load_strict(dp), []
    mons = read_monitors(env)
    m = _find(mons, args[0])
    if args[1] not in modes_of(m):
        raise DisplayError(f"mode {args[1]} not available on {m['name']}")
    key = D.monitor_key(m, mons)
    entry = _entry(m, key, data)
    entry["mode"] = args[1]
    w, h = D.mode_size(m, entry)
    entry["scale"] = D.clamp_scale(entry["scale"], w, h)
    data["monitors"][key] = entry
    commit(env, dp, sd, data, mons)
    return warns


def _layout(args, env, dp, sd):
    if not args or args[0] not in D.LAYOUT_MODES:
        raise UsageError(f"layout needs one of {', '.join(D.LAYOUT_MODES)}")
    mode, primary, position, rest = args[0], None, None, args[1:]
    while rest:
        if rest[0] not in ("--primary", "--position") or len(rest) < 2:
            raise UsageError(f"layout: unexpected argument {rest[0]!r}")
        if rest[0] == "--primary":
            primary = rest[1]
        else:
            position = rest[1]
            if position not in D.POSITIONS:
                raise UsageError(f"position must be one of {', '.join(D.POSITIONS)}")
        rest = rest[2:]
    data, warns = load_strict(dp), []
    mons = read_monitors(env)
    if len(mons) != 2:
        raise DisplayError("layout needs exactly two monitors")
    keys = [D.monitor_key(m, mons) for m in mons]
    combo = D.combo_key(keys)
    saved = data["layouts"].get(combo) or {}
    pkey = keys[mons.index(_find(mons, primary))] if primary else saved.get("primary", keys[0])
    data["layouts"][combo] = {"mode": mode, "primary": pkey, "position": position or saved.get("position", "right")}
    commit(env, dp, sd, data, mons)
    return warns


def monitor_at_cursor(env, mons):
    """The monitor under the pointer (logical coordinates), else the focused one, else the first."""
    try:
        cx, cy = (float(v) for v in _hypr(env, ["cursorpos"]).stdout.split(","))
    except (ValueError, DisplayError):
        cx = cy = None
    if cx is not None:
        for m in mons:
            w, h = m["width"] / m["scale"], m["height"] / m["scale"]
            if m.get("transform", 0) % 2:                  # rotated 90/270 degrees
                w, h = h, w
            if m.get("x", 0) <= cx < m.get("x", 0) + w and m.get("y", 0) <= cy < m.get("y", 0) + h:
                return m
    return next((m for m in mons if m.get("focused")), mons[0])


def _brightness(args, env, dp, sd):
    usage = "brightness needs NAME [PERCENT | --step DELTA | --key up|down]"
    if not args or len(args) > 3:
        raise UsageError(usage)
    name, rest = args[0], args[1:]
    percent = delta = key = None
    if rest[:1] == ["--key"]:
        if len(rest) != 2 or rest[1] not in ("up", "down"):
            raise UsageError(usage)
        key = rest[1]
    elif rest[:1] == ["--step"]:
        if len(rest) != 2:
            raise UsageError(usage)
        try:
            delta = int(rest[1])
        except ValueError:
            raise UsageError(f"not a whole number: {rest[1]!r}")
        if not -100 <= delta <= 100 or delta == 0:
            raise UsageError("step must be a non-zero whole number between -100 and 100")
    elif len(rest) == 1:
        try:
            percent = int(rest[0])
        except ValueError:
            raise UsageError(f"not a whole number: {rest[0]!r}")
        if not 0 <= percent <= 100:
            raise UsageError("percent must be 0-100")
    elif rest:
        raise UsageError(usage)
    mons = read_monitors(env)
    m = monitor_at_cursor(env, mons) if name == "@cursor" else _find(mons, name)
    internal = D.is_internal(m)
    try:
        if key is not None:
            out = BR.step(m["name"], internal, BR.key_delta(BR.get(m["name"], internal, env)["percent"], key), env)
        elif delta is not None:
            out = BR.step(m["name"], internal, delta, env)
        elif percent is not None:
            out = BR.set(m["name"], internal, percent, env)
        else:
            out = BR.get(m["name"], internal, env)
    except BR.BrightnessError as e:
        raise DisplayError(str(e))
    print(json.dumps({"name": m["name"], **out}))
    return []


def _keep(args, env, dp, sd):
    if args:
        raise UsageError("keep takes no arguments")
    _restore(sd / "displays-prev.json", None)
    return []


def _revert(args, env, dp, sd):
    if args:
        raise UsageError("revert takes no arguments")
    prev = sd / "displays-prev.json"
    if not prev.exists():
        raise DisplayError("nothing to revert")
    data, warns = D.load(prev)
    commit(env, dp, sd, data, read_monitors(env), make_prev=False)
    _restore(prev, None)
    return warns


def _apply(args, env, dp, sd):
    if args[:1] == ["--lid"]:
        if len(args) != 2 or args[1] not in ("open", "closed"):
            raise UsageError("--lid needs open or closed")
        env["BBKOS_LID_STATE"] = args[1]
        args = []
    if args:
        raise UsageError("apply takes at most --lid open|closed")
    data, warns = D.load(dp)
    if warns:                                        # unusable or partly invalid file: leave everything as it is
        return warns
    mons = read_monitors(env)
    if D.render_lua(D.resolve(data, mons, lid_closed(env))) != _read_text(sd / "hypr-monitors.lua"):
        commit(env, dp, sd, data, mons, make_prev=False)
    return warns


COMMANDS = {"status": _status, "set-scale": _set_scale, "set-mode": _set_mode, "layout": _layout,
            "brightness": _brightness, "keep": _keep, "revert": _revert, "apply": _apply}


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    if argv[:1] in (["-h"], ["--help"], ["help"]):
        print(USAGE)
        return 0
    try:
        if not argv or argv[0] not in COMMANDS:
            raise UsageError(f"unknown command {argv[0]!r}" if argv else "missing command")
        warns = COMMANDS[argv[0]](list(argv[1:]), env, *paths(env))
    except UsageError as e:
        print(f"bbkos-display: {_first_line(str(e)) or 'usage error'} (try --help)", file=sys.stderr)
        return 2
    except DisplayError as e:
        print(_first_line(str(e)) or "failed", file=sys.stderr)
        return 1
    except OSError as e:
        print(_first_line(f"{e.filename + ': ' if e.filename else ''}{e.strerror or e}") or "failed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    for w in warns:
        print(f"warning: {_first_line(w)}", file=sys.stderr)
    return 0
