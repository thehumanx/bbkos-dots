import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets
import qs
import qs.components

// The bbkOS menu's window (docs/modules/menu.md): a search field and the ranked results, or the Create web app form.
// Full screen and transparent so a click outside dismisses it, like the pickers; layer namespace bbkos-picker, so it
// appears at once with no compositor fade (opened from the keyboard many times a day; docs/modules/motion.md).
// The parent (Launcher.qml) owns the data: `results` is a binding on `query`; each item is
// { id, title, subtitle, tag, glyph, icon, confirm, ... }.
PanelWindow {
    id: win

    property var results: []
    property string armedId: ""                 // a destructive command waiting for its second Enter
    property bool form: false                   // the Create web app form instead of the list
    property bool pinMode: false                // picking an app to pin to the dock: the grid opens at once
    property bool grid: false                   // All apps: every app and web app as an icon grid (Tab)
    property var apps: []                       // the grid's items, alphabetical, filtered by the query
    readonly property int columns: 6
    property string formStatus: ""
    property bool formBusy: false
    readonly property string query: input.text
    signal activated(var item)
    signal uninstall(var item)
    signal edited()                             // the query changed: the parent disarms (armedId is its binding)
    signal dismissed()
    signal createWebApp(string name, string url)

    function setQuery(text: string) { input.text = text; input.forceActiveFocus() }
    function openForm() { form = true; formStatus = ""; nameField.text = ""; urlField.text = ""; nameField.forceActiveFocus() }
    function closeForm() { form = false; input.forceActiveFocus() }
    function pick(index: int) { if (index >= 0 && index < list.count) win.activated(win.results[index]) }
    Component.onCompleted: if (pinMode) showGrid(true)
    function showGrid(on: bool) { grid = on; appGrid.currentIndex = 0; list.currentIndex = 0; input.forceActiveFocus() }
    // The highlighted item and how arrows move, in whichever view is showing.
    function current(): var { return grid ? (appGrid.currentIndex >= 0 ? apps[appGrid.currentIndex] : null)
                                          : (list.currentIndex >= 0 ? results[list.currentIndex] : null) }
    function move(dx: int, dy: int) {
        if (!grid) { list.currentIndex = Math.max(0, Math.min(list.count - 1, list.currentIndex + dy)); return }
        appGrid.currentIndex = Math.max(0, Math.min(appGrid.count - 1, appGrid.currentIndex + dx + dy * columns))
    }

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    WlrLayershell.namespace: "bbkos-picker"
    color: "transparent"

    MouseArea { anchors.fill: parent; onClicked: win.dismissed() }

    Rectangle {
        id: card
        width: 600
        height: body.implicitHeight + 28
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.round(parent.height * 0.18)
        radius: Theme.radius
        color: Theme.popupBg
        border.width: Theme.hair
        border.color: Theme.cardEdge

        CardShadow {}
        MouseArea { anchors.fill: parent }                         // swallow clicks inside the card

        ColumnLayout {
            id: body
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
            spacing: 8

            // ---- Search ------------------------------------------------------------------------------------
            Item {
                visible: !win.form
                Layout.fillWidth: true
                implicitHeight: 34

                Txt {
                    text: win.pinMode ? "Pick an app to pin" : "Search apps, commands and settings"
                    visible: input.text === ""
                    color: Theme.dim
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
                    onTextChanged: { list.currentIndex = 0; win.edited() }
                    Keys.onEscapePressed: win.dismissed()
                    Keys.onDownPressed: win.move(0, 1)
                    Keys.onUpPressed: win.move(0, -1)
                    // Left/Right move through the grid; in the list they move the text cursor as usual.
                    Keys.onLeftPressed: event => { if (win.grid) win.move(-1, 0); else event.accepted = false }
                    Keys.onRightPressed: event => { if (win.grid) win.move(1, 0); else event.accepted = false }
                    Keys.onTabPressed: win.showGrid(!win.grid)
                    Keys.onReturnPressed: { const it = win.current(); if (it) win.activated(it) }
                    // Delete with the cursor at the end of the text (where it would delete nothing): uninstall the
                    // highlighted app or web app, after a second Delete. Inside the text it deletes as usual.
                    Keys.onDeletePressed: event => {
                        const it = win.current()
                        if (cursorPosition === text.length && it) win.uninstall(it)
                        else event.accepted = false
                    }
                    Keys.onPressed: event => {
                        // Ctrl+1 .. Ctrl+9 open the result with that number.
                        if ((event.modifiers & Qt.ControlModifier) && event.key >= Qt.Key_1 && event.key <= Qt.Key_9) {
                            win.pick(event.key - Qt.Key_1)
                            event.accepted = true
                        }
                    }
                }
            }

            Rectangle { visible: !win.form && (win.grid ? appGrid.count : list.count) > 0; Layout.fillWidth: true; implicitHeight: Theme.hair; color: Theme.inset }

            // ---- All apps (grid) ---------------------------------------------------------------------------------
            Txt {
                visible: !win.form && win.grid
                text: "All apps \u00b7 " + appGrid.count
                color: Theme.dim
                font.pixelSize: Theme.fontSize - 1
            }
            GridView {
                id: appGrid
                visible: !win.form && win.grid
                Layout.fillWidth: true
                implicitHeight: Math.min(Math.ceil(count / win.columns), 4) * cellHeight
                cellWidth: Math.floor(width / win.columns)
                cellHeight: 104
                clip: true
                model: win.grid ? win.apps : []
                currentIndex: 0
                boundsBehavior: Flickable.StopAtBounds
                highlightMoveDuration: 0
                onCountChanged: if (currentIndex >= count) currentIndex = 0

                delegate: Rectangle {
                    id: tile
                    required property var modelData
                    required property int index
                    readonly property bool armedRemove: win.armedId !== "" && win.armedId === "uninstall:" + modelData.id
                    width: appGrid.cellWidth - 4
                    height: appGrid.cellHeight - 4
                    radius: Theme.controlRadius
                    color: GridView.isCurrentItem ? Theme.control : "transparent"
                    border.width: armedRemove ? Theme.hair : 0
                    border.color: Theme.crit

                    ColumnLayout {
                        anchors { fill: parent; margins: 8 }
                        spacing: 6
                        IconImage {
                            Layout.alignment: Qt.AlignHCenter
                            implicitSize: 48
                            source: tile.modelData.icon ?? ""
                        }
                        Txt {
                            Layout.fillWidth: true
                            text: tile.armedRemove ? "Delete again to uninstall" : tile.modelData.title
                            color: tile.armedRemove ? Theme.crit : Theme.fg
                            font.pixelSize: Theme.fontSize - 2
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: appGrid.currentIndex = tile.index
                        onClicked: win.activated(tile.modelData)
                    }
                }
            }

            ListView {
                id: list
                visible: !win.form && !win.grid
                Layout.fillWidth: true
                implicitHeight: Math.min(contentHeight, 9 * 46)
                clip: true
                model: win.results
                currentIndex: 0
                boundsBehavior: Flickable.StopAtBounds
                highlightMoveDuration: 0

                delegate: Rectangle {
                    id: row
                    required property var modelData
                    required property int index
                    readonly property bool armedRemove: win.armedId !== "" && win.armedId === "uninstall:" + modelData.id
                    readonly property bool armed: win.armedId !== "" && (win.armedId === modelData.id || armedRemove)
                    width: ListView.view.width
                    height: 46
                    radius: Theme.controlRadius
                    color: ListView.isCurrentItem ? Theme.control : "transparent"

                    RowLayout {
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                        spacing: 12
                        Item {
                            implicitWidth: 26
                            implicitHeight: 26
                            IconImage { anchors.fill: parent; visible: (row.modelData.icon ?? "") !== ""; source: row.modelData.icon ?? "" }
                            Txt {
                                anchors.centerIn: parent
                                visible: (row.modelData.icon ?? "") === ""
                                text: row.modelData.glyph ?? ""
                                color: row.armed ? Theme.crit : Theme.accent
                                font.pixelSize: Theme.fontSize + 4
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Txt {
                                text: row.armedRemove ? "Press Delete again to uninstall " + row.modelData.title
                                    : row.armed ? "Press Enter again to " + row.modelData.title.toLowerCase() : row.modelData.title
                                color: row.armed ? Theme.crit : Theme.fg
                                font.bold: row.armed
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Txt {
                                visible: text !== ""
                                text: row.modelData.subtitle ?? ""
                                color: Theme.dim
                                font.pixelSize: Theme.fontSize - 2
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        Txt { text: row.modelData.tag ?? ""; color: Theme.dim; font.pixelSize: Theme.fontSize - 2 }
                        Txt {
                            visible: row.index < 9
                            text: "^" + (row.index + 1)
                            color: Theme.dim
                            opacity: 0.6
                            font.pixelSize: Theme.fontSize - 2
                            Layout.preferredWidth: 20
                            horizontalAlignment: Text.AlignRight
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: list.currentIndex = row.index
                        onClicked: win.pick(row.index)
                    }
                }
            }

            Txt {
                visible: !win.form
                text: win.pinMode ? "Enter pin   Arrows move   Esc close"
                    : win.grid ? "Enter open   Arrows move   Delete uninstall   Tab back to results   Esc close"
                               : "Enter open   Ctrl+1-9 quick pick   Tab all apps   Delete uninstall   Esc close"
                color: Theme.dim
                opacity: 0.7
                font.pixelSize: Theme.fontSize - 2
            }

            // ---- Create web app ------------------------------------------------------------------------------
            ColumnLayout {
                visible: win.form
                Layout.fillWidth: true
                spacing: 10

                Txt { text: "Create web app"; font.bold: true; font.pixelSize: Theme.fontSize + 1 }
                Txt {
                    text: "The site opens in its own Vivaldi window, signed in as in the browser, and gets its own entry in this menu."
                    color: Theme.dim
                    font.pixelSize: Theme.fontSize - 1
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                Rectangle {                                   // name
                    Layout.fillWidth: true
                    implicitHeight: 36
                    radius: Theme.controlRadius
                    color: Theme.inset
                    border.width: Theme.hair
                    border.color: nameField.activeFocus ? Theme.accent : Theme.cardEdge
                    Txt { anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                          visible: nameField.text === ""; text: "Name, for example Gmail"; color: Theme.dim }
                    TextInput {
                        id: nameField
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.fg
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSize
                        maximumLength: 60
                        KeyNavigation.tab: urlField
                        Keys.onEscapePressed: win.closeForm()
                        Keys.onReturnPressed: urlField.forceActiveFocus()
                    }
                }
                Rectangle {                                   // address
                    Layout.fillWidth: true
                    implicitHeight: 36
                    radius: Theme.controlRadius
                    color: Theme.inset
                    border.width: Theme.hair
                    border.color: urlField.activeFocus ? Theme.accent : Theme.cardEdge
                    Txt { anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                          visible: urlField.text === ""; text: "Address, for example mail.google.com"; color: Theme.dim }
                    TextInput {
                        id: urlField
                        anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.fg
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSize
                        KeyNavigation.tab: nameField
                        Keys.onEscapePressed: win.closeForm()
                        Keys.onReturnPressed: win.submitForm()
                    }
                }
                Txt {
                    visible: win.formStatus !== ""
                    text: win.formStatus
                    color: win.formStatus.startsWith("Created") ? Theme.accent : win.formBusy ? Theme.dim : Theme.crit
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Txt { text: "Enter create   Esc back"; color: Theme.dim; opacity: 0.7; font.pixelSize: Theme.fontSize - 2; Layout.fillWidth: true }
                    Button { text: "Back"; onClicked: win.closeForm() }
                    Button {
                        text: win.formBusy ? "Creating…" : "Create"
                        tint: Theme.accent
                        enabled: !win.formBusy && nameField.text.trim() !== "" && urlField.text.trim() !== ""
                        onClicked: win.submitForm()
                    }
                }
            }
        }

    }

    function submitForm() {
        if (!formBusy && nameField.text.trim() !== "" && urlField.text.trim() !== "")
            createWebApp(nameField.text.trim(), urlField.text.trim())
    }
}
