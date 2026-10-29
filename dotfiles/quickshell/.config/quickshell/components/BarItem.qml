import QtQuick
import qs

// The wrapper every bar widget goes in: `BarItem { MyWidget {} }`. It owns the look that follows the bar settings, so a
// widget needs no styling of its own: the individual pill (when Theme.barPills is "individual"), the pill radius, the
// bar's thickness and orientation. Set `active: false` to hide the item (and its pill) while the widget has nothing to
// show; do not hide the widget itself, a hidden widget would still leave an empty pill.
// One content item (the widget). Sizes to it; centred on the bar's cross axis.
Item {
    id: root
    default property alias content: holder.data
    property bool active: true
    // The widget's popup or window is open: an accent-tinted plate sits behind it, so it is clear which
    // widget opened what. The widget's own colours are not touched.
    property bool highlighted: false

    readonly property bool isBarItem: true          // BarHit finds its way up to this item by the marker
    readonly property bool vertical: Theme.barVertical
    readonly property bool pill: Theme.barPills === "individual"
    // Cross-axis size: the bar's thickness, less a 4 px margin each side when anything draws a pill.
    // Grid mode: the cell fills the bar's thickness, edge to edge.
    readonly property int cross: Theme.barPills === "off" || Theme.gridMode ? Theme.barHeight : Theme.barHeight - 8
    // An individual pill (and so grid mode) has 8 px of its own; Theme.barItemPad (bar.md) is added in every bar mode.
    readonly property int pad: (pill ? 8 : 0) + Theme.barItemPad

    visible: active
    implicitWidth: vertical ? cross : holder.childrenRect.width + 2 * pad
    implicitHeight: vertical ? holder.childrenRect.height + 2 * pad : cross

    Rectangle {
        anchors.fill: parent
        visible: root.pill
        radius: Theme.pillRadius
        color: Theme.pillBg
        border.width: Theme.gridMode ? Theme.hair : 0      // grid mode: a hairline cell (BarSection overlaps neighbours by one hairline)
        border.color: Theme.cardEdge
    }

    Rectangle {                              // active plate: a little wider than the box along the bar when there is no pill
        readonly property real along: root.pill ? 0 : 6
        x: root.vertical ? 0 : -along
        y: root.vertical ? -along : 0
        width: root.width + (root.vertical ? 0 : 2 * along)
        height: root.height + (root.vertical ? 2 * along : 0)
        radius: root.pill ? Theme.pillRadius : Theme.controlRadius
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.30)
        opacity: root.highlighted ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.durFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    }

    Item {
        id: holder
        width: childrenRect.width
        height: childrenRect.height
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
    }
}
