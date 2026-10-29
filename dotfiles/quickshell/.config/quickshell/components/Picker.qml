import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets
import qs

// Shared search-and-pick overlay (launcher, clipboard history). The window is full screen and transparent so a
// click outside the panel dismisses it. (HyprlandFocusGrab was tried for this and did not dismiss on click.)
// The parent supplies `results` (a binding on `query`); items are { label: string, icon: string, data: var } and may carry
// `image` (a file URL: the row is taller and shows it as a thumbnail; clipboard images, 2026-10-28) and `sub` (a dim line).
// With `preview` (a Component, 2026-10-29) the panel is wider and of fixed height: the list on the left, the preview of
// the current item on the right; the parent follows `current` to fill it.
PanelWindow {
    id: win

    property string placeholder: "Search"
    property var results: []
    readonly property string query: input.text
    property Component preview: null
    readonly property var current: list.currentIndex >= 0 && list.currentIndex < results.length ? results[list.currentIndex] : null
    function search(text: string) { input.text = text }      // test hooks (clipboard search, select)
    function select(i: int) { choose(i) }

    // The row the user chose, by its data. A new `results` array (clipboard thumbnails written, an image decoded) makes
    // the ListView start again at row 0; the choice is put back after it. Only keys, hover and typing set it.
    property var chosen: undefined
    function choose(i: int) {
        if (i < 0 || i >= results.length) return
        list.currentIndex = i
        chosen = results[i].data
    }
    function restoreChoice() {
        const i = chosen === undefined ? -1 : results.findIndex(r => r.data === chosen)
        list.currentIndex = i >= 0 ? i : 0
    }
    onResultsChanged: Qt.callLater(restoreChoice)          // a named function: an arrow here makes qmllint skip the file
    signal picked(var data)
    signal dismissed()

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    WlrLayershell.namespace: "bbkos-picker"
    color: "transparent"

    MouseArea { anchors.fill: parent; onClicked: win.dismissed() }

    Rectangle {
        width: win.preview ? 880 : 520
        height: field.height + (win.preview ? 460 : list.contentHeight) + 36
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.2
        radius: Theme.radius
        color: Theme.popupBg
        border.width: Theme.hair
        border.color: Theme.cardEdge
        // No open animation: pickers come from the keyboard many times a day (docs/modules/motion.md); the Hyprland
        // layer rule bbkos-instant-layers turns the compositor fade off too.

        CardShadow {}
        MouseArea { anchors.fill: parent }                         // swallow clicks inside the panel

        ColumnLayout {
            anchors { fill: parent; margins: 14 }
            spacing: 8

            Item {
                id: field
                Layout.fillWidth: true
                implicitHeight: 32

                Text {
                    text: win.placeholder
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
                    onTextChanged: { win.chosen = undefined; list.currentIndex = 0 }
                    Keys.onEscapePressed: win.dismissed()
                    Keys.onDownPressed: win.choose(list.currentIndex + 1)
                    Keys.onUpPressed: win.choose(list.currentIndex - 1)
                    Keys.onReturnPressed: if (list.currentItem) win.picked(list.currentItem.item.data)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 14

                ListView {
                    id: list
                    Layout.fillWidth: !win.preview
                    Layout.preferredWidth: win.preview ? 360 : -1
                    Layout.fillHeight: !!win.preview
                    Layout.alignment: Qt.AlignTop
                    implicitHeight: contentHeight
                    interactive: !!win.preview && contentHeight > height          // image rows can overflow the fixed height
                    clip: !!win.preview
                    onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                    model: win.results
                    currentIndex: 0

                    delegate: Rectangle {
                        id: row
                        required property var modelData
                        required property int index
                        readonly property var item: modelData
                        readonly property bool hasImage: modelData.image !== undefined      // "" while the thumbnail is being made
                        width: ListView.view.width
                        height: row.hasImage ? 72 : 36
                        radius: Theme.controlRadius
                        color: ListView.isCurrentItem ? Theme.control : "transparent"

                        RowLayout {
                            anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                            spacing: 10
                            IconImage { visible: row.modelData.icon !== ""; implicitSize: 22; source: row.modelData.icon }
                            Rectangle {                                         // thumbnail frame
                                visible: row.hasImage
                                Layout.preferredWidth: 96
                                Layout.preferredHeight: 60
                                radius: Theme.controlRadius
                                color: Theme.inset
                                clip: true
                                Image {
                                    anchors.fill: parent
                                    source: row.modelData.image || ""
                                    fillMode: Image.PreserveAspectFit
                                    sourceSize: Qt.size(192, 120)
                                    asynchronous: true
                                    cache: false
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    text: row.modelData.label
                                    textFormat: Text.PlainText          // copied HTML must show as text, not render (it did until 2026-10-28)
                                    maximumLineCount: 1
                                    color: Theme.fg
                                    font.family: Theme.font
                                    font.pixelSize: Theme.fontSize
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Text {
                                    visible: !!row.modelData.sub
                                    text: row.modelData.sub ?? ""
                                    textFormat: Text.PlainText
                                    color: Theme.dim
                                    font.family: Theme.font
                                    font.pixelSize: Theme.fontSize - 1
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            onEntered: win.choose(row.index)
                            onClicked: win.picked(row.modelData.data)
                        }
                    }
                }

                Rectangle {                                   // divider between the list and the preview
                    visible: !!win.preview
                    Layout.fillHeight: true
                    Layout.preferredWidth: Theme.hair
                    color: Theme.cardEdge
                }

                Loader {
                    active: !!win.preview
                    visible: active
                    sourceComponent: win.preview
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }
    }
}
