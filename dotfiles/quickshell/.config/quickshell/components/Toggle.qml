import QtQuick
import qs

// On/off switch. Emits toggled(value); it never changes `checked` itself (the model owns the state).
// High contrast in both states: on is the accent track with a dark knob carrying an accent tick, off is a dark track with an
// outline and a light knob, so the state reads at a glance even when the accent is a pale colour.
Rectangle {
    id: root
    property bool checked: false
    signal toggled(bool value)

    implicitWidth: 46
    implicitHeight: 26
    radius: Theme.gridSquare ? 0 : height / 2          // grid mode: square
    opacity: enabled ? 1 : 0.4
    color: checked ? Theme.accent : Theme.inset
    border.width: 2
    border.color: checked ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.55)
    Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    Behavior on border.color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

    Rectangle {
        id: knob
        property real size: area.pressed ? 20 : 16
        width: size; height: size; radius: Theme.gridSquare ? 0 : size / 2
        anchors.verticalCenter: parent.verticalCenter
        x: root.checked ? root.width - width - 5 : 5
        color: root.checked ? Theme.bg : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.85)
        Behavior on x { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
        Behavior on size { NumberAnimation { duration: 80; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
        Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

        Text {
            anchors.centerIn: parent
            visible: root.checked
            text: ""                                   // Font Awesome check
            color: Theme.accent
            font.family: Theme.font
            font.pixelSize: 10
        }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.toggled(!root.checked)
    }
}
