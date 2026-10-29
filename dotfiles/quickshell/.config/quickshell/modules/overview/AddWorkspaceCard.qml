import QtQuick
import qs
import qs.components

// The "+" card at the end of the workspace strip (modules/overview). Clicking it adds the next free workspace and
// selects it without switching, so a window can then be dragged onto the new slot. While a window is dragged it is
// also a drop target: dropping there creates the workspace and moves the window into it.
Item {
    id: card

    required property var host                 // the Overview window: workspace list, drag state and actions
    required property bool dropTarget
    property real reveal: 1                    // entrance progress (staggered by the host), 0 = hidden

    opacity: reveal
    scale: 0.9 + 0.1 * reveal
    transformOrigin: Item.Top
    transform: Translate { y: -(1 - card.reveal) * 30 }

    readonly property int workspaceId: -1      // sentinel used by the host's drop hit-testing

    Component.onCompleted: host.registerWorkspaceCard(card)
    Component.onDestruction: host.unregisterWorkspaceCard(card)

    Rectangle {
        anchors.fill: parent
        radius: Theme.controlRadius + 2
        color: card.dropTarget ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                               : Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, 0.52)
        border.width: card.dropTarget ? 2 : 1
        border.color: card.dropTarget || area.containsMouse
            ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.16)

        Rectangle {
            id: plus
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -8
            width: 32
            height: 32
            radius: Theme.gridSquare ? 0 : 16
            color: card.dropTarget ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.10)

            Txt {
                anchors.centerIn: parent
                text: "+"
                color: card.dropTarget ? Theme.bg : Theme.fg
                font.pixelSize: 22
                font.bold: true
            }
        }

        Txt {
            anchors { bottom: parent.bottom; bottomMargin: 10; horizontalCenter: parent.horizontalCenter }
            text: card.dropTarget ? "Move here" : "New workspace"
            color: card.dropTarget ? Theme.accent : Theme.dim
            font.pixelSize: Theme.fontSize - 4
        }
    }

    MouseArea {
        id: area
        anchors.fill: parent
        enabled: card.host.interactive
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton
        onClicked: if (card.host && card.host.dragAddress === "") card.host.addWorkspace()
    }
}
