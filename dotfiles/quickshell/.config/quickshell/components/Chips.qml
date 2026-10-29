import QtQuick
import QtQuick.Layouts
import qs

// One value out of a list as a wrapping row of chips. Owns no state: `current` is what is shown, chosen(value) is
// emitted on a click. `model` holds plain values or { value, label } objects (with `font`, the chip is drawn in that family). Numbers compare within 0.005 (a scale
// of 1.5 read back from Hyprland), everything else as text. The chosen chip is the accent with dark bold text.
Flow {
    id: root
    property var model: []
    property var current
    signal chosen(var value)

    function valueOf(o) { return (o !== null && typeof o === "object") ? o.value : o }
    function labelOf(o) { return (o !== null && typeof o === "object") ? String(o.label ?? o.value) : String(o) }
    function same(a, b) {
        if (a === undefined || a === null || b === undefined || b === null) return false
        if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 0.005
        return String(a) === String(b)
    }

    Layout.fillWidth: true
    spacing: 6

    Repeater {
        model: Array.isArray(root.model) ? root.model : []
        delegate: Rectangle {
            id: chip
            required property var modelData
            readonly property bool selected: root.same(root.valueOf(modelData), root.current)

            width: Math.ceil((name.implicitWidth + 24) / 2) * 2      // even: whole pixels at 1.5x
            height: 30
            radius: Theme.controlRadius
            color: selected ? Theme.accent : (area.containsMouse ? Theme.accentSoft : Theme.control)
            border.width: Theme.hair
            border.color: selected ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, area.containsMouse ? 0.4 : 0.16)
            Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
            scale: area.pressed && !Theme.reduceMotion ? 0.97 : 1          // press feedback, as Button
            Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

            Txt {
                id: name
                anchors.centerIn: parent
                text: root.labelOf(chip.modelData)
                color: chip.selected ? Theme.bg : Theme.fg
                font.bold: chip.selected
                font.pixelSize: Theme.fontSize - 1
                font.family: chip.modelData !== null && typeof chip.modelData === "object" && chip.modelData.font ? chip.modelData.font : Theme.font
            }
            MouseArea {
                id: area
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (!chip.selected) root.chosen(root.valueOf(chip.modelData))
            }
        }
    }
}
