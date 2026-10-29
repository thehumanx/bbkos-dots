"""Settings schema, validation, persistence.

One table (RANGES) drives validation, clamping and `set_value`.
validate() never raises: it always returns a complete settings dict and a
list of short warnings.
"""
import copy
import json
import math
import os
import re
import shutil
import tempfile
from pathlib import Path

VERSION = 1

SCHEMES = ("content", "expressive", "fidelity", "fruit-salad", "monochrome",
           "neutral", "rainbow", "tonal-spot", "vibrant")

# Bar widgets and their default section. The bar layout is a list of "section:widget" entries; a widget appears once,
# and its place in the list sets its order within its section (see _coerce_layout).
BAR_SECTIONS = ("start", "center", "end")
BAR_WIDGETS = {"overview": "start", "workspaces": "start", "clock": "center", "media": "center", "timer": "center", "updates": "center", "record": "end", "privacy": "end", "tray": "end", "display": "end",
               "audio": "end", "bluetooth": "end", "network": "end", "battery": "end", "notifications": "end",
               "settings": "end"}
BAR_LAYOUT_DEFAULT = [f"{sec}:{w}" for w, sec in BAR_WIDGETS.items()]
BAR_LAYOUT_ALLOWED = tuple(f"{sec}:{w}" for sec in BAR_SECTIONS for w in BAR_WIDGETS)

# Icon sets each bar widget offers (bar.icon<Widget>). The glyphs are in components/BarIcons.js, keyed by these names.
# The first entry of each widget is its default; "fa" is the original icon set; "none" draws no icon (the settings gear must stay visible, so it has no "none").
BAR_ICON_STYLES = {"Wifi": ("bars", "material", "fa", "none"), "Bluetooth": ("material", "fa", "none"),
                   "Audio": ("fa", "material", "none"), "Battery": ("fa", "material", "none"),
                   "Display": ("monitor", "desktop", "tv", "none"), "Settings": ("fa", "material")}
BAR_ICON_DEFAULTS = {"Wifi": "bars", "Bluetooth": "material", "Audio": "fa", "Battery": "fa",
                     "Display": "monitor", "Settings": "fa"}

# Per power profile (saver = power-saver, balanced, performance): what the root helper bbkos-power-apply sets while that
# profile is active. "default" = do not override (power-profiles-daemon stays in charge); a cap of 0 = the firmware value.
POWER_EPP = ("default", "performance", "balance_performance", "balance_power", "power")
POWER_TURBO = ("default", "on", "off")
POWER_PROFILES = ("saver", "balanced", "performance")
# The battery's charge mode (power.chargeMode, one for all profiles): a value of BAT0/charge_types (ideapad_acpi), written by
# the same helper. Long_Life is Lenovo's conservation mode (the firmware stops at its own limit, about 80 %); "default" = leave it.
POWER_CHARGE = ("default", "Fast", "Standard", "Long_Life")

# Lock screen (hyprlock) layout, edited on the Lock screen page. Each element has Show, X, Y (px from the screen centre,
# y up, as hyprlock positions) and Size (avatar diameter or font size). The password field is always shown.
LOCK_ELEMENTS = ("avatar", "welcome", "date", "time", "battery")
LOCK_ELEMENT_DEFAULTS = {"avatar": (0, 260, 84), "welcome": (0, 190, 18), "date": (0, 125, 14),
                         "time": (0, 50, 96), "battery": (0, -150, 13)}
LOCK_SIZE_RANGE = {"avatar": (32, 300)}      # every other element's Size is a font size, 8-200
LOCK_DEFAULTS = {
    **{f"{e}{k}": v for e, (x, y, size) in LOCK_ELEMENT_DEFAULTS.items()
       for k, v in (("Show", True), ("X", x), ("Y", y), ("Size", size))},
    "fieldX": 0, "fieldY": -70, "fieldWidth": 300, "fieldHeight": 50, "fieldRadius": -1, "fieldOpacity": 0.14,
    "blurPasses": 3, "blurSize": 7, "brightness": 0.75, "autoDim": True,
    "font": "JetBrainsMono Nerd Font", "textColor": "#f0f0f0", "welcomeText": "Welcome $USER",
    "timeFormat": "24h", "dateFormat": "weekday-long",
    # The avatar picture: "" = the one shipped with the dotfiles (~/.config/hypr/lock-avatar.png), else the copy that
    # `bbkos-theme avatar set` made (avatar.py); never a path typed by hand.
    "avatar": "",
    # Left or right puts the element's edge edgeMargin % of the screen width in from that edge (its X is then unused);
    # center places it at X from the middle.
    **{f"{e}Align": "center" for e in (*LOCK_ELEMENTS, "field")}, "edgeMargin": 10,
}
LOCK_ALIGNS = ("left", "center", "right")
LOCK_TIME_FORMATS = ("24h", "12h")
LOCK_DATE_FORMATS = ("weekday-long", "weekday-short", "numeric")
_HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
# The only shape lock.avatar may take besides "": an absolute path ending in a copy made by avatar.py. It is written into
# hyprlock.conf, where "#" starts a comment and a newline a new key, so neither can appear.
_AVATAR_PATH = re.compile(r"^/[^#\x00-\x1f]*/avatar-[0-9a-f]{12}\.(png|jpg|jpeg|webp)$")

# Stage mode (modules/stage): every workspace uses Hyprland's monocle layout, so each window opens alone and full size,
# and a rail of thumbnail cards for the other windows of the workspace sits at one edge of the monitor.
STAGE_POSITIONS = ("left", "right")
STAGE_ORDERS = ("recent", "opened")
STAGE_DEFAULTS = {
    "enabled": False, "railPosition": "left", "railWidth": 150, "railPadding": 12, "railOpacity": 0.0,
    "cardHeight": 100, "cardGap": 12, "cardRadius": 10, "showTitle": True, "showIcon": True,
    "order": "recent", "refreshSeconds": 3, "showWithOneWindow": False, "reserveSpace": True, "animations": True,
}

# Screenshots (omasnap, docs/modules/capture.md): written into ~/.config/omasnap/omasnap.conf by `bbkos-theme apply`.
CAPTURE_EDITOR_MODES = ("overlay", "window")
CAPTURE_DEFAULTS = {"autosave": True, "directory": "~/Pictures/Screenshots", "editorMode": "overlay",
                    # Screen recording (bbkos-record, gpu-screen-recorder): what a recording starts with.
                    "recordArea": "region", "recordAudio": "desktop", "recordCamera": False, "recordCameraSize": "medium",
                    "recordCameraMirror": True,
                    "recordQuality": "very_high", "recordFps": 60, "recordDirectory": "~/Videos"}
RECORD_AREAS = ("region", "screen")
RECORD_AUDIOS = ("none", "desktop", "mic", "both")
RECORD_CAMERA_SIZES = ("small", "medium", "large")
RECORD_QUALITIES = ("medium", "high", "very_high", "ultra")

# Webcam (bbkos-camera, docs/modules/camera.md): the UVC picture controls, applied with v4l2-ctl to the colour camera.
# Defaults are the camera's own (auto exposure and white balance) except steadyFramerate, which stops it dropping the
# frame rate in dim light.
CAMERA_MODES = ("auto", "manual")
CAMERA_POWER_LINES = ("off", "50hz", "60hz")
CAMERA_DEFAULTS = {"exposure": "auto", "exposureTime": 156, "brightness": 128, "contrast": 32, "saturation": 64,
                   "sharpness": 3, "gamma": 120, "backlight": 1, "whiteBalance": "auto", "whiteBalanceTemp": 4600,
                   "steadyFramerate": True, "powerLine": "50hz"}

# Calendar popup (the bar clock's click target, docs/modules/calendar.md). nepali shows the Bikram Sambat date beside
# every day; the rest are display choices.
CALENDAR_WEEK_STARTS = ("mon", "sun", "sat")
CALENDAR_DEFAULTS = {"nepali": False, "weekStart": "mon", "weekNumbers": False, "moon": True}

# Idle timers (hypridle, the Idle and lock page): seconds of inactivity before each step, 0 = never. dim also switches the
# keyboard light off. Awake mode skips every step except the ones the owner does by hand (bbkos-awake).
IDLE_DEFAULTS = {"dim": 150, "lock": 300, "screenOff": 330, "suspend": 900}

# Notification popups (Quickshell's own daemon, docs/modules/notifications.md). timeout: seconds a popup stays when the sender
# gave none (or always, with senderTimeout off); criticalSticky keeps a critical one until it is closed; position "auto" is the
# bar's end corner; historySize is how many notifications the bell's list keeps.
NOTIF_POSITIONS = ("auto", "top-right", "top-left", "bottom-right", "bottom-left")
NOTIF_DEFAULTS = {"timeout": 6, "senderTimeout": True, "criticalSticky": True, "maxPopups": 5, "position": "auto",
                  "historySize": 100, "showPictures": True, "mutedApps": [],
                  "toastCharger": True, "toastAudio": True, "toastVpn": True}
# toast*: the short notices for a state change (charger, audio output, VPN; modules/toast), one switch each.
# mutedApps: app names (as the app sends them) whose notifications are dropped: no popup, no history entry. Names only: no
# commas (the CLI separates a list with commas), no control characters, at most NOTIF_APP_MAX characters and NOTIF_APPS_MAX names.
NOTIF_APP_MAX = 64
NOTIF_APPS_MAX = 200

# Keyboard, mouse and cursor (the Keyboard and mouse page; rendered into the input block of hypr-theme.lua). layout and variant
# are xkb names, comma separated for several layouts (the first is the active one; "us,np" with an options string that has a
# group switch would let you change). options is one of a few common presets, never free text (it goes into a Lua file).
KB_OPTIONS = ("none", "caps:escape", "ctrl:nocaps", "ctrl:swapcaps")
KEYBOARD_DEFAULTS = {"layout": "us", "variant": "", "options": "none", "repeatRate": 25, "repeatDelay": 600, "numlock": False}
MOUSE_ACCEL = ("default", "flat", "adaptive")
MOUSE_DEFAULTS = {"sensitivity": 0.0, "accelProfile": "default", "naturalScroll": False, "leftHanded": False}
CURSOR_DEFAULTS = {"theme": "Afterglow-cursors", "size": 24}
_XKB_LAYOUT = re.compile(r"^[a-z0-9_]+(,[a-z0-9_]+)*$")
_XKB_VARIANT = re.compile(r"^[A-Za-z0-9_]*(,[A-Za-z0-9_]*)*$")
_ICON_THEME_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Night light (hyprsunset, the Night light page): off, on all the time, or only between start and end (24 h "H:MM").
# temperature is in kelvin, lower is warmer; 6000 is hyprsunset's own neutral.
NIGHT_MODES = ("off", "on", "schedule")
NIGHT_DEFAULTS = {"mode": "off", "temperature": 4000, "start": "21:00", "end": "07:00"}
_CLOCK = re.compile(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$")

# Window and cursor behaviour (the Window behaviour page; Hyprland options, values from the Hyprland wiki's config reference).
# followMouse: click = input.follow_mouse 0, hover = 1 (focus follows the mouse), detached = 2 (the cursor's window and the
# keyboard's window differ until you click). focusOnActivate lets an app that asks to be focused take focus (the owner's OAuth
# hand-offs need it, so it stays on by default); workspaceBackAndForth turns a switch to the current workspace into a switch to
# the previous one; cursorHideAfter is seconds of stillness before the cursor hides (0 = never); cursorWarps lets focus changes
# move the cursor; snap lets floating windows snap to edges (snapGap pixels).
FOLLOW_MOUSE = {"click": 0, "hover": 1, "detached": 2}
BEHAVIOR_DEFAULTS = {"followMouse": "hover", "focusOnActivate": True, "workspaceBackAndForth": False,
                     "hideCursorWhenTyping": False, "cursorHideAfter": 0, "cursorWarps": True, "snap": False, "snapGap": 10}

# The bar clock (the Date and time page): 24 or 12 hour, seconds (the clock then wakes every second instead of every minute),
# the date before the time, and the small popup with the full date (and the Nepali one) while the pointer rests on it. The
# calendar popup has its own keys above.
CLOCK_DEFAULTS = {"hour24": True, "seconds": False, "date": True, "hoverDate": True}

# The music widget in the bar (modules/bar/MediaWidget.qml): the longest it grows, in px (the title is cut to fit, and to make
# room for the buttons while the pointer is on it).
MEDIA_DEFAULTS = {"maxWidth": 220}

# Clipboard history (the Clipboard page): how many copied texts cliphist keeps. bbkos-clip-store reads the number from the
# generated clipboard.conf each time something is copied.
# images: copied images (screenshots, "Copy image") are kept too, at most 10 MB each (2026-10-28).
CLIPBOARD_DEFAULTS = {"maxItems": 100, "images": True}

# The lid and the power button (the Lid and power page). The root helper power/bbkos-logind-apply turns these into logind's
# drop-in /etc/systemd/logind.conf.d/bbkos.conf; it validates the same words again (its lists must match these).
# lidBattery / lidPower: what closing the lid does on battery / on the charger; powerKeyLong: what holding the power button does.
# A docked lid (an external screen) and a short power press are not settings (bbkos-lid and the power menu handle them).
LID_ACTIONS = ("ignore", "lock", "suspend", "suspend-then-hibernate", "hibernate")
POWERKEY_ACTIONS = ("ignore", "suspend", "suspend-then-hibernate", "hibernate", "poweroff")
SESSION_DEFAULTS = {"lidBattery": "suspend-then-hibernate", "lidPower": "suspend-then-hibernate", "powerKeyLong": "poweroff"}

# The bbkOS menu (the Launcher page; modules/launcher/Launcher.qml reads these live). webSearch picks the engine of the last
# result ("Search the web for ...") or turns it off; the addresses are in Launcher.qml. calculator shows "= value" for a sum;
# maxResults caps the list; commands includes the bbkOS commands and settings pages; learn lets the menu remember what you open
# and which words found it (frecency), which orders the results.
WEB_SEARCH = ("duckduckgo", "google", "brave", "startpage", "ecosia", "off")
LAUNCHER_DEFAULTS = {"webSearch": "duckduckgo", "calculator": True, "maxResults": 40, "commands": True, "learn": True}

# The privacy indicator in the bar (the Privacy page, bar widget "privacy"): which of the three show it. It lights while an app has
# an open microphone input, a camera stream (through PipeWire) or a screen-sharing stream (services/Privacy.qml).
PRIVACY_DEFAULTS = {"mic": True, "camera": True, "screen": True}

# Screen time (the Screen time page): a reminder to look away after this many minutes at the screen without a break (0 = off). A
# break is the screen off or locked for five minutes, or the laptop asleep (components/ScreenBreak.js, services/ScreenTime.qml).
WELLBEING_DEFAULTS = {"breakEvery": 0}

DEFAULTS = {
    "version": VERSION,
    "wallpaper": {"path": "", "fit": "cover"},
    "colors": {"mode": "dark", "scheme": "tonal-spot", "sourceIndex": 0, "contrast": 0.0, "accentStrength": 1.0, "folderIcons": True,
               "auto": False, "lightFrom": "07:00", "darkFrom": "19:00"},
    "shell": {"barHeight": 30, "gap": 12, "radius": 12, "controlRadius": 6,
              "fontSize": 13, "font": "JetBrainsMono Nerd Font",
              "barPosition": "top", "barOpacity": 1.0, "barBlur": False, "barBlurAmount": 0.5, "tint": 0.8,
              "barPills": "off", "pillRadius": 8, "barItemGap": 12, "barItemPad": 0, "pillOpacity": 1.0,
              "barFloat": 0, "barHug": False, "barRadius": 0,
              "popupShadow": 0.5, "reduceMotion": False, "gridMode": False, "gridRoundControls": False},
    "windows": {"gapsIn": 5, "gapsOut": 20, "borderSize": 2, "activeBorder": True, "rounding": 10,
                "activeOpacity": 1.0, "inactiveOpacity": 1.0,
                "shadowEnabled": True, "shadowRange": 4,
                "blurEnabled": True, "blurSize": 3, "blurPasses": 1,
                "animations": True,
                "resizeOnBorder": False, "borderGrabArea": 15, "animationSpeed": 1.0},
    "touchpad": {"naturalScroll": False, "scrollFactor": 1.0, "scrollMethod": "auto",
                 "flipX": False, "flipY": False, "tapToClick": True, "tapAndDrag": True,
                 "dragLock": 0, "tapButtonMap": "auto", "clickfingerBehavior": False,
                 "middleButtonEmulation": False, "drag3fg": 0, "disableWhileTyping": True,
                 "wsSwipeDistance": 300, "wsSwipeInvert": True, "wsSwipeCancelRatio": 0.5,
                 "wsSwipeDirectionLock": True, "wsSwipeCreateNew": True, "wsSwipeForever": False,
                 "swipe3Up": "none", "swipe3Down": "none",
                 "swipe4Up": "none", "swipe4Down": "none", "swipe4Left": "none", "swipe4Right": "none"},
    "bar": {"layout": list(BAR_LAYOUT_DEFAULT), "iconsOnly": False, "iconGap": 2, **{f"icon{w}": v for w, v in BAR_ICON_DEFAULTS.items()}},
    "stage": dict(STAGE_DEFAULTS),
    "capture": dict(CAPTURE_DEFAULTS),
    "camera": dict(CAMERA_DEFAULTS),
    "terminal": {"fontSize": 11, "padding": 0, "opacity": 1.0},
    "lock": dict(LOCK_DEFAULTS),
    "calendar": dict(CALENDAR_DEFAULTS),
    "idle": dict(IDLE_DEFAULTS),
    "notifications": {**NOTIF_DEFAULTS, "mutedApps": []},     # a fresh list: dict() would share the default one
    "keyboard": dict(KEYBOARD_DEFAULTS),
    "mouse": dict(MOUSE_DEFAULTS),
    "cursor": dict(CURSOR_DEFAULTS),
    "nightlight": dict(NIGHT_DEFAULTS),
    "behavior": dict(BEHAVIOR_DEFAULTS),
    "clock": dict(CLOCK_DEFAULTS),
    "clipboard": dict(CLIPBOARD_DEFAULTS),
    "session": dict(SESSION_DEFAULTS),
    "launcher": dict(LAUNCHER_DEFAULTS),
    "privacy": dict(PRIVACY_DEFAULTS),
    "media": dict(MEDIA_DEFAULTS),
    "wellbeing": dict(WELLBEING_DEFAULTS),
    "power": {**{f"{p}Epp": "default" for p in POWER_PROFILES},
              **{f"{p}Turbo": "default" for p in POWER_PROFILES},
              **{f"{p}Cap": 0 for p in POWER_PROFILES},
              "chargeMode": "default"},
}

# Actions a multi-finger swipe can run (render.py maps each to a Hyprland gesture action; the overview ones run the
# workspace overview's IPC, since no stock Hyprland action maps to it).
SWIPE_ACTIONS = ("none", "workspace", "close", "fullscreen", "float", "special", "overview", "overview-close")

# kinds: ("int", lo, hi, step) ("float", lo, hi) ("bool",) ("enum", values) ("str",)
RANGES = {
    "wallpaper.path": ("str",),
    "wallpaper.fit": ("enum", ("cover",)),
    "colors.mode": ("enum", ("dark", "light")),
    "colors.scheme": ("enum", SCHEMES),
    "colors.sourceIndex": ("int", 0, 3, 1),   # matugen --help says 0-4 but accepts 0-3
    "colors.contrast": ("float", -1.0, 1.0),
    "colors.accentStrength": ("float", 0.0, 1.0),     # how vivid the wallpaper's colour is in accents and tints (render.mute: OKLCH chroma x this; 0 = grey)
    "colors.folderIcons": ("bool",),
    "colors.auto": ("bool",),                         # switch light and dark by the clock (modules/theme/ThemeSchedule.qml)
    "colors.lightFrom": ("str",),
    "colors.darkFrom": ("str",),                  # folder icons in GTK apps (Thunar) take the accent's hue
    "shell.barHeight": ("int", 24, 48, 2),
    "shell.gap": ("int", 0, 32, 2),
    "shell.radius": ("int", 0, 24, 2),
    "shell.controlRadius": ("int", 0, 16, 2),
    "shell.fontSize": ("int", 10, 20, 1),
    "shell.font": ("str",),
    "shell.barPosition": ("enum", ("top", "bottom", "left", "right")),
    "shell.barOpacity": ("float", 0.2, 1.0),
    "shell.barBlur": ("bool",),
    "shell.barBlurAmount": ("float", 0.05, 1.0),
    "shell.tint": ("float", 0.0, 1.0),                # how far widget colours lean toward the wallpaper tints
    "shell.barPills": ("enum", ("off", "grouped", "individual")),
    "shell.pillRadius": ("int", 0, 16, 2),
    "shell.barItemGap": ("int", 0, 32, 2),
    "shell.barItemPad": ("int", 0, 24, 2),            # extra space inside each widget, along the bar, on top of an individual pill's own 8 px (every bar mode)
    "shell.pillOpacity": ("float", 0.0, 1.0),
    "shell.barFloat": ("int", 0, 24, 2),              # space around the bar: it floats clear of the screen edges (0 = attached)
    "shell.barRadius": ("int", 0, 24, 2),             # corner radius of the bar itself (capped at half its thickness)
    "shell.gridMode": ("bool",),                      # flat grid look: no gaps, no rounding, hairline cell borders (effective())
    "shell.gridRoundControls": ("bool",),             # grid mode keeps the rounded corners of popups, buttons and controls (GRID_ROUND_OFF is not applied)
    "shell.barHug": ("bool",),                        # the bar shrinks to its widgets and sits in the middle of the edge
    "shell.popupShadow": ("float", 0.0, 1.0),         # strength of the tinted shadow under popups, pickers and the OSD (0 = none)
    "shell.reduceMotion": ("bool",),                  # fades only: no scale, slide or window movement (shell and Hyprland)
    "windows.gapsIn": ("int", 0, 20, 1),
    "windows.gapsOut": ("int", 0, 40, 1),
    "windows.borderSize": ("int", 0, 8, 1),
    "windows.activeBorder": ("bool",),                # false: the focused window's border looks like every other (no highlight)
    "windows.rounding": ("int", 0, 24, 1),
    "windows.activeOpacity": ("float", 0.6, 1.0),
    "windows.inactiveOpacity": ("float", 0.6, 1.0),
    "windows.shadowEnabled": ("bool",),
    "windows.shadowRange": ("int", 0, 20, 1),
    "windows.blurEnabled": ("bool",),
    "windows.blurSize": ("int", 1, 12, 1),
    "windows.blurPasses": ("int", 1, 4, 1),
    "windows.animations": ("bool",),
    "windows.resizeOnBorder": ("bool",),
    "windows.borderGrabArea": ("int", 0, 30, 1),
    "touchpad.naturalScroll": ("bool",),
    "touchpad.scrollFactor": ("float", 0.1, 2.0),
    "touchpad.scrollMethod": ("enum", ("auto", "2fg", "edge", "on_button_down", "no_scroll")),
    "touchpad.flipX": ("bool",),
    "touchpad.flipY": ("bool",),
    "touchpad.tapToClick": ("bool",),
    "touchpad.tapAndDrag": ("bool",),
    "touchpad.dragLock": ("int", 0, 2, 1),
    "touchpad.tapButtonMap": ("enum", ("auto", "lrm", "lmr")),
    "touchpad.clickfingerBehavior": ("bool",),
    "touchpad.middleButtonEmulation": ("bool",),
    "touchpad.drag3fg": ("int", 0, 2, 1),
    "touchpad.disableWhileTyping": ("bool",),
    "touchpad.wsSwipeDistance": ("int", 50, 2000, 10),
    "touchpad.wsSwipeInvert": ("bool",),
    "touchpad.wsSwipeCancelRatio": ("float", 0.0, 1.0),
    "touchpad.wsSwipeDirectionLock": ("bool",),
    "touchpad.wsSwipeCreateNew": ("bool",),
    "touchpad.wsSwipeForever": ("bool",),
    "touchpad.swipe3Up": ("enum", SWIPE_ACTIONS),
    "touchpad.swipe3Down": ("enum", SWIPE_ACTIONS),
    "touchpad.swipe4Up": ("enum", SWIPE_ACTIONS),
    "touchpad.swipe4Down": ("enum", SWIPE_ACTIONS),
    "touchpad.swipe4Left": ("enum", SWIPE_ACTIONS),
    "touchpad.swipe4Right": ("enum", SWIPE_ACTIONS),
    "bar.layout": ("layout", BAR_LAYOUT_ALLOWED),
    "bar.iconGap": ("int", 1, 6, 1),                  # spaces between a widget's icon and its text
    "bar.iconsOnly": ("bool",),                       # widgets draw their icon only; a dot instead of a count (notifications, updates)
    **{f"bar.icon{w}": ("enum", styles) for w, styles in BAR_ICON_STYLES.items()},
    "terminal.fontSize": ("int", 8, 20, 1),
    "terminal.padding": ("int", 0, 24, 1),
    "terminal.opacity": ("float", 0.6, 1.0),
    "capture.autosave": ("bool",),
    "capture.directory": ("str",),
    "capture.editorMode": ("enum", CAPTURE_EDITOR_MODES),
    "capture.recordArea": ("enum", RECORD_AREAS),
    "capture.recordAudio": ("enum", RECORD_AUDIOS),
    "capture.recordCamera": ("bool",),
    "capture.recordCameraSize": ("enum", RECORD_CAMERA_SIZES),
    "capture.recordCameraMirror": ("bool",),
    "capture.recordQuality": ("enum", RECORD_QUALITIES),
    "capture.recordFps": ("int", 30, 60, 30),
    "capture.recordDirectory": ("str",),
    "camera.exposure": ("enum", CAMERA_MODES),
    "camera.exposureTime": ("int", 3, 1250, 1),
    "camera.brightness": ("int", 0, 255, 1),
    "camera.contrast": ("int", 0, 100, 1),
    "camera.saturation": ("int", 0, 100, 1),
    "camera.sharpness": ("int", 0, 7, 1),
    "camera.gamma": ("int", 90, 150, 1),
    "camera.backlight": ("int", 0, 2, 1),
    "camera.whiteBalance": ("enum", CAMERA_MODES),
    "camera.whiteBalanceTemp": ("int", 2800, 6500, 100),
    "camera.steadyFramerate": ("bool",),
    "camera.powerLine": ("enum", CAMERA_POWER_LINES),
    "stage.enabled": ("bool",),
    "stage.railPosition": ("enum", STAGE_POSITIONS),
    "stage.railWidth": ("int", 100, 320, 10),
    "stage.railPadding": ("int", 0, 32, 2),
    "stage.railOpacity": ("float", 0.0, 1.0),
    "stage.cardHeight": ("int", 60, 240, 10),
    "stage.cardGap": ("int", 0, 32, 2),
    "stage.cardRadius": ("int", 0, 24, 2),
    "stage.showTitle": ("bool",),
    "stage.showIcon": ("bool",),
    "stage.order": ("enum", STAGE_ORDERS),
    "stage.refreshSeconds": ("int", 0, 30, 1),
    "stage.showWithOneWindow": ("bool",),
    "stage.reserveSpace": ("bool",),
    "stage.animations": ("bool",),
    **{f"lock.{e}Show": ("bool",) for e in LOCK_ELEMENTS},
    **{f"lock.{e}{a}": ("int", -1200, 1200, 1) for e in LOCK_ELEMENTS for a in ("X", "Y")},
    **{f"lock.{e}Size": ("int", *LOCK_SIZE_RANGE.get(e, (8, 200)), 1) for e in LOCK_ELEMENTS},
    "lock.fieldX": ("int", -600, 600, 1),
    "lock.fieldY": ("int", -500, 500, 1),
    "lock.fieldWidth": ("int", 120, 800, 1),
    "lock.fieldHeight": ("int", 30, 120, 1),
    "lock.fieldRadius": ("int", -1, 60, 1),
    "lock.fieldOpacity": ("float", 0.0, 1.0),
    "lock.blurPasses": ("int", 0, 5, 1),
    "lock.blurSize": ("int", 1, 15, 1),
    "lock.brightness": ("float", 0.2, 1.0),
    "lock.autoDim": ("bool",),
    "lock.font": ("str",),
    "lock.avatar": ("str",),
    "lock.textColor": ("str",),
    "lock.welcomeText": ("str",),
    **{f"lock.{e}Align": ("enum", LOCK_ALIGNS) for e in (*LOCK_ELEMENTS, "field")},
    "lock.edgeMargin": ("int", 0, 40, 1),
    "lock.timeFormat": ("enum", LOCK_TIME_FORMATS),
    "lock.dateFormat": ("enum", LOCK_DATE_FORMATS),
    "calendar.nepali": ("bool",),
    "calendar.weekStart": ("enum", CALENDAR_WEEK_STARTS),
    "calendar.weekNumbers": ("bool",),
    "calendar.moon": ("bool",),
    **{f"idle.{k}": ("int", 0, 3600, 30) for k in IDLE_DEFAULTS},
    "notifications.timeout": ("int", 2, 30, 1),
    "notifications.senderTimeout": ("bool",),
    "notifications.criticalSticky": ("bool",),
    "notifications.maxPopups": ("int", 1, 10, 1),
    "notifications.position": ("enum", NOTIF_POSITIONS),
    "notifications.historySize": ("int", 20, 500, 20),
    "notifications.showPictures": ("bool",),
    "notifications.mutedApps": ("applist",),
    "notifications.toastCharger": ("bool",),
    "notifications.toastAudio": ("bool",),
    "notifications.toastVpn": ("bool",),
    "keyboard.layout": ("str",),
    "keyboard.variant": ("str",),
    "keyboard.options": ("enum", KB_OPTIONS),
    "keyboard.repeatRate": ("int", 10, 60, 1),
    "keyboard.repeatDelay": ("int", 150, 1000, 50),
    "keyboard.numlock": ("bool",),
    "mouse.sensitivity": ("float", -1.0, 1.0),
    "mouse.accelProfile": ("enum", MOUSE_ACCEL),
    "mouse.naturalScroll": ("bool",),
    "mouse.leftHanded": ("bool",),
    "cursor.theme": ("str",),
    "cursor.size": ("int", 16, 48, 2),
    "clipboard.maxItems": ("int", 10, 500, 10),
    "clipboard.images": ("bool",),
    "wellbeing.breakEvery": ("int", 0, 120, 5),
    "media.maxWidth": ("int", 120, 400, 10),
    "privacy.mic": ("bool",),
    "privacy.camera": ("bool",),
    "privacy.screen": ("bool",),
    "launcher.webSearch": ("enum", WEB_SEARCH),
    "launcher.calculator": ("bool",),
    "launcher.maxResults": ("int", 10, 40, 5),
    "launcher.commands": ("bool",),
    "launcher.learn": ("bool",),
    "session.lidBattery": ("enum", LID_ACTIONS),
    "session.lidPower": ("enum", LID_ACTIONS),
    "session.powerKeyLong": ("enum", POWERKEY_ACTIONS),
    "clock.hour24": ("bool",),
    "clock.seconds": ("bool",),
    "clock.date": ("bool",),
    "clock.hoverDate": ("bool",),
    "behavior.followMouse": ("enum", tuple(FOLLOW_MOUSE)),
    "behavior.focusOnActivate": ("bool",),
    "behavior.workspaceBackAndForth": ("bool",),
    "behavior.hideCursorWhenTyping": ("bool",),
    "behavior.cursorHideAfter": ("int", 0, 20, 1),
    "behavior.cursorWarps": ("bool",),
    "behavior.snap": ("bool",),
    "behavior.snapGap": ("int", 0, 100, 5),
    "windows.animationSpeed": ("float", 0.5, 2.0),
    "nightlight.mode": ("enum", NIGHT_MODES),
    "nightlight.temperature": ("int", 2500, 6000, 100),
    "nightlight.start": ("str",),
    "nightlight.end": ("str",),
    **{f"power.{p}Epp": ("enum", POWER_EPP) for p in POWER_PROFILES},
    **{f"power.{p}Turbo": ("enum", POWER_TURBO) for p in POWER_PROFILES},
    **{f"power.{p}Cap": ("int", 0, 28, 1) for p in POWER_PROFILES},
    "power.chargeMode": ("enum", POWER_CHARGE),
}

MAX_STR = 512


def _default(dotted):
    s, k = dotted.split(".")
    return DEFAULTS[s][k]


def _capture_dir_ok(value):
    """A folder for screenshots: absolute, or under ~/ ; never empty or relative (it would depend on the cwd)."""
    return value.startswith("~/") and len(value) > 2 or (os.path.isabs(value) and value != "/")


def _coerce_layout(value):
    """A list of "section:widget" entries: unknown and repeated entries are dropped (the first one wins), and any
    widget left out goes to the end of its default section. Returns (layout, warning or None)."""
    if not isinstance(value, list) or not all(isinstance(e, str) for e in value):
        return list(BAR_LAYOUT_DEFAULT), "bar.layout: invalid value, using the default layout"
    out, seen, dropped = [], set(), False
    for e in value:
        widget = e.split(":", 1)[-1]
        if e not in BAR_LAYOUT_ALLOWED or widget in seen:
            dropped = True
            continue
        seen.add(widget)
        out.append(e)
    for widget, sec in BAR_WIDGETS.items():
        if widget not in seen:
            out.append(f"{sec}:{widget}")
    return out, ("bar.layout: unknown or repeated entries ignored" if dropped else None)


def _app_names(names):
    """Keep the usable app names (a string, trimmed, 1..NOTIF_APP_MAX characters, no comma or control character), first
    spelling wins, at most NOTIF_APPS_MAX. Returns the cleaned list and whether anything was dropped."""
    out, dropped = [], False
    for n in names:
        n = n.strip() if isinstance(n, str) else ""
        if not n or len(n) > NOTIF_APP_MAX or "," in n or any(ord(c) < 32 for c in n) or n in out or len(out) >= NOTIF_APPS_MAX:
            dropped = True
            continue
        out.append(n)
    return out, dropped


def _coerce(dotted, value):
    """Return (value, warning or None). Never raises."""
    spec = RANGES[dotted]
    kind = spec[0]
    default = _default(dotted)
    bad = (default, f"{dotted}: invalid value, using {default!r}")
    if kind == "layout":
        return _coerce_layout(value)
    if kind == "applist":
        if not isinstance(value, list):
            return bad
        out, dropped = _app_names(value)
        return out, (f"{dotted}: unusable names ignored" if dropped else None)
    if kind == "bool":
        return (value, None) if isinstance(value, bool) else bad
    if kind == "str":
        if (not isinstance(value, str) or len(value) > MAX_STR
                or any(ord(c) < 32 for c in value)
                or (dotted in ("shell.font", "lock.font") and not value.strip())
                or (dotted == "lock.textColor" and not _HEX_COLOUR.match(value))
                or (dotted == "lock.avatar" and value != "" and not _AVATAR_PATH.match(value))
                or (dotted == "keyboard.layout" and not _XKB_LAYOUT.match(value))
                or (dotted == "keyboard.variant" and not _XKB_VARIANT.match(value))
                or (dotted == "cursor.theme" and not _ICON_THEME_NAME.match(value))
                or (dotted in ("nightlight.start", "nightlight.end", "colors.lightFrom", "colors.darkFrom") and not _CLOCK.match(value))
                or (dotted in ("capture.directory", "capture.recordDirectory") and not _capture_dir_ok(value))):
            return bad
        if dotted == "lock.textColor":
            return value.lower(), None
        if dotted == "wallpaper.path" and value and not os.path.isabs(value):
            # never resolve a hand-edited relative path against the cwd
            return "", f"{dotted}: {value!r} is not absolute, ignored"
        return value, None
    if kind == "enum":
        return (value, None) if isinstance(value, str) and value in spec[1] else bad
    # numeric: bool is not a number here
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return bad
    if isinstance(value, float) and not math.isfinite(value):
        return bad
    if kind == "int":
        _, lo, hi, step = spec
        v = int(round(value)) if isinstance(value, float) else value
        v = min(max(v, lo), hi)
        v = lo + int(round((v - lo) / step)) * step
        v = min(v, hi)
        if dotted.endswith("Cap") and 0 < v < 10:
            v = 10                      # a package cap below 10 W would stall the CPU: 0 (off) or 10 and up
    else:
        _, lo, hi = spec
        # clamp ints before float(): huge ints would overflow it
        v = float(min(max(value, lo), hi)) if isinstance(value, int) else min(max(value, lo), hi)
    if v != value:
        return v, f"{dotted}: {value!r} adjusted to {v!r}"
    return v, None


# Grid mode (shell.gridMode, docs/modules/grid-mode.md): while on, the renderers see these values instead of the owner's,
# so every consumer of the generated files (the shell, Hyprland, hyprlock) follows from one place and the saved values stay
# as they are: switching the mode off puts the owner's look back.
GRID_OVERRIDES = {
    "shell": {"gap": 0, "barRadius": 0, "barFloat": 0, "barItemGap": 0,
              "barHug": False, "barPills": "individual", "popupShadow": 0.0},
    "windows": {"gapsIn": 0, "gapsOut": 0, "rounding": 0, "shadowEnabled": False, "borderSize": 1},
    "lock": {"fieldRadius": 0},
    "stage": {"cardGap": 0, "cardRadius": 0},
}
# The corners of popups, buttons and controls: squared by grid mode unless shell.gridRoundControls is on.
GRID_ROUND_OFF = {
    "shell": {"radius": 0, "controlRadius": 0, "pillRadius": 0},
}


def grid_overrides(settings):
    """The values grid mode puts in place for these settings: GRID_OVERRIDES, plus GRID_ROUND_OFF unless the owner keeps the controls round."""
    out = copy.deepcopy(GRID_OVERRIDES)
    if settings["shell"].get("gridRoundControls") is not True:
        for section, values in GRID_ROUND_OFF.items():
            out[section].update(values)
    return out


def effective(settings):
    """The settings the renderers use: `settings`, or a copy with the grid values applied while shell.gridMode is on."""
    if settings["shell"].get("gridMode") is not True:
        return settings
    out = copy.deepcopy(settings)
    for section, values in grid_overrides(settings).items():
        out[section].update(values)
    return out


def validate(raw):
    out = copy.deepcopy(DEFAULTS)
    warns = []
    if not isinstance(raw, dict):
        return out, ["settings is not an object, using defaults"]
    if raw.get("version") != VERSION:
        warns.append(f"version {raw.get('version')!r} unsupported, expected {VERSION}")
    for key in raw:
        if key != "version" and key not in DEFAULTS:
            warns.append(f"{key}: unknown section ignored")
    for section, keys in DEFAULTS.items():
        if section == "version":
            continue
        got = raw.get(section)
        if not isinstance(got, dict):
            if section in raw:
                warns.append(f"{section}: not an object, using defaults")
            continue
        for k in got:
            if k not in keys:
                warns.append(f"{section}.{k}: unknown key ignored")
        for k in keys:
            dotted = f"{section}.{k}"
            if k not in got:
                continue
            v, w = _coerce(dotted, got[k])
            out[section][k] = v
            if w:
                warns.append(w)
    return out, warns


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(path):
    path = Path(path)
    bak = path.with_name(path.name + ".bak")
    warns = []
    if not path.exists():  # also a dangling link
        if not bak.exists():
            return copy.deepcopy(DEFAULTS), ["settings file missing, using defaults"]
        warns.append(f"{path.name} missing, trying backup")
    else:
        try:
            out, w = validate(_read(path))
            return out, w
        except (OSError, ValueError, RecursionError) as e:
            warns.append(f"{path.name} unreadable ({type(e).__name__}), trying backup")
    try:
        out, w = validate(_read(bak))
        return out, warns + w
    except (OSError, ValueError, RecursionError) as e:
        warns.append(f"{bak.name} unusable ({type(e).__name__}), using defaults")
    return copy.deepcopy(DEFAULTS), warns


def _atomic_write(path, text):
    # Resolve symlinks (settings.json is a Stow link into the repo): replace
    # the target file so the link survives and the tracked file updates.
    path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def dumps(settings):
    return json.dumps(settings, indent=2) + "\n"


def save_atomic(path, settings):
    """Validate (clamping) then write atomically."""
    clean, _ = validate(settings)
    _atomic_write(path, dumps(clean))


def promote_backup(path):
    """Copy the current settings file to <path>.bak (atomically)."""
    path = Path(path)
    _atomic_write(path.with_name(path.name + ".bak"), path.read_text(encoding="utf-8"))


def set_value(settings, dotted, text):
    """Return a new settings dict with `dotted` set from CLI text. Raises ValueError."""
    spec = RANGES.get(dotted)
    if spec is None:
        raise ValueError(f"unknown key: {dotted}")
    kind = spec[0]
    if kind == "bool":
        t = text.strip().lower()
        if t in ("true", "on", "yes", "1"):
            value = True
        elif t in ("false", "off", "no", "0"):
            value = False
        else:
            raise ValueError(f"{dotted}: expected true or false, got {text!r}")
    elif kind == "int":
        try:
            value = int(text.strip())
        except ValueError:
            raise ValueError(f"{dotted}: expected an integer, got {text!r}") from None
    elif kind == "float":
        try:
            value = float(text.strip())
        except ValueError:
            raise ValueError(f"{dotted}: expected a number, got {text!r}") from None
        if not math.isfinite(value):
            raise ValueError(f"{dotted}: expected a finite number, got {text!r}")
    elif kind == "enum":
        value = text.strip()
        if value not in spec[1]:
            raise ValueError(f"{dotted}: expected one of {', '.join(spec[1])}, got {text!r}")
    elif kind == "applist":
        value = [e for e in text.split(",") if e.strip()]
        if _app_names(value)[1]:
            raise ValueError(f"{dotted}: names must be 1 to {NOTIF_APP_MAX} characters, no control characters, no repeats")
    elif kind == "layout":
        entries = [e.strip() for e in text.split(",") if e.strip()]
        for e in entries:
            if e not in BAR_LAYOUT_ALLOWED:
                raise ValueError(f"{dotted}: unknown entry {e!r} (section:widget, sections start/center/end)")
        names = [e.split(":", 1)[1] for e in entries]
        if len(set(names)) != len(names):
            raise ValueError(f"{dotted}: a widget may appear only once")
        value = entries
    else:
        value = text
        if _coerce(dotted, value)[1]:
            raise ValueError(f"{dotted}: invalid string")
    out = copy.deepcopy(settings)
    section, key = dotted.split(".")
    out[section][key], _ = _coerce(dotted, value)
    return out
