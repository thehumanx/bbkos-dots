pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Runs the root helper bbkos-logind-apply (installed by scripts/install-logind-helper.sh, allowed through sudoers with no
// arguments) after the lid or power-button settings (session.*) change, so logind's drop-in follows the settings file. The helper
// reads settings.json itself and decides what to write; this file only decides when and shows how it went.
// Contract (docs/modules/lid-power.md):
// - installed: whether the helper file exists (checked by refresh(), which the page calls when it opens).
// - status: "idle" (nothing run yet, or the last run worked), "applying", "not-installed" (sudo has no rule, or the helper is
//   missing) or "error: <first line>"; last: the helper's last result ({applied, changed, errors}).
// - One run at a time; an edit during a run is remembered and runs once more afterwards. A run over 10 s is stopped.
Singleton {
    id: root

    readonly property string installedPath: "/usr/local/sbin/bbkos-logind-apply"
    // BBKOS_LOGIND_HELPER is a test hook: a stand-in helper is run directly (it cannot pass the sudoers rule).
    readonly property string helperPath: Quickshell.env("BBKOS_LOGIND_HELPER") || installedPath

    property bool installed: true
    property string status: "idle"
    property var last: ({})

    property bool _again: false
    property bool _timedOut: false
    property string _sessionJson: "{}"          // session.* as last seen; taken once at startup (see init)

    function init() { _sessionJson = JSON.stringify(ThemeStore.settings.session ?? {}) }
    function refresh() { if (!probe.running) probe.running = true }

    function apply() {
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
        } else if (code === 0 && parsed !== null && (parsed.errors ?? []).length === 0) {
            last = parsed
            status = "idle"
            installed = true
        } else if (/a password is required|not allowed|command not found|No such file/i.test(errText)) {
            status = "not-installed"
            installed = false
        } else {
            const why = parsed && parsed.errors && parsed.errors.length > 0 ? parsed.errors[0] : errText
            status = "error: " + (firstLine(why) || "exit " + code)
        }
        if (_again) { _again = false; apply() }
    }

    Process {
        id: proc
        command: root.helperPath === root.installedPath ? ["sudo", "-n", root.helperPath] : [root.helperPath]
        stdout: StdioCollector { id: out }
        stderr: StdioCollector { id: err }
        onExited: (code, status) => root.finished(code)
    }
    Process {
        id: probe
        command: ["test", "-x", root.helperPath]
        onExited: code => root.installed = code === 0
    }
    Timer { id: watchdog; interval: 10000; onTriggered: { root._timedOut = true; proc.running = false } }

    Connections {
        target: ThemeStore
        function onSettingsChanged() {
            const now = JSON.stringify(ThemeStore.settings.session ?? {})
            if (now === root._sessionJson) return
            root._sessionJson = now
            root.apply()
        }
    }
}
