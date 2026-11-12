import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs

// Adds a time zone: a "+ Add time zone" button that opens a search box over the tz database (`bbkos-zones list`, read once, the
// first time it opens). Typing "tok" lists Tokyo; the first matches show under the box, a click or Enter picks one. Matches the
// city, the region and the full name, ignoring case, spaces and underscores. `exclude` hides zones that are already chosen.
// Used by the date popup's world clocks and the Bar > Widgets page (docs/modules/calendar.md).
ColumnLayout {
    id: root
    property var exclude: []
    property bool full: false                              // the list is at its limit: the button is greyed
    readonly property bool typing: input.activeFocus
    property bool open: false
    property var all: []
    signal picked(string zone)

    spacing: 6
    Layout.fillWidth: true

    function norm(s) { return String(s).toLowerCase().replace(/[_\s/]+/g, "") }
    readonly property var matches: {
        const q = norm(input.text)
        if (q === "") return []
        const out = []
        for (const z of all) {
            if (exclude.indexOf(z.zone) >= 0) continue
            if (norm(z.zone).indexOf(q) >= 0) out.push(z)
            if (out.length >= 6) break
        }
        return out
    }
    function pick(z) { root.picked(z); input.text = ""; open = false }

    Process {
        id: listProc
        command: ["bbkos-zones", "list"]
        stdout: StdioCollector { onStreamFinished: { try { root.all = JSON.parse(text) } catch (e) { root.all = [] } } }
    }

    Button {
        visible: !root.open
        text: "+  Add time zone"
        enabled: !root.full
        onClicked: { root.open = true; if (root.all.length === 0 && !listProc.running) listProc.running = true; input.forceActiveFocus() }
    }

    Rectangle {
        visible: root.open
        Layout.fillWidth: true
        implicitHeight: 30
        radius: Theme.controlRadius
        color: Theme.inset
        border.width: input.activeFocus ? 2 : Theme.hair
        border.color: input.activeFocus ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.3)
        TextInput {
            id: input
            anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            color: Theme.fg
            font.family: Theme.font
            font.pixelSize: Theme.fontSize
            selectionColor: Theme.accent
            selectedTextColor: Theme.bg
            onVisibleChanged: if (visible) forceActiveFocus()
            Keys.onReturnPressed: if (root.matches.length > 0) root.pick(root.matches[0].zone)
            Keys.onEscapePressed: ev => { text = ""; root.open = false; ev.accepted = true }
        }
        Txt {
            visible: input.text === ""
            anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
            text: "City or region, e.g. Tokyo"
            color: Theme.dim
        }
    }
    Repeater {
        model: root.open ? root.matches : []
        delegate: Rectangle {
            required property var modelData
            Layout.fillWidth: true
            implicitHeight: 28
            radius: Theme.controlRadius
            color: hit.containsMouse ? Theme.control : "transparent"
            RowLayout {
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                Txt { text: modelData.city; Layout.fillWidth: true; elide: Text.ElideRight }
                Txt { text: modelData.region; color: Theme.dim; font.pixelSize: Theme.fontSize - 1 }
            }
            MouseArea { id: hit; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.pick(modelData.zone) }
        }
    }
    Txt {
        visible: root.open && input.text !== "" && root.matches.length === 0 && root.all.length > 0
        text: "No place matches"
        color: Theme.dim
    }
}
