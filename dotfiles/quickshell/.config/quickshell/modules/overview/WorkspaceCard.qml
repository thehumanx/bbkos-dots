import QtQuick
import qs
import qs.components
import "OverviewModel.js" as Model

// One workspace in the overview's top strip: its number, a miniature of its window layout, and a count. Clicking it
// shows that workspace's windows below; clicking the already selected one (or double-clicking) switches to it.
// While a window is dragged, the card under the pointer gets the accent border and "Move here".
Item {
    id: card

    required property int workspaceId
    required property var workspace            // HyprlandWorkspace or null for an empty slot
    required property bool selected
    required property bool current             // the focused workspace
    required property bool dropTarget
    required property var frame                // OverviewModel.monitorFrame()
    required property var host                 // the Overview window: card list and actions
    property real reveal: 1                    // entrance progress (staggered by the host), 0 = hidden

    readonly property var windows: Model.windowsOf(workspace, frame)
    readonly property color line: selected || dropTarget ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.16)

    opacity: reveal
    scale: 0.9 + 0.1 * reveal
    transformOrigin: Item.Top
    transform: Translate { y: -(1 - card.reveal) * 30 }

    Component.onCompleted: host.registerWorkspaceCard(card)
    Component.onDestruction: host.unregisterWorkspaceCard(card)

    Rectangle {
        id: box
        anchors.fill: parent
        radius: Theme.controlRadius + 2
        color: card.dropTarget ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                               : Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.72)
        border.width: card.selected || card.dropTarget ? 2 : 1
        border.color: card.line
        clip: true

        // Number badge; the focused workspace's badge is filled.
        Rectangle {
            id: badge
            x: 8
            y: 6
            width: Math.max(18, num.implicitWidth + 10)
            height: 18
            radius: Theme.controlRadius
            color: card.current ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.10)

            Txt {
                id: num
                anchors.centerIn: parent
                text: String(card.workspaceId)
                color: card.current ? Theme.bg : Theme.fg
                font.pixelSize: Theme.fontSize - 3
                font.bold: true
            }
        }

        Txt {
            anchors { right: parent.right; rightMargin: 8; verticalCenter: badge.verticalCenter }
            visible: card.windows.length > 0
            text: String(card.windows.length)
            color: card.selected ? Theme.accent : Theme.dim
            font.pixelSize: Theme.fontSize - 3
        }

        // Miniature of the workspace: every window as a small rectangle in its real relative position. No previews
        // here on purpose, so only the selected workspace ever starts a screen capture.
        Item {
            id: mini
            anchors { left: parent.left; right: parent.right; top: badge.bottom; bottom: parent.bottom }
            anchors.margins: 8
            anchors.topMargin: 4

            Repeater {
                model: card.windows

                Rectangle {
                    required property var modelData
                    x: Math.round(modelData.rect.x * mini.width)
                    y: Math.round(modelData.rect.y * mini.height)
                    width: Math.max(3, Math.round(modelData.rect.width * mini.width))
                    height: Math.max(3, Math.round(modelData.rect.height * mini.height))
                    radius: 1
                    color: card.selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.42)
                                         : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.22)
                    border.width: 1
                    border.color: card.selected ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.10)
                }
            }

            Txt {
                anchors.centerIn: parent
                visible: card.windows.length === 0 && !card.dropTarget
                text: "empty"
                color: Theme.dim
                opacity: 0.5
                font.pixelSize: Theme.fontSize - 4
            }

            Txt {
                anchors.centerIn: parent
                visible: card.dropTarget
                text: "Move here"
                color: Theme.accent
                font.pixelSize: Theme.fontSize - 3
                font.bold: true
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: card.host.interactive
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton
        onClicked: if (card.host) card.host.workspaceClicked(card.workspaceId)
        onDoubleClicked: if (card.host) card.host.switchToWorkspace(card.workspaceId)
    }
}
