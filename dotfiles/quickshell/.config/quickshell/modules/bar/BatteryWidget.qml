import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Hidden (by its BarItem in Bar.qml) on machines without a battery. Warn at 20%, critical at 10% while discharging.
// Left click opens the battery popup on this bar's screen. The icon set is bar.iconBattery.
Txt {
    property string screenName
    horizontalAlignment: Text.AlignHCenter
    readonly property int pct: Power.percent
    readonly property var icons: BarIcons.style("battery", SettingsStore.shown("bar.iconBattery"))
    readonly property string charging: Power.pluggedIn && icons.bolt !== "" ? icons.bolt + " " : ""     // a gap before the level icon
    readonly property string icon: charging
        + (pct >= 90 ? icons.levels[0] : pct >= 65 ? icons.levels[1] : pct >= 40 ? icons.levels[2] : pct >= 15 ? icons.levels[3] : icons.levels[4])
    text: Theme.barIconsOnly ? icon : Theme.barVertical ? icon + "\n" + pct : BarIcons.label(icon, pct + "%", Theme.barIconGap)
    color: Power.pluggedIn ? Theme.accent
         : (Power.discharging && pct <= 10) ? Theme.crit
         : (Power.discharging && pct <= 20) ? Theme.warn
         : tone(Theme.accent2)

    BarHit { id: hit; cursorShape: Qt.PointingHandCursor
        onClicked: PanelState.toggle("battery", screenName, hit.center())
    }
}
