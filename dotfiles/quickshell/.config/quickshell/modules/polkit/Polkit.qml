import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.Polkit
import qs
import qs.components

// Polkit authentication agent: GUI apps and pkexec ask here for a password.
// The window exists only while an authentication request is active.
Scope {
    PolkitAgent { id: agent }

    LazyLoader {
        active: agent.isActive

        PanelWindow {
            implicitWidth: 420
            implicitHeight: col.implicitHeight + 40
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
            WlrLayershell.namespace: "bbkos-polkit"
            color: "transparent"

            readonly property var flow: agent.flow

            Rectangle {
                anchors.fill: parent
                radius: Theme.radius
                color: Theme.popupBg

                ColumnLayout {
                    id: col
                    anchors { fill: parent; margins: 20 }
                    spacing: 10

                    Txt { text: "Authentication required"; font.bold: true; font.pixelSize: Theme.fontSize + 2 }
                    Txt { text: flow ? flow.message : ""; color: Theme.dim; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Txt {
                        text: flow ? flow.supplementaryMessage : ""
                        visible: text !== ""
                        color: flow && flow.supplementaryIsError ? Theme.crit : Theme.dim
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 36
                        radius: Theme.controlRadius
                        color: Theme.inset
                        visible: flow && flow.isResponseRequired

                        TextInput {
                            id: input
                            anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                            verticalAlignment: TextInput.AlignVCenter
                            echoMode: flow && flow.responseVisible ? TextInput.Normal : TextInput.Password
                            color: Theme.fg
                            font.family: Theme.font
                            font.pixelSize: Theme.fontSize
                            focus: true
                            Component.onCompleted: forceActiveFocus()
                            Keys.onEscapePressed: flow.cancelAuthenticationRequest()
                            Keys.onReturnPressed: { flow.submit(text); text = "" }
                        }
                        Txt {
                            text: flow ? flow.inputPrompt : ""
                            color: Theme.dim
                            visible: input.text === ""
                            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                        }
                    }

                    RowLayout {
                        Layout.alignment: Qt.AlignRight
                        spacing: 10
                        Txt {
                            text: "Cancel"; color: Theme.dim; padding: 6
                            MouseArea { anchors.fill: parent; onClicked: flow.cancelAuthenticationRequest() }
                        }
                        Txt {
                            text: "Authenticate"; color: Theme.accent; font.bold: true; padding: 6
                            MouseArea { anchors.fill: parent; onClicked: { flow.submit(input.text); input.text = "" } }
                        }
                    }
                }
            }
        }
    }
}
