"""Keybind data model: key normalisation, validation, load and save.

validate_bind() never raises. Action ids come in as an argument so this
module does not depend on the catalogue.
"""
import copy
import json
import string
from pathlib import Path

from .keybind_actions import DISPATCH_ARGS, expand
from .reload import lua_quote
from .settings import _atomic_write

VERSION = 1
CANON_MODS = ("SUPER", "CTRL", "ALT", "SHIFT")
FLAG_NAMES = ("locked", "repeating", "mouse")
ACTION_TYPES = ("exec", "dispatch", "preset")
MAX_COMMAND = 512
# Combos other software commonly expects to own (warning only).
RESERVED_COMBOS = frozenset({
    (("ALT",), "F4"),
    (("CTRL", "ALT"), "Delete"),
    (("CTRL", "ALT"), "BackSpace"),
    (("CTRL", "ALT"), "Escape"),
})

_ALIASES = {
    "enter": "Return",
    "return": "Return",
    ",": "comma",
    "comma": "comma",
    ";": "semicolon",
    ".": "period",
    "-": "minus",
    "=": "equal",
    "/": "slash",
    "\\": "backslash",
    "'": "apostrophe",
    "[": "bracketleft",
    "]": "bracketright",
    "`": "grave",
    "semicolon": "semicolon",
    "prior": "Page_Up",
    "page_up": "Page_Up",
    "insert": "Insert",
    "next": "Page_Down",
    "page_down": "Page_Down",
}

KNOWN_KEYS = frozenset(
    set(string.ascii_uppercase)
    | set(string.digits)
    | {f"F{n}" for n in range(1, 13)}
    | {"left", "right", "up", "down"}
    | {"Print", "Return", "Escape", "Tab", "space", "comma", "semicolon", "period", "minus", "equal", "slash",
       "backslash", "apostrophe", "bracketleft", "bracketright", "grave", "Insert", "Page_Up",
       "Page_Down", "Home", "End", "Delete", "BackSpace"}
    | {"XF86AudioLowerVolume", "XF86AudioRaiseVolume", "XF86AudioMute",
       "XF86AudioMicMute", "XF86AudioPlay", "XF86AudioPause", "XF86AudioNext",
       "XF86AudioPrev", "XF86MonBrightnessUp", "XF86MonBrightnessDown",
       "XF86PowerOff"}
    | {"mouse:272", "mouse:273", "mouse_down", "mouse_up",
       "switch:on:Lid Switch", "switch:off:Lid Switch"}
)


def key_alias(name):
    """Normalise a key name: aliases collapse, single letters/digits uppercase."""
    if not isinstance(name, str):
        return name
    hit = _ALIASES.get(name.lower())
    if hit:
        return hit
    if len(name) == 1 and name.isalnum():
        return name.upper()
    if name[:1] in "fF" and name[1:].isdigit():
        return "F" + name[1:]
    return name


def canonical_combo(keys):
    mods = set(keys.get("mods", []))
    return (tuple(m for m in CANON_MODS if m in mods), key_alias(keys.get("key")))


def _validate_action(action, actions):
    if not isinstance(action, dict):
        return None, "action must be an object"
    kind = action.get("type")
    if kind not in ACTION_TYPES:
        return None, "action type must be exec, dispatch or preset"
    if kind == "exec":
        cmd = action.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return None, "command is empty"
        if "\n" in cmd or "\r" in cmd:
            return None, "command has a newline"
        if len(cmd) > MAX_COMMAND:
            return None, f"command is longer than {MAX_COMMAND} characters"
        return {"type": "exec", "command": cmd}, None
    if kind == "dispatch":
        name = action.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, "dispatch name is empty"
        if name not in DISPATCH_ARGS:
            return None, f"unknown dispatcher {name}"
        args = action.get("args", {})
        if not isinstance(args, dict):
            return None, "dispatch args must be an object"
        return {"type": "dispatch", "name": name, "args": copy.deepcopy(args)}, None
    pid = action.get("id")
    if not isinstance(pid, str) or (actions is not None and pid not in actions):
        return None, f"unknown preset {pid!r}"
    return {"type": "preset", "id": pid}, None


def validate_bind(raw, actions):
    """Return (clean_bind, warnings) or (None, errors).

    `actions` is the set of valid preset ids; None skips the preset check.
    """
    if not isinstance(raw, dict):
        return None, ["bind is not an object"]
    bid = raw.get("id")
    if not isinstance(bid, str) or not bid:
        return None, ["bind has a missing or non-string id"]
    errs = []

    keys = raw.get("keys")
    mods, key = [], None
    if not isinstance(keys, dict) or set(keys) != {"mods", "key"}:
        errs.append("keys must be {mods, key}")
    else:
        raw_mods = keys["mods"]
        if not isinstance(raw_mods, list) or not all(isinstance(m, str) for m in raw_mods):
            errs.append("mods must be a list of names")
        else:
            bad = [m for m in raw_mods if m not in CANON_MODS]
            if bad:
                errs.append(f"unknown modifier {bad[0]}")
            mods = [m for m in CANON_MODS if m in raw_mods]
        if not isinstance(keys["key"], str):
            errs.append("key must be a string")
        else:
            key = key_alias(keys["key"])
            if key not in KNOWN_KEYS:
                errs.append(f"unknown key {keys['key']}")

    raw_flags = raw.get("flags", {})
    flags = {n: False for n in FLAG_NAMES}
    if not isinstance(raw_flags, dict):
        errs.append("flags must be an object")
    else:
        for name, val in raw_flags.items():
            if name not in FLAG_NAMES:
                errs.append(f"unknown flag {name}")
            elif not isinstance(val, bool):
                errs.append(f"flag {name} must be true or false")
            else:
                flags[name] = val

    action, err = _validate_action(raw.get("action"), actions)
    if err:
        errs.append(err)

    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        errs.append("enabled must be true or false")

    if key is not None and key.startswith("mouse:") and not flags["mouse"]:
        errs.append("mouse trigger needs the mouse flag")

    if key is not None and flags["locked"] and key == "XF86PowerOff":
        errs.append("the power key cannot be locked")

    if errs:
        return None, [f"{bid}: {e}" for e in errs]
    warns = []
    if (tuple(mods), key) in RESERVED_COMBOS:
        warns.append(f"{bid}: combo is commonly reserved by other software")
    if flags["locked"] and not key.startswith("XF86"):
        warns.append(f"{bid}: locked bind on a non-media key runs from the lock screen")
    return {"id": bid, "keys": {"mods": mods, "key": key}, "action": action,
            "flags": flags, "enabled": enabled}, warns


def _read_rows(path):
    """Return (rows, warning). rows is None when the file is unusable."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"keybinds.json is invalid, using defaults ({type(e).__name__})"
    if not isinstance(data, dict) or not isinstance(data.get("binds"), list):
        return None, "keybinds.json is invalid, using defaults"
    return data["binds"], None


def load_binds(path, defaults_path, actions=None):
    """Load binds from path, or the defaults. Returns (binds, warnings).

    `actions` is the set of valid preset ids; None accepts any preset id
    (the catalogue check then happens where the catalogue is known).
    """
    warnings = []
    rows = None
    if Path(path).exists():
        rows, warn = _read_rows(path)
        if warn:
            warnings.append(warn)
    if rows is None:
        rows, warn = _read_rows(defaults_path)
        if rows is None:
            return [], warnings + [warn]
    binds, seen = [], set()
    for raw in rows:
        clean, msgs = validate_bind(raw, actions)
        if clean is None:
            warnings.append(f"skipped bind: {msgs[0]}")
        elif clean["id"] in seen:
            warnings.append(f"skipped bind: {clean['id']}: duplicate id")
        else:
            seen.add(clean["id"])
            binds.append(clean)
            warnings.extend(msgs)
    return binds, warnings


def find_conflicts(binds):
    """Pairs of enabled bind ids sharing a canonical combo, in file order."""
    first, out = {}, []
    for b in binds:
        if not b.get("enabled", True):
            continue
        combo = canonical_combo(b["keys"])
        if combo in first:
            out.append((first[combo], b["id"]))
        else:
            first[combo] = b["id"]
    return out


def dumps(binds):
    return json.dumps({"version": VERSION, "binds": binds}, indent=2) + "\n"


def save_atomic(path, binds):
    _atomic_write(path, dumps(binds))


# Dispatchers whose single argument is passed positionally, not as a table.
_POSITIONAL = frozenset({"exec_cmd", "layout", "workspace.toggle_special"})
_HEADER = ("-- Generated by bbkos from keybinds.json (defaults: keybinds.defaults.json). "
           "Do not edit.\n")


def _lua_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return lua_quote(str(v))


def _render_dispatch(name, args):
    keys = [k for k in DISPATCH_ARGS[name] if k in args]
    if name in _POSITIONAL:
        body = _lua_value(args[keys[0]]) if keys else ""
    elif keys:
        body = "{ " + ", ".join("%s = %s" % (k, _lua_value(args[k])) for k in keys) + " }"
    else:
        body = ""
    return "hl.dsp.%s(%s)" % (name, body)


# In stage mode (monocle) the windows of a workspace are stacked, so a directional focus has nowhere to go; the same
# keys cycle through them instead. Decided when the key is pressed, from the active workspace's own layout (stage mode
# is per workspace since 2026-10-23), so no regeneration is needed when stage mode is switched.
_IS_STAGE = 'local ws = hl.get_active_workspace(); local stage = ws ~= nil and ws.tiled_layout == "monocle"; '

_STAGE_CYCLE = {"left": "cycleprev", "up": "cycleprev", "right": "cyclenext", "down": "cyclenext"}


def _render_focus(args):
    direction = args["direction"]
    return ('function() ' + _IS_STAGE + 'if stage then '
            'hl.dispatch(hl.dsp.layout("%s")) else hl.dispatch(%s) end end'
            % (_STAGE_CYCLE[direction], _render_dispatch("focus", args)))


# Alt+Tab works like a browser's Ctrl+Tab: a tap goes back to the previous window (most recently used first), and while
# the modifier stays down each further Tab steps deeper into that order; releasing the modifier ends the cycle. Hyprland's
# own focus history cannot be used to put the order right afterwards (in monocle only the first focus of several in one
# call takes effect, measured 2026-10-26), so BBKOS_MRU keeps the order itself: window.active moves a window to the front
# (not while a cycle runs, since each step really focuses the window), and the release moves the chosen one to the front.
# The list is seeded from the focus history when the config first loads; windows that are gone or on another workspace
# are skipped when a cycle starts.
_CYCLE_LUA = """\
BBKOS_MRU = BBKOS_MRU or {}
local function bbkos_touch(w)
  for i, a in ipairs(BBKOS_MRU) do
    if a == w.address then table.remove(BBKOS_MRU, i) break end
  end
  table.insert(BBKOS_MRU, 1, w.address)
end
if #BBKOS_MRU == 0 then
  local all = hl.get_windows({})
  table.sort(all, function(a, b) return a.focus_history_id < b.focus_history_id end)
  for _, w in ipairs(all) do BBKOS_MRU[#BBKOS_MRU + 1] = w.address end
end
if BBKOS_ACTIVE_SUB then BBKOS_ACTIVE_SUB:remove() end
BBKOS_ACTIVE_SUB = hl.on("window.active", function(w)
  if w and not BBKOS_CYCLE then bbkos_touch(w) end
end)
function bbkos_cycle(step)
  local c = BBKOS_CYCLE
  if not c then
    local ws = hl.get_active_workspace()
    if not ws then return end
    local rank, list = {}, {}
    for i, a in ipairs(BBKOS_MRU) do rank[a] = i end
    for _, w in ipairs(hl.get_windows({ workspace = ws.id })) do
      if w.mapped then list[#list + 1] = w end
    end
    if #list < 2 then return end
    table.sort(list, function(a, b)
      if a.active ~= b.active then return a.active end
      local ra, rb = rank[a.address], rank[b.address]
      if ra and rb then return ra < rb end
      if ra or rb then return ra ~= nil end
      return a.focus_history_id < b.focus_history_id
    end)
    c = { list = list, idx = 1 }
    BBKOS_CYCLE = c
  end
  c.idx = (c.idx - 1 + step) % #c.list + 1
  local w = c.list[c.idx]
  if pcall(hl.dispatch, hl.dsp.focus({ window = "address:" .. w.address })) then
    hl.dispatch(hl.dsp.window.bring_to_top())
  end
end
function bbkos_cycle_end()
  local c = BBKOS_CYCLE
  BBKOS_CYCLE = nil
  if c then bbkos_touch(c.list[c.idx]) end
end
"""

# xkb keycodes (evdev + 8) of the modifier keys a cycle can be held on.
_RELEASE_KEYS = {"SUPER": (133, 134), "CTRL": (37, 105), "ALT": (64, 108)}


def _render_cycle(args, mods):
    """One Alt+Tab press. Shift only picks the direction, so the cycle ends when the other modifiers go up; a combo
    with no other modifier has nothing to hold, so each press is a whole cycle."""
    step = "-1" if args.get("direction") == "prev" else "1"
    end = "" if any(m in _RELEASE_KEYS for m in mods) else "; bbkos_cycle_end()"
    return "function() bbkos_cycle(%s)%s end" % (step, end)


def _cycle_release_hook(mods_used):
    """Ends the cycle when a held modifier of any cycle bind is released. A release bind cannot do this: Hyprland does
    not deliver one for a modifier once another key (Tab) was pressed in between (measured 2026-10-26), but the raw key
    event (keycode, time, state 1/0) always arrives. The old subscription is removed first so a config reload does not stack them."""
    codes = sorted(c for m in mods_used for c in _RELEASE_KEYS.get(m, ()))
    table = ", ".join("[%d] = true" % c for c in codes)
    return ("if BBKOS_CYCLE_KEYS then BBKOS_CYCLE_KEYS:remove() end\n"
            "local cycle_mods = { %s }\n"
            'BBKOS_CYCLE_KEYS = hl.on("input.keyboard.key", function(code, _, state)\n'
            "  if state == 0 and cycle_mods[code] then bbkos_cycle_end() end\n"
            "end)\n" % table)


# Binds whose action is a few lines of Lua that look at the live window or config when the key is pressed. Decided at press
# time, so no regeneration is needed. (Added 2026-10-21, ported from Omarchy's scripts; docs/modules/keybindings.md.)
_LUA_FUNCTIONS = {
    # Tiled fullscreen: the window fills the screen while the app still believes it is tiled (client state 2); again to undo.
    "window.tiled_fullscreen": (
        'function() local w = hl.get_active_window(); if not w then return end; '
        'hl.dispatch(hl.dsp.window.fullscreen_state({ internal = 0, client = (w.fullscreen_client == 2) and 0 or 2 })) end'),
    # Force the focused window opaque, or give it its transparency back.
    "window.toggle_opaque": (
        'function() local w = hl.get_active_window(); if not w then return end; '
        'hl.dispatch(hl.dsp.window.set_prop({ window = "address:" .. w.address, prop = "opaque", value = "toggle" })) end'),
    # All gaps to 0, and back to what they were (the values are kept in BBKOS_GAPS until the next config reload, which
    # resets the gaps itself).
    "window.toggle_gaps": (
        'function() if BBKOS_GAPS then hl.config({ general = { gaps_in = BBKOS_GAPS[1], gaps_out = BBKOS_GAPS[2] } }); '
        'BBKOS_GAPS = nil else BBKOS_GAPS = { hl.get_config("general.gaps_in"), hl.get_config("general.gaps_out") }; '
        'hl.config({ general = { gaps_in = 0, gaps_out = 0 } }) end end'),
}


def render_lua(binds):
    """Hyprland Lua for the enabled binds, in list order (header comment first)."""
    lines = [_HEADER]
    cycle_mods = set()
    for b in binds:
        if not b.get("enabled", True):
            continue
        mods, key = canonical_combo(b["keys"])
        keys = lua_quote(" + ".join(mods + (key,)))
        action = expand(b["action"])
        if action["type"] == "exec":
            dsp = _render_dispatch("exec_cmd", {"command": action["command"]})
        elif action["name"] == "focus" and action.get("args", {}).get("direction") in _STAGE_CYCLE:
            dsp = _render_focus(action["args"])
        elif action["name"] in _LUA_FUNCTIONS:
            dsp = _LUA_FUNCTIONS[action["name"]]
        elif action["name"] == "window.cycle":
            dsp = _render_cycle(action.get("args", {}), mods)
            cycle_mods.update(mods)
        else:
            dsp = _render_dispatch(action["name"], action.get("args", {}))
        flags = b.get("flags", {})
        opts = [n for n in FLAG_NAMES if flags.get(n)]
        if "mouse" in opts:
            opts = ["mouse"]
        tail = ", { %s }" % ", ".join("%s = true" % n for n in opts) if opts else ""
        lines.append("hl.bind(%s, %s%s)\n" % (keys, dsp, tail))
    if cycle_mods:
        lines.insert(1, _CYCLE_LUA)
        lines.append(_cycle_release_hook(cycle_mods))
    return "".join(lines)
