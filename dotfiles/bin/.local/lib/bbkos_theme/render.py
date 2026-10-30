"""Pure renderers: palette + settings -> token dict and config file text."""
import json
import os
import re

from . import a11y, contrast

# OKLCH lightness targets for ANSI colours (chroma and hue are kept from the
# palette role, except near-grey roles, see below): normals sit mid-range so
# brights have headroom without drifting toward the foreground.
DARK_NORMAL_L, DARK_BRIGHT_STEP, DARK_BRIGHT_CEIL = 0.72, 0.07, 0.85
LIGHT_NORMAL_L, LIGHT_BRIGHT_STEP, LIGHT_BRIGHT_FLOOR = 0.52, 0.07, 0.40
SCALARS = ("bg", "surface", "fg", "dim", "accent", "warn", "crit", "outline",
           "borderActive1", "borderActive2", "borderInactive",
           "secondary", "tertiary", "accentSoft", "secondarySoft", "tertiarySoft", "surfaceHigh", "gridEdge")
SHELL_KEYS = ("barHeight", "gap", "radius", "controlRadius", "fontSize", "font",
              "barPosition", "barOpacity", "barBlur", "barBlurAmount", "barPills", "pillRadius", "barItemGap", "barItemPad", "pillOpacity", "tint", "barFloat", "barHug", "barRadius",
              "popupShadow", "reduceMotion", "gridMode", "gridRoundControls")
GRID_EDGE_STRENGTH = 0.22   # how far the grid border leans from the surface toward the text colour
ANSI_ROLES = ("ansi_red", "ansi_green", "ansi_yellow", "ansi_blue", "ansi_magenta", "ansi_cyan")
# Near-grey repair: matugen can return a custom colour as white or almost
# white (seen live: yellow and cyan #ffffff under scheme fidelity), which has
# no usable hue, so two roles would render as the same grey. Such a role gets
# its canonical OKLCH hue and a modest chroma (still reduced to fit the gamut).
NEAR_GREY_CHROMA = 0.04
NEAR_GREY_MIN_CHROMA = 0.09
CANONICAL_HUE = {"ansi_red": 29, "ansi_green": 142, "ansi_yellow": 100,
                 "ansi_blue": 264, "ansi_magenta": 328, "ansi_cyan": 195}


def num(v):
    """ints as ints; floats rounded to 2 decimals, never scientific."""
    if isinstance(v, int):
        return str(v)
    s = f"{round(float(v), 2):.2f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def lua_bool(v):
    return "true" if v else "false"


TINT_HUE_STEP = 40       # degrees either side of the wallpaper's own hue


# The palette colours the accent and the tints come from: matugen's primary and tertiary, and the two primary tones
# (palette.TONES). `colors.accentStrength` scales their chroma before anything is derived or lifted to its contrast floor.
ACCENT_SOURCES = ("primary", "tertiary", "tone_primary", "soft_primary")


def mute(hex_colour, strength):
    """`hex_colour` with its OKLCH chroma multiplied by `strength` (0 = grey); lightness and hue are kept."""
    if strength >= 1.0:
        return hex_colour
    l, c, hue = contrast.to_oklch(hex_colour)
    return contrast.from_oklch(l, c * strength, hue)


def soft_tints(palette):
    """The deep shades used as backgrounds (hover, pills, the active page): accent-soft is the primary's deep shade, the
    other two the same shade with the hue turned -/+ TINT_HUE_STEP degrees. No floor: text on them is what is checked."""
    out = {"accentSoft": palette["soft_primary"]}
    for name, step in (("secondary", -TINT_HUE_STEP), ("tertiary", TINT_HUE_STEP)):
        l, c, hue = contrast.to_oklch(palette["soft_primary"])
        out[name + "Soft"] = contrast.from_oklch(l, c, (hue + step) % 360)
    return out


def hue_tints(palette, ensure):
    """secondary / tertiary: the wallpaper's primary tone with its hue turned -/+ TINT_HUE_STEP degrees (same lightness and
    chroma, chroma only reduced to fit the gamut), then lifted by `ensure` to read as text. A grey wallpaper keeps every
    tint grey."""
    out = {}
    for name, step in (("secondary", -TINT_HUE_STEP), ("tertiary", TINT_HUE_STEP)):
        l, c, hue = contrast.to_oklch(palette["tone_primary"])
        out[name] = ensure(contrast.from_oklch(l, c, (hue + step) % 360))
    return out


def tokens(palette, settings):
    """The colour tokens, with every text and control colour lifted until it clears its WCAG floor on every surface it is
    drawn on (a11y.py lists the surfaces; docs/modules/theme.md the reasoning). Lifting moves OKLCH lightness only, so the
    wallpaper's hue and chroma are kept; a colour that already clears its floors is not touched."""
    strength = settings["colors"]["accentStrength"]
    palette = dict(palette, **{k: mute(palette[k], strength) for k in ACCENT_SOURCES})
    bg = palette["surface"]
    container = palette["surface_container"]
    surface_high = palette["surface_high"]
    tint = settings["shell"]["tint"]
    light = settings["colors"]["mode"] == "light"
    soft = soft_tints(palette)
    T, U = a11y.TEXT, a11y.UI

    # fg first: the control surface mixes 12% of fg into the popup, so it moves with fg; a few rounds settle it
    fg = palette["on_surface"]
    for _ in range(6):
        s = a11y.surfaces(bg, container, soft["accentSoft"], surface_high, fg, tint)
        lifted = contrast.ensure_all(palette["on_surface"], [(s[b], T) for b in a11y.FG_ON]
                                     + [(s["popup"], U, 0.55), (s["inset"], U, 0.85)])
        if lifted == fg:
            break
        fg = lifted
    s = a11y.surfaces(bg, container, soft["accentSoft"], surface_high, fg, tint)

    def on(names, floor=T):
        return [(s[b], floor) for b in names]

    text_on_accent_surfaces = lambda c: contrast.ensure_all(c, on(a11y.ACCENT_TEXT_ON))
    signal = lambda c: contrast.ensure_all(c, on(a11y.SIGNAL_ON))
    dim = contrast.ensure_all(palette["outline"], on(a11y.DIM_ON))
    ensure = lambda c, floor: contrast.ensure_contrast(c, bg, floor)
    white = ensure(palette["on_surface_variant"], T)
    normal, bright = [], []
    for role in ANSI_ROLES:
        _, c, hue = contrast.to_oklch(palette[role])
        if c < NEAR_GREY_CHROMA:
            c, hue = NEAR_GREY_MIN_CHROMA, CANONICAL_HUE[role]
        if light:
            ln, lb = LIGHT_NORMAL_L, LIGHT_NORMAL_L - LIGHT_BRIGHT_STEP
            lb = max(lb, LIGHT_BRIGHT_FLOOR)
        else:
            ln, lb = DARK_NORMAL_L, min(DARK_NORMAL_L + DARK_BRIGHT_STEP, DARK_BRIGHT_CEIL)
        normal.append(ensure(contrast.from_oklch(ln, c, hue), T))
        bright.append(ensure(contrast.from_oklch(lb, c, hue), T))
    return {
        "bg": bg, "surface": container, "fg": fg, "dim": dim,
        "accent": contrast.ensure_all(palette["primary"], on(a11y.ACCENT_TEXT_ON) + [(s["accentSoft"], U)]),
        "warn": signal(palette["warn"]),
        "crit": signal(palette["error"]),
        "outline": palette["outline"],
        # the focus ring (the active window border) is a UI component: 3:1 against the window colour
        "borderActive1": ensure(palette["primary"], U), "borderActive2": ensure(palette["tertiary"], U),
        "borderInactive": palette["outline_variant"],
        # Wallpaper tints for widgets and controls: two more accent hues and a deep shade of each, plus a raised surface.
        **hue_tints(palette, text_on_accent_surfaces), **soft,
        "surfaceHigh": surface_high,
        # Grid mode's cell border: one opaque colour (the surface lifted toward the text colour), so a joint where two cells
        # or windows overlap paints the same colour as the rest of the line instead of two translucent layers stacked.
        "gridEdge": contrast.blend(container, fg, GRID_EDGE_STRENGTH),
        # 0 is the background, 7 (white) and 8 (bright black, used for comments) are the secondary text tiers: all 4.5:1
        "ansi": [container] + normal + [white, dim] + bright + [fg],
    }


def render_colors_json(t, settings):
    doc = {"colors": {k: t[k] for k in SCALARS}, "ansi": list(t["ansi"]),
           "shell": {k: settings["shell"][k] for k in SHELL_KEYS}}
    return json.dumps(doc, indent=2) + "\n"


def _rgba(h, alpha):
    return f"rgba({h.lstrip('#')}{alpha})"


# Multi-finger swipe settings: key -> (fingers, direction). Three-finger left and right are not here: Hyprland's
# built-in horizontal workspace swipe already covers them, and a per-direction gesture for the same fingers is ignored.
SWIPES = {"swipe3Up": (3, "up"), "swipe3Down": (3, "down"),
          "swipe4Up": (4, "up"), "swipe4Down": (4, "down"), "swipe4Left": (4, "left"), "swipe4Right": (4, "right")}
SWIPE_LUA = {"workspace": "workspace", "close": "close", "fullscreen": "fullscreen", "float": "float", "special": "special"}
# Overview actions are not stock Hyprland gesture actions: they call the workspace overview through its IPC
# (modules/overview). Emitted as a Lua-function action, which Hyprland 0.56 runs on the completed gesture. The
# direct form (hl.exec_cmd) is used: inside a function, hl.dsp.exec_cmd only builds a dispatcher object and runs nothing.
SWIPE_FUNCS = {
    "overview": 'function() hl.exec_cmd("qs ipc call overview open") end',
    "overview-close": 'function() hl.exec_cmd("qs ipc call overview close") end',
}


def _swipe_action(action):
    func = SWIPE_FUNCS.get(action)
    return func if func is not None else f'"{SWIPE_LUA[action]}"'


S_FOLLOW = {"click": 0, "hover": 1, "detached": 2}      # settings.FOLLOW_MOUSE


def render_input_extra(settings):
    """Keyboard and mouse lines for the input block of hypr-theme.lua (layout, repeat, pointer). Values left at Hyprland's own
    default ("default" acceleration, no options) are left out. Every value was validated by settings.py, so none can break
    out of its Lua string."""
    k, m = settings["keyboard"], settings["mouse"]
    lines = [f'    kb_layout = "{k["layout"]}",', f'    kb_variant = "{k["variant"]}",',
             f'    kb_options = "{"" if k["options"] == "none" else k["options"]}",',
             f'    repeat_rate = {num(k["repeatRate"])},', f'    repeat_delay = {num(k["repeatDelay"])},',
             f'    numlock_by_default = {lua_bool(k["numlock"])},',
             f'    sensitivity = {num(m["sensitivity"])},',
             f'    natural_scroll = {lua_bool(m["naturalScroll"])},', f'    left_handed = {lua_bool(m["leftHanded"])},']
    if m["accelProfile"] != "default":
        lines.append(f'    accel_profile = "{m["accelProfile"]}",')
    lines.append(f'    follow_mouse = {S_FOLLOW[settings["behavior"]["followMouse"]]},')
    return lines


def render_behavior(settings):
    """The misc, binds, cursor and snap entries of the Window behaviour page for the one hl.config call (follow_mouse is
    in the input block, render_input_extra). cursor.no_warps is the opposite of the page's "cursor follows focus"."""
    b = settings["behavior"]
    return ("  binds = {\n"
            f"    workspace_back_and_forth = {lua_bool(b['workspaceBackAndForth'])},\n"
            "  },\n"
            "  cursor = {\n"
            f"    hide_on_key_press = {lua_bool(b['hideCursorWhenTyping'])},\n"
            f"    inactive_timeout = {num(b['cursorHideAfter'])},\n"
            f"    no_warps = {lua_bool(not b['cursorWarps'])},\n"
            "  },\n")


def render_cursor_env(settings):
    """hl.env lines: apps started from now on pick up the cursor theme and size (the running ones are changed by
    `hyprctl setcursor` and gsettings, reload.reload_cursor)."""
    c = settings["cursor"]
    return "".join(f'hl.env("{k}", "{v}")\n' for k, v in (
        ("XCURSOR_THEME", c["theme"]), ("HYPRCURSOR_THEME", c["theme"]),
        ("XCURSOR_SIZE", c["size"]), ("HYPRCURSOR_SIZE", c["size"])))


def render_touchpad_parts(tp, extra=()):
    """(config, gestures): the input and gesture entries for the one hl.config call, and the hl.gesture lines
    after it. Values set to "auto" or "none" are left out, so Hyprland keeps its own default."""
    inp = list(extra)
    if tp["scrollMethod"] != "auto":
        inp.append(f'    scroll_method = "{tp["scrollMethod"]}",')
    pad = [
        f'      natural_scroll = {lua_bool(tp["naturalScroll"])},',
        f'      scroll_factor = {num(tp["scrollFactor"])},',
        f'      flip_x = {lua_bool(tp["flipX"])},',
        f'      flip_y = {lua_bool(tp["flipY"])},',
        f'      tap_to_click = {lua_bool(tp["tapToClick"])},',
        f'      tap_and_drag = {lua_bool(tp["tapAndDrag"])},',
        f'      drag_lock = {num(tp["dragLock"])},',
        f'      clickfinger_behavior = {lua_bool(tp["clickfingerBehavior"])},',
        f'      middle_button_emulation = {lua_bool(tp["middleButtonEmulation"])},',
        f'      drag_3fg = {num(tp["drag3fg"])},',
        f'      disable_while_typing = {lua_bool(tp["disableWhileTyping"])},',
    ]
    if tp["tapButtonMap"] != "auto":
        pad.append(f'      tap_button_map = "{tp["tapButtonMap"]}",')
    gest = [
        f'    workspace_swipe_distance = {num(tp["wsSwipeDistance"])},',
        f'    workspace_swipe_invert = {lua_bool(tp["wsSwipeInvert"])},',
        f'    workspace_swipe_cancel_ratio = {num(tp["wsSwipeCancelRatio"])},',
        f'    workspace_swipe_direction_lock = {lua_bool(tp["wsSwipeDirectionLock"])},',
        f'    workspace_swipe_create_new = {lua_bool(tp["wsSwipeCreateNew"])},',
        f'    workspace_swipe_forever = {lua_bool(tp["wsSwipeForever"])},',
    ]
    config = ("  input = {\n" + "".join(l + "\n" for l in inp)
              + "    touchpad = {\n" + "".join(l + "\n" for l in pad) + "    },\n  },\n"
              + "  gestures = {\n" + "".join(l + "\n" for l in gest) + "  },\n")
    swipes = "".join(
        f'hl.gesture({{ fingers = {SWIPES[k][0]}, direction = "{SWIPES[k][1]}", action = {_swipe_action(tp[k])} }})\n'
        for k in SWIPES if tp[k] != "none")
    return config, swipes


# Motion (docs/modules/motion.md): Emil Kowalski's curves (github.com/emilkowalski/skills, emil-design-eng), the same
# ones Theme.qml uses. Hyprland's speed is in tenths of a second: 2 = 200 ms. Things that appear ease out (fast start);
# leaving is quicker than arriving; a workspace slides with the iOS drawer curve, matching the three-finger swipe.
MOTION_CURVES = (("bbkOut", (0.23, 1), (0.32, 1)),
                 ("bbkDrawer", (0.32, 0.72), (0, 1)))


def render_motion(reduce, factor=1.0):
    """hl.curve / hl.animation lines. Reduced motion keeps the fades and drops movement: windows do not pop in or glide,
    and workspaces cross-fade instead of sliding. `factor` (windows.animationSpeed) makes every animation that many times
    faster (below 1: slower); each speed is its duration in tenths of a second, so it is divided by the factor."""
    curves = "".join(f'hl.curve("{n}", {{ type = "bezier", points = {{ {{{a[0]:g}, {a[1]:g}}}, '
                     f'{{{b[0]:g}, {b[1]:g}}} }} }})\n' for n, a, b in MOTION_CURVES)
    move = not reduce
    rows = (("global", True, 2, "bbkOut", None),
            ("windowsIn", move, 2.2, "bbkOut", "popin 90%"),
            ("windowsOut", move, 1.4, "bbkOut", "popin 90%"),
            ("windowsMove", move, 2.6, "bbkOut", None),
            ("border", True, 2, "bbkOut", None),
            ("fadeIn", True, 1.8, "bbkOut", None),
            ("fadeOut", True, 1.4, "bbkOut", None),
            ("fadeSwitch", True, 2, "bbkOut", None),
            ("layersIn", True, 1.6, "bbkOut", "fade"),
            ("layersOut", True, 1.2, "bbkOut", "fade"),
            ("fadeLayersIn", True, 1.6, "bbkOut", None),
            ("fadeLayersOut", True, 1.2, "bbkOut", None),
            ("workspaces", True, 2.6, "bbkDrawer", "fade" if reduce else "slide"),
            ("specialWorkspace", True, 2.4, "bbkDrawer", "fade" if reduce else "slidevert"),
            ("zoomFactor", True, 3, "bbkOut", None))
    anims = "".join(f'hl.animation({{ leaf = "{leaf}", enabled = {lua_bool(on)}, speed = {num(speed if factor == 1 else round(speed / factor, 2))}, '
                    f'bezier = "{curve}"' + (f', style = "{style}"' if style else "") + " })\n"
                    for leaf, on, speed, curve, style in rows)
    return curves + anims


def render_hypr_lua(t, settings):
    w = settings["windows"]
    sh = settings["shell"]
    tp_config, tp_gestures = render_touchpad_parts(settings["touchpad"], render_input_extra(settings))
    # Stage mode default for every workspace (each window opens alone, full size); off: the normal tiling layout. One
    # workspace can differ until the next boot (StageState.qml adds a runtime workspace rule).
    layout = "monocle" if settings["stage"]["enabled"] else "dwindle"
    inactive = _rgba(t['gridEdge'], 'ff') if sh['gridMode'] else _rgba(t['borderInactive'], 'aa')
    # windows.activeBorder off: the focused window gets the inactive colour, so only the window's own border size remains.
    active = f'{{ colors = {{ "{_rgba(t["borderActive1"], "ee")}", "{_rgba(t["borderActive2"], "ee")}" }}, angle = 45 }}' if w['activeBorder'] else f'"{inactive}"'
    return f"""-- Generated by bbkos-theme. Do not edit.
hl.config({{
  general = {{
    layout = "{layout}",
    gaps_in = {num(w['gapsIn'])},
    gaps_out = {num(w['gapsOut'])},
    border_size = {num(w['borderSize'])},
    resize_on_border = {lua_bool(w['resizeOnBorder'])},
    extend_border_grab_area = {num(w['borderGrabArea'])},
    snap = {{ enabled = {lua_bool(settings['behavior']['snap'])}, window_gap = {num(settings['behavior']['snapGap'])}, monitor_gap = {num(settings['behavior']['snapGap'])} }},
    col = {{
      active_border = {active},
      inactive_border = "{inactive}",
    }},
  }},
  decoration = {{
    rounding = {num(w['rounding'])},
    active_opacity = {num(w['activeOpacity'])},
    inactive_opacity = {num(w['inactiveOpacity'])},
    shadow = {{ enabled = {lua_bool(w['shadowEnabled'])}, range = {num(w['shadowRange'])} }},
    blur = {{ enabled = {lua_bool(w['blurEnabled'])}, size = {num(w['blurSize'])}, passes = {num(w['blurPasses'])} }},
  }},
  animations = {{ enabled = {lua_bool(w['animations'])} }},
  misc = {{ background_color = 0xff{t['bg'].lstrip('#')}, focus_on_activate = {lua_bool(settings['behavior']['focusOnActivate'])} }},
{render_behavior(settings)}{tp_config}}})
{render_cursor_env(settings)}{tp_gestures}{render_motion(sh['reduceMotion'], w['animationSpeed'])}"""


def render_kitty_conf(t, settings):
    term = settings["terminal"]
    lines = ["# Generated by bbkos-theme. Do not edit.",
             f"foreground {t['fg']}", f"background {t['bg']}",
             f"cursor {t['accent']}", f"cursor_text_color {t['bg']}",
             f"selection_foreground {t['bg']}", f"selection_background {t['accent']}",
             f"url_color {t['accent']}"]
    lines += [f"color{i} {c}" for i, c in enumerate(t["ansi"])]
    lines += [f"font_size {num(term['fontSize'])}",
              f"window_padding_width {num(term['padding'])}",
              f"background_opacity {num(term['opacity'])}"]
    return "\n".join(lines) + "\n"


def _css_rgba(h, alpha):
    h = h.lstrip("#")
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})"


def render_gtk_css(t, settings):
    """GTK 3 and GTK 4 (libadwaita) colour definitions. GTK 3 reads them through the generated theme bbkos-a / bbkos-b
    (render_gtk3_theme, written by reload.reload_gtk), so an open app recolours when the theme name flips; GTK 4 imports
    this file from ~/.config/gtk-4.0/gtk.css at start. The stock GTK 3 Adwaita bakes most of its colours into the
    stylesheet, so overrides do nothing there; adw-gtk3 is built on the libadwaita names (window_bg_color,
    accent_bg_color ...) and takes them. The theme_* names are kept for older themes. Surfaces follow the shell: the
    content area (view) is the window colour, the frame around it (toolbar, menu bar, sidebar, header bar) the tinted
    popup surface, a selected sidebar row the accent's deep shade, as in the settings window. Text roles are already
    lifted to their contrast floors on these surfaces (tokens, a11y.FG_ON / DIM_ON). The comment markers at the top
    (mode, accent, folders) are read back by reload.reload_gtk."""
    on_accent = t["bg"]                                    # the text on a selection or an accent button (as in the shell)
    frame = a11y.token_surfaces(t, settings["shell"]["tint"])["popup"]
    c = {  # name -> colour
        "theme_bg_color": frame, "theme_fg_color": t["fg"],
        "theme_base_color": t["bg"], "theme_text_color": t["fg"],
        "theme_selected_bg_color": t["accentSoft"], "theme_selected_fg_color": t["fg"],
        "insensitive_bg_color": t["surface"], "insensitive_fg_color": t["dim"],
        "theme_unfocused_bg_color": frame, "theme_unfocused_fg_color": t["fg"],
        "theme_unfocused_base_color": t["bg"], "theme_unfocused_text_color": t["fg"],
        "theme_unfocused_selected_bg_color": t["accentSoft"], "theme_unfocused_selected_fg_color": t["fg"],
        "theme_tooltip_bg_color": t["surfaceHigh"], "theme_tooltip_fg_color": t["fg"],
        "borders": _css_rgba(t["fg"], 0.2), "unfocused_borders": _css_rgba(t["fg"], 0.2),
        "warning_color": t["warn"], "error_color": t["crit"], "success_color": t["secondary"],
        "accent_bg_color": t["accent"], "accent_fg_color": on_accent, "accent_color": t["accent"],
        "destructive_bg_color": t["crit"], "destructive_fg_color": on_accent, "destructive_color": t["crit"],
        "window_bg_color": frame, "window_fg_color": t["fg"],
        "view_bg_color": t["bg"], "view_fg_color": t["fg"],
        "headerbar_bg_color": frame, "headerbar_fg_color": t["fg"],
        "headerbar_border_color": _css_rgba(t["fg"], 0.2), "headerbar_backdrop_color": frame,
        "card_bg_color": t["surface"], "card_fg_color": t["fg"],
        "popover_bg_color": t["surfaceHigh"], "popover_fg_color": t["fg"],
        "dialog_bg_color": frame, "dialog_fg_color": t["fg"],
        "sidebar_bg_color": frame, "sidebar_fg_color": t["fg"], "sidebar_backdrop_color": frame,
        "sidebar_border_color": _css_rgba(t["fg"], 0.2),
        "secondary_sidebar_bg_color": frame, "secondary_sidebar_fg_color": t["fg"],
        "bbkos_selection_color": t["accentSoft"],
    }
    lines = ["/* Generated by bbkos-theme. Do not edit. */", f"/* mode: {settings['colors']['mode']} */",
             f"/* accent: {t['accent']} */", f"/* folders: {'on' if settings['colors']['folderIcons'] else 'off'} */"]
    lines += [f"@define-color {k} {v};" for k, v in c.items()]
    return "\n".join(lines) + "\n"


# GTK 3 only, after the parent theme. Every selection (files in Thunar's icon and list views, sidebar rows, list rows)
# is the accent's deep shade with the normal text colour, as in the shell's settings sidebar: a pair the theme engine
# lifts to 4.5:1 (a11y.FG_ON includes accentSoft). adw-gtk3 used the full accent behind white text in Thunar's icon
# view (unreadable with a light accent, the owner's report 2026-10-23), 25 % of the accent elsewhere, and a grey on
# sidebars. Thunar's sidebar is a tree view with the class `sidebar`, not a GtkPlacesSidebar.
GTK3_RULES = """placessidebar row:selected, .sidebar row:selected, placessidebar row:backdrop:selected,
.sidebar.view:selected, .sidebar .view:selected, .sidebar.view:selected:focus, .sidebar .view:selected:focus,
.sidebar.view:selected:backdrop, .sidebar .view:selected:backdrop,
.view:selected, .view:selected:focus, .view:selected:backdrop, iconview:selected, iconview:selected:focus,
treeview.view:selected, treeview.view:selected:focus, treeview.view:selected:backdrop,
.view text:selected, iconview text:selected, flowbox flowboxchild:selected, list row:selected, row:selected {
  background-color: @bbkos_selection_color;
  color: @view_fg_color;
}
"""


def render_gtk3_theme(parent_css, colours_css, stamp):
    """~/.local/share/themes/bbkos-{a,b}/gtk-3.0/gtk.css: the adw-gtk3 variant, then the generated colours, then
    GTK3_RULES. Later @define-color lines win, so the colours override the parent's. `stamp` (a hash of the colours)
    lets reload_gtk see that nothing changed and leave running apps alone."""
    return (f"/* Generated by bbkos-theme. Do not edit. colours: {stamp} */\n"
            f'@import url("file://{parent_css}");\n'
            f'@import url("file://{colours_css}");\n' + GTK3_RULES)


# Folder icons in the accent (colors.folderIcons): Adwaita's own folder SVGs with their blues turned to the accent's hue,
# the same idea as Adwaita-colors (github.com/dpejoh/Adwaita-colors), generated instead of shipped per colour.
FOLDER_ICONS = ("places/folder.svg", "places/folder-documents.svg", "places/folder-download.svg",
                "places/folder-drag-accept.svg", "places/folder-music.svg", "places/folder-pictures.svg",
                "places/folder-projects.svg", "places/folder-publicshare.svg", "places/folder-remote.svg",
                "places/folder-templates.svg", "places/folder-videos.svg", "places/user-home.svg",
                "places/user-desktop.svg", "places/user-bookmarks.svg", "mimetypes/inode-directory.svg",
                "status/folder-open.svg")
FOLDER_GREY_CHROMA = 0.015      # OKLCH chroma under which an accent counts as grey: the folders fade to grey with it


def recolour_folder_svg(svg, accent):
    """Every #rrggbb in `svg` turned to the accent's hue in OKLCH, keeping each colour's lightness and chroma (so the
    folder keeps its shading and vividness); an accent near grey (a monochrome scheme) takes the chroma down with it.
    Out-of-gamut results lose chroma, never hue (contrast.from_oklch)."""
    _, ac, ah = contrast.to_oklch(accent)
    scale = min(1.0, ac / FOLDER_GREY_CHROMA)

    def turn(m):
        L, C, _ = contrast.to_oklch(m.group(0))
        return contrast.from_oklch(L, C * scale, ah)
    return re.sub(r"#[0-9a-fA-F]{6}\b", turn, svg)


def render_icon_index(name):
    dirs = sorted({p.split("/")[0] for p in FOLDER_ICONS})
    ctx = {"places": "Places", "mimetypes": "MimeTypes", "status": "Status"}
    out = ["[Icon Theme]", f"Name={name}", "Comment=Adwaita folders in the wallpaper's accent (generated by bbkos-theme)",
           "Inherits=Adwaita,AdwaitaLegacy,hicolor", "Hidden=true",
           "Directories=" + ",".join(f"scalable/{d}" for d in dirs), ""]
    for d in dirs:
        out += [f"[scalable/{d}]", f"Context={ctx[d]}", "Size=128", "MinSize=8", "MaxSize=512", "Type=Scalable", ""]
    return "\n".join(out)


def render_hypridle(settings):
    """hypridle.conf from the idle settings. Every step asks bbkos-awake, which does nothing while awake mode is on (hypridle
    cannot skip one listener itself). A step set to 0 has no listener. bbkos-idle starts hypridle with this file."""
    i = settings["idle"]
    out = ["# Generated by bbkos-theme from the idle section of settings.json. Do not edit.\n",
           "# dim -> lock -> screen off -> suspend-then-hibernate. Events only (no polling); hypridle also honours video idle-inhibit.\n",
           "\ngeneral {\n",
           "    lock_cmd = bbkos-lock                                                # single hyprlock, flock-guarded\n",
           "    before_sleep_cmd = loginctl lock-session                             # lock before any sleep\n",
           "    after_sleep_cmd = hyprctl dispatch 'hl.dsp.dpms({action = \"on\"})'; loginctl lock-session\n",
           "}\n"]

    def listener(seconds, on, resume=None):
        if seconds <= 0:
            return
        out.append(f"\nlistener {{\n    timeout = {seconds}\n    on-timeout = {on}\n")
        if resume:
            out.append(f"    on-resume = {resume}\n")
        out.append("}\n")
    listener(i["dim"], "bbkos-awake idle-dim", "bbkos-awake idle-dim-resume")
    listener(i["dim"], "bbkos-awake idle-kbd", "bbkos-awake idle-kbd-resume")
    listener(i["lock"], "bbkos-awake idle-lock")
    listener(i["screenOff"], "bbkos-awake idle-screen-off", "bbkos-awake idle-screen-on")
    listener(i["suspend"], "bbkos-awake idle-suspend")
    return "".join(out)


def render_hyprsunset_conf(settings):
    """~/.config/hypr/hyprsunset.conf (hyprlang) from the night light settings. Each profile starts at its time and resets the
    others; hyprsunset applies the one for the current time at startup. Off writes a plain no-change profile (the service is
    stopped then, reload.reload_nightlight)."""
    n = settings["nightlight"]
    head = "# Generated by bbkos-theme from the nightlight section of settings.json. Do not edit.\n\n"
    neutral = "profile {\n    time = 00:00\n    identity = true\n}\n"
    if n["mode"] == "on":
        return head + f"profile {{\n    time = 00:00\n    temperature = {n['temperature']}\n}}\n"
    if n["mode"] == "schedule":
        return head + (f"profile {{\n    time = {n['end']}\n    identity = true\n}}\n\n"
                       f"profile {{\n    time = {n['start']}\n    temperature = {n['temperature']}\n}}\n")
    return head + neutral


def render_clipboard_conf(settings):
    """clipboard.conf in the theme state directory, read by bbkos-clip-store (a shell script run on every copy)."""
    return ("# Generated by bbkos-theme from the clipboard section of settings.json. Do not edit.\n"
            f"max-items = {settings['clipboard']['maxItems']}\n"
            f"images = {'true' if settings['clipboard']['images'] else 'false'}\n")


def render_omasnap_conf(settings):
    """~/.config/omasnap/omasnap.conf (INI) from the capture settings. omasnap has its own defaults for everything else."""
    c = settings["capture"]
    return ("# Generated by bbkos-theme from the capture section of settings.json. Do not edit.\n"
            "[output]\n"
            f"autosave = {lua_bool(c['autosave'])}\n"
            f"directory = {c['directory']}\n"
            "\n[editor]\n"
            f"mode = {c['editorMode']}\n")


LOCK_DATE_FORMATS = {"weekday-long": "%A, %d %B %Y", "weekday-short": "%a %d %b", "numeric": "%d/%m/%Y"}
LOCK_TIME_FORMATS = {"24h": "%H:%M", "12h": "%I:%M"}
LOCK_TEXT_MAX = 200


def lock_text(raw):
    """A label text for hyprlock from the user's template. Only $USER survives as a variable; other `$`, backslashes,
    backticks, control characters and `cmd[` (hyprlock runs `cmd[update:N] <shell>` labels) are removed, a single `#`
    (a hyprlang comment) is doubled, and the result is cut to LOCK_TEXT_MAX characters."""
    text = "".join(c for c in str(raw) if ord(c) >= 32 and c not in "\\`")
    while "cmd[" in text.lower():
        i = text.lower().index("cmd[")
        text = text[:i] + text[i + 4:]
    text = text.replace("$USER", "\x00").replace("$", "").replace("\x00", "$USER")
    return text[:LOCK_TEXT_MAX].replace("#", "##")


def _hex_rgb(h):
    h = h.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def render_hyprlock(settings, brightness=None):
    """hyprlock.conf from the lock settings: the blurred wallpaper, then each visible element (hyprlock positions are
    offsets from the screen centre, y up). The password field is always present. `brightness` is the value a11y.lock_brightness
    allowed for this wallpaper; None keeps the setting."""
    lk = settings["lock"]
    shown = lk["brightness"] if brightness is None else min(brightness, lk["brightness"])
    capped = f"# brightness capped to {num(shown)} (setting {num(lk['brightness'])}): the wallpaper is too bright for the text colour\n" if shown < lk["brightness"] else ""
    home = os.path.expanduser("~")
    font = lk["font"]
    colour = f"rgb({_hex_rgb(lk['textColor'])})"
    # The saved wallpaper (its real extension and location); no wallpaper set: a plain dark background.
    wp = settings["wallpaper"]["path"]
    wallpaper_line = f"    path = {wp}\n" if wp else "    color = rgb(20, 24, 26)\n"

    margin = num(lk["edgeMargin"])

    def place(e):
        """position and alignment. Left and right put the edge `edgeMargin` % in from the screen edge (hyprlock takes a
        percentage or pixels for a position, not both, so X is unused then); centre places the middle at X."""
        align = lk[e + "Align"]
        x = {"left": f"{margin}%", "right": f"-{margin}%"}.get(align, num(lk[e + "X"]))
        return (f"    position = {x}, {num(lk[e + 'Y'])}\n    halign = {align}\n    valign = center\n")

    def label(e, text, alpha=None):
        c = colour if alpha is None else f"rgba({_hex_rgb(lk['textColor'])}, {num(alpha)})"
        return (f"label {{\n    monitor =\n    text = {text}\n    font_size = {num(lk[e + 'Size'])}\n"
                f"    font_family = {font}\n    color = {c}\n{place(e)}}}\n")

    out = ["# bbkOS hyprlock, generated by bbkos-theme from the lock section of settings.json. Do not edit.\n" + capped,
           "general {\n    hide_cursor = true\n}\n",
           "animations {\n    enabled = false\n}\n",
           f"background {{\n    monitor =\n{wallpaper_line}"
           f"    blur_passes = {num(lk['blurPasses'])}\n    blur_size = {num(lk['blurSize'])}\n"
           f"    brightness = {num(shown)}\n}}\n"]
    if lk["avatarShow"]:
        # The chosen copy (bbkos-theme avatar set), or the shipped picture when none is set or the copy has gone.
        avatar = lk["avatar"] if lk["avatar"] and os.path.isfile(lk["avatar"]) else f"{home}/.config/hypr/lock-avatar.png"
        out.append(f"image {{\n    monitor =\n    path = {avatar}\n"
                   f"    size = {num(lk['avatarSize'])}\n    rounding = -1\n    border_size = 0\n{place('avatar')}}}\n")
    if lk["welcomeShow"]:
        out.append(label("welcome", lock_text(lk["welcomeText"])))
    if lk["dateShow"]:
        out.append(label("date", f'cmd[update:60000] date +"{LOCK_DATE_FORMATS[lk["dateFormat"]]}"', 0.8))
    if lk["timeShow"]:
        out.append(label("time", f'cmd[update:1000] date +"{LOCK_TIME_FORMATS[lk["timeFormat"]]}"'))
    out.append(
        f"input-field {{\n    monitor =\n    size = {num(lk['fieldWidth'])}, {num(lk['fieldHeight'])}\n"
        f"    outline_thickness = 0\n    inner_color = rgba(255, 255, 255, {num(lk['fieldOpacity'])})\n"
        f"    outer_color = rgba(255, 255, 255, 0.0)\n    check_color = rgba(255, 255, 255, {num(lk['fieldOpacity'])})\n"
        f"    fail_color = rgba(255, 85, 85, 0.30)\n    font_color = {colour}\n    fade_on_empty = false\n"
        f"    rounding = {num(lk['fieldRadius'])}\n    font_family = {font}\n    placeholder_text = <i>Password</i>\n"
        f"    fail_text = $PAMFAIL\n    dots_spacing = 0.3\n"
        f"{place('field')}}}\n")
    if lk["batteryShow"]:
        out.append(label("battery", "cmd[update:1000] bbkos-lock-battery", 0.85))
    return "\n".join(out)
