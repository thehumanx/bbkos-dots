import QtQuick
import Quickshell
import Quickshell.Widgets
import qs
import qs.components
import qs.services

// The focused window's icon and title (docs/modules/dock.md), a fixed-width cell so a changing title never moves its
// neighbours. Event-driven: Hyprland updates the active toplevel and its title; nothing polls. Empty workspace: an empty cell.
Row {
    id: root
    readonly property string winClass: ActiveWindow.appId
    readonly property string winTitle: ActiveWindow.title
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
