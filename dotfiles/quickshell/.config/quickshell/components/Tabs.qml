import QtQuick
import QtQuick.Layouts
import qs

// A row of tabs under a page title: text labels, the current one bold in the accent with a 2 px accent line under it, a
// hairline under the whole row. Tabs choose a place, not a value, so they look unlike Chips. Owns no state: `current` is
// the index shown, picked(index) is emitted on a click.
Item {
    id: root
    property var model: []               // labels
    property int current: 0
    signal picked(int index)

    implicitHeight: 36
    Layout.fillWidth: true

    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Theme.hair
        color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.12)
    }
    Row {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        spacing: 4
        Repeater {
            model: root.model
            delegate: Item {
                id: tab
                required property var modelData
                required property int index
                readonly property bool active: index === root.current
                width: Math.ceil((name.implicitWidth + 24) / 2) * 2
                height: root.height
                Rectangle {
                    anchors { fill: parent; bottomMargin: 4 }
                    radius: Theme.controlRadius
                    color: area.containsMouse && !tab.active ? Theme.control : "transparent"
                    Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
                }
                Txt {
                    id: name
                    anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: parent.verticalCenter; verticalCenterOffset: -2 }
                    text: tab.modelData
                    color: tab.active ? Theme.accent : (area.containsMouse ? Theme.fg : Theme.dim)
                    font.bold: tab.active
                }
                Rectangle {
                    visible: tab.active
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 2
                    color: Theme.accent
                }
                MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.picked(tab.index) }
            }
        }
    }
}
