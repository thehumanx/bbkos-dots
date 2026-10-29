import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import "SearchIndex.js" as SearchIndex

// Page list of the settings window, in groups. `pages` and `groups` are Pages.js (PAGES, GROUPS); the sidebar lists the pages
// under their group, in `groups` order. `current` (a page id) is owned by the window; a click emits picked(place). The search
// box filters by the label, group and keywords of a page and of each of its tabs (a flat list while there is a query: a tab
// that matches is listed as "Page › Tab" and opens that tab) and the single settings that match (SearchIndex.js: label, hint,
// card title and place; at most 40), each with where it is: settings named by the query first, then pages, then settings that
// match only through their hint. Picking a setting opens its tab and the page scrolls to the row and lights it up
// (SettingsStore.reveal). Enter opens the first hit, Esc clears the box first.
Rectangle {
    id: root
    property var pages: []
    property var groups: []
    property string current: ""
    property string query: ""
    signal picked(string place, string reveal)

    function setSearch(text: string): void { search.text = text }
    function pickFirst(): void { const h = hits.find(e => e.header === ""); if (h) picked(h.place, h.reveal ?? "") }
    function matches(hay: string, q: string): bool {
        hay = hay.toLowerCase()
        return q.split(/\s+/).filter(w => w !== "").every(w => hay.indexOf(w) >= 0)
    }
    readonly property var hits: {
        const q = query.trim().toLowerCase()
        if (q === "") return []
        const pageHits = []
        for (const p of pages) {
            const base = p.label + " " + p.group + " " + (p.keywords ?? "")
            if (matches(base, q)) { pageHits.push({ header: "", place: p.id, page: p.id, icon: p.icon, label: p.label }); continue }
            for (const t of p.tabs)
                if (matches(base + " " + t.label + " " + (t.keywords ?? ""), q))
                    pageHits.push({ header: "", place: p.id + "/" + t.id, page: p.id, icon: p.icon, label: p.label + "  ›  " + t.label })
        }
        // Settings whose name has every word come first (Enter opens the best one), then pages, then settings that match only
        // through their hint, card or place.
        const named = [], other = []
        for (const r of SearchIndex.ROWS) {
            if (named.length + other.length >= 40) break
            const named_ = matches(r.label, q)
            if (!named_ && !matches(r.label + " " + r.hint + " " + r.section + " " + r.where, q)) continue
            const p = pages.find(x => x.id === r.place.split("/")[0])
            ;(named_ ? named : other).push({ header: "", place: r.place, page: r.place.split("/")[0], icon: p ? p.icon : "", label: r.label,
                                             sub: r.where + (r.section !== "" ? " · " + r.section : ""), reveal: r.label })
        }
        let out = []
        if (named.length > 0) out = out.concat([{ header: "Settings", place: "" }], named)
        if (pageHits.length > 0) out = out.concat([{ header: "Pages", place: "" }], pageHits)
        if (other.length > 0) out = out.concat([{ header: named.length > 0 ? "Also mentioned" : "Settings", place: "" }], other)
        return out
    }

    color: Theme.popupBg

    // [{ header: "Appearance" }, { index, icon, label }, ...]
    readonly property var entries: {
        if (query.trim() !== "") return hits
        const out = []
        for (const g of groups) {
            out.push({ header: g, place: "" })
            for (const p of pages)
                if (p.group === g) out.push({ header: "", place: p.id, page: p.id, icon: p.icon, label: p.label })
        }
        return out
    }

    // The list scrolls (wheel, drag) when the window is too short for every page; no scroll bar.
    Flickable {
        id: flick
        anchors { fill: parent; margins: 14 }
        contentWidth: width
        contentHeight: list.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: list
        width: flick.width
        spacing: 2

        Txt { text: "Settings"; font.bold: true; font.pixelSize: Theme.fontSize + 4; Layout.preferredHeight: 32; Layout.leftMargin: 10; Layout.topMargin: 4; Layout.bottomMargin: 6 }

        Rectangle {                                   // search
            Layout.fillWidth: true
            Layout.bottomMargin: 4
            implicitHeight: 32
            radius: Theme.controlRadius
            color: Theme.inset
            border.width: search.activeFocus ? 2 : Theme.hair
            border.color: search.activeFocus ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.3)
            Txt { anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter } text: "\uf002"; color: Theme.dim }
            TextInput {
                id: search
                anchors { fill: parent; leftMargin: 32; rightMargin: 10 }
                verticalAlignment: TextInput.AlignVCenter
                clip: true
                color: Theme.fg
                font.family: Theme.font
                font.pixelSize: Theme.fontSize
                selectionColor: Theme.accent
                selectedTextColor: Theme.bg
                onTextChanged: root.query = text
                onAccepted: root.pickFirst()
                Keys.onEscapePressed: event => { if (text !== "") { text = ""; event.accepted = true } else event.accepted = false }
                Txt { visible: search.text === "" && !search.activeFocus; text: "Search settings"; color: Theme.dim; anchors.verticalCenter: parent.verticalCenter }
            }
        }
        Txt { visible: root.query.trim() !== "" && root.hits.length === 0; text: "No setting matches."; color: Theme.dim; Layout.leftMargin: 10; Layout.topMargin: 8 }

        Repeater {
            model: root.entries
            delegate: Item {
                id: entry
                required property var modelData
                readonly property bool isHeader: modelData.header !== ""
                readonly property bool active: !isHeader && root.current === modelData.page && !modelData.sub

                Layout.fillWidth: true
                Layout.topMargin: isHeader ? 12 : 0
                implicitHeight: isHeader ? 24 : (modelData.sub ? 48 : 38)

                Txt {
                    visible: entry.isHeader
                    anchors { left: parent.left; leftMargin: 10; bottom: parent.bottom; bottomMargin: 2 }
                    text: entry.modelData.header.toUpperCase()
                    color: Theme.dim
                    font.pixelSize: Theme.fontSize - 2
                    font.letterSpacing: 1
                    font.bold: true
                }

                Rectangle {
                    visible: !entry.isHeader
                    anchors.fill: parent
                    radius: Theme.controlRadius
                    color: entry.active ? Theme.accentSoft : (area.containsMouse ? Theme.control : "transparent")
                    Behavior on color { ColorAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }

                    RowLayout {
                        anchors { fill: parent; leftMargin: 16; rightMargin: 10 }
                        spacing: 12
                        Txt { text: entry.modelData.icon ?? ""; color: entry.active ? Theme.accent : Theme.dim; horizontalAlignment: Text.AlignHCenter; Layout.preferredWidth: 20 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Txt { text: entry.modelData.label ?? ""; font.bold: entry.active && !entry.modelData.sub; elide: Text.ElideRight; Layout.fillWidth: true }
                            Txt {
                                visible: !!entry.modelData.sub
                                text: entry.modelData.sub ?? ""
                                color: Theme.dim
                                font.pixelSize: Theme.fontSize - 2
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.picked(entry.modelData.place, entry.modelData.reveal ?? "") }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
    }
}
