import QtQuick
import Quickshell
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Pending package updates (services/Updates.qml). Hidden by its BarItem in Bar.qml while there are none. Click opens a
// floating terminal running bbkos-update (yay -Syu, then bbkos-check). Icon and count, the count on a second line in a
// vertical bar.
Txt {
    readonly property string icon: "󰚰"
    horizontalAlignment: Text.AlignHCenter
    text: Theme.barIconsOnly ? icon : Theme.barVertical ? icon + "\n" + Updates.count : BarIcons.label(icon, Updates.count, Theme.barIconGap)
    color: Theme.accent2

    BadgeDot { shown: Theme.barIconsOnly; dotColor: Theme.accent2 }     // the count is hidden: a dot says updates are waiting

    BarHit { cursorShape: Qt.PointingHandCursor
        onClicked: Quickshell.execDetached(["bbkos-tui", "bbkos-update"])
    }
}
