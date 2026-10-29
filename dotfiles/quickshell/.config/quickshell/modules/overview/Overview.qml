import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Wayland
import qs
import qs.components
import qs.services
import "OverviewModel.js" as Model
import "../../components/FileUrl.js" as FileUrl

// Mission Control-style workspace overview (docs/modules/overview.md). A layer-shell overlay, inset by the bar, shows
// the workspaces Hyprland currently has (plus a "+" card) along the top and the windows of the selected one below.
//
// How it moves: the windows live in one "screen layer" that is the real monitor at 1:1. Opening scales and moves that
// single layer from the real screen down into the stage slot while the blurred wallpaper fades in and the workspace
// strip drops in from above; closing runs the same progress backwards, so the screen scales back up onto the real
// one. One progress value (`p`, 0 = normal desktop, 1 = overview) drives everything, so each frame is a handful of
// GPU transforms and nothing is relaid out.
//
// What keeps it smooth: the overlay windows are persistent (mapped on open, never rebuilt), the blurred wallpaper is a
// pre-baked texture (Backdrop.qml), window and workspace delegates are stable (diffed into ListModels, so a Hyprland
// refresh never recreates a capture), and the animation only starts once the window screenshots have arrived, so the
// swap between the real windows and their screenshots is not visible.
Scope {
    id: root

    // Test hooks: `qs ipc call overview status` and the actions the bar icon and gestures use.
    IpcHandler {
        target: "overview"
        function toggle(): void { OverviewState.toggle("") }
        function toggleOn(screenName: string): void { OverviewState.toggle(screenName) }
        function open(): void { OverviewState.openOn("") }
        function openOn(screenName: string): void { OverviewState.openOn(screenName) }
        function close(): void { OverviewState.close() }
        function select(workspace: int): void { if (Model.isWorkspaceId(workspace)) OverviewState.selected = workspace }
        function switchTo(workspace: int): void { if (Model.isWorkspaceId(workspace)) root.switchToWorkspace(workspace) }
        function move(address: string, workspace: int): void { root.moveWindow(address, workspace) }
        function add(): int { return OverviewState.addWorkspace() }
        function status(): string {
            const w = root.workspaceFor(OverviewState.selected)
            return JSON.stringify({
                open: OverviewState.open,
                shown: root.shown,
                progress: root.p,
                screen: root.targetName,
                selected: OverviewState.selected,
                workspaces: root.workspaceIds,
                focused: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : 0,
                windows: w ? w.toplevels.values.map(t => t.address) : []
            })
        }
    }

    // The screen that shows the overview: the one latched at open (the bar icon's screen, else the focused one then), else the first.
    readonly property string targetName: {
        const names = Quickshell.screens.map(sc => sc.name)
        if (OverviewState.target !== "" && names.includes(OverviewState.target)) return OverviewState.target
        const f = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
        return names.includes(f) ? f : (names.length > 0 ? names[0] : "")
    }

    // The strip lists the workspaces that currently exist, any empty slots added with "+", and always the focused and
    // selected ones (so navigating to a fresh empty workspace still shows a card). Sorted by id.
    readonly property var workspaceIds: {
        const ids = []
        const workspaces = Hyprland.workspaces.values
        for (let i = 0; i < workspaces.length; i++) {
            const id = Number(workspaces[i].id)
            if (id >= 1 && !ids.includes(id)) ids.push(id)
        }
        for (let i = 0; i < OverviewState.extra.length; i++) {
            const id = Number(OverviewState.extra[i])
            if (id >= 1 && !ids.includes(id)) ids.push(id)
        }
        const focused = OverviewState.focusedWorkspaceId()
        if (focused >= 1 && !ids.includes(focused)) ids.push(focused)
        if (OverviewState.selected >= 1 && !ids.includes(OverviewState.selected)) ids.push(OverviewState.selected)
        ids.sort((left, right) => left - right)
        return ids
    }

    // The strip's delegates are driven by this model, kept in step with `workspaceIds` by minimal inserts and removes:
    // a plain array model would rebuild every card whenever the selection or any workspace changed.
    ListModel { id: wsModel }

    function syncWorkspaces(): void {
        const ids = root.shown ? root.workspaceIds : []
        for (let i = wsModel.count - 1; i >= 0; i--)
            if (!ids.includes(wsModel.get(i).wid)) wsModel.remove(i)
        for (let i = 0; i < ids.length; i++) {
            if (i < wsModel.count && wsModel.get(i).wid === ids[i]) continue
            wsModel.insert(i, { wid: ids[i] })
        }
    }
    onWorkspaceIdsChanged: syncWorkspaces()
    onShownChanged: syncWorkspaces()

    // Hyprland's IPC events do not carry a window's new geometry when another window moves it (retiling); Quickshell's
    // lastIpcObject can stay stale. Refresh both models on a debounce; the cards follow in place.
    function refreshNow(): void {
        Hyprland.refreshMonitors()      // monitor x/y can be stale after a hotplug; the window fractions are built from it
        Hyprland.refreshWorkspaces()
        Hyprland.refreshToplevels()
    }
    function scheduleRefresh(): void { refreshTimer.restart() }

    Timer {
        id: refreshTimer
        interval: 140
        repeat: false
        onTriggered: root.refreshNow()
    }

    // A stage-mode switch re-lays the workspace out in Hyprland without any event that carries the new geometry, so
    // refresh once the `hyprctl eval` has applied the rule (a second time in case the first came too early).
    Connections {
        target: StageState
        function onOverridesChanged() { if (OverviewState.open) { root.scheduleRefresh(); lateRefresh.restart() } }
    }
    Timer { id: lateRefresh; interval: 450; onTriggered: root.refreshNow() }

    // ---- Open / close progress ----------------------------------------------------------------------------------
    property real p: 0                          // 0 = normal desktop, 1 = overview
    property bool shown: false                  // the overlay windows are mapped (open, or still animating closed)
    property bool closing: false
    property bool zoomClose: true               // closing scales the stage back up onto the real screen
    property bool forceZoom: false              // set by actions that switch to the selected workspace
    property bool waitingOpen: false            // mapped, waiting for the screenshots before the animation starts
    property bool gateMin: false
    // While closing onto a workspace that is not the one on screen (Esc after previewing another one) the stage would
    // zoom onto the wrong windows, so it stays put and the whole sheet fades instead.
    readonly property real layerP: closing && !zoomClose ? 1 : p
    // Cards take part in input and animate their own moves only once the overview has fully opened.
    readonly property bool settled: OverviewState.open && p >= 1

    NumberAnimation {
        id: openAnim
        target: root
        property: "p"
        to: 1
        duration: Theme.durLarge
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Theme.easeDrawer
    }

    NumberAnimation {
        id: closeAnim
        target: root
        property: "p"
        to: 0
        duration: Theme.durLarge - 40
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Theme.easeDrawer
        onFinished: { root.closing = false; root.shown = false }
    }

    // The open waits for every screenshot (at least 40 ms so the data refresh lands, at most 220 ms), so the animation
    // never starts from placeholders.
    Timer { id: minGate; interval: 40; onTriggered: { root.gateMin = true; root.tryStartOpen(false) } }
    Timer { id: maxGate; interval: 220; onTriggered: root.tryStartOpen(true) }

    function tryStartOpen(force: bool): void {
        if (!waitingOpen) return
        if (!force) {
            if (!gateMin) return
            for (let i = 0; i < screens.instances.length; i++)
                if (screens.instances[i].target && !screens.instances[i].contentReady()) return
        }
        waitingOpen = false
        minGate.stop()
        maxGate.stop()
        openAnim.start()
    }

    property int prevSelected: 1

    Connections {
        target: OverviewState
        function onOpenChanged() {
            if (OverviewState.open) {
                closeAnim.stop()
                root.closing = false
                root.shown = true
                root.syncWorkspaces()
                root.prevSelected = OverviewState.selected
                root.refreshNow()
                if (root.p > 0.001) openAnim.start()                  // reopened while still closing: reverse in place
                else {
                    root.waitingOpen = true
                    root.gateMin = false
                    minGate.restart()
                    maxGate.restart()
                }
            } else {
                refreshTimer.stop()
                root.waitingOpen = false
                minGate.stop()
                maxGate.stop()
                openAnim.stop()
                if (root.p <= 0.001) { root.p = 0; root.shown = false; return }
                root.zoomClose = root.forceZoom || OverviewState.selected === OverviewState.focusedWorkspaceId()
                root.forceZoom = false
                root.closing = true
                closeAnim.start()
            }
        }
        // A background 3-finger swipe moves the overview's view instead, with a small slide of the stage.
        function onSelectedChanged() {
            if (!OverviewState.open) return
            const dir = Math.sign(OverviewState.selected - root.prevSelected)
            root.prevSelected = OverviewState.selected
            if (dir === 0 || root.p < 1) return
            for (let i = 0; i < screens.instances.length; i++) {
                const w = screens.instances[i]
                if (w.target) w.beginStageSlide(dir)
            }
        }
    }

    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (!OverviewState.open) return
            const name = event.name
            if (name === "movewindow" || name === "movewindowv2" || name === "openwindow"
                || name === "closewindow" || name === "createworkspace" || name === "destroyworkspace"
                || name === "moveworkspace" || name === "workspace" || name === "fullscreen"
                || name === "changefloatingmode" || name === "minimize")
                root.scheduleRefresh()
        }

        // Hyprland's own horizontal swipe switches the workspace behind the backdrop; follow it once the service state
        // has actually moved (inside the raw event the focused workspace is still stale and would be written back).
        function onFocusedWorkspaceChanged() {
            if (!OverviewState.open) return
            // Moving the cursor to the other monitor focuses that monitor's workspace; only a change on the screen the
            // overview is on may move the view.
            const fm = Hyprland.focusedMonitor
            if (fm && fm.name !== root.targetName) return
            const id = OverviewState.focusedWorkspaceId()
            if (id >= 1 && id !== OverviewState.selected) OverviewState.selected = id
        }
    }

    function workspaceFor(id: var): var {
        const found = Hyprland.workspaces.values.find(w => w.id === Number(id))
        return found ?? null
    }

    function switchToWorkspace(id: int) {
        if (!Model.isWorkspaceId(id)) return
        // Hyprland 0.56 runs Lua configs and no longer accepts the legacy "workspace N" dispatcher over IPC; the Lua
        // dispatcher is the documented replacement (`hl.dsp.focus`).
        Hyprland.dispatch("hl.dsp.focus({ workspace = " + id + " })")
        // The stage shows the selected workspace, so closing zooms it onto the screen only when it is the target.
        root.forceZoom = OverviewState.selected === id
        OverviewState.close()
    }

    function moveWindow(address: string, workspace: int) {
        const target = Model.normalizeAddress(address)
        if (target === "" || !Model.isWorkspaceId(workspace)) return
        // Hyprland's Lua window.move() brings the moved window (and so its workspace) to the front when it was the
        // focused one; put the focus back where it was, so a drop never yanks the user to another workspace.
        const before = Hyprland.focusedWorkspace ? Number(Hyprland.focusedWorkspace.id) : 0
        Hyprland.dispatch("hl.dsp.window.move({ workspace = " + workspace + ", window = \"address:" + target + "\" })")
        if (before >= 1 && before !== workspace)
            Hyprland.dispatch("hl.dsp.focus({ workspace = " + before + " })")
        root.scheduleRefresh()
    }

    // One overlay per screen (a click anywhere closes it, like the popup panels), created once and only mapped while
    // shown. Only the target screen builds the strip and the cards; the others are an invisible click-catcher.
    Variants {
        id: screens
        model: Quickshell.screens

        Scope {
            id: perScreen
            required property var modelData

            PanelWindow {
                id: win

                readonly property var modelData: perScreen.modelData

                // modelData goes null while the delegate of an unplugged monitor is torn down ("dangling screen object"):
                // every read of it below is null-safe, or the unplug logs a TypeError per binding (2026-10-28).
                readonly property bool target: modelData?.name === root.targetName
                readonly property var selectedWorkspace: root.shown ? root.workspaceFor(OverviewState.selected) : null
                readonly property var monitorInfo: selectedWorkspace && selectedWorkspace.monitor
                    ? selectedWorkspace.monitor : Hyprland.monitorFor(modelData)
                readonly property var frame: Model.monitorFrame(monitorInfo)
                readonly property var windows: root.shown && target ? Model.windowsOf(selectedWorkspace, frame) : []

                // The real monitor in logical pixels: the screen layer's own size, and the unit window geometry is in.
                readonly property real frameWidth: frame ? frame.width : (modelData?.width ?? 0)
                readonly property real frameHeight: frame ? frame.height : (modelData?.height ?? 0)
                // The overlay surface is inset by the bar edge; these margins are the surface's origin in the monitor's
                // frame, so the real screen's top-left corner sits at (-surfaceX, -surfaceY) in surface coordinates.
                readonly property real surfaceX: Theme.barPosition === "left" ? Theme.barInset : 0
                readonly property real surfaceY: Theme.barPosition === "top" ? Theme.barInset : 0

                readonly property real progress: root.layerP
                // Where the screen ends up: the largest rectangle of the monitor's aspect that fits the stage area.
                readonly property real aspect: frameHeight > 0 ? frameWidth / frameHeight : 16 / 10
                readonly property real slotWidth: Math.max(1, Math.min(stageArea.width, stageArea.height * aspect))
                readonly property real slotHeight: slotWidth / aspect
                readonly property real slotX: stageArea.x + (stageArea.width - slotWidth) / 2
                readonly property real slotY: stageArea.y + (stageArea.height - slotHeight) / 2
                readonly property real stageScale: frameWidth > 0 ? slotWidth / frameWidth : 1
                // Current scale of the layer: 1 at the real screen, stageScale in the stage. Decoration divides by this.
                readonly property real layerScale: 1 + (stageScale - 1) * Math.max(0, Math.min(1, progress))
                readonly property bool settled: root.settled
                readonly property bool interactive: OverviewState.open && root.p > 0.6

                // Stage slide for a follow (background swipe) or a preview change.
                property real slide: 0
                property real slideFade: 1

                function beginStageSlide(dir) {
                    if (dir === 0) return
                    win.slide = dir > 0 ? 90 : -90
                    win.slideFade = 0.2
                    slideAnim.restart()
                }

                ParallelAnimation {
                    id: slideAnim
                    NumberAnimation { target: win; property: "slide"; to: 0; duration: 240; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut }
                    NumberAnimation { target: win; property: "slideFade"; to: 1; duration: 240; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut }
                }

                // ---- Window cards: a stable ListModel, diffed from `windows` -----------------------------------------
                ListModel { id: winModel }

                function indexOfAddress(address) {
                    for (let i = 0; i < winModel.count; i++)
                        if (winModel.get(i).address === address) return i
                    return -1
                }

                function syncWindows() {
                    const list = win.windows
                    const seen = ({})
                    for (let i = 0; i < list.length; i++) {
                        const w = list[i]
                        seen[w.address] = true
                        const row = { address: w.address, appId: w.appId, title: w.title,
                                      rx: w.rect.x, ry: w.rect.y, rw: w.rect.width, rh: w.rect.height, order: i }
                        const at = indexOfAddress(w.address)
                        if (at < 0) winModel.append(row)
                        else winModel.set(at, row)
                    }
                    for (let i = winModel.count - 1; i >= 0; i--)
                        if (!seen[winModel.get(i).address]) winModel.remove(i)
                }
                onWindowsChanged: syncWindows()

                function toplevelFor(address) {
                    const list = Hyprland.toplevels.values
                    for (let i = 0; i < list.length; i++)
                        if (Model.normalizeAddress(list[i].address) === address) return list[i]
                    return null
                }

                // Every card registers, so the open can wait until all screenshots have arrived.
                property var windowCards: []
                function registerWindowCard(card) { if (windowCards.indexOf(card) < 0) windowCards.push(card) }
                function unregisterWindowCard(card) {
                    const i = windowCards.indexOf(card)
                    if (i >= 0) windowCards.splice(i, 1)
                }
                function contentReady() {
                    for (let i = 0; i < windowCards.length; i++)
                        if (!windowCards[i].hasContent && windowCards[i].captureSource !== null) return false
                    return true
                }
                function windowContentChanged() { root.tryStartOpen(false) }

                // ---- Drag state --------------------------------------------------------------------------------------
                // Coordinates are scene coordinates (mapToItem(null, ...)), shared by the window cards and the workspace
                // cards, so hit-testing does not depend on where either is nested.
                property var workspaceCards: []
                property string dragAddress: ""
                property real dragX: 0
                property real dragY: 0
                property real dragOffsetX: 0
                property real dragOffsetY: 0
                property int dropWorkspace: 0

                function registerWorkspaceCard(card) {
                    if (workspaceCards.indexOf(card) < 0) workspaceCards.push(card)
                }
                function unregisterWorkspaceCard(card) {
                    const i = workspaceCards.indexOf(card)
                    if (i >= 0) workspaceCards.splice(i, 1)
                }
                function workspaceCardAt(x, y) {
                    for (let i = 0; i < workspaceCards.length; i++) {
                        const card = workspaceCards[i]
                        const pos = card.mapToItem(null, 0, 0)
                        if (x >= pos.x && x <= pos.x + card.width && y >= pos.y && y <= pos.y + card.height)
                            return card.workspaceId
                    }
                    return 0
                }
                function refreshDrop() {
                    dropWorkspace = dragAddress === "" ? 0 : workspaceCardAt(dragX, dragY)
                }
                function beginDrag(address, scenePoint, localX, localY) {
                    dragAddress = address
                    dragOffsetX = localX
                    dragOffsetY = localY
                    dragX = scenePoint.x
                    dragY = scenePoint.y
                    refreshDrop()
                }
                function updateDrag(scenePoint) {
                    dragX = scenePoint.x
                    dragY = scenePoint.y
                    refreshDrop()
                }
                function clearDrag() {
                    dragAddress = ""
                    dropWorkspace = 0
                    dragX = 0
                    dragY = 0
                }
                function endDrag() {
                    const address = dragAddress
                    const targetId = dropWorkspace
                    clearDrag()
                    if (address === "") return
                    if (targetId === -1) {
                        const id = OverviewState.addWorkspace()
                        root.moveWindow(address, id)
                    } else if (targetId >= 1) {
                        root.moveWindow(address, targetId)
                    }
                }
                function cancelDrag() { clearDrag() }

                function addWorkspace() { return OverviewState.addWorkspace() }
                function stepSelection(delta) {
                    const ids = root.workspaceIds
                    if (ids.length === 0) return
                    let i = ids.indexOf(Number(OverviewState.selected))
                    if (i < 0) i = 0
                    i = Math.max(0, Math.min(ids.length - 1, i + delta))
                    OverviewState.selected = ids[i]
                }

                function workspaceClicked(id) {
                    if (dragAddress !== "") return
                    if (id === OverviewState.selected) root.switchToWorkspace(id)
                    else OverviewState.selected = id
                }
                function switchToWorkspace(id) { root.switchToWorkspace(id) }
                function activateWindow(address) {
                    const target = Model.normalizeAddress(address)
                    if (target === "") return
                    const focused = Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : 0
                    if (focused !== OverviewState.selected)
                        Hyprland.dispatch("hl.dsp.focus({ workspace = " + OverviewState.selected + " })")
                    Hyprland.dispatch("hl.dsp.focus({ window = \"address:" + target + "\" })")
                    root.forceZoom = true
                    OverviewState.close()
                }

                screen: modelData
                visible: root.shown
                // Keep the bar visible and uncovered in this mode: start the overlay at the bar edge instead of covering
                // it. Theme.barPosition and barInset follow the live settings.
                anchors { top: true; bottom: true; left: true; right: true }
                margins {
                    top: Theme.barPosition === "top" ? Theme.barInset : 0
                    bottom: Theme.barPosition === "bottom" ? Theme.barInset : 0
                    left: Theme.barPosition === "left" ? Theme.barInset : 0
                    right: Theme.barPosition === "right" ? Theme.barInset : 0
                }
                exclusionMode: ExclusionMode.Ignore
                WlrLayershell.layer: WlrLayer.Overlay
                // Exclusive on every screen while open, like the panels: while one exclusive layer exists Hyprland only
                // sends pointer events to exclusive layers, so a non-exclusive overlay on another screen would see
                // nothing. Released as soon as the close starts so the keyboard is the user's again during the animation.
                WlrLayershell.keyboardFocus: OverviewState.open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
                WlrLayershell.namespace: "bbkos-overview"
                color: "transparent"

                Shortcut { sequence: "Escape"; onActivated: OverviewState.close() }
                MouseArea { anchors.fill: parent; enabled: OverviewState.open; onClicked: OverviewState.close() }

                Item {
                    id: sheet
                    anchors.fill: parent
                    visible: win.target
                    opacity: root.closing && !root.zoomClose ? root.p : 1

                    // Blurred, bar-tinted wallpaper instead of a flat panel (Backdrop.qml for the how and why).
                    Backdrop {
                        anchors.fill: parent
                        opacity: root.p
                        screenWidth: win.modelData?.width ?? 0
                        screenHeight: win.modelData?.height ?? 0
                        screenScale: win.modelData?.devicePixelRatio ?? 1
                    }

                    // Navigation only exists on the target screen; Esc above is on every screen.
                    Shortcut {
                        sequence: "Left"
                        onActivated: if (win.dragAddress === "") win.stepSelection(-1)
                    }
                    Shortcut {
                        sequence: "Right"
                        onActivated: if (win.dragAddress === "") win.stepSelection(1)
                    }
                    Shortcut {
                        sequence: "Return"
                        onActivated: if (win.dragAddress === "") root.switchToWorkspace(OverviewState.selected)
                    }

                    // Entrance of the top area: it drops in from above and fades with the progress.
                    readonly property real topReveal: Math.max(0, Math.min(1, (win.progress - 0.1) / 0.9))

                    Txt {
                        id: heading
                        anchors { top: parent.top; left: parent.left; topMargin: 26; leftMargin: 40 }
                        text: "Workspaces"
                        color: Theme.fg
                        opacity: sheet.topReveal
                        font.pixelSize: Theme.fontSize + 5
                        font.bold: true
                        transform: Translate { y: -(1 - sheet.topReveal) * 36 }
                    }

                    // Stage mode switch (modules/stage) for the workspace shown below (OverviewState.selected): its windows
                    // open one at a time with a rail of cards. Per workspace until the next boot (StageState); the
                    // default for every workspace is stage.enabled on the Stage mode settings page.
                    Row {
                        anchors { right: parent.right; verticalCenter: heading.verticalCenter; rightMargin: 40 }
                        spacing: 10
                        opacity: sheet.topReveal
                        transform: Translate { y: -(1 - sheet.topReveal) * 36 }

                        Txt {
                            text: "Stage mode for workspace " + OverviewState.selected
                            color: Theme.dim
                            font.pixelSize: Theme.fontSize - 1
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Toggle {
                            anchors.verticalCenter: parent.verticalCenter
                            enabled: win.interactive
                            checked: StageState.isStage(String(OverviewState.selected))
                            onToggled: value => StageState.set(String(OverviewState.selected), value)
                        }
                    }

                    // The workspaces Hyprland currently has, in id order, plus the "+" card. No fixed slots. Each card
                    // drops in a little after the previous one.
                    Row {
                        id: strip
                        anchors { top: heading.bottom; topMargin: 18; horizontalCenter: parent.horizontalCenter }
                        spacing: Theme.gap

                        readonly property int count: wsModel.count + 1
                        readonly property real available: win.width - 80
                        readonly property real cardWidth: Math.max(56, Math.min(160,
                            (available - Math.max(0, count - 1) * spacing) / Math.max(1, count)))

                        function revealOf(i) {
                            return Math.max(0, Math.min(1, win.progress * 1.5 - 0.1 - i * 0.07))
                        }

                        Repeater {
                            model: win.target ? wsModel : null

                            WorkspaceCard {
                                required property int index
                                required property int wid
                                readonly property var ws: root.workspaceFor(wid)
                                width: strip.cardWidth
                                height: 104
                                reveal: strip.revealOf(index)
                                workspaceId: wid
                                workspace: ws
                                selected: OverviewState.selected === wid
                                current: ws ? ws.focused : false
                                dropTarget: win.dragAddress !== "" && win.dropWorkspace === wid
                                frame: Model.monitorFrame(ws && ws.monitor ? ws.monitor : win.monitorInfo)
                                host: win
                            }
                        }

                        AddWorkspaceCard {
                            width: strip.cardWidth
                            height: 104
                            host: win
                            reveal: strip.revealOf(wsModel.count)
                            dropTarget: win.dragAddress !== "" && win.dropWorkspace === -1
                        }
                    }

                    // Where the screen settles; only its geometry is used (win.slotX/Y/Width/Height).
                    Item {
                        id: stageArea
                        anchors {
                            top: strip.bottom; topMargin: 22
                            left: parent.left; right: parent.right
                            bottom: parent.bottom; bottomMargin: 22
                            leftMargin: 40; rightMargin: 40
                        }
                    }

                    // The screen layer: the real monitor at 1:1, scaled and moved into the stage slot by the progress.
                    // Above the strip, so a dragged window passes over the workspace cards.
                    Item {
                        id: screenLayer
                        z: 10
                        visible: win.target
                        width: win.frameWidth
                        height: win.frameHeight
                        transformOrigin: Item.TopLeft
                        scale: win.layerScale
                        x: -win.surfaceX + (win.slotX + win.surfaceX) * Math.max(0, Math.min(1, win.progress))
                        y: -win.surfaceY + (win.slotY + win.surfaceY) * Math.max(0, Math.min(1, win.progress))

                        // The screen's own wallpaper, sharp: it makes the shrinking layer read as the screen itself. Fades
                        // in at the start of the open (the real wallpaper is identical underneath).
                        Image {
                            anchors.fill: parent
                            opacity: Math.max(0, Math.min(1, win.progress * 4))
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: false
                            source: ThemeStore.wallpaperPath !== "" ? FileUrl.toUrl(ThemeStore.wallpaperPath) : ""
                            sourceSize: Qt.size(Math.round((win.modelData?.width ?? 0) * (win.modelData?.devicePixelRatio ?? 1) / 2),
                                                Math.round((win.modelData?.height ?? 0) * (win.modelData?.devicePixelRatio ?? 1) / 2))
                        }

                        // Frame of the stage, a hair-line that stays one pixel wide at any scale.
                        Rectangle {
                            anchors.fill: parent
                            color: "transparent"
                            opacity: win.progress
                            border.width: Theme.hair / win.layerScale
                            border.color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.22)
                            z: 1
                        }

                        // The windows of the selected workspace, at their real places. The slide moves them sideways when
                        // the selection changes.
                        Item {
                            id: content
                            width: parent.width
                            height: parent.height
                            x: win.slide / win.layerScale
                            opacity: win.slideFade

                            Repeater {
                                model: win.target ? winModel : null

                                WindowCard {
                                    host: win
                                }
                            }
                        }

                        Txt {
                            anchors.centerIn: parent
                            visible: win.target && winModel.count === 0
                            opacity: win.progress
                            text: "No windows on this workspace"
                            color: Theme.dim
                            font.pixelSize: Theme.fontSize / win.layerScale
                        }
                    }
                }
            }

            // The bar stays visible next to the overview, but while the overview holds an exclusive layer Hyprland
            // sends pointer events to exclusive layers only, so the bar itself never sees a click (measured: no hover
            // event on the bar widget while open). This transparent strip over the bar is exclusive too and closes the
            // overview on a click, so the grid icon closes it again (any other bar item closes it as well, like a click
            // outside a panel). Esc is handled here because the keyboard follows the pointer between exclusive layers.
            PanelWindow {
                screen: perScreen.modelData
                visible: OverviewState.open && Theme.barInset > 0
                anchors {
                    top: Theme.barPosition !== "bottom"
                    bottom: Theme.barPosition !== "top"
                    left: Theme.barPosition !== "right"
                    right: Theme.barPosition !== "left"
                }
                implicitWidth: Theme.barVertical ? Theme.barInset : 0
                implicitHeight: Theme.barVertical ? 0 : Theme.barInset
                exclusionMode: ExclusionMode.Ignore
                WlrLayershell.layer: WlrLayer.Overlay
                WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
                WlrLayershell.namespace: "bbkos-overview-bar"
                color: "transparent"

                Shortcut { sequence: "Escape"; onActivated: OverviewState.close() }
                MouseArea {
                    anchors.fill: parent
                    onClicked: OverviewState.close()
                }
            }
        }
    }
}
