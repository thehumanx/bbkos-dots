import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs
import qs.services
import "../bar"
import "../overview/OverviewModel.js" as Model
import "RailGeometry.js" as Geo

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
        // Test hooks for the pinned apps: what a click on that app's tile does, and the unpin ×.
        function dockclick(id: string): void { if (rails.instances.length > 0) rails.instances[0].panel.dockActivate(id) }
        function undock(id: string): void { Dock.unpin(id) }
        function dock(): string {
            return JSON.stringify({ on: Dock.on, apps: Dock.apps, running: Dock.running, alignBar: Dock.alignBar,
                                    resolved: rails.instances.length > 0 ? rails.instances[0].panel.dockResolved() : [] })     // the pins whose tile found its desktop entry
        }
        function status(): string {
            const out = []
            for (let i = 0; i < rails.instances.length; i++) {
                const r = rails.instances[i].panel
                out.push({ screen: r.screenName, workspace: r.workspace ? r.workspace.name : "", stage: r.stageHere,
                           windows: r.windows.length, front: r.frontAddress, frame: r.frame, toplevels: r.workspace ? r.workspace.toplevels.values.length : -1,
                           cards: r.cardModel.count, visible: r.railVisible, edge: r.position, hug: r.hug,
                           body: { x: r.railStrip.x, y: r.railStrip.y, width: r.railStrip.width, height: r.railStrip.height },
                           style: { radius: r.bodyRadius, blur: r.blurActive, pills: Theme.barPills },
                           tile: r.tile, padding: r.padding, dockSize: { width: r.dockWidth, height: r.dockHeight } })
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

            // Hyprland lays layer windows out in the order they were mapped, and the first takes the edge: a rail that stays
            // mapped while the bar is hidden and shown again ends up before the bar, takes the full height and pushes the bar
            // aside (and covers its edge line). So when the bar comes back the rail is unmapped and mapped again, after it.
            property bool remapping: false
            Connections {
                target: BarState
                function onHiddenChanged() { if (!BarState.hidden) unmapTimer.restart() }
            }
            Timer { id: unmapTimer; interval: 250; onTriggered: { per.remapping = true; mapTimer.restart() } }
            Timer { id: mapTimer; interval: 120; onTriggered: per.remapping = false }

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
                    // A pinned app's window shows as its tile in the dock above, so it is not a card as well.
                    const list = windows.filter(w => w.address !== frontAddress && !(Dock.on && Dock.isPinnedWindow(w.appId)))
                    if (root.opt("order", "recent") === "recent") {
                        list.sort((a, b) => a.focus - b.focus)
                    } else {
                        const all = Hyprland.toplevels.values.map(t => Model.normalizeAddress(t.address))
                        list.sort((a, b) => all.indexOf(a.address) - all.indexOf(b.address))
                    }
                    return list
                }
                // The dock (pinned apps) shows on every workspace; without it the rail shows only on a stage workspace with windows to list.
                readonly property bool railVisible: Dock.on || (stageHere
                    && (windows.length >= 2 || (windows.length >= 1 && root.opt("showWithOneWindow", false) === true)))

                // Looks, all from settings.
                readonly property string position: root.opt("railPosition", "left")
                readonly property bool sideRail: Geo.vertical(position)          // left or right: the rail's length runs down the screen
                // A live change of edge left the layer where it was (measured in the test shell, 2026-10-31: left to right and right to
                // bottom kept the old place): map the window again, as after the bar comes back. A blink of 120 ms, only on a change.
                onPositionChanged: { per.remapping = true; mapTimer.restart() }
                readonly property bool hug: root.opt("railHug", false) === true  // only as long as its contents, at railAlign along the edge
                readonly property string align: root.opt("railAlign", "start")   // the contents along a full rail, the body when hugging
                readonly property int railWidth: root.opt("railWidth", 150)      // a side rail's thickness; sets the tile size on every edge
                readonly property int padding: Theme.gridMode ? Theme.gridMargin : root.opt("railPadding", 12)
                readonly property int cardHeight: root.opt("cardHeight", 100)   // a card's length along the rail, on every edge
                readonly property int gap: Theme.gridMode ? Theme.gridMargin : root.opt("cardGap", 12)   // grid: the window margin, for the padding too
                readonly property int cardRadius: Theme.gridMode ? Theme.gridWindowRadius : root.opt("cardRadius", 10)   // grid: the windows' corner radius
                readonly property bool showTitle: root.opt("showTitle", true) === true
                readonly property bool showIcon: root.opt("showIcon", true) === true
                readonly property bool animations: root.opt("animations", true) === true
                // A tile is the same size on every edge: half of a side rail's inside, less the gap (DockGrid's two columns).
                readonly property real tile: Math.round((Math.max(40, railWidth - 2 * padding) - gap) / 2)
                // The rail's thickness: railWidth on a side; on the top or bottom one row of tiles and the padding (owner, 2026-10-31).
                readonly property real railThick: sideRail ? railWidth : tile + 2 * padding
                readonly property real crossSize: sideRail ? Math.max(40, railWidth - 2 * padding) : tile   // tiles and cards across the rail
                readonly property real cardWidth: crossSize
                readonly property real float: Theme.gridMode ? 0 : Theme.barFloat       // grid mode floats nothing
                readonly property real px: Theme.gridMode ? Theme.hair : 1               // grid: whole physical pixels for the hairlines
                readonly property real thickness: railThick + float
                readonly property real bodyRadius: Theme.gridMode ? 0 : Math.min(Theme.barRadius, railThick / 2)
                readonly property bool blurActive: railBlur.active
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
                function dockResolved(): var { return dockGrid.resolved() }
                readonly property real dockWidth: dockGrid.width
                readonly property real dockHeight: dockGrid.height
                // A pinned app's tile: focus its window when it has one, start it otherwise.
                function dockActivate(id: string): void {
                    if (id in Dock.running) focusWindow(Dock.running[id])
                    else Dock.launch(id)
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
                visible: railVisible && !per.remapping
                anchors {
                    top: win.position !== "bottom"
                    bottom: win.position !== "top"
                    left: win.position !== "right"
                    right: win.position !== "left"
                }
                // A reserving rail is placed inside the usable area, which the compositor already keeps clear of the bar
                // (an extra margin put it 36 px too low). Without reserving it spans the whole monitor edge, so it
                // takes the bar's inset like the overview does.
                readonly property bool reserve: root.opt("reserveSpace", true) === true
                // Grid mode, reserving, and only where the bar's thickness is not a whole number of physical pixels on this screen
                // (Theme.barHeight is rounded to one, so normally never): one logical pixel clear of the bar. A fractional bar edge
                // shares its last row with the rail's first; whenever the rail repainted (a tile's hover animation) the compositor
                // redrew that row from the rail alone and the bar's edge line vanished (screen recordings, 2026-10-30; dock.md).
                readonly property int gridPad: Theme.gridMode && reserve && !Theme.exactOn(per.modelData, Theme.barInset) ? 1 : 0
                readonly property var marginSet: Geo.windowMargins({ edge: position, reserve: reserve, barPosition: Theme.barPosition,
                                                                     barInset: Theme.barInset, gridPad: gridPad })
                margins {
                    top: win.marginSet.top
                    bottom: win.marginSet.bottom
                    left: win.marginSet.left
                    right: win.marginSet.right
                }
                // The window spans its whole edge and reserves the same thickness whether the body hugs or not (as end-4's dock and
                // Bar.qml do), so nothing is re-laid out when an app is pinned; input goes to the body only.
                implicitWidth: sideRail ? thickness : 0
                implicitHeight: sideRail ? 0 : thickness
                exclusionMode: reserve ? ExclusionMode.Normal : ExclusionMode.Ignore
                exclusiveZone: thickness
                WlrLayershell.layer: WlrLayer.Top
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
                WlrLayershell.namespace: "bbkos-stage"
                color: "transparent"
                mask: Region { item: body }

                readonly property rect bodyRect: {
                    const b = Geo.body({ edge: position, hug: hug, align: align, float: float, thickness: railThick,
                                         windowLength: sideRail ? win.height : win.width,
                                         contentLength: (sideRail ? content.height : content.width) + 2 * padding, px: px })
                    return Qt.rect(b.x, b.y, b.width, b.height)
                }
                // Where the body sits on its screen, in logical pixels: what the blur looks at (the bar's own arithmetic, Bar.qml bodyStrip).
                readonly property rect railStrip: {
                    const o = Geo.windowOrigin({ edge: position, screenWidth: per.modelData.width, screenHeight: per.modelData.height,
                                                 windowThickness: thickness, barPosition: Theme.barPosition, barInset: Theme.barInset })
                    return Qt.rect(o.x + bodyRect.x, o.y + bodyRect.y, bodyRect.width, bodyRect.height)
                }

                Rectangle {
                    id: body
                    x: win.bodyRect.x
                    y: win.bodyRect.y
                    width: win.bodyRect.width
                    height: win.bodyRect.height
                    // The bar's background in both modes (barBg, blurred like the bar; stage.railOpacity is no longer read), with the
                    // bar's corners outside grid mode; grid mode puts the bar's cell fill over it (below), so the two read as one style.
                    color: railBlur.active ? "transparent" : Theme.barBg
                    radius: win.bodyRadius

                    BarBlur {
                        id: railBlur
                        anchors.fill: parent
                        z: -1
                        screenWidth: per.modelData.width
                        screenHeight: per.modelData.height
                        strip: win.railStrip
                        radius: body.radius
                    }
                    Rectangle {                    // grid mode: one big empty cell over that, like the bar's empty stretches (Bar.qml gridFills)
                        z: 0
                        visible: Theme.gridMode
                        anchors.fill: parent
                        color: Theme.pillBg
                    }
                    Rectangle {                    // grid mode: the line along the rail's inner edge, like the bar's
                        z: 1
                        visible: Theme.gridMode
                        color: Theme.cardEdge
                        width: win.sideRail ? Theme.hair : parent.width
                        height: win.sideRail ? parent.height : Theme.hair
                        x: win.position === "left" ? parent.width - Theme.hair : 0
                        y: win.position === "top" ? parent.height - Theme.hair : 0
                    }
                    // Grid mode, hugging: the body is one cell, so it draws its two ends along the edge too. The screen's own edges
                    // are drawn by modules/frame alone, above the rail.
                    // Not where the body reaches an end of its window: there the bar's line or the screen frame is already drawn.
                    Repeater {
                        model: Theme.gridMode && win.hug ? 2 : 0
                        Rectangle {
                            required property int index
                            readonly property real start: win.sideRail ? win.bodyRect.y : win.bodyRect.x
                            readonly property real end: start + (win.sideRail ? win.bodyRect.height : win.bodyRect.width)
                            readonly property real windowLength: win.sideRail ? win.height : win.width
                            visible: index === 0 ? start > 0.5 : end < windowLength - 0.5
                            z: 1
                            color: Theme.cardEdge
                            width: win.sideRail ? body.width : Theme.hair
                            height: win.sideRail ? Theme.hair : body.height
                            x: win.sideRail || index === 0 ? 0 : body.width - Theme.hair
                            y: !win.sideRail || index === 0 ? 0 : body.height - Theme.hair
                        }
                    }

                    Flickable {
                        id: flick
                        anchors.fill: parent
                        contentWidth: win.sideRail ? width : Math.max(width, content.width + 2 * win.padding)
                        contentHeight: win.sideRail ? Math.max(height, content.height + 2 * win.padding) : height
                        flickableDirection: win.sideRail ? Flickable.VerticalFlick : Flickable.HorizontalFlick
                        interactive: win.sideRail ? contentHeight > height : contentWidth > width
                        clip: true

                        // Laid out along the rail: a column on a side rail, a row on a top or bottom one.
                        Grid {
                            id: content
                            // One line of children; the other count is left at 0 (computed): a Grid given 1000 rows reserves the spacing of
                            // every one of them (a column 8122 px tall for five tiles, 2026-10-31).
                            columns: win.sideRail ? 1 : 0
                            rows: win.sideRail ? 0 : 1
                            spacing: win.gap
                            // Along a full-length rail the tiles and cards sit at stage.railAlign (start, centre or end); from the start with
                            // scrolling when they do not fit. A hugging body is placed by RailGeometry instead, so its contents start at once.
                            readonly property real room: win.sideRail ? flick.height : flick.width
                            readonly property real len: win.sideRail ? height : width
                            readonly property real alongPos: win.hug || win.align === "start" ? win.padding
                                : win.align === "end" ? Math.max(win.padding, room - len - win.padding)
                                : Math.max(win.padding, (room - len) / 2)
                            x: win.sideRail ? win.padding : alongPos
                            y: win.sideRail ? alongPos : win.padding

                            DockGrid { id: dockGrid; visible: Dock.on; rail: win }

                            // The line between the pinned apps and the open windows after them, edge to edge across the rail; only while
                            // there are cards to separate. The grid's spacing puts the same gap on both sides of it. An Item holds it,
                            // since the Grid places its children and the line reaches past the padding.
                            Item {
                                visible: Dock.on && cardList.count > 0
                                width: win.sideRail ? win.crossSize : 1
                                height: win.sideRail ? 1 : win.crossSize
                                Rectangle {
                                    x: win.sideRail ? -win.padding : 0
                                    y: win.sideRail ? 0 : -win.padding
                                    width: win.sideRail ? win.railThick : 1
                                    height: win.sideRail ? 1 : win.railThick   // one logical pixel draws one crisp physical row here; a fractional hairline height was dropped
                                    color: Theme.cardEdge
                                }
                            }

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
}
