import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Wi-Fi name with signal bars when connected (the first bar is the strongest), a globe for wired, a crossed Wi-Fi icon
// and dim text when offline ("connecting…" while a network is being joined, "off" only when Wi-Fi is switched off). The icon set is bar.iconWifi.
Txt {
    property string screenName      // the bar's screen: the popup opens there
    readonly property var icons: BarIcons.style("wifi", SettingsStore.shown("bar.iconWifi"))
    readonly property int level: Net.signal >= 0.75 ? 0 : Net.signal >= 0.5 ? 1 : Net.signal >= 0.25 ? 2 : 3
    readonly property string full: Net.wifiConnected ? BarIcons.label(icons.levels[level], Net.ssid !== "" ? Net.ssid : "Wi-Fi", Theme.barIconGap)
        : Net.wiredConnected ? BarIcons.label(icons.wired, "Wired", Theme.barIconGap)
        : Net.connecting ? BarIcons.label(icons.off, "connecting…", Theme.barIconGap)
        : BarIcons.label(icons.off, Net.wifiEnabled ? "offline" : "off", Theme.barIconGap)
    readonly property string glyph: Net.wifiConnected ? icons.levels[level] : Net.wiredConnected ? icons.wired : icons.off
    // Icons only (bar.iconsOnly): just the glyph; with the icon set "none" there is no glyph, so the text stays and the widget is not lost.
    text: (Theme.barIconsOnly || Theme.barVertical) && glyph !== "" ? glyph : Theme.barVertical ? full.trim().substring(0, 1) : full      // icon only in a vertical bar
    color: (Net.wifiConnected || Net.wiredConnected) ? tone(Theme.accent) : dimColor
    elide: Text.ElideRight
    width: Math.min(implicitWidth, 160)

    BarHit { id: hit; cursorShape: Qt.PointingHandCursor; onClicked: PanelState.toggle("wifi", screenName, hit.center()) }
}
