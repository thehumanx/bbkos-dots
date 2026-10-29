import QtQuick
import QtQuick.Layouts
import qs

// One part of a bar popup, with the settings window's row rhythm: the settings hairline above it (unless `first`), 12 px
// of room, an optional title in the section-title style, then the children 8 px apart. The popup card itself is the
// card, so there is no card inside it (docs/specs/2026-10-29-popup-redesign-design.md).
ColumnLayout {
    id: root
    property string title: ""
    property bool first: false
    default property alias content: body.data

    Layout.fillWidth: true
    spacing: 0

    Rectangle {
        visible: !root.first
        Layout.fillWidth: true
        Layout.bottomMargin: 12
        implicitHeight: Theme.hair
        color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.10)
    }
    Txt {
        visible: root.title !== ""
        text: root.title
        font.bold: true
        font.pixelSize: Theme.fontSize + 1
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.preferredHeight: 22
        Layout.bottomMargin: 8
        verticalAlignment: Text.AlignVCenter
    }
    ColumnLayout { id: body; Layout.fillWidth: true; spacing: 8 }
}
