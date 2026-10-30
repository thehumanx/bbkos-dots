pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// State of the settings app. `bbkos-theme` is the only writer of settings.json: this store never writes the file, it
// queues `bbkos-theme set -- KEY VALUE` / `reset [SECTION]` runs and reads the result back through ThemeStore (which
// watches the file). Contract (docs/modules/settings-app.md):
// - set(key, value): debounced 150 ms, latest value per key wins; one tool process at a time, requests run in order;
//   a newer set of a key drops an older queued set of the same key.
// - status: "applying" while anything is pending, queued or running; "idle" when drained; "error: <first stderr line>"
//   after a non-zero exit, kept until the next successful run (the queue carries on).
// - setWallpaper(path) / clearWallpaper(): `bbkos-theme wallpaper set -- PATH` / `wallpaper clear` through the same
//   queue (key "wallpaper"); a newer wallpaper request replaces an older QUEUED one (never the running one).
// - Watchdog: a run still going after watchdogMs (60 s) is stopped (SIGTERM through running = false, SIGKILL 5 s later)
//   and ends as "error: bbkos-theme timed out"; the queue carries on once the process has gone.
// - Odd input (null, NaN, undefined, objects, bad keys) is ignored with a log line; nothing here throws.
// - Window open: the settings are snapshotted, and the wallpaper COPY (ThemeStore.wallpaperPath) is copied to
//   $XDG_RUNTIME_DIR/bbkos-settings/open.<ext> (snapshotWallpaper = that path, "" = none at open, undefined = not
//   available: failed or still copying). Window close deletes it. revertToOpen() restores the wallpaper through the
//   same queue when it differs. The helper steps (mkdir/cp/cmp/rm) run one at a time in their own Process, never a shell.
Singleton {
    id: root

    readonly property var values: ThemeStore.settings
    property string status: "idle"
    property bool windowOpen: false
    property var snapshot: ({})

    // Test hooks (read-only for consumers): requests not finished yet, and tool runs started since the shell loaded.
    readonly property int queued: _queued
    readonly property int runs: _runs
    // True while a wallpaper job is queued or running (the wallpaper page shows "Applying...").
    property bool wallpaperBusy: false
    // Watchdog interval for one tool run (ms). Test hook (IPC `settings watchdogMs`) lowers it for the session.
    property int watchdogMs: 60000
    // Test hook, written by the open wallpaper page: images it lists (-1 when that page is not shown).
    property int imageCount: -1
    // Test hook (IPC `settings refreshFolder`): asks the open wallpaper page to re-read its image folder.
    signal folderRefreshRequested()
    // Asks the open window to show a place: "page" or "page/tab" (modules/settings/Pages.js).
    signal pageRequested(string place)
    // The place the window shows ("bbkos/stage"), "" while it is closed. Written by the window; test hook `settings where`.
    property string place: ""
    // The label of a row the open page should scroll to and light up once (a search hit); the page clears it.
    property string reveal: ""
    signal searchRequested(string text)
    signal searchPickRequested()                      // test hook: Enter in the search box (qs ipc call settings pick)               // test hook: types into the sidebar search box (qs ipc call settings search TEXT)

    readonly property string tool: (Quickshell.env("HOME") ?? "") + "/.local/bin/bbkos-theme"
    // Every section of settings.json (the tool writes them all), so a new section needs no change here. Until 2026-10-28 this
    // was a fixed list of 9 that had fallen behind: resets of the other 18 sections were ignored and Revert skipped them.
    readonly property var sections: Object.keys(values ?? {}).filter(k => values[k] !== null && typeof values[k] === "object" && !Array.isArray(values[k]))
    // The built-in defaults and the values grid mode puts in place of the owner's (`bbkos-theme defaults`), read once when
    // the window first opens; {} until then.
    property var defaults: ({})
    property var gridOverrides: ({})
    property var gridRoundOff: ({})       // the corner radii grid mode also squares unless shell.gridRoundControls is on

    property int _queued: 0
    property int _runs: 0
    property var _pending: ({})      // key -> text, waiting for the debounce
    property var _queue: []          // [{ key, args }] (key "" for a reset)
    property var _job: null          // the job whose process is running
    property bool _exited: false
    property string _lastError: ""
    property bool _timedOut: false   // the running job was stopped by the watchdog
    // key -> requested value (typed) until its run ends, so a control can show what was asked for (see shown()).
    property var _intent: ({})

    // Wallpaper snapshot (see header). snapshotState: "none" (window closed), "pending", "ready", "failed".
    property var snapshotWallpaper: undefined
    property string snapshotState: "none"
    property int _snapGen: 0
    // "" (snapshot disabled) unless XDG_RUNTIME_DIR is a usable absolute path: nothing below ever runs rm/mkdir/cp then.
    readonly property string _snapDir: snapDirFor(Quickshell.env("XDG_RUNTIME_DIR"))
    readonly property var _snapExts: ["png", "jpg", "jpeg", "webp", "bmp", "gif"]   // wallpaper.py EXTENSIONS
    property var _aux: []            // [{ args, done(code) }] helper steps, one at a time
    property var _auxJob: null
    property bool _auxExited: false

    onWindowOpenChanged: {
        if (windowOpen) { snapshot = copy(values); beginSnapshot(); if (Object.keys(defaults).length === 0) defaultsProc.running = true }
        else { endSnapshot(); place = "" }
    }

    function toggleWindow(): void { windowOpen = !windowOpen }
    // Open the window at `place` ("page" or "page/tab", Pages.js; the bbkOS menu's settings entries, `settings page`).
    // A window that is not built yet reads startPage when it is created; an open one gets pageRequested.
    property string startPage: ""
    function openPage(place: string): void {
        if (windowOpen) { pageRequested(place); return }
        startPage = place
        windowOpen = true
    }

    function copy(v) {
        try { return JSON.parse(JSON.stringify(v ?? {})) } catch (e) { return {} }
    }

    // Dotted lookup in `values` ("windows.rounding"); undefined when missing. Binding-safe (reads `values`).
    function get(key: string): var {
        if (typeof key !== "string" || key === "") return undefined
        let v = values
        for (const part of key.split(".")) {
            if (v === null || typeof v !== "object" || !(part in v)) return undefined
            v = v[part]
        }
        return v
    }

    // What a control should show: the value last requested for `key` while its run is pending, else get(key), else (a
    // shell key missing from an older settings.json) the value the shell is using, which is the built-in default; any other
    // key missing from the file shows its built-in default once `defaults` is loaded (a key added later, power.chargeMode).
    function shown(key: string): var {
        if (typeof key === "string" && key in _intent) return _intent[key]
        const v = get(key)
        if (v === undefined && typeof key === "string" && key.startsWith("shell.")) return ThemeStore.shell[key.slice(6)]
        return v === undefined ? defaultOf(key) : v
    }

    // Text sent to the tool, or null for a value that cannot be sent.
    function format(value) {
        if (typeof value === "boolean") return value ? "true" : "false"
        if (typeof value === "number") return isFinite(value) ? String(value) : null
        if (typeof value === "string") return value
        if (Array.isArray(value) && value.every(v => typeof v === "string")) return value.join(",")   // bar.layout
        return null
    }

    function validKey(key) { return typeof key === "string" && /^[a-z]+\.[A-Za-z0-9]+$/.test(key) }

    function set(key: string, value: var): void {
        if (!validKey(key)) { console.warn("SettingsStore.set: ignored bad key " + JSON.stringify(key)); return }
        const text = format(value)
        if (text === null) { console.warn("SettingsStore.set: ignored value " + String(value) + " for " + key); return }
        // Nothing to do: same as the file and nothing for this key in flight.
        const busyKey = (key in _pending) || _queue.some(j => j.key === key) || (_job !== null && _job.key === key)
        if (!busyKey && format(get(key)) === text) return
        _pending[key] = text
        const i = Object.assign({}, _intent); i[key] = value; _intent = i
        debounce.restart()
        update()
    }

    // The built-in default of `key` (dotted), undefined when it is not known (yet).
    function defaultOf(key: string): var {
        let v = defaults
        for (const part of String(key).split(".")) {
            if (v === null || typeof v !== "object" || !(part in v)) return undefined
            v = v[part]
        }
        return v
    }
    // True when `key` shows a value other than its default (false while the defaults are not known, or for values the
    // tool takes no text for, such as the per-app lists).
    function modified(key: string): bool {
        const d = format(defaultOf(key))
        const v = format(shown(key))
        return d !== null && v !== null && d !== v
    }

    // The value grid mode puts in place of `key` (settings.py GRID_OVERRIDES, plus GRID_ROUND_OFF unless the controls stay round), undefined when it leaves the key alone.
    function gridValue(key: string): var {
        if (typeof key !== "string") return undefined
        const [section, name] = key.split(".")
        // The gap between tiled windows follows the margin around them: settings.py grid_gaps_in(), same arithmetic.
        if (key === "windows.gapsIn") return Math.floor((Number(shown("windows.gapsOut")) + 1) / 2)
        // The stage rail's padding and tile gap are the same margin (settings.py grid_rail_gap(), capped at 32).
        if (key === "stage.railPadding" || key === "stage.cardGap") return Math.min(32, Number(shown("windows.gapsOut")))
        if (key === "stage.cardRadius") return Number(shown("windows.rounding"))      // the rail's tiles and cards are rounded like the windows
        const o = gridOverrides[section]
        if (o !== undefined && o !== null && name in o) return o[name]
        const r = gridRoundOff[section]
        if (shown("shell.gridRoundControls") !== true && r !== undefined && r !== null && name in r) return r[name]
        return undefined
    }

    // True while grid mode is on and replaces `key`: the row shows that instead of a control.
    function gridLocked(key: string): bool {
        return shown("shell.gridMode") === true && gridValue(key) !== undefined
    }

    // reset(""): everything; reset("idle"): one section; reset("windows.rounding"): one key.
    function reset(target: string): void { resetMany(target === "" ? [] : [target]) }

    // One tool run for all of `targets` (sections and keys); [] resets everything. Unknown targets are dropped with a log line.
    function resetMany(targets): void {
        const list = (Array.isArray(targets) ? targets : []).filter(t => {
            const ok = typeof t === "string" && (sections.includes(t) || (validKey(t) && sections.includes(t.split(".")[0])))
            if (!ok) console.warn("SettingsStore.reset: ignored unknown section or key " + JSON.stringify(t))
            return ok
        })
        if (Array.isArray(targets) && targets.length > 0 && list.length === 0) return
        flush()                                       // earlier sets run first: order of requests is kept
        _queue.push({ key: "", args: [tool, "reset"].concat(list) })
        update()
        pump()
    }

    // Wallpaper changes cannot go through set() (the tool rejects `set wallpaper.path`). Odd input is ignored.
    function setWallpaper(path: string): void {
        if (typeof path !== "string" || !path.startsWith("/") || path.length < 2 || path.indexOf("\0") >= 0) {
            console.warn("SettingsStore.setWallpaper: ignored non-absolute path " + JSON.stringify(path)); return
        }
        enqueueWallpaper([tool, "wallpaper", "set", "--", path])
    }

    function clearWallpaper(): void { enqueueWallpaper([tool, "wallpaper", "clear"]) }

    // The lock screen avatar (2026-10-28): `bbkos-theme avatar set -- PATH` copies the image and sets lock.avatar, `avatar
    // clear` goes back to the shipped picture. Same queue; a newer request replaces an older queued one.
    function setAvatar(path: string): void {
        if (typeof path !== "string" || !path.startsWith("/") || path.length < 2 || path.indexOf("\0") >= 0) {
            console.warn("SettingsStore.setAvatar: ignored non-absolute path " + JSON.stringify(path)); return
        }
        enqueueAvatar([tool, "avatar", "set", "--", path])
    }
    function clearAvatar(): void { enqueueAvatar([tool, "avatar", "clear"]) }
    function enqueueAvatar(args) {
        flush()
        _queue = _queue.filter(j => j.key !== "avatar")
        _queue.push({ key: "avatar", args: args })
        update()
        pump()
    }

    function enqueueWallpaper(args) {
        flush()                                       // earlier sets run first: order of requests is kept
        _queue = _queue.filter(j => j.key !== "wallpaper")
        _queue.push({ key: "wallpaper", args: args })
        update()
        pump()
    }

    function setWatchdogMs(ms) {
        watchdogMs = (typeof ms === "number" && isFinite(ms) && ms > 0) ? Math.max(100, Math.round(ms)) : 60000
    }

    // Test hook: queue `sleep SECONDS` (whole seconds, 0-120) as a run, to exercise the queue and the watchdog without
    // touching any setting. The tool path itself never changes.
    function probe(seconds) {
        const s = Math.floor(Number(seconds))
        if (!isFinite(s) || s < 0 || s > 120) { console.warn("SettingsStore.probe: ignored " + String(seconds)); return }
        flush()
        _queue.push({ key: "", args: ["sleep", String(s)] })
        update()
        pump()
    }

    function timeout() {
        if (_job === null || _timedOut) return
        _timedOut = true
        console.warn("SettingsStore: " + _job.args.join(" ") + ": still running after " + watchdogMs + " ms, stopping it")
        proc.running = false
        killTimer.restart()
    }

    function snapExt(path) {
        const m = /\.([A-Za-z0-9]+)$/.exec(String(path))
        const e = m ? m[1].toLowerCase() : ""
        return _snapExts.includes(e) ? e : ""
    }

    // Pure: the snapshot directory for an XDG_RUNTIME_DIR value, or "" when the value is unset, empty, relative,
    // "/" (or only slashes), contains NUL, a newline or a ".." segment.
    function snapDirFor(env): string {
        if (typeof env !== "string" || !env.startsWith("/") || /^\/+$/.test(env) || /[\0\n]/.test(env) || /(^|\/)\.\.(\/|$)/.test(env)) return ""
        return env.replace(/\/+$/, "") + "/bbkos-settings"
    }

    function cleanupArgs() {
        return ["rm", "-f", "--"].concat(_snapExts.map(e => _snapDir + "/open." + e))
    }

    function beginSnapshot() {
        const gen = ++_snapGen
        snapshotWallpaper = undefined
        snapshotState = "pending"
        const cur = ThemeStore.wallpaperPath
        if (_snapDir === "") {
            if (cur === "") { snapshotWallpaper = ""; snapshotState = "ready"; return }   // nothing to copy: no directory needed
            console.warn("SettingsStore: XDG_RUNTIME_DIR is not a usable absolute path; wallpaper revert disabled for this window")
            snapshotState = "disabled"; return
        }
        auxRun(cleanupArgs(), () => {})                       // leftovers of a crashed session; failure is harmless
        if (cur === "") { snapshotWallpaper = ""; snapshotState = "ready"; return }
        const ext = snapExt(cur)
        const dst = _snapDir + "/open." + ext
        const fail = why => {
            if (gen !== _snapGen) return
            console.warn("SettingsStore: wallpaper snapshot failed (" + why + "); wallpaper revert disabled for this window")
            snapshotWallpaper = undefined; snapshotState = "failed"
        }
        if (ext === "") { fail("unsupported image extension"); return }
        auxRun(["mkdir", "-p", "-m", "700", "--", _snapDir], c => {
            if (c !== 0) { fail("mkdir exit " + c); return }
            auxRun(["cp", "-f", "--", cur, dst], c2 => {
                if (c2 !== 0) { fail("cp exit " + c2); return }
                if (gen !== _snapGen) return
                snapshotWallpaper = dst; snapshotState = "ready"
            })
        })
    }

    function endSnapshot() {
        _snapGen++
        snapshotWallpaper = undefined
        snapshotState = "none"
        if (_snapDir === "") return
        auxRun(cleanupArgs(), c => { if (c !== 0) console.warn("SettingsStore: could not delete the wallpaper snapshot") })
    }

    // Queue a helper command; done(exitCode) runs when it ends (-1 when it could not start). Nothing throws.
    function auxRun(args, done) {
        _aux.push({ args: args, done: done })
        auxPump()
    }

    function auxPump() {
        if (_auxJob !== null || _aux.length === 0) return
        _auxJob = _aux.shift()
        _auxExited = false
        auxProc.command = _auxJob.args
        auxProc.running = true
    }

    function auxFinish(code) {
        const job = _auxJob
        _auxJob = null
        try { job.done(code) } catch (e) { console.warn("SettingsStore: helper callback failed: " + e) }
        Qt.callLater(auxPump)
    }

    // Wallpaper part of revertToOpen: set/clear through the queue when the current copy differs from the snapshot.
    function revertWallpaper() {
        const want = snapshotWallpaper
        if (want === undefined) {
            console.warn("SettingsStore.revertToOpen: wallpaper not reverted (snapshot " + snapshotState + ")"); return
        }
        const gen = _snapGen
        const cur = ThemeStore.wallpaperPath
        // A wallpaper job is queued or running: ThemeStore.wallpaperPath is stale until its write is read back, so do not
        // compare; queue the restore (a queued wallpaper job is replaced, a running one finishes first).
        if (wallpaperBusy) { want === "" ? clearWallpaper() : setWallpaper(want); return }
        if (want === "") { if (cur !== "") clearWallpaper(); return }
        // Same name check first (cheap), then the content: `cmp -s` compares every byte, so equal size and mtime cannot fool it.
        if (cur === "" || snapExt(cur) !== snapExt(want)) { setWallpaper(want); return }
        auxRun(["cmp", "-s", "--", cur, want], c => {
            if (gen !== _snapGen || !windowOpen) return
            if (c !== 0 || wallpaperBusy) setWallpaper(want)               // 1 differs, 2 unreadable: restore either way
        })
    }

    // Re-apply the values from when the window opened, key by key through the same queue (only keys that differ).
    // wallpaper.path is not set() but restored from the snapshot copy by revertWallpaper().
    function revertToOpen(): void {
        const snap = snapshot
        if (snap === null || typeof snap !== "object") return
        for (const section of sections) {
            const s = snap[section]
            if (s === null || typeof s !== "object") continue
            for (const k in s) {
                const key = section + "." + k
                const want = format(s[k])
                if (want === null || want === format(shown(key))) continue
                if (key === "wallpaper.path") continue
                set(key, s[k])
            }
        }
        revertWallpaper()
    }

    // Move debounced sets into the queue; a queued (not yet running) set of the same key is replaced by the newer one.
    function flush() {
        debounce.stop()
        for (const key in _pending) {
            _queue = _queue.filter(j => j.key !== key)
            _queue.push({ key: key, args: [tool, "set", "--", key, _pending[key]] })
        }
        _pending = {}
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

    function finish(error) {
        const job = _job
        _job = null
        watchdog.stop()
        killTimer.stop()
        if (error === "") _lastError = ""
        else { _lastError = error; console.warn("SettingsStore: " + job.args.slice(1).join(" ") + ": " + error) }
        // The run for this key is over; keep the intent only if a newer request for it is still waiting.
        if (job.key !== "" && job.key in _intent && !(job.key in _pending) && !_queue.some(j => j.key === job.key)) {
            const i = Object.assign({}, _intent); delete i[job.key]; _intent = i
        }
        update()
        Qt.callLater(pump)
    }

    function update() {
        _queued = Object.keys(_pending).length + _queue.length + (_job !== null ? 1 : 0)
        wallpaperBusy = (_job !== null && _job.key === "wallpaper") || _queue.some(j => j.key === "wallpaper")
        status = _lastError !== "" ? "error: " + _lastError : (_queued > 0 ? "applying" : "idle")
    }

    function firstLine(text) {
        for (const line of String(text ?? "").split("\n")) if (line.trim() !== "") return line.trim()
        return ""
    }

    Process {
        id: auxProc
        onExited: (exitCode, exitStatus) => { root._auxExited = true; root.auxFinish(exitStatus !== 0 ? -1 : exitCode) }
        onRunningChanged: if (!running && root._auxJob !== null && !root._auxExited) root.auxFinish(-1)
    }

    Process {
        id: defaultsProc
        command: [root.tool, "defaults"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const doc = JSON.parse(text)
                    root.defaults = doc.defaults ?? {}
                    root.gridOverrides = doc.gridMode ?? {}
                    root.gridRoundOff = doc.gridRoundOff ?? {}
                } catch (e) { console.warn("SettingsStore: cannot read the defaults: " + e) }
            }
        }
    }

    Timer { id: debounce; interval: 150; onTriggered: root.flush() }
    Timer { id: watchdog; interval: root.watchdogMs; onTriggered: root.timeout() }
    // SIGTERM was ignored: kill. Process.signal(int) is in the installed type file (quickshell-io.qmltypes).
    Timer { id: killTimer; interval: 5000; onTriggered: if (proc.running) proc.signal(9) }

    // Verified order (probe, Quickshell 0.3.2): stderr streamFinished, then exited(code, status), then running=false.
    // A binary that cannot start gives running=false with no exited.
    Process {
        id: proc
        stderr: StdioCollector { id: err }
        onExited: (exitCode, exitStatus) => {
            root._exited = true
            const line = root.firstLine(err.text)
            if (root._timedOut) root.finish("bbkos-theme timed out")
            else if (exitStatus !== 0) root.finish("bbkos-theme crashed" + (line ? ": " + line : ""))
            else if (exitCode !== 0) root.finish(line || "bbkos-theme exited with code " + exitCode)
            else {
                if (line) console.log("SettingsStore: bbkos-theme: " + line)   // warnings on success
                root.finish("")
            }
        }
        onRunningChanged: if (!running && root._job !== null && !root._exited)
            root.finish(root._timedOut ? "bbkos-theme timed out" : "could not start " + root.tool)
    }
}
