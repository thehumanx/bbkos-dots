# Module: bar

Part of the Quickshell shell (see `quickshell.md`). One bar per screen on the edge `Theme.barPosition` (top, bottom, left or right), thickness `Theme.barHeight` (setting `shell.barHeight`, default 30 px, 24-48 in steps of 2; the owner uses 36), reserves space. Files in `dotfiles/quickshell/.config/quickshell/modules/bar/`.

| Widget | Source | Interaction | Shown when |
|---|---|---|---|
| Workspaces | `Quickshell.Hyprland` (`workspaces`, `focusedWorkspace`) | click activates | always (ids above 0) |
| Clock | `SystemClock`, minute precision; "Sun 25, 5:26" | click opens the calendar; hover shows a card with the full date (`media.md`) | always |
| Updates | `services/Updates.qml` (`checkupdates`, every 30 min, 5 min after a failed check; repo packages only, not AUR) | click opens a floating terminal running `bbkos-update` (`yay -Syu`, then `bbkos-check`) | at least one update pending. Icon and count, default place right after the clock |
| Tray | `Services.SystemTray` | left activate, middle secondary, right menu | one icon per item that registers (Vivaldi registers none on Linux; apps like nm-applet, Discord, Steam, Claude Desktop do). Monochrome icons (every visible pixel nearly grey, read through a small Canvas) are recoloured to the bar's text colour (`MultiEffect`), so black app icons stay visible; coloured icons such as Spotify's keep their colours |
| Audio | `Services.Pipewire` | click opens the popup, middle click mutes, scroll 5 % | always |
| Bluetooth | `Quickshell.Bluetooth` | none | adapter present. Icon by state: bluetooth-off (adapter off), bluetooth-connect in accent (devices connected), bluetooth otherwise (Material icons) |
| Network | `Quickshell.Networking` | none | always (Wi-Fi name with signal bars from the joined network's `signalStrength`, wired globe, or a crossed Wi-Fi icon with `off` (Wi-Fi switched off), `connecting…` (a network is being joined) or `offline` (on, not connected)) |
| Battery | `Services.UPower` | none | laptop battery present |
| Notifications | `services/Notifs.qml` (`NotificationServer` + persisted history, capped at 100) | click opens the history sheet (`docs/modules/notifications.md`); count is unread, cleared with "Mark all read" | always, so the history is always reachable. Bell plus accent count while unread (`99+` above 99) |
| Music | `services/Media.qml` (MPRIS; `media.*`, `media.md`) | left click opens the app the song plays in, middle skips, scroll sets the volume; hover shows previous, play or pause and next | a song is playing or paused; horizontal bars only |
| Recording | `services/Record.qml` (`bbkos-record status`) | click stops and saves the recording | only while a recording runs: a red dot and the elapsed time, default end section before the tray (`capture.md`) |
| Privacy | `services/Privacy.qml` (PipeWire streams) | none | only while an app uses the microphone, camera or a screen share: amber glyphs, default end section after the recording indicator (`privacy.md`) |
| Settings (gear) | `SettingsStore.windowOpen` (accent while open) | click opens or closes the settings window (`settings-app.md`; the click is not yet confirmed) | always, right end |

Later phases (planned, not built): CPU/RAM/temperature, calendar popup, power-profile control (`PowerProfiles` is already available in `Power.qml`).

## Settings (Bar page of the settings app, tabs Layout, Look and Widgets since 2026-10-28; `shell.*` keys; `docs/modules/theme.md` has the ranges)

| Key | Default | Effect |
|---|---|---|
| `barPosition` | top | edge of the screen; vertical bars show icon-only widgets (value on a second line for brightness, volume, battery) and a two-line clock |
| `barOpacity` | 1.0 (0.2-1.0) | bar background alpha (`Theme.barBg`) |
| `barBlur` | false | blur behind the bar; only with opacity below 1. Drawn by the bar itself (`BarBlur.qml`, below), not by a Hyprland layer rule |
| `barBlurAmount` | 0.5 (0.05-1.0) | strength of the bar's blur, independent of the windows' blur |
| `tint` | 0.8 (0-1) | how far widget icons lean toward the wallpaper tints (`theme.md`, "Tints") |
| `barPills` | off | `off`, `grouped` (one pill per section: start, centre, end) or `individual` (one per widget) |
| `barItemPad` | 0 (0-24, step 2) | "Widget padding": extra space inside each widget, left and right (top and bottom on a vertical bar), in every bar mode. Added to an individual pill's own 8 px (so grid mode, which forces individual pills, starts at 8); grouped pills keep their own fixed 10 px around the group |
| `pillRadius` | 8 (0-16, step 2) | corner radius of the pills |
| `barFloat` | 0 (0-24, step 2) | space around the bar: it floats this far off the screen edges. Applies to the edge the bar sits on and, when it spans the edge, to both ends |
| `barRadius` | 0 (0-24, step 2) | corner radius of the bar itself (capped at half the thickness); with a float or hug the rounded body shows against the wallpaper |
| `barHug` | false | the bar body is only as long as its three groups (start, centre, end, a `shell.gap` apart) and is centred on the edge |
| `bar.iconWifi` | bars | Wi-Fi icon set: `bars` (signal strength), `material`, `fa`, `none` |
| `bar.iconBluetooth` | material | Bluetooth icon set: `material`, `fa`, `none` |
| `bar.iconAudio` / `bar.iconBattery` | fa | volume and battery icon sets: `fa`, `material`, `none` |
| `bar.iconDisplay` | monitor | brightness widget icon set (the monitor glyph): `monitor`, `desktop`, `tv`, `none` |
| `bar.iconGap` | 2 (1-6) | "Icon to text gap": spaces between a widget's icon and its text, in the monospace font about 8 px each (`Theme.barIconGap`, `BarIcons.label(glyph, text, gap)`; the music widget uses 4 px per step; the clock, workspaces and tray have no icon). The space between widgets is `shell.barItemGap` ("Widget gap") |
| `bar.iconsOnly` | false | "Icons only" (top of Widget icons): no text on the widgets, see below |
| `bar.iconSettings` | fa | gear icon set: `fa`, `material` (no `none`, the gear must stay clickable) |

The icon sets are picked on Bar › Look ("Widget icons"); the glyphs live in `components/BarIcons.js`, keyed by the same names as `BAR_ICON_STYLES` in `bbkos_theme/settings.py`. A missing or unknown set falls back to the widget's first (default) set.

Popups, notifications and the OSD follow the bar: `Theme.barEdge` / `Theme.barInset` are the edge and thickness they clear. A popup opens at the widget that was clicked: just clear of the bar and centred on the widget along it (under it on a top bar, above it on a bottom bar, beside it on a left or right bar), pushed in by one gap where that would leave the screen. The widget's `BarHit.center()` gives its position, `PanelState.toggle(which, screen, along)` carries it, `Panels.qml` places the card. Opened without a widget (the power key, `qs ipc call panel toggle`) it sits in the corner at the bar's end (top right for a top bar, bottom right for a bottom bar, top left for a left bar, top right for a right bar). A new popup widget passes `hit.center()` the same way (give its `BarHit` an `id`). The notification history is the exception: a full-height sheet on the right for every bar position (see `notifications.md`).

## Grid mode (2026-10-26)

The `title` widget (2026-10-30, `dock.md`) shows the focused window's icon and title in a fixed-width cell after the workspaces; horizontal bars only. In grid mode with the dock on, the workspaces cell (the first) is as wide as the rail, so the title cell's edge meets the rail's (`dock.md`).

With `shell.gridMode` (`grid-mode.md`) every widget is a cell the full thickness of the bar, drawn with a hairline border (`Theme.cardEdge`) and touching its neighbours (they overlap by one hairline so a shared line is drawn once); a line also runs along the bar's inner edge, and the empty space between the start, centre and end groups (and beside them) is filled with empty cells in the same style, so the bar reads as one seamless row (2026-10-28; `Bar.qml` `gridFills`). Checked at top, bottom, left and right on both screens; the gap's colour went from the bare bar (4,37,51) to the cell colour (16,42,53 beside a clock cell of 15,44,55). No float, no radius, no hug, no gap between widgets, whatever the saved values are.

## Icons only (2026-10-26)

`bar.iconsOnly` (read as `Theme.barIconsOnly`, from `ThemeStore.settings.bar`) strips the text from the widgets: Wi-Fi shows the signal glyph (not the network name), Bluetooth the glyph (not the device), Audio, Battery and Display their icon (not the percentage), Music the note (not the title; the hover buttons still appear and the widget widens for them), Recording the red dot (not the time). Notifications keep the bell and show a small accent dot (`components/BadgeDot.qml`, 6 px, top right of the icon) while something is unread, instead of the count; Updates keep their icon and show the dot in accent2 whenever the widget is shown (it is only shown while updates are pending). Not changed on purpose: the clock, the workspace numbers, the timer's countdown and the tray, which are the content, not a label. A Wi-Fi icon set of `none` has no glyph, so that widget keeps its text rather than vanishing. Vertical bars are unchanged in practice (they already showed icons, with the value on a second line, which this also removes).

## Floating, rounded and hugging bar (2026-10-21)

The bar window is the bar plus the space it floats off its edge (`Theme.barHeight + Theme.barFloat` thick); the bar itself is `body` in `Bar.qml`, drawn inside it. The window is transparent and its input region is the body (`mask: Region`), so the space around a floating or hugging bar lets clicks through to what is below. The compositor reserves the whole window, so windows start below the float. `Theme.barInset` (what popups, notifications, the OSD and the stage clear) is the thickness plus the float. Body geometry: attached it fills the window; floating it is inset by `barFloat` from the screen edges (top and both ends for a top bar); hugging its length is `sum of the group sizes + one gap between groups and at both ends` and it is centred, each `BarSection` taking its start from `hugPos`. `barRadius` rounds the body; the blur (`BarBlur`) and the contrast sampling (`BarContrast.strip`) follow the body's rectangle, and the blur is masked to the rounded corners. Defaults reproduce the old attached, square bar exactly.

## Hide or show (2026-10-21)

`Super+Shift+Space` (preset `toggle-bar`), or `qs ipc call bar toggle|hide|unhide`. State is `services/BarState.qml` (runtime only: a shell restart brings the bar back). Hidden, the bar window is unmapped, so its reserved edge is freed and windows reflow (the stage rail is mapped again when the bar returns, so it lands after the bar: `dock.md`), and `Theme.barInset` is 0, so panels, notifications, the OSD and the stage rail move to the screen edge. (`show` is not usable as an IPC function name: `qs ipc call bar show` printed the help instead of calling it, hence `unhide`.) Verified 2026-10-21: layer present/absent via `hyprctl layers` and a power panel screenshot at top, bottom, left and right. Not verified: notifications with the bar hidden, a second monitor.

## Bar blur (2026-10-21)

`modules/bar/BarBlur.qml`: the wallpaper strip under the bar (cover-fit like `modules/wallpaper`, the strip geometry comes from `BarContrast.strip`), blurred with a `MultiEffect` on a quarter-size copy scaled back up (a blur has no fine detail, so a quarter-size copy looks the same), then the bar colour at the bar opacity on top. While it shows the bar window's own colour is transparent. It replaces the Hyprland layer rule `bbkos-bar-blur`: a layer rule has no strength of its own (it uses `decoration.blur` size and passes, the windows' values), so the bar could not be tuned apart from the windows. A bar reserves its edge, so only the wallpaper is behind it; a floating window dragged under the bar is no longer blurred behind it (accepted). Static: nothing redraws until the wallpaper, the amount or the position changes.

Measured 2026-10-21 (edge energy of the bar crop, ffmpeg `sobel`+`signalstats`): no blur 30.4, amount 0.05 15.4, 0.5 13.8, 1.0 12.9. The step from 0.05 to 1.0 is small on this soft wallpaper; a busier image shows more. Checked by screenshot at top, bottom, left and right with blur on. Not measured: GPU or battery cost of the blur.

## Widget colours (2026-10-21)

Widgets lean toward the wallpaper tints through `Txt.tone(Theme.accentN)` (`Theme.tinted`, strength `shell.tint`): Network and Notifications-read use accent / accent2, Clock, Audio, Bluetooth, Workspaces and the gear accent3, Display, Battery and Updates accent2. State colours are unchanged (accent when connected, plugged in or open; warn and crit on a low battery).

## Active widget (2026-10-21)

While a widget's popup or window is open, its `BarItem` draws a plate behind it: the accent at 30% (`BarItem.highlighted`, 120 ms fade; a little wider than the box along the bar when there are no pills). `Bar.qml` sets `highlighted` per widget: the panel widgets from `PanelState.isOn(panel, screenName)` (the screen the panel opened on; a panel opened with no screen, by the power key or IPC, matches the focused monitor), the gear from `SettingsStore.windowOpen`. Checked by screenshot for the Wi-Fi, audio and battery panels and the gear, with pills off, individual pills and a left bar. Not checked: grouped pills, bottom and right bars, a second monitor.

## Layout and adding a widget

Any widget can be switched off (2026-10-31): the switch at the start of its row in Bar › Layout, or `bbkos-theme set bar.hidden tray,updates` (`settings.py` `bar.hidden`). A hidden widget is not created at all and leaves no pill or grid cell (the empty cells close up), but keeps its place in `bar.layout`. A popup whose widget is hidden still opens from its key or IPC, in the screen corner (Popup placement).


`Bar.qml` places three `BarSection`s (start, centre, end) per screen; each item sits in a `BarItem`. The two components own everything the settings change (orientation, pill, radius, thickness), so a new widget needs no styling code:

1. Write the widget as an item (usually a `Txt`; use `fgColor` / `dimColor` for text colours, not `Theme.fg` / `Theme.dim`).
2. For a clickable widget use `BarHit { onClicked: ... }` (`components/BarHit.qml`) instead of `MouseArea { anchors.fill: parent }`: it covers the whole BarItem (pill, padding and the bar's full thickness), not just the glyph and text. A widget of several clickable parts (workspace numbers, tray icons) sets `crossOnly: true`: each part keeps its own length along the bar, plus half the widget gap either side, and takes the full thickness.
3. Put it in a section: `BarItem { MyWidget {} }`. A widget with nothing to show some of the time sets `active` on its `BarItem` (`BarItem { active: Foo.available; ... }`), never `visible` on the widget (a hidden widget would still leave an empty pill).
4. In a vertical bar (`Theme.barVertical`) keep the widget narrow: icon only, or icon and value on two lines.

Verified with a throwaway `BarItem { Txt { text: "T 00:00" } }`: it took the position, pill mode and radius with no other change.

## Text colour on a translucent bar

Colours come from the wallpaper palette (matugen) as everywhere. While the bar is translucent and has no pills, `BarContrast` (one per bar) samples the wallpaper strip behind the bar through an offscreen `Canvas` (cover-fitted like the wallpaper window, 32x8 samples, mean relative luminance), blends it with the bar tint at the bar opacity, and picks the palette `fg` if it reaches contrast 4.5 against that backdrop, else the palette background colour (the opposite tone); `dim` needs 3.0, else a faded `fg`. Pills and an opaque bar use the palette's own `fg` / `dim`. `Txt.fgColor` / `dimColor` read the colours from the bar window (`QsWindow.window.barFg` / `barDim`) and fall back to `Theme.fg` / `Theme.dim` anywhere else. Re-sampled when the wallpaper (path or bytes), position, thickness or screen size changes; a missing or unreadable wallpaper keeps the palette colours. Test hook: `qs ipc call bar status` (per bar: luma, backdrop, colours in use).

Measured: the Canvas decode of the owner's 6000x4000 wallpaper took about 0.5 s (asynchronous, once per change, nothing kept afterwards). Not unit-tested in QML (no QML test harness here); the luminance maths was asserted in a scratch Quickshell and the sampling run in an isolated shell with white, black and the real wallpaper.
