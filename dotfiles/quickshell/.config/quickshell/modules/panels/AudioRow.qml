import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// One audio device. Click makes it the default (new sounds follow it).
Rectangle {
    id: row
    required property var node
    property bool isDefault: false
    property bool input: false
    signal chosen()

    implicitHeight: 36
    Layout.fillWidth: true
    radius: Theme.controlRadius
    color: isDefault ? Theme.inset : "transparent"

    RowLayout {
        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
        spacing: 8
        Txt {
            text: row.input ? "" : Audio.isBluetooth(row.node) ? "" : ""
            color: row.isDefault ? Theme.accent : Theme.fg
        }
        Txt { text: Audio.label(row.node); Layout.fillWidth: true; elide: Text.ElideRight }
        Txt { visible: row.isDefault; text: ""; color: Theme.accent }
    }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: row.chosen() }
}
