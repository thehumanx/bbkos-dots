pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// State of the keybindings page. `bbkos-keybinds` is the only writer of keybinds.json and hypr-binds.lua: this store
// never writes a file, it queues bbkos-keybinds runs and reads the result back with `status` (the only run whose stdout
// is JSON). Contract (docs/specs/2026-10-19-keybindings-design.md):
// - refresh(): `bbkos-keybinds status` -> binds, actions, conflicts, warnings, shipped. Nothing polls; the page calls it.
// - add / update / remove / setEnabled / restore / restoreAll: one CLI run each, then a refresh. One process at a
//   time, in request order. A bind object goes to the tool on stdin (`--json -`), never through a shell or a temp file.
//   `replace` (default false) is --replace: it disables other enabled binds on the same keys, else a clash exits 3.
// - status: "applying" while anything is queued or running, "idle" when drained, "error: <first stderr line>" after a
//   failed run, kept until the next successful run (the queue carries on). A failed write is not cleared by the
//   refresh that follows it; the next successful write (or a refresh after a failed refresh) clears it.
// - Watchdog: a run still going after watchdogMs (60 s) is stopped (SIGTERM through running = false, SIGKILL 5 s later)
//   and ends as "error: bbkos-keybinds timed out"; the queue carries on once the process has gone.
// - Odd input (null bind, missing id) is ignored with a log line; nothing here throws.
Singleton {
    id: root

    property var binds: []               // bbkos-keybinds status "binds"
    property var actions: []             // status "actions": the action catalogue
    property var conflicts: []           // status "conflicts": pairs of bind ids sharing keys
    property var warnings: []            // status "warnings": strings
    property var shipped: []             // status "shipped": ids of the shipped default binds (restore applies to these)
    property string status: "idle"
    property int watchdogMs: 60000
    readonly property int runs: _runs    // test hook: process runs since the shell loaded

    readonly property string tool: (Quickshell.env("HOME") ?? "") + "/.local/bin/bbkos-keybinds"

    property var _queue: []              // [{ kind: "status"|"write", args, stdin }]
    property var _job: null
    property bool _exited: false
    property bool _timedOut: false
    property string _lastError: ""
    property bool _errorFromWrite: false
    property int _runs: 0

    Component.onCompleted: refresh()

    function refresh(): void {
        if (_queue.some(j => j.kind === "status")) return
        enqueue("status", [tool, "status"], "")
    }

    function add(bind: var, replace: bool): void {
        if (!validBind(bind)) { console.warn("KeybindStore.add: ignored " + JSON.stringify(bind)); return }
        enqueueWrite(["add"].concat(replace === true ? ["--replace"] : [], ["--json", "-"]), JSON.stringify(bind))
    }

    function update(id: string, bind: var, replace: bool): void {
        if (!validId(id)) { console.warn("KeybindStore.update: ignored bad id " + JSON.stringify(id)); return }
        if (!validBind(bind)) { console.warn("KeybindStore.update: ignored " + JSON.stringify(bind)); return }
        enqueueWrite(["set", id].concat(replace === true ? ["--replace"] : [], ["--json", "-"]), JSON.stringify(bind))
    }

    function remove(id: string): void {
        if (!validId(id)) { console.warn("KeybindStore.remove: ignored bad id " + JSON.stringify(id)); return }
        enqueueWrite(["remove", id], "")
    }

    function setEnabled(id: string, on: bool, replace: bool): void {
        if (!validId(id)) { console.warn("KeybindStore.setEnabled: ignored bad id " + JSON.stringify(id)); return }
        if (on === true) enqueueWrite(["enable", id].concat(replace === true ? ["--replace"] : []), "")
        else enqueueWrite(["disable", id], "")
    }

    function restore(id: string, replace: bool): void {
        if (!validId(id)) { console.warn("KeybindStore.restore: ignored bad id " + JSON.stringify(id)); return }
        enqueueWrite(["restore", id].concat(replace === true ? ["--replace"] : []), "")
    }

    function restoreAll(): void { enqueueWrite(["restore-all"], "") }

    function validId(id) { return typeof id === "string" && id !== "" && id.indexOf("\0") < 0 && !id.startsWith("-") }

    function validBind(bind) { return bind !== null && typeof bind === "object" && !Array.isArray(bind) }

    function setWatchdogMs(ms) {
        watchdogMs = (typeof ms === "number" && isFinite(ms) && ms > 0) ? Math.max(100, Math.round(ms)) : 60000
    }

    // A write run, then one refresh (not a second one when the last queued job already is a refresh).
    function enqueueWrite(args, stdin) {
        enqueue("write", [tool].concat(args), stdin)
        const last = _queue.length > 0 ? _queue[_queue.length - 1] : null
        if (last === null || last.kind !== "status") enqueue("status", [tool, "status"], "")
    }

    function enqueue(kind, args, stdin) {
        _queue = _queue.concat([{ kind: kind, args: args, stdin: stdin }])
        sync()
        pump()
    }

    function timeout() {
        if (_job === null || _timedOut) return
        _timedOut = true
        console.warn("KeybindStore: " + _job.args.slice(1).join(" ") + ": still running after " + watchdogMs + " ms, stopping it")
        proc.running = false
        killTimer.restart()
    }

    function pump() {
        if (_job !== null || _queue.length === 0) return
        const q = _queue.slice()
        _job = q.shift()
        _queue = q
        _exited = false
        _timedOut = false
        _runs++
        proc.stdinEnabled = _job.stdin !== ""
        proc.command = _job.args
        proc.running = true
        watchdog.restart()
        sync()
    }

    function finish(error, out) {
        const job = _job
        _job = null
        watchdog.stop()
        killTimer.stop()
        let err = error
        if (err === "" && job.kind === "status") err = parseStatus(out)
        if (err !== "") {
            _lastError = err
            _errorFromWrite = job.kind === "write"
            console.warn("KeybindStore: " + job.args.slice(1).join(" ") + ": " + err)
        } else if (job.kind === "write" || !_errorFromWrite) {
            _lastError = ""
            _errorFromWrite = false
        }
        sync()
        Qt.callLater(pump)
    }

    // Returns "" when the JSON was usable (and applied), else the error text. A bad reply leaves the old state alone.
    function parseStatus(text) {
        let s = null
        try { s = JSON.parse(text) } catch (e) { s = null }
        if (s === null || typeof s !== "object" || !Array.isArray(s.binds)) return "unreadable bbkos-keybinds status"
        binds = s.binds
        actions = Array.isArray(s.actions) ? s.actions : []
        conflicts = Array.isArray(s.conflicts) ? s.conflicts : []
        warnings = Array.isArray(s.warnings) ? s.warnings : []
        shipped = Array.isArray(s.shipped) ? s.shipped : []
        return ""
    }

    // `update` is the public edit function, so the status line is derived here.
    function sync() {
        const n = _queue.length + (_job !== null ? 1 : 0)
        status = _lastError !== "" ? "error: " + _lastError : (n > 0 ? "applying" : "idle")
    }

    function firstLine(text) {
        for (const line of String(text ?? "").split("\n")) if (line.trim() !== "") return line.trim()
        return ""
    }

    Timer { id: watchdog; interval: root.watchdogMs; onTriggered: root.timeout() }
    // SIGTERM was ignored: kill. Process.signal(int) is in the installed type file (quickshell-io.qmltypes).
    Timer { id: killTimer; interval: 5000; onTriggered: if (proc.running) proc.signal(9) }

    // Order (verified for SettingsStore, Quickshell 0.3.2): stdout/stderr streamFinished, then exited, then running=false.
    // A binary that cannot start gives running=false with no exited.
    Process {
        id: proc
        stdout: StdioCollector { id: outc }
        stderr: StdioCollector { id: errc }
        onStarted: {
            if (root._job !== null && root._job.stdin !== "") {
                write(root._job.stdin)
                stdinEnabled = false          // closes the pipe so the tool sees end of input
            }
        }
        onExited: (exitCode, exitStatus) => {
            root._exited = true
            const line = root.firstLine(errc.text)
            if (root._timedOut) root.finish("bbkos-keybinds timed out", "")
            else if (exitStatus !== 0) root.finish("bbkos-keybinds crashed" + (line ? ": " + line : ""), "")
            else if (exitCode !== 0) root.finish(line || "bbkos-keybinds exited with code " + exitCode, "")
            else {
                if (line) console.log("KeybindStore: bbkos-keybinds: " + line)   // warnings on success
                root.finish("", outc.text)
            }
        }
        onRunningChanged: if (!running && root._job !== null && !root._exited)
            root.finish(root._timedOut ? "bbkos-keybinds timed out" : "could not start " + root.tool, "")
    }
}
