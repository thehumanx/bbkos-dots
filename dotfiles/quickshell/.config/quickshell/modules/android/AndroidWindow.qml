import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components

// Android apps (docs/modules/android.md): disable, remove and restore apps on a phone over adb, guided by UAD-ng's safety
// ratings. All work is done by `bbkos-android` (JSON out); this window keeps the last answers and the selection.
// Exists only while `open` (LazyLoader). Hyprland floats it 960x680 centred by class "org.quickshell" + title
// "bbkOS Android" (hyprland.lua). Opened by `qs ipc call android toggle` (the "Android apps" launcher entry).
Scope {
    id: root
    property bool open: false

    property var devices: []
    property bool adbFound: true
    property string serial: ""                   // the phone in use; "" until one is ready (or picked when several)
    property var rows: []
    property string listSerial: ""               // the phone `rows` came from
    property string listError: ""
    property var listAge: null
    property string error: ""
    property bool loading: false
    property bool slowHint: false                // loading for a while: the first run downloads the safety list

    property string tab: "installed"             // installed | off (disabled and removed)
    property string query: ""
    property var ratings: ({ Recommended: true, Advanced: true, Expert: false, Unsafe: false, Unlisted: false })
    property bool showUser: false
    property var selected: ({})                  // package -> true
    property var results: ({})                   // package -> {ok, error}, from the last action
    property string confirming: ""               // "disable" | "remove" while the confirm sheet is up
    property bool wifiOpen: false
    property string wifiMessage: ""
    property var queue: []                       // pending [action, packages, serial] runs (Restore can need enable and restore)

    readonly property var readyDevices: devices.filter(d => d.state === "device")
    readonly property var device: devices.find(d => d.serial === serial) ?? null
    readonly property var visibleRows: rows.filter(r => {
        if (tab === "installed" ? r.state !== "installed" : r.state === "installed") return false
        if (!showUser && !r.system) return false
        if (!ratings[r.rating]) return false
        if (query === "") return true
        const q = query.toLowerCase()
        return r.package.toLowerCase().includes(q) || r.name.toLowerCase().includes(q) || r.description.toLowerCase().includes(q)
    })
    // Only ticked rows the filters show are acted on: a tick hidden by a search or filter never reaches the phone, and a
    // locked row (an app re-rated Unsafe by a list update after it was ticked) is never counted.
    readonly property var selectedRows: visibleRows.filter(r => selected[r.package] && !lockedRow(r))
    readonly property bool busy: loading || actProc.running || queue.length > 0

    function lockedRow(r) { return tab === "installed" && r.rating === "Unsafe" }
    function toggleSelect(pkg) {
        const s = Object.assign({}, selected)
        if (s[pkg]) delete s[pkg]; else s[pkg] = true
        selected = s
    }
    function clearSelection() { selected = ({}) }
    function setTab(t) { if (t !== tab) { tab = t; clearSelection(); results = ({}) } }
    function toggleRating(name) { const r = Object.assign({}, ratings); r[name] = !r[name]; ratings = r }

    function refreshStatus() { if (!statusProc.running) statusProc.running = true }
    function loadList() {
        if (serial === "" || listProc.running) return
        loading = true; slowHint = false
        listProc.command = ["bbkos-android", "list", "--serial", serial]
        listProc.running = true
    }
    function refresh() {
        if (listAge !== null && listAge > 7 * 86400 && !updateProc.running) updateProc.running = true
        else refreshStatus()
    }
    function runNext() {
        if (queue.length === 0 || actProc.running) return
        const [action, pkgs, target] = queue[0]          // the phone the run was started for, even if the picker moved
        queue = queue.slice(1)
        actProc.command = ["bbkos-android", action].concat(pkgs).concat(["--serial", target])
        actProc.running = true
    }
    function startAction(action) {
        const pkgs = selectedRows.filter(r => !lockedRow(r))
        confirming = ""
        if (pkgs.length === 0) return
        results = ({})
        if (action === "restore") {
            const q = []
            const dis = pkgs.filter(r => r.state === "disabled").map(r => r.package)
            const rem = pkgs.filter(r => r.state === "removed").map(r => r.package)
            if (dis.length) q.push(["enable", dis, serial])
            if (rem.length) q.push(["restore", rem, serial])
            queue = q
        } else {
            queue = [[action, pkgs.map(r => r.package), serial]]
        }
        confirming = ""
        runNext()
    }

    onOpenChanged: if (open) { error = ""; results = ({}); refreshStatus() }
    onSerialChanged: { rows = []; queue = []; results = ({}); clearSelection(); loadList() }

    IpcHandler {
        target: "android"
        function toggle(): void { root.open = !root.open }
        function refresh(): void { root.refresh() }
        // Test hooks (screenshots and checks): the state the window shows, tick a package, switch tab, open a sheet.
        function status(): string {
            return JSON.stringify({ open: root.open, serial: root.serial, devices: root.devices.length, rows: root.rows.length,
                                    visible: root.visibleRows.length, selected: root.selectedRows.length, listSerial: root.listSerial,
                                    queue: root.queue.length, busy: root.busy,
                                    loading: root.loading, error: root.error, listError: root.listError })
        }
        function select(pkg: string): void { root.toggleSelect(pkg) }      // bypasses the lock, like a stale tick would
        function rating(name: string): void { root.toggleRating(name) }
        function tab(name: string): void { root.setTab(name) }
        function useSerial(s: string): void { root.serial = s }
        function confirm(action: string): void { if (root.selectedRows.length > 0) root.confirming = action }
        function wifi(): void { root.wifiOpen = true }
        function act(action: string): void { root.startAction(action) }   // test hook: the confirm sheet's button
        function close(): void { root.confirming = ""; root.wifiOpen = false }
    }

    Process {
        id: statusProc
        command: ["bbkos-android", "status"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const st = JSON.parse(text)
                    root.adbFound = st.adb
                    root.devices = st.devices
                    root.error = st.error ?? ""
                } catch (e) { root.error = "Could not read the phone status" }
                const ready = root.devices.filter(d => d.state === "device")
                if (!ready.some(d => d.serial === root.serial))
                    root.serial = ready.length === 1 ? ready[0].serial : ""
                else root.loadList()
            }
        }
    }
    Process {
        id: listProc
        stdout: StdioCollector {
            onStreamFinished: {
                root.loading = false
                try {
                    const res = JSON.parse(text)
                    if (res.error) { root.error = res.error; return }
                    if (res.serial !== root.serial) { Qt.callLater(root.loadList); return }   // the picker moved while loading
                    root.rows = res.packages
                    root.listSerial = res.serial
                    root.listError = res.listError
                    root.listAge = res.listAge
                    root.error = ""
                    const keep = {}
                    for (const r of res.packages) if (root.selected[r.package] && !root.lockedRow(r)) keep[r.package] = true
                    root.selected = keep
                } catch (e) { root.error = "Could not read the app list" }
            }
        }
    }
    Process {
        id: actProc
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const res = JSON.parse(text)
                    if (res.error) root.error = res.error
                    const r = Object.assign({}, root.results)
                    for (const x of res.results ?? []) r[x.package] = { ok: x.ok, error: x.error }
                    root.results = r
                } catch (e) { root.error = "Could not read the result" }
                Qt.callLater(() => {
                    if (root.queue.length > 0) { root.runNext(); return }
                    root.clearSelection()
                    root.loadList()
                })
            }
        }
    }
    Process {
        id: updateProc
        command: ["bbkos-android", "update-list"]
        onExited: root.refreshStatus()
    }
    Process {
        id: wifiProc
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.wifiMessage = JSON.parse(text).message } catch (e) { root.wifiMessage = "Could not read adb's answer" }
                root.refreshStatus()
            }
        }
    }
    Timer {                                      // no phone ready: look again every 2 s while the window is open
        interval: 2000
        repeat: true
        running: root.open && root.readyDevices.length === 0 && !root.wifiOpen
        onTriggered: root.refreshStatus()
    }
    Timer { interval: 3000; running: root.loading; onTriggered: root.slowHint = true }

    LazyLoader {
        active: root.open

        FloatingWindow {
            id: win
            title: "bbkOS Android"
            implicitWidth: 960
            implicitHeight: 680
            minimumSize: Qt.size(720, 480)
            color: Theme.bg

            onClosed: root.open = false
            onVisibleChanged: if (!visible) root.open = false
            Shortcut {
                sequence: "Escape"
                onActivated: {
                    if (root.confirming !== "") root.confirming = ""
                    else if (root.wifiOpen) root.wifiOpen = false
                    else root.open = false
                }
            }

            ColumnLayout {
                anchors { fill: parent; margins: 20 }
                spacing: 12

                // ---- device line
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Txt { text: ""; font.pixelSize: Theme.fontSize + 8; color: root.device ? Theme.accent : Theme.dim }
                    ColumnLayout {
                        spacing: 0
                        Txt {
                            font.bold: true
                            font.pixelSize: Theme.fontSize + 2
                            text: root.device ? [root.device.brand, root.device.model].filter(x => x).join(" ")
                                  : root.readyDevices.length > 1 ? "Pick a phone" : "No phone ready"
                        }
                        Txt {
                            visible: !!root.device
                            color: Theme.dim
                            font.pixelSize: Theme.fontSize - 1
                            text: root.device ? "Android " + root.device.android + " · "
                                                + (root.device.transport === "wifi" ? "Wi-Fi" : "USB") + " · " + root.device.serial : ""
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Button { text: "Wi-Fi…"; enabled: !root.busy; onClicked: { root.wifiMessage = ""; root.wifiOpen = true } }
                    Button { text: "Refresh"; enabled: !root.busy; onClicked: root.refresh() }
                }
                Chips {
                    visible: root.readyDevices.length > 1
                    enabled: !root.busy                  // no switching phones while a list or an action runs
                    model: root.readyDevices.map(d => ({ value: d.serial, label: d.model + " · " + d.serial }))
                    current: root.serial
                    onChosen: v => root.serial = v
                }

                // ---- filters
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    visible: root.rows.length > 0
                    Field {
                        Layout.fillWidth: true
                        placeholder: "Search apps, packages, descriptions"
                        onTextChanged: root.query = text
                    }
                    Txt { text: "Show user apps"; color: Theme.dim }
                    Toggle { checked: root.showUser; onToggled: v => root.showUser = v }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    visible: root.rows.length > 0
                    Repeater {
                        model: ["Recommended", "Advanced", "Expert", "Unsafe", "Unlisted"]
                        delegate: Rectangle {
                            required property string modelData
                            readonly property bool on: root.ratings[modelData] === true
                            implicitWidth: lbl.implicitWidth + 24; implicitHeight: 30
                            radius: Theme.controlRadius
                            color: on ? Theme.accent : ma.containsMouse ? Theme.accentSoft : Theme.control
                            Txt { id: lbl; anchors.centerIn: parent; text: parent.modelData; color: parent.on ? Theme.bg : Theme.fg; font.bold: parent.on; font.pixelSize: Theme.fontSize - 1 }
                            MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.toggleRating(parent.modelData) }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Chips {
                        Layout.fillWidth: false
                        model: [{ value: "installed", label: "Installed " + root.rows.filter(r => r.state === "installed").length },
                                { value: "off", label: "Disabled / Removed " + root.rows.filter(r => r.state !== "installed").length }]
                        current: root.tab
                        onChosen: v => root.setTab(v)
                    }
                }
                Txt {
                    visible: root.listError !== ""
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.warn
                    text: root.listError + ". Every app shows as Unlisted, and Disable and Remove are refused; connect to the internet and Refresh."
                }
                Txt {
                    visible: root.error !== ""
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.crit
                    text: root.error
                }

                // ---- list, or what to do when there is none
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: Theme.radius
                    color: Theme.surface
                    border.width: Theme.hair
                    border.color: Theme.cardEdge

                    ListView {
                        id: list
                        anchors { fill: parent; margins: 6 }
                        visible: root.rows.length > 0
                        clip: true
                        spacing: 2
                        model: root.visibleRows
                        boundsBehavior: Flickable.StopAtBounds
                        delegate: AppRow {
                            required property var modelData
                            row: modelData
                            width: ListView.view.width
                            selected: root.selected[modelData.package] === true
                            locked: root.lockedRow(modelData)
                            result: root.results[modelData.package] ?? null
                            onToggled: root.toggleSelect(modelData.package)
                        }
                    }
                    Txt {
                        visible: root.rows.length > 0 && root.visibleRows.length === 0
                        anchors.centerIn: parent
                        color: Theme.dim
                        text: "Nothing matches the filters"
                    }
                    ColumnLayout {
                        visible: root.rows.length === 0
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 60, 520)
                        spacing: 8
                        Txt {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            font.bold: true
                            font.pixelSize: Theme.fontSize + 2
                            text: !root.adbFound ? "adb not found"
                                  : root.loading ? "Loading apps…"
                                  : root.devices.some(d => d.state === "unauthorized") ? "Accept the USB debugging prompt on the phone"
                                  : root.readyDevices.length > 1 && root.serial === "" ? "Pick a phone above"
                                  : root.devices.some(d => d.state === "offline") ? "Phone offline: replug it or connect again"
                                  : "Connect your phone"
                        }
                        Txt {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            color: Theme.dim
                            text: !root.adbFound ? "Install the android-tools package."
                                  : root.loading ? (root.slowHint ? "The first time also downloads the safety list from UAD-ng; this can take 20 seconds." : "")
                                  : root.device || root.readyDevices.length > 1 ? ""
                                  : "On the phone: Settings → About phone → tap Build number 7 times, then Developer options → USB debugging. "
                                    + "Plug the phone in and accept the prompt, or use Wi-Fi… for wireless debugging."
                        }
                    }
                }

                // ---- action bar
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: root.rows.length > 0
                    Txt {
                        text: root.busy && !root.loading ? "Working…" : root.selectedRows.length + " selected"
                        color: Theme.dim
                    }
                    Item { Layout.fillWidth: true }
                    Button { text: "Clear"; enabled: root.selectedRows.length > 0; onClicked: root.clearSelection() }
                    Button {
                        visible: root.tab === "installed"
                        text: "Disable" + (root.selectedRows.length > 0 ? " " + root.selectedRows.length : "")
                        enabled: root.selectedRows.length > 0 && !root.busy
                        onClicked: root.confirming = "disable"
                    }
                    Button {
                        visible: root.tab === "installed"
                        text: "Remove" + (root.selectedRows.length > 0 ? " " + root.selectedRows.length : "")
                        tint: Theme.crit
                        enabled: root.selectedRows.length > 0 && !root.busy
                        onClicked: root.confirming = "remove"
                    }
                    Button {
                        visible: root.tab === "off"
                        text: "Restore" + (root.selectedRows.length > 0 ? " " + root.selectedRows.length : "")
                        enabled: root.selectedRows.length > 0 && !root.busy
                        onClicked: root.startAction("restore")
                    }
                }
            }

            ConfirmSheet {
                anchors.fill: parent
                visible: root.confirming !== ""
                action: root.confirming
                rows: root.selectedRows.filter(r => !root.lockedRow(r))
                onConfirmed: root.startAction(root.confirming)
                onCancelled: root.confirming = ""
            }
            WifiForm {
                anchors.fill: parent
                visible: root.wifiOpen
                message: root.wifiMessage
                busy: wifiProc.running
                onRun: args => { root.wifiMessage = ""; wifiProc.command = ["bbkos-android"].concat(args); wifiProc.running = true }
                onClosed: root.wifiOpen = false
            }
        }
    }
}
