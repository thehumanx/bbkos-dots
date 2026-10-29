import QtQuick
import Quickshell
import Quickshell.Io
import qs
import qs.components
import "../../components/ScheduleMath.js" as ScheduleMath
import qs.services

// Switches the palette between light and dark by the clock while colors.auto is on (Wallpaper and colours page). The switch is
// the ordinary `bbkos-theme set colors.mode` through SettingsStore, made when the schedule is turned on (or the shell starts with
// it on) and again when the time crosses lightFrom or darkFrom; between those moments a mode picked by hand stays. The clock is
// SystemClock at minute precision, enabled only while the schedule is on, so it costs nothing otherwise (the bar clock already
// wakes every minute). Test hook: `qs ipc call themeschedule status`.
Scope {
    id: root

    readonly property var cfg: ThemeStore.settings.colors ?? ({})
    readonly property bool on: cfg.auto === true
    property string applied: ""                  // the palette this schedule last asked for ("" = not asked yet)

    SystemClock { id: clock; precision: SystemClock.Minutes; enabled: root.on }

    readonly property string wanted: ScheduleMath.isLight(clock.date.getHours() * 60 + clock.date.getMinutes(),
                                                          cfg.lightFrom ?? "07:00", cfg.darkFrom ?? "19:00") ? "light" : "dark"

    function sync() {
        if (!on) { applied = ""; return }
        if (wanted === applied) return
        applied = wanted
        if (cfg.mode !== wanted) SettingsStore.set("colors.mode", wanted)
    }
    onOnChanged: sync()
    onWantedChanged: sync()
    Component.onCompleted: sync()

    IpcHandler {
        target: "themeschedule"
        function status(): string { return JSON.stringify({ on: root.on, wanted: root.wanted, applied: root.applied, mode: root.cfg.mode ?? "" }) }
    }
}
