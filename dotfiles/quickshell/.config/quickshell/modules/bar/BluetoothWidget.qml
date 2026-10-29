import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Hidden (by its BarItem in Bar.qml) when there is no adapter. Icon only in a vertical bar. The icon shows the state
// (bar.iconBluetooth): off when the adapter is off, connected when devices are connected, idle otherwise. Accent when
// devices are connected. Shows the device name (like the Wi-Fi widget shows the network), "name +N" for several.
Txt {
    property string screenName      // the bar's screen: the popup opens there
    readonly property var icons: BarIcons.style("bluetooth", SettingsStore.shown("bar.iconBluetooth"))
    readonly property string glyph: !Bt.enabled ? icons.off : Bt.connectedCount > 0 ? icons.connected : icons.idle
    readonly property string device: Bt.connectedCount > 0 && !Theme.barVertical && !Theme.barIconsOnly
        ? Bt.connected[0].name + (Bt.connectedCount > 1 ? " +" + (Bt.connectedCount - 1) : "") : ""
    text: device === "" ? glyph : BarIcons.label(glyph, device, Theme.barIconGap)
    elide: Text.ElideRight
    width: Math.min(implicitWidth, 180)
    color: Bt.enabled && Bt.connectedCount > 0 ? Theme.accent : tone(Theme.accent3)

    BarHit { id: hit; cursorShape: Qt.PointingHandCursor; onClicked: PanelState.toggle("bluetooth", screenName, hit.center()) }
}
