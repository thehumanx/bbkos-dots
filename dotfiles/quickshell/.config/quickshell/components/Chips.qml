import QtQuick
import QtQuick.Layouts
import qs

// One value out of a list as a wrapping row of chips. Owns no state: `current` is what is shown, chosen(value) is
// emitted on a click. `model` holds plain values or { value, label } objects (with `font`, the chip is drawn in that family). Numbers compare within 0.005 (a scale
// of 1.5 read back from Hyprland), everything else as text. The chosen chip is the accent with dark bold text.
// `multi: true` (SettingChoices): `currents` is a list, every chip in it is chosen, and a click on a chosen chip is emitted too
// (the owner turns it off). Multi chips also carry a small checkbox in front, so they read as "pick several" and the single ones as "pick one".
Flow {
    id: root
    property var model: []
    property var current
    property bool multi: false
    property var currents: []
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
            readonly property bool selected: root.multi ? (Array.isArray(root.currents) && root.currents.some(c => root.same(root.valueOf(modelData), c)))
                                                         : root.same(root.valueOf(modelData), root.current)

            width: Math.ceil((name.implicitWidth + 24 + (root.multi ? 22 : 0)) / 2) * 2      // even: whole pixels at 1.5x
            height: 30
            radius: Theme.controlRadius
            color: selected ? Theme.accent : (area.containsMouse ? Theme.accentSoft : Theme.control)
            border.width: Theme.hair
            border.color: selected ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, area.containsMouse ? 0.4 : 0.16)
            Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
            scale: area.pressed && !Theme.reduceMotion ? 0.97 : 1          // press feedback, as Button
            Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

            Rectangle {                                                     // checkbox, multi only
                visible: root.multi
                width: 14; height: 14
                radius: 4
                anchors.verticalCenter: parent.verticalCenter
                x: 10
                color: chip.selected ? Theme.bg : "transparent"
                border.width: Theme.hair
                border.color: chip.selected ? Theme.bg : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.5)
                Txt {
                    anchors.centerIn: parent
                    visible: chip.selected
                    text: "✓"
                    color: Theme.accent
                    font.bold: true
                    font.pixelSize: 11
                }
            }
            Txt {
                id: name
                anchors.verticalCenter: parent.verticalCenter
                x: root.multi ? 32 : Math.round((parent.width - width) / 2)
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
                onClicked: if (root.multi || !chip.selected) root.chosen(root.valueOf(chip.modelData))
            }
        }
    }
}
