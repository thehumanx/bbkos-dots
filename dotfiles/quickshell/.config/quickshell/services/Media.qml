pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Services.Mpris

// The song for the bar's music widget (modules/bar/MediaWidget.qml, docs/modules/media.md): the first MPRIS player that is
// playing, else the first one that is paused on a track, so the widget stays (dimmed) and play can be pressed. It goes when
// the player does.
Singleton {
    id: root

    readonly property var player: Mpris.players.values.find(p => p.isPlaying)
        ?? Mpris.players.values.find(p => p.playbackState === MprisPlaybackState.Paused && (p.trackTitle ?? "") !== "") ?? null
    readonly property bool present: player !== null
    readonly property bool playing: player !== null && player.isPlaying
    readonly property string title: player ? (player.trackTitle ?? "") : ""
    readonly property string artist: player ? (player.trackArtist ?? "") : ""

    IpcHandler {                                         // test hooks: what the widget shows, and what a click on it does
        target: "media"
        function status(): string {
            return JSON.stringify({ present: root.present, playing: root.playing, title: root.title, artist: root.artist,
                                    desktopEntry: root.player ? root.player.desktopEntry : "", identity: root.player ? root.player.identity : "",
                                    window: root.windowAddress() })
        }
        function open(): void { root.open() }
    }

    function toggle(): void { if (player && player.canTogglePlaying) player.togglePlaying() }
    function next(): void { if (player && player.canGoNext) player.next() }
    function previous(): void { if (player && player.canGoPrevious) player.previous() }

    // The window that is playing, as a Hyprland address ("" when there is none): a window whose class is the player's desktop
    // entry (or its name), the one titled with the song first, else the most recently used. The tab is not looked for.
    function windowAddress(): string {
        if (!player) return ""
        const id = String(player.desktopEntry ?? "").toLowerCase().replace(/\.desktop$/, "")
        const name = String(player.identity ?? "").toLowerCase()
        const song = title.toLowerCase()
        let best = null, bestScore = -1
        for (const t of Hyprland.toplevels.values) {
            const ipc = t.lastIpcObject
            if (!ipc || ipc.mapped === false) continue
            const cls = String(ipc["class"] ?? "").toLowerCase()
            if (cls === "") continue
            let score = -1
            if (id !== "" && cls === id) score = 2
            else if ((id !== "" && cls.indexOf(id) >= 0) || (name !== "" && cls.indexOf(name) >= 0)) score = 1
            if (score < 0) continue
            if (song !== "" && String(t.title ?? ipc.title ?? "").toLowerCase().indexOf(song) >= 0) score += 4
            score -= 0.001 * (Number(ipc.focusHistoryID) || 0)
            if (score > bestScore) { best = ipc; bestScore = score }
        }
        const a = best ? String(best.address ?? "") : ""
        return /^0x[0-9a-f]{1,16}$/.test(a) ? a : ""
    }

    // Open the app the song plays in: focus its window (switching workspace if it is elsewhere), else ask the player to raise
    // itself, else start its desktop entry. The pointer stays where it is (no_warps for this one focus, as the stage rail does).
    function open(): void {
        if (!player) return
        const a = windowAddress()
        if (a !== "") {
            Quickshell.execDetached(["hyprctl", "eval",
                "local nw = hl.get_config('cursor.no_warps'); hl.config({cursor={no_warps=true}}); "
                + "hl.dispatch(hl.dsp.focus({window='address:" + a + "'})); hl.config({cursor={no_warps=nw}})"])
        } else if (player.canRaise) {
            player.raise()
        } else {
            const e = DesktopEntries.byId(String(player.desktopEntry ?? ""))
            if (e) e.execute()
        }
    }
}
