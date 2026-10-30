import QtQuick
import QtQuick.Layouts
import qs
import qs.services

// A titled group of settings in one rounded card: `SettingsSection { title: "Rail"; SettingSlider {...} ... }`. The
// children are rows (SettingRow and the Setting* controls) stacked with hairline dividers; anything else works too.
// While any row in the card (at any depth) differs from its default, the title line shows "Reset these" at the right:
// a second click within 4 s puts exactly those keys back, in one tool run (SettingsStore.resetMany).
ColumnLayout {
    id: root
    property string title
    property string description: ""
    property bool padded: false          // free-form content (no rows): 16 px above and below
    default property alias content: body.data
    property bool armed: false

    // Keys of the visible rows in this card that differ from their default. Read in a binding, so it follows every row.
    readonly property var modifiedKeys: {
        const out = []
        const walk = item => {
            for (const c of item.children) {
                if (!c.visible) continue
                if (typeof c.key === "string" && c.key !== "" && c.modified === true && c.locked !== true && !out.includes(c.key)) out.push(c.key)
                walk(c)
            }
        }
        walk(body)
        return out
    }

    Layout.fillWidth: true
    spacing: 8

    RowLayout {
        visible: root.title !== "" || root.modifiedKeys.length > 0
        Layout.fillWidth: true
        Layout.preferredHeight: 22
        Txt { text: root.title; font.bold: true; font.pixelSize: Theme.fontSize + 1; Layout.fillWidth: true }
        Rectangle {
            visible: root.modifiedKeys.length > 0
            implicitWidth: resetText.implicitWidth + 16
            implicitHeight: 22
            radius: Theme.controlRadius
            color: resetArea.containsMouse ? Theme.accentSoft : "transparent"
            border.width: root.armed ? Theme.hair : 0
            border.color: Theme.crit
            Txt {
                id: resetText
                anchors.centerIn: parent
                text: root.armed ? "Click again to reset " + root.modifiedKeys.length + (root.modifiedKeys.length === 1 ? " setting" : " settings")
                                 : "  Reset these"
                color: root.armed ? Theme.crit : Theme.dim
                font.pixelSize: Theme.fontSize - 1
            }
            MouseArea {
                id: resetArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (!root.armed) { root.armed = true; disarm.restart(); return }
                    root.armed = false
                    disarm.stop()
                    SettingsStore.resetMany(root.modifiedKeys)
                }
            }
        }
    }
    Txt { visible: root.description !== ""; text: root.description; color: Theme.dim; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: Math.ceil((body.implicitHeight + (root.padded ? 32 : 0)) / 2) * 2
        radius: Theme.radius
        color: Theme.popupBg
        border.width: Theme.hair
        border.color: Theme.cardEdge

        ColumnLayout {
            id: body
            anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 20; rightMargin: 20; topMargin: root.padded ? 16 : 0 }
            spacing: root.padded ? 12 : 0
        }
    }

    Timer { id: disarm; interval: 4000; onTriggered: root.armed = false }
}
