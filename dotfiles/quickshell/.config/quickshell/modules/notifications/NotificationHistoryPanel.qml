import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// The notification history panel (the bar's bell widget opens it). Full-height sheet on the right, inside the
// Panels.qml backdrop. Read state is manual (B): clicking a card marks that one read, "Mark all read" clears the
// whole unread count. Entries stay until dismissed or cleared.
ColumnLayout {
    id: root
    anchors.fill: parent
    spacing: 8

    property bool clearArmed: false

    Timer { id: disarm; interval: 4000; onTriggered: root.clearArmed = false }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Txt { text: "Notifications"; font.bold: true; font.pixelSize: Theme.fontSize + 1; Layout.fillWidth: true }
        Txt { text: "DND"; color: Notifs.dnd ? Theme.accent : Theme.dim }
        Toggle { checked: Notifs.dnd; onToggled: value => Notifs.setDnd(value) }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        Button {
            text: "Mark all read"
            tint: Theme.accent
            enabled: Notifs.unread > 0
            onClicked: Notifs.markAllRead()
        }
        Item { Layout.fillWidth: true }
        Button {
            text: root.clearArmed ? "Clear all?" : "Clear all"
            tint: root.clearArmed ? Theme.crit : Theme.fg
            enabled: Notifs.history.length > 0
            onClicked: {
                if (!root.clearArmed) { root.clearArmed = true; disarm.restart(); return }
                root.clearArmed = false
                Notifs.clearAll()
            }
        }
    }

    Rectangle { Layout.fillWidth: true; implicitHeight: Theme.hair; color: Theme.inset }

    Item {
        id: listHost
        Layout.fillWidth: true
        Layout.fillHeight: true

        ListView {
            id: list
            anchors.fill: parent
            visible: count > 0
            clip: true
            spacing: 6
            boundsBehavior: Flickable.StopAtBounds
            model: Notifs.history
            delegate: NotificationHistoryCard { width: ListView.view.width }
        }

        Txt {
            anchors.centerIn: parent
            visible: list.count === 0
            text: "No notifications"
            color: Theme.dim
        }
    }
}
