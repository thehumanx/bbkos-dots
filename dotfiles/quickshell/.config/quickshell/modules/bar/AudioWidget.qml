import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Volume icon (headphones when the output is Bluetooth) and percentage. The Bluetooth device name is on the Bluetooth widget.
// Left click opens the audio popup, middle click toggles mute, scroll changes volume in 5% steps. The icon set is bar.iconAudio.
Txt {
    property string screenName      // the bar's screen: the popup opens there
    readonly property int pct: Math.round(Audio.volume * 100)
    readonly property var icons: BarIcons.style("audio", SettingsStore.shown("bar.iconAudio"))
    readonly property string icon: Audio.muted ? icons.muted : Audio.isBluetooth(Audio.sink) ? icons.headphones
        : pct < 33 ? icons.low : icons.high
    horizontalAlignment: Text.AlignHCenter
    text: Audio.muted || Theme.barIconsOnly ? icon : Theme.barVertical ? icon + "\n" + pct : BarIcons.label(icon, pct + "%", Theme.barIconGap)
    color: Audio.muted ? dimColor : tone(Theme.accent3)

    BarHit { id: hit; acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => { if (mouse.button === Qt.MiddleButton) Audio.toggleMute(); else PanelState.toggle("audio", screenName, hit.center()) }
        onWheel: wheel => Audio.step(wheel.angleDelta.y > 0 ? 0.05 : -0.05)
    }
}
