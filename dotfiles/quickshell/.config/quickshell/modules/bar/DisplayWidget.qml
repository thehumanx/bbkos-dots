import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Backlight icon and the brightness of the monitor this bar is on (icon only when that monitor has no brightness
// control). Left click opens the display popup on this screen, scroll changes this monitor's brightness in 5% steps.
// The icon set is bar.iconDisplay.
Txt {
    property string screenName      // the bar's screen: this widget is that monitor's brightness, the popup opens there
    readonly property var icons: BarIcons.style("display", SettingsStore.shown("bar.iconDisplay"))
    readonly property int pct: Displays.brightnessOf(screenName)
    horizontalAlignment: Text.AlignHCenter
    color: tone(Theme.accent2)
    text: pct < 0 || Theme.barIconsOnly ? icons.icon : Theme.barVertical ? icons.icon + "\n" + pct : BarIcons.label(icons.icon, pct + "%", Theme.barIconGap)

    BarHit { id: hit; cursorShape: Qt.PointingHandCursor
        onClicked: PanelState.toggle("display", screenName, hit.center())
        onWheel: wheel => Displays.stepBrightness(screenName, wheel.angleDelta.y > 0 ? 1 : -1)
    }
}
