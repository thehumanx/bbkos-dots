import QtQuick
import Quickshell
import qs
import qs.components
import qs.services

// Minute precision: the clock wakes once a minute, aligned to the minute boundary (once a second only when clock.seconds is
// on). clock.hour24, clock.date and clock.seconds choose the format ("Sun 24, 5:11"; no AM or PM, the hour says which). Left
// click opens the calendar popup (modules/panels/CalendarPanel.qml) on this bar's screen; resting the pointer on it shows the
// full date and the Nepali one in a small card (clock.hoverDate, modules/bar/DateHover.qml).
Txt {
    id: root
    property string screenName
    readonly property var cfg: ThemeStore.settings.clock ?? ({})
    readonly property bool h24: cfg.hour24 !== false
    readonly property bool secs: cfg.seconds === true
    SystemClock { id: clock; precision: root.secs ? SystemClock.Seconds : SystemClock.Minutes }
    horizontalAlignment: Text.AlignHCenter
    color: tone(Theme.accent3)
    // Qt only counts 12 hours when the format has AM or PM, so the hour is worked out here.
    readonly property string hour: h24 ? Qt.formatDateTime(clock.date, "HH") : String(clock.date.getHours() % 12 || 12)
    text: Theme.barVertical ? hour + "\n" + Qt.formatDateTime(clock.date, "mm")
                            : (cfg.date !== false ? Qt.formatDateTime(clock.date, "ddd d, ") : "") + hour + Qt.formatDateTime(clock.date, ":mm") + (secs ? Qt.formatDateTime(clock.date, ":ss") : "")

    BarHit {
        id: hit
        hoverEnabled: true
        onClicked: PanelState.toggle("calendar", screenName, hit.center())
    }

    // The card shows as soon as the pointer is on the clock, and goes when it leaves or the calendar opens.
    readonly property bool wantTip: hit.containsMouse && cfg.hoverDate !== false && !PanelState.isOn("calendar", screenName)
    DateHover { id: dateHover; target: hit.slot ? hit.slot : root; shown: root.wantTip }
}
