pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower

// Runs the root helper bbkos-power-apply (installed by scripts/install-power-helper.sh, allowed through sudoers with no
// arguments) whenever what it applies may be out of date: at login, after a profile change, when the charger is plugged
// or unplugged (power-profiles-daemon rewrites balanced's EPP then), after a Power-settings edit and after a resume.
// The helper decides what to write from settings.json (power.*) and the active profile; this file only decides when.
// Contract (docs/modules/power-tuning.md):
// - status: "idle", "applying", "not-installed" (sudo has no rule for the helper, or the helper is missing) or
//   "error: <first line>"; last: the helper's last result ({profile, applied, skipped, errors}), {} before the first run.
// - One run at a time. A request while one is running is remembered and runs once more afterwards (coalesced).
// - A run still going after 10 s is stopped and ends as "error: helper timed out".
// - Going back to "default" for the current profile's EPP bounces the profile (another one, then back) so the daemon
//   rewrites its own EPP: it only does so on a change. Only on a settings edit, never on a profile change.
Singleton {
    id: root

    readonly property string installedPath: "/usr/local/sbin/bbkos-power-apply"
    // BBKOS_POWER_HELPER is a test hook: a stand-in helper is run directly (it cannot pass the sudoers rule).
    readonly property string helperPath: Quickshell.env("BBKOS_POWER_HELPER") || installedPath
    readonly property var prefixes: ["saver", "balanced", "performance"]    // Power.profile 0, 1, 2

    property string status: "idle"
    property var last: ({})

    property bool _again: false
    property bool _timedOut: false
    // power.* as last seen, to tell a real edit from any other settings change. Taken ONCE at startup (Component.onCompleted
    // assigns it; a binding would update itself on every settings change and every edit would look like "no change").
    // Starting from "" instead made the first edit after each shell restart look like the first load of the file.
    property string _powerJson: "{}"
    Component.onCompleted: _powerJson = JSON.stringify(ThemeStore.settings.power ?? {})
    property real _lastTick: Date.now()

    function apply(reason: string) {
        if (proc.running) { _again = true; return }
        status = "applying"
        watchdog.restart()
        proc.running = true
    }

    function firstLine(text: string): string {
        const lines = String(text).split("\n").map(l => l.trim()).filter(l => l !== "")
        return lines.length > 0 ? lines[0] : ""
    }

    function finished(code: int) {
        watchdog.stop()
        const errText = err.text.trim()
        let parsed = null
        try { parsed = JSON.parse(out.text.trim().split("\n").pop()) } catch (e) { parsed = null }
        if (_timedOut) {
            _timedOut = false
            status = "error: helper timed out"
        } else if (code === 0 && parsed !== null) {
            last = parsed
            status = "idle"
        } else if (/a password is required|not allowed|command not found|No such file/i.test(errText)) {
            status = "not-installed"
        } else {
            const why = parsed && parsed.errors && parsed.errors.length > 0 ? parsed.errors[0] : errText
            status = "error: " + (firstLine(why) || "exit " + code)
        }
        if (_again) { _again = false; apply("again") }
    }

    // A real edit of power.*: bounce the profile when the current profile's EPP went back to "default", then apply.
    function settingsChanged() {
        const power = ThemeStore.settings.power
        const now = JSON.stringify(power ?? {})
        if (now === _powerJson) return
        const prev = JSON.parse(_powerJson)
        _powerJson = now
        const key = prefixes[Power.profile] + "Epp"
        const wasOverridden = prev[key] !== undefined && prev[key] !== "default"
        if (wasOverridden && (power === undefined || power[key] === undefined || power[key] === "default")) {
            bounceBack = PowerProfiles.profile
            PowerProfiles.profile = bounceBack === 1 ? 0 : 1
            bounceTimer.restart()
        } else {
            apply("settings")
        }
    }
    property int bounceBack: 1

    Process {
        id: proc
        command: root.helperPath === root.installedPath ? ["sudo", "-n", root.helperPath] : [root.helperPath]
        stdout: StdioCollector { id: out }
        stderr: StdioCollector { id: err }
        onExited: (code, status) => root.finished(code)
    }

    Timer { id: watchdog; interval: 10000; onTriggered: { root._timedOut = true; proc.running = false } }
    Timer { id: loginTimer; interval: 3000; running: true; onTriggered: root.apply("login") }      // UPower and the daemon start lazily
    Timer { id: profileTimer; interval: 400; onTriggered: root.apply("profile") }                   // after the daemon's own write
    // After the bounce: put the profile back and apply once the daemon has written. profileTimer is restarted here as
    // well as by the profile signal, so the edit is applied even when the profile change never takes effect.
    Timer { id: bounceTimer; interval: 300; onTriggered: { PowerProfiles.profile = root.bounceBack; profileTimer.restart() } }

    // Resume: this timer stops while asleep, so a long gap between two ticks means the machine slept.
    Timer {
        interval: 30000; running: true; repeat: true
        onTriggered: { const n = Date.now(); if (n - root._lastTick > 90000) root.apply("resume"); root._lastTick = n }
    }

    Connections { target: PowerProfiles; function onProfileChanged() { profileTimer.restart() } }
    // Charger plugged or unplugged: the daemon rewrites balanced's EPP now, so wait for it like after a profile change.
    Connections { target: Power; function onDischargingChanged() { profileTimer.restart() } }
    Connections { target: ThemeStore; function onSettingsChanged() { root.settingsChanged() } }
}
