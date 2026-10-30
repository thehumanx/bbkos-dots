pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Hyprland
import qs.services

// Single place for look-and-feel values. Bound to the generated theme (services/ThemeStore.qml, written by
// `bbkos-theme`); ThemeStore falls back per value to today's built-in look (in brackets) when the file is missing or bad.
Singleton {
    readonly property color bg: ThemeStore.colors.bg                   // #101014
    readonly property color surface: ThemeStore.colors.surface         // #1b1b22
    readonly property color fg: ThemeStore.colors.fg                   // #e6e6ea
    readonly property color dim: ThemeStore.colors.dim                 // #a7a8b3
    readonly property color accent: ThemeStore.colors.accent           // #7fa8fd
    readonly property color warn: ThemeStore.colors.warn               // #e0af68
    readonly property color crit: ThemeStore.colors.crit               // #ff8298
    // Wallpaper tints (docs/modules/theme.md "Tints"): `accent` is the wallpaper's primary tone; `accent2` / `accent3` are
    // that hue turned either way, `*Soft` the deep shade of each (backgrounds), `surfaceHigh` a raised surface.
    readonly property color accent2: ThemeStore.colors.secondary
    readonly property color accent3: ThemeStore.colors.tertiary
    readonly property color accentSoft: ThemeStore.colors.accentSoft
    readonly property color accent2Soft: ThemeStore.colors.secondarySoft
    readonly property color accent3Soft: ThemeStore.colors.tertiarySoft
    readonly property color surfaceHigh: ThemeStore.colors.surfaceHigh
    // Grid mode's cell border: one opaque colour from the wallpaper's palette (the surface leaned toward the text colour).
    readonly property color gridEdge: ThemeStore.colors.gridEdge
    // The surfaces below (popupBg, inset, control, pillBg) are the ones the theme engine checks text contrast on:
    // bbkos_theme/a11y.py `surfaces` is the same arithmetic. Change one, change the other.
    // Background of popups, notification cards, the volume OSD and dialogs: the surface leaned toward the wallpaper's deep
    // shade by the tint setting (up to 50%), instead of a plain grey-teal. Opaque.
    readonly property color popupBg: Qt.tint(surface, Qt.rgba(accentSoft.r, accentSoft.g, accentSoft.b, tint * 0.5))
    // Parts inside a popup or card, both derived from popupBg so they follow the wallpaper tint with it: `inset` is the
    // sunken shade (progress tracks, selected rows, notification cards, inputs, dividers), `control` the raised one
    // (buttons, chips, hover rows).
    readonly property color inset: Qt.tint(popupBg, Qt.rgba(bg.r, bg.g, bg.b, 0.55))
    readonly property color control: Qt.tint(popupBg, Qt.rgba(fg.r, fg.g, fg.b, 0.12))
    // shell.tint (0-1): how far widget colours lean toward their tint. 0 = plain text colour everywhere.
    readonly property real tint: ThemeStore.shell.tint
    // `base` (the text colour where the widget sits) leaned toward `tone` by the tint setting.
    function tinted(tone: color, base: color): color { return Qt.tint(base, Qt.rgba(tone.r, tone.g, tone.b, tint)) }

    // Shadow under popups, pickers, notification cards and the OSD (shell.popupShadow, 0 = none): a near-black shade of
    // the wallpaper's hue rather than plain black, stronger on a dark theme where a black shadow barely shows.
    readonly property real shadowStrength: ThemeStore.shell.popupShadow   // 0.5
    readonly property color shadow: Qt.hsla(Math.max(0, accent.hslHue), Math.min(0.5, accent.hslSaturation), 0.05,
                                            shadowStrength * (bg.hslLightness > 0.5 ? 0.4 : 0.85))
    readonly property int shadowPad: 32   // free room a card's window keeps around the card for its shadow (blur + offset)
    // Grid mode (shell.gridMode, docs/modules/grid-mode.md): no rounding, no gaps, hairline borders between cells. The
    // renderer already hands over radii, gaps and shadow as 0 (settings.GRID_OVERRIDES), so those tokens need nothing here;
    // this flag is for what a token cannot say: the cell borders, the stronger edge, square knobs and tracks.
    readonly property bool gridMode: ThemeStore.shell.gridMode
    // Grid mode squares the corners of popups, buttons and controls too, unless shell.gridRoundControls keeps them round (the bar, windows and stage cards are always square).
    // Grid mode: the margin around the windows (windows.gapsOut), which the stage rail uses for its padding and the gap between
    // its tiles (settings.py grid_rail_gap, capped at the rail settings' maximum of 32).
    readonly property int gridMargin: Math.min(32, Math.max(0, Math.round((ThemeStore.settings.windows ?? ({})).gapsOut ?? 20)))
    // Grid mode: the windows' corner radius (windows.rounding, not overridden by grid mode), which the pinned-app tiles share.
    readonly property int gridWindowRadius: Math.max(0, Math.round((ThemeStore.settings.windows ?? ({})).rounding ?? 10))
    readonly property bool gridSquare: gridMode && !ThemeStore.shell.gridRoundControls
    // The hairline edge every floating card has, so it never melts into what is behind it. A grid draws every cell's edge, in the opaque gridEdge: where two cells overlap by a hairline a translucent edge would stack twice.
    readonly property color cardEdge: gridMode ? gridEdge : Qt.rgba(fg.r, fg.g, fg.b, 0.08)

    // Motion (docs/modules/motion.md): Emil Kowalski's curves, as Easing.BezierSpline control points. easeOut for
    // things that appear or answer a press, easeInOut for something moving across the screen, easeDrawer (iOS sheets)
    // for large surfaces. hypr-theme.lua uses the same curves for windows and workspaces.
    readonly property bool reduceMotion: ThemeStore.shell.reduceMotion // false: fades only, no scale or slide
    readonly property var easeOut: [0.23, 1, 0.32, 1, 1, 1]
    readonly property var easeInOut: [0.77, 0, 0.175, 1, 1, 1]
    readonly property var easeDrawer: [0.32, 0.72, 0, 1, 1, 1]
    readonly property int durFast: 120     // hover, press, switch, colour
    readonly property int durEnter: 200    // a popup or card arriving
    readonly property int durExit: 140     // leaving is quicker than arriving
    readonly property int durLarge: 300    // the overview zoom

    readonly property string font: ThemeStore.shell.font               // JetBrainsMono Nerd Font
    readonly property int fontSize: ThemeStore.shell.fontSize          // 13
    // Grid mode rounds the bar's thickness up to a whole number of physical pixels (26 → 30 at 16/15 scale, docs/modules/grid-mode.md):
    // a layer surface is a whole number of logical pixels, and where a fractional physical edge is shared (the bar's last row and the
    // rail's first) the compositor redraws it from one surface alone and the bar's edge line drops out. The saved value is kept.
    readonly property int barHeight: gridMode ? wholePixels(ThemeStore.shell.barHeight) : ThemeStore.shell.barHeight   // 30
    // A screen's real scale (1.0667 on this panel), from Hyprland. Not ShellScreen.devicePixelRatio: that is the output's
    // integer scale, 2 here, and a "hairline" of 1/2 logical px was 0.53 physical px, drawn or dropped by where it fell.
    function scaleOf(screen: var): real {
        const m = screen ? Hyprland.monitorFor(screen) : null
        return m && m.scale > 0 ? m.scale : 1
    }
    // Whether a length of `v` logical pixels is a whole number of physical pixels on `screen`.
    function exactOn(screen: var, v: real): bool {
        const p = v * scaleOf(screen)
        return Math.abs(p - Math.round(p)) < 0.001
    }
    // The smallest length from `v` to v + 15 that is whole on the most screens (the first such length when several tie): at
    // 16/15 (this panel) that is a multiple of 15, at 1.25 of 4, at 1 or 2 any. A scale with no whole length in that range keeps `v`.
    function wholePixels(v: int): int {
        let best = v, bestCount = -1
        for (let l = v; l <= v + 15; l++) {
            let n = 0
            for (const s of Quickshell.screens) if (exactOn(s, l)) n++
            if (n > bestCount) { best = l; bestCount = n }
        }
        return best
    }
    readonly property int gap: ThemeStore.shell.gap                    // 12
    readonly property int radius: ThemeStore.shell.radius              // 12: popups, cards, dialogs
    readonly property int controlRadius: ThemeStore.shell.controlRadius // 6: rows, buttons, inputs

    // Bar (modules/bar, docs/modules/bar.md). barBlur is already false at full opacity: nothing is behind an opaque bar.
    readonly property string barPosition: ThemeStore.shell.barPosition // top | bottom | left | right
    readonly property bool barVertical: barPosition === "left" || barPosition === "right"
    readonly property bool barIconsOnly: (ThemeStore.settings.bar ?? ({})).iconsOnly === true   // bar.iconsOnly: widgets draw their icon, no text
    readonly property int barIconGap: Math.max(1, Math.min(6, Math.round((ThemeStore.settings.bar ?? ({})).iconGap ?? 2)))   // bar.iconGap: spaces between a widget's icon and its text
    readonly property real barOpacity: ThemeStore.shell.barOpacity     // 1.0
    readonly property bool barBlur: ThemeStore.shell.barBlur && barOpacity < 1.0   // false
    readonly property real barBlurAmount: ThemeStore.shell.barBlurAmount   // 0.5: strength of the bar's own blur
    readonly property string barPills: ThemeStore.shell.barPills       // off | grouped | individual
    readonly property int pillRadius: ThemeStore.shell.pillRadius      // 8
    readonly property int barItemGap: ThemeStore.shell.barItemGap      // 12
    readonly property int barItemPad: ThemeStore.shell.barItemPad      // 0: extra space inside each widget, along the bar, on top of an individual pill's own 8 px
    readonly property real pillOpacity: ThemeStore.shell.pillOpacity   // 1.0
    // The pill leans toward the wallpaper's deep shade by the tint setting (up to 45%, so text keeps its contrast).
    readonly property color pillBg: {
        const c = Qt.tint(surface, Qt.rgba(accentSoft.r, accentSoft.g, accentSoft.b, tint * 0.45))
        return Qt.rgba(c.r, c.g, c.b, pillOpacity)
    }
    // What popups, notifications and the OSD must clear: the edge the bar sits on and how far it reaches into the screen (thickness plus the float space).
    readonly property string barEdge: barPosition
    readonly property int barFloat: ThemeStore.shell.barFloat          // 0: space around the bar (it floats clear of the edges)
    readonly property int barRadius: ThemeStore.shell.barRadius        // 0: corner radius of the bar itself
    readonly property bool barHug: ThemeStore.shell.barHug             // false: the bar shrinks to its widgets, centred on the edge
    readonly property int barInset: BarState.hidden ? 0 : barHeight + barFloat     // the bar's own thickness plus the space it floats off the edge
    readonly property color barBg: Qt.rgba(bg.r, bg.g, bg.b, barOpacity)
    // Text colours on the bar are per screen (they depend on the wallpaper behind that bar): Txt.fgColor / dimColor.
    // One physical screen pixel in logical units (15/16 on this panel at 1.0667). Hairlines and borders use this. It follows
    // the first screen's scale; a second screen with another scale gets lines slightly off one pixel (scaleOf gives its own).
    readonly property real hair: 1 / scaleOf(Quickshell.screens.length > 0 ? Quickshell.screens[0] : null)
    // `v` rounded to whole physical pixels (up, so nothing is cut), in steps of `hair`: grid cells are sized and placed with it
    // so each shared hairline lands on one pixel (a cell at a fractional position drew its joint two pixels wide).
    function wholeUp(v: real): real { return Math.ceil(v / hair - 0.001) * hair }
    function whole(v: real): real { return Math.round(v / hair) * hair }
}
