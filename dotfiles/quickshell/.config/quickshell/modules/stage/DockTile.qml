import QtQuick
import Quickshell
import Quickshell.Widgets
import qs
import qs.components
import qs.services

// One tile of the pinned-apps grid (Dock.qml): an app icon, a dot while the app has a window open, a small × on hover to
// unpin. With `add` it is the "+" tile that opens the menu to pick an app to pin. Grid mode: a cell with a hairline edge and the
// windows' corner radius. Otherwise the bar's pill style (shell.barPills): its own pill when individual; plain when grouped (the
// grid draws one pill around all tiles) or off. The hover plate and accent border are the same in both.
Item {
    id: tile

    required property var rail
    property string appId: ""              // desktop-file id; "" for the "+" tile
    property bool add: false
    property bool running: false
    readonly property var entry: Dock.entryFor(appId)
    readonly property bool hovered: area.containsMouse || remove.containsMouse
    readonly property string iconSource: {
        if (!entry || !entry.icon) return ""
        return entry.icon.startsWith("/") ? "file://" + entry.icon : Quickshell.iconPath(entry.icon, "application-x-executable")
    }

    signal activated()
    signal removed()

    readonly property bool ownPill: !Theme.gridMode && Theme.barPills === "individual"
    readonly property real radius: Math.min(Theme.gridMode ? tile.rail.cardRadius : Theme.pillRadius, Math.min(tile.width, tile.height) / 2)

    Rectangle {                             // the cell
        anchors.fill: parent
        radius: tile.radius
        color: tile.ownPill ? Theme.pillBg : "transparent"

        Rectangle {                         // hover plate
            anchors.fill: parent
            radius: parent.radius
            color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30)
            opacity: tile.hovered ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
        }
    }

    // The border is its own rectangle above the plate: as a border of the cell the plate (its child) was drawn over it, and at
    // the highlight's brightness the border looked gone while hovering. On hover it turns accent, like the window cards.
    Rectangle {
        anchors.fill: parent
        radius: tile.radius
        color: "transparent"
        border.width: tile.hovered || Theme.gridMode ? Theme.hair : 0     // outside grid mode only the hover accent: bar pills have no edge
        border.color: tile.hovered ? Theme.accent : Theme.cardEdge
    }

    IconImage {
        anchors.centerIn: parent
        visible: !tile.add && tile.iconSource !== ""
        implicitSize: Math.round(Math.min(tile.width, tile.height) * 0.5)
        source: tile.iconSource
    }

    Txt {                                   // "+" (and a "?" for a pinned app that is no longer installed)
        anchors.centerIn: parent
        visible: tile.add || tile.iconSource === ""
        text: tile.add ? "+" : "?"
        color: Theme.dim
        font.pixelSize: Theme.fontSize + 6
    }

    Rectangle {                             // the app has a window open
        visible: tile.running && !tile.add
        width: 4; height: 4; radius: 2
        color: Theme.accent
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 4 }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton
        onClicked: tile.activated()
    }

    MouseArea {                             // × : unpin
        id: remove
        visible: !tile.add && tile.hovered
        width: 18; height: 18
        anchors { top: parent.top; right: parent.right }
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tile.removed()
        Txt {
            anchors.centerIn: parent
            text: "×"
            color: remove.containsMouse ? Theme.accent : Theme.dim
            font.pixelSize: Theme.fontSize + 2
        }
    }
}
