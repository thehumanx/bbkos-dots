import QtQuick
import QtQuick.Layouts
import qs
import qs.components

// Wi-Fi debugging: pair once with the address and code from the phone's Developer options -> Wireless debugging ->
// Pair device with pairing code, then connect with the address shown on the Wireless debugging screen. The window
// runs `bbkos-android pair` / `connect` on run(args) and sets `message` / `busy`.
Rectangle {
    id: root
    property string message: ""
    property bool busy: false
    signal run(var args)
    signal closed()

    color: Qt.rgba(0, 0, 0, 0.55)
    MouseArea { anchors.fill: parent; onClicked: root.closed() }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 520)
        height: form.implicitHeight + 40
        radius: Theme.radius
        color: Theme.popupBg
        border.width: Theme.hair
        border.color: Theme.cardEdge
        MouseArea { anchors.fill: parent }

        ColumnLayout {
            id: form
            anchors { fill: parent; margins: 20 }
            spacing: 10

            Txt { text: "Connect over Wi-Fi"; font.bold: true; font.pixelSize: Theme.fontSize + 4 }
            Txt {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Theme.dim
                text: "On the phone: Developer options → Wireless debugging. The phone and this laptop must be on the same network."
            }

            Txt { text: "1. Pair (once): tap “Pair device with pairing code”"; font.bold: true; Layout.topMargin: 6 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Field { id: pairAddr; Layout.fillWidth: true; placeholder: "192.168.1.5:37000" }
                Field { id: code; implicitWidth: 110; placeholder: "6-digit code"; onAccepted: pairBtn.clicked() }
                Button {
                    id: pairBtn
                    text: "Pair"
                    enabled: !root.busy && pairAddr.text !== "" && code.text !== ""
                    onClicked: root.run(["pair", pairAddr.text.trim(), code.text.trim()])
                }
            }

            Txt { text: "2. Connect: the address under “IP address & Port”"; font.bold: true; Layout.topMargin: 6 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Field { id: addr; Layout.fillWidth: true; placeholder: "192.168.1.5:41234"; onAccepted: connectBtn.clicked() }
                Button {
                    id: connectBtn
                    text: "Connect"
                    enabled: !root.busy && addr.text !== ""
                    onClicked: root.run(["connect", addr.text.trim()])
                }
            }

            Txt {
                visible: root.message !== "" || root.busy
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: root.busy ? "Working…" : root.message
                color: Theme.dim
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button { text: "Close"; onClicked: root.closed() }
            }
        }
    }
}
