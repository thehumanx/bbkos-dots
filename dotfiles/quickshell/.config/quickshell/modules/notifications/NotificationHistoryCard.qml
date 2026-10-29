import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// One history entry in the notification panel. Clicking the card marks it read; the × removes it from history (and
// dismisses the live notification if it is still on screen).
Rectangle {
    id: card
    required property var modelData
    readonly property bool unread: !modelData.read
    readonly property bool critical: modelData.urgency === 2

    implicitHeight: content.implicitHeight + 20
    radius: Theme.controlRadius + 2
    color: area.containsMouse ? Qt.lighter(Theme.inset, 1.15) : Theme.inset
    border.width: critical ? Theme.hair : 0
    border.color: Theme.crit

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: Notifs.markRead(card.modelData.key)
    }

    ColumnLayout {
        id: content
        anchors { fill: parent; leftMargin: 12; rightMargin: 10; topMargin: 10; bottomMargin: 10 }
        spacing: 3

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Rectangle {                       // unread marker; transparent rather than hidden so the text does not jump
                implicitWidth: 8
                implicitHeight: 8
                radius: Theme.gridSquare ? 0 : 4
                color: card.unread ? Theme.accent : "transparent"
            }
            Image {                           // the app's icon, when it sent one that exists in the icon theme
                readonly property string url: Notifs.iconUrl(card.modelData.appIcon ?? "")
                visible: url !== ""
                source: url
                sourceSize: Qt.size(32, 32)
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
            Txt {
                text: card.modelData.appName !== "" ? card.modelData.appName : "Notification"
                textFormat: Text.PlainText
                color: Theme.dim
                font.pixelSize: Theme.fontSize - 2
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Txt {
                text: card.timeLabel(card.modelData.time)
                color: Theme.dim
                font.pixelSize: Theme.fontSize - 2
            }
            Rectangle {
                implicitWidth: 20
                implicitHeight: 20
                radius: Theme.controlRadius
                color: close.containsMouse ? Theme.surface : "transparent"

                Txt {
                    anchors.centerIn: parent
                    text: "×"
                    color: close.containsMouse ? Theme.crit : Theme.dim
                    font.pixelSize: Theme.fontSize + 1
                }
                MouseArea {
                    id: close
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Notifs.remove(card.modelData.key)
                }
            }
        }

        Txt {
            text: card.modelData.summary
            textFormat: Text.PlainText
            font.bold: true
            visible: text !== ""
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            maximumLineCount: 3
            elide: Text.ElideRight
        }
        Txt {
            text: card.modelData.body
            textFormat: Text.PlainText
            color: Theme.dim
            visible: text !== ""
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            maximumLineCount: 5
            elide: Text.ElideRight
        }
    }

    // No polling timer: the label is computed when the card is built (HH:mm today, Yesterday, or a date).
    function timeLabel(ms): string {
        const d = new Date(ms)
        const now = new Date()
        const hm = Qt.formatTime(d, "HH:mm")
        const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth()
            && a.getDate() === b.getDate()
        if (sameDay(d, now)) return hm
        const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
        if (sameDay(d, yesterday)) return "Yesterday " + hm
        return Qt.formatDate(d, "d MMM") + " " + hm
    }
}
