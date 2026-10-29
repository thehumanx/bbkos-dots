.pragma library
// The settings window's pages, in sidebar order, grouped. The one list of pages: the window (SettingsWindow.qml), the
// bbkOS menu (launcher/Commands.js) and the search index (scripts/build-settings-index.py reads `page:` names here) use it.
// Each page: id, label, group, icon (Nerd Font glyph, one per page), keywords for the search, and tabs. A page with
// one tab shows no tab bar. Each tab: id, label, page (the Page*.qml component that draws it), keywords.
// A place in the window is "page" or "page/tab" (`qs ipc call settings page windows/stage`, SettingsStore.openPage).
// Reorganised 2026-10-28 from 30 flat pages to these 16 (docs/modules/settings-app.md, "Reorganisation").

var GROUPS = ["Look", "Desktop", "Devices", "System"]

var PAGES = [
    { id: "appearance", label: "Appearance", group: "Look", icon: "",
      keywords: "theme look style",
      tabs: [
        { id: "wallpaper", label: "Wallpaper and colours", page: "PageWallpaper",
          keywords: "wallpaper background image colour color theme palette dark light mode accent contrast scheme schedule automatic folder icons tint" },
        { id: "style", label: "Style", page: "PageShell",
          keywords: "shell grid mode font text size radius corners gap popup shadow reduce motion" },
        { id: "terminal", label: "Terminal", page: "PageTerminal", keywords: "kitty terminal font padding opacity" }] },
    { id: "bar", label: "Bar", group: "Look", icon: "",
      keywords: "bar panel",
      tabs: [
        { id: "layout", label: "Layout", page: "PageBarLayout",
          keywords: "position top bottom left right thickness height float hug radius widget order sections drag" },
        { id: "look", label: "Look", page: "PageBarLook",
          keywords: "opacity blur pills widget background padding icons only icon style" },
        { id: "widgets", label: "Widgets", page: "PageBarWidgets",
          keywords: "clock date time 24 hour seconds calendar week numbers moon music media song player width" }] },
    { id: "windows", label: "Windows", group: "Look", icon: "",
      keywords: "window",
      tabs: [
        { id: "look", label: "Look", page: "PageWindows",
          keywords: "gaps border rounding opacity shadow blur animation speed resize grab" },
        { id: "behaviour", label: "Behaviour", page: "PageBehavior",
          keywords: "focus follow mouse click activate workspace switch back snap floating" },
        { id: "stage", label: "Stage mode", page: "PageStage", keywords: "stage manager mode rail tiling monocle cards" }] },
    { id: "lock", label: "Lock screen", group: "Look", icon: "",
      keywords: "lock screen hyprlock avatar picture photo profile image clock blur welcome password",
      tabs: [{ id: "editor", label: "Lock screen", page: "PageLock", keywords: "" }] },

    { id: "notifications", label: "Notifications", group: "Desktop", icon: "",
      keywords: "notifications popups do not disturb dnd timeout critical history corner mute apps",
      tabs: [{ id: "main", label: "Notifications", page: "PageNotifications", keywords: "" }] },
    { id: "apps", label: "Apps", group: "Desktop", icon: "",
      keywords: "apps applications",
      tabs: [
        { id: "defaults", label: "Default apps", page: "PageApps",
          keywords: "default browser terminal files images video music pdf mail open with mime" },
        { id: "startup", label: "Startup", page: "PageStartup", keywords: "startup autostart login start" },
        { id: "launcher", label: "Launcher", page: "PageLauncher",
          keywords: "launcher menu search super r web search engine calculator results learn frecency forget commands" }] },
    { id: "capture", label: "Capture and camera", group: "Desktop", icon: "",
      keywords: "capture",
      tabs: [
        { id: "capture", label: "Screenshots and recording", page: "PageCapture",
          keywords: "screenshot screen recording record video folder editor fps quality" },
        { id: "camera", label: "Camera", page: "PageCamera",
          keywords: "webcam camera exposure brightness contrast white balance gamma saturation" }] },
    { id: "privacy", label: "Privacy and wellbeing", group: "Desktop", icon: "",
      keywords: "privacy indicator microphone mic camera screen sharing clipboard history copy paste images clear screen time break reminder look away eyes",
      tabs: [{ id: "main", label: "Privacy and wellbeing", page: "PagePrivacy", keywords: "" }] },

    { id: "network", label: "Network", group: "Devices", icon: "",
      keywords: "network wifi wi-fi saved connections forget tailscale vpn phone mirror",
      tabs: [{ id: "main", label: "Network", page: "PageNetwork", keywords: "" }] },
    { id: "displays", label: "Displays", group: "Devices", icon: "",
      keywords: "display monitor screen scale zoom night light blue light warm temperature schedule hyprsunset",
      tabs: [{ id: "main", label: "Displays", page: "PageDisplays", keywords: "" }] },
    { id: "sound", label: "Sound", group: "Devices", icon: "",
      keywords: "sound audio volume output input microphone speaker mute apps devices",
      tabs: [{ id: "main", label: "Sound", page: "PageSound", keywords: "" }] },
    { id: "power", label: "Power and sleep", group: "Devices", icon: "",
      keywords: "power sleep",
      tabs: [
        { id: "idle", label: "When idle", page: "PageIdle",
          keywords: "idle sleep suspend dim lock screen off timeout awake keep awake" },
        { id: "lid", label: "Lid and power button", page: "PageLidPower",
          keywords: "lid close closed power button suspend hibernate shutdown power off clamshell laptop bag charger" },
        { id: "profiles", label: "Power profiles", page: "PagePower",
          keywords: "power profile battery cpu turbo epp energy saver performance balanced cap" }] },
    { id: "keyboard", label: "Keyboard", group: "Devices", icon: "",
      keywords: "keyboard",
      tabs: [
        { id: "typing", label: "Typing", page: "PageKeyboard",
          keywords: "layout variant caps lock repeat rate delay numlock" },
        { id: "shortcuts", label: "Shortcuts", page: "PageKeybindings",
          keywords: "keybindings keys shortcuts bindings hotkeys super" },
        { id: "dictation", label: "Dictation", page: "PageDictation",
          keywords: "dictation voice speech talk microphone voxtype whisper type transcribe" }] },
    { id: "mouse", label: "Mouse and touchpad", group: "Devices", icon: "",
      keywords: "mouse touchpad pointer",
      tabs: [
        { id: "mouse", label: "Mouse and cursor", page: "PageMouse",
          keywords: "mouse pointer speed acceleration natural scrolling left handed cursor size theme hide typing still follows focus" },
        { id: "touchpad", label: "Touchpad", page: "PageTouchpad",
          keywords: "touchpad tap click scroll natural drag lock disable while typing" },
        { id: "gestures", label: "Gestures", page: "PageGestures",
          keywords: "gestures swipe workspace three four fingers" }] },

    { id: "accessibility", label: "Accessibility", group: "System", icon: "",
      keywords: "accessibility reduce motion contrast text size large cursor size key repeat slow keys vision",
      tabs: [{ id: "main", label: "Accessibility", page: "PageAccessibility", keywords: "" }] },
    { id: "about", label: "About and system", group: "System", icon: "",
      keywords: "system",
      tabs: [
        { id: "about", label: "About and updates", page: "PageAbout",
          keywords: "about system info updates kernel version battery health uptime update" },
        { id: "reset", label: "Reset", page: "PageReset", keywords: "reset defaults restore revert" }] }
]

// The page with this id, or null.
function find(id) {
    for (var i = 0; i < PAGES.length; i++) if (PAGES[i].id === id) return PAGES[i]
    return null
}

// "page" or "page/tab" -> { page, tab } (tab index), or null for an unknown place. A missing or unknown tab is tab 0.
function resolve(place) {
    var parts = String(place).split("/")
    var p = find(parts[0])
    if (p === null) return null
    var t = 0
    if (parts.length > 1)
        for (var i = 0; i < p.tabs.length; i++) if (p.tabs[i].id === parts[1]) t = i
    return { page: p.id, tab: t }
}
