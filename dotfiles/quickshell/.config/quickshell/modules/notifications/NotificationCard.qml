import QtQuick
import QtQuick.Layouts
import Quickshell.Services.Notifications
import qs
import qs.components
import qs.services

// One popup. Click marks its history entry read, runs its default action and dismisses it; a right click (or two-finger
// tap) only closes it (and marks it read); normal and low urgency expire after the sender's
// timeout, or notifications.timeout (6 s default); a critical one stays unless notifications.criticalSticky is off.
Rectangle {
    id: card
    required property var modelData
    required property int index
    property bool popupAtLeft: false                              // the corner the stack sits in: the card slides in from that side
    readonly property bool critical: modelData.urgency === NotificationUrgency.Critical

    Layout.fillWidth: true
    implicitHeight: content.implicitHeight + 20
    radius: Theme.controlRadius + 2
    color: Theme.popupBg
    border.width: Theme.hair
    border.color: critical ? Theme.crit : Theme.cardEdge

    // Arrives from the screen edge it sits at (docs/modules/motion.md): 24 px and a fade, strong ease-out; reduce
    // motion keeps the fade. It leaves with the stack (the compositor fades the last one out).
    readonly property int fromSide: card.popupAtLeft ? -1 : 1
    property real p: 0
    Component.onCompleted: p = 1
    Behavior on p { NumberAnimation { duration: Theme.durEnter + 40; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut } }
    opacity: p
    transform: Translate { x: Theme.reduceMotion ? 0 : card.fromSide * 24 * (1 - card.p) }

    CardShadow {}

    ColumnLayout {
        id: content
        anchors { fill: parent; margins: 10 }
        spacing: 2

        // A picture the sender attached. A wide or tall one (a screenshot, omasnap) is a thumbnail across the card; a
        // square-ish one is a logo or an avatar (Claude sends its app logo as the image) and gets a 40 px tile beside the
        // text, as mako and swaync show it. A plain icon name (image://icon/) is the small app icon below.
        Image {
            id: pic
            readonly property bool has: (Notifs.cfg.showPictures ?? true) && card.modelData.image !== "" && !String(card.modelData.image).startsWith("image://icon/") && status === Image.Ready
            readonly property real aspect: implicitWidth / Math.max(1, implicitHeight)
            readonly property bool wide: has && (aspect > 1.33 || aspect < 0.75)
            visible: wide
            source: card.modelData.image
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? Math.min(180, width * implicitHeight / Math.max(1, implicitWidth)) : 0
            fillMode: Image.PreserveAspectFit
            sourceSize.width: 720                                // twice the card's width: sharp on the thumbnail
            smooth: true
            asynchronous: true
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Image {
                visible: pic.has && !pic.wide
                source: visible ? card.modelData.image : ""
                sourceSize: Qt.size(80, 80)
                Layout.preferredWidth: 40
                Layout.preferredHeight: 40
                Layout.alignment: Qt.AlignTop
                fillMode: Image.PreserveAspectFit
                smooth: true
                asynchronous: true
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Image {                                      // the app's icon, when it sent one that exists in the icon theme
                        readonly property string url: Notifs.iconUrl(Notifs.iconOf(card.modelData))
                        visible: url !== ""
                        source: url
                        sourceSize: Qt.size(32, 32)
                        Layout.preferredWidth: 16
                        Layout.preferredHeight: 16
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    Txt { text: card.modelData.appName; textFormat: Text.PlainText; color: Theme.dim; font.pixelSize: Theme.fontSize - 2; Layout.fillWidth: true; elide: Text.ElideRight }
                }
                Txt { text: card.modelData.summary; textFormat: Text.PlainText; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                Txt { text: card.modelData.body; textFormat: Text.PlainText; color: Theme.dim; visible: text !== ""; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight }
            }
        }
    }

    Timer {
        readonly property var cfg: Notifs.cfg
        running: (!card.critical || cfg.criticalSticky === false)
        interval: (cfg.senderTimeout ?? true) && card.modelData.expireTimeout > 0 ? card.modelData.expireTimeout * 1000 : (cfg.timeout ?? 6) * 1000
        onTriggered: card.modelData.expire()
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton           // a two-finger tap on the touchpad arrives as the right button
        // Right: close it without the default action. Left: the default action first (e.g. "edit" on a screenshot; most
        // senders have none), then close it.
        onClicked: ev => Notifs.activate(card.modelData.id, ev.button !== Qt.RightButton)
    }
}
