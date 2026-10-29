pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Display state and control. `bbkos-display` is the only writer of displays.json and the monitor rules; this service
// runs it (and brightnessctl) one process at a time, in request order, and reads the result back with `status`.
// Contract (docs/modules/displays.md):
// - refresh(): `bbkos-display status` -> monitors, layout, pending. Nothing polls; the panel calls it when it opens.
// - setScale / setMode / setLayout: run the tool, then refresh. A change starts the keep prompt: keepSeconds counts
//   down from keepWindow (15 s) and reaches revert() unless keep() is called first. The countdown belongs to this
//   singleton, not to the panel, so closing the panel does not cancel the safety revert.
// - brightness: per monitor (name -> 0-100). `bbkos-display brightness NAME [PERCENT]` does the work: the laptop
//   panel through brightnessctl (percent 1 = the lowest step, evenly spaced in perceived brightness, see brightness.py), an external monitor through DDC/CI
//   (ddcutil). Its own queue, so a slow DDC call never blocks scale or layout changes. setBrightness() queues at once (the newest waiting change wins, so a drag is throttled to one write at a time);
//   stepBrightness() on the laptop panel runs bbkos-brightness (which also shows the OSD).
// - status: "applying" while anything is queued or running, "idle", or "error: <first stderr line>" after a failed run
//   (kept until the next successful run; the queue carries on).
// - Watchdog: a run still going after watchdogMs (30 s) is stopped (SIGTERM, SIGKILL 5 s later) and ends as an error.
Singleton {
    id: root

    property var monitors: []            // bbkos-display status "monitors"
    property var layout: null            // { mode, position, primary } with two monitors, else null
    property bool pending: false         // a change has not been kept or reverted yet
    property var brightness: ({})        // monitor name -> 0-100; absent until read
    // A brightness the user set (the Display popup, the widget's wheel on an external monitor): the OSD shows it, as it
    // shows every volume change. Not emitted for re-reads, so opening the popup does not flash the OSD. The brightness
    // keys show the OSD themselves (bbkos-brightness -> osd brightnessOn).
    signal brightnessSet(string name, int percent)
    property var brightnessError: ({})   // monitor name -> first error line of its last failed run
    property string status: "idle"
    property int keepSeconds: 0          // seconds left to keep the last change, 0 = no countdown running
    readonly property int keepWindow: 15
    property int watchdogMs: 30000
    readonly property int runs: _runs    // test hook: process runs since the shell loaded

    readonly property string home: Quickshell.env("HOME") ?? ""
    readonly property string tool: home + "/.local/bin/bbkos-display"
    readonly property string brightnessTool: home + "/.local/bin/bbkos-brightness"

    property var _queue: []              // [{ kind, args, after(stdoutText) }]
    property var _job: null
    property bool _exited: false
    property bool _timedOut: false
    property string _lastError: ""
    property int _runs: 0
    property var _bQueue: []             // [{ name, kind: "get"|"set", args }]
    property var _bJob: null
    property bool _bExited: false
    property bool _bTimedOut: false

    Component.onCompleted: refresh()

    function refresh(): void {
        if (_queue.some(j => j.kind === "status")) return
        enqueue("status", [tool, "status"], text => parseStatus(text))
    }

    function kindOf(name: string): var {
        const m = monitors.find(x => x.name === name)
        return m ? (m.brightness ?? null) : null
    }

    // The laptop panel's name (the monitor with a backlight); "" until the first status has arrived.
    function internalName(): string {
        const m = monitors.find(x => x.brightness === "backlight")
        return m ? m.name : ""
    }

    // -1 while unknown.
    function brightnessOf(name: string): int {
        const v = brightness[name]
        return v === undefined ? -1 : v
    }

    // "" means the laptop panel (the brightness keys do not know its name).
    function refreshBrightness(name: string): void {
        const n = name === "" ? internalName() : name
        if (n === "" || kindOf(n) === null) return
        bEnqueue({ name: n, kind: "get", args: [tool, "brightness", n] })
    }

    function refreshAllBrightness(): void { for (const m of monitors) refreshBrightness(m.name) }

    function setBrightness(name: string, percent: real): void {
        if (!isFinite(percent) || kindOf(name) === null) return
        const p = Math.max(0, Math.min(100, Math.round(percent)))
        const b = Object.assign({}, brightness); b[name] = p; brightness = b
        // Straight into the queue: the first change runs at once, and while one runs the newest waiting one replaces the
        // others (bEnqueue), so a drag is throttled to one write at a time (about 5 a second over DDC) without a timer.
        // Until 2026-10-29 a 150 ms debounce delayed every single press as well.
        bEnqueue({ name: name, kind: "set", args: [tool, "brightness", name, String(p)] })
        brightnessSet(name, p)
    }

    function stepBrightness(name: string, delta: real): void {
        if (!isFinite(delta) || delta === 0) return
        const n = name === "" ? internalName() : name
        const kind = kindOf(n)
        if (kind === "backlight") {
            if (_queue.filter(j => j.kind === "brightness-step").length >= 2) return    // a fast wheel must not pile up runs
            enqueue("brightness-step", [brightnessTool, delta > 0 ? "up" : "down"], () => refreshBrightness(n))
        } else if (kind === "ddc") {
            const cur = brightnessOf(n)
            setBrightness(n, (cur < 0 ? 50 : cur) + (delta > 0 ? 5 : -5))
        }
    }

    function bEnqueue(job) {
        _bQueue = _bQueue.filter(j => !(j.name === job.name && j.kind === job.kind))   // the newest of a kind wins
        _bQueue.push(job)
        bPump()
    }

    function bPump() {
        if (_bJob !== null || _bQueue.length === 0) return
        _bJob = _bQueue.shift()
        _bExited = false
        _bTimedOut = false
        bproc.command = _bJob.args
        bproc.running = true
        bWatchdog.restart()
    }

    function bFinish(error, text) {
        const job = _bJob
        _bJob = null
        bWatchdog.stop()
        bKillTimer.stop()
        const errs = Object.assign({}, brightnessError)
        if (error === "") {
            delete errs[job.name]
            try {
                const r = JSON.parse(text)
                // a re-read must not undo a change that is still waiting to be written
                const pendingSet = _bQueue.some(j => j.name === job.name && j.kind === "set")
                if (job.kind === "get" && !pendingSet && isFinite(r.percent)) {
                    const b = Object.assign({}, brightness); b[job.name] = r.percent; brightness = b
                }
            } catch (e) { console.warn("Displays: unreadable brightness output for " + job.name) }
        } else {
            errs[job.name] = error
            console.warn("Displays: brightness " + job.name + ": " + error)
        }
        brightnessError = errs
        Qt.callLater(bPump)
    }

    function bTimeout() {
        if (_bJob === null || _bTimedOut) return
        _bTimedOut = true
        console.warn("Displays: brightness " + _bJob.name + ": still running after 20 s, stopping it")
        bproc.running = false
        bKillTimer.restart()
    }

    function setScale(name: string, scale: real): void { change([tool, "set-scale", name, String(scale)]) }
    function setMode(name: string, mode: string): void { change([tool, "set-mode", name, mode]) }

    function setLayout(mode: string, primary: string, position: string): void {
        const args = [tool, "layout", mode]
        if (primary !== "") args.push("--primary", primary)
        if (position !== "") args.push("--position", position)
        change(args)
    }

    function keep(): void { resolvePending("keep") }
    function revert(): void { resolvePending("revert") }

    function resolvePending(which) {
        keepTimer.stop()
        keepSeconds = 0
        enqueue(which, [tool, which], () => refresh())
    }

    function change(args) {
        enqueue("change", args, () => {
            pending = true
            keepSeconds = keepWindow
            keepTimer.restart()
            refresh()
        })
    }

    function parseStatus(text) {
        let s = null
        try { s = JSON.parse(text) } catch (e) { s = null }
        if (s === null || typeof s !== "object" || !Array.isArray(s.monitors)) {
            _lastError = "unreadable bbkos-display status"
            console.warn("Displays: " + _lastError)
            update()
            return
        }
        monitors = s.monitors
        layout = s.layout ?? null
        pending = s.pending === true
        // Forget the brightness and error of a monitor that is gone, so a replug reads it afresh (an unplugged HDMI
        // kept its old value and "unknown monitor" error, 2026-10-28).
        const names = monitors.map(m => m.name)
        const keepOnly = obj => { const o = {}; for (const k in obj) if (names.includes(k)) o[k] = obj[k]; return o }
        if (Object.keys(brightness).some(k => !names.includes(k))) brightness = keepOnly(brightness)
        if (Object.keys(brightnessError).some(k => !names.includes(k))) brightnessError = keepOnly(brightnessError)
        for (const m of monitors) if (m.brightness && !(m.name in brightness)) refreshBrightness(m.name)
        // A change nobody answered survived a shell restart, crash or logout: its countdown died with the old shell.
        // Start a new one, so the safety revert still happens.
        if (pending && keepSeconds === 0 && !keepTimer.running) { keepSeconds = keepWindow; keepTimer.restart() }
    }

    function enqueue(kind, args, after) {
        _queue.push({ kind: kind, args: args, after: after })
        update()
        pump()
    }

    function pump() {
        if (_job !== null || _queue.length === 0) return
        _job = _queue.shift()
        _exited = false
        _timedOut = false
        _runs++
        proc.command = _job.args
        proc.running = true
        watchdog.restart()
        update()
    }

    function finish(error, text) {
        const job = _job
        _job = null
        watchdog.stop()
        killTimer.stop()
        if (error === "") _lastError = ""
        else { _lastError = error; console.warn("Displays: " + job.args.join(" ") + ": " + error) }
        if (error === "" && job.after) {
            try { job.after(text) } catch (e) { console.warn("Displays: callback failed: " + e) }
        }
        update()
        Qt.callLater(pump)
    }

    function timeout() {
        if (_job === null || _timedOut) return
        _timedOut = true
        console.warn("Displays: " + _job.args.join(" ") + ": still running after " + watchdogMs + " ms, stopping it")
        proc.running = false
        killTimer.restart()
    }

    function update() {
        const busy = _job !== null || _queue.length > 0
        status = _lastError !== "" ? "error: " + _lastError : (busy ? "applying" : "idle")
    }

    function firstLine(text) {
        for (const line of String(text ?? "").split("\n")) if (line.trim() !== "") return line.trim()
        return ""
    }

    Timer {
        id: keepTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.keepSeconds = Math.max(0, root.keepSeconds - 1)
            if (root.keepSeconds === 0) { stop(); root.revert() }
        }
    }

    Timer { id: bWatchdog; interval: 20000; onTriggered: root.bTimeout() }
    Timer { id: bKillTimer; interval: 5000; onTriggered: if (bproc.running) bproc.signal(9) }
    Timer { id: watchdog; interval: root.watchdogMs; onTriggered: root.timeout() }
    Timer { id: killTimer; interval: 5000; onTriggered: if (proc.running) proc.signal(9) }

    // Order (verified for SettingsStore, Quickshell 0.3.2): stdout/stderr streamFinished, then exited, then running=false.
    // A binary that cannot start gives running=false with no exited.
    Process {
        id: proc
        stdout: StdioCollector { id: outc }
        stderr: StdioCollector { id: errc }
        onExited: (exitCode, exitStatus) => {
            root._exited = true
            const line = root.firstLine(errc.text)
            if (root._timedOut) root.finish("timed out", "")
            else if (exitStatus !== 0) root.finish("crashed" + (line ? ": " + line : ""), "")
            else if (exitCode !== 0) root.finish(line || "exited with code " + exitCode, "")
            else root.finish("", outc.text)
        }
        onRunningChanged: if (!running && root._job !== null && !root._exited)
            root.finish(root._timedOut ? "timed out" : "could not start " + root._job.args[0], "")
    }

    // The brightness process (see proc for the exit order).
    Process {
        id: bproc
        stdout: StdioCollector { id: boutc }
        stderr: StdioCollector { id: berrc }
        onExited: (exitCode, exitStatus) => {
            root._bExited = true
            const line = root.firstLine(berrc.text)
            if (root._bTimedOut) root.bFinish("timed out", "")
            else if (exitStatus !== 0) root.bFinish("crashed" + (line ? ": " + line : ""), "")
            else if (exitCode !== 0) root.bFinish(line || "exited with code " + exitCode, "")
            else root.bFinish("", boutc.text)
        }
        onRunningChanged: if (!running && root._bJob !== null && !root._bExited)
            root.bFinish(root._bTimedOut ? "timed out" : "could not start " + root._bJob.args[0], "")
    }
}
