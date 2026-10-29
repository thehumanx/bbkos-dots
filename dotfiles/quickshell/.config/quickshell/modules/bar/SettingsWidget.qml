import QtQuick
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Gear icon: left click opens or closes the settings window. Accent while the window is open. The icon set is bar.iconSettings.
Txt {
    readonly property var icons: BarIcons.style("settings", SettingsStore.shown("bar.iconSettings"))
    text: icons.icon
    color: SettingsStore.windowOpen ? Theme.accent : tone(Theme.accent3)

    BarHit { cursorShape: Qt.PointingHandCursor; onClicked: SettingsStore.toggleWindow() }
}
