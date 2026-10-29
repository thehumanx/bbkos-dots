"""bbkos-keybinds command line: edit keybinds.json, render hypr-binds.lua, reload Hyprland.

Hand-parsed like display_cli.py. Every mutation runs under an flock on <keybinds.json>.lock and either
completes (files written, Hyprland reloaded) or puts keybinds.json, its .bak and hypr-binds.lua back as they were.
"""
import contextlib
import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import keybinds as K
from .keybind_actions import ACTIONS, CATALOGUE, missing_tools
from .settings import _atomic_write

USAGE = """\
usage: bbkos-keybinds COMMAND
  status                                  binds, warnings, conflicts, the action catalogue and shipped ids as JSON
  add [--replace] --json FILE|-           add a bind (a full bind object)
  set ID [--replace] --json FILE|-        replace the bind ID
  remove ID                               delete a bind
  enable ID [--replace] | disable ID      turn a bind on or off
  restore ID [--replace]                  put a shipped bind back to its default
  restore-all                             replace every bind with the defaults
  render                                  write hypr-binds.lua only
  apply                                   render, then hyprctl reload
--replace disables any other enabled bind on the same keys (otherwise a clash exits 3).
environment: BBKOS_KEYBINDS, BBKOS_STATE_DIR override the paths"""

TIMEOUT = 5
DEFAULTS = Path(__file__).resolve().parent / "keybinds.defaults.json"
SKIPPED = "saved; reload skipped (Hyprland not running)"


class UsageError(Exception):
    pass


class ValidationError(Exception):
    pass


class ConflictError(Exception):
    pass


class KeybindError(Exception):
    pass


def paths(env):
    home = Path.home()
    return (Path(env.get("BBKOS_KEYBINDS") or home / ".config/bbkos/keybinds.json"),
            Path(env.get("BBKOS_STATE_DIR") or home / ".local/state/bbkos/theme"))


def _first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def _read_text(path):
    """The file's text, or None when it does not exist. Any other error propagates: a file we cannot read
    must never be treated as absent, or a rollback would delete it."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _restore(path, text):
    if text is None:
        try:
            os.unlink(os.path.realpath(path))
        except OSError:
            pass
    else:
        _atomic_write(path, text)


def _hyprctl(env):
    return shutil.which("hyprctl", path=env.get("PATH", os.defpath))


def _hypr(env, args):
    exe = _hyprctl(env)
    if not exe:
        raise KeybindError("hyprctl not found")
    try:
        return subprocess.run([exe, *args], env=env, capture_output=True, text=True,
                              timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        raise KeybindError(f"hyprctl failed: {e}")


def hyprland_running(env):
    return bool(env.get("HYPRLAND_INSTANCE_SIGNATURE")) and _hyprctl(env) is not None


def _reload(env):
    before = _hypr(env, ["configerrors"]).stdout.strip()
    res = _hypr(env, ["reload"])
    if res.returncode != 0:
        raise KeybindError(_first_line(res.stderr or res.stdout) or "hyprctl reload failed")
    after = _hypr(env, ["configerrors"]).stdout.strip()
    if after and after != before:
        raise KeybindError(f"Hyprland config errors: {_first_line(after)}")


def _redo_reload(env):
    """Reload once more from the restored files. Best effort; the original error is what gets reported."""
    try:
        _hypr(env, ["reload"])
    except (KeybindError, OSError):
        pass


@contextlib.contextmanager
def _locked(kb_path):
    lock = Path(str(kb_path) + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# Loading and checking

def load(kb_path):
    """(binds, warnings), every bind validated against the catalogue so rendering cannot fail."""
    return K.load_binds(kb_path, DEFAULTS, actions=set(ACTIONS))


def load_strict(kb_path):
    """The binds, or an error when the file is unusable or a row was dropped: writing it back would silently
    lose the user's entries, so nothing is changed until it is fixed (restore-all replaces it)."""
    binds, warns = load(kb_path)
    for w in warns:
        if w.startswith("skipped bind") or "is invalid" in w:
            raise KeybindError(f"{_first_line(w)}; fix or remove {kb_path} or run restore-all (nothing was changed)")
    return binds, warns


def _defaults():
    binds, warns = K.load_binds(DEFAULTS, DEFAULTS, actions=set(ACTIONS))
    bad = [w for w in warns if w.startswith("skipped bind") or "is invalid" in w]
    if bad:
        raise KeybindError(f"shipped defaults are broken: {_first_line(bad[0])}")
    return binds


def _read_json_arg(src):
    try:
        text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    except OSError as e:
        raise ValidationError(f"cannot read {src}: {e.strerror or e}")
    try:
        return json.loads(text)
    except ValueError as e:
        raise ValidationError(f"not valid JSON: {e}")


def _validate(raw):
    clean, msgs = K.validate_bind(raw, set(ACTIONS))
    if clean is None:
        raise ValidationError(msgs[0] if msgs else "invalid bind")
    return clean, msgs


def _index(binds, bid):
    for i, b in enumerate(binds):
        if b["id"] == bid:
            return i
    raise KeybindError(f"no bind with id {bid!r}")


def _combo_text(keys):
    mods, key = K.canonical_combo(keys)
    return " + ".join(mods + (key,))


def _resolve_conflicts(binds, bid, replace):
    """Disable (with replace) or refuse other enabled binds on the same keys as bind bid."""
    new = binds[_index(binds, bid)]
    if not new["enabled"]:
        return
    combo = K.canonical_combo(new["keys"])
    clash = [b for b in binds if b["id"] != bid and b["enabled"] and K.canonical_combo(b["keys"]) == combo]
    if clash and not replace:
        raise ConflictError(f"conflict: {_combo_text(new['keys'])} is already bound to "
                            f"{', '.join(b['id'] for b in clash)} (use --replace)")
    for b in clash:
        b["enabled"] = False


# Writing

def commit(env, kb_path, state_dir, binds, write_json=True, reload=True):
    """Write keybinds.json (old text kept in .bak) and hypr-binds.lua, then reload Hyprland.

    On any failure put every file back as it was (None = it did not exist) and, if a reload was attempted,
    reload once more from the restored files. Returns a status message or None."""
    lua = state_dir / "hypr-binds.lua"
    bak = Path(str(kb_path) + ".bak")
    text = K.render_lua(binds)                     # before touching anything: a render error writes nothing
    new_json = K.dumps(binds)
    old_json, old_bak, old_lua = _read_text(kb_path), _read_text(bak), _read_text(lua)
    reloaded = False
    try:
        if write_json:
            if old_json is not None:
                _atomic_write(bak, old_json)
            _atomic_write(kb_path, new_json)
        _atomic_write(lua, text)
        if not reload:
            return None
        if not hyprland_running(env):
            return SKIPPED
        reloaded = True
        _reload(env)
        return None
    except BaseException as original:
        restores = [(kb_path, old_json), (bak, old_bak)] if write_json else []
        failed = []
        for path, old in restores + [(lua, old_lua)]:
            try:                                   # one failed restore must not skip the rest
                _restore(path, old)
            except OSError as e:
                failed.append(f"warning: could not restore {path}: {e.strerror or e}")
        if reloaded:
            _redo_reload(env)
        # main() prints these after the error line, so the error stays the first line of stderr.
        original.restore_warnings = failed
        raise original


# Argument parsing helpers

def _take_flags(args, allow_json):
    """Split --replace and --json SRC off args. Returns (positional, replace, json_src)."""
    pos, replace, src, rest = [], False, None, list(args)
    while rest:
        a = rest.pop(0)
        if a == "--replace":
            replace = True
        elif a == "--json" and allow_json:
            if not rest:
                raise UsageError("--json needs FILE or -")
            src = rest.pop(0)
        elif a.startswith("--"):
            raise UsageError(f"unexpected option {a!r}")
        else:
            pos.append(a)
    return pos, replace, src


# Commands

def _status(args, env, kp, sd):
    if args:
        raise UsageError("status takes no arguments")
    binds, warns = load(kp)
    which = lambda c: shutil.which(c, path=env.get("PATH", os.defpath))  # noqa: E731
    actions = [dict(e, missing=missing_tools(e, which)) for e in CATALOGUE]
    print(json.dumps({"binds": binds, "warnings": warns,
                      "conflicts": [list(p) for p in K.find_conflicts(binds)], "actions": actions,
                      "shipped": [b["id"] for b in _defaults()]}))
    return [], None


def _add(args, env, kp, sd):
    pos, replace, src = _take_flags(args, True)
    if pos or src is None:
        raise UsageError("add needs --json FILE|-")
    new, warns = _validate(_read_json_arg(src))
    with _locked(kp):
        binds, _ = load_strict(kp)
        if any(b["id"] == new["id"] for b in binds):
            raise ValidationError(f"a bind with id {new['id']!r} already exists (use set)")
        binds.append(new)
        _resolve_conflicts(binds, new["id"], replace)
        return warns, commit(env, kp, sd, binds)


def _set(args, env, kp, sd):
    pos, replace, src = _take_flags(args, True)
    if len(pos) != 1 or src is None:
        raise UsageError("set needs ID --json FILE|-")
    raw = _read_json_arg(src)
    if isinstance(raw, dict) and "id" not in raw:
        raw = dict(raw, id=pos[0])
    new, warns = _validate(raw)
    if new["id"] != pos[0]:
        raise ValidationError(f"bind id {new['id']!r} does not match {pos[0]!r}")
    with _locked(kp):
        binds, _ = load_strict(kp)
        binds[_index(binds, pos[0])] = new
        _resolve_conflicts(binds, new["id"], replace)
        return warns, commit(env, kp, sd, binds)


def _remove(args, env, kp, sd):
    if len(args) != 1:
        raise UsageError("remove needs ID")
    with _locked(kp):
        binds, _ = load_strict(kp)
        del binds[_index(binds, args[0])]
        return [], commit(env, kp, sd, binds)


def _set_enabled(value):
    def run(args, env, kp, sd):
        pos, replace, _ = _take_flags(args, False)
        if len(pos) != 1 or (replace and not value):
            raise UsageError("enable needs ID [--replace]" if value else "disable needs ID")
        with _locked(kp):
            binds, _ = load_strict(kp)
            binds[_index(binds, pos[0])]["enabled"] = value
            _resolve_conflicts(binds, pos[0], replace)
            return [], commit(env, kp, sd, binds)
    return run


def _restore_one(args, env, kp, sd):
    pos, replace, _ = _take_flags(args, False)
    if len(pos) != 1:
        raise UsageError("restore needs ID")
    shipped = {b["id"]: b for b in _defaults()}
    if pos[0] not in shipped:
        raise ValidationError(f"{pos[0]!r} is not a shipped bind")
    with _locked(kp):
        binds, _ = load_strict(kp)
        try:
            binds[_index(binds, pos[0])] = shipped[pos[0]]
        except KeybindError:
            binds.append(shipped[pos[0]])
        _resolve_conflicts(binds, pos[0], replace)
        return [], commit(env, kp, sd, binds)


def _restore_all(args, env, kp, sd):
    if args:
        raise UsageError("restore-all takes no arguments")
    binds = _defaults()
    with _locked(kp):                              # no strict load: this is the way out of a broken file
        return [], commit(env, kp, sd, binds)


def _render(args, env, kp, sd):
    if args:
        raise UsageError("render takes no arguments")
    with _locked(kp):
        binds, warns = load(kp)
        commit(env, kp, sd, binds, write_json=False, reload=False)
        return warns, None


def _apply(args, env, kp, sd):
    if args:
        raise UsageError("apply takes no arguments")
    with _locked(kp):
        binds, warns = load(kp)
        return warns, commit(env, kp, sd, binds, write_json=False)


COMMANDS = {"status": _status, "add": _add, "set": _set, "remove": _remove,
            "enable": _set_enabled(True), "disable": _set_enabled(False),
            "restore": _restore_one, "restore-all": _restore_all, "render": _render, "apply": _apply}


def _fail(exc, message, code):
    """The error first (the settings page shows only the first stderr line), then any rollback warnings."""
    print(message, file=sys.stderr)
    for w in getattr(exc, "restore_warnings", ()):
        print(w, file=sys.stderr)
    return code


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    if argv[:1] in (["-h"], ["--help"], ["help"]):
        print(USAGE)
        return 0
    try:
        if not argv or argv[0] not in COMMANDS:
            raise UsageError(f"unknown command {argv[0]!r}" if argv else "missing command")
        warns, note = COMMANDS[argv[0]](list(argv[1:]), env, *paths(env))
    except UsageError as e:
        return _fail(e, f"bbkos-keybinds: {_first_line(str(e)) or 'usage error'} (try --help)", 2)
    except ValidationError as e:
        return _fail(e, _first_line(str(e)) or "invalid bind", 2)
    except ConflictError as e:
        return _fail(e, _first_line(str(e)) or "conflict", 3)
    except KeybindError as e:
        return _fail(e, _first_line(str(e)) or "failed", 1)
    except OSError as e:
        return _fail(e, _first_line(f"{e.filename + ': ' if e.filename else ''}{e.strerror or e}") or "failed", 1)
    except KeyboardInterrupt as e:
        return _fail(e, "interrupted", 130)
    for w in warns:
        print(f"warning: {_first_line(w)}", file=sys.stderr)
    if note:
        print(note)
    return 0
