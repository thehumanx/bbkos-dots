import QtQuick
import Quickshell
import qs
import qs.components
import qs.services

// The small card under the bar clock while the pointer rests on it (clock.hoverDate): the full date. A PopupWindow hung from the bar item, so it needs no layer of its own; it exists only while shown.
LazyLoader {
    id: root
    required property Item target                        // the bar item it hangs from
    property bool shown: false
    active: shown

    PopupWindow {
        id: win
        readonly property var d: clock.date
        readonly property string edge: Theme.barEdge
        readonly property int pad: Theme.shadowPad
        // Free room for the shadow on every side but the one facing the bar, where only a small gap is left so the card sits close.
        readonly property int gap: 6
        readonly property int padL: edge === "left" ? gap : pad
        readonly property int padR: edge === "right" ? gap : pad
        readonly property int padT: edge === "top" ? gap : pad
        readonly property int padB: edge === "bottom" ? gap : pad

        visible: true
        color: "transparent"
        implicitWidth: card.width + padL + padR
        implicitHeight: card.height + padT + padB
        anchor.window: root.target.QsWindow.window
        anchor.rect: {
            const p = root.target.mapToItem(null, 0, 0)
            return Qt.rect(p.x, p.y, root.target.width, root.target.height)
        }
        anchor.edges: edge === "top" ? Edges.Bottom : edge === "bottom" ? Edges.Top : edge === "left" ? Edges.Right : Edges.Left
        anchor.gravity: anchor.edges

        SystemClock { id: clock; precision: SystemClock.Minutes }

        Rectangle {
            id: card
            x: win.padL; y: win.padT
            width: col.implicitWidth + 28
            height: col.implicitHeight + 20
            radius: Theme.radius
            color: Theme.popupBg
            border.width: Theme.hair
            border.color: Theme.cardEdge
            CardShadow {}
            Column {
                id: col
                anchors.centerIn: parent
                spacing: 4
                Txt {
                    anchors.horizontalCenter: parent.horizontalCenter
                    color: Theme.fg
                    text: Qt.formatDate(win.d, "dddd, d MMMM yyyy")
                }
            }
        }
    }
}
