import QtQuick
import qs

// Text button: a raised surface with a hairline edge, accent-soft on hover.
Rectangle {
    id: root
    property alias text: label.text
    property color tint: Theme.fg
    signal clicked()

    implicitWidth: label.implicitWidth + 24
    implicitHeight: 30
    radius: Theme.controlRadius
    color: area.pressed ? Theme.accentSoft : area.containsMouse ? Theme.accentSoft : Theme.control
    border.width: Theme.hair
    border.color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, area.containsMouse ? 0.4 : 0.2)
    opacity: enabled ? 1 : 0.4
    Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    // Press feedback (docs/modules/motion.md): shrinks to 97% while held, so the click is felt at once.
    scale: area.pressed && !Theme.reduceMotion ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

    Text {
        id: label
        anchors.centerIn: parent
        color: root.tint
        font.family: Theme.font
        font.pixelSize: Theme.fontSize - 1
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        enabled: root.enabled
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
