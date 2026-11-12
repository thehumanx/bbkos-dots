import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.services

// The date popup's world clocks (docs/modules/calendar.md): a strip of cards across both panels of the popup, one per time zone in calendar.zones (four to a row): the place, the time there,
// the day there and "3:15 h ahead / behind" against this computer's own time. The offsets come from `bbkos-zones now`
// (daylight saving included), read when the popup opens and when the list changes; the minute comes from the popup's SystemClock.
// Hover a card for its x; the add button opens a search box (ZoneAdder).
PopupSection {
    id: root
    title: "World clocks"
    property date now: new Date()                          // the popup's minute tick
    readonly property bool typing: adder.typing
    readonly property var zones: { const z = SettingsStore.shown("calendar.zones"); return Array.isArray(z) ? z : [] }
    readonly property bool hour24: SettingsStore.shown("clock.hour24") !== false
    property var info: ({})                                 // zone -> { city, offset (minutes from UTC) }

    onZonesChanged: refresh()
    Component.onCompleted: refresh()
    function refresh() {
        if (zones.length === 0) { info = ({}); return }
        if (proc.running) { again = true; return }
        proc.command = ["bbkos-zones", "now"].concat(zones)
        proc.running = true
    }
    property bool again: false
    Process {
        id: proc
        stdout: StdioCollector {
            onStreamFinished: {
                try { const m = {}; for (const r of JSON.parse(text)) m[r.zone] = r; root.info = m } catch (e) { root.info = ({}) }
            }
        }
        onExited: if (root.again) { root.again = false; root.refresh() }
    }

    // t is shifted so its UTC fields are the zone's wall clock.
    function hhmm(t: date): string {
        const h = t.getUTCHours(), m = t.getUTCMinutes()
        const mm = (m < 10 ? "0" : "") + m
        if (hour24) return (h < 10 ? "0" : "") + h + ":" + mm
        return ((h % 12) === 0 ? 12 : h % 12) + ":" + mm
    }
    function ampm(t: date): string { return hour24 ? "" : (t.getUTCHours() < 12 ? " AM" : " PM") }
    function dayName(offset: int, t: date): string {      // the day there against the day here
        const here = -now.getTimezoneOffset()
        const d = Math.floor((now.getTime() + offset * 60000) / 86400000) - Math.floor((now.getTime() + here * 60000) / 86400000)
        return d === 0 ? "Today" : d === 1 ? "Tomorrow" : d === -1 ? "Yesterday" : Qt.locale().dayName(t.getUTCDay(), Locale.ShortFormat)
    }
    function gap(offset: int): string {                   // "5:15 h ahead"
        const diff = offset + now.getTimezoneOffset()
        const a = Math.abs(diff)
        return diff === 0 ? "same time" : Math.floor(a / 60) + (a % 60 ? ":" + (a % 60 < 10 ? "0" : "") + a % 60 : "") + " h " + (diff > 0 ? "ahead" : "behind")
    }
    function remove(z) { SettingsStore.set("calendar.zones", zones.filter(n => n !== z)) }

    Txt { visible: root.zones.length === 0; text: "Add places to see their time here."; color: Theme.dim }
    GridLayout {
        id: grid
        visible: root.zones.length > 0
        Layout.fillWidth: true
        columns: 4
        columnSpacing: 8
        rowSpacing: 8
        Repeater {
            model: root.zones
            delegate: Rectangle {
                id: card
                required property string modelData
                readonly property var r: root.info[modelData] ?? null
                readonly property date t: new Date(root.now.getTime() + (r ? r.offset : 0) * 60000)
                Layout.preferredWidth: (root.width - 3 * grid.columnSpacing) / 4      // a quarter of the strip each, however few cards there are
                implicitHeight: col.implicitHeight + 20
                radius: Theme.controlRadius
                color: Theme.inset
                HoverHandler { id: hv }
                ColumnLayout {
                    id: col
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
                    spacing: 2
                    Txt { text: card.r ? card.r.city : card.modelData.split("/").pop().replace(/_/g, " "); color: Theme.dim; font.pixelSize: Theme.fontSize - 1; elide: Text.ElideRight; Layout.fillWidth: true; Layout.rightMargin: 16 }
                    RowLayout {
                        spacing: 0
                        Txt { visible: card.r !== null; text: root.hhmm(card.t); font.bold: true; font.pixelSize: Theme.fontSize + 3 }
                        Txt { visible: card.r !== null && root.ampm(card.t) !== ""; text: root.ampm(card.t); color: Theme.dim; font.pixelSize: Theme.fontSize - 1; Layout.alignment: Qt.AlignBaseline }
                    }
                    Txt { visible: card.r !== null; text: card.r ? root.dayName(card.r.offset, card.t) + "  ·  " + root.gap(card.r.offset) : ""; color: Theme.dim; font.pixelSize: Theme.fontSize - 2; elide: Text.ElideRight; Layout.fillWidth: true }
                }
                Rectangle {                                   // remove, on hover
                    anchors { top: parent.top; right: parent.right; margins: 4 }
                    implicitWidth: 20; implicitHeight: 20
                    radius: Theme.controlRadius
                    opacity: hv.hovered ? 1 : 0
                    enabled: hv.hovered
                    color: xHit.containsMouse ? Theme.control : "transparent"
                    Txt { anchors.centerIn: parent; text: "×"; color: Theme.dim }
                    MouseArea { id: xHit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.remove(card.modelData) }
                }
            }
        }
    }
    ZoneAdder {
        id: adder
        exclude: root.zones
        full: root.zones.length >= 8
        onPicked: z => SettingsStore.set("calendar.zones", root.zones.concat([z]))
    }
}
