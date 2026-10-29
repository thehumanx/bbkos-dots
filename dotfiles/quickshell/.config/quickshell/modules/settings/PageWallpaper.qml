import QtQuick
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import Quickshell
import Quickshell.Io
import qs
import qs.components
import qs.services
import "../../components/FileUrl.js" as FileUrl

// Wallpaper and colours: the current wallpaper, a thumbnail grid of ~/Pictures/Wallpapers, the colour controls
// (mode, scheme, dominant colour, contrast) and a read-only palette strip.
// - Wallpaper changes go through SettingsStore.setWallpaper / clearWallpaper (the tool copies the file, runs matugen).
// - Thumbnails: a GridView in a fixed-height box that scrolls by itself. A GridView only creates the delegates in or
//   next to its view, so off-screen images are never decoded; each Image decodes at 320x200 (sourceSize), not at
//   the file's size.
// - The header image uses cache: false and is reloaded when the file at wallpaper.path changes on disk, because every
//   `wallpaper set` writes the same path (current.<ext>).
SettingsPage {
    id: page
    note: "Colours follow the wallpaper: pick an image and the whole shell, the terminal and the lock screen re-tint."

    readonly property string dir: (Quickshell.env("HOME") ?? "") + "/Pictures/Wallpapers"
    readonly property string current: ThemeStore.wallpaperPath
    readonly property bool hasCurrent: current.startsWith("/")
    readonly property string error: SettingsStore.status.startsWith("error: ") ? SettingsStore.status.slice(7) : ""
    readonly property var ansi: {
        const a = ThemeStore.colorsDoc !== null && typeof ThemeStore.colorsDoc === "object" ? ThemeStore.colorsDoc.ansi : null
        return Array.isArray(a) ? a : []
    }
    readonly property var paletteKeys: ["bg", "surface", "fg", "dim", "accent", "warn", "crit", "outline",
                                        "borderActive1", "borderActive2", "borderInactive",
                                        "secondary", "tertiary", "accentSoft", "secondarySoft", "tertiarySoft", "surfaceHigh"]
    readonly property var ansiNames: ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
                                      "bright black", "bright red", "bright green", "bright yellow",
                                      "bright blue", "bright magenta", "bright cyan", "bright white"]
    property string hoverName: ""            // swatch under the pointer, shown under the palette
    property string hoverColor: ""
    property int serial: 0                   // bumped when the current wallpaper file changes on disk

    function swatchColor(v) { return (typeof v === "string" && /^#[0-9a-fA-F]{6}$/.test(v)) ? v : Theme.surface }

    // Test hook (settings status "images"): set while this page exists, -1 again when it is destroyed.
    readonly property int imageCount: folder.count
    onImageCountChanged: SettingsStore.imageCount = imageCount
    Component.onCompleted: SettingsStore.imageCount = imageCount
    Component.onDestruction: SettingsStore.imageCount = -1

    // A FolderListModel does not notice a folder that did not exist when `folder` was set: point it elsewhere and back.
    function refreshFolder() {
        folder.folder = "file:///"
        folder.folder = FileUrl.toUrl(page.dir)
    }
    Connections { target: SettingsStore; function onFolderRefreshRequested() { page.refreshFolder() } }

    FolderListModel {
        id: folder
        folder: FileUrl.toUrl(page.dir)
        nameFilters: ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif"]
        caseSensitive: false
        showDirs: false
        showFiles: true
        showHidden: false
        sortField: FolderListModel.Name
    }

    // The tool replaces current.<ext> in place: watch it (never read it) and reload the header image.
    FileView {
        path: page.hasCurrent ? page.current : ""
        preload: false
        watchChanges: true
        printErrors: false
        onFileChanged: settle.restart()
    }
    Timer { id: settle; interval: 150; onTriggered: page.serial++ }

    // mkdir first, thunar only when it succeeded (two detached calls would race).
    Process {
        id: mkdir
        command: ["mkdir", "-p", "--", page.dir]
        onExited: (code, status) => {
            if (code === 0 && status === 0) {
                page.refreshFolder()          // the folder may have just been created
                Quickshell.execDetached(["thunar", page.dir])
            }
            else console.warn("PageWallpaper: could not create " + page.dir)
        }
    }

    SettingsSection {
        title: "Wallpaper"
        padded: true

        // Header: current wallpaper and its buttons.
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Rectangle {
                Layout.preferredWidth: 160
                Layout.preferredHeight: 100
                radius: Theme.controlRadius
                color: Theme.bg
                border.width: Theme.hair
                border.color: Theme.dim
                clip: true

                Image {
                    id: cur
                    anchors.fill: parent
                    anchors.margins: 2
                    visible: status === Image.Ready
                    asynchronous: true
                    cache: false
                    fillMode: Image.PreserveAspectCrop
                    sourceSize: Qt.size(320, 200)
                    source: ""
                    function reload() { source = ""; source = page.hasCurrent ? FileUrl.toUrl(page.current) : "" }
                    Connections {
                        target: page
                        function onCurrentChanged() { Qt.callLater(cur.reload) }
                        function onSerialChanged() { Qt.callLater(cur.reload) }
                    }
                    Component.onCompleted: reload()
                }
                Txt {
                    anchors.centerIn: parent
                    visible: cur.status !== Image.Ready
                    text: "No wallpaper"
                    color: Theme.dim
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 8
                Txt { text: "Current wallpaper"; font.bold: true; Layout.preferredHeight: 20 }
                Txt {
                    text: page.hasCurrent ? page.current.split("/").pop() : "None: the plain colour shows."
                    color: Theme.dim
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                    Layout.preferredHeight: 20
                }
                RowLayout {
                    spacing: 8
                    Button { text: "Clear wallpaper"; enabled: page.hasCurrent; onClicked: SettingsStore.clearWallpaper() }
                    Button { text: "Open folder"; onClicked: mkdir.running = true }
                }
            }
        }

        // Status line: errors in Theme.crit, "Applying..." while a wallpaper job runs.
        Txt {
            text: page.error !== "" ? page.error : SettingsStore.wallpaperBusy ? "Applying..." : ""
            color: page.error !== "" ? Theme.crit : Theme.dim
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.preferredHeight: 20
        }

        // Thumbnail grid, or the hint when the folder is missing or has no images.
        Item {
            id: gridBox
            Layout.fillWidth: true
            readonly property int cols: Math.max(1, Math.floor(width / 176))
            readonly property int cellW: Math.floor(width / cols / 2) * 2
            readonly property int cellH: Math.round(cellW * 5 / 8 / 2) * 2 + 28     // thumbnail 8:5 plus caption
            readonly property int rows: Math.max(1, Math.min(2, Math.ceil(folder.count / cols)))
            Layout.preferredHeight: folder.count > 0 ? rows * cellH : 28

            Txt {
                visible: folder.count === 0
                anchors.verticalCenter: parent.verticalCenter
                text: "Put images in ~/Pictures/Wallpapers, then pick one here."
                color: Theme.dim
            }

            GridView {
                id: grid
                anchors.fill: parent
                visible: folder.count > 0
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                cellWidth: gridBox.cellW
                cellHeight: gridBox.cellH
                model: folder

                delegate: Item {
                    id: cell
                    required property string fileName
                    required property string filePath
                    width: grid.cellWidth
                    height: grid.cellHeight

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 4
                        radius: Theme.controlRadius
                        color: "transparent"
                        border.width: Theme.hair
                        border.color: area.containsMouse ? Theme.accent : Theme.dim

                        Image {
                            x: 2; y: 2
                            width: parent.width - 4
                            height: parent.height - 28
                            asynchronous: true
                            fillMode: Image.PreserveAspectCrop
                            sourceSize: Qt.size(320, 200)
                            source: FileUrl.toUrl(cell.filePath)
                        }
                        Txt {
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 4 }
                            height: 20
                            text: cell.fileName
                            color: area.containsMouse ? Theme.fg : Theme.dim
                            font.pixelSize: Theme.fontSize - 2
                            elide: Text.ElideMiddle
                        }
                        MouseArea {
                            id: area
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: SettingsStore.setWallpaper(cell.filePath)
                        }
                    }
                }
            }
        }
    }

    SettingsSection {
        title: "Colours"
        SettingChoice { label: "Mode"; hint: "Dark or light palette"; key: "colors.mode"; model: [{ value: "dark", label: "Dark" }, { value: "light", label: "Light" }] }
        SettingToggle { label: "Switch by the time of day"; hint: "Light from the first time until the second, dark the rest. A mode you pick stays until the next switch"; key: "colors.auto" }
        SettingChoice { label: "Light from"; hint: "Needs the switch above"; key: "colors.lightFrom"; model: ["05:00", "06:00", "07:00", "08:00", "09:00"]; enabled: SettingsStore.shown("colors.auto") === true }
        SettingChoice { label: "Dark from"; hint: "Needs the switch above"; key: "colors.darkFrom"; model: ["16:00", "17:00", "18:00", "19:00", "20:00", "21:00"]; enabled: SettingsStore.shown("colors.auto") === true }
        SettingChoice {
            label: "Scheme"; hint: "How the palette is built from the wallpaper"; key: "colors.scheme"
            model: ["content", "expressive", "fidelity", "fruit-salad", "monochrome", "neutral", "rainbow", "tonal-spot", "vibrant"]
                .map(v => ({ value: v, label: v.charAt(0).toUpperCase() + v.slice(1).replace("-", " ") }))
        }
        SettingChoice {
            label: "Colour from the image"; hint: "Which of the image's main colours the palette is built on"; key: "colors.sourceIndex"
            model: [{ value: 0, label: "Most common" }, { value: 1, label: "Second" }, { value: 2, label: "Third" }, { value: 3, label: "Fourth" }]
        }
        SettingSlider { label: "Contrast"; hint: "High values push every colour toward white"; key: "colors.contrast"; from: -1; to: 1; step: 0.1 }
        SettingSlider { label: "Accent colour strength"; hint: "How vivid the wallpaper's colour is in selections, slider fills and tints (0 = grey)"; key: "colors.accentStrength"; from: 0; to: 1; step: 0.05; percent: true }
        SettingSlider { label: "Tint strength"; hint: "How far bar icons and highlights lean toward the wallpaper's tints (0 = plain text colour)"; key: "shell.tint"; from: 0; to: 1; step: 0.05; percent: true }
        SettingToggle { label: "Folder icons in the accent"; hint: "Thunar and other GTK apps: Adwaita's folders take the wallpaper's hue"; key: "colors.folderIcons" }
    }

    // Palette (read-only): the shell colours first, then the 16 terminal colours.
    SettingsSection {
        title: "Palette"
        padded: true
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: page.paletteKeys
                delegate: Rectangle {
                    required property string modelData
                    width: 24; height: 24
                    radius: Math.min(Theme.controlRadius, 8)
                    color: page.swatchColor(ThemeStore.colors[modelData])
                    border.width: Theme.hair
                    border.color: Theme.dim
                    HoverHandler {
                        onHoveredChanged: { page.hoverName = hovered ? parent.modelData : ""; page.hoverColor = hovered ? parent.color.toString() : "" }
                    }
                }
            }
        }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: 16
                delegate: Rectangle {
                    required property int index
                    width: 24; height: 24
                    radius: Math.min(Theme.controlRadius, 8)
                    color: page.swatchColor(page.ansi[index])
                    border.width: Theme.hair
                    border.color: Theme.dim
                    HoverHandler {
                        onHoveredChanged: { page.hoverName = hovered ? "ansi " + page.ansiNames[parent.index] : ""; page.hoverColor = hovered ? parent.color.toString() : "" }
                    }
                }
            }
        }
        Txt { text: page.hoverName !== "" ? page.hoverName + "  " + page.hoverColor : "Hover a swatch for its name"; color: Theme.dim; Layout.preferredHeight: 20 }
    }
}
