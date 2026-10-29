import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs
import qs.services
import "../overview/OverviewModel.js" as Model

// Stage mode (docs/modules/stage.md), per workspace: a stage workspace uses Hyprland's monocle layout (the default from
// stage.enabled via render.py, a per-workspace choice via StageState), so each window opens alone and full size. This
// rail shows the OTHER tiled windows of the monitor's active workspace, when that workspace is in stage mode, as
// small still cards along one edge; a click brings one to the front. The rail only exists while the workspace has at
// least two windows (or one, with stage.showWithOneWindow), and it reserves its own space like the bar, so the front
// window is resized when the rail appears or goes away. Everything it shows is read from settings.json (stage.*), so
// every size and look is tunable from the settings app.
Scope {
    id: root

    // Settings with the defaults of settings.py, used only while a key is missing from the file.
    readonly property var cfg: ThemeStore.settings.stage ?? ({})
    function opt(key: string, fallback: var): var { return cfg[key] !== undefined ? cfg[key] : fallback }
    readonly property bool enabled: StageState.anyOn       // some workspace is in stage mode: listen to Hyprland

    // Bumped by the periodic refresh and when the front window changes: every card takes a new still.
    property int captureVersion: 0

    IpcHandler {
        target: "stage"
        function refresh(): void { root.refreshNow(); root.captureVersion++ }
        // Test hook: what a click on that window's rail card does (the first screen's rail), cursor handling included.
        function focus(address: string): void { if (rails.instances.length > 0) rails.instances[0].panel.focusWindow(address) }
        function status(): string {
            const out = []
            for (let i = 0; i < rails.instances.length; i++) {
                const r = rails.instances[i].panel
                out.push({ screen: r.screenName, workspace: r.workspace ? r.workspace.name : "", stage: r.stageHere,
                           windows: r.windows.length, front: r.frontAddress, frame: r.frame, toplevels: r.workspace ? r.workspace.toplevels.values.length : -1,
                           cards: r.cardModel.count, visible: r.railVisible })
            }
            return JSON.stringify({ enabled: root.enabled, overrides: StageState.overrides, screens: out })
        }
    }

    function refreshNow(): void {
        Hyprland.refreshMonitors()      // a monitor's x/y goes stale after a hotplug or layout change, and the frame is built from it
        Hyprland.refreshWorkspaces()
        Hyprland.refreshToplevels()
    }

    // Hyprland's events do not carry geometry or focus history; refresh the models on a debounce, only while the mode is on.
    Timer { id: refreshTimer; interval: 140; onTriggered: root.refreshNow() }

    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (!root.enabled) return
            const name = event.name
            if (name === "openwindow" || name === "closewindow" || name === "movewindow" || name === "movewindowv2"
                || name === "activewindow" || name === "activewindowv2" || name === "workspace"
                || name === "moveworkspace" || name === "fullscreen" || name === "changefloatingmode"
                || name === "monitoradded" || name === "monitoraddedv2" || name === "monitorremoved"
                || name === "configreloaded")
                refreshTimer.restart()
        }
    }

    // Periodic still refresh while any rail is visible (0 = only when the front window changes).
    Timer {
        interval: Math.max(1, root.opt("refreshSeconds", 3)) * 1000
        repeat: true
        running: root.enabled && root.opt("refreshSeconds", 3) > 0 && root.anyVisible
        onTriggered: root.captureVersion++
    }

    property bool anyVisible: false
    function updateVisible(): void {
        let any = false
        for (let i = 0; i < rails.instances.length; i++) if (rails.instances[i].panel.railVisible) any = true
        anyVisible = any
    }

    Variants {
        id: rails
        model: Quickshell.screens

        Scope {
            id: per
            required property var modelData
            property alias panel: win

            PanelWindow {
                id: win

                readonly property string screenName: per.modelData.name
                readonly property var monitor: Hyprland.monitorFor(per.modelData)
                readonly property var workspace: monitor ? monitor.activeWorkspace : null
                readonly property var frame: Model.monitorFrame(monitor)

                // The tiled windows of the active workspace; the one with the newest focus is the one on top.
                readonly property bool stageHere: workspace !== null && StageState.isStage(workspace.name)
                readonly property var windows: stageHere
                    ? Model.windowsOf(workspace, frame).filter(w => !w.floating) : []
                readonly property var front: {
                    let best = null
                    for (let i = 0; i < windows.length; i++) if (best === null || windows[i].focus < best.focus) best = windows[i]
                    return best
                }
                readonly property string frontAddress: front ? front.address : ""
                // The other windows: most recently used first, or in the order Hyprland lists them.
                readonly property var others: {
                    const list = windows.filter(w => w.address !== frontAddress)
                    if (root.opt("order", "recent") === "recent") {
                        list.sort((a, b) => a.focus - b.focus)
                    } else {
                        const all = Hyprland.toplevels.values.map(t => Model.normalizeAddress(t.address))
                        list.sort((a, b) => all.indexOf(a.address) - all.indexOf(b.address))
                    }
                    return list
                }
                readonly property bool railVisible: stageHere
                    && (windows.length >= 2 || (windows.length >= 1 && root.opt("showWithOneWindow", false) === true))

                // Looks, all from settings.
                readonly property string position: root.opt("railPosition", "left")
                readonly property int railWidth: root.opt("railWidth", 150)
                readonly property int padding: root.opt("railPadding", 12)
                readonly property int cardHeight: root.opt("cardHeight", 100)
                readonly property int gap: Theme.gridMode ? 0 : root.opt("cardGap", 12)
                readonly property int cardRadius: Theme.gridMode ? 0 : root.opt("cardRadius", 10)
                readonly property bool showTitle: root.opt("showTitle", true) === true
                readonly property bool showIcon: root.opt("showIcon", true) === true
                readonly property bool animations: root.opt("animations", true) === true
                readonly property real cardWidth: Math.max(40, railWidth - 2 * padding)
                readonly property int captureVersion: root.captureVersion

                // Stable cards: a ListModel diffed against `others`, so a refresh never recreates a screenshot.
                ListModel { id: cardList }
                property alias cardModel: cardList

                function syncCards() {
                    const list = win.railVisible ? win.others : []
                    for (let i = cardList.count - 1; i >= 0; i--)
                        if (!list.some(w => w.address === cardList.get(i).address)) cardList.remove(i)
                    for (let i = 0; i < list.length; i++) {
                        const w = list[i]
                        const row = { address: w.address, appId: w.appId, title: w.title }
                        let at = -1
                        for (let j = 0; j < cardList.count; j++) if (cardList.get(j).address === w.address) { at = j; break }
                        if (at < 0) cardList.insert(Math.min(i, cardList.count), row)
                        else {
                            cardList.set(at, row)
                            if (at !== i) cardList.move(at, i, 1)
                        }
                    }
                }
                onOthersChanged: syncCards()
                onRailVisibleChanged: { syncCards(); root.updateVisible() }
                onFrontAddressChanged: root.captureVersion++
                Component.onCompleted: syncCards()

                function toplevelFor(address) {
                    const list = Hyprland.toplevels.values
                    for (let i = 0; i < list.length; i++)
                        if (Model.normalizeAddress(list[i].address) === address) return list[i]
                    return null
                }
                function focusWindow(address) {
                    const target = Model.normalizeAddress(address)
                    // Focusing a window warps the cursor to its centre (Hyprland cursor.no_warps is off). From the rail the
                    // pointer should stay on the card, so no_warps is on for exactly this one focus and then put back to
                    // what it was. `target` is a validated 0x-hex address, so it is safe inside the Lua text.
                    if (target !== "") Quickshell.execDetached(["hyprctl", "eval",
                        "local nw = hl.get_config('cursor.no_warps'); hl.config({cursor={no_warps=true}}); "
                        + "hl.dispatch(hl.dsp.focus({window='address:" + target + "'})); hl.config({cursor={no_warps=nw}})"])
                }

                screen: per.modelData
                visible: railVisible
                anchors {
                    top: true
                    bottom: true
                    left: win.position === "left"
                    right: win.position === "right"
                }
                // A reserving rail is placed inside the usable area, which the compositor already keeps clear of the bar
                // (an extra margin put it 36 px too low). Without reserving it spans the whole monitor edge, so it
                // takes the bar's inset like the overview does.
                readonly property bool reserve: root.opt("reserveSpace", true) === true
                margins {
                    top: !reserve && Theme.barPosition === "top" ? Theme.barInset : 0
                    bottom: !reserve && Theme.barPosition === "bottom" ? Theme.barInset : 0
                    left: !reserve && win.position === "left" && Theme.barPosition === "left" ? Theme.barInset : 0
                    right: !reserve && win.position === "right" && Theme.barPosition === "right" ? Theme.barInset : 0
                }
                implicitWidth: railWidth
                exclusionMode: reserve ? ExclusionMode.Normal : ExclusionMode.Ignore
                exclusiveZone: railWidth
                WlrLayershell.layer: WlrLayer.Top
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                WlrLayershell.namespace: "bbkos-stage"
                color: Qt.rgba(Theme.surface.r, Theme.surface.g, Theme.surface.b, root.opt("railOpacity", 0.0))

                Flickable {
                    id: flick
                    anchors.fill: parent
                    contentWidth: width
                    contentHeight: Math.max(height, column.height + 2 * win.padding)
                    interactive: contentHeight > height
                    clip: true

                    Column {
                        id: column
                        x: win.padding
                        width: win.cardWidth
                        spacing: win.gap
                        // Centred when it fits (like macOS), from the top with scrolling when it does not.
                        y: Math.max(win.padding, (flick.height - height) / 2)

                        Repeater {
                            model: cardList

                            StageCard { rail: win }
                        }
                    }
                }
            }
        }
    }
}
