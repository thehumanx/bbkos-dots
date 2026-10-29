import QtQuick
import qs
import qs.components
import qs.services
import "../../components/Duration.js" as Duration
import "../../components/BarIcons.js" as BarIcons

// The live timer (the BarItem in Bar.qml hides it while no timer exists). Click opens the timer popup: pause, +1 min,
// +5 min, reset. Paused is dim; done is red and flashes three times (a red plate, the text flipping tone),
// then stays a soft red until dismissed. The icon is a Nerd Font glyph.
Txt {
    id: root
    property string screenName
    readonly property bool done: Countdown.state === "done"
    readonly property string t: Duration.format(Countdown.remaining)
    horizontalAlignment: Text.AlignHCenter
    font.bold: true
    text: Theme.barVertical ? (t.length > 5 ? t.slice(0, t.length - 3).replace(":", "h\n") : t.replace(":", "\n"))
                            : "󰔛" + BarIcons.gapText(Theme.barIconGap) + t
    // A real red, not Theme.crit: with a high-contrast theme crit is near-white. Light red on a dark bar, dark red on a
    // light one (4.5:1 either way); over the plate at its brightest the text flips to the opposite tone.
    readonly property bool lightBar: Theme.bg.hslLightness > 0.5
    readonly property color red: lightBar ? "#b00020" : "#ff5a5a"
    color: done ? (plate.opacity > 0.6 ? (lightBar ? "#ffffff" : "#101010") : red)
         : Countdown.state === "paused" ? dimColor : tone(Theme.accent)

    property real glow: 0
    Connections {
        target: Countdown
        function onDoneSerialChanged() { flash.restart() }
    }
    SequentialAnimation {
        id: flash
        loops: 3
        NumberAnimation { target: root; property: "glow"; to: 1; duration: 160 }
        NumberAnimation { target: root; property: "glow"; to: 0; duration: 280 }
    }

    Rectangle {                                // behind the text, the size of the whole bar item (BarHit's box)
        id: plate
        x: hit.x; y: hit.y; width: hit.width; height: hit.height
        z: -1
        radius: Theme.controlRadius
        color: root.red
        opacity: root.done ? (flash.running ? root.glow : 0.22) : 0
        visible: opacity > 0
    }

    BarHit { id: hit; onClicked: PanelState.toggle("timer", screenName, hit.center()) }
}
