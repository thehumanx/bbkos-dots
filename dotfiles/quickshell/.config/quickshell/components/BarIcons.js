.pragma library

// Glyph sets for the bar's widget icons (Nerd Font codepoints; Material = nf-md, Font Awesome = nf-fa). The style keys
// are the values the settings accept for bar.icon<Widget> (bbkos_theme/settings.py BAR_ICON_STYLES). The first set of
// each widget is its default and what an unknown or missing style falls back to. "none" draws no glyph.

const sets = {
    wifi: {
        bars: { name: "Signal bars", levels: ["󰤨", "󰤥", "󰤢", "󰤟"], off: "󰖪", wired: "󰈀" },
        material: { name: "Material", levels: ["󰖩", "󰖩", "󰖩", "󰖩"], off: "󰖪", wired: "󰈀" },
        fa: { name: "Font Awesome", levels: ["", "", "", ""], off: "", wired: "" },
        none: { name: "None", levels: ["", "", "", ""], off: "", wired: "" },
    },
    bluetooth: {
        material: { name: "Material", idle: "󰂯", connected: "󰂱", off: "󰂲" },
        fa: { name: "Font Awesome", idle: "", connected: "", off: "" },
        none: { name: "None", idle: "", connected: "", off: "" },
    },
    audio: {
        fa: { name: "Font Awesome", muted: "", headphones: "", low: "", high: "" },
        material: { name: "Material", muted: "󰝟", headphones: "󰋋", low: "󰕿", high: "󰕾" },
        none: { name: "None", muted: "", headphones: "", low: "", high: "" },
    },
    battery: {
        fa: { name: "Font Awesome", levels: ["", "", "", "", ""], bolt: "" },
        material: { name: "Material", levels: ["󰁹", "󰂀", "󰁽", "󰁻", "󰁺"], bolt: "" },
        none: { name: "None", levels: ["", "", "", "", ""], bolt: "" },
    },
    display: {
        monitor: { name: "Monitor", icon: "󰍹" },
        desktop: { name: "Desktop", icon: "" },
        tv: { name: "TV", icon: "" },
        none: { name: "None", icon: "" },
    },
    settings: {
        fa: { name: "Font Awesome", icon: "" },
        material: { name: "Material", icon: "󰒓" },
    },
}

// The set for one widget and setting value; falls back to the widget's default (its first set).
function style(widget, value) {
    const s = sets[widget]
    return s[value] ?? s[Object.keys(s)[0]]
}

// `gap` spaces (Theme.barIconGap, default 2) between an icon and its text.
function gapText(gap) {
    return " ".repeat(gap ?? 2)
}

// Glyph, `gap` spaces, text; just the text when there is no glyph.
function label(glyph, text, gap) {
    return glyph === "" ? text : glyph + gapText(gap) + text
}

// Settings choices for one widget: each style with its glyphs as a sample. Plain loops: the QML engine has no flatMap.
function choices(widget) {
    const s = sets[widget]
    return Object.keys(s).map(k => {
        const d = s[k]
        let sample = ""
        for (const f of Object.keys(d)) {
            if (f === "name") continue
            const v = Array.isArray(d[f]) ? d[f] : [d[f]]
            for (const g of v) if (g !== "" && sample.indexOf(g) < 0) sample += (sample === "" ? "" : " ") + g
        }
        return { value: k, label: sample === "" ? d.name : sample + "  " + d.name }
    })
}
