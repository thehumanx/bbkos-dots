import QtQuick
import QtQuick.Layouts
import qs
import qs.components
import qs.services

// Keybindings page: the binds grouped by catalogue group, a search field, Add, and an editor (key capture + action
// picker). It lists and opens the editor; KeyCapture and ActionPicker only take input. The page never writes a file:
// every change is a KeybindStore call, and the CLI's own validation is the final word (its first error line arrives
// in KeybindStore.status). The checks below only catch what can be told before a run.
SettingsPage {
    id: page
    card: true
    note: ""

    property string query: ""
    property bool editing: false
    property string editId: ""                 // "" = a new bind
    property var edMods: []
    property string edKey: ""
    property var edAction: null
    property bool edEnabled: true
    property var edFlags: ({ locked: false, repeating: false, mouse: false })
    property bool pendingSave: false           // a save is queued; the editor stays open until the store settles
    property string confirm: ""                // id awaiting a restore confirm, or "*" for all defaults

    readonly property var actionById: {
        const m = {}
        for (const a of KeybindStore.actions) m[a.id] = a
        return m
    }

    Component.onCompleted: KeybindStore.refresh()

    function isReadOnly(b): bool { return String(b.keys?.key ?? "").startsWith("switch:") }

    function comboParts(b): var { return (b.keys?.mods ?? []).concat([b.keys?.key ?? ""]) }

    function labelOf(b): string {
        const a = b.action ?? {}
        if (a.type === "preset") return actionById[a.id]?.label ?? a.id
        if (a.type === "exec") return a.command
        if (a.type === "dispatch") return a.name + (a.args && Object.keys(a.args).length ? " " + JSON.stringify(a.args) : "")
        return b.id
    }

    function groupOf(b): string {
        if (isReadOnly(b)) return "System"
        return b.action?.type === "preset" ? (actionById[b.action.id]?.group ?? "Other") : "Custom"
    }

    // [{ group, rows: [bind] }] in catalogue order, then Custom and System, filtered by the search text.
    function groups(): var {
        const q = page.query.trim().toLowerCase()
        const order = [], by = {}
        for (const a of KeybindStore.actions) if (!(a.group in by)) { by[a.group] = []; order.push(a.group) }
        for (const g of ["Custom", "System", "Other"]) by[g] = []
        for (const b of KeybindStore.binds) {
            const hay = (labelOf(b) + " " + comboParts(b).join(" ") + " " + (b.action?.command ?? "")).toLowerCase()
            if (q !== "" && hay.indexOf(q) < 0) continue
            by[groupOf(b)].push(b)
        }
        return order.concat(["Custom", "System", "Other"]).filter(g => by[g].length > 0).map(g => ({ group: g, rows: by[g] }))
    }

    function restorable(b): bool { return KeybindStore.shipped.includes(b.id) }

    function sameCombo(b): bool {
        const norm = k => String(k).toLowerCase().replace(/^enter$/, "return").replace(/^page_up$/, "prior").replace(/^page_down$/, "next")
        const mods = m => (m ?? []).map(x => String(x).toUpperCase()).sort().join("+")
        return b.enabled !== false && norm(b.keys.key) === norm(page.edKey) && mods(b.keys.mods) === mods(page.edMods)
    }

    // The enabled bind the editor's combo would clash with (not the bind being edited), or null.
    function conflict(): var {
        if (page.edKey === "") return null
        return KeybindStore.binds.find(b => b.id !== page.editId && sameCombo(b)) ?? null
    }

    function error(): string {
        if (page.edKey === "") return "Record a key combination."
        const a = page.edAction
        if (a === null) return "Choose an action (a dispatcher needs a name and valid JSON arguments)."
        if (a.type === "exec") {
            if (a.command.trim() === "") return "The command is empty."
            if (a.command.length > 512) return "The command is longer than 512 characters."
            if (a.command.indexOf("\n") >= 0) return "The command contains a newline."
        }
        return ""
    }

    readonly property string problem: { void page.edKey; void page.edAction; return page.error() }
    readonly property var clash: { void page.edKey; void page.edMods; void KeybindStore.binds; return page.conflict() }

    function open(b): void {
        page.editId = b ? b.id : ""
        page.edMods = b ? b.keys.mods : []
        page.edKey = b ? b.keys.key : ""
        page.edAction = b ? b.action : null
        page.edEnabled = b ? b.enabled !== false : true
        page.edFlags = b?.flags ?? { locked: false, repeating: false, mouse: false }
        page.pendingSave = false
        page.editing = true
    }

    function save(replace: bool): void {
        const f = page.edFlags ?? {}
        const flags = { locked: f.locked === true, repeating: f.repeating === true,
                        mouse: page.edKey.startsWith("mouse:") }
        const bind = { id: page.editId !== "" ? page.editId : "custom-" + Date.now(),
                       keys: { mods: page.edMods, key: page.edKey }, action: page.edAction, flags: flags, enabled: page.edEnabled }
        if (page.editId !== "") KeybindStore.update(page.editId, bind, replace)
        else KeybindStore.add(bind, replace)
        page.pendingSave = true                // closes on "idle"; an "error: ..." keeps the editor open
    }

    function closeEditor(): void { page.editing = false; page.pendingSave = false }

    Connections {
        target: KeybindStore
        function onStatusChanged() { if (page.pendingSave && KeybindStore.status === "idle") page.closeEditor() }
    }

    // Search, Add, restore all.
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 28; radius: Theme.controlRadius; color: Theme.bg
            border.width: Theme.hair; border.color: Theme.dim
            TextInput {
                id: search
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                verticalAlignment: TextInput.AlignVCenter
                color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.fontSize; clip: true
                onTextChanged: page.query = text
            }
            Txt {
                visible: search.text === ""
                anchors { fill: parent; leftMargin: 8 }
                text: "Search by name, command or key"
                color: Theme.dim
            }
        }
        Button { text: "Add"; tint: Theme.accent; onClicked: page.open(null) }
        Button { text: "Restore all defaults"; onClicked: page.confirm = "*" }
    }

    RowLayout {
        visible: page.confirm === "*"
        Layout.fillWidth: true
        spacing: 8
        Txt { text: "Replace every bind with the shipped defaults?"; color: Theme.warn; Layout.fillWidth: true }
        Button { text: "Restore all"; tint: Theme.crit; onClicked: { page.confirm = ""; KeybindStore.restoreAll() } }
        Button { text: "Cancel"; onClicked: page.confirm = "" }
    }

    // Editor for a new bind: at the top, there is no row yet. Editing an existing bind opens it inside that row (below).
    // Created fresh for each edit, so the picker starts from the bind's action.
    Loader {
        active: page.editing && page.editId === ""
        visible: active
        Layout.fillWidth: true
        sourceComponent: editorCard
    }
    Component {
        id: editorCard
        Rectangle {
            width: parent ? parent.width : 0
            implicitHeight: editor.implicitHeight + 24
            radius: Theme.controlRadius
            color: Theme.bg
            ColumnLayout {
                id: editor
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                spacing: 8
                Txt { text: page.editId === "" ? "New keybinding" : "Edit keybinding"; font.bold: true }
                KeyCapture {
                    Layout.fillWidth: true
                    mods: page.edMods
                    key: page.edKey
                    onCaptured: (m, k) => { page.edMods = m; page.edKey = k; page.pendingSave = false }
                }
                ActionPicker {
                    Layout.fillWidth: true
                    actions: KeybindStore.actions
                    value: page.edAction
                    onPicked: a => { page.edAction = a; page.pendingSave = false }
                }
                Txt { visible: page.problem !== ""; text: page.problem; color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Txt {
                    visible: page.problem === "" && page.pendingSave && KeybindStore.status.startsWith("error: ")
                    text: KeybindStore.status.slice(7); color: Theme.crit; wrapMode: Text.Wrap; Layout.fillWidth: true
                }
                // Duplicate: show the clashing row and the choice before Save.
                RowLayout {
                    visible: page.clash !== null && page.problem === ""
                    Layout.fillWidth: true
                    spacing: 8
                    Txt {
                        text: page.clash ? "Already used by \"" + page.labelOf(page.clash) + "\". Replace it?" : ""
                        color: Theme.warn; wrapMode: Text.Wrap; Layout.fillWidth: true
                    }
                    Button { text: "Replace"; tint: Theme.crit; onClicked: page.save(true) }
                    Button { text: "Cancel"; onClicked: page.closeEditor() }
                }
                RowLayout {
                    spacing: 8
                    Button { text: "Save"; tint: Theme.accent; enabled: page.problem === "" && page.clash === null && !page.pendingSave; onClicked: page.save(false) }
                    Button { text: "Close"; onClicked: page.closeEditor() }
                }
            }
        }
    }

    // The list.
    Repeater {
        model: page.groups()
        delegate: ColumnLayout {
            id: grp
            required property var modelData
            Layout.fillWidth: true
            spacing: 4
            Txt { text: grp.modelData.group; color: Theme.dim; font.bold: true; Layout.topMargin: 6 }
            Repeater {
                model: grp.modelData.rows
                delegate: ColumnLayout {
                    id: row
                    required property var modelData
                    readonly property bool locked: page.isReadOnly(modelData)
                    Layout.fillWidth: true
                    spacing: 2
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Txt { visible: row.locked; text: ""; color: Theme.dim }
                        Txt {
                            text: page.labelOf(row.modelData)
                            elide: Text.ElideRight
                            opacity: row.modelData.enabled === false ? 0.5 : 1
                            Layout.fillWidth: true
                        }
                        Repeater {
                            model: page.comboParts(row.modelData)
                            delegate: Rectangle {
                                id: chip
                                required property string modelData
                                implicitWidth: chipText.implicitWidth + 12
                                implicitHeight: 22
                                radius: Theme.controlRadius
                                color: Theme.bg
                                border.width: Theme.hair
                                border.color: Theme.dim
                                Txt { id: chipText; anchors.centerIn: parent; text: chip.modelData; font.pixelSize: Theme.fontSize - 1 }
                            }
                        }
                        Toggle {
                            checked: row.modelData.enabled !== false
                            enabled: !row.locked
                            onToggled: v => KeybindStore.setEnabled(row.modelData.id, v, false)
                        }
                        Button { visible: !row.locked && page.restorable(row.modelData); text: "Restore"; onClicked: page.confirm = row.modelData.id }
                        Button { visible: !row.locked; text: "Edit"; onClicked: page.open(row.modelData) }
                        Button { visible: !row.locked; text: "Remove"; tint: Theme.crit; onClicked: KeybindStore.remove(row.modelData.id) }
                    }
                    RowLayout {
                        visible: page.confirm === row.modelData.id
                        Layout.fillWidth: true
                        spacing: 8
                        Txt { text: "Put this bind back to its shipped default?"; color: Theme.warn; Layout.fillWidth: true }
                        Button { text: "Restore"; tint: Theme.crit; onClicked: { page.confirm = ""; KeybindStore.restore(row.modelData.id, false) } }
                        Button { text: "Cancel"; onClicked: page.confirm = "" }
                    }
                    // The editor for this bind, shown right under the row being edited.
                    Loader {
                        active: page.editing && page.editId === row.modelData.id
                        visible: active
                        Layout.fillWidth: true
                        Layout.topMargin: 6
                        Layout.bottomMargin: 6
                        sourceComponent: editorCard
                    }
                }
            }
        }
    }

    Txt { visible: page.groups().length === 0; text: "No keybindings match."; color: Theme.dim }

    // Status line: applying, idle, or error: <first line>, as in SettingsStore. Warnings from the last load follow.
    Txt {
        readonly property bool failed: KeybindStore.status.startsWith("error: ")
        text: failed ? KeybindStore.status.slice(7) : KeybindStore.status === "applying" ? "Applying..." : (KeybindStore.warnings[0] ?? "")
        color: failed ? Theme.crit : Theme.dim
        elide: Text.ElideRight
        Layout.fillWidth: true
    }
}
