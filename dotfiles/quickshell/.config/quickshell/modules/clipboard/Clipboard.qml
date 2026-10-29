pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs
import qs.components

// Clipboard history picker. History is recorded by cliphist.service (text and, since 2026-10-28, images; 100 entries by
// default, wiped on logout); this module only reads it. Toggled with `qs ipc call clipboard toggle`.
// cliphist lists an image as "[[ binary data 1.2 MiB png 1920x1080 ]]". While the picker is open the newest image entries
// are decoded into $XDG_RUNTIME_DIR/bbkos-clip (RAM, gone at logout, emptied each time the picker opens) to show as
// thumbnails; picking one copies it back with its image type.
// Beside the list (2026-10-29) a preview of the current entry: the full text (cliphist's list cuts it at about 100
// characters, so it is decoded again, at most 20 KB) or the whole image (an image older than the 20 decoded at open is
// decoded when selected). The folder is $BBKOS_CLIP_DIR when set (the shell tests keep it out of the live one).
Scope {
    id: root
    property bool open: false
    property var entries: []                       // [{ id, text, image: { size, ext, w, h } | null }], newest first
    property int thumbSerial: 0                    // bumped when the thumbnails are written, so the rows reload them
    property var decoded: ({})                     // ids whose image file is in thumbDir
    readonly property string thumbDir: (Quickshell.env("BBKOS_CLIP_DIR") ?? "") !== "" ? Quickshell.env("BBKOS_CLIP_DIR")
        : (Quickshell.env("XDG_RUNTIME_DIR") ?? "") !== "" ? Quickshell.env("XDG_RUNTIME_DIR") + "/bbkos-clip" : ""
    readonly property int textLimit: 20480         // bytes of a text entry shown in the preview
    property var picker: null
    property string selectedId: ""
    readonly property var selected: entries.find(e => e.id === selectedId) ?? null
    property string previewText: ""
    property int previewBytes: 0                   // the whole entry's size, to say when only the first part is shown
    property string previewFor: ""                 // the id previewText belongs to
    readonly property var mimes: ({ png: "image/png", jpeg: "image/jpeg", jpg: "image/jpeg", gif: "image/gif", bmp: "image/bmp", webp: "image/webp" })

    IpcHandler {
        target: "clipboard"
        function toggle(): void { root.open = !root.open }
        // Test hooks: the entries as the picker sees them (images with their decoded thumbnail path); the preview of the
        // current entry; move the selection; type into the search.
        function list(): string { return JSON.stringify(root.entries.slice(0, 20).map(e => ({ id: e.id, text: e.text, image: e.image !== null, thumb: root.thumb(e) }))) }
        function preview(): string {
            const e = root.selected
            return JSON.stringify({ id: root.selectedId, kind: !e ? "" : e.image ? "image" : "text", ready: root.previewReady(),
                                    text: e && !e.image ? root.previewText : "", source: root.previewSource(), info: root.previewInfo() })
        }
        function select(index: int): void { if (root.picker) root.picker.select(index) }
        function search(text: string): void { if (root.picker) root.picker.search(text) }
    }

    onOpenChanged: {
        if (open) lister.running = true
        else { selectedId = ""; previewText = ""; previewFor = "" }
    }
    onSelectedIdChanged: loadPreview()

    function parse(line) {
        const i = line.indexOf("\t")
        const id = line.slice(0, i), text = line.slice(i + 1)
        const m = /^\[\[ binary data (.+) (png|jpeg|jpg|gif|bmp|webp) (\d+)x(\d+) \]\]$/.exec(text)
        return { id: id, text: text, image: m ? { size: m[1], ext: m[2], w: m[3], h: m[4] } : null }
    }
    function thumb(e) { return e.image && thumbDir !== "" ? thumbDir + "/" + e.id + "." + e.image.ext : "" }

    function previewReady() {
        const e = selected
        return !!e && (e.image ? decoded[e.id] === true : previewFor === e.id)
    }
    function previewSource() {
        const e = selected
        return e && e.image && decoded[e.id] === true ? "file://" + thumb(e) + "?" + thumbSerial : ""
    }
    function previewInfo() {
        const e = selected
        if (!e) return ""
        if (e.image) return e.image.ext.toUpperCase() + "  ·  " + e.image.w + " × " + e.image.h + "  ·  " + e.image.size
        if (previewFor !== e.id) return ""
        if (previewBytes > textLimit) return "First " + (textLimit / 1024) + " KB of " + Math.round(previewBytes / 1024) + " KB shown"
        const lines = previewText.split("\n").length
        return previewText.length + (previewText.length === 1 ? " character" : " characters") + "  ·  " + lines + (lines === 1 ? " line" : " lines")
    }

    // One decode at a time; when it ends, the current selection is loaded if it changed meanwhile. Thumbnails first: their
    // start empties the folder.
    function loadPreview() {
        const e = entries.find(x => x.id === selectedId)       // not `selected`: in onSelectedIdChanged it may not be updated yet
        if (!e || !/^[0-9]+$/.test(e.id) || textProc.running || imageProc.running || thumbs.running) return
        if (e.image) {
            if (decoded[e.id] === true || thumbDir === "") return
            imageProc.forId = e.id
            imageProc.command = ["sh", "-c", 'mkdir -m 700 -p -- "$1" && cliphist decode "$2" > "$1/$2.$3"', "sh", thumbDir, e.id, e.image.ext]
            imageProc.running = true
        } else if (previewFor !== e.id) {
            textProc.forId = e.id
            textProc.command = ["sh", "-c", 'cliphist decode "$1" | wc -c; cliphist decode "$1" | head -c "$2"', "sh", e.id, String(textLimit)]
            textProc.running = true
        }
    }

    Process {
        id: lister
        command: ["cliphist", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                root.entries = this.text.split("\n").filter(l => l.indexOf("\t") > 0).map(l => root.parse(l))
                // Thumbnails of the 20 newest images: ids are numeric, extensions from the list above, never a shell word.
                const imgs = root.entries.filter(e => e.image !== null && /^[0-9]+$/.test(e.id)).slice(0, 20)
                if (root.thumbDir === "" || imgs.length === 0) return
                thumbs.command = ["sh", "-c",
                    'd="$1"; shift; rm -rf -- "$d"; mkdir -m 700 -p -- "$d" || exit 1; '
                    + 'while [ $# -gt 1 ]; do cliphist decode "$1" > "$d/$1.$2"; shift 2; done',
                    "sh", root.thumbDir].concat(...imgs.map(e => [e.id, e.image.ext]))
                thumbs.ids = imgs.map(e => e.id)
                root.decoded = ({})
                thumbs.running = true
            }
        }
    }
    Process {
        id: thumbs
        property var ids: []
        onExited: {
            const d = {}
            for (const id of ids) d[id] = true
            root.decoded = d
            root.thumbSerial++
            root.loadPreview()
        }
    }

    Process {
        id: textProc
        property string forId: ""
        stdout: StdioCollector {
            onStreamFinished: {
                const t = this.text, nl = t.indexOf("\n")
                root.previewBytes = parseInt(t.slice(0, nl)) || 0
                root.previewText = t.slice(nl + 1)
                root.previewFor = textProc.forId
            }
        }
        onExited: root.loadPreview()
    }

    Process {
        id: imageProc
        property string forId: ""
        onExited: (code) => {
            if (code === 0) { const d = Object.assign({}, root.decoded); d[forId] = true; root.decoded = d; root.thumbSerial++ }
            root.loadPreview()
        }
    }

    Process { id: copier }

    function pick(id: string) {
        if (!/^[0-9]+$/.test(id)) return           // ids are numeric; never pass anything else to the shell
        const e = entries.find(x => x.id === id)
        const mime = e && e.image ? mimes[e.image.ext] : ""
        copier.command = mime !== ""
            ? ["sh", "-c", "cliphist decode \"$1\" | wl-copy --type \"$2\"", "sh", id, mime]
            : ["sh", "-c", "cliphist decode \"$1\" | wl-copy", "sh", id]
        copier.running = true
    }

    LazyLoader {
        active: root.open

        Picker {
            id: picker
            placeholder: "Search clipboard history"
            results: root.entries
                .filter(e => (e.image ? "image picture " + e.image.ext + " " + e.text : e.text).toLowerCase().includes(picker.query.toLowerCase()))
                .map(e => e.image
                    ? ({ label: "Image  ·  " + e.image.w + " × " + e.image.h, sub: e.image.ext.toUpperCase() + "  ·  " + e.image.size,
                         icon: "", data: e.id, image: root.decoded[e.id] === true ? "file://" + root.thumb(e) + "?" + root.thumbSerial : "" })
                    : ({ label: e.text, icon: "", data: e.id }))
            onCurrentChanged: root.selectedId = picker.current ? picker.current.data : ""
            Component.onCompleted: root.picker = picker
            Component.onDestruction: root.picker = null
            onPicked: id => { root.pick(id); root.open = false }
            onDismissed: root.open = false

            preview: Component {
                ColumnLayout {
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: Theme.controlRadius
                        color: Theme.inset
                        clip: true

                        Image {
                            visible: !!root.selected && !!root.selected.image
                            anchors { fill: parent; margins: 8 }
                            source: root.previewSource()
                            fillMode: Image.PreserveAspectFit
                            sourceSize: Qt.size(1000, 800)
                            asynchronous: true
                            cache: false
                        }

                        Flickable {
                            id: flick
                            visible: !!root.selected && !root.selected.image
                            anchors { fill: parent; margins: 10 }
                            contentHeight: body.implicitHeight
                            clip: true
                            boundsBehavior: Flickable.StopAtBounds
                            Connections { target: root; function onSelectedIdChanged() { flick.contentY = 0 } }

                            Text {
                                id: body
                                width: flick.width
                                text: root.previewFor === root.selectedId ? root.previewText : ""
                                textFormat: Text.PlainText          // copied HTML must show as text, not render
                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                color: Theme.fg
                                font.family: Theme.font
                                font.pixelSize: Theme.fontSize
                            }
                        }

                        Text {
                            visible: !root.selected
                            anchors.centerIn: parent
                            text: "Nothing selected"
                            color: Theme.dim
                            font.family: Theme.font
                            font.pixelSize: Theme.fontSize
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: root.previewInfo()
                        color: Theme.dim
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSize - 1
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
}
