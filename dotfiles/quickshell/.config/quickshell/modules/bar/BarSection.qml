import QtQuick
import QtQuick.Layouts
import qs

// One of the bar's three groups (start, centre, end). It fills the bar along its length, and lays its BarItems out from
// its own edge: `align` "start" (left or top), "end" (right or bottom), or "centre". It keeps no size of its own, so a
// group is never cropped by a size measured before its items were laid out. When Theme.barPills is "grouped", one pill
// is drawn around the group (none while every item is hidden).
Item {
    id: root
    default property alias content: grid.data
    property string align: "start"
    // Hugging bar (Theme.barHug): Bar.qml puts the groups one after another and gives each its own start along the bar.
    property bool hug: false
    property real hugPos: 0

    readonly property bool vertical: Theme.barVertical
    readonly property bool grouped: Theme.barPills === "grouped"
    readonly property int pad: grouped ? 10 : 0
    readonly property int inset: Theme.gap + pad     // from the bar's edge to the items
    // How much of the bar this group needs along it, its pill padding included (0 while every item is hidden).
    readonly property real extent: grid.alongSize > 0 ? grid.alongSize + 2 * pad : 0

    // Where the group's items start and end along the bar (Bar.qml's grid mode fills the stretches between groups).
    readonly property real spanFrom: grid.alongPos
    readonly property real spanTo: grid.alongPos + grid.alongSize

    // Across the bar: the bar's thickness. Along it: whatever the parent gives (Bar.qml fills the bar).
    implicitWidth: vertical ? Theme.barHeight : 0
    implicitHeight: vertical ? 0 : Theme.barHeight

    Rectangle {
        x: root.vertical ? (root.width - width) / 2 : grid.x - root.pad
        y: root.vertical ? grid.y - root.pad : (root.height - height) / 2
        width: root.vertical ? Theme.barHeight - 8 : grid.width + 2 * root.pad
        height: root.vertical ? grid.height + 2 * root.pad : Theme.barHeight - 8
        visible: root.grouped && grid.width > 0 && grid.height > 0
        radius: Theme.pillRadius
        color: Theme.pillBg
    }

    GridLayout {
        id: grid
        // Plain x/y rather than anchors: anchors that flip to undefined when the bar changes position can leave the group
        // stranded until the shell reloads. Along the bar the group sits at its edge (or centred), across it it centres.
        readonly property real along: root.vertical ? root.height : root.width
        readonly property real alongSize: root.vertical ? height : width
        readonly property real alongPos: root.hug ? root.hugPos
            : root.align === "start" ? root.inset
            : root.align === "end" ? along - alongSize - root.inset
            : (along - alongSize) / 2
        x: root.vertical ? (root.width - width) / 2 : alongPos
        y: root.vertical ? alongPos : (root.height - height) / 2
        columns: root.vertical ? 1 : 1000
        // Grid mode: cells overlap by one hairline, so two neighbours share one line instead of drawing two.
        rowSpacing: Theme.gridMode ? -Theme.hair : Theme.barItemGap
        columnSpacing: Theme.gridMode ? -Theme.hair : Theme.barItemGap
    }
}
