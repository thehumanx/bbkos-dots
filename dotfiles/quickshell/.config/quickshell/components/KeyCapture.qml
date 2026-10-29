import QtQuick
import QtQuick.Layouts
import qs

// Records one key press with its modifiers. A pure input: `mods` / `key` only display what the parent holds; a captured
// combo is emitted as captured(mods, key) (mods in canonical order SUPER, CTRL, ALT, SHIFT; key as an xkb name).
// Escape while recording cancels. Modifier-only presses are ignored until a real key arrives.
// Note: a key Hyprland itself binds (for example Super+Q) never reaches the window, so it cannot be recorded.
Rectangle {
    id: root
    property var mods: []
    property string key: ""
    property bool recording: false
    signal captured(var mods, string key)

    readonly property string combo: key === "" ? "" : mods.concat([key]).join(" + ")

    implicitHeight: 32
    implicitWidth: row.implicitWidth + 16
    radius: Theme.controlRadius
    color: Theme.inset
    border.width: Theme.hair
    border.color: recording ? Theme.accent : Theme.dim
    focus: recording

    readonly property var named: ({
        [Qt.Key_Return]: "Return", [Qt.Key_Enter]: "Return", [Qt.Key_Space]: "space", [Qt.Key_Tab]: "Tab",
        [Qt.Key_Backtab]: "Tab", [Qt.Key_Backspace]: "BackSpace", [Qt.Key_Delete]: "Delete", [Qt.Key_Insert]: "Insert",
        [Qt.Key_Home]: "Home", [Qt.Key_End]: "End", [Qt.Key_PageUp]: "Prior", [Qt.Key_PageDown]: "Next",
        [Qt.Key_Left]: "left", [Qt.Key_Right]: "right", [Qt.Key_Up]: "up", [Qt.Key_Down]: "down",
        [Qt.Key_Print]: "Print", [Qt.Key_Comma]: "comma", [Qt.Key_Period]: "period", [Qt.Key_Minus]: "minus",
        [Qt.Key_Equal]: "equal", [Qt.Key_Slash]: "slash", [Qt.Key_Backslash]: "backslash",
        [Qt.Key_Semicolon]: "semicolon", [Qt.Key_Apostrophe]: "apostrophe", [Qt.Key_BracketLeft]: "bracketleft",
        [Qt.Key_BracketRight]: "bracketright", [Qt.Key_QuoteLeft]: "grave",
        [Qt.Key_VolumeUp]: "XF86AudioRaiseVolume", [Qt.Key_VolumeDown]: "XF86AudioLowerVolume",
        [Qt.Key_VolumeMute]: "XF86AudioMute", [Qt.Key_MediaPlay]: "XF86AudioPlay", [Qt.Key_MediaNext]: "XF86AudioNext",
        [Qt.Key_MediaPrevious]: "XF86AudioPrev", [Qt.Key_MonBrightnessUp]: "XF86MonBrightnessUp",
        [Qt.Key_MonBrightnessDown]: "XF86MonBrightnessDown"
    })
    // Shift turns these into other symbols; record the key on the cap instead.
    readonly property var unshifted: ({
        [Qt.Key_Exclam]: "1", [Qt.Key_At]: "2", [Qt.Key_NumberSign]: "3", [Qt.Key_Dollar]: "4", [Qt.Key_Percent]: "5",
        [Qt.Key_AsciiCircum]: "6", [Qt.Key_Ampersand]: "7", [Qt.Key_Asterisk]: "8", [Qt.Key_ParenLeft]: "9",
        [Qt.Key_ParenRight]: "0", [Qt.Key_Underscore]: "minus", [Qt.Key_Plus]: "equal", [Qt.Key_Less]: "comma",
        [Qt.Key_Greater]: "period", [Qt.Key_Question]: "slash", [Qt.Key_Colon]: "semicolon",
        [Qt.Key_QuoteDbl]: "apostrophe", [Qt.Key_BraceLeft]: "bracketleft", [Qt.Key_BraceRight]: "bracketright",
        [Qt.Key_Bar]: "backslash", [Qt.Key_AsciiTilde]: "grave"
    })

    function keyName(k: int): string {
        if (k >= Qt.Key_A && k <= Qt.Key_Z) return String.fromCharCode(k)
        if (k >= Qt.Key_0 && k <= Qt.Key_9) return String.fromCharCode(k)
        if (k >= Qt.Key_F1 && k <= Qt.Key_F12) return "F" + (k - Qt.Key_F1 + 1)
        return root.named[k] ?? root.unshifted[k] ?? ""
    }

    function modList(m: int): var {
        const out = []
        if (m & Qt.MetaModifier) out.push("SUPER")
        if (m & Qt.ControlModifier) out.push("CTRL")
        if (m & Qt.AltModifier) out.push("ALT")
        if (m & Qt.ShiftModifier) out.push("SHIFT")
        return out
    }

    function begin(): void { recording = true; forceActiveFocus() }

    Keys.onPressed: event => {
        if (!root.recording) return
        event.accepted = true
        if (event.key === Qt.Key_Escape) { root.recording = false; return }
        const name = root.keyName(event.key)
        if (name === "") return                       // a modifier on its own, or a key with no name here
        root.recording = false
        root.captured(root.modList(event.modifiers), name)
    }
    onActiveFocusChanged: if (!activeFocus) recording = false

    RowLayout {
        id: row
        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
        spacing: 10
        Txt {
            text: root.recording ? "Press a key combination (Esc cancels)" : (root.combo !== "" ? root.combo : "No key set")
            color: root.recording || root.combo === "" ? Theme.dim : Theme.fg
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Txt { text: root.recording ? "" : "Record"; color: Theme.accent }
    }
    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.begin() }
}
