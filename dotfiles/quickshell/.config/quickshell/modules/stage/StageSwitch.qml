import QtQuick
import qs
import qs.components

// Stage mode for the workspace on screen, as a two-icon switch at the far end of the rail (Stage.qml): tiled (Font Awesome
// th-large) and stage (clone, windows stacked). The current mode's half is lit with the accent; a click on a half picks that
// mode. Grid mode: a cell with a hairline edge and the windows' corner radius, like the pinned tiles; otherwise its own pill.
Item {
    id: root

    required property var rail                 // the rail window: corner radius
    property bool on: false                    // the workspace is in stage mode
    signal picked(bool stage)

    readonly property real radius: Math.min(Theme.gridMode ? rail.cardRadius : Theme.pillRadius, height / 2)
    readonly property real inset: 3            // the lit half sits this far inside the edge

    Rectangle {                                // the cell
        anchors.fill: parent
        radius: root.radius
        color: Theme.gridMode ? "transparent" : Theme.pillBg
        border.width: Theme.gridMode ? Theme.hair : 0
        border.color: Theme.cardEdge
    }

    Repeater {
        model: [{ stage: false, glyph: "" }, { stage: true, glyph: "" }]

        Item {
            id: half
            required property var modelData
            required property int index
            readonly property bool current: modelData.stage === root.on
            x: index * root.width / 2
            width: root.width / 2
            height: root.height

            Rectangle {                        // lit when current, a softer plate on hover
                anchors.fill: parent
                anchors.margins: root.inset
                radius: Math.max(0, root.radius - root.inset)
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, half.current ? 0.30 : 0.15)
                opacity: half.current || area.containsMouse ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
            }
            Txt {
                anchors.centerIn: parent
                text: half.modelData.glyph
                color: half.current ? Theme.accent : Theme.dim
                font.pixelSize: Theme.fontSize + 4
            }
            MouseArea {
                id: area
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: half.current ? Qt.ArrowCursor : Qt.PointingHandCursor
                onClicked: if (!half.current) root.picked(half.modelData.stage)
            }
        }
    }
}
