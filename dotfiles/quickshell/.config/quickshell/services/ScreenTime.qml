pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../components/ScreenBreak.js" as ScreenBreak

// Seconds the screen has been on, since boot and since the charger was last unplugged (the battery popup shows both).
// "On" = not locked (no hyprlock) and the monitors are not powered off (DPMS). Sampled every 30 s; a gap longer than two
// intervals (suspend, a stalled shell) is not counted. The totals live in $XDG_STATE_HOME/quickshell so a shell restart
// keeps them; a different boot id resets the boot total. The unplug total only grows on battery and restarts at 0 on
// each unplug, so on AC it still shows the last discharge. An unplug is "on battery now, and the last state we saved was
// AC" (saved, not a binding: a binding to Power.discharging has already flipped when the change handler runs, so the
// first unplug after a shell start was missed), which also catches an unplug while the shell was not running. After a
// reboot a higher battery percentage than saved means it was charged while off.
Singleton {
    id: root

    readonly property int interval: 30000
    property real bootSeconds: 0
    property real streakSeconds: 0      // the current stretch at the screen (wellbeing.breakEvery reminds when it is long enough)
    property real _offSeconds: 0
    readonly property int breakEvery: (ThemeStore.settings.wellbeing ?? {}).breakEvery ?? 0
    property real unplugSeconds: 0
    property real uptimeSeconds: 0      // wall clock since the kernel started (/proc/uptime), refreshed every sample
    property real _changedAt: 0         // when the charger state last changed (ms since epoch, 0 = not known); the popup's "since last charge"
    readonly property real chargerSeconds: _changedAt > 0 ? Math.max(0, (clock.date.getTime() - _changedAt) / 1000) : -1

    property string _bootId: ""
    property real _last: 0
    property var _onBattery: null    // last charger state seen (saved); null = not known yet
    property int _percent: -1        // battery percentage at the last save (-1 = unknown)
    property int _offPercent: -1     // the saved percentage when it came from an earlier boot, checked once UPower is ready

    readonly property string _screenOnCmd: "pgrep -x hyprlock >/dev/null && exit 1; hyprctl monitors -j | grep -q '\"dpmsStatus\": true'"

    function _save() {
        if (Power.device.ready) _percent = Power.percent
        store.setText(JSON.stringify({ bootId: _bootId, boot: bootSeconds, unplug: unplugSeconds,
                                       onBattery: _onBattery, percent: _percent, changedAt: _changedAt }))
    }

    function _track() {   // waits until UPower has read the battery: before that "discharging" reads false even on battery
        if (_bootId === "" || !Power.device.ready) return
        // Charged while the laptop was off: the percentage went up (2 points of slack for the gauge settling).
        if (_offPercent >= 0 && Power.percent > _offPercent + 2) _onBattery = false
        _offPercent = -1
        const d = Power.discharging
        if (d === _onBattery) return
        if (d && _onBattery === false) unplugSeconds = 0
        _onBattery = d
        _changedAt = Date.now()
        _save()
    }

    Connections {
        target: Power
        function onDischargingChanged() { root._track() }
    }
    Connections {
        target: Power.device
        function onReadyChanged() { root._track() }
    }

    FileView {
        id: store
        path: Quickshell.statePath("screentime.json")
        blockLoading: true
        atomicWrites: true
    }

    Process {
        id: probe
        command: ["sh", "-c", root._screenOnCmd]
        onExited: (code, status) => {
            const now = Date.now()
            const dt = root._last > 0 ? now - root._last : 0
            root._last = now
            root._track()
            root._streak(code === 0, dt)
            if (code !== 0 || dt <= 0 || dt > 2 * root.interval) return
            root.bootSeconds += dt / 1000
            if (Power.discharging) root.unplugSeconds += dt / 1000
            root._save()
        }
    }

    SystemClock { id: clock; precision: SystemClock.Minutes }

    Process {
        id: upProbe
        command: ["cat", "/proc/uptime"]
        stdout: StdioCollector { onStreamFinished: root.uptimeSeconds = Number(text.split(" ")[0]) || 0 }
    }

    Process {
        id: bootProbe
        command: ["cat", "/proc/sys/kernel/random/boot_id"]
        stdout: StdioCollector { onStreamFinished: root._init(text.trim()) }
        running: true
    }

    // The break reminder: a notification through the shell's own server (so do not disturb and the history apply).
    function _streak(on: bool, dt: real) {
        const r = ScreenBreak.step({ streak: streakSeconds, off: _offSeconds }, on, dt, interval, breakEvery)
        streakSeconds = r.streak
        _offSeconds = r.off
        if (r.remind)
            Quickshell.execDetached(["notify-send", "-a", "bbkOS", "-u", "low", "Time for a break",
                                     "You have been at the screen for " + breakEvery + " minutes. Look away for a moment."])
    }

    IpcHandler {
        target: "screentime"
        function status(): string { return JSON.stringify({ boot: root.bootSeconds, unplug: root.unplugSeconds, streak: root.streakSeconds, breakEvery: root.breakEvery }) }
        function setStreak(seconds: int): void { root.streakSeconds = seconds }       // test hook
    }

    function _init(id) {
        _bootId = id
        try {
            const saved = JSON.parse(store.text())
            unplugSeconds = Number(saved.unplug) || 0
            _changedAt = Number(saved.changedAt) || 0
            if (saved.bootId === id) bootSeconds = Number(saved.boot) || 0
            if (typeof saved.onBattery === "boolean") _onBattery = saved.onBattery
            const p = Number(saved.percent)
            if (saved.bootId !== id && saved.percent !== undefined && p >= 0) _offPercent = p
            if (saved.bootId === id && p >= 0) _percent = p
        } catch (e) { /* first run, or an unreadable file: start from 0 */ }
        _last = Date.now()
        _track()
        upProbe.running = true
        tick.running = true
    }

    Timer {
        id: tick
        interval: root.interval
        repeat: true
        onTriggered: {
            if (!probe.running) probe.running = true
            if (!upProbe.running) upProbe.running = true
        }
    }
}
