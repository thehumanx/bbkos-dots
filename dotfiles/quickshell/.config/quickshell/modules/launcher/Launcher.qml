import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs
import qs.services
import "Rank.js" as Rank
import "Commands.js" as Commands

// The bbkOS menu (docs/modules/menu.md): one search for apps, web apps, bbkOS commands, settings pages, a calculator
// and a web search, ranked like Raycast's root search (Rank.js) and learning from what is opened. The same key and
// IPC target as the old app launcher (`qs ipc call launcher toggle`). The window (and its search state) exists only
// while open.
Scope {
    id: root
    property bool open: false

    // Desktop entries load lazily on first use; load them now so the first open is complete.
    Component.onCompleted: void DesktopEntries.applications

    // ---- Usage (frecency and learned search terms), $XDG_STATE_HOME/quickshell/launcher-usage.json, bounded by Rank.record.
    property var usage: ({})
    FileView {
        id: usageFile
        path: Quickshell.statePath("launcher-usage.json")
        atomicWrites: true
        printErrors: false
        blockLoading: true
    }
    function loadUsage() {
        try { const v = JSON.parse(usageFile.text() || "{}"); usage = (v && typeof v === "object" && !Array.isArray(v)) ? v : {} }
        catch (e) { usage = {} }
    }
    function remember(id: string, query: string) {
        if (cfg.learn === false) return                 // launcher.learn off: nothing is recorded
        usage = Rank.record(usage, id, query, Date.now())
        usageFile.setText(JSON.stringify(usage))
    }
    function forgetUsage() { usage = ({}); usageFile.setText("{}") }

    // ---- Settings (Launcher page): launcher.* in settings.json.
    readonly property var cfg: ThemeStore.settings.launcher ?? ({})
    readonly property var engines: ({
        duckduckgo: { name: "DuckDuckGo", url: "https://duckduckgo.com/?q=" },
        google: { name: "Google", url: "https://www.google.com/search?q=" },
        brave: { name: "Brave Search", url: "https://search.brave.com/search?q=" },
        startpage: { name: "Startpage", url: "https://www.startpage.com/do/search?q=" },
        ecosia: { name: "Ecosia", url: "https://www.ecosia.org/search?q=" }
    })
    readonly property var engine: engines[cfg.webSearch ?? "duckduckgo"] ?? null     // null: "off" (no web search result)

    // ---- Web apps (bbkos-webapp list), read each time the menu opens; each gets a "Remove web app" command.
    property var webapps: []
    Process {
        id: webappList
        command: ["bbkos-webapp", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                const out = []
                for (const line of text.split("\n")) {
                    try { const o = JSON.parse(line); if (o && o.slug) out.push(o) } catch (e) {}
                }
                root.webapps = out.slice(0, 200)
            }
        }
    }
    onOpenChanged: if (open) { loadUsage(); webappList.running = true }

    // Apps must NOT run inside quickshell.service's cgroup: a Quickshell restart or crash would kill every app
    // started from here. `uwsm app` starts each one in its own systemd scope under app.slice.
    function launchEntry(entry) {
        if (entry.runInTerminal)
            Quickshell.execDetached(["uwsm", "app", "-T", "--"].concat(entry.command))   // the default terminal
        else
            Quickshell.execDetached(["uwsm", "app", "--", entry.id + ".desktop"])
    }

    function allItems(): var {
        const out = []
        for (const e of DesktopEntries.applications.values) {
            if (e.noDisplay) continue
            const web = e.id.startsWith("bbkos-webapp-")
            out.push({ id: "app:" + e.id, title: e.name, subtitle: web ? "Web app" : (e.genericName || ""),
                       keywords: e.keywords.concat([e.genericName].filter(x => x)),          // not the comment: long descriptions match anything kind: web ? "webapp" : "app",
                       tag: web ? "Web app" : "App", icon: e.icon.startsWith("/") ? "file://" + e.icon            // an absolute icon file (web apps)
                                                     : Quickshell.iconPath(e.icon, "application-x-executable"), entry: e })
        }
        for (const w of webapps)
            out.push({ id: "webapp-remove:" + w.slug, title: "Remove web app: " + w.name, subtitle: w.url, glyph: "",
                       keywords: ["delete", "uninstall", "pwa"], kind: "command", tag: "Web app", confirm: true,
                       run: { webappRemove: w.slug } })
        return cfg.commands === false ? out : out.concat(Commands.items())
    }

    // All apps (the grid): every app and web app, alphabetical; a query keeps only the ones that match it.
    function appsFor(query: string): var {
        const q = query.trim()
        const apps = allItems().filter(i => i.entry)
        if (q === "") return apps.sort((a, b) => a.title.localeCompare(b.title))
        return Rank.rank(apps, q, {}, Date.now())
    }

    function search(query: string): var {
        const q = query.trim()
        const ranked = Rank.rank(allItems(), q, cfg.learn === false ? ({}) : usage, Date.now())
        const out = []
        const value = q === "" || cfg.calculator === false ? null : Rank.calculate(q)
        if (value !== null)
            out.push({ id: "calc", title: "= " + value, subtitle: "Enter copies the result", glyph: "",
                       tag: "Calculator", run: { copy: String(value) } })
        for (const r of ranked.slice(0, cfg.maxResults ?? 40)) out.push(r)
        if (q !== "" && engine)
            out.push({ id: "search", title: "Search the web for “" + q + "”", subtitle: engine.name + ", in the default browser",
                       glyph: "", tag: "Web", run: { web: q } })
        return out
    }

    // ---- Carrying out a result. `armed`: a destructive command waits for a second Enter within 4 s.
    property string armed: ""
    Timer { id: disarm; interval: 4000; onTriggered: root.armed = "" }

    function activate(item, query: string) {
        if (item.confirm && root.armed !== item.id) { root.armed = item.id; disarm.restart(); return }
        root.armed = ""
        if (item.id !== "calc" && item.id !== "search") remember(item.id, query)
        if (item.entry) { launchEntry(item.entry); root.open = false; return }
        const r = item.run || {}
        if (r.webapp === "create") { menu.item.openForm(); return }
        if (r.allApps) { menu.item.setQuery(""); menu.item.showGrid(true); return }
        root.open = false
        if (r.exec) Quickshell.execDetached(r.exec)
        else if (r.panel) PanelState.toggle(r.panel, "")
        else if (r.settings !== undefined) { SettingsStore.openPage(r.settings); SettingsStore.reveal = r.reveal ?? "" }
        else if (r.profile !== undefined) Power.setProfile(r.profile)
        else if (r.stage) StageState.toggle(Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.name : "")
        else if (r.awake) Awake.set(!Awake.on)
        else if (r.mode) SettingsStore.set("colors.mode", r.mode)
        else if (r.overview) OverviewState.toggle("")
        else if (r.copy !== undefined) Quickshell.execDetached(["wl-copy", "--", r.copy])
        else if (r.web) Quickshell.execDetached(["uwsm", "app", "--", "xdg-open", (engine ?? engines.duckduckgo).url + encodeURIComponent(r.web)])
        else if (r.webappRemove) {
            Quickshell.execDetached(["bbkos-webapp", "remove", r.webappRemove])
            webapps = webapps.filter(w => w.slug !== r.webappRemove)
        }
    }

    // ---- Uninstall (the Delete key on an app or web app): a second Delete within 4 s, then bbkos-uninstall, which
    // removes a web app at once and runs `sudo pacman -Rns` (or flatpak uninstall) in a floating terminal, where pacman
    // lists what goes, unneeded dependencies included, and asks Y/n. Core packages and apps from no package manager
    // are refused with a notification.
    function uninstall(item) {
        if (!item || !item.entry) return
        const key = "uninstall:" + item.id
        if (root.armed !== key) { root.armed = key; disarm.restart(); return }
        root.armed = ""
        Quickshell.execDetached(["bbkos-uninstall", item.entry.id])
        if (item.kind === "webapp") webapps = webapps.filter(w => "app:bbkos-webapp-" + w.slug !== item.id)
        else root.open = false
    }

    // ---- Create web app: bbkos-webapp install NAME URL (fetches the icon, about 1-5 s).
    Process {
        id: installer
        stdout: StdioCollector { id: installOut }
        stderr: StdioCollector { id: installErr }
        onExited: code => {
            const w = menu.item
            if (!w) return
            w.formBusy = false
            if (code === 0) {
                w.formStatus = "Created. It is in this menu now."
                root.remember("app:bbkos-webapp-" + installOut.text.trim(), "")
                webappList.running = true
                w.closeForm()
                w.setQuery(root.lastCreated)
            } else {
                w.formStatus = installErr.text.trim() || "Could not create the web app"
            }
        }
    }
    property string lastCreated: ""
    function createWebApp(name: string, url: string) {
        lastCreated = name
        menu.item.formBusy = true
        menu.item.formStatus = "Creating (fetching the site's icon)…"
        installer.command = ["bbkos-webapp", "install", name, url]
        installer.running = true
    }

    IpcHandler {
        target: "launcher"
        function toggle(): void { root.open = !root.open }
        function close(): void { root.open = false }
        function forget(): void { root.forgetUsage() }          // the Launcher page's "Forget what the menu learned"
        function launch(id: string): void {            // scripting and tests: qs ipc call launcher launch kitty
            const e = DesktopEntries.byId(id)
            if (e) root.launchEntry(e)
        }
        // Test hooks: the top results for a query, as the menu would show them; and the web app form.
        function query(text: string): string {
            return JSON.stringify(root.search(text).slice(0, 9).map(r => ({ id: r.id, title: r.title, tag: r.tag ?? "" })))
        }
        function type(text: string): void { if (menu.item) menu.item.setQuery(text) }
        function form(): void { if (menu.item) menu.item.openForm() }
        function grid(on: bool): void { if (menu.item) menu.item.showGrid(on) }
        function create(name: string, url: string): void { if (menu.item) { menu.item.openForm(); root.createWebApp(name, url) } }
        // Carry out the result with this id for this query, as Enter would (twice for a command that asks to confirm).
        function run(id: string, query: string): string {
            const r = root.search(query).find(x => x.id === id)
            if (!r) return "not found"
            root.activate(r, query)
            return root.armed === id ? "armed" : "done"
        }
        function del(id: string, query: string): string {     // test hook: the Delete key on that result
            const r = root.search(query).find(x => x.id === id)
            if (!r) return "not found"
            root.uninstall(r)
            return root.armed === "uninstall:" + id ? "armed" : "done"
        }
    }

    LazyLoader {
        id: menu
        active: root.open

        MenuWindow {
            results: root.search(query)
            apps: grid ? root.appsFor(query) : []
            armedId: root.armed
            onActivated: item => root.activate(item, query)
            onUninstall: item => root.uninstall(item)
            onEdited: root.armed = ""
            onDismissed: root.open = false
            onCreateWebApp: (name, url) => root.createWebApp(name, url)
        }
    }
}
