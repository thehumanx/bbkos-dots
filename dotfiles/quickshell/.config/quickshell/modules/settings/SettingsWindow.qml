import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.services
import "Pages.js" as Pages

// bbkOS settings window. Exists only while SettingsStore.windowOpen (LazyLoader), so there is never more than one.
// Hyprland tiles it by class "org.quickshell" + title "bbkOS Settings" (hyprland.lua; floating 1120x720 until 2026-10-28).
// Every route that closes it ends with windowOpen false: `settings toggle`, the bar gear and Super+, flip the flag;
// a compositor close (Super+C) emits FloatingWindow.closed, handled below.
// The pages and their tabs are Pages.js; a place is "page" or "page/tab". The header (title, tabs) stays put while the page
// under it scrolls, and both are centred at most `maxContent` wide so rows stay readable in a wide tile.
Scope {
    Component.onCompleted: LogindApply.init()           // so a CLI edit of session.* is applied to logind too, whether or not the page is open

    IpcHandler {
        target: "settings"
        function toggle(): void { SettingsStore.toggleWindow() }
        function search(text: string): void { SettingsStore.searchRequested(text) }
        function pick(): void { SettingsStore.searchPickRequested() }                       // test hook: Enter in the search box
        function status(): string {         // test hook; `runs` counts tool runs since the shell loaded
            return JSON.stringify({ open: SettingsStore.windowOpen, status: SettingsStore.status,
                                    queued: SettingsStore.queued, runs: SettingsStore.runs,
                                    wallpaperBusy: SettingsStore.wallpaperBusy, images: SettingsStore.imageCount,
                                    watchdogMs: SettingsStore.watchdogMs })
        }
        // Test hook: what a control for `key` shows (SettingsStore.shown), as JSON; null when nothing is known yet.
        function shown(key: string): string { return JSON.stringify(SettingsStore.shown(key) ?? null) }
        // Test hook: the value is parsed like a control would send it (true/false, number, else text).
        function set(key: string, value: string): void {
            const v = value === "true" ? true : value === "false" ? false
                    : /^-?(\d+(\.\d*)?|\.\d+)$/.test(value) ? Number(value) : value
            SettingsStore.set(key, v)
        }
        function reset(section: string): void { SettingsStore.reset(section) }   // "" resets everything
        function wallpaper(path: string): void { SettingsStore.setWallpaper(path) }       // absolute path
        function refreshFolder(): void { SettingsStore.folderRefreshRequested() }          // test hook
        function clearWallpaper(): void { SettingsStore.clearWallpaper() }
        function revert(): void { SettingsStore.revertToOpen() }
        function page(place: string): void { SettingsStore.openPage(place) }              // "windows" or "windows/stage"
        function where(): string { return SettingsStore.place }                            // test hook: the place shown
        function snapDirFor(env: string): string { return SettingsStore.snapDirFor(env) }  // test hook: the pure path guard
        // Test hook: the wallpaper snapshot taken at window open (state: none = window closed, pending, ready, failed,
        // disabled = XDG_RUNTIME_DIR unusable).
        function snapshotInfo(): string {
            return JSON.stringify({ wallpaper: SettingsStore.snapshotWallpaper ?? "", state: SettingsStore.snapshotState })
        }
        // Test hooks for the watchdog: set its interval for this session (<= 0 restores 60000; returns the value in use),
        // and queue `sleep SECONDS` (0-120) as a stand-in run through the same queue, Process and watchdog.
        function watchdogMs(ms: int): string { SettingsStore.setWatchdogMs(ms); return String(SettingsStore.watchdogMs) }
        function probe(seconds: int): void { SettingsStore.probe(seconds) }
    }

    IpcHandler {                                         // test hook for the keybindings store (docs/modules/keybindings.md)
        target: "keybinds"
        function status(): string {
            return JSON.stringify({ status: KeybindStore.status, binds: KeybindStore.binds.length })
        }
    }

    LazyLoader {
        active: SettingsStore.windowOpen

        FloatingWindow {
            id: win
            property string page: "appearance"
            property var tabOf: ({})                 // page id -> tab index last shown (this window only)
            readonly property var entry: Pages.find(page) ?? Pages.PAGES[0]
            readonly property int tab: Math.min(tabOf[page] ?? 0, entry.tabs.length - 1)
            readonly property int maxContent: 960

            function go(place) {
                const r = Pages.resolve(place)
                if (r === null) { console.warn("settings: unknown page " + JSON.stringify(place)); return }
                const t = Object.assign({}, tabOf)
                if (String(place).indexOf("/") >= 0 || !(r.page in t)) t[r.page] = r.tab
                tabOf = t
                page = r.page
            }
            Component.onCompleted: if (SettingsStore.startPage !== "") { go(SettingsStore.startPage); SettingsStore.startPage = "" }
            Binding { target: SettingsStore; property: "place"; value: win.page + "/" + (win.entry.tabs[win.tab]?.id ?? ""); restoreMode: Binding.RestoreNone }

            title: "bbkOS Settings"
            implicitWidth: 1120
            implicitHeight: 720
            // Narrowest width at which a slider row keeps a usable slider: sidebar 248 + page margins 64 +
            // card margins 40 + label 260 + stepper (2x30 buttons, 52 value, gaps) 190 + two row gaps 32 + slider 100.
            minimumSize: Qt.size(960, 480)
            color: Theme.bg

            onClosed: SettingsStore.windowOpen = false                       // compositor close (Super+C)
            onVisibleChanged: if (!visible) SettingsStore.windowOpen = false

            Connections {
                target: SettingsStore
                function onPageRequested(place) { win.go(place) }
                function onSearchRequested(text) { sidebar.setSearch(text) }
                function onSearchPickRequested() { sidebar.pickFirst() }
            }

            Shortcut { sequence: "Escape"; onActivated: SettingsStore.windowOpen = false }

            RowLayout {
                anchors.fill: parent
                spacing: 0

                Sidebar {
                    id: sidebar
                    Layout.preferredWidth: 248
                    Layout.fillHeight: true
                    pages: Pages.PAGES
                    groups: Pages.GROUPS
                    current: win.page
                    onPicked: (place, reveal) => { win.go(place); SettingsStore.reveal = reveal }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors { top: parent.top; bottom: parent.bottom; horizontalCenter: parent.horizontalCenter }
                        anchors.topMargin: 24
                        anchors.bottomMargin: 12
                        width: Math.min(parent.width - 64, win.maxContent)
                        spacing: 8

                        Txt { text: win.entry.label; font.bold: true; font.pixelSize: Theme.fontSize + 9; Layout.preferredHeight: 36 }
                        Tabs {
                            visible: win.entry.tabs.length > 1
                            model: win.entry.tabs.map(t => t.label)
                            current: win.tab
                            onPicked: i => { const t = Object.assign({}, win.tabOf); t[win.page] = i; win.tabOf = t }
                            Layout.bottomMargin: 8
                        }

                        Loader {
                            id: pageLoader
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            sourceComponent: win.components[win.entry.tabs[win.tab]?.page] ?? null      // ?.: tab can lag the page by one update
                        }

                        Txt {
                            readonly property bool failed: SettingsStore.status.startsWith("error: ")
                            text: failed ? SettingsStore.status.slice(7) : SettingsStore.status === "applying" ? "Applying..." : ""
                            color: failed ? Theme.crit : Theme.dim
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            Layout.preferredHeight: 20
                        }
                    }
                }
            }

            Rectangle {                                                      // close button, top right
                width: 32; height: 32
                anchors { top: parent.top; right: parent.right; topMargin: 12; rightMargin: 12 }
                radius: Theme.controlRadius
                color: closeArea.containsMouse ? Theme.control : "transparent"
                scale: closeArea.pressed ? 0.97 : 1
                Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
                Txt { anchors.centerIn: parent; text: "\uf00d"; color: closeArea.containsMouse ? Theme.fg : Theme.dim }
                MouseArea { id: closeArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: SettingsStore.windowOpen = false }
            }

            // Pages.js names each tab's page; one Component per Page*.qml, loaded only while its tab is shown.
            readonly property var components: ({
                PageWallpaper: cPageWallpaper,
                PageShell: cPageShell,
                PageTerminal: cPageTerminal,
                PageBarLayout: cPageBarLayout,
                PageBarLook: cPageBarLook,
                PageBarWidgets: cPageBarWidgets,
                PageWindows: cPageWindows,
                PageBehavior: cPageBehavior,
                PageStage: cPageStage,
                PageLock: cPageLock,
                PageNotifications: cPageNotifications,
                PageApps: cPageApps,
                PageStartup: cPageStartup,
                PageLauncher: cPageLauncher,
                PageCapture: cPageCapture,
                PageCamera: cPageCamera,
                PagePrivacy: cPagePrivacy,
                PageNetwork: cPageNetwork,
                PageDisplays: cPageDisplays,
                PageSound: cPageSound,
                PageIdle: cPageIdle,
                PageLidPower: cPageLidPower,
                PagePower: cPagePower,
                PageKeyboard: cPageKeyboard,
                PageKeybindings: cPageKeybindings,
                PageDictation: cPageDictation,
                PageMouse: cPageMouse,
                PageTouchpad: cPageTouchpad,
                PageGestures: cPageGestures,
                PageAccessibility: cPageAccessibility,
                PageAbout: cPageAbout,
                PageReset: cPageReset
            })
            Component { id: cPageWallpaper; PageWallpaper {} }
            Component { id: cPageShell; PageShell {} }
            Component { id: cPageTerminal; PageTerminal {} }
            Component { id: cPageBarLayout; PageBarLayout {} }
            Component { id: cPageBarLook; PageBarLook {} }
            Component { id: cPageBarWidgets; PageBarWidgets {} }
            Component { id: cPageWindows; PageWindows {} }
            Component { id: cPageBehavior; PageBehavior {} }
            Component { id: cPageStage; PageStage {} }
            Component { id: cPageLock; PageLock {} }
            Component { id: cPageNotifications; PageNotifications {} }
            Component { id: cPageApps; PageApps {} }
            Component { id: cPageStartup; PageStartup {} }
            Component { id: cPageLauncher; PageLauncher {} }
            Component { id: cPageCapture; PageCapture {} }
            Component { id: cPageCamera; PageCamera {} }
            Component { id: cPagePrivacy; PagePrivacy {} }
            Component { id: cPageNetwork; PageNetwork {} }
            Component { id: cPageDisplays; PageDisplays {} }
            Component { id: cPageSound; PageSound {} }
            Component { id: cPageIdle; PageIdle {} }
            Component { id: cPageLidPower; PageLidPower {} }
            Component { id: cPagePower; PagePower {} }
            Component { id: cPageKeyboard; PageKeyboard {} }
            Component { id: cPageKeybindings; PageKeybindings {} }
            Component { id: cPageDictation; PageDictation {} }
            Component { id: cPageMouse; PageMouse {} }
            Component { id: cPageTouchpad; PageTouchpad {} }
            Component { id: cPageGestures; PageGestures {} }
            Component { id: cPageAccessibility; PageAccessibility {} }
            Component { id: cPageAbout; PageAbout {} }
            Component { id: cPageReset; PageReset {} }
        }
    }
}
