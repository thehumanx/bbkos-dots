import QtQuick
import QtQuick.Layouts
import Quickshell
import qs
import qs.components
import qs.services

// Power menu (power key). Lock, suspend and hibernate act at once; log out, reboot and power off need a second click
// within 4 seconds (they end running apps; a stray click must not do it). A failed action shows a notification.
ColumnLayout {
    id: root
    spacing: 2

    property int armed: -1

    readonly property var actions: [
        { icon: "", label: "Lock",      cmd: ["bbkos-lock"],                          confirm: false },
        { icon: "", label: "Suspend",   cmd: ["systemctl", "suspend-then-hibernate"], confirm: false },   // same as closing the lid
        { icon: "", label: "Hibernate", cmd: ["systemctl", "hibernate"],              confirm: false },
        { icon: "", label: "Log out",   cmd: ["uwsm", "stop"],                        confirm: true },
        { icon: "", label: "Reboot",    cmd: ["systemctl", "reboot"],                 confirm: true },
        { icon: "", label: "Power off", cmd: ["systemctl", "poweroff"],               confirm: true }
    ]

    function run(i) {
        const a = actions[i]
        if (a.confirm && armed !== i) { armed = i; disarm.restart(); return }
        PanelState.close()
        Quickshell.execDetached(["sh", "-c", '"$@" || notify-send -u critical "Power menu" "$1 failed"', "sh"].concat(a.cmd))
    }

    Timer { id: disarm; interval: 4000; onTriggered: root.armed = -1 }

    PopupHeader { title: "Power" }

    Repeater {
        model: root.actions
        delegate: Rectangle {
            required property var modelData
            required property int index
            readonly property bool isArmed: root.armed === index
            Layout.fillWidth: true
            implicitHeight: 36
            radius: Theme.controlRadius
            color: isArmed ? Theme.crit : (hover.containsMouse ? Theme.control : "transparent")

            RowLayout {
                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                spacing: 10
                Txt { text: modelData.icon; color: isArmed ? Theme.bg : Theme.fg; Layout.preferredWidth: 20 }
                Txt { text: isArmed ? "Click again to " + modelData.label.toLowerCase() : modelData.label; color: isArmed ? Theme.bg : Theme.fg; Layout.fillWidth: true }
            }
            MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.run(index) }
        }
    }
}
