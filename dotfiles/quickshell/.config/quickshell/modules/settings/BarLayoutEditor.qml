import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Where each bar widget sits: its section (Left, Centre, Right) and its place in that section. Drag a widget by its
// grip onto another widget (it takes that spot) or onto a section heading (it goes to the end of that section). The
// section buttons do the same without dragging. Settings bar.layout is the order on the bar; writes go through
// SettingsStore like every other control.
// `key` and `modified` let the card's "Reset these" (SettingsSection) put the default order back.
ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: 2

    readonly property string key: "bar.layout"
    readonly property bool modified: SettingsStore.modified(key)

    readonly property var sectionNames: [{ id: "start", label: "Left" }, { id: "center", label: "Centre" },
                                         { id: "end", label: "Right" }]
    readonly property var widgetNames: ({
        overview: "Overview", workspaces: "Workspaces", clock: "Clock", media: "Music", timer: "Timer", updates: "Updates", tray: "Tray", display: "Display brightness", audio: "Audio",
        bluetooth: "Bluetooth", network: "Network", battery: "Battery", notifications: "Notifications", record: "Recording indicator", privacy: "Privacy indicator", settings: "Settings button"
    })
    // Where each widget's own settings are ("page/tab#row" for SettingsStore.openPage and reveal); a widget missing here has none.
    readonly property var widgetSettings: ({
        clock: "bar/widgets#24-hour clock", media: "bar/widgets#Longest width", privacy: "privacy/main#Microphone",
        record: "capture/capture#What to record", display: "displays/main", audio: "sound/main", network: "network/main",
        battery: "power/profiles", notifications: "notifications/main", updates: "about/about", workspaces: "windows/behaviour#Switch back"
    })
    readonly property var layout: {
        const v = SettingsStore.shown("bar.layout")
        return Array.isArray(v) ? v : []
    }

    // Heading and widget rows, in bar order: each section's heading, then its widgets.
    readonly property var rowModel: {
        const out = []
        for (const sec of sectionNames) {
            out.push({ header: true, section: sec.id })
            for (const e of layout)
                if (e.startsWith(sec.id + ":")) out.push({ header: false, section: sec.id, widget: e.slice(sec.id.length + 1) })
        }
        return out
    }

    property string dragWidget: ""
    property int dragTarget: -1
    // The settings page this editor sits in: its scrolling is paused while a widget is held.
    property var scroller: null
    onDragWidgetChanged: if (scroller) scroller.scrollLocked = dragWidget !== ""

    function setSection(widget: string, section: string): void {
        const rest = layout.filter(e => e.split(":")[1] !== widget)
        let at = -1
        rest.forEach((e, i) => { if (e.startsWith(section + ":")) at = i })
        rest.splice(at + 1, 0, section + ":" + widget)
        SettingsStore.set("bar.layout", rest)
    }

    // Put `widget` where the row at `target` is: before a widget row, or at the end of a heading's section.
    function dropOn(widget: string, target: int): void {
        const r = rowModel[target]
        if (!r || (!r.header && r.widget === widget)) return
        const rest = layout.filter(e => e.split(":")[1] !== widget)
        let at
        if (r.header) {
            let last = -1
            rest.forEach((e, i) => { if (e.startsWith(r.section + ":")) last = i })
            if (last >= 0) {
                at = last + 1
            } else {
                // Empty section: go before the first widget of the next section that has one.
                const later = sectionNames.slice(sectionNames.findIndex(s => s.id === r.section) + 1).map(s => s.id)
                at = rest.findIndex(e => later.some(id => e.startsWith(id + ":")))
                if (at < 0) at = rest.length
            }
        } else {
            at = rest.indexOf(r.section + ":" + r.widget)
            if (at < 0) return
        }
        const section = r.section
        rest.splice(at, 0, section + ":" + widget)
        SettingsStore.set("bar.layout", rest)
    }

    // Which row the pointer is over, while dragging.
    function trackDrag(grip: Item, mouse): void {
        const p = grip.mapToItem(list, mouse.x, mouse.y)
        dragTarget = -1
        for (let i = 0; i < rep.count; i++) {
            const q = rep.itemAt(i)
            if (!q) continue
            const top = q.mapToItem(list, 0, 0).y
            if (p.y >= top && p.y < top + q.height) { dragTarget = i; break }
        }
    }

    ColumnLayout {
        id: list
        Layout.fillWidth: true
        spacing: 2

        Repeater {
            id: rep
            model: root.rowModel
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                Layout.fillWidth: true
                implicitHeight: modelData.header ? heading.implicitHeight + 10 : 32

                Rectangle {
                    anchors.fill: parent
                    radius: Theme.controlRadius
                    color: root.dragTarget === row.index ? Theme.surface : "transparent"
                }

                Txt {
                    id: heading
                    visible: row.modelData.header
                    anchors { left: parent.left; leftMargin: 4; verticalCenter: parent.verticalCenter }
                    text: root.sectionNames.find(s => s.id === row.modelData.section)?.label ?? ""
                    color: Theme.dim
                    font.bold: true
                }

                RowLayout {
                    visible: !row.modelData.header
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: 8

                    // Grip: press and drag to move the widget.
                    Rectangle {
                        implicitWidth: 24
                        implicitHeight: 24
                        radius: Theme.controlRadius
                        border.width: Theme.hair
                        border.color: Theme.dim
                        color: "transparent"
                        Txt { anchors.centerIn: parent; text: "⋮⋮"; color: Theme.dim }
                        MouseArea {
                            id: gripArea
                            anchors.fill: parent
                            cursorShape: Qt.SizeAllCursor
                            // Keep the scrolling page from taking the drag: the page scrolls only when the grip is not held.
                            preventStealing: true
                            onPressed: {
                                root.dragWidget = row.modelData.widget
                                root.dragTarget = row.index
                            }
                            onPositionChanged: mouse => { if (gripArea.pressed) root.trackDrag(gripArea, mouse) }
                            onReleased: {
                                if (root.dragWidget !== "" && root.dragTarget >= 0) root.dropOn(root.dragWidget, root.dragTarget)
                                root.dragWidget = ""
                                root.dragTarget = -1
                            }
                        }
                    }

                    Txt {
                        text: root.widgetNames[row.modelData.widget] ?? row.modelData.widget ?? ""
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Button {                                   // the widget's own settings, on whichever page holds them
                        readonly property string target: root.widgetSettings[row.modelData.widget] ?? ""
                        visible: target !== ""
                        text: "\uf013  Settings"
                        onClicked: {
                            const parts = target.split("#")
                            SettingsStore.openPage(parts[0])
                            if (parts.length > 1) SettingsStore.reveal = parts[1]
                        }
                    }
                    Repeater {
                        model: root.sectionNames
                        delegate: Button {
                            required property var modelData
                            text: modelData.label
                            tint: root.layout.includes(modelData.id + ":" + row.modelData.widget) ? Theme.accent : Theme.fg
                            onClicked: root.setSection(row.modelData.widget, modelData.id)
                        }
                    }
                }
            }
        }
    }
}
