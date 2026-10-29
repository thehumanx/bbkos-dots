pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

// Stage mode per workspace (docs/modules/stage.md). stage.enabled in settings.json is the default every workspace
// starts with (render.py writes it as Hyprland's general.layout); a workspace switched from the overview, a key or IPC
// keeps its own choice until the next boot. The choices live in $XDG_RUNTIME_DIR/bbkos-stage.json (a tmpfs, emptied at
// shutdown), so they survive a shell or Hyprland restart within the session and are gone after a reboot.
// Hyprland side: one runtime workspace rule per switched workspace (`layout = "monocle"` or `"dwindle"`), kept as a
// handle in the Lua global BBKOS_STAGE so a later switch disables the old rule instead of piling up new ones. A config
// reload drops runtime rules (tested), so they are added again on `configreloaded`.
Singleton {
    id: root

    readonly property bool defaultOn: (ThemeStore.settings.stage ?? {}).enabled === true
    property var overrides: ({})                // workspace name -> true/false, only where it differs from the default
    readonly property bool anyOn: defaultOn || Object.keys(overrides).some(k => overrides[k] === true)
    readonly property string path: (Quickshell.env("XDG_RUNTIME_DIR") ?? "") + "/bbkos-stage.json"

    function isStage(name: string): bool {
        return Object.prototype.hasOwnProperty.call(overrides, name) ? overrides[name] === true : defaultOn
    }

    function set(name: string, on: bool) {
        if (name === "" || name.startsWith("special:")) return
        const next = Object.assign({}, overrides)
        if (on === defaultOn) delete next[name]
        else next[name] = on
        overrides = next
        store.setText(JSON.stringify(next))
        apply(name)
    }
    function toggle(name: string) { set(name, !isStage(name)) }

    // One workspace: drop its old rule, add the new one if it differs from the default.
    function rule(name: string): string {
        const key = JSON.stringify(name)
        let lua = "BBKOS_STAGE = BBKOS_STAGE or {}; local r = BBKOS_STAGE[" + key + "]; if r then r:set_enabled(false) end; "
                  + "BBKOS_STAGE[" + key + "] = nil; "
        if (Object.prototype.hasOwnProperty.call(overrides, name))
            lua += "BBKOS_STAGE[" + key + "] = hl.workspace_rule({ workspace = " + key + ", layout = \""
                   + (overrides[name] ? "monocle" : "dwindle") + "\" }); "
        return lua
    }
    function apply(name: string) { Quickshell.execDetached(["hyprctl", "eval", rule(name)]) }
    // Every switched workspace, from scratch (after a config reload the old handles point at rules that are gone).
    function applyAll() {
        let lua = "BBKOS_STAGE = {}; "
        for (const name in overrides) lua += rule(name)
        Quickshell.execDetached(["hyprctl", "eval", lua])
    }

    // A new default in the settings makes every workspace follow it: the per-workspace choices are cleared.
    property bool _started: false
    onDefaultOnChanged: {
        if (!_started) return
        const names = Object.keys(overrides)
        overrides = ({})
        store.setText("{}")
        for (const n of names) apply(n)
    }

    Connections {
        target: Hyprland
        function onRawEvent(event) { if (event.name === "configreloaded") root.applyAll() }
    }

    FileView {
        id: store
        path: root.path
        atomicWrites: true
        printErrors: false
        blockLoading: true
    }
    Component.onCompleted: {
        try {
            const v = JSON.parse(store.text() || "{}")
            const clean = {}
            if (v && typeof v === "object" && !Array.isArray(v))
                for (const k in v) if (typeof v[k] === "boolean" && v[k] !== defaultOn && Object.keys(clean).length < 100) clean[k] = v[k]
            overrides = clean
        } catch (e) {
            overrides = ({})
        }
        applyAll()
        _started = true
    }

    IpcHandler {
        target: "stagews"
        // Test hooks and the keybinding action: qs ipc call stagews toggle "" (the focused workspace) or a name.
        function toggle(name: string): void { root.toggle(name !== "" ? name : (Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.name : "")) }
        function set(name: string, on: bool): void { root.set(name, on) }
        function status(): string {
            return JSON.stringify({ defaultOn: root.defaultOn, overrides: root.overrides, anyOn: root.anyOn, file: root.path })
        }
    }
}
