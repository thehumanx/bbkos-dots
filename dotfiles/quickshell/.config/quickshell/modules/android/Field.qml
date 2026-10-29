import QtQuick
import qs
import qs.components

// One-line text field with a placeholder, the look of SettingText. `text` is the typed value; accepted() on Enter.
Rectangle {
    id: root
    property alias text: input.text
    property string placeholder: ""
    property alias inputMethodHints: input.inputMethodHints
    signal accepted()

    implicitWidth: 200
    implicitHeight: 32
    radius: Theme.controlRadius
    color: Theme.inset
    border.width: input.activeFocus ? 2 : Theme.hair
    border.color: input.activeFocus ? Theme.accent : Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, 0.3)

    function focusInput() { input.forceActiveFocus() }

    TextInput {
        id: input
        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
        verticalAlignment: TextInput.AlignVCenter
        clip: true
        color: Theme.fg
        font.family: Theme.font
        font.pixelSize: Theme.fontSize
        selectionColor: Theme.accent
        selectedTextColor: Theme.bg
        onAccepted: root.accepted()
    }
    Txt {
        visible: input.text === "" && !input.activeFocus
        anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
        text: root.placeholder
        color: Theme.dim
    }
}
