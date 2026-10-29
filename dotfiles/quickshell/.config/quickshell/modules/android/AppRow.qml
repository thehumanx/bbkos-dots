import QtQuick
import QtQuick.Layouts
import qs
import qs.components

// One package in the Android apps list: tick box, letter tile, name and package, safety rating, the UAD description
// (two lines, click to expand). `locked` rows (Unsafe on the Installed tab) cannot be ticked. `result` is the last
// action's outcome for this package ({ok, error}) or null.
Rectangle {
    id: root
    required property var row
    property bool selected: false
    property bool locked: false
    property var result: null
    property bool expanded: false
    signal toggled()

    readonly property string title: row.name || row.package
    readonly property color ratingColor: row.rating === "Recommended" ? Theme.accent
                                         : row.rating === "Advanced" ? Theme.accent2
                                         : row.rating === "Expert" ? Theme.warn
                                         : row.rating === "Unsafe" ? Theme.crit : Theme.dim

    function tileColor(pkg) {
        let h = 0
        for (let i = 0; i < pkg.length; i++) h = (h * 31 + pkg.charCodeAt(i)) >>> 0
        return [Theme.accent, Theme.accent2, Theme.accent3][h % 3]
    }

    implicitHeight: content.implicitHeight + 16
    radius: Theme.controlRadius
    color: selected ? Theme.accentSoft : area.containsMouse ? Theme.control : "transparent"

    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.locked ? Qt.ForbiddenCursor : Qt.PointingHandCursor
        onClicked: if (!root.locked) root.toggled()
    }

    RowLayout {
        id: content
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 10; rightMargin: 12 }
        spacing: 12

        Rectangle {                                     // tick box, or a lock for Unsafe
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 8
            implicitWidth: 18; implicitHeight: 18
            radius: 4
            color: root.selected ? Theme.accent : "transparent"
            border.width: root.locked ? 0 : 2
            border.color: root.selected ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.5)
            Txt {
                anchors.centerIn: parent
                text: root.locked ? "" : root.selected ? "" : ""
                color: root.locked ? Theme.crit : Theme.bg
                font.pixelSize: Theme.fontSize - 2
            }
        }

        Rectangle {                                     // letter tile in place of an icon
            Layout.alignment: Qt.AlignTop
            implicitWidth: 34; implicitHeight: 34
            radius: Theme.controlRadius
            color: Qt.rgba(tint.r, tint.g, tint.b, 0.22)
            readonly property color tint: root.tileColor(root.row.package)
            Txt {
                anchors.centerIn: parent
                text: (root.row.name || root.row.package.split(".").pop() || "?").charAt(0).toUpperCase()
                color: parent.tint
                font.bold: true
                font.pixelSize: Theme.fontSize + 3
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Txt { text: root.title; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                Txt {
                    visible: root.row.state !== "installed"
                    text: root.row.state === "disabled" ? "disabled" : "removed"
                    color: Theme.dim
                    font.pixelSize: Theme.fontSize - 2
                }
                Rectangle {
                    implicitWidth: rating.implicitWidth + 14; implicitHeight: 20
                    radius: 10
                    color: Qt.rgba(root.ratingColor.r, root.ratingColor.g, root.ratingColor.b, 0.18)
                    Txt {
                        id: rating
                        anchors.centerIn: parent
                        text: root.row.rating + (root.row.list ? " · " + root.row.list : "")
                        color: root.ratingColor
                        font.pixelSize: Theme.fontSize - 2
                    }
                }
            }
            Txt {
                visible: !!root.row.name
                text: root.row.package
                color: Theme.dim
                font.pixelSize: Theme.fontSize - 2
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Txt {
                visible: root.row.description !== ""
                Layout.fillWidth: true
                text: root.row.description
                color: Theme.dim
                wrapMode: Text.Wrap
                maximumLineCount: root.expanded ? 40 : 2
                elide: Text.ElideRight
                font.pixelSize: Theme.fontSize - 1
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.expanded = !root.expanded
                }
            }
            Txt {
                visible: (root.row.neededBy ?? []).length > 0
                Layout.fillWidth: true
                text: "Needed by " + (root.row.neededBy ?? []).join(", ")
                color: Theme.warn
                wrapMode: Text.Wrap
                font.pixelSize: Theme.fontSize - 2
            }
            Txt {
                visible: root.result !== null
                Layout.fillWidth: true
                text: root.result ? (root.result.ok ? " Done" : " " + root.result.error) : ""
                color: root.result && root.result.ok ? Theme.accent : Theme.crit
                wrapMode: Text.Wrap
                font.pixelSize: Theme.fontSize - 1
            }
        }
    }
}
