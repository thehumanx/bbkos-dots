import QtQuick
import Quickshell
import qs
import qs.components
import qs.services
import "../../components/BarIcons.js" as BarIcons

// Unread notification count (services/Notifs.qml). Always visible so the history panel is always reachable; the count
// is only drawn while something is unread. Left click opens the notification panel on this bar's screen.
Txt {
    id: root
    property string screenName
    horizontalAlignment: Text.AlignHCenter

    readonly property string icon: Notifs.dnd ? "󰂛" : "󰂚"           // bell with a slash while do not disturb is on
    readonly property int unread: Notifs.unread
    readonly property string badge: unread > 99 ? "99+" : String(unread)

    // Icons only (bar.iconsOnly): the bell alone, with a dot while something is unread instead of the count.
    text: Theme.barIconsOnly ? icon : Theme.barVertical ? icon + (unread > 0 ? "\n" + badge : "") : (unread > 0 ? BarIcons.label(icon, badge, Theme.barIconGap) : icon)
    color: unread > 0 && !Theme.barIconsOnly ? Theme.accent : tone(Theme.accent2)     // icons only: the dot says unread

    BadgeDot { shown: Theme.barIconsOnly && root.unread > 0; dotColor: Theme.accent }

    BarHit { id: hit; cursorShape: Qt.PointingHandCursor
        onClicked: PanelState.toggle("notifications", screenName, hit.center())
    }
}
