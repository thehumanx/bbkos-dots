import QtQuick
import QtQuick.Layouts
import qs
import qs.components

// Confirmation before Disable or Remove: the selected packages, Expert ones in amber with their description. The
// window passes `action` ("disable" / "remove") and `rows`; confirmed() runs it, cancelled() closes the sheet.
Rectangle {
    id: root
    property string action: ""
    property var rows: []
    signal confirmed()
    signal cancelled()

    readonly property string verb: action === "remove" ? "Remove" : "Disable"

    color: Qt.rgba(0, 0, 0, 0.55)
    MouseArea { anchors.fill: parent; onClicked: root.cancelled() }       // a click outside the card cancels

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 620)
        height: Math.min(parent.height - 80, card.implicitHeight + 40)
        radius: Theme.radius
        color: Theme.popupBg
        border.width: Theme.hair
        border.color: Theme.cardEdge
        MouseArea { anchors.fill: parent }                                 // swallow clicks inside the card

        ColumnLayout {
            id: card
            anchors { fill: parent; margins: 20 }
            spacing: 12

            Txt {
                text: root.verb + " " + root.rows.length + (root.rows.length === 1 ? " app?" : " apps?")
                font.bold: true
                font.pixelSize: Theme.fontSize + 4
            }
            Txt {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Theme.dim
                text: root.action === "remove"
                      ? "Removed for your user only; Restore brings them back. An app with no factory copy on the phone (one you installed, or a maker app kept in user storage) is refused: Disable it instead."
                      : "Disabled apps stay installed but cannot run. Restore turns them back on."
            }
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: contentHeight
                Layout.maximumHeight: 360
                clip: true
                spacing: 6
                model: root.rows
                delegate: ColumnLayout {
                    required property var modelData
                    width: ListView.view.width
                    spacing: 1
                    readonly property bool expert: modelData.rating === "Expert"
                    readonly property bool gone: root.action === "remove" && !modelData.system   // not restorable
                    Txt {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: (parent.expert ? "  " : "") + (modelData.name ? modelData.name + "  " : "") + modelData.package
                        color: parent.expert ? Theme.warn : Theme.fg
                    }
                    Txt {
                        visible: parent.gone
                        text: "Installed by you: Remove will be refused, use Disable"
                        color: Theme.warn
                        font.pixelSize: Theme.fontSize - 2
                    }
                    Txt {
                        visible: parent.expert && modelData.description !== ""
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        maximumLineCount: 3
                        elide: Text.ElideRight
                        text: modelData.description
                        color: Theme.dim
                        font.pixelSize: Theme.fontSize - 2
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "Cancel"; onClicked: root.cancelled() }
                Button {
                    text: root.verb + " " + root.rows.length + (root.rows.length === 1 ? " app" : " apps")
                    tint: Theme.crit
                    onClicked: root.confirmed()
                }
            }
        }
    }
}
