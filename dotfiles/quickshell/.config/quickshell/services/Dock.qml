pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Hyprland
import qs

// Pinned apps (docs/modules/dock.md): the desktop-file ids in stage.dockApps, and which of them have a window open.
// The rail (modules/stage) draws them; this holds the state so the rail and the menu's pin mode share it.
Singleton {
    id: root

    // Grid mode switches the dock on (settings.GRID_OVERRIDES, which the stage settings cannot carry to the shell, so
    // this reads Theme.gridMode as Stage.qml does); otherwise stage.dock decides.
    readonly property bool on: Theme.gridMode || ((ThemeStore.settings.stage ?? {}).dock === true)
    readonly property var apps: {
        const v = SettingsStore.shown("stage.dockApps")
        return Array.isArray(v) ? v : []
    }

    // The rail's width and side, as Stage.qml reads them (settings.py defaults when the key is missing).
    readonly property int railWidth: (ThemeStore.settings.stage ?? {}).railWidth ?? 150
    readonly property bool railLeft: ((ThemeStore.settings.stage ?? {}).railPosition ?? "left") === "left"
    // Grid mode, dock on, rail at the left of a horizontal bar: the bar's first cell (workspaces) is as wide as the
    // rail, so the line between the workspaces and the title cell continues down the rail's inner edge.
    readonly property bool railHug: (ThemeStore.settings.stage ?? {}).railHug === true
    readonly property bool alignBar: on && Theme.gridMode && !Theme.barVertical && railLeft && !railHug   // a hugging rail has no corner to meet

    // The "+" tile was clicked: the menu opens in pin mode (Launcher.qml).
    signal pickRequested()

    function pin(id: string): void { if (id !== "" && apps.indexOf(id) < 0) SettingsStore.set("stage.dockApps", apps.concat([id])) }
    function unpin(id: string): void { SettingsStore.set("stage.dockApps", apps.filter(a => a !== id)) }
    function launch(id: string): void { Quickshell.execDetached(["uwsm", "app", "--", id + ".desktop"]) }

    // Quickshell loads the desktop entries lazily, so a lookup made before they are in finds nothing. Reading `.values`
    // makes every binding that calls these two functions run again when the list arrives (a "?" tile and no running dots
    // after every shell restart until it did).
    Component.onCompleted: void DesktopEntries.applications
    function entryFor(id: string): var {
        void DesktopEntries.applications.values
        return id !== "" ? DesktopEntries.byId(id) : null
    }
    // The desktop-file id a window class belongs to ("" when there is none).
    function idFor(appId: string): string {
        void DesktopEntries.applications.values
        const e = appId !== "" ? DesktopEntries.heuristicLookup(appId) : null
        return e ? e.id : ""
    }
    function isPinnedWindow(appId: string): bool { const id = idFor(appId); return id !== "" && apps.indexOf(id) >= 0 }

    // Pinned id -> the address of one of its open windows (the first Hyprland lists).
    readonly property var running: {
        const out = {}
        for (const t of Hyprland.toplevels.values) {
            const id = idFor(t.wayland ? String(t.wayland.appId ?? "") : "")
            if (id !== "" && !(id in out)) out[id] = t.address
        }
        return out
    }
}
