import QtQuick
import qs

// A number control in one piece: "−" at the left end, "+" at the right end and between them a bar filled up to the
// value with the value written in it. Press or drag on the bar to set the value there; a click on − or + moves one
// step, holding it repeats. The fill is the soft accent with a 2 px accent edge at the value, so the text stays the normal
// colour and a full bar does not glare with a pale accent (first tried: a full accent fill, too loud on the owner's). The owner kept the stepper and asked for the slider to become one with it (2026-10-28);
// the shape follows Blender's number slider field. Owns no state: `value` is what is shown, moved(v) is emitted
// (already snapped to `step` within from-to) while the bar is pressed or dragged and on each step, released() when
// a drag ends. `text` is what is written in the bar (the caller formats it, with a unit).
Item {
    id: root
    property real value: 0
    property real from: 0
    property real to: 1
    property real step: 1
    property string text: ""
    property bool known: true                 // false: no fill, the buttons do nothing (missing value)
    property string unknownText: "-"          // written in the bar while !known ("…" where a value is still being read)
    readonly property bool pressed: barArea.pressed
    signal moved(real value)
    signal released()

    readonly property real frac: known && to > from ? Math.max(0, Math.min(1, (value - from) / (to - from))) : 0
    readonly property bool fractional: Math.round(step) !== step
    readonly property real end: 30                                       // width of the − and + ends

    function snap(v) {
        if (!(step > 0) || !(to > from)) return from
        const n = Math.max(from, Math.min(to, Math.round((v - from) / step) * step + from))
        return Number(n.toFixed(fractional ? 6 : 0))                  // 0.1 + 0.2 noise must not reach the tool
    }
    function nudge(dir) {
        if (!known) return
        const v = snap(value + dir * step)
        if (v !== value) moved(v)
    }

    implicitWidth: 240
    implicitHeight: 30
    opacity: enabled ? 1 : 0.4

    Rectangle {
        id: frame
        anchors.fill: parent
        radius: Theme.controlRadius
        color: Theme.inset
        border.width: Theme.hair
        border.color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, (barArea.containsMouse || minus.hovered || plus.hovered) && root.enabled ? 0.4 : 0.2)
        Behavior on border.color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    }

    component End: Rectangle {
        id: btn
        property string glyph
        property int dir
        readonly property bool hovered: area.containsMouse
        readonly property bool can: root.known && (dir < 0 ? root.value > root.from : root.value < root.to)
        width: root.end
        height: root.height
        color: area.pressed && can ? Theme.accentSoft : area.containsMouse && can ? Theme.control : "transparent"
        radius: Theme.controlRadius
        Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
        Txt { anchors.centerIn: parent; text: btn.glyph; color: btn.can ? Theme.fg : Theme.dim; opacity: btn.can ? 1 : 0.5 }
        MouseArea {
            id: area
            anchors.fill: parent
            hoverEnabled: true
            enabled: root.enabled
            cursorShape: btn.can ? Qt.PointingHandCursor : Qt.ArrowCursor
            onPressed: { root.nudge(btn.dir); repeat.interval = 400; repeat.restart() }
            onReleased: repeat.stop()
            onCanceled: repeat.stop()
        }
        Timer { id: repeat; repeat: true; onTriggered: { interval = 70; if (btn.can) root.nudge(btn.dir); else stop() } }
    }

    End { id: minus; glyph: "−"; dir: -1; anchors.left: parent.left }
    End { id: plus; glyph: "+"; dir: 1; anchors.right: parent.right }

    Rectangle { x: root.end; width: Theme.hair; height: parent.height; color: frame.border.color }
    Rectangle { x: root.width - root.end - Theme.hair; width: Theme.hair; height: parent.height; color: frame.border.color }

    Item {
        id: bar
        anchors { fill: parent; leftMargin: root.end + Theme.hair; rightMargin: root.end + Theme.hair; topMargin: Theme.hair; bottomMargin: Theme.hair }

        Rectangle { id: fill; width: bar.width * root.frac; height: bar.height; color: Theme.accentSoft }
        Rectangle {                                                      // the value's edge
            visible: root.known && root.frac > 0 && root.frac < 1
            x: Math.max(0, fill.width - width)
            width: 2
            height: bar.height
            color: Theme.accent
        }
        Txt {                                                            // right-aligned: the edge only meets it near the top
            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            text: root.known ? root.text : root.unknownText
            font.bold: true
            font.pixelSize: Theme.fontSize - 1
        }
        MouseArea {
            id: barArea
            anchors.fill: parent
            enabled: root.enabled && root.known
            hoverEnabled: true
            cursorShape: Qt.SizeHorCursor
            preventStealing: true                                        // the page's Flickable must not take the drag
            function set(mx) {
                const v = root.snap(root.from + Math.max(0, Math.min(1, mx / Math.max(1, width))) * (root.to - root.from))
                if (v !== root.value) root.moved(v)
            }
            onPressed: mouse => set(mouse.x)
            onPositionChanged: mouse => { if (pressed) set(mouse.x) }
            onReleased: root.released()
        }
    }
}
