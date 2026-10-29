"""Display settings: schema, validation, persistence, layout resolution.

Persisted per monitor (keyed by description, see monitor_key) in
~/.config/bbkos/displays.json. load() never raises: it always returns a
complete dict and a list of short warnings.
"""
import copy
import json
import math
from pathlib import Path

from .settings import _atomic_write

VERSION = 1
SCALES = (1.0, 1.1, 1.2, 1.25)
LAYOUT_MODES = ("extend", "mirror", "only")
POSITIONS = ("left", "right", "above", "below")

DEFAULTS = {"version": VERSION, "monitors": {}, "layouts": {}}


def scale_options(width, height):
    """Every offered scale. A scale that leaves a fractional logical size (1920 / 1.15) would be allowed, but SCALES
    offers only these four. width and height are kept for the callers and a future filter."""
    return list(SCALES)


def clamp_scale(scale, width, height):
    """The offered scale nearest to scale."""
    return min(scale_options(width, height), key=lambda s: (abs(s - scale), s))


def monitor_key(mon, all_mons):
    """Description, or 'name:<name>' when it is empty or shared by another monitor."""
    desc = mon.get("description") or ""
    shared = sum(1 for m in all_mons if (m.get("description") or "") == desc) > 1
    return f"name:{mon['name']}" if not desc or shared else desc


def combo_key(keys):
    return "\n".join(sorted(keys))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _validate(raw):
    out = copy.deepcopy(DEFAULTS)
    warns = []
    if not isinstance(raw, dict):
        return out, ["displays file is not an object, using defaults"]
    mons = raw.get("monitors")
    if "monitors" in raw and not isinstance(mons, dict):
        warns.append("ignored 'monitors': not an object")
    for key, v in (mons.items() if isinstance(mons, dict) else []):
        if isinstance(v, dict) and _is_num(v.get("scale")) and v["scale"] > 0 and isinstance(v.get("mode"), str):
            out["monitors"][key] = {"scale": float(v["scale"]), "mode": v["mode"]}
        else:
            warns.append(f"ignored invalid monitor entry {key!r}")
    lays = raw.get("layouts")
    if "layouts" in raw and not isinstance(lays, dict):
        warns.append("ignored 'layouts': not an object")
    for key, v in (lays.items() if isinstance(lays, dict) else []):
        if (isinstance(v, dict) and v.get("mode") in LAYOUT_MODES and isinstance(v.get("primary"), str)
                and v.get("position") in POSITIONS):
            out["layouts"][key] = {"mode": v["mode"], "primary": v["primary"], "position": v["position"]}
        else:
            warns.append(f"ignored invalid layout entry {key!r}")
    return out, warns


def load(path):
    path = Path(path)
    if not path.exists():
        return copy.deepcopy(DEFAULTS), []
    try:
        with open(path, encoding="utf-8") as f:
            return _validate(json.load(f))
    except (OSError, ValueError, RecursionError) as e:
        return copy.deepcopy(DEFAULTS), [f"{path.name} unreadable ({type(e).__name__}), using defaults"]


def save_atomic(path, data):
    clean, _ = _validate(data)
    _atomic_write(path, json.dumps(clean, indent=2) + "\n")


def mode_size(mon, saved):
    """Pixel size under the saved mode (WxH@R), else the current one."""
    try:
        w, h = saved["mode"].split("@")[0].split("x")
        return int(w), int(h)
    except (KeyError, ValueError, AttributeError):
        return mon["width"], mon["height"]


INTERNAL_PREFIXES = ("eDP", "LVDS", "DSI")


def is_internal(mon):
    return mon["name"].startswith(INTERNAL_PREFIXES)


def _output(mon, key):
    """Internal panels are selected by name (stable, and the selector bbkos-lid uses, so the two never hold
    separate rules for one panel); everything else by description (names change between ports and boots)."""
    return mon["name"] if key.startswith("name:") or is_internal(mon) else "desc:" + mon["description"]


def _rule(mon, key, data):
    saved = data["monitors"].get(key)
    rule = {"output": _output(mon, key),
            "mode": "preferred", "position": "auto", "scale": "auto", "disabled": False, "mirror": None}
    logical = None
    if saved:
        w, h = mode_size(mon, saved)
        rule["scale"] = clamp_scale(saved["scale"], w, h)
        rule["mode"] = saved["mode"]
        logical = (round(w / rule["scale"]), round(h / rule["scale"]))
    if logical is None:
        scale = mon.get("scale") or 1.0
        logical = (round(mon["width"] / scale), round(mon["height"] / scale))
    return rule, logical


def resolve(data, mons, lid_closed=False):
    """One monitor rule per connected monitor (dicts shaped like `hyprctl monitors all -j` entries).
    With the lid closed the internal panel is disabled, but only while another monitor stays enabled."""
    keys = [monitor_key(m, mons) for m in mons]
    pairs = [_rule(m, k, data) for m, k in zip(mons, keys)]
    rules = [r for r, _ in pairs]
    layout = data["layouts"].get(combo_key(keys)) if len(mons) == 2 else None
    if layout is not None:
        _layout(layout, keys, mons, pairs)
    if lid_closed:
        internal = [r for m, r in zip(mons, rules) if is_internal(m)]
        if any(not r["disabled"] for m, r in zip(mons, rules) if not is_internal(m)):
            for r in internal:
                r["disabled"] = True
    return rules


def _layout(layout, keys, mons, pairs):
    """Place the second monitor (or mirror / disable it) relative to the main one, in place on `pairs`."""
    pi = keys.index(layout["primary"]) if layout["primary"] in keys else 0
    si = 1 - pi
    (prim, (pw, ph)), (sec, (sw, sh)) = pairs[pi], pairs[si]
    prim["position"] = "0x0"
    if layout["mode"] == "mirror":
        sec["mirror"] = mons[pi]["name"]
        sec["position"] = "0x0"
    elif layout["mode"] == "only":
        sec["disabled"] = True
    else:
        x, y = {"right": (pw, 0), "left": (-sw, 0), "below": (0, ph), "above": (0, -sh)}[layout["position"]]
        sec["position"] = f"{x}x{y}"


HEADER = "-- bbkos-display: generated monitor rules from ~/.config/bbkos/displays.json. Do not edit.\n"


def render_lua(rules):
    from .reload import lua_quote
    from .render import num
    out = [HEADER]
    for r in rules:
        fields = [f"output = {lua_quote(r['output'])}", f"mode = {lua_quote(r['mode'])}",
                  f"position = {lua_quote(r['position'])}",
                  "scale = " + (lua_quote(r["scale"]) if r["scale"] == "auto" else num(r["scale"]))]
        if r["disabled"]:
            fields.append("disabled = true")
        if r["mirror"]:
            fields.append(f"mirror = {lua_quote(r['mirror'])}")
        out.append("hl.monitor({ " + ", ".join(fields) + " })\n")
    return "".join(out)
