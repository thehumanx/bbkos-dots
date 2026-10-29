import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs

// Emoji picker (docs/modules/emoji.md). `qs ipc call emoji toggle` (Super+;) opens a search box and a grid; Enter or a click
// types the emoji into the window that had the focus (wtype), the same way Omarchy's picker is used. The names come from
// emoji.json, generated from the Unicode list by scripts/build-emoji-data.py. The window exists only while open; recents
// (16) are kept in the shell's state directory. If wtype is not installed the emoji is copied to the clipboard instead.
Scope {
    id: root
    property bool open: false
    property var emoji: []                        // [[char, name, group], ...] in Unicode order
    property var recent: []                       // chars, newest first

    readonly property int maxRecent: 16

    IpcHandler {
        target: "emoji"
        function toggle(): void { root.open = !root.open }
        function close(): void { root.open = false }
        function pick(char: string): void { root.type(char) }          // test hook: type this text into the focused window
        function status(): string { return JSON.stringify({ open: root.open, count: root.emoji.length, recent: root.recent }) }
    }

    FileView {
        id: data
        path: Quickshell.shellPath("modules/emoji/emoji.json")
        blockLoading: true
        printErrors: false
        onLoaded: {
            try { root.emoji = JSON.parse(text()).emoji } catch (e) { console.warn("Emoji: emoji.json is not valid: " + e) }
        }
    }

    FileView {
        id: store
        path: Quickshell.statePath("emoji-recent.json")
        blockLoading: true
        atomicWrites: true
        printErrors: false
        onLoaded: {
            try {
                const v = JSON.parse(text())
                if (Array.isArray(v)) root.recent = v.filter(c => typeof c === "string" && c.length > 0 && c.length < 20).slice(0, root.maxRecent)
            } catch (e) { root.recent = [] }
        }
    }

    function remember(char: string): void {
        recent = [char].concat(recent.filter(c => c !== char)).slice(0, maxRecent)
        store.setText(JSON.stringify(recent))
    }

    // Words of the query must all appear in the name. Empty query: the recents first, then everything else.
    function search(query: string): var {
        const tokens = query.toLowerCase().split(/\s+/).filter(t => t !== "")
        if (tokens.length === 0) {
            const byChar = {}
            for (const e of emoji) byChar[e[0]] = e
            const first = recent.filter(c => byChar[c]).map(c => byChar[c])
            const seen = new Set(first.map(e => e[0]))
            return first.concat(emoji.filter(e => !seen.has(e[0])))
        }
        return emoji.filter(e => tokens.every(t => e[1].includes(t)))
    }

    // Type into the window that has the focus once the picker is gone. The emoji is an argument, never part of the
    // shell text; no wtype -> copy it so Ctrl+V still works.
    property string pending: ""
    function type(char: string): void {
        if (char === "" || char.length > 20) return
        pending = char
        typeDelay.restart()
    }
    Timer {
        id: typeDelay
        interval: 150                              // the compositor hands the focus back when the picker's window is destroyed
        onTriggered: Quickshell.execDetached(["sh", "-c", "wtype \"$1\" || wl-copy \"$1\"", "sh", root.pending])
    }

    LazyLoader {
        active: root.open

        PanelWindow {
            id: win
            readonly property int cols: 9
            readonly property int cell: 48

            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
            WlrLayershell.namespace: "bbkos-picker"
            color: "transparent"

            readonly property var results: root.search(input.text)

            function choose(char) { root.remember(char); root.open = false; root.type(char) }

            MouseArea { anchors.fill: parent; onClicked: root.open = false }

            Rectangle {
                width: win.cols * win.cell + 28
                height: 32 + grid.height + footer.height + 28 + 16
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height * 0.18
                radius: Theme.radius
                color: Theme.popupBg

                MouseArea { anchors.fill: parent }                      // swallow clicks inside the panel

                ColumnLayout {
                    anchors { fill: parent; margins: 14 }
                    spacing: 8

                    Item {
                        Layout.fillWidth: true
                        implicitHeight: 32
                        Text {
                            text: "Search emoji"
                            visible: input.text === ""
                            color: Theme.dim
                            font.family: Theme.font
                            font.pixelSize: Theme.fontSize + 2
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        TextInput {
                            id: input
                            anchors.fill: parent
                            verticalAlignment: TextInput.AlignVCenter
                            color: Theme.fg
                            font.family: Theme.font
                            font.pixelSize: Theme.fontSize + 2
                            focus: true
                            Component.onCompleted: forceActiveFocus()
                            onTextChanged: grid.currentIndex = 0
                            Keys.onEscapePressed: root.open = false
                            Keys.onLeftPressed: grid.moveCurrentIndexLeft()
                            Keys.onRightPressed: grid.moveCurrentIndexRight()
                            Keys.onUpPressed: grid.moveCurrentIndexUp()
                            Keys.onDownPressed: grid.moveCurrentIndexDown()
                            Keys.onReturnPressed: if (grid.currentItem) win.choose(grid.currentItem.char)
                        }
                    }

                    GridView {
                        id: grid
                        Layout.fillWidth: true
                        Layout.preferredHeight: win.cell * 6
                        clip: true
                        cellWidth: win.cell
                        cellHeight: win.cell
                        boundsBehavior: Flickable.StopAtBounds
                        model: win.results
                        currentIndex: 0
                        highlightMoveDuration: 0
                        highlight: Rectangle { radius: Theme.controlRadius; color: Theme.control }

                        delegate: Item {
                            id: cellItem
                            required property var modelData
                            required property int index
                            readonly property string char: modelData[0]
                            width: win.cell
                            height: win.cell
                            Text {
                                anchors.centerIn: parent
                                text: cellItem.char
                                font.family: "Noto Color Emoji"
                                font.pixelSize: 26
                                renderType: Text.NativeRendering
                            }
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                onEntered: grid.currentIndex = cellItem.index
                                onClicked: win.choose(cellItem.char)
                            }
                        }
                    }

                    Text {
                        id: footer
                        Layout.fillWidth: true
                        text: win.results.length === 0 ? "No emoji match"
                            : grid.currentItem ? grid.currentItem.modelData[1] : ""
                        color: Theme.dim
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSize - 1
                        elide: Text.ElideRight
                        height: implicitHeight
                    }
                }
            }
        }
    }
}
