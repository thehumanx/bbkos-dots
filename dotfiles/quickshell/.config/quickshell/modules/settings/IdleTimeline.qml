import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// The idle steps on one time line, so their order and spacing show at a glance: a dot per step at its time (dim, lock,
// screen off, suspend; "never" is left out), the name above and the time below, steps at the same time share a dot. The scale
// is the square root of the time, so 1 to 5 minutes do not crowd at the start while an hour still fits. Reads
// SettingsStore.shown, so it follows the chips below while they apply. A line under it says when the order is unusual.
ColumnLayout {
    id: root
    spacing: 6
    Layout.fillWidth: true
    Layout.topMargin: 14
    Layout.bottomMargin: 10

    function secs(key) { const v = SettingsStore.shown(key); return typeof v === "number" ? v : 0 }
    function fmt(s) { return s < 3600 ? (s / 60) + " min" : (s / 3600) + " h" }
    readonly property var steps: [
        { name: "Dim", s: secs("idle.dim") }, { name: "Lock", s: secs("idle.lock") },
        { name: "Screen off", s: secs("idle.screenOff") }, { name: "Suspend", s: secs("idle.suspend") }].filter(x => x.s > 0)
    // Steps at the same time become one dot: [{ names, s }] in time order.
    readonly property var groups: {
        const out = []
        for (const st of steps.map((x, i) => Object.assign({ i: i }, x)).sort((a, b) => a.s - b.s || a.i - b.i)) {
            const g = out.find(x => x.s === st.s)
            if (g) g.names.push(st.name); else out.push({ names: [st.name], s: st.s })
        }
        return out
    }
    readonly property real span: Math.max(600, ...steps.map(x => x.s)) * 1.1
    readonly property string warning: {
        const d = secs("idle.dim"), l = secs("idle.lock"), o = secs("idle.screenOff"), u = secs("idle.suspend")
        if (u > 0 && l > 0 && u < l) return "The laptop suspends before the lock step (suspending locks it anyway)."
        if (o > 0 && l > 0 && o < l) return "The screen switches off before it locks: a key press shows the desktop unlocked."
        if (d > 0 && l > 0 && d > l) return "The screen dims after it has locked."
        return ""
    }

    Item {
        Layout.fillWidth: true
        implicitHeight: 64

        Rectangle {                                                   // the axis
            id: axis
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            height: 2
            color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.18)
        }
        Txt { anchors { left: parent.left; bottom: axis.top; bottomMargin: 6 } text: "Idle"; color: Theme.dim; font.pixelSize: Theme.fontSize - 2 }

        Repeater {
            model: root.groups
            delegate: Item {
                id: mark
                required property var modelData
                required property int index
                readonly property real fx: Math.sqrt(modelData.s / root.span)
                x: Math.max(24, fx * parent.width)
                y: 0
                width: 0
                height: parent.height
                Behavior on x { NumberAnimation { duration: Theme.durEnter; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

                Rectangle {
                    width: 10; height: 10; radius: Theme.gridSquare ? 0 : 5
                    x: -5
                    anchors.verticalCenter: parent.verticalCenter
                    color: Theme.accent
                }
                Txt {                                                  // names: above, or below for every other dot
                    x: -width / 2
                    y: mark.index % 2 === 0 ? parent.height / 2 - height - 8 : parent.height / 2 + 8
                    text: mark.modelData.names.join(" + ")
                    font.bold: true
                    font.pixelSize: Theme.fontSize - 1
                }
                Txt {
                    x: -width / 2
                    y: mark.index % 2 === 0 ? parent.height / 2 + 8 : parent.height / 2 - height - 8
                    text: root.fmt(mark.modelData.s)
                    color: Theme.dim
                    font.pixelSize: Theme.fontSize - 2
                }
            }
        }
    }
    Txt {
        visible: root.warning !== ""
        text: root.warning
        color: Theme.warn
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
}
