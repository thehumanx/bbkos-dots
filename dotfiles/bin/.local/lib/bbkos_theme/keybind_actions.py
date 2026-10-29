"""Static catalogue of keybind actions (presets) shared by the CLI and the UI."""
import shutil

DISPATCH_ARGS = {
    "exec_cmd": ("command",),
    "focus": ("direction", "workspace"),
    "window.close": (),
    "window.fullscreen": ("mode",),
    "window.tiled_fullscreen": (),
    "window.toggle_opaque": (),
    "window.toggle_gaps": (),
    "window.cycle": ("direction",),
    "window.float": ("action",),
    "window.pseudo": (),
    "window.move": ("workspace",),
    "window.drag": (),
    "window.resize": (),
    "layout": ("layout",),
    "workspace.toggle_special": ("name",),
}


def _exec(id_, label, group, command, needs=None, locked_ok=False):
    e = {"id": id_, "label": label, "group": group,
         "action": {"type": "exec", "command": command}}
    if needs:
        e["needs"] = needs
    if locked_ok:
        e["locked_ok"] = True
    return e


def _dispatch(id_, label, group, dispatcher, **args):
    return {"id": id_, "label": label, "group": group,
            "action": {"type": "dispatch", "name": dispatcher, "args": args}}


CATALOGUE = [
    _exec("launcher", "bbkOS menu (apps, commands, settings)", "Shell", "qs ipc call launcher toggle", "qs"),
    _exec("clipboard", "Clipboard history", "Shell", "qs ipc call clipboard toggle", "qs"),
    _exec("settings-window", "Settings", "Shell", "qs ipc call settings toggle", "qs"),
    _exec("power-panel", "Power menu", "Shell", "qs ipc call panel toggle power", "qs"),
    _exec("lock", "Lock session", "Shell", "loginctl lock-session"),
    _exec("logout", "Log out", "Shell", "uwsm stop"),

    _exec("volume-up", "Volume up", "Audio",
          "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+", "wpctl", True),
    _exec("volume-up-precise", "Volume up (1%)", "Audio",
          "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 1%+", "wpctl", True),
    _exec("volume-down-precise", "Volume down (1%)", "Audio",
          "wpctl set-volume @DEFAULT_AUDIO_SINK@ 1%-", "wpctl", True),
    _exec("volume-down", "Volume down", "Audio",
          "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", "wpctl", True),
    _exec("volume-mute", "Mute", "Audio",
          "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", "wpctl", True),
    _exec("mic-mute", "Mute microphone", "Audio",
          "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", "wpctl", True),
    _exec("media-play-pause", "Play / pause", "Audio", "playerctl play-pause", "playerctl", True),
    _exec("media-next", "Next track", "Audio", "playerctl next", "playerctl", True),
    _exec("media-prev", "Previous track", "Audio", "playerctl previous", "playerctl", True),

    _exec("brightness-up", "Brightness up", "Display", "bbkos-brightness up",
          "bbkos-brightness", True),
    _exec("brightness-down", "Brightness down", "Display", "bbkos-brightness down",
          "bbkos-brightness", True),
    _exec("brightness-up-precise", "Brightness up (1%)", "Display", "bbkos-brightness up1",
          "bbkos-brightness", True),
    _exec("brightness-down-precise", "Brightness down (1%)", "Display", "bbkos-brightness down1",
          "bbkos-brightness", True),

    # omasnap (docs/modules/capture.md): the same key opens and closes its overlay. Smart selection: drag a region, click a
    # window, click empty space for the monitor; the editor and OCR open from the preview.
    _exec("screenshot-region", "Screenshot (select region or window)", "Screenshots", "omasnap", "omasnap"),
    # bbkos-record (capture.md): stops a running recording, otherwise opens the options panel (the old Omarchy key's behaviour).
    _exec("record-menu", "Screen recording (stop, or open the options)", "Screenshots",
          "bbkos-record stop || qs ipc call panel toggle record", "bbkos-record"),
    _exec("emoji-picker", "Emoji picker", "Shell", "qs ipc call emoji toggle", "qs"),
    # Voxtype (docs/modules/dictation.md): one key starts and stops dictation; a notification when the service is not running.
    _exec("dictation-toggle", "Dictation (start or stop)", "Shell",
          'voxtype record toggle || notify-send -a bbkos "Dictation" "Voxtype is not running: systemctl --user status voxtype"', "voxtype"),
    _exec("toggle-bar", "Hide or show the bar", "Shell", "qs ipc call bar toggle", "qs"),
    # Stage mode for the focused workspace until the next boot (docs/modules/stage.md); no default key.
    _exec("stage-workspace", "Stage mode for this workspace", "Shell", "qs ipc call stagews toggle ''", "qs"),
    _exec("ocr-text", "Copy text from a screen region (OCR)", "Screenshots", "bbkos-ocr", "bbkos-ocr"),

    # The default terminal (Settings, Default apps: ~/.config/xdg-terminals.list, read by `uwsm app -T`).
    _exec("launch-terminal", "Terminal", "Apps", "uwsm app -T"),
    _exec("launch-files", "File manager", "Apps", "uwsm app -- thunar"),
    _exec("claude-bbkos", "Claude Code in bbkOS", "Apps",
          'uwsm app -- kitty --directory "$HOME/.local/share/bbkos/repo" claude', "claude"),

    _dispatch("close-window", "Close window", "Windows", "window.close"),
    _dispatch("toggle-fullscreen", "Toggle fullscreen", "Windows", "window.fullscreen", mode="fullscreen"),
    _dispatch("toggle-maximize", "Toggle maximized (full width)", "Windows", "window.fullscreen", mode="maximized"),
    _dispatch("toggle-tiled-fullscreen", "Toggle tiled fullscreen", "Windows", "window.tiled_fullscreen"),
    _dispatch("toggle-opaque", "Toggle transparency of the window", "Windows", "window.toggle_opaque"),
    _dispatch("toggle-gaps", "Toggle window gaps (none / your settings)", "Windows", "window.toggle_gaps"),
    _dispatch("toggle-float", "Toggle floating", "Windows", "window.float", action="toggle"),
    _dispatch("pseudo", "Pseudo-tile", "Windows", "window.pseudo"),
    _dispatch("toggle-split", "Toggle split", "Windows", "layout", layout="togglesplit"),
    _dispatch("cycle-window-next", "Previous window (hold the modifier to go deeper)", "Windows", "window.cycle", direction="next"),
    _dispatch("cycle-window-prev", "Back through recent windows (hold the modifier)", "Windows", "window.cycle", direction="prev"),
    _dispatch("focus-left", "Focus left", "Windows", "focus", direction="left"),
    _dispatch("focus-right", "Focus right", "Windows", "focus", direction="right"),
    _dispatch("focus-up", "Focus up", "Windows", "focus", direction="up"),
    _dispatch("focus-down", "Focus down", "Windows", "focus", direction="down"),
]

for _n in range(1, 11):
    CATALOGUE.append(_dispatch("workspace-%d" % _n, "Workspace %d" % _n, "Workspaces",
                               "focus", workspace=_n))
    CATALOGUE.append(_dispatch("move-to-workspace-%d" % _n, "Move window to workspace %d" % _n,
                               "Workspaces", "window.move", workspace=_n))

CATALOGUE += [
    _dispatch("special-workspace", "Toggle scratchpad", "Workspaces",
              "workspace.toggle_special", name="magic"),
    _dispatch("move-to-special", "Move window to scratchpad", "Workspaces",
              "window.move", workspace="special:magic"),
    _dispatch("scroll-workspace-next", "Next workspace", "Workspaces",
              "focus", workspace="e+1"),
    _dispatch("scroll-workspace-prev", "Previous workspace", "Workspaces",
              "focus", workspace="e-1"),
    _dispatch("drag-window", "Drag window", "Mouse", "window.drag"),
    _dispatch("resize-window", "Resize window", "Mouse", "window.resize"),
]

ACTIONS = {e["id"]: e for e in CATALOGUE}


def expand(action):
    """A preset becomes its catalogue action; exec and dispatch pass through."""
    if action.get("type") == "preset":
        return ACTIONS[action["id"]]["action"]
    return action


def missing_tools(entry, which=shutil.which):
    need = entry.get("needs")
    return [need] if need and not which(need) else []
