import QtQuick
import QtQuick.Layouts
import qs

// The title line of a bar popup, in the settings window's section-title style (bold, one size up, 22 high):
// `PopupHeader { title: "Wi-Fi"; Toggle {...} }`. `status` is dim text at the right (Battery's "On battery"); children
// (a Toggle, a mute button) sit after it at the right edge.
RowLayout {
    id: root
    property string title
    property string status: ""
    property color statusColor: Theme.dim
    default property alias content: slot.data

    Layout.fillWidth: true
    Layout.minimumHeight: 22
    spacing: 8

    Txt { text: root.title; font.bold: true; font.pixelSize: Theme.fontSize + 1; elide: Text.ElideRight; Layout.fillWidth: true }
    Txt { visible: root.status !== ""; text: root.status; color: root.statusColor }
    RowLayout { id: slot; spacing: 8; visible: children.length > 0 }
}
