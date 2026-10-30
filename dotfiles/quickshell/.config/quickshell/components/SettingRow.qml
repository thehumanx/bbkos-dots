import QtQuick
import QtQuick.Layouts
import qs
import qs.services
import "../modules/settings/Pages.js" as Pages

// The frame of one setting: a label (and an optional dim hint under it) on the left, the control on the right, 12 px of air
// above and below and a hairline between rows. The children go into the control area (a RowLayout, so they take Layout.*).
// The divider is hidden on the first row of its card. The Setting* controls build on this; a disabled row dims its parts
// itself (the label here, each control by its own `enabled` handling).
// With a `key` (a settings.py key) the row also:
// - shows a small accent dot after the label while the value differs from the default; on hover the dot becomes a reset
//   button that needs a second click within 4 s ("Reset to 12"), like every reset (docs/design.md section 5);
// - shows "Set by grid mode" in place of the control while grid mode replaces this key (SettingsStore.gridLocked);
// - with `lockedBy` ("the bar style"), shows "Set by the bar style" in place of the control for a key something else decides.
// `describe(value)` turns a value into the words of "Reset to ..."; the Setting* controls override it.
Item {
    id: root
    property string label
    property string hint: ""
    property real labelWidth: 260
    property string key: ""
    property string lockedBy: ""                  // a key that no longer applies on its own: "Set by " + this, no control
    // A place where this setting really lives ("appearance/style", or "appearance/style#Font size" to light up that row
    // there): shown under the hint as a link (the Accessibility page gathers rows from other pages).
    property string link: ""
    default property alias control: slot.data

    readonly property bool modified: key !== "" && SettingsStore.modified(key)
    readonly property bool gridLocked: key !== "" && SettingsStore.gridLocked(key)
    readonly property bool locked: gridLocked || lockedBy !== ""
    property bool armed: false
    property bool flash: false                    // set by the search for a moment: the row lights up once
    function describe(v): string { return String(v) }

    // The first visible row of its parent (sibling Repeaters and spacers have no height of their own).
    readonly property bool first: {
        const p = parent
        if (!p || !p.visibleChildren) return true
        for (let i = 0; i < p.visibleChildren.length; i++) {
            const c = p.visibleChildren[i]
            if (c === root) return true
            if (c.implicitHeight > 0) return false
        }
        return true
    }

    Layout.fillWidth: true
    implicitHeight: Math.ceil((Math.max(labelColumn.implicitHeight, slot.implicitHeight, lockedNote.implicitHeight) + 24) / 2) * 2

    Rectangle {                                   // search highlight
        anchors { fill: parent; leftMargin: -12; rightMargin: -12 }
        radius: Theme.controlRadius
        color: Theme.accentSoft
        opacity: root.flash ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.durLarge; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    }

    Rectangle {
        visible: !root.first
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Theme.hair
        color: Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.10)
    }

    HoverHandler { id: rowHover }

    RowLayout {
        anchors { fill: parent; topMargin: 12; bottomMargin: 12 }
        spacing: 16

        ColumnLayout {
            id: labelColumn
            Layout.preferredWidth: root.labelWidth
            Layout.maximumWidth: root.labelWidth
            Layout.alignment: Qt.AlignVCenter
            spacing: 2
            RowLayout {
                spacing: 8
                Layout.fillWidth: true
                Txt {
                    text: root.label
                    wrapMode: Text.WordWrap
                    Layout.maximumWidth: root.labelWidth - (marker.visible ? 96 : 0)   // room for the hover pill: no reflow on hover
                    opacity: root.enabled ? 1 : 0.4
                }
                Item {                            // modified marker / reset
                    id: marker
                    visible: root.modified && root.enabled && !root.gridLocked
                    implicitWidth: 8                      // fixed: the pill below floats over the free space after it
                    implicitHeight: 20
                    z: 2
                    Rectangle {
                        visible: !(rowHover.hovered || root.armed)
                        anchors.centerIn: parent
                        width: 6; height: 6; radius: Theme.gridSquare ? 0 : 3
                        color: Theme.accent
                    }
                    Rectangle {
                        visible: rowHover.hovered || root.armed
                        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                        width: resetText.implicitWidth + 16
                        height: 20
                        radius: Theme.controlRadius
                        color: resetArea.containsMouse ? Theme.accentSoft : Theme.control
                        border.width: Theme.hair
                        border.color: root.armed ? Theme.crit : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.2)
                        Txt {
                            id: resetText
                            anchors.centerIn: parent
                            text: root.armed ? "Reset to " + root.describe(SettingsStore.defaultOf(root.key)) : "  Default"
                            color: root.armed ? Theme.crit : Theme.dim
                            font.pixelSize: Theme.fontSize - 2
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
                                SettingsStore.reset(root.key)
                            }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
            }
            Txt {
                visible: root.link !== ""
                readonly property var place: Pages.resolve(root.link.split("#")[0])
                readonly property var page: place ? Pages.find(place.page) : null
                text: "\uf08e  " + (page ? page.label + (page.tabs.length > 1 ? " › " + page.tabs[place.tab].label : "") : root.link)
                color: linkArea.containsMouse ? Theme.accent : Theme.dim
                font.pixelSize: Theme.fontSize - 1
                font.underline: linkArea.containsMouse
                MouseArea {
                    id: linkArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        const parts = root.link.split("#")
                        SettingsStore.openPage(parts[0])
                        SettingsStore.reveal = parts.length > 1 ? parts[1] : root.label
                    }
                }
            }
            Txt {
                visible: root.hint !== ""
                text: root.hint
                color: Theme.dim
                font.pixelSize: Theme.fontSize - 1
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                opacity: root.enabled ? 1 : 0.4
            }
        }
        RowLayout {
            id: slot
            visible: !root.locked
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 8
        }
        Txt {
            id: lockedNote
            visible: root.locked
            text: root.gridLocked ? "Set by grid mode  ·  " + root.describe(SettingsStore.gridValue(root.key)) : "Set by " + root.lockedBy
            color: Theme.dim
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
        }
    }

    Timer { id: disarm; interval: 4000; onTriggered: root.armed = false }
}
