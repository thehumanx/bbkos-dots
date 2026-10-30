import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Widgets
import qs
import qs.components

// The focused window's icon and title (docs/modules/dock.md), a fixed-width cell so a changing title never moves its
// neighbours. Event-driven: Hyprland updates the active toplevel and its title; nothing polls. Empty workspace: an empty cell.
Row {
    id: root
    // Hyprland.activeToplevel stays null until the first focus change after the shell starts (and `activated` is false for
    // every window until then), so until then the window Hyprland lists as most recently focused stands in.
    readonly property var activeTop: Hyprland.activeToplevel
        ?? Hyprland.toplevels.values.find(t => t.lastIpcObject && t.lastIpcObject.focusHistoryID === 0) ?? null
    Component.onCompleted: Hyprland.refreshToplevels()
    readonly property var wl: activeTop ? activeTop.wayland : null
    readonly property string winClass: wl ? String(wl.appId ?? "") : (activeTop && activeTop.lastIpcObject ? String(activeTop.lastIpcObject["class"] ?? "") : "")
    readonly property string winTitle: activeTop ? String(activeTop.title ?? "") : ""
    readonly property var deskEntry: { void DesktopEntries.applications.values; return winClass !== "" ? DesktopEntries.heuristicLookup(winClass) : null }
    readonly property string winIcon: deskEntry && deskEntry.icon ? deskEntry.icon : winClass

    spacing: 8
    width: 260

    IconImage {
        id: icon
        visible: root.winClass !== ""
        anchors.verticalCenter: parent.verticalCenter
        implicitSize: Theme.fontSize + 2
        source: root.winIcon !== "" ? Quickshell.iconPath(root.winIcon, "application-x-executable") : ""
    }

    Txt {
        anchors.verticalCenter: parent.verticalCenter
        width: root.width - (icon.visible ? icon.width + root.spacing : 0)
        text: root.winTitle !== "" ? root.winTitle : root.winClass
        elide: Text.ElideRight
        color: dimColor
    }
}
