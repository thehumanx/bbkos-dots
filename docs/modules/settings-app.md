# Settings app (Quickshell)

`Super+,`, the gear icon at the right end of the bar, or `qs ipc call settings toggle` opens the bbkOS settings window: 16 pages in four groups (Look, Desktop, Devices, System), long pages split into tabs, a search that finds single settings, and a reset on every changed row and card. Source: `dotfiles/quickshell/.config/quickshell/` `modules/settings/{SettingsWindow,Sidebar,SettingsPage,Pages.js,SearchIndex.js,Page*}.qml`, `services/SettingsStore.qml`, `components/{SettingRow,SettingsSection,Setting{Slider,Toggle,Choice,Text},StepBar,Tabs,Chips}.qml`, `modules/bar/SettingsWidget.qml`, `scripts/build-settings-index.py`. Built in Task 10 (2026-10-18), grown to 30 pages by 2026-10-24, reorganised on 2026-10-28 (next section).

## Reorganisation (2026-10-28)

Owner request: "the settings app has grown a lot and the options are scattered all over the place": group related settings, better UX and UI, a better pattern for every control. The sections after this one describe the window as it grew; their page names, sidebar indices (`index 14`) and `settings page N` calls are history.

**Structure.** `modules/settings/Pages.js` is the one list of pages: the window, the bbkOS menu (`launcher/Commands.js`) and the search index read it. A page has tabs; a page with one tab shows no tab bar. A place is `page` or `page/tab` (`qs ipc call settings page windows/stage`, `SettingsStore.openPage`). Reference: DankMaterialShell's settings (`Common/SettingsTabs.qml`, a tree of pages with children; read in the scratchpad, nothing copied) has nearly the same grouping (Power & sleep, Mouse & touchpad, Displays with gamma inside, Applications with default and autostart apps, Digital wellbeing); GNOME Settings and KDE System Settings for the sidebar groups.

| Group | Page (id) | Tabs (id: page file) | Was |
|---|---|---|---|
| bbkOS (2026-10-31) | bbkOS (`bbkos`) | Grid mode (`grid`: PageGrid), Rail and pinned apps (`rail`: PageRail), Stage mode (`stage`: PageStage) | Grid mode on Appearance › Style; the rail and stage mode on Windows › Stage mode |
| Look | Appearance (`appearance`) | Wallpaper and colours (`wallpaper`: PageWallpaper), Style (`style`: PageShell), Terminal (`terminal`: PageTerminal) | Wallpaper and colours, Shell, Terminal |
| | Bar (`bar`) | Layout (PageBarLayout), Look (PageBarLook), Widgets (PageBarWidgets: clock, calendar, music) | Bar, Date and time, the music card of Sound |
| | Windows (`windows`) | Look (PageWindows), Behaviour (PageBehavior) | Windows, Window behaviour (Stage mode moved to bbkOS, 2026-10-31) |
| | Lock screen (`lock`) | one (PageLock) | Lock screen |
| Desktop | Notifications (`notifications`) | one | Notifications |
| | Apps (`apps`) | Default apps (PageApps), Startup (PageStartup), Launcher (PageLauncher) | Default apps, Startup apps, Launcher |
| | Capture and camera (`capture`) | Screenshots and recording (PageCapture), Camera (PageCamera) | Capture, Camera |
| | Privacy and wellbeing (`privacy`) | one (PagePrivacy: indicator, in use now, clipboard history, break reminder, screen on) | Privacy, Clipboard, Screen time |
| Devices | Network (`network`) | one | Network |
| | Displays (`displays`) | one (PageDisplays: scale per monitor, night light) | the Displays card of Shell, Night light |
| | Sound (`sound`) | one | Sound |
| | Power and sleep (`power`) | When idle (`idle`: PageIdle), Lid and power button (`lid`: PageLidPower), Power profiles (`profiles`: PagePower) | Idle and lock, Lid and power button, Power |
| | Keyboard (`keyboard`) | Typing (PageKeyboard), Shortcuts (PageKeybindings), Dictation (PageDictation, read-only, 2026-10-29: `dictation.md`) | the keyboard card of Keyboard and mouse, Keybindings |
| | Mouse and touchpad (`mouse`) | Mouse and cursor (PageMouse: mouse, cursor size and theme, the cursor rows of Window behaviour), Touchpad (PageTouchpad), Gestures (PageGestures: swipes, workspace swipe) | Keyboard and mouse, Touchpad, three cursor rows of Window behaviour |
| System | Accessibility (`accessibility`) | one; each row links to its own page | Accessibility |
| | About and system (`about`) | About and updates (PageAbout), Reset (PageReset: revert, reset everything) | About and updates, Reset |

Nothing was dropped: every key that had a row still has one. Duplicates removed: the calendar keys were on both the Bar and the Date and time page (now Bar › Widgets only; the Bar copy's moon hint was the true one, "shown with the selected day"). Every page has its own icon (Lock screen and Lid, Keybindings and Keyboard and mouse shared one).

**Window.** A header that stays put (page title, then `Tabs` when the page has more than one), the page under it scrolls; header and page are centred, at most 960 px wide (`maxContent`), so a tiled window no longer stretches rows to 1400 px. The tab last shown per page is kept while the window is open. The sidebar fits 16 entries without scrolling at 1166 px.

**Controls** (one rule: on/off is a `Toggle`; 2-6 named values or a short uneven set is `Chips`; a continuous number is a `StepBar`):
- `StepBar` (new; `SettingSlider` uses it): the owner kept the stepper and asked for the slider to become one with it. One 30 px control: `−` at the left end, `+` at the right end (hold to repeat), between them a bar filled up to the value in the soft accent with a 2 px accent edge, the value written at its right with its unit. Press or drag anywhere on the bar sets the value. Shape from Blender's number slider field. First tried with a full accent fill and the text in two colours: with the owner's near-white accent a full bar glared, so the fill is `accentSoft` and the text stays `fg`. The audio and display popups keep the old `Slider`.
- Units on every number (`suffix`: px, pt, s, ms, K, ×, /s; `percent: true` shows 0-1 as 0-100 %; `factor`/`decimals`: camera exposure in ms instead of tenths of a ms).
- Sliders that were really choices became chips: touchpad drag lock (Off, Until a short pause, Until the next tap) and three/four-finger drag (Off, Three fingers, Four fingers), colour from the image (Most common, Second, Third, Fourth), camera backlight compensation (Off, Some, Strongest), recording frame rate (30, 60 fps), monitor scale (100 %, 110 %, 120 %, 125 %, `MonitorScaleRow`). Chip labels are words, not raw values (Dark/Light, Tonal spot).
- `SettingChoice { compact: true }`: the current choice as a button with a chevron; the chips open under it (the six swipe actions of eight choices each).
- Font chips are drawn in their own font (`Chips` model entries may carry `font`).
- Labels wrap instead of being cut with an ellipsis.
- **Grid mode**: a row whose key grid mode replaces (`settings.py` `GRID_OVERRIDES`, plus `GRID_ROUND_OFF` unless `shell.gridRoundControls` is on, read through `bbkos-theme defaults`; `SettingsStore.gridValue(key)`) shows "Set by grid mode · 0 px" instead of its control.
- Dependent rows stay in place, dimmed, as `design.md` section 5 says (proposed hiding them; kept the existing rule).

**Reset where you are.** A row whose value differs from its default shows a small accent dot after its label; on hover the dot becomes "Default", and a second click within 4 s ("Reset to 12 px") resets that key. A card with any changed row shows "Reset these" at its title: a second click resets exactly those keys in one tool run. Cards without plain rows take part through `key` and `modified` on a child (the bar widget order, the per-app notification mutes). The Reset tab keeps only Revert and Reset everything; the list of 26 section buttons is gone. This needs two new tool calls: `bbkos-theme reset TARGET...` (sections and keys, one write and one apply) and `bbkos-theme defaults` (JSON: the defaults and the grid overrides), `theme.md`.

**Bug fixed on the way.** `SettingsStore.sections` was a fixed list of 9 sections while `settings.json` had 27: `reset("idle")` and the Reset page rows for 18 sections (idle, notifications, keyboard, mouse, cursor, night light, window behaviour, date and time, music, clipboard, lid, launcher, privacy, screen time, stage, capture, camera, calendar) were dropped with a WARN, and "Revert to when this window opened" skipped those sections. The list is now the sections of the file itself.

**Search for single settings.** `scripts/build-settings-index.py` writes `modules/settings/SearchIndex.js` (218 rows: label, hint, card title, place; labels built at run time, such as key binds and devices, are not in it; the Accessibility page is skipped as its rows have their own page) from `Pages.js` and the page files; `tests/theme/test_settings_pages.py` fails while it is stale. The sidebar lists settings named by the query first ("Settings", with "Page › Tab · Card" under each), then pages and tabs ("Pages"), then settings that match only through their hint ("Also mentioned"). Picking a setting opens its tab, scrolls the row into view and lights it up for 1.4 s (`SettingsStore.reveal`, `SettingsPage.tryReveal`, retried while the page lays out). DankMaterialShell does the same with a generated `settings_search_index.json`.

**Links.** Accessibility rows show their page under the label ("↗ Appearance › Style") and open it at that row (`SettingRow.link`, `"page/tab#Row label"`). The Bar › Layout widget list has a Settings button on each widget that has settings elsewhere (clock and music: Bar › Widgets; privacy dot: Privacy and wellbeing; brightness: Displays; volume: Sound; network, battery, notifications, updates, recording, workspaces).

**Idle timeline.** Power and sleep › When idle draws the four steps on one time line above their chips (square-root scale; steps at the same time share a dot; a line in the warning colour when the order is unusual, for example the screen switching off before it locks), and says when Keep awake is on that none of them happen now.


**Menu.** The bbkOS menu lists every page and every tab of a page with tabs ("Stage mode", "Settings · Windows"), built from `Pages.js`; the old page names stay findable through the keywords. Learned ranking for the old `settings:N` entries is not carried over.

Verified 2026-10-28 on screen (tiled window 1785x1166 on eDP-1, grid mode on, the owner's settings): every one of the 31 tabs opened through `settings page` with `settings where` agreeing and no QML warning in the journal; screenshots read for each; search "snap distance" and "folder icons" (opens the tab, scrolls, lights the row), "blur" (seven settings across Bar, Windows and Lock screen, then pages); a key reset through the store (`clock.seconds` set to true, then `reset clock.seconds` back to the default, which the old section list would have ignored); the Idle timeline with the owner's values (Lock and Screen off share a dot at 5 min); tests: `tests/theme` (CLI `reset` with keys and several targets, `defaults`, the index and the page list), `tests/keybinds` (updated for the new structure). Not verified: anything that needs the pointer (no pointer injection here): hover on a row and the two-click reset of a row or a card, a drag on a StepBar, the − / + hold repeat, a click on a tab, a compact choice, an Accessibility link or a widget's Settings button; light mode; a second monitor; the window at its minimum size; grid mode off.

## Design

- **One writer.** The app never writes `settings.json`. Every change runs `bbkos-theme set -- KEY VALUE` (or `reset [SECTION]`), which validates, clamps, applies live and only then writes the file. The app reads the result back through `ThemeStore.settings` (the watched file). So the window shows what is really applied, and an invalid value can never reach the file.
- **Window.** A `FloatingWindow` titled `bbkOS Settings` inside a `LazyLoader` gated by `SettingsStore.windowOpen`: it exists only while open, never twice. Colour `Theme.bg`; sidebar `Theme.surface` with the active page in `Theme.accent`; a `Loader` shows the page; the bottom line shows "Applying...", the tool's first error line in `Theme.crit`, or nothing. `Esc` closes it.
- **Pages** (sidebar order): Wallpaper and colours (`PageWallpaper`, below), Shell, Bar (`PageBar`: position, thickness, widget gap and padding, opacity, blur, widget background, pill radius, widget icons with "Icons only" and the icon-to-text gap; blur is disabled at 100% opacity and the radius with no pills; see `bar.md`), Windows, Terminal, Reset (`PageReset`, below). Ranges mirror `bbkos_theme/settings.py` `RANGES`.
  - `PageShell`: the **Grid mode** toggle (`shell.gridMode`, `grid-mode.md`) and "Round popups and controls in grid mode" (`shell.gridRoundControls`) at the top of "Shape", then `gap` 0-32, `radius` 0-24, `controlRadius` 0-16 (all step 2), `fontSize` 10-20, and `font` as chips. The font list is a curated candidate list (Adwaita Sans, GNOME's proportional UI font, added 2026-10-28; JetBrainsMono, FiraCode, Hack, CaskaydiaCove, Iosevka Nerd Font, Noto Sans Mono, DejaVu Sans Mono, Liberation Mono) filtered with `Qt.fontFamilies()` (exists in Qt 6.12: `QtObject::fontFamilies` in `libQt6Qml`; probed windowless, returned 530 families incl. `JetBrainsMono Nerd Font`), plus the current value if it is not in the list. Installed on this machine: JetBrainsMono Nerd Font, Noto Sans Mono, DejaVu Sans Mono, Liberation Mono.
  - `PageShell` also has one **Scale** row per enabled monitor (`MonitorScaleRow`): a slider over the valid scales (1, 1.1, 1.2, 1.25), value and -/+ stepper. A drag applies once, on release, through `Displays` -> `bbkos-display` (see `displays.md`), with the same 15 s "Keep these settings?" prompt as the display popup, shown on the page.
  - `PageWindows`: `windows.gapsIn` 0-20, `gapsOut` 0-40, `borderSize` 0-8 + `activeBorder` toggle (off: the focused border has the inactive colour), `rounding` 0-24, `activeOpacity` / `inactiveOpacity` 0.6-1.0 step 0.05, `shadowEnabled` + `shadowRange` 0-20, `blurEnabled` + `blurSize` 1-12 + `blurPasses` 1-4, `animations`, `resizeOnBorder` (drag a window border to resize; `general.resize_on_border`) and `borderGrabArea` 0-30 px (`general.extend_border_grab_area`, enabled only with it). Super + drag binds are on the Keybindings page, not here. The sub-controls of an off toggle (shadow range; blur size and passes) stay in place at opacity 0.4 with `enabled: false` (disables the whole row: slider, value, stepper), so the layout never jumps. A `Theme.dim` note says blur, shadow and animations cost GPU and battery and are not measured yet.
  - `PageTerminal`: `terminal.fontSize` 8-20, `padding` 0-24, `opacity` 0.6-1.0 step 0.05; the note says changes reach running kitty windows through a config reload.
  - `SettingsPage` now scrolls (`Flickable`, wheel/drag, 4 px indicator); an empty `note` hides the note line.

## Redesign (2026-10-21)

Owner request: more intuitive and modern, a toggle with more contrast, modern sliders everywhere, a wider window.

- **Window** (2026-10-28: tiled, filling the workspace, see "Hyprland rule"; before that 1120x720 floating via rule `size = "1120 720"`; the QML `implicitWidth` 1120, minimum 960x480; labels are no longer cut off). The earlier 900x640 / 780x400 figures elsewhere in this file are history.
- **Sidebar** grouped: Appearance (Wallpaper and colours, Shell, Bar, Windows, Terminal, Lock screen, Stage mode), Input (Keybindings, Touchpad), System (Reset, Power). Page index = position in `SettingsWindow.pages` (the `settings page N` hook is unchanged); each page has a `group`, the sidebar lists them grouped. Open page: accent-soft fill, accent icon, bold (the accent bar on the left edge was removed 2026-10-25). Every page has an icon.
- **Pages** have a large title with a one-line description, then `SettingsSection`s: a titled rounded card of rows with hairline dividers. Rows are `SettingRow` (label, optional dim `hint` under it, control on the right, 12 px padding, divider hidden on the first row of a card). `SettingSlider`, `SettingToggle`, `SettingChoice`, `SettingText` and `MonitorScaleRow` are built on it; the stepper is now `-  value  +` and the value is bold. A page that is not split into sections sets `card: true` (Keybindings, Lock screen) and gets one card. Regrouped: Shell (Shape, Text, Displays), Bar (Position and size, Background, Widget background, Widget icons, Widget order), Windows (Layout, Opacity, Effects, Resizing), Stage (switch, Rail, Cards, Previews), Touchpad (Pointer and scrolling, Tapping and clicking, Workspace swipe, Multi-finger gestures), Power (Helper, one card per profile; the old `Hint` lines became row hints), Reset (Reset a group, Revert and restore), Wallpaper (Wallpaper, Colours, Palette). New controls on the way: Bar page "Blur strength" (`shell.barBlurAmount`), Colours "Tint strength" (`shell.tint`), the palette strip shows the six new tint tokens.
- **Toggle** (`components/Toggle.qml`): on = accent track with a dark knob and an accent tick; off = dark track, 2 px light outline, light knob. The old one was an accent track with a light knob, almost the same colour for a pale accent (owner's `#b4fdff` and white).
- **Slider** (`components/Slider.qml`, removed 2026-10-29 when the audio and display popups moved to `StepBar`; was shared with them and the scale row): 6 px rounded track, accent fill, a light bead with a dark ring (readable on the fill and on the empty track whatever the accent is), halo on hover and drag. The signals and the value contract are unchanged.
- **Button and Chips**: raised `surfaceHigh` fill with a hairline edge, accent-soft on hover; the chosen chip is the accent with bold dark text.
- Not done (nice to have): keyboard navigation of the sidebar. (The search box was added on 2026-10-24, below.)

Verified 2026-10-21 by screenshots of all eleven pages at 1120x720 (and the audio, display and Wi-Fi popups for the new slider and toggle). Not verified: real mouse drags on the slider and clicks on toggles and chips (no pointer injection here), the minimum window size (960x480) rendered, other font sizes.

## Close button, scrolling sidebar, no scroll bars (2026-10-23)

A close button (x, 32 px, top right of the window, hover fill, press scale 0.97) closes the window as Esc does. The sidebar
is a `Flickable` (wheel, drag): in a window too short for all pages (the owner's was cut after "Reset") the rest is
reached by scrolling, the "Settings" title scrolling with the list. The pages' 4 px scroll indicator was removed at the
owner's request ("i hate scrollbar"), with its 16 px gutter (the minimum-width arithmetic in `SettingsWindow.qml` lost
that 16 px); pages still scroll by wheel and drag. Earlier notes above that mention the indicator are the history.
Checked on screen at 1120x720 and 1120x480: no scroll bar, close button shown, the sidebar content moves when scrolled
(set from code: no wheel tool here). Not checked: a click on the close button, a real wheel scroll.

## Idle and lock page (2026-10-24)

Fifteenth sidebar entry (`PageIdle`, index 14, new group Hardware; sidebar groups are now Appearance, Input, Hardware, Tools,
System): the awake-mode switch and four chips rows (dim, lock, screen off, suspend) for `idle.*`. Doc: `idle.md`. The Reset page has an
Idle and lock row.

## Notifications page (2026-10-24)

Sixteenth sidebar entry (`PageNotifications`, index 15, new group Desktop; the groups are now Appearance, Desktop, Input, Hardware,
Tools, System): do not disturb, the popup corner, time on screen, sender time, critical popups, popups at once, pictures, the
history size and a switch per app that has sent a notification (mute). Doc: `notifications.md` "Settings". The Reset page has a Notifications row.

## Keyboard and mouse page (2026-10-24)

Seventeenth sidebar entry (`PageKeyboardMouse`, index 16, group Input): keyboard layout, variant, Caps Lock remap, repeat rate
and delay, Num Lock; pointer speed, acceleration, natural scrolling, left-handed; cursor size and theme. Doc: `input.md`. The Reset
page has Keyboard, Mouse and Cursor rows.

## Night light page (2026-10-24)

Eighteenth sidebar entry (`PageNightLight`, index 17, group Hardware): mode (off, always on, schedule), warmth in kelvin, and the
evening and morning times of the schedule. Doc: `nightlight.md`. The Reset page has a Night light row.

## Sound and Startup apps pages (2026-10-24)

Nineteenth and twentieth sidebar entries: `PageSound` (index 18, group Hardware: default output and input, their volume and mute, and
a volume for each playing app, live PipeWire state through `Audio.qml`, `sound.md`) and `PageStartup` (index 19, group System: the
apps started at login, switch off or on, add and remove, through `bbkos-autostart`, `startup.md`). Neither writes `settings.json`,
so neither has a Reset row.

## Window behaviour page (2026-10-24)

Twenty-first sidebar entry (`PageBehavior`, index 20, group Desktop): how focus follows the mouse, whether apps may take focus,
switching back, the cursor (hide while typing, hide when still, follow focus) and snapping floating windows. The Windows page gained
an animation speed slider. Doc: `behavior.md`. The Reset page has a Window behaviour row.

## About and updates, Network pages (2026-10-24)

Twenty-second and twenty-third sidebar entries: `PageAbout` (index 21, group System: update count with Check now and Update, the last
update, and read-only facts about this computer through `bbkos-about`, `about.md`) and `PageNetwork` (index 22, new group Network:
Wi-Fi switch, saved connections with auto-connect and Forget, Tailscale status, the phone mirror switch, through `bbkos-network`,
`network.md`). Neither writes `settings.json`, so neither has a Reset row. The sidebar groups are now Appearance, Desktop, Input,
Hardware, Network, Tools, System.

## Date and time page (2026-10-24)

Twenty-fourth sidebar entry (`PageDateTime`, index 23, group System): the bar clock (24 hour, date, seconds) and the calendar keys that
had no page (week start, week numbers, moon). Doc: `calendar.md`. The Reset page has a Date and time row (the clock keys;
the calendar keeps its own). The Sound page also holds the **Music widget in the bar** section (`media.*`, `media.md`) and the Reset page has a Music widget row.

## Clipboard page (2026-10-24)

Twenty-fifth sidebar entry (`PageClipboard`, index 24, group Tools; since 2026-10-28 the Clipboard history card of Privacy and wellbeing, which also has **Keep images**, `clipboard.images`, default on): `clipboard.maxItems` (10 to 500 step 10, default 100) and a two-click
Clear now (`cliphist wipe`). `bbkos-theme` renders `clipboard.conf` (a new generated file) and `bbkos-clip-store` reads the number on every
copy, 100 without it; password-manager copies are still skipped and the history is still wiped at logout. The Reset page has a Clipboard row.
Verified: 4 tests (`test_clipboard_settings.py`: the render, the script with and without the file, a hostile file, secrets), the file
rewritten live for 50 and back to 100. Not verified: the page on screen, a real copy with the new limit (that would have replaced the
owner's clipboard), Clear now (it would have erased the history).

## Light and dark by the clock (2026-10-24)

The Wallpaper and colours page has three more rows under Mode: a switch "Switch by the time of day" and the two switch times (`colors.auto`,
`lightFrom`, `darkFrom`; theme.md has the behaviour). Verified live: a schedule that matched the current mode changed nothing, one that
did not switched the palette to light within seconds, and turning it off and the mode back to dark restored everything; 6 tests
(`test_schedule_math.py`: the time parsing and the day, the wrapping and the equal cases under node, the keys). Not verified: a real
crossing of a switch time (only the start-up and turn-on paths), after a suspend across a switch time, the rows on screen.

## Search, and the Accessibility page (2026-10-24)

The sidebar has a search box under the title. It filters the pages (a flat list while there is a query) by their label, group and
`keywords` (a string per page in `SettingsWindow.pages`; every word typed must appear); Enter opens the first hit, Esc clears the box
before it closes the window. It searches pages, not single settings: a new page or setting needs its words added to `keywords`. Test hook:
`qs ipc call settings search TEXT`. The **Accessibility** page (`PageAccessibility`, index 25, group Appearance) gathers existing keys
(reduce motion, window animations, contrast, interface and terminal text size, cursor size, key repeat delay and rate): nothing new is
stored, so a change there shows on the other pages. Verified on screen: "sleep" listed only Idle and lock, the Accessibility page with
the real values (contrast 1.00, interface text 11). Not verified: typing in the box with a real keyboard, Enter and Esc in it, the no-match
text, the box at the minimum window size.

## Lid and power button page (2026-10-24)

Twenty-seventh sidebar entry (`PageLidPower`, index 26, group Hardware): what closing the lid does on battery and on the charger, and what
holding the power button does. It needs a root helper installed once (`sudo ~/.local/share/bbkos/repo/scripts/install-logind-helper.sh`); until then the page
says so and the choices are saved but not applied. Doc: `lid-power.md`. The Reset page has a Lid and power button row.

## Launcher page (2026-10-24)

Twenty-eighth sidebar entry (`PageLauncher`, index 27, group Desktop): the web search engine (or none), the calculator, bbkOS commands and settings
pages in the results, how many results, whether the menu learns, and Forget. Doc: `menu.md` "Settings". The Reset page has a Launcher row.

## Privacy page (2026-10-24)

Twenty-ninth sidebar entry (`PagePrivacy`, index 28, group System): which of the microphone, camera and screen sharing light the bar's new
privacy indicator, and what is in use right now. Doc: `privacy.md`. The Reset page has a Privacy row. The Bar page's layout editor lists the
new widget as "Privacy indicator".

## Screen time page (2026-10-24)

Thirtieth sidebar entry (`PageScreenTime`, index 29, group System): a break reminder (never, 20, 30, 45, 60, 90 minutes) and the screen-on totals (this stretch,
since the computer started, since the charger was unplugged). Doc: `screentime.md`. The Reset page has a Screen time row.

## Capture page (2026-10-21)

Twelfth sidebar entry (`PageCapture`, index 11, group "Tools"; `qs ipc call settings page 11`): screenshots (save by default,
save folder, editor overlay or window), screen recording (what, sound, camera, camera size, mirror, quality, fps, folder) and the
keys. Keys and ranges mirror `settings.py` `capture.*`; see `capture.md`. The Reset page has a Capture row. The sidebar groups are
now Appearance, Input, Tools, System.

## Camera page (2026-10-21)

Thirteenth sidebar entry (`PageCamera`, index 12, group "Tools"; `qs ipc call settings page 12`): exposure (automatic or manual
with an exposure time), backlight compensation, brightness, gamma, contrast, white balance, saturation, sharpness, steady
frame rate and mains frequency. Keys and ranges mirror `settings.py` `camera.*`; see `camera.md`. The Reset page has a Camera row.

## Default apps page (2026-10-23)

Fourteenth sidebar entry (`PageApps`, index 13, group System; also "Default apps" in the bbkOS menu): the terminal, and
which app opens web links, folders, images, video, music, PDFs, text files and mail links. **Terminal** (added the same
day): not a MIME type but the first entry of `~/.config/xdg-terminals.list` (the proposed freedesktop default-terminal
spec, read by `uwsm app -T`); offered: entries in the `TerminalEmulator` category that are shown in menus, without foot's
server and client halves (here: foot, kitty); a choice puts that entry first and keeps the other lines. The "Terminal"
key action (the owner's Super+Enter, Super+Q by default) runs `uwsm app -T`, and the bbkOS menu starts terminal apps with
`uwsm app -T --`. Checked: with foot first, `uwsm app -T` opened a foot window; back to kitty after (kitty is the
owner's default, recorded in the file). The floating tool windows (`bbkos-tui`: updates, nmtui, bluetui; the health
check; uninstall) stay on kitty: they need its `--class` (Hyprland floats them by class) and `--hold`. One row of chips per kind; the chips are the
installed apps whose desktop entry lists the kind's first MIME type (`NoDisplay` entries count: imv and zathura ship
hidden from menus but open files; `Hidden=true` does not). A choice runs `bbkos-defaults set KIND ID`
(`bbkos_theme/defaultapps.py`), which writes every MIME type of that kind (a browser: `x-scheme-handler/https`, `http`,
`text/html`, `application/xhtml+xml`, `about`, `unknown`) into `~/.config/mimeapps.list` `[Default Applications]`,
keeping every other line and section, atomically; then the page re-reads `bbkos-defaults status`. This is the
freedesktop file `xdg-open`, GTK, Qt and Thunar read. Verified: the page on screen with the owner's current choices
(Zen, Thunar) and the candidates, `tests/theme/test_defaultapps.py` (candidates, writing inside the section, refusing an
app that cannot open the kind). Not verified: a change made from the page by a click (the owner's choices were not
changed), apps that read only their own settings (some browsers ask to be the default themselves).

## bbkOS page (2026-10-31)

Owner: what is particular to bbkOS ("what's distinct with this rice") is on one page, first in the sidebar in a group of its own, and the window opens on it when no place is asked for (it is the first entry of `Pages.js`). Settings were moved, not copied: Grid mode (`PageGrid`: grid mode and round popups and controls, from Appearance › Style), Rail and pinned apps (`PageRail`: pinned apps, side, thickness, hug, alignment, padding, background opacity, reserve space, from Windows › Stage mode) and Stage mode (`PageStage`, below). The search index, the menu entries and `qs ipc call settings page bbkos/rail` follow `Pages.js`. Nepali calendar, screen-time breaks and dictation stay on their pages.

## Stage mode page (2026-10-21)

Since 2026-10-31 the tab bbkOS › Stage mode (`bbkos/stage`); until then Windows › Stage mode, and before 2026-10-28 the eleventh sidebar entry (`PageStage`, `qs ipc call settings page 10`). Since 2026-10-31 the rail rows are on bbkOS › Rail and pinned apps; this page keeps: "Stage mode by default" (`stage.enabled`,
the mode every workspace starts in; since 2026-10-23 one workspace can differ until the next boot, see `stage.md`) and
every size and look of the rail (pinned apps, side on any of four edges, thickness, hug its contents and the position
along the edge, padding, background opacity (since 2026-10-31 "Set by the bar style": a row with `lockedBy`, shown like a
grid-locked row and skipped by "Reset these"), reserve space, show with one window, card length, gap, corner radius,
title, icon, order, animations, refresh interval). The rail controls are always active (a
workspace can be in stage mode while the default is off). Keys and ranges mirror `settings.py` `stage.*`.

## Hyprland rule (spec 8 item 5)

**Update 2026-10-28:** the owner wants the settings window as a full tile, so the rule is now `float = false` (the window fills the workspace, next to the stage-mode thumbnails when that is on). The text below is the original floating design.

Evidence: a bare `FloatingWindow { title: "bbkOS Settings" }` opened from the real module, read with `hyprctl clients -j`: `class` and `initialClass` `org.quickshell`, `title` and `initialTitle` `bbkOS Settings`, `xwayland` false, tiled (611x726) without a rule. The class is shared by every Quickshell window, so the rule matches both (Hyprland matches the whole string; see the `bbkos-tui` lesson in `panels.md`):

```lua
hl.window_rule({
    name  = "bbkos-settings",
    match = { class = "org\\.quickshell", title = "bbkOS Settings" },
    float = false,   -- 2026-10-28: tiled (was float = true, size = "1120 720", center = true)
})
hl.bind(mainMod .. " + comma", hl.dsp.exec_cmd("qs ipc call settings toggle"))
```

After one `hyprctl reload` (configerrors empty): the window is `floating: true`, `size: [900, 640]`, `at: [190, 95]` on the 1280x800 logical screen with a 30 px bar: centred in the work area ((1280-900)/2 = 190, 30 + (770-640)/2 = 95). `hyprctl binds -j` lists `key: comma`, `modmask: 64` (Super), dispatcher `__lua` (Lua binds do not show their command). `Super+,` was free.

## API used (read from the installed type files, Quickshell 0.3.2)

- `Quickshell/_Window/quickshell-window.qmltypes`: `FloatingWindow` (`FloatingWindowInterface`, prototype `WindowInterface`): `title`, `minimumSize`, and from `WindowInterface` `implicitWidth`, `implicitHeight`, `visible`, `color`, signal `closed()`. `maximumSize`, `minimized`, `maximized`, `fullscreen`, `parentWindow` exist and are not used.
- `Quickshell/Io/quickshell-io.qmltypes`: `Process` (`command`: string list, `running`, `stderr`: `DataStreamParser`, signals `exited(int exitCode, QProcess::ExitStatus exitStatus)`, `runningChanged`); `StdioCollector` (`text`, `streamFinished`); `IpcHandler`.
- Order verified with a windowless probe: `stderr` `streamFinished`, then `exited`, then `running` false. A binary that cannot start logs `WARN: Process failed to start` and gives `running` false with **no** `exited`; the store treats that as an error and moves on.

## SettingsStore contract (`services/SettingsStore.qml`, singleton)

| Member | Meaning |
|---|---|
| `readonly property var values` | `ThemeStore.settings` (the parsed `settings.json`; no second FileView) |
| `property string status` | `"idle"`, `"applying"` (anything pending, queued or running), or `"error: <first stderr line>"` |
| `property bool windowOpen` | The window exists while true |
| `property var snapshot` | Deep copy of `values` taken each time the window opens |
| `get(key): var` | Dotted lookup in `values` (`"windows.rounding"`); `undefined` if missing |
| `shown(key): var` | (Addition.) The value last requested for `key` while its run is pending, else `get(key)`, else (a key missing from an older `settings.json`) the built-in default: for `shell.*` the value the shell uses, for any other key `defaultOf(key)` once the defaults are loaded (since 2026-10-29; before, such a choice showed no chip selected). Controls use it so a slider does not jump back while the tool runs; on failure it falls back to the file's value |
| `set(key, value)` | Debounced 150 ms; latest value per key. Booleans to `true`/`false`, numbers via `String`, strings as-is. Runs `~/.local/bin/bbkos-theme set -- KEY VALUE` as an argument list (no shell). A set equal to the file's value with nothing in flight for that key is skipped |
| `reset(target)` | `bbkos-theme reset TARGET` (a section or, since 2026-10-28, one key; `""` = everything). Pending sets are queued first, so the order of requests is kept |
| `resetMany(targets)` | (2026-10-28.) One `bbkos-theme reset T1 T2 ...` run for several sections and keys (a card's "Reset these") |
| `sections` | (2026-10-28.) The sections of `settings.json` itself (was a fixed list of 9 of the 27) |
| `defaults`, `gridOverrides`, `gridRoundOff`, `defaultOf(key)` | (2026-10-28.) Read once from `bbkos-theme defaults` when the window first opens |
| `modified(key)`, `gridValue(key)`, `gridLocked(key)` | (2026-10-28.) The value shown differs from the default; grid mode replaces the key now |
| `openPage(place)`, `startPage`, `place`, `reveal` | (2026-10-28.) Open the window at `page/tab`; the place shown (test hook `settings where`); the row label the open page scrolls to and lights up once |
| `revertToOpen()` | Sets every snapshot key whose value differs from the current one, through the same queue, then `revertWallpaper()` (see Wallpaper snapshot). `wallpaper.path` is not `set()`: it is restored from the snapshot copy |
| `snapshotWallpaper`, `snapshotState` | (Task 13.) Path of the wallpaper copy taken at window open (`""` = no wallpaper at open, `undefined` = unavailable); state `none` (window closed) / `pending` / `ready` / `failed` / `disabled` (`XDG_RUNTIME_DIR` unusable and a wallpaper was set) |
| `toggleWindow()` | Flip `windowOpen` |
| `setWallpaper(path)` | (Task 12.) Queues `bbkos-theme wallpaper set -- PATH` (argument list, no shell) through the same queue: one process at a time, in request order after pending sets. A newer wallpaper request replaces an older **queued** one (never the running one). Same `applying` / `error: <first stderr line>` handling. Anything but a non-empty absolute string without NUL is ignored with a log line |
| `clearWallpaper()` | Queues `bbkos-theme wallpaper clear` the same way |
| `wallpaperBusy` | True while a wallpaper job is queued or running (the page shows "Applying...") |
| `imageCount` | Test hook: images listed by the open wallpaper page, `-1` when that page does not exist |
| `queued`, `runs` | Test hooks: requests not finished; tool runs since the shell loaded |

Rules: exactly one `bbkos-theme` process at a time; requests run in order; a newer set of a key replaces an older **queued** set of the same key (removed and appended at the end, so a later reset is never undone). A non-zero exit sets `error: <first non-blank stderr line>`, which stays until the next successful run while the queue carries on. Odd input (null, undefined, NaN, objects, keys not shaped `section.key`, unknown sections) is ignored with one `WARN qml: SettingsStore...` line. The tool path is absolute (`$HOME/.local/bin`), so a different `PATH` in the service does not matter.

**Watchdog** (final fix pass): a run still going after `watchdogMs` (60 s; a `Timer` started in `pump()`, stopped in `finish()`) is stopped with `proc.running = false` (SIGTERM), SIGKILL (`proc.signal(9)`) 5 s later if it is still running; when the process has gone, the job ends as `error: bbkos-theme timed out` (one WARN line) and the queue carries on. Killing `bbkos-theme` does not stop a matugen it started in its own scope (that has its own 20 s timeout), and a killed run can leave a stray `.*.tmp` next to a target (as with any SIGTERM). Tested 2026-10-18 through the `watchdogMs`/`probe` hooks (no setting touched): with the interval at 1500 ms, `probe 10` was stopped after about 1.5 s (`sleep` gone well before the 5 s kill step, so SIGTERM ended it), status `error: bbkos-theme timed out`, `queued` 0; with `probe 10` followed by `probe 0` the second ran and cleared the error (status `idle`); interval restored to 60000. Not tested: the SIGKILL step (needs a process that ignores SIGTERM; `sleep` does not) and a real stalled `bbkos-theme`.

## Controls (`components/`)

- `SettingRow { label, hint, key, link }`: the frame of every row (label column 260 px, control right). With `key`: the modified dot and its two-click reset, "Set by grid mode" in place of the control. `link`: a place shown under the label that opens there. `flash`: lit by a search hit. `describe(value)` words a value for "Reset to ..." and "Set by grid mode · ...".
- `SettingSlider { label, key, from, to, step, suffix, percent, factor, decimals }`: a `StepBar` (above). Dragging and the ends snap to `step` within `from`-`to`; only a changed value is sent.
- `SettingToggle { label, key }`: label and `Toggle`; disabled when the value is not a boolean.
- `SettingChoice { label, key, model, compact }`: chips that wrap onto more lines. `model` holds values or `{value, label, font}`; values compare as text. `compact`: a button that opens the chips.
- `SettingsSection { title, description }`: the titled card; "Reset these" while a row in it is changed.
- `Tabs { model, current }`: the tab row under a page title (accent text and a 2 px accent line under the current tab).
- None keeps a copy of the value: each reads `SettingsStore.shown(key)` and calls `SettingsStore.set`. Tokens only (`Theme.accent/surface/dim/fg/bg`, `Theme.controlRadius`, `Theme.radius`, `Theme.hair`); even sizes. (Until 2026-10-28 `SettingSlider` was a `Slider` with a separate `- value +` stepper.)

## Keybindings page

Seventh sidebar entry (`PageKeybindings`, index 6). Full reference: `keybindings.md`.

- **What it lists.** The binds from `bbkos-keybinds status`, grouped by catalogue group (then Custom, System, Other), each row with its label (or the raw command), the combo as chips, an enabled toggle, Restore (shipped binds only), Edit and Remove. Read-only (locked) rows show a lock, with the toggle disabled and Edit, Remove and Restore hidden. A search field filters by label, command and key.
- **How edits are saved.** The page never writes a file. Add, Edit, Remove, the toggle, Restore and "Restore all defaults" (behind a confirm step) each call `KeybindStore`, which queues one `bbkos-keybinds` run at a time (`--json -` on stdin, no shell), then refreshes. The editor stays open until the run succeeds; the CLI's first error line is shown in it and in the status line. A failed reload is rolled back by the tool. The editor's duplicate check is local; if the combo is taken it offers Replace (`--replace`) or Cancel, and the CLI has the last word.
- **Recording.** "Record" captures the next key press; Escape cancels. A combo Hyprland already binds cannot be recorded (it never reaches the window).
- **Test hook.** `qs ipc call keybinds status` returns `{"status": "idle|applying|error: ...", "binds": N}`; `qs ipc call settings page keyboard/shortcuts` opens the page (Keyboard › Shortcuts since 2026-10-28).

## Bar widget order

Bar › Layout lists every widget under Left, Centre and Right (each with a Settings button when it has settings elsewhere). Drag a widget by its grip (⋮⋮) onto another widget to put it at that spot, or onto a section heading to put it at the end of that section. Left, Centre and Right buttons on each row do the same without dragging. The bar builds each section from `bar.layout` (see `theme.md`). The card's "Reset these" puts the default order back.

## Touchpad page

Mouse and touchpad › Touchpad and › Gestures since 2026-10-28 (`PageTouchpad`, `PageGestures`; was the eighth sidebar entry, index 7). Natural scroll, scroll speed and method, flips, tap-to-click, tap-and-drag, drag lock, tap button mapping, click behaviour, disable while typing, workspace swipe tuning, and a swipe action for 3 fingers (up, down) and 4 fingers (up, down, left, right). Keys and ranges are in `theme.md` section 3. Changes apply straight away through `bbkos-theme apply` (full Hyprland reload). Three-finger left and right are not offered: they are the built-in workspace swipe.

## Lock screen page (`lock`; index 9 until 2026-10-28)

Spec `docs/specs/2026-10-19-lock-screen-editor-design.md`, plan `docs/plans/2026-10-19-lock-screen-editor.md`. A scaled mock of the lock screen (`LockPreview.qml`: the blurred wallpaper and each element at its offset and size) above the controls (`PageLock.qml`). Click an element on the mock, or pick it in the chip row, to edit it; drag it to move it; drag the square at its bottom-right corner to resize it (avatar diameter, text font size, field width and height). A drag shows at once and is saved once on release. The side panel has Show, Align (Left, Center, Right), X, Y and Size per element (the password field is always shown: no Show toggle), then Field, Background (blur passes, blur size, brightness) and Text (font, colour, welcome text with `$USER`, 12 or 24-hour time, three date formats). "Test real lock (5 s)" runs `bbkos-lock-test`: it locks for real, photographs the lock screen with `grim`, unlocks by itself and shows the photo under the button. Each test counts as one failed login for PAM, so it refuses while any failed login is on record (see `desktop-tools.md`).

Keys: the `lock` section of `settings.json` (`docs/modules/theme.md` has the ranges): `<element>Show/X/Y/Size` for `avatar`, `welcome`, `date`, `time`, `battery`; `fieldX/Y/Width/Height/Radius/Opacity`; `blurPasses`, `blurSize`, `brightness`; `font`, `textColor`, `welcomeText`, `timeFormat`, `dateFormat`. Positions are pixels from the screen centre, y up (hyprlock's), in the panel's own pixels (1920x1200 at scale 1.0667), which the preview now uses too. **Align** Left or Right puts the element's edge `lock.edgeMargin` % (default 10, 0-40; the Layout slider) of the screen width in from that edge; X is then unused (hyprlock takes a percentage or pixels for a position, not both, so the X row is disabled and dragging only moves Y). Center places the middle at X. Reset: each card's "Reset these" (the Reset page's "Lock screen" row until 2026-10-28).

**Avatar picture (2026-10-28).** The avatar editor (the page now opens with the avatar selected) has a Picture row: a thumbnail of the current picture, "Choose picture..." (zenity's file dialog, which comes up through the GTK portal, floating 1000x640, in ~/Pictures with an Images filter) and "Use the default" while a picture of your own is set. The choice runs `bbkos-theme avatar set -- PATH` through the store's queue (`SettingsStore.setAvatar`, `clearAvatar`); the preview and the thumbnail follow `lock.avatar`. Reference: DankMaterialShell's profile image (a file browser, then AccountsService for the whole account; here only the lock screen, no root and no D-Bus). Verified: the row before and after a real `avatar set` of a copy of the shipped picture (hint, buttons and preview changed; `hyprlock.conf` pointed at the copy), the dialog opened with the same command and closed, `avatar clear` back to the shipped picture with the copy folder emptied; 5 tests. Not verified: a click on the buttons, a real lock with a picture of another shape (hyprlock crops it round; the preview crops the same way).

The mock is an approximation of hyprlock (font metrics, blur strength). Positions are pixels, so a monitor of another size shifts the layout.

## IPC target `settings`

| Call | Effect |
|---|---|
| `toggle` | Open or close the window |
| `status` | JSON `{open, status, queued, runs, wallpaperBusy, images, watchdogMs}` (`images`: files the wallpaper page lists, `-1` when it is not shown) |
| `refreshFolder` | Test hook: the open wallpaper page re-reads its image folder (the same `refreshFolder()` the Open folder button calls) |
| `wallpaper PATH` | Test hook: `SettingsStore.setWallpaper` (absolute path) |
| `clearWallpaper` | Test hook: `SettingsStore.clearWallpaper` |
| `set KEY VALUE` | Test hook: `true`/`false` to bool, `-?digits[.digits]` to number, else text; then `SettingsStore.set` |
| `reset TARGET` | `SettingsStore.reset`: a section or one key (`""` = everything) |
| `revert` | `SettingsStore.revertToOpen` |
| `snapshotInfo` | Test hook (Task 13): JSON `{wallpaper, state}` of the wallpaper snapshot (`wallpaper` is `""` when there is none or it failed) |
| `snapDirFor ENV` | Test hook (Task 13): the pure path guard, returns the snapshot directory for an `XDG_RUNTIME_DIR` value or `""` |
| `page PLACE` | Open the window at `page` or `page/tab` (`Pages.js` ids, for example `bbkos/stage`); an unknown place logs a WARN. Until 2026-10-28 `page N` took a sidebar index |
| `where` | Test hook (2026-10-28): the place shown, `""` while closed |
| `search TEXT` | Test hook: types into the sidebar search box |
| `pick` | Test hook (2026-10-28): Enter in the search box (opens the first hit) |
| `watchdogMs MS` | Test hook (final fix pass): watchdog interval for this session (minimum 100; `0` or less restores 60000); returns the value in use. `status` also shows `watchdogMs` |
| `probe SECONDS` | Test hook (final fix pass): queues `sleep SECONDS` (whole seconds 0-120, else ignored with a WARN) as a stand-in run through the same queue, `Process` and watchdog; touches no setting. The tool path is never changed. A finished `probe 0` clears a left-over error status |

## Verified live (2026-10-18)

- `toggle` opens (status `open: true`, one client `org.quickshell` / `bbkOS Settings`, floating 900x640 at 190,95), `toggle` again closes (0 clients). Same after a cold `systemctl --user restart quickshell.service`.
- `set shell.radius 14`: one tool run, `theme status`, `settings.json` and the tool agree on 14. Two quick `set shell.radius 20`: `runs` went up by one, final 20.
- `set shell.radius abc`: status `error: shell.radius: expected an integer, got 'abc'` (the tool's own first line; the file kept the old value); the next valid set returned status `idle`.
- `reset shell`, `reset colors` through the hook: defaults back; `reset nonsense` ignored with a log line.
- Ten sets on three shell keys in quick bursts: final values the latest of each; a `/proc` sampler (5 ms) saw at most **one** `bbkos-theme` process (6 runs for 10 sets).
- `revert` after two changes: exactly two runs, values back to the snapshot.
- The window follows the theme live: with `shell.radius 24` and `colors.contrast 0.8` the card corners and colours changed in the open window; the error line rendered in `Theme.crit`.
- Opened with `colors.json` moved away, and with it replaced by garbage: the window shows with the built-in colours (`accent #7aa2f7`); restored with `bbkos-theme apply`.
- Window content was checked with a temporary in-process `grabToImage` hook (removed again): the screen was locked during the session, so `grim` showed only the lock screen.
- Queue logic (coalescing, order with reset, error then recovery, odd input, a missing binary) was also run against a fake `bbkos-theme` in a windowless probe with a scratch `HOME`.

## Task 11 pages: verified live (2026-10-18)

- Every key of the three pages through `settings set`: in-range value reached the system (Windows keys: `hyprctl getoption`; shell: `theme status`; terminal: `kitty-theme.conf`), out-of-range numbers were clamped by the tool (e.g. `windows.rounding 99` to 24, `terminal.opacity 0.1` to 0.6), invalid booleans were rejected with the file unchanged; all restored. Each page was opened with a clean journal (at the time the page index was forced temporarily in the source and reverted; the `page N` hook came later in Task 13); the window opened with `colors.json` missing and garbage.
- Screen was locked, so `grim` showed the lock screen: **the pages have never been seen rendered.**
- Dimming of sub-controls: originally by reading the code only. Final fix pass: a windowless probe (`qs -p` on a scratch copy of the config, no window) measured the effective opacity of a disabled `SettingSlider` row's parts: before 0.40 (label), 0.16 (slider), 0.40 (value), 0.16, 0.16 (stepper buttons); after 0.40 for all five. The look itself is still unseen.

## Wallpaper and colours page (Task 12)

`modules/settings/PageWallpaper.qml` on the `SettingsPage` frame (tokens only, even sizes, `Theme.hair` borders):

- **Header**: current wallpaper (`Image` of `ThemeStore.wallpaperPath`, 320x200 decode, `cache: false`, reloaded when a `FileView` watcher sees the file change, because every `wallpaper set` rewrites the same `current.<ext>`; a `Theme.bg` box with "No wallpaper" when empty or failed), "Clear wallpaper" (disabled when none) and "Open folder".
- **Thumbnail grid** of `~/Pictures/Wallpapers`: `FolderListModel` (`nameFilters` png/jpg/jpeg/webp/bmp/gif, `caseSensitive: false` so `.PNG` matches, no dirs, no hidden, sorted by name) feeding a `GridView` in a fixed-height box (two rows, scrolls inside itself). A `GridView` creates only the delegates in or next to its view, so off-screen images are never decoded (a plain `Flow` in the page `Flickable` would create all of them). Each thumbnail: `Image` `asynchronous`, `sourceSize` 320x200, `PreserveAspectCrop`, file name caption (`ElideMiddle`), `Theme.hair` border turning `Theme.accent` on hover. Click: `SettingsStore.setWallpaper(filePath)`. URLs come from `components/FileUrl.js` (`toUrl`: each path segment percent-encoded; `Wallpaper.qml` imports the same file and its behaviour is unchanged). Missing or empty folder: the hint "Put images in ~/Pictures/Wallpapers, then pick one here." takes the grid's place.
- **Open folder**: a `Process` runs `mkdir -p -- DIR`; only when it exits 0 does `refreshFolder()` run (a `FolderListModel` does not notice a folder that did not exist when `folder` was set, so the page points `folder` at `file:///` and back) and then `Quickshell.execDetached(["thunar", DIR])` run (two detached calls would race: thunar could start before the folder exists). A failing mkdir logs a warning.
- **Colour controls**: `colors.mode` (dark, light) and `colors.scheme` (nine, from `RANGES`) as `SettingChoice`; `colors.accentStrength` ("Accent colour strength", a percent slider next to Contrast, 2026-10-29), `colors.sourceIndex` 0-3 step 1 (matugen accepts 0-3, not the 0-4 of its --help) ("Dominant colour (0 = most)") and `colors.contrast` -1..1 step 0.1 as `SettingSlider`.
- **Palette**: read-only 24 px swatches: the eleven `ThemeStore.colors` keys, then the 16 `ansi` colours from `ThemeStore.colorsDoc.ansi` (not part of `colors`); non-`#rrggbb` data shows `Theme.surface`. Hovering a swatch shows its name and hex value under the palette ("ansi red" for the 16 terminal colours).
- **Status line** above the grid: the tool's error in `Theme.crit`, "Applying..." while a wallpaper job runs (the window's bottom line shows the same status).

APIs read from the installed type files: `Qt/labs/folderlistmodel/plugins.qmltypes` (`FolderListModel`: `folder` url, `nameFilters`, `sortField` + enum `Name`, `showDirs`, `showFiles`, `showHidden`, `caseSensitive`, `count`; the role names `fileName` / `filePath` are not in the type file: confirmed by running, delegates with `required property string fileName/filePath` got values); `QtQuick/plugins.qmltypes` (`GridView` `cellWidth`/`cellHeight`, `Image` `sourceSize`, `fillMode` enum `PreserveAspectCrop`, `asynchronous`, `cache`); `Quickshell/quickshell-core.qmltypes` (`execDetached(string[] command)`).

Verified live (2026-10-18, screen locked): 38 files in the folder: `images` 38 (including `UPPER.PNG` and a non-image `bad.png`, which shows a broken thumbnail and one `Error decoding` log line). `settings wallpaper` with ordinary, spaced, unicode-and-parenthesis, leading-dash and upper-case names, a jpg and a 4000x2500 png: `bbkos-theme status`, `wallpaper status` (image Ready, decoded 1920x1200) and `theme status` (accent changed) agreed each time; two PNGs in a row both applied. A non-image `x.png` gave `error: Format error decoding Png: Invalid PNG signature.`, the previous wallpaper stayed, the next valid request cleared it; relative and empty paths were ignored with a log line. Five requests in 0.1 s: 2 tool runs, last one wins, never more than one `bbkos-theme` process (`/proc` sampler, 5 ms). Every colour key through the hook reached `theme status` (mode, nine schemes, sourceIndex 0-3 changed the accent with a four-colour image, contrast -1 and 1). `colors.sourceIndex 4` failed in matugen on ANY image (`4 is not in 0..4`; clap's half-open range, not image dependent): the range is now 0-3 (settings.py RANGES, slider, spec). `clearWallpaper` returned to the plain colour and emptied `~/.local/share/bbkos/wallpaper/`. PSS of the quickshell process (sum of `Pss:`, 28 images of 4000x2500 plus 10 small ones): window closed 213.6 MB, open 226.5 MB (+12.9 MB), closed again 215.9 MB; the same window open on an empty folder: 222.8 MB (+8.4 MB), so the grid with 38 files costs about 4 MB over the empty page, not the tens of MB a full decode of one 4000x2500 image would (40 MB each). Missing folder: the page opens with `images` 0 (hint branch by code reading; the screen was locked, so no picture exists).

Fix round 1 (2026-10-18): `colors.sourceIndex` range is 0-3 (matugen accepts 0-3 whatever its --help says). Open folder with a missing folder, then add images: the refresh by hook is tested (folder absent, window open: `images` 0; folder and two PNGs created from the shell: still 0, the model did not notice; `settings refreshFolder`: `images` 2); the real click, thunar launch and the mkdir handler are not tested.

Hot reload note: Suspected trigger (unconfirmed): hot reload after adding a new QML type file, or after a multi-file edit, or an edit while the settings window was open; the shell then answers "Not ready to accept queries yet" until `systemctl --user restart quickshell.service`. Cause not found, not reproducible on demand. Evidence: `task-12-report.md` (an edit while the settings window was open left the instance answering "Not ready to accept queries yet" for about 80 s and later edits did not reload; a multi-file edit wedged it again in fix round 1; one restart fixed each). `task-9-report.md` (hot reload stopped working after a `systemctl --user restart`: edits produced no `Reloading configuration`; cause not investigated).

## Reset page and revert (Task 13)

`PageReset.qml` on the `SettingsPage` frame: a row per section (Shell, Windows, Terminal, Colours, Wallpaper) with a `Reset` button and a dim consequence line (`SettingsStore.reset(section)`; Wallpaper clears the wallpaper: the copy becomes `previous.<ext>`, one step undo, see `theme.md` section 7), a `Revert` button (`revertToOpen()`), and `Reset everything`. The last arms on the first click (turns into a `Theme.crit` "Click again to reset everything"), runs `reset("")` on a second click, and a 4 s `Timer` disarms it, the same pattern as `PowerPanel`. All buttons are disabled while `SettingsStore.status === "applying"`.

**Wallpaper snapshot.** On window open the store copies the wallpaper copy (`ThemeStore.wallpaperPath`) to `$XDG_RUNTIME_DIR/bbkos-settings/open.<ext>` (`mkdir -p -m 700`, then `cp -f`; helper `Process` argument lists, one at a time, never a shell; nothing is copied when no wallpaper is set). Window close, and the next open before re-snapshotting, run `rm -f` on `open.{png,jpg,jpeg,webp,bmp,gif}` (the extensions `wallpaper.py` accepts). A failed mkdir/cp logs one WARN, sets `snapshotState` `failed` and `snapshotWallpaper` `undefined`: wallpaper revert is disabled for that window (logged when used), the other reverts work. `revertToOpen()` then: no wallpaper at open and one now -> `clearWallpaper()`; wallpaper at open and none now, or another extension -> `setWallpaper(snapshot)`; same extension -> `cmp -s current snapshot` and `setWallpaper(snapshot)` on a difference or read error. `cmp` was chosen over size+mtime because the copy's mtime is the copy time and equal sizes are common for same-resolution images; the files are at most 40 MB (tool cap) and the run is off the UI thread. Set/clear go through the normal queue (one `bbkos-theme` at a time). A revert that arrives while the snapshot is still `pending` skips the wallpaper (logged).

**Path guard.** `snapDirFor(env)` returns `""` unless `XDG_RUNTIME_DIR` is an absolute path (not `/`, no NUL, newline or `..` segment). With `""` no rm/mkdir/cp is ever queued (begin and end are no-ops); with a wallpaper set the state is `disabled` and one WARN is logged, with none set the snapshot is `ready` (nothing to copy). The other reverts always work. Tested exhaustively on the pure function through the `snapDirFor` hook (`/run/user/1000`, trailing slash, empty, `runtime`, `/`, `//`, `./x`, `/a/../b`, `/..`); the unset case (not passable over IPC) is the same `typeof` check; "no Process started" with the real variable unset was not run (it would break IPC), only read from the code.

**Revert while a wallpaper job runs.** `ThemeStore.wallpaperPath` is stale until a running job's write is read back, so when `wallpaperBusy` is true `revertWallpaper()` skips the comparison and queues `setWallpaper(snapshot)` / `clearWallpaper()` (a queued wallpaper job is replaced, a running one finishes first). Tested: A at open, `wallpaper b` then an immediate `revert` -> copy equals A; none at open, same -> no wallpaper.

**Test fix.** `tests/theme/test_settings.py`: the old "tracked file equals defaults" test could not hold once the tracked `settings.json` became the owner's live config (Stow link). Replaced by: the tracked file validates with no warnings; a deliberately invalid copy in a temp dir is flagged; `dumps(DEFAULTS)` round-trips through `validate` clean.

**Verified live (2026-10-18).** Revert after 4 and after 13 changes across sections: every key back to the snapshot (compared key by key), 13 queued jobs never ran 2 `bbkos-theme` at once (max 1, sampled). Wallpaper: none at open + set -> revert clears it; a.png at open + b.png -> revert makes the copy `cmp`-equal to a.png; no-op revert starts no run. `reset colors|shell|windows|terminal|wallpaper|""` changed only that section's keys to the defaults. Snapshot file appears on open, is gone after close, re-created on the next open. Unwritable runtime dir (a file in its place) and a read-only dir (cp fails): window opens, `state: failed`, one WARN, other reverts work, wallpaper stays. The Reset page loads without journal errors (page hook). The owner's file and `bbkos-theme status` were identical after the run.

## Not tested (click-only or not allowed)

- Task 13: every click on the Reset page (section Reset buttons, Revert, the second-click arming of Reset everything, the 4 s disarm, disabled look while applying) and its layout (`grim` showed the lock screen). The `reset terminal` check is weak: the owner's terminal values already equal the defaults, so a no-op reset passes too. The arm/disarm logic is only checked by reading it against `PowerPanel`. `snapshotState` `pending` followed by an early revert is by code reading only.

- Task 12 page: clicking a thumbnail, hover highlight, scrolling the grid and the page (wheel, drag), the Open folder button and its mkdir-then-refresh handler (thunar was not launched; the command list `["mkdir","-p","--",DIR]` then `["thunar", DIR]` is asserted by code reading only), the Clear wallpaper button, chips and sliders (the hook was used instead), the layout as drawn (`grim` showed the lock screen), the hint's look, and the header image reload after a second PNG (same path; the wallpaper module's reload was seen through `wallpaper status`, the page's own `FileView` reload was not observed).


- Task 11 pages: scrolling (wheel, drag) and the indicator, sidebar navigation, chips (font), toggles, slider drag, the dimmed rows' look and non-interactivity, the visual layout of all three pages.

- Closing by the compositor (`Super+C`): `hyprctl dispatch` is not allowed in tests. `closed()` is the `WindowInterface` signal in the type file; the window sets `windowOpen` false on `closed` and on `visible` becoming false. Unverified until the owner presses `Super+C` on it and then `Super+,` opens it again.
- `Super+,` itself (the bind is registered; the key press was not made), the bar gear click, `Esc`.
- Dragging a slider, the stepper buttons, clicking a chip or a toggle, sidebar clicks, hover colours. Page switching was done through the `page N` test hook, never by clicking the sidebar.
- Resizing the window below 900x640 (minimum 780x400 since the final fix pass).

## Thunar action (Task 14)

**2026-10-21:** Thunar showed two "Set as wallpaper" entries. The other one is Thunar's own `thunar-wallpaper-plugin.so`, which writes
xfconf for xfdesktop and does nothing here. It is removed (`sudo rm /usr/lib/thunarx-3/thunar-wallpaper-plugin.so`) and kept away by
`NoExtract = usr/lib/thunarx-3/thunar-wallpaper-plugin.so` in `/etc/pacman.conf`. Thunar also follows the theme now: see `theme.md`, "GTK apps".

Right-click an image in Thunar: "Set as wallpaper" runs `bbkos-theme wallpaper set -- FILE` and recolours the system. Stow package `dotfiles/thunar` links `~/.config/Thunar/uca.xml` into the repo (`--no-folding`: `~/.config/Thunar` stays a real directory, `accels.scm` is Thunar's and untouched).

- **Merge, not overwrite.** The file Thunar had created (stock action "Open Terminal Here", id `1792283569536788-1`) is kept byte-for-byte and first; the new action (id `1792283569536789-2`) follows. Backup of the original: `~/.config/Thunar/uca.xml.pre-bbkos` (keep it).
- **Command**: `sh -c 'out=$(bbkos-theme wallpaper set -- "$1" 2>&1) || notify-send -u critical "Set as wallpaper failed" "$out"' sh %f` (XML-escaped in the file). Thunar shows nothing on failure itself, so the failure line of `bbkos-theme` goes to `notify-send`. `%f` is the last token and sits outside any quotes so that Thunar's own quoting applies; the file arrives as `$1` and `--` guards a leading dash.
- **Filter**: patterns for png/jpg/jpeg/webp/bmp/gif in both cases plus `<image-files/>` only (no directories/other types). Icon `image-x-generic` (exists in Adwaita; `preferences-desktop-wallpaper` is only in AdwaitaLegacy here).
- **Schema evidence**: no Thunar doc for `uca.xml` is installed (`/usr/share/doc/thunar` has only `README.gtkrc`; the man page does not mention it). The element names come from `strings /usr/lib/thunarx-3/thunar-uca.so` (the plugin that reads and writes the file): its writer template has `icon name submenu unique-id command description range patterns`, its parser knows `startup-notify directories audio-files image-files other-files text-files video-files`, and it links `g_shell_quote` / `xfce_g_string_append_quoted` (substituted paths are shell-quoted). The `%f` = first selected file (full path), `%F` = all selected files, and "Thunar parses the command with g_shell_parse_argv and spawns it without a shell" are from memory of Thunar's source / the Xfce docs, not from anything installed. The existing file's own `exo-open ... %f` unquoted use agrees.
- **Symlink caveat**: Thunar's editor dialog (Edit > Configure custom actions) saves `uca.xml` by writing a new file, which replaces the symlink with a regular file (the repo copy then stops being the source). To re-link: move the regular file away (`mv ~/.config/Thunar/uca.xml ~/.config/Thunar/uca.xml.thunar-edit`), run `stow -R --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ thunar`, and merge any edits into the repo file. (Replace-on-save is expected behaviour; not observed here, Thunar was not launched.)
- **Tested** (`tests/theme/test_thunar_uca.py`, temp HOME and `BBKOS_*` dirs, fake matugen/hyprctl/notify-send, no Hyprland signature): XML well-formed; stock action byte-identical; unique ids; exact child tags of the new action; the command, with `%f` replaced by `shlex.quote(path)`, both via `sh -c` and via argv split without a shell, succeeds for `My Pic (1).png`, `日本語.jpg`, `-x.png` (also relative), `it's.png`, `a b'c"d.png`, a real ffmpeg PNG, puts the copy in the share dir and sends no notification; a bad image / missing file produces exactly one `notify-send -u critical "Set as wallpaper failed" <one line>`. Note `BBKOS_MATUGEN` does not exist in the code: matugen is found through `PATH`, so the test puts the fake first.
- **Dependencies and environment**: `notify-send` (package `libnotify`) must be installed; the command relies on `bbkos-theme` and `notify-send` being on the PATH of Thunar's session (`~/.local/bin` is in the session PATH since the `uwsm/env` change: verified by the final reviewer, `/proc/<Hyprland pid>/environ` and Quickshell's environment both contain `/home/user/.local/bin`; Thunar's own environment was not read). A missing `bbkos-theme` still notifies, because the shell reports its own error through `$out`.
- **File mode**: the repo copy `dotfiles/thunar/.config/Thunar/uca.xml` is mode 0644 (the original Thunar file was 0600); it holds no secrets.
- **Open risk: AND versus OR of the filters.** The action lists patterns for six extensions (png, jpg, jpeg, webp, bmp, gif, each in lower and upper case) and also `<image-files/>`. The official Thunar docs (docs.xfce.org/xfce/thunar/custom-actions, fetched 2026-10-18) do not say whether patterns and file-type boxes combine as AND or OR, nor whether pattern matching is case-sensitive (their example lists `*.jpg;*.JPG;*.jpeg;*.JPEG`). Consequences: under **OR** the entry shows for EVERY image type (svg, tiff, avif ...) and such files fail with a notification; under **AND** an image with an unlisted extension (for example `.jpe`) or, if matching is case-sensitive, a mixed-case extension such as `.Png` is **hidden**. Our patterns are a subset of the image types, so the six listed extensions are covered either way. Unknown which of the two is true; untested.
- **Untested / unknown (click-only)**: that Thunar shows the entry for images and hides it for other files and directories; that a click runs it; Thunar's real quoting function (emulated with `shlex.quote`; the official docs do say Thunar quotes substituted paths itself and that field codes must not be quoted, which is why `%f` is unquoted and last); whether a running Thunar re-reads `uca.xml` live (unknown: assume a restart of Thunar is needed).

## Known limitations

Found in review and deliberately not fixed (a replaced or cleared wallpaper copy is kept as `previous.<ext>`, but that is ONE step only: two wallpaper changes in a row lose the original copy; the checklist preamble tells you to copy your settings and wallpaper first):

- **Found by the last fix-pass review, not fixed (all Minor):** (1) when a generated-file replace fails during a wallpaper change, a `.settings.json.<random>.tmp` file stays next to the real settings file (the repo directory; `.gitignore` hides it, harmless; the old code cleaned it up); (2) a late failure (wallpaper replace or `settings.json` replace) with a new image of the SAME extension can leave `bbkos-theme status` saying `fresh: yes` over the new image's colours; `bbkos-theme apply` repairs it; (3) two narrow edges in `retire_current`/`install`: if deleting an older `previous.*` with a different extension fails, `install` raises after the old copy was moved (no `current.*`, the copy survives as `previous.<ext>`), and a rolled-back install has already deleted that older `previous.*`.

- **Clear wallpaper and Reset > Wallpaper** delete the stored copy with one click (no arming); Revert restores it only while the window stays open. Since the final fix pass the deleted (or replaced) copy is moved to `~/.local/share/bbkos/wallpaper/previous.<ext>` first: one step back with `bbkos-theme wallpaper set -- ~/.local/share/bbkos/wallpaper/previous.jpg` (the extension that is there).

- **Status wording**: `status` shows `error: ...` even while the queue is not empty (the error stays until the next successful run). An error line appears twice on the Wallpaper page (page status line and the window's bottom line). The text carries a doubled `error: error:` internally (the store prefixes a tool line that already starts with `error:`); both display sites strip one prefix, so the owner sees one.
- **Flicker**: possibly one frame after a run, when the pending intent drops before the file watcher re-reads (`finish()` in `SettingsStore.qml`). `refreshFolder()` briefly sets `imageCount` to 0.
- **IPC `set` hook** normalises `"007"` to `7` (test hook only).
- **Odd font-size literals** (`fontSize-1`, `+2`, `+4`) in the settings pages: sizes derived from `Theme.fontSize` are not always even.
- **Wallpaper page**: nested scrolling of the thumbnail grid (the wheel over the grid does not pass to the page at its ends; untested); the "No images" hint can flash while the model loads; no placeholder behind a thumbnail while it decodes; tall portrait images decode at about 100x200 and are cropped, so they may look soft (by code reading, never seen rendered); a symlink to a directory is hidden (`showDirs: false`); an unreadable file shows a broken thumbnail.
- **Revert**: `revertToOpen` does not `set` `wallpaper.path` (the tool rejects it); the wallpaper is restored from the snapshot copy instead. `wallpaperBusy` tracks only jobs keyed `wallpaper`: a queued or running `reset wallpaper` (or `reset ""`) followed by an immediate revert still compares against the stale path (narrow window). If `setWallpaper(snapshot)` is queued behind a long job and the window closes, `endSnapshot` can delete the snapshot first (the tool then fails and the error shows in the status). `snapDirFor` accepts `/a/./b` (harmless). A revert arriving while the snapshot is `pending` skips the wallpaper.
- **Hot reload**: can wedge (suspected trigger, unconfirmed: see failure-modes.md and the note under the Wallpaper page); restart `quickshell.service`.
- **Fixed in the final fix pass** (found in the Task 11 review):
  1. Double dimming of disabled rows: the Windows page no longer sets a row `opacity`; `SettingSlider` dims its label and value to 0.4 when disabled, `Slider` and `Button` dim themselves, so every part ends at 0.4 (measured by the windowless probe; the look is unseen).
  2. Scroll indicator radius is `width / 2` (`SettingsPage.qml`).
  3. Minimum window size raised from 640x400 to 780x400: sidebar 240 + page margins 48 + indicator gutter 12 + card margins 32 + the slider row's fixed parts 352 (label 200, value 48, two 28 px buttons, four 12 px gaps) + 96 for the slider. Chosen over letting the 200 px label shrink, which would elide labels. The Hyprland rule still opens the window at 900x640. By arithmetic from the code; not seen rendered.
  4. `NetworkRow.qml` reveal toggle uses `Theme.controlRadius`.

## Owner verification checklist (nothing below could be tested by the agents)

The agents never saw these pages rendered or clicked (the screen was locked during their tests; `grim` showed the lock screen). Each step lists what you should see. If a step fails, note the step number. Order matters for group F.

**Before you start: save a restore point.** Steps 7, 8, 20 and 21 replace or delete your current wallpaper copy, and steps 9-21 change mode, scheme, sizes and fonts. `settings.json.bak` is NOT a restore point (every successful change rewrites it), and `previous.<ext>` keeps only one wallpaper step. So first run:

```sh
mkdir -p ~/bbkos-before-checklist && cp -L ~/.config/bbkos/settings.json ~/.local/share/bbkos/wallpaper/current.* ~/bbkos-before-checklist/
```

(If no wallpaper is set, `cp` complains about `current.*`; the settings file is still copied.) To restore afterwards, in this order:

```sh
bbkos-theme wallpaper set -- ~/bbkos-before-checklist/current.jpg   # FIRST (use the extension you saved): the saved settings point at the share-dir copy
cp ~/bbkos-before-checklist/settings.json ~/.config/bbkos/settings.json   # cp writes through the Stow link
bbkos-theme apply
```

**A. Open and close**
1. Press `Super+,`. Expect: the "bbkOS Settings" window, floating and centred, about 900x640, five sidebar entries (Wallpaper and colours, Shell, Windows, Terminal, Reset).
2. Press `Super+,` again (or the gear again). Expect: it closes.
3. Click the gear icon at the right end of the bar. Expect: the window opens; a second click closes it.
4. Open it and press `Esc`. Expect: it closes.
5. Open it, press `Super+C` (compositor close), then press `Super+,`. Expect: it opens again (not stuck).

**B. Wallpaper and colours page**
6. Click "Open folder". Expect: Thunar opens on `~/Pictures/Wallpapers` (the folder exists on this machine now; if it did not, it would be created first). Copy two or three images in: expect the grid fills after the click (the code re-reads the folder after mkdir); images added later without a click may need a page switch and back.
7. (Replaces your current wallpaper copy; the old one becomes `previous.<ext>`.) Click a thumbnail. Expect: the header preview and the desktop change within about a second, the colours of bar, borders and the window follow; "Applying..." shows briefly.
8. (Deletes your current wallpaper copy with one click; it becomes `previous.<ext>`.) Click "Clear wallpaper". Expect: plain background colour, header shows "No wallpaper", colours fall back to the blue `#7aa2f7`-based palette; the button is disabled when none is set.
9. Switch dark/light. Expect: the whole shell recolours. Switch back.
10. Click each of the nine schemes. Expect: the colours change each time (monochrome is grey; some schemes look alike on some images).
11. Move "Dominant colour" 0, 1, 2, 3. Expect: with a multi-coloured image the accent changes; with a plain image nothing changes.
12. Move the contrast slider to -1 and +1. Expect: text and borders become fainter / stronger; return to 0.
13. Look at the swatch strip: 11 colour swatches then 16 terminal colours, no grey holes.

**C. Shell page**
14. Drag each slider (bar height, gap, radius, control radius, font size). Expect: the bar and popups change live while you drag; values step by 2 where stated. Use the `-`/`+` buttons too.
15. Click each font chip. Expect: the shell font changes; only installed fonts are offered (JetBrainsMono Nerd Font, Noto Sans Mono, DejaVu Sans Mono, Liberation Mono at the last check).

**D. Windows page**
16. Scroll to the bottom with the wheel and by dragging. Expect: the page scrolls (there is no scroll bar since 2026-10-23), nothing is cut off.
17. Turn shadow off, then blur off. Expect: the sub-controls (shadow range; blur size and passes) dim and stop reacting but keep their place. Turn them on again.
18. Move each slider (gaps, border, rounding, opacities, shadow range, blur size, passes) and toggle animations. Expect: open windows change live.

**E. Terminal page**
19. Move font size, padding and opacity with a kitty window open. Expect: the terminal changes (colour reload is verified; opacity, font and padding reload on a running kitty is UNTESTED, so a restart of the terminal may be needed: note which).

**F. Reset page (WARNING: resets your choices; do this LAST or skip it)**
20. (Reset > Wallpaper deletes your current wallpaper copy; it becomes `previous.<ext>`.) Click a section's Reset (try Terminal first). Expect: only that section returns to defaults.
21. (Deletes your current wallpaper copy; it becomes `previous.<ext>`.) Click "Reset everything" once. Expect: the button turns red and reads "Click again to reset everything"; wait 4 seconds: it disarms. Click twice within 4 seconds: everything (including the wallpaper) returns to defaults.
22. Change two or three settings, click Revert. Expect: back to how they were when the window opened, including the wallpaper if you changed it.

**G. Thunar**
23. Right-click an image (png, jpg) in Thunar. Expect: "Set as wallpaper" in the menu; clicking it changes the wallpaper and colours.
24. Right-click a text file and a folder. Expect: no such entry.
25. Right-click images with unusual extensions (`.svg`, `.jpe`, `.Png`, `.tiff`) and note whether the entry shows: this settles the AND/OR question. An svg that shows the entry should produce a notification when run.
26. Right-click a corrupt "image" (for example a renamed text file ending in `.png`) and run the action. Expect: a critical notification "Set as wallpaper failed" with one line of reason; the old wallpaper stays.
27. Does a running Thunar show the entry without a restart (it was installed while Thunar may have been closed)?

**H. Look**
28. Judge legibility of dim text (inactive workspaces, secondary labels) on your wallpaper's palette, in dark and light.
29. Disabled rows in the Windows page (turn blur off): label, slider, value and buttons should all look equally faint (fixed double dimming; measured in a probe, never seen rendered). Turn blur back on.
30. Drag the window narrower than 900 px. Expect: it stops at 780 px wide and the sliders keep a usable width (minimum raised from 640; by arithmetic, never seen rendered); note anything that overlaps or gets cut off.
31. Set `shell.radius` high (24) and low (0): popups (Wi-Fi, Bluetooth, power, audio), notification cards and the launcher follow; note any corner that does not.

**I. Next reboot or login**
32. After logging in: Hyprland border colours, kitty colours and the bar already show the generated theme (not the old blue-grey), and `journalctl --user -u quickshell.service -b` shows no errors from ThemeStore or Wallpaper; `bbkos-check` ends with "all checks passed" (the unpushed-commits note is expected until you push).

**J. Battery**
33. Blur, shadow and animations are now ON by default also on battery (the old battery profile is gone), and the cost is unmeasured. During the deferred real-use battery test, compare idle power with all three off (`bbkos-theme set windows.blurEnabled false`, `windows.shadowEnabled false`, `windows.animations false`) and on, using `bbkos-power-sample`.

## Power page

Ninth sidebar entry (`PagePower`, index 8). Per profile (Battery saver, Balanced, Performance): CPU energy preference, turbo (System default / On / Off) and a package power cap (Off, 12, 16, 20, 24 W), each with a Safe or Moderate tag and the measured effect. "Applied now" shows what the kernel holds. Above the profiles, Battery charging (2026-10-29): `power.chargeMode` as System default / Fast / Standard / Limit to ~80 %, and "Charging now" read from `charge_types`. A banner appears when the root helper is not installed. Applied by `services/PowerTuning.qml` through the helper `power/bbkos-power-apply`. Full reference: `power-tuning.md`.
