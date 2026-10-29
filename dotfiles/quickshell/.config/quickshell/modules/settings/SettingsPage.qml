import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Frame of one settings page (one tab of a sidebar entry): a dim note, then the page's content. The window draws the title and
// the tabs above it (SettingsWindow). The content is normally a few `SettingsSection`s (titled cards). A page that has not been split into sections sets `card: true`,
// which wraps its controls in one plain card. Scrolls (mouse wheel, drag) when the content is taller than the window, with no scroll bar (the owner's choice). An empty `note` hides the line.
Item {
    id: root
    property string note: ""
    property bool card: false
    // Set by a control that needs the pointer while held (a drag handle): the page stops scrolling until it is cleared.
    property bool scrollLocked: false
    default property alias content: body.data

    // Search hit (SettingsStore.reveal): find the row with that label, scroll it into view and light it up for a moment.
    // Tried a few times while the page lays itself out after loading.
    property int revealTries: 0
    function findRow(item, label) {
        for (const c of item.children) {
            if (c.visible && c.label === label && c.flash !== undefined) return c
            const r = findRow(c, label)
            if (r) return r
        }
        return null
    }
    function tryReveal() {
        const label = SettingsStore.reveal
        if (label === "") return
        const row = findRow(body, label)
        if (!row || row.height === 0) { if (++revealTries < 10) revealTimer.restart(); else SettingsStore.reveal = ""; return }
        const y = row.mapToItem(column, 0, 0).y
        flick.contentY = Math.max(0, Math.min(y - 80, flick.contentHeight - flick.height))
        row.flash = true
        flashTimer.target = row
        flashTimer.restart()
        SettingsStore.reveal = ""
    }
    Connections { target: SettingsStore; function onRevealChanged() { root.revealTries = 0; revealTimer.restart() } }
    Component.onCompleted: revealTimer.restart()
    Timer { id: revealTimer; interval: 60; onTriggered: root.tryReveal() }
    Timer { id: flashTimer; property var target: null; interval: 1400; onTriggered: if (target) target.flash = false }

    Flickable {
        id: flick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight + 24
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: !root.scrollLocked

        ColumnLayout {
            id: column
            width: flick.width
            spacing: 4

            Txt {
                visible: root.note !== ""
                text: root.note
                color: Theme.dim
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.bottomMargin: 8
            }
            Item { Layout.preferredHeight: 4 }

            Rectangle {                      // the page's card, or nothing visible when the page is made of sections
                Layout.fillWidth: true
                implicitHeight: Math.ceil((body.implicitHeight + (root.card ? 32 : 0)) / 2) * 2
                radius: Theme.radius
                color: root.card ? Theme.popupBg : "transparent"

                ColumnLayout {
                    id: body
                    anchors { left: parent.left; right: parent.right; top: parent.top }
                    anchors.margins: root.card ? 16 : 0
                    anchors.leftMargin: root.card ? 20 : 0
                    anchors.rightMargin: root.card ? 20 : 0
                    spacing: root.card ? 12 : 28
                }
            }
        }
    }
}
