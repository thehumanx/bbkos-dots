import QtQuick
import QtQuick.Layouts
import Quickshell
import qs

// Chooses what a bind does. A pure input: `actions` is the catalogue (KeybindStore.actions) and `value` the current
// action; every change is emitted as picked(action) where action is one of
//   { type: "preset", id }  |  { type: "exec", command }  |  { type: "dispatch", name, args }
// or null while the free-text modes are incomplete. Modes: the grouped catalogue, "Open app...", "Run command...",
// "Hyprland action...". The mode starts from `value` when the picker is created (the page creates it per edit);
// switching mode emits picked(null).
ColumnLayout {
    id: root
    property var actions: []
    property var value: null
    property string mode: "catalogue"       // catalogue | app | command | dispatch
    property string appQuery: ""
    signal picked(var action)

    spacing: 8

    function groups(): var {
        const order = [], by = {}
        for (const a of (Array.isArray(root.actions) ? root.actions : [])) {
            if (!by[a.group]) { by[a.group] = []; order.push(a.group) }
            by[a.group].push(a)
        }
        return order.map(g => ({ group: g, items: by[g] }))
    }

    // Single-quote an argument for the shell when it needs it.
    function quoted(s: string): string { return /^[A-Za-z0-9_\/.:=@%+,-]+$/.test(s) ? s : "'" + s.replace(/'/g, "'\\''") + "'" }

    function appCommand(e): string {
        const cmd = (e.runInTerminal ? ["kitty", "-e"] : []).concat(e.command ?? [])
        return "uwsm app -- " + cmd.map(quoted).join(" ")
    }

    function apps(): var {
        const q = root.appQuery.trim().toLowerCase()
        const out = []
        for (const e of DesktopEntries.applications.values)
            if (!e.noDisplay && (q === "" || String(e.name).toLowerCase().indexOf(q) >= 0)) out.push(e)
        out.sort((a, b) => String(a.name).localeCompare(String(b.name)))
        return out.slice(0, 40)
    }

    function emitDispatch(): void {
        const name = dispName.text.trim()
        let args = {}
        if (dispArgs.text.trim() !== "") {
            try { args = JSON.parse(dispArgs.text) } catch (e) { args = null }
            if (args === null || typeof args !== "object" || Array.isArray(args)) args = null
        }
        root.picked(name === "" || args === null ? null : { type: "dispatch", name: name, args: args })
    }

    Component.onCompleted: {
        const v = root.value
        if (v && v.type === "exec") { mode = "command"; cmdInput.text = v.command ?? "" }
        else if (v && v.type === "dispatch") {
            mode = "dispatch"; dispName.text = v.name ?? ""; dispArgs.text = JSON.stringify(v.args ?? {})
        }
    }

    Chips {
        model: [{ value: "catalogue", label: "Actions" }, { value: "app", label: "Open app..." },
                { value: "command", label: "Run command..." }, { value: "dispatch", label: "Hyprland action..." }]
        current: root.mode
        onChosen: v => { root.mode = v; root.picked(null) }   // a new mode starts with no action chosen
    }

    // Catalogue: grouped, scrolls inside a fixed height.
    Flickable {
        visible: root.mode === "catalogue"
        Layout.fillWidth: true
        Layout.preferredHeight: 200
        contentHeight: cat.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ColumnLayout {
            id: cat
            width: parent.width
            spacing: 2
            Repeater {
                model: root.mode === "catalogue" ? root.groups() : []
                delegate: ColumnLayout {
                    id: grp
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 2
                    Txt { text: grp.modelData.group; color: Theme.dim; font.bold: true; Layout.topMargin: 4 }
                    Repeater {
                        model: grp.modelData.items
                        delegate: Rectangle {
                            id: item
                            required property var modelData
                            readonly property bool selected: root.value?.type === "preset" && root.value.id === modelData.id
                            readonly property bool missing: Array.isArray(modelData.missing) && modelData.missing.length > 0
                            Layout.fillWidth: true
                            implicitHeight: 28
                            radius: Theme.controlRadius
                            color: selected ? Theme.accent : (ia.containsMouse ? Theme.control : "transparent")
                            RowLayout {
                                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                                Txt { text: item.modelData.label; color: item.selected ? Theme.bg : Theme.fg; elide: Text.ElideRight; Layout.fillWidth: true }
                                Txt { visible: item.missing; text: "needs " + (item.modelData.missing ?? []).join(", "); color: Theme.warn }
                            }
                            MouseArea { id: ia; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: root.picked({ type: "preset", id: item.modelData.id }) }
                        }
                    }
                }
            }
        }
    }

    // Installed apps.
    ColumnLayout {
        visible: root.mode === "app"
        Layout.fillWidth: true
        spacing: 4
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 28; radius: Theme.controlRadius; color: Theme.inset
            border.width: Theme.hair; border.color: Theme.dim
            TextInput {
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.fontSize; clip: true
                onTextChanged: root.appQuery = text
            }
        }
        Repeater {
            model: root.mode === "app" ? root.apps() : []
            delegate: Rectangle {
                id: app
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: 28
                radius: Theme.controlRadius
                color: aa.containsMouse ? Theme.control : "transparent"
                Txt { anchors { fill: parent; leftMargin: 8 }
                    text: app.modelData.name; elide: Text.ElideRight }
                MouseArea { id: aa; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked({ type: "exec", command: root.appCommand(app.modelData) }) }
            }
        }
    }

    // Free command.
    Rectangle {
        visible: root.mode === "command"
        Layout.fillWidth: true; implicitHeight: 28; radius: Theme.controlRadius; color: Theme.inset
        border.width: Theme.hair; border.color: Theme.dim
        TextInput {
            id: cmdInput
            anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
            verticalAlignment: TextInput.AlignVCenter
            color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.fontSize; clip: true
            onTextChanged: if (root.mode === "command") root.picked({ type: "exec", command: text })
        }
        Txt { visible: cmdInput.text === ""; anchors { fill: parent; leftMargin: 8 }
            text: "Shell command"; color: Theme.dim }
    }

    // Hyprland dispatcher and its JSON arguments.
    ColumnLayout {
        visible: root.mode === "dispatch"
        Layout.fillWidth: true
        spacing: 4
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 28; radius: Theme.controlRadius; color: Theme.inset
            border.width: Theme.hair; border.color: Theme.dim
            TextInput {
                id: dispName
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.fontSize; clip: true
                onTextChanged: if (root.mode === "dispatch") root.emitDispatch()
            }
            Txt { visible: dispName.text === ""; anchors { fill: parent; leftMargin: 8 }
                text: "Dispatcher, for example focus"; color: Theme.dim }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 28; radius: Theme.controlRadius; color: Theme.inset
            border.width: Theme.hair; border.color: Theme.dim
            TextInput {
                id: dispArgs
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.fontSize; clip: true
                onTextChanged: if (root.mode === "dispatch") root.emitDispatch()
            }
            Txt { visible: dispArgs.text === ""; anchors { fill: parent; leftMargin: 8 }
                text: "Arguments as JSON, for example {\"direction\": \"left\"}"; color: Theme.dim }
        }
    }
}
