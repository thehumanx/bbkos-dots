import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs
import qs.components
import qs.services

// Speed test and Share for the network the laptop is on (docs/modules/panels.md, "Speed test and Share"). Both run only
// on a click and only while the popup is open: closing it stops a test (the processes end with the panel).
// Method from Omarchy (omarchy-network-speedtest, omarchy-network-qr): bbkos-speedtest and bbkos-wifi-qr.
ColumnLayout {
    id: root
    spacing: 8

    // ---- Speed test: ping, then download, then upload. Each direction prints a rate a second; the result is the
    // median of the samples after the first two (TCP ramp-up).
    property string phase: ""                 // "" | ping | down | up
    property real live: -1                    // the newest sample of the running phase, Mbps
    property var samples: []
    property string error: ""
    readonly property bool testing: phase !== ""
    readonly property var result: Net.lastSpeed // { ping, down, up, at } of the last finished or stopped test

    function median(list) {
        const v = list.slice(list.length > 4 ? 2 : 0).sort((a, b) => a - b)
        return v.length ? v[Math.floor((v.length - 1) / 2)] : -1
    }
    function startTest() {
        error = ""
        Net.lastSpeed = ({ ping: -1, down: -1, up: -1, at: 0 })
        run("ping")
    }
    function run(p) { samples = []; live = -1; phase = p; speed.command = ["bbkos-speedtest", p]; speed.running = true }
    function stopTest() { phase = ""; speed.running = false }

    Process {
        id: speed
        stdout: SplitParser {
            onRead: line => {
                const v = parseFloat(line)
                if (!isFinite(v)) return
                if (root.phase === "ping") { Net.lastSpeed = Object.assign({}, Net.lastSpeed, { ping: v }); return }
                root.live = v
                root.samples = root.samples.concat([v])
            }
        }
        stderr: StdioCollector { id: speedErr }
        onExited: code => {
            const p = root.phase
            if (p === "") return                              // stopped by the user
            if (code !== 0) { root.error = speedErr.text.trim() || "The speed test failed"; root.phase = ""; return }
            if (p === "down" || p === "up") {
                const o = {}; o[p] = root.median(root.samples)
                Net.lastSpeed = Object.assign({}, Net.lastSpeed, o)
            }
            if (p === "ping") root.run("down")
            else if (p === "down") root.run("up")
            else { Net.lastSpeed = Object.assign({}, Net.lastSpeed, { at: Date.now() }); root.phase = "" }
        }
    }

    // ---- Share: the QR matrix from bbkos-wifi-qr, drawn on a light square. The password itself is fetched only when
    // "Show password" is pressed and is dropped when the share card closes.
    property bool sharing: false
    property var matrix: []
    property string shareSsid: ""
    property string shareError: ""
    property string password: ""
    onSharingChanged: { password = ""; matrix = []; shareError = ""; if (sharing) qr.running = true }

    Process {
        id: qr
        command: ["bbkos-wifi-qr"]
        stdout: StdioCollector {
            onStreamFinished: {
                const lines = text.split("\n").filter(l => l !== "")
                if (lines.length > 0 && lines[0].startsWith("meta\t")) root.shareSsid = lines.shift().split("\t").slice(2).join("\t")
                root.matrix = lines.filter(l => /^[01]+$/.test(l))
            }
        }
        stderr: StdioCollector { id: qrErr }
        onExited: code => { if (code !== 0) root.shareError = qrErr.text.trim() || "Could not make the QR code" }
    }
    Process {
        id: pw
        command: ["bbkos-wifi-qr", "--password"]
        stdout: StdioCollector { onStreamFinished: root.password = text.replace(/\n$/, "") }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Button { text: root.testing ? "Stop" : "Speed test"; onClicked: root.testing ? root.stopTest() : root.startTest() }
        Button { text: root.sharing ? "Hide code" : "Share"; visible: Net.wifiConnected; onClicked: root.sharing = !root.sharing }
        Item { Layout.fillWidth: true }
    }

    // Results: three figures, the running one updating live.
    RowLayout {
        visible: root.testing || root.result.at > 0 || root.result.ping >= 0
        Layout.fillWidth: true
        spacing: 16
        Repeater {
            model: [
                { key: "ping", label: "Ping", unit: "ms" },
                { key: "down", label: "Download", unit: "Mbps" },
                { key: "up", label: "Upload", unit: "Mbps" }
            ]
            delegate: ColumnLayout {
                required property var modelData
                readonly property bool running: root.phase === modelData.key
                readonly property real value: running && modelData.key !== "ping" ? root.live : root.result[modelData.key]
                spacing: 0
                Txt {
                    text: value >= 0 ? (value < 10 && modelData.key !== "ping" ? value.toFixed(1) : Math.round(value)) + " " + modelData.unit
                                     : running ? "…" : "–"
                    font.bold: true
                    color: running ? Theme.accent : Theme.fg
                }
                Txt { text: modelData.label; color: Theme.dim; font.pixelSize: Theme.fontSize - 2 }
            }
        }
        Item { Layout.fillWidth: true }
    }
    Txt {
        visible: root.testing || root.error !== ""
        text: root.error !== "" ? root.error : "Uses data while it runs (about 8 s each way)"
        color: root.error !== "" ? Theme.crit : Theme.dim
        font.pixelSize: Theme.fontSize - 2
        wrapMode: Text.Wrap
        Layout.fillWidth: true
    }

    // The QR card. Modules are drawn in the darker of the two text colours on the lighter one, so the code is always
    // dark on light (some scanners do not read an inverted code), in either theme.
    ColumnLayout {
        visible: root.sharing
        Layout.fillWidth: true
        spacing: 8
        Txt { visible: root.shareError !== ""; text: root.shareError; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Rectangle {
            visible: root.matrix.length > 0
            Layout.alignment: Qt.AlignHCenter
            readonly property int n: root.matrix.length
            readonly property int cell: n > 0 ? Math.max(3, Math.floor(196 / n)) : 4
            readonly property bool fgLight: Theme.fg.hslLightness > Theme.bg.hslLightness
            implicitWidth: n * cell + 16
            implicitHeight: n * cell + 16
            radius: Theme.controlRadius
            color: fgLight ? Theme.fg : Theme.bg
            Canvas {
                id: code
                anchors.centerIn: parent
                width: parent.n * parent.cell
                height: width
                onPaint: {
                    const ctx = getContext("2d")
                    ctx.reset()
                    ctx.fillStyle = parent.fgLight ? Theme.bg : Theme.fg
                    const c = parent.cell
                    root.matrix.forEach((row, y) => {
                        for (let x = 0; x < row.length; x++) if (row[x] === "1") ctx.fillRect(x * c, y * c, c, c)
                    })
                }
                Connections { target: root; function onMatrixChanged() { code.requestPaint() } }
            }
        }
        Txt { visible: root.matrix.length > 0; text: "Scan to join " + root.shareSsid; color: Theme.dim; Layout.alignment: Qt.AlignHCenter; font.pixelSize: Theme.fontSize - 1 }
        RowLayout {
            visible: root.matrix.length > 0
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            Txt { visible: root.password !== ""; text: root.password; font.bold: true; textFormat: Text.PlainText }
            Button {
                text: root.password !== "" ? "Hide password" : "Show password"
                onClicked: { if (root.password !== "") root.password = ""; else pw.running = true }
            }
        }
    }

    IpcHandler {                                  // test hook: qs ipc call wifitools status | speedtest | share
        target: "wifitools"
        function status(): string {
            return JSON.stringify({ phase: root.phase, live: root.live, result: root.result, error: root.error,
                                    sharing: root.sharing, qrSize: root.matrix.length, shareError: root.shareError })
        }
        function speedtest(): void { root.startTest() }
        function share(on: bool): void { root.sharing = on }
    }
}
