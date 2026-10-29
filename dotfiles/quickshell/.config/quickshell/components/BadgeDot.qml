import QtQuick
import qs

// A small dot at the top right corner of a bar widget's icon: "something is waiting" without a count (bar.iconsOnly).
// Put it inside the widget's Txt; `shown` turns it on and `dotColor` is a Theme token. A ring in the bar's own colour
// keeps it apart from the glyph, whatever colour that is. An even size, so it lands on whole physical pixels.
Rectangle {
    property bool shown: false
    property color dotColor: Theme.accent
    width: 8
    height: 8
    radius: Theme.gridSquare ? 0 : 4
    x: parent.width - width + 2
    y: 0
    color: dotColor
    border.width: 1
    border.color: Theme.bg
    visible: shown
}
