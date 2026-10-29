import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services
import "../../components/Duration.js" as Duration

// The timer: presets and a typed duration while it is idle; the live time with pause, +1 min, +5 min and reset while it
// runs. Used inside the calendar popup and as the timer popup (the bar widget opens it). services/Countdown is the state.
ColumnLayout {
    id: root
    spacing: 8

    property bool autoFocus: false                       // focus the input on open (the timer popup)
    property bool embedded: false                        // inside the calendar: its title is a section title, not the popup's
    readonly property bool typing: input.activeFocus     // the calendar's key shortcuts stand aside while typing
    readonly property bool done: Countdown.state === "done"
    readonly property var presets: [{ value: 60, label: "1 min" }, { value: 300, label: "5 min" }, { value: 600, label: "10 min" },
                                    { value: 900, label: "15 min" }, { value: 1500, label: "25 min" }, { value: 1800, label: "30 min" },
                                    { value: 3600, label: "1 h" }]
    property bool bad: false                             // the typed text is not a duration

    function startTyped() {
        const ms = Duration.parse(input.text)
        bad = ms === null
        if (bad) return
        Countdown.start(ms)
        input.text = ""
    }

    PopupHeader { visible: !root.embedded; title: "Timer" }

    // Idle: pick a preset or type a time
    ColumnLayout {
        visible: !Countdown.active
        Layout.fillWidth: true
        spacing: 8
        Chips {
            model: root.presets
            onChosen: v => Countdown.start(v * 1000)
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 30
                radius: Theme.controlRadius
                color: Theme.inset
                border.width: root.bad ? Theme.hair * 2 : 0
                border.color: Theme.crit
                TextInput {
                    id: input
                    anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                    verticalAlignment: TextInput.AlignVCenter
                    color: Theme.fg
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSize
                    clip: true
                    selectByMouse: true
                    onTextChanged: root.bad = false
                    Keys.onReturnPressed: root.startTyped()
                    Keys.onEnterPressed: root.startTyped()
                    Component.onCompleted: if (root.autoFocus) forceActiveFocus()
                }
                Txt { text: "5   5:30   1h30m"; color: Theme.dim; visible: input.text === ""; anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter } }
            }
            Button { text: "Start"; tint: Theme.accent; enabled: input.text !== ""; onClicked: root.startTyped() }
        }
        Txt { visible: root.bad; text: "Try 5 (minutes), 5:30, 90s or 1h30m"; color: Theme.crit; font.pixelSize: Theme.fontSize - 1 }
    }

    // Running, paused or done
    ColumnLayout {
        visible: Countdown.active
        Layout.fillWidth: true
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            Txt {
                text: Duration.format(Countdown.remaining)
                font.pixelSize: Theme.fontSize * 2
                font.bold: true
                color: root.done ? Theme.crit : Countdown.state === "paused" ? Theme.dim : Theme.fg
            }
            Txt {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: root.done ? "Time's up" : Countdown.state === "paused" ? "Paused" : "of " + Duration.format(Countdown.total)
                color: root.done ? Theme.crit : Theme.dim
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 6
            radius: Theme.gridSquare ? 0 : 3
            color: Theme.inset
            Rectangle {
                width: parent.width * (root.done ? 1 : Countdown.progress)
                height: parent.height
                radius: parent.radius
                color: root.done ? Theme.crit : Theme.accent
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Button {
                visible: !root.done
                text: Countdown.state === "paused" ? "Resume" : "Pause"
                tint: Theme.accent
                Layout.fillWidth: true
                onClicked: Countdown.state === "paused" ? Countdown.resume() : Countdown.pause()
            }
            Button { text: "+1 min"; Layout.fillWidth: true; onClicked: Countdown.add(60000) }
            Button { text: "+5 min"; Layout.fillWidth: true; onClicked: Countdown.add(300000) }
            Button { text: root.done ? "Dismiss" : "Reset"; tint: root.done ? Theme.crit : Theme.fg; Layout.fillWidth: true; onClicked: Countdown.reset() }
        }
    }
}
