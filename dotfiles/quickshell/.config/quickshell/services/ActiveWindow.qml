pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

// The focused window, for the bar's window title (modules/bar/WindowTitle.qml; docs/modules/dock.md).
Singleton {
    id: root

    // Hyprland.activeToplevel stays null until the first focus change after the shell starts (and `activated` is false for
    // every window until then), so until then the window Hyprland lists as most recently focused stands in.
    // Focus on a workspace with no windows: Hyprland sends `activewindowv2` with an empty address, but Quickshell keeps
    // activeToplevel on the last window (still `activated`; probed 2026-10-31), so the title showed a window from another
    // workspace. That event clears it here until the next window takes the focus.
    property bool noWindow: false
    Connections {
        target: Hyprland
        function onRawEvent(event) { if (event.name === "activewindowv2") root.noWindow = event.data === "" }
    }
    readonly property var top: noWindow ? null : Hyprland.activeToplevel
        ?? Hyprland.toplevels.values.find(t => t.lastIpcObject && t.lastIpcObject.focusHistoryID === 0) ?? null
    Component.onCompleted: Hyprland.refreshToplevels()

    readonly property string appId: top && top.wayland ? String(top.wayland.appId ?? "")
        : (top && top.lastIpcObject ? String(top.lastIpcObject["class"] ?? "") : "")
    readonly property string title: top ? String(top.title ?? "") : ""

    IpcHandler {
        target: "activewindow"
        // Test hook: what the bar's title cell shows.
        function status(): string { return JSON.stringify({ title: root.title, "class": root.appId }) }
    }
}
