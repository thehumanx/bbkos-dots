.pragma library
.import "../settings/Pages.js" as Pages
.import "../settings/SearchIndex.js" as SearchIndex
// The bbkOS menu's own commands (docs/modules/menu.md). Each: id, title, subtitle, glyph (Nerd Font), keywords, and
// `run`, which Launcher.qml carries out:
//   { exec: [argv] }          a detached process (system tools, bbkos-* commands)
//   { panel: "wifi" }         a bar popup (PanelState)
//   { settings: "page/tab" }  the settings window at that place (settings/Pages.js)
//   { profile: 0|1|2 }        power mode (Power.setProfile)
//   { stage: true }           stage mode for the focused workspace (StageState)
//   { awake: true }           keep awake on/off (Awake)
//   { mode: "light"|"dark" }  colour mode (SettingsStore)
//   { overview: true }        the workspace overview
//   { webapp: "create" }      the menu's Create web app form
//   { allApps: true }         the All apps grid
// `confirm: true`: the first Enter only arms it ("Press Enter again to ..."), within 4 s, as every destructive action
// in bbkOS (docs/design.md section 5).

var COMMANDS = [
    // Session
    { id: "lock", title: "Lock screen", glyph: "", keywords: ["lock"], run: { exec: ["loginctl", "lock-session"] } },
    { id: "suspend", title: "Suspend", glyph: "", keywords: ["sleep"], run: { exec: ["systemctl", "suspend"] } },
    { id: "logout", title: "Log out", glyph: "", keywords: ["exit", "sign out"], confirm: true, run: { exec: ["uwsm", "stop"] } },
    { id: "reboot", title: "Restart", glyph: "", keywords: ["reboot"], confirm: true, run: { exec: ["systemctl", "reboot"] } },
    { id: "poweroff", title: "Shut down", glyph: "", keywords: ["power off", "turn off"], confirm: true, run: { exec: ["systemctl", "poweroff"] } },

    // Power and system
    { id: "profile-saver", title: "Power mode: Battery", glyph: "", keywords: ["power saver", "eco"], run: { profile: 0 } },
    { id: "profile-balanced", title: "Power mode: Balanced", glyph: "", keywords: ["power"], run: { profile: 1 } },
    { id: "profile-performance", title: "Power mode: Performance", glyph: "", keywords: ["power", "fast"], run: { profile: 2 } },
    { id: "awake", title: "Keep awake", subtitle: "On or off: no screen dimming, lock or suspend", glyph: "", keywords: ["caffeine", "inhibit"], run: { awake: true } },
    { id: "update", title: "Update system", glyph: "", keywords: ["upgrade", "pacman"], run: { exec: ["bbkos-tui", "bbkos-update"] } },
    { id: "check", title: "Health check", subtitle: "bbkos-check", glyph: "", keywords: ["status", "doctor"], run: { exec: ["uwsm", "app", "--", "kitty", "--class", "bbkos-tui-check", "--hold", "bbkos-check"] } },

    // Shell
    { id: "all-apps", title: "All apps", subtitle: "Every installed app at a glance (also Tab)", glyph: "\uf00a", keywords: ["applications", "installed", "programs", "grid"], run: { allApps: true } },
    { id: "overview", title: "Workspace overview", glyph: "", keywords: ["mission control", "expose"], run: { overview: true } },
    { id: "stage", title: "Stage mode for this workspace", subtitle: "Until the next reboot", glyph: "", keywords: ["stage manager", "monocle"], run: { stage: true } },
    { id: "bar", title: "Hide or show the bar", glyph: "", keywords: ["panel"], run: { exec: ["qs", "ipc", "call", "bar", "toggle"] } },
    { id: "clipboard", title: "Clipboard history", glyph: "", keywords: ["paste"], run: { exec: ["qs", "ipc", "call", "clipboard", "toggle"] } },
    { id: "android", title: "Android apps", subtitle: "Disable or remove apps on your phone", glyph: "\uf10b", keywords: ["phone", "debloat", "bloatware", "adb", "uninstall"], run: { exec: ["qs", "ipc", "call", "android", "toggle"] } },
    { id: "emoji", title: "Emoji picker", glyph: "", keywords: ["emoticon", "smiley"], run: { exec: ["qs", "ipc", "call", "emoji", "toggle"] } },
    { id: "notifications", title: "Notifications", glyph: "", keywords: ["history"], run: { panel: "notifications" } },
    { id: "wifi", title: "Wi-Fi", glyph: "", keywords: ["network", "internet", "speed test", "share"], run: { panel: "wifi" } },
    { id: "bluetooth", title: "Bluetooth", glyph: "", keywords: ["headphones", "pair"], run: { panel: "bluetooth" } },
    { id: "audio", title: "Sound", glyph: "", keywords: ["volume", "speaker", "microphone"], run: { panel: "audio" } },
    { id: "display", title: "Display and brightness", glyph: "", keywords: ["monitor", "screen"], run: { panel: "display" } },
    { id: "battery", title: "Battery", glyph: "", keywords: ["power"], run: { panel: "battery" } },
    { id: "calendar", title: "Calendar", glyph: "", keywords: ["date"], run: { panel: "calendar" } },

    // Apps
    { id: "claude-bbkos", title: "Claude Code in bbkOS", subtitle: "A terminal in the bbkos-dots checkout running claude (Super+Ctrl+Enter)", glyph: "", keywords: ["claude", "ai", "terminal", "code", "bbkos"], run: { exec: ["sh", "-c", "exec uwsm app -- kitty --directory \"$HOME/.local/share/bbkos/repo\" claude"] } },

    // Capture
    { id: "screenshot", title: "Screenshot", glyph: "", keywords: ["capture", "snip"], run: { exec: ["omasnap"] } },
    { id: "record", title: "Record the screen", glyph: "", keywords: ["video", "capture"], run: { panel: "record" } },
    { id: "ocr", title: "Copy text from the screen", subtitle: "OCR", glyph: "", keywords: ["ocr", "text"], run: { exec: ["bbkos-ocr"] } },

    // Look
    { id: "light", title: "Light mode", glyph: "", keywords: ["theme", "appearance"], run: { mode: "light" } },
    { id: "dark", title: "Dark mode", glyph: "", keywords: ["theme", "appearance"], run: { mode: "dark" } },

    // Web apps (bbkos-webapp)
    { id: "webapp-create", title: "Create web app", subtitle: "A site in its own window, opened in Vivaldi", glyph: "", keywords: ["pwa", "website", "install"], run: { webapp: "create" } }
]

// One entry per settings page, and one per tab of a page with tabs ("Stage mode", subtitle "Settings · Windows"), from the
// settings window's own list, so the menu never falls behind it. The old page names stay findable through the keywords.
function settingsEntries() {
    var out = []
    for (var i = 0; i < Pages.PAGES.length; i++) {
        var p = Pages.PAGES[i]
        var words = (p.keywords + " " + p.tabs.map(function (t) { return t.label + " " + t.keywords }).join(" ")).split(/\s+/)
        out.push({ id: p.id, title: p.label, subtitle: "Settings", keywords: words.filter(function (w) { return w !== "" }) })
        if (p.tabs.length < 2) continue
        for (var j = 0; j < p.tabs.length; j++) {
            var t = p.tabs[j]
            out.push({ id: p.id + "/" + t.id, title: t.label, subtitle: "Settings · " + p.label,
                       keywords: (p.label + " " + t.keywords).split(/\s+/).filter(function (w) { return w !== "" }) })
        }
    }
    return out
}

// One entry per single setting (the settings window's own search index, so the menu never falls behind it): the row's label,
// "Settings · Page › Tab · Card" as the subtitle (shown, not searched: `subtitleOnly`, or every row of a tab would match its name); opens its tab and lights the row up (SettingsStore.reveal). The hint text is
// not searched here: hints are long and would match dozens of rows for a word like "gap".
function settingRowEntries() {
    var out = []
    for (var i = 0; i < SearchIndex.ROWS.length; i++) {
        var r = SearchIndex.ROWS[i]
        out.push({ id: "setting:" + r.place + "/" + r.section + "/" + r.label, title: r.label,
                   subtitle: "Settings · " + r.where + (r.section !== "" ? " · " + r.section : ""),
                   keywords: [], subtitleOnly: true, kind: "settings", tag: "Settings", run: { settings: r.place, reveal: r.label } })
    }
    return out
}

function items() {
    var out = []
    for (var i = 0; i < COMMANDS.length; i++) {
        var c = COMMANDS[i]
        out.push({ id: "cmd:" + c.id, title: c.title, subtitle: c.subtitle || "", glyph: c.glyph, keywords: c.keywords || [],
                   kind: "command", tag: "Command", confirm: c.confirm === true, run: c.run })
    }
    var settings = settingsEntries()
    for (var j = 0; j < settings.length; j++)
        out.push({ id: "settings:" + settings[j].id, title: settings[j].title, subtitle: settings[j].subtitle, glyph: "",
                   keywords: ["settings", "preferences"].concat(settings[j].keywords), kind: "settings", tag: "Settings",
                   run: { settings: settings[j].id } })
    return out.concat(settingRowEntries())
}
