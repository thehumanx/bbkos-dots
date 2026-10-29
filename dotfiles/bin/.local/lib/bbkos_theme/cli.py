"""bbkos-theme command line. Hand-parsed: the surface is small, and filenames
(leading dash, spaces, unicode) and negative values must pass through as-is."""
import copy
import json
import os
import sys
from pathlib import Path

from . import a11y
from . import apply as A
from . import avatar as AV
from . import settings as S

USAGE = """\
usage: bbkos-theme COMMAND
  apply [--only shape|colors] [--out-dir DIR]   render and reload (DIR: dry run)
  set KEY VALUE                                  change one setting, then apply
  wallpaper set [--] FILE                        copy FILE in as the wallpaper, then apply
  wallpaper clear                                no wallpaper (fallback colour), then apply
  avatar set [--] FILE                           copy FILE in as the lock screen avatar, then apply
  avatar clear                                   back to the shipped avatar, then apply
  reset [TARGET...]                              defaults for each TARGET (a SECTION or a KEY), or everything
  defaults                                       JSON: the built-in defaults, and what grid mode overrides
  status                                         paths and freshness
  contrast                                       WCAG contrast of the generated colours (exit 1 if a pair fails)
sections: {sections}
environment: BBKOS_SETTINGS, BBKOS_STATE_DIR, BBKOS_SHARE_DIR, BBKOS_AVATAR_DIR override the paths"""

SECTIONS = ("shell", "windows", "touchpad", "bar", "stage", "capture", "camera", "terminal", "lock", "calendar", "idle", "notifications", "keyboard", "mouse", "cursor", "nightlight", "behavior", "clock", "clipboard", "session", "launcher", "privacy", "media", "wellbeing", "colors", "wallpaper", "power")

USAGE = USAGE.replace("{sections}", ", ".join(SECTIONS))


class UsageError(Exception):
    pass


def paths(env=None):
    env = os.environ if env is None else env
    home = Path.home()
    return (Path(env.get("BBKOS_SETTINGS") or home / ".config/bbkos/settings.json"),
            Path(env.get("BBKOS_STATE_DIR") or home / ".local/state/bbkos/theme"),
            Path(env.get("BBKOS_SHARE_DIR") or home / ".local/share/bbkos/wallpaper"))


def _strip_dashdash(args):
    return args[1:] if args[:1] == ["--"] else args


def _apply(args, sp, st, sh):
    only = out = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--only", "--out-dir"):
            if i + 1 >= len(args):
                raise UsageError(f"{a} needs a value")
            if a == "--only":
                only = args[i + 1]
                if only not in ("shape", "colors"):
                    raise UsageError(f"--only must be shape or colors, not {only!r}")
            else:
                out = Path(args[i + 1])
            i += 2
        else:
            raise UsageError(f"apply: unexpected argument {a!r}")
    return A.apply(sp, st, sh, only=only, out_dir=out)


def _set(args, sp, st, sh):
    args = _strip_dashdash(args)
    if len(args) != 2:
        raise UsageError("set needs KEY VALUE")
    key, value = args
    if key == "lock.avatar":
        raise A.ApplyError("lock.avatar: use `bbkos-theme avatar set FILE` or `bbkos-theme avatar clear`")
    if key == "wallpaper.path":
        # only `wallpaper set` makes the copy the path must point at
        raise A.ApplyError("wallpaper.path: use `bbkos-theme wallpaper set FILE` "
                           "or `bbkos-theme wallpaper clear`")
    if key not in S.RANGES:
        raise A.ApplyError(f"unknown key: {key}")
    return A.update(sp, st, sh, lambda s: S.set_value(s, key, value))


def _wallpaper(args, sp, st, sh):
    if not args or args[0] not in ("set", "clear"):
        raise UsageError("wallpaper needs set FILE or clear")
    if args[0] == "clear":
        if len(args) != 1:
            raise UsageError("wallpaper clear takes no arguments")
        return A.update(sp, st, sh, lambda s: S.set_value(s, "wallpaper.path", ""),
                        clear_wallpaper=True)
    rest = _strip_dashdash(args[1:])
    if len(rest) != 1 or not rest[0]:
        raise UsageError("wallpaper set needs exactly one FILE")
    return A.update(sp, st, sh, wallpaper_src=Path(rest[0]).absolute())


def _avatar(args, sp, st, sh):
    """The lock screen avatar: a copy in avatar.default_dir() (BBKOS_AVATAR_DIR), recorded in lock.avatar. Other copies are
    removed only after the settings were written, so a failed apply leaves the old picture in place."""
    if not args or args[0] not in ("set", "clear"):
        raise UsageError("avatar needs set FILE or clear")
    folder = AV.default_dir()
    if args[0] == "clear":
        if len(args) != 1:
            raise UsageError("avatar clear takes no arguments")
        warns = A.update(sp, st, sh, lambda s: S.set_value(s, "lock.avatar", ""))
        AV.remove_others(folder)
        return warns
    rest = _strip_dashdash(args[1:])
    if len(rest) != 1 or not rest[0]:
        raise UsageError("avatar set needs exactly one FILE")
    try:
        copy = AV.copy_in(rest[0], folder)
    except AV.AvatarError as e:
        raise A.ApplyError(str(e)) from e
    try:
        warns = A.update(sp, st, sh, lambda s: S.set_value(s, "lock.avatar", str(copy)))
    except BaseException:
        current = S.load(sp)[0]["lock"]["avatar"]
        if str(copy) != current:
            copy.unlink(missing_ok=True)
        raise
    AV.remove_others(folder, keep=copy)
    return warns


def _reset(args, sp, st, sh):
    """No TARGET: everything. Each TARGET is a SECTION or one KEY (`windows.rounding`); all of them are reset in one
    write and one apply, so a settings page can put its own keys back without a reload per key."""
    sections, keys = [], []
    for t in args:
        if t in SECTIONS:
            sections.append(t)
        elif t in S.RANGES and t != "wallpaper.path":
            keys.append(t)
        else:
            raise UsageError(f"unknown section or key {t!r} (sections: {', '.join(SECTIONS)})")

    def mutate(s):
        if not args:
            return copy.deepcopy(S.DEFAULTS)
        s = copy.deepcopy(s)
        for section in sections:
            s[section] = copy.deepcopy(S.DEFAULTS[section])
        for key in keys:
            section, name = key.split(".", 1)
            s[section][name] = copy.deepcopy(S.DEFAULTS[section][name])
        return s

    return A.update(sp, st, sh, mutate, clear_wallpaper=not args or "wallpaper" in sections)


def _defaults(args, sp, st, sh):
    if args:
        raise UsageError("defaults takes no arguments")
    print(json.dumps({"defaults": S.DEFAULTS, "gridMode": S.GRID_OVERRIDES, "gridRoundOff": S.GRID_ROUND_OFF}, sort_keys=True))
    return []


def _status(args, sp, st, sh):
    if args:
        raise UsageError("status takes no arguments")
    s, warns = S.load(sp)
    lines = [f"settings: {sp}", f"state dir: {st}"]
    for name in A.GENERATED:
        lines.append(f"{name}: {'yes' if (st / name).exists() else 'no'}")
    stamp = A.read_stamp_hash(st)
    if stamp is None:
        lines.append("fresh: unknown")
    elif stamp == A.settings_hash(s) and A._settings_file_ok(sp):  # a backup stand-in is not fresh
        lines.append("fresh: yes")
    else:
        lines.append("fresh: no (run bbkos-theme apply)")
    wp = s["wallpaper"]["path"]
    lines.append(f"wallpaper: {wp or 'none'}" + ("" if not wp or os.path.isfile(wp) else " (missing)"))
    lines.append(f"mode: {s['colors']['mode']}")
    lines.append(f"scheme: {s['colors']['scheme']}")
    print("\n".join(lines))
    return warns


def _contrast(args, sp, st, sh):
    """Measure the generated colors.json against the WCAG table in a11y.py: 4.5:1 for text, 3:1 for control parts and the
    focus ring. The tokens are built to pass (render.tokens); this proves the files on disk do."""
    if args:
        raise UsageError("contrast takes no arguments")
    path = st / "colors.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        tokens = dict(doc["colors"], ansi=doc["ansi"])
        tint = float(doc["shell"]["tint"])
        rows = a11y.pairs(tokens, tint)
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise A.ApplyError(f"cannot read {path}: {e.__class__.__name__}; run bbkos-theme apply") from e
    bad = [r for r in rows if r[1] + 1e-9 < r[2]]
    low = min(rows, key=lambda r: r[1] / r[2])
    print(f"{len(rows) - len(bad)} of {len(rows)} colour pairs pass (tint {tint:g}); "
          f"tightest: {low[0]} {low[1]:.2f}:1 (needs {low[2]:g}:1)")
    for name, ratio, floor in bad:
        print(f"  FAIL {name}: {ratio:.2f}:1, needs {floor:g}:1")
    if bad:
        raise A.ApplyError(f"{len(bad)} colour pair(s) below their contrast floor: run bbkos-theme apply")
    return []


COMMANDS = {"apply": _apply, "set": _set, "wallpaper": _wallpaper, "avatar": _avatar, "reset": _reset,
            "status": _status, "contrast": _contrast, "defaults": _defaults}


def _one_line(text):
    for line in str(text).splitlines():
        if line.strip():
            return line.strip()
    return "failed"


def main(argv):
    if argv[:1] in (["-h"], ["--help"], ["help"]):
        print(USAGE)
        return 0
    try:
        if not argv or argv[0] not in COMMANDS:
            raise UsageError(f"unknown command {argv[0]!r}" if argv else "missing command")
        warns = COMMANDS[argv[0]](list(argv[1:]), *paths())
    except UsageError as e:
        print(f"bbkos-theme: {_one_line(e)} (try --help)", file=sys.stderr)
        return 2
    except A.ApplyError as e:
        print(_one_line(e), file=sys.stderr)
        return 1
    except OSError as e:
        print(_one_line(f"{e.filename + ': ' if e.filename else ''}{e.strerror or e}"),
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    for w in warns:
        print(f"warning: {_one_line(w)}", file=sys.stderr)
    return 0
