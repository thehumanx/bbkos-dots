import QtQuick
import qs
import qs.components
import qs.services

// The music widget (docs/modules/media.md): a note, the artist and title. It is as wide
// as the song needs, up to media.maxWidth; with the pointer on it, previous, play or pause and next appear and the title is cut
// shorter to make room, so the widget never grows. A paused song stays, dimmed. Left click opens the app the song plays in,
// middle click skips to the next song, scrolling changes the volume. The BarItem in Bar.qml hides it while nothing is on.
Item {
    id: root
    property string screenName
    readonly property var cfg: ThemeStore.settings.media ?? ({})
    readonly property int maxW: cfg.maxWidth ?? 220
    readonly property int gap: 4 * Theme.barIconGap          // note to title: 8 px at the default of 2 spaces
    readonly property int btnW: 18
    readonly property int controlsW: 3 * btnW
    readonly property int iconW: Math.ceil(iconText.implicitWidth)
    readonly property string label: Media.artist !== "" ? Media.artist + " – " + Media.title : Media.title

    // One MouseArea (the BarHit below) owns the hover and every click; the buttons are only drawn, and a click is matched to a
    // button by where it landed. Separate MouseAreas on the buttons took the hover from the widget's as the pointer reached
    // them, so the buttons vanished and came back, over and over.
    readonly property bool hovered: hit.containsMouse
    readonly property int hoverIdx: {                    // the button under the pointer, -1 for none
        if (!hovered) return -1
        const p = hit.mapToItem(controls, hit.mouseX, hit.mouseY)
        return p.x >= 0 && p.x < controlsW && p.y >= -4 && p.y <= controls.height + 4 ? Math.floor(p.x / btnW) : -1
    }

    // Wide enough for the song, never wider than maxW, never so narrow that the buttons leave the title nothing.
    readonly property real wantW: Theme.barIconsOnly ? iconW + (hovered ? gap + controlsW : 0)      // bar.iconsOnly: the note, no title
        : Math.min(maxW, Math.max(iconW + gap + Math.ceil(probe.implicitWidth), iconW + 2 * gap + controlsW + 48))
    property real shownW: wantW
    Behavior on shownW { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    implicitWidth: Math.round(shownW)
    implicitHeight: Math.ceil(iconText.implicitHeight) + 8      // the height it had with the old progress line, so the bar and the hover area stay the same

    Txt { id: probe; visible: false; text: root.label }

    Row {
        id: row
        spacing: root.gap
        anchors.verticalCenter: parent.verticalCenter
        opacity: Media.playing ? 1 : 0.55
        Behavior on opacity { NumberAnimation { duration: Theme.durFast } }

        Txt { id: iconText; text: "󰝚"; color: tone(Theme.accent); anchors.verticalCenter: parent.verticalCenter }
        Txt {
            visible: !Theme.barIconsOnly
            text: root.label
            textFormat: Text.PlainText
            elide: Text.ElideRight
            width: Math.max(0, root.width - root.iconW - root.gap - (root.hovered ? root.gap + root.controlsW : 0))
            anchors.verticalCenter: parent.verticalCenter
        }
        Row {                                            // previous, play or pause, next: only while the pointer is on the widget
            id: controls
            visible: root.hovered
            anchors.verticalCenter: parent.verticalCenter
            Repeater {
                model: ["󰒮", Media.playing ? "󰏤" : "󰐊", "󰒭"]
                delegate: Txt {
                    required property string modelData
                    required property int index
                    width: root.btnW
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData
                    color: root.hoverIdx === index ? tone(Theme.accent) : fgColor
                }
            }
        }
    }


    BarHit {
        id: hit
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        onClicked: ev => {
            if (ev.button === Qt.MiddleButton) Media.next()
            else if (root.hoverIdx === 0) Media.previous()
            else if (root.hoverIdx === 1) Media.toggle()
            else if (root.hoverIdx === 2) Media.next()
            else Media.open()
        }
        onWheel: ev => Audio.step(ev.angleDelta.y > 0 ? 0.05 : -0.05)
    }
}
