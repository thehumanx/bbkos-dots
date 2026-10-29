import QtQuick
import qs

// The click area of a bar widget. A bare `MouseArea { anchors.fill: parent }` on a widget only covers its icon and text,
// a few pixels on a 36 px bar. This one covers the whole BarItem the widget sits in (its pill, padding and the bar's full
// thickness), so a click anywhere on the widget's box lands. Put it inside the widget, in place of the MouseArea; it takes
// the same signals (onClicked, onWheel, acceptedButtons, ...).
// `crossOnly` is for a widget made of several clickable parts (workspace numbers, tray icons): each part keeps its own
// length along the bar (plus half the widget gap at either end, so no dead strip lies between two parts) and takes the
// bar's full thickness. Outside a BarItem it falls back to the parent's own box.
MouseArea {
    id: root
    property bool crossOnly: false

    // The BarItem around the widget (components/BarItem.qml marks itself with isBarItem).
    readonly property Item slot: {
        let p = parent
        while (p && p.isBarItem !== true) p = p.parent
        return p
    }
    // Where the parent's origin sits inside the BarItem. Reads x and y of every item in between, so it stays live.
    readonly property point origin: {
        let x = 0, y = 0, p = parent
        while (p && p !== slot) { x += p.x; y += p.y; p = p.parent }
        return Qt.point(x, y)
    }
    readonly property real grow: Theme.barItemGap / 2
    readonly property bool alongX: crossOnly && !Theme.barVertical      // the part keeps its own width
    readonly property bool alongY: crossOnly && Theme.barVertical       // the part keeps its own height

    cursorShape: Qt.PointingHandCursor
    x: !slot ? 0 : alongX ? -grow : -origin.x
    y: !slot ? 0 : alongY ? -grow : -origin.y
    width: !slot ? parent.width : alongX ? parent.width + 2 * grow : slot.width
    height: !slot ? parent.height : alongY ? parent.height + 2 * grow : slot.height

    // Where the widget sits along the bar, in screen pixels (x on a horizontal bar, y on a vertical one): a popup opened
    // from this widget centres on it (services/PanelState, modules/panels/Panels.qml). The bar window spans the screen
    // edge, so window and screen coordinates agree along the bar.
    function center(): real {
        const item = slot ? slot : root
        const p = item.mapToItem(null, item.width / 2, item.height / 2)
        return Theme.barVertical ? p.y : p.x
    }
}
