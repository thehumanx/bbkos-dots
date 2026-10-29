pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Notifications

// The notification daemon (owns org.freedesktop.Notifications) and the history behind the bar widget and the
// notification panel. Quickshell only tracks live notifications: a Notification object is destroyed when it expires,
// is dismissed, or is closed by the app. History is therefore our own list of copies. It is capped at `cap` entries
// and saved to $XDG_STATE_HOME/quickshell/by-shell/<shell-id>/notifications.json, so a shell restart keeps it.
Singleton {
    id: root

    property alias server: server
    readonly property int count: server.trackedNotifications.values.length
    readonly property var cfg: ThemeStore.settings.notifications ?? ({})
    readonly property int cap: Math.max(20, Math.min(500, cfg.historySize ?? 100))      // notifications.historySize
    readonly property var mutedApps: Array.isArray(cfg.mutedApps) ? cfg.mutedApps : []       // notifications.mutedApps
    function isMuted(appName): bool { return mutedApps.includes(String(appName ?? "").trim()) }
    readonly property int maxText: 2000                       // characters kept per field in history: the file is rewritten on every change
    property var history: []                                  // [{ key, notifId, appName, appIcon, summary, body, urgency, time, read }]
    readonly property int unread: {
        let n = 0
        for (const e of history) if (!e.read) n++
        return n
    }

    // Do not disturb: no popup and no sound for a new notification, but it still enters the history (the panel shows it).
    // The flag is kept in the state directory so it survives a shell restart and a reboot.
    property bool dnd: false
    readonly property bool soundAllowed: !dnd                 // any notification sound must ask this (none is played today)
    function setDnd(value: bool): void {
        dnd = value
        dndStore.setText(value ? "on" : "off")
    }

    property int _nextKey: 1
    property bool _ready: false

    // The icon name a notification carries: with images supported, Quickshell hands a plain icon name over as image://icon/NAME.
    function iconOf(n): string {
        const img = String(n.image ?? "")
        return String(n.appIcon || (img.startsWith("image://icon/") ? img.slice(13) : "") || n.desktopEntry || "")
    }

    // The URL of an app icon (a theme icon name or a file path), or "" when there is none.
    function iconUrl(name: string): string {
        if (!name) return ""
        return name.startsWith("/") ? "file://" + name : Quickshell.iconPath(name, true)
    }

    function _save() {
        if (!_ready) return
        store.setText(JSON.stringify({ version: 1, entries: history }))
    }

    function _load() {
        try {
            const saved = JSON.parse(store.text())
            if (saved && Array.isArray(saved.entries)) {
                const out = []
                let next = 1
                for (const raw of saved.entries) {
                    if (!raw || typeof raw !== "object") continue
                    const appName = typeof raw.appName === "string" ? raw.appName : ""
                    const summary = typeof raw.summary === "string" ? raw.summary.slice(0, maxText) : ""
                    const body = typeof raw.body === "string" ? raw.body.slice(0, maxText) : ""
                    if (appName === "" && summary === "" && body === "") continue
                    const time = Number(raw.time)
                    const urgency = Number(raw.urgency)
                    let key = Number(raw.key)
                    if (!Number.isFinite(key) || key <= 0) key = next
                    next = Math.max(next, key + 1)
                    out.push({
                        key: key,
                        notifId: -1,           // the notification objects did not survive the (re)load
                        appName: appName,
                        appIcon: typeof raw.appIcon === "string" ? raw.appIcon.slice(0, 300) : "",
                        summary: summary,
                        body: body,
                        urgency: Number.isFinite(urgency) ? Math.max(0, Math.min(2, urgency)) : 1,
                        time: Number.isFinite(time) && time > 0 ? time : Date.now(),
                        read: raw.read === true
                    })
                    if (out.length >= cap) break
                }
                history = out
                _nextKey = next
            }
        } catch (e) { /* first run, or an unreadable file: start empty */ }
        _ready = true
    }

    function _record(n) {
        if (!n || n.transient || n.lastGeneration) return        // transient bypasses persistence by spec; reload re-emits
        const entry = {
            key: _nextKey++,
            notifId: n.id,
            appName: n.appName ?? "",
            appIcon: iconOf(n).slice(0, 300),     // an icon name or a file path
            summary: String(n.summary ?? "").slice(0, maxText),
            body: String(n.body ?? "").slice(0, maxText),
            urgency: n.urgency,
            time: Date.now(),
            read: false
        }
        history = [entry].concat(history).slice(0, cap)
        _save()
    }

    // Mark one history entry read (clicking a card in the panel).
    function markRead(key) {
        let changed = false
        for (const e of history) if (e.key === key && !e.read) { e.read = true; changed = true }
        if (changed) { history = history.slice(); _save() }
    }

    // A popup card was clicked: its notification is leaving the live list, but its history entry stays.
    function markLiveRead(notifId) {
        let changed = false
        for (const e of history) if (e.notifId === notifId && !e.read) { e.read = true; changed = true }
        if (changed) { history = history.slice(); _save() }
    }

    // Run the notification's "default" action (what clicking its body means in the spec), if the sender gave one.
    // Returns whether there was one. A popup click calls this before it dismisses the card.
    function invokeDefault(notifId) {
        const n = server.trackedNotifications.values.find(x => x.id === notifId)
        if (!n) return false
        const a = n.actions.find(x => x.identifier === "default")
        if (!a) return false
        a.invoke()
        return true
    }

    // A popup card was clicked (left: run the default action, right: only close it); the history entry is marked read.
    // Invoking an action already closes a non-resident notification (Quickshell's NotificationAction::invoke), so it is
    // dismissed only while still live: dismissing it again logged "Cannot close destroyed notification" (2026-10-26, -28).
    function activate(notifId, runDefault) {
        markLiveRead(notifId)
        if (runDefault) invokeDefault(notifId)
        const n = server.trackedNotifications.values.find(x => x.id === notifId)
        if (n) n.dismiss()
    }

    // "Mark all read": clears the badge for the whole history; the entries themselves stay.
    function markAllRead() {
        let changed = false
        for (const e of history) if (!e.read) { e.read = true; changed = true }
        if (changed) { history = history.slice(); _save() }
    }

    // Remove one entry. If its notification is still live, dismiss that too so the popup goes with it.
    function remove(key) {
        const e = history.find(x => x.key === key)
        if (!e) return
        if (e.notifId >= 0) {
            const live = server.trackedNotifications.values.find(n => n.id === e.notifId)
            if (live) live.dismiss()
        }
        history = history.filter(x => x.key !== key)
        _save()
    }

    // Remove the whole history. Live popups are left alone; they are not history.
    function clearAll() {
        if (history.length === 0) return
        history = []
        _save()
    }

    FileView {
        id: store
        path: Quickshell.statePath("notifications.json")
        blockLoading: true
        atomicWrites: true
        printErrors: false                 // a missing file on first run is normal; _load() starts empty
        onLoaded: if (!root._ready) root._load()
        onLoadFailed: if (!root._ready) root._load()
    }

    FileView {
        id: dndStore
        path: Quickshell.statePath("dnd")
        blockLoading: true
        printErrors: false
        onLoaded: root.dnd = text().trim() === "on"
    }

    Component.onCompleted: if (!_ready) _load()

    NotificationServer {
        id: server
        // History keeps non-transient notifications after the popup goes away, so the capability is now true.
        persistenceSupported: true
        bodySupported: true
        bodyMarkupSupported: false     // plain text: no arbitrary markup from apps
        actionsSupported: true         // the sender's "default" action runs when its popup is clicked (screenshot: edit)
        imageSupported: true           // a thumbnail on the popup (the screenshot)
        onNotification: n => {
            if (root.isMuted(n.appName)) return        // muted app: not tracked, so no popup, and no history entry
            n.tracked = true
            root._record(n)
            if (root.dnd) n.expire()           // no popup will show it, and the popup's timer is what expires a live one
        }
    }
}
