pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../components/Duration.js" as Duration

// The countdown timer (docs/modules/calendar.md). One timer: idle, running, paused or done. It keeps the end time as a
// wall-clock stamp, so a suspend or a late tick cannot make it drift; the tick is one single-shot timer aimed at the
// next whole second and runs only while the timer is running. Started from the calendar popup, the timer popup or IPC.
// Not kept across a shell restart.
Singleton {
    id: root

    property string state: "idle"            // idle | running | paused | done
    property real total: 0                   // ms the timer was set to (grows with +1 min)
    property real remaining: 0               // ms left, updated on every tick
    property real endMs: 0                   // Date.now() at which a running timer ends
    property int doneSerial: 0               // counts completions: the bar widget flashes on each change
    readonly property bool active: state !== "idle"
    readonly property real progress: total > 0 ? Math.min(1, Math.max(0, 1 - remaining / total)) : 0

    function start(ms: real): void {
        if (!(ms > 0)) return
        total = ms
        remaining = ms
        endMs = Date.now() + ms
        state = "running"
        schedule()
    }
    function pause(): void {
        if (state !== "running") return
        tick()
        if (state === "running") { state = "paused"; ticker.stop() }
    }
    function resume(): void {
        if (state !== "paused") return
        endMs = Date.now() + remaining
        state = "running"
        schedule()
    }
    function reset(): void {
        ticker.stop()
        state = "idle"
        total = 0
        remaining = 0
    }
    // Make it longer; on a finished or idle timer this starts a new one of that length.
    function add(ms: real): void {
        if (state === "running") { endMs += ms; total += ms; tick() }
        else if (state === "paused") { remaining += ms; total += ms }
        else start(ms)
    }

    function tick(): void {
        if (state !== "running") return
        remaining = Math.max(0, endMs - Date.now())
        if (remaining <= 0) finish()
        else schedule()
    }
    function schedule(): void {
        ticker.interval = (remaining % 1000 || 1000) + 5      // just after the display's next second
        ticker.restart()
    }
    function finish(): void {
        ticker.stop()
        remaining = 0
        state = "done"
        doneSerial++
        Quickshell.execDetached(["notify-send", "-a", "Timer", "Timer finished", Duration.format(total) + " is up."])
    }

    Timer { id: ticker; repeat: false; onTriggered: root.tick() }

    IpcHandler {                             // test hooks and scripting: qs ipc call timer start 90
        target: "timer"
        function start(seconds: int): void { root.start(seconds * 1000) }
        function pause(): void { root.pause() }
        function resume(): void { root.resume() }
        function reset(): void { root.reset() }
        function add(seconds: int): void { root.add(seconds * 1000) }
        function status(): string { return JSON.stringify({ state: root.state, total: root.total, remaining: root.remaining, doneSerial: root.doneSerial }) }
    }
}
