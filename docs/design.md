# bbkOS design system

The rules for how anything in bbkOS looks, behaves and is built. Read it before adding a feature, a widget, a panel, a setting or a command, and keep to it, so that a thing written by the owner, Claude or any other agent looks and acts like the rest. Where this file and the code disagree, the code is the fact: fix the code or fix this file in the same change.

Companion docs: `principles.md` (how changes are made), `modules/theme.md` (the theme engine and every setting's range), `modules/settings-app.md` (the settings window), `modules/bar.md`, `modules/panels.md`, `modules/failure-modes.md`.

## 1. Principles

1. **One source of truth for the look.** Every colour, size, radius and font comes from `Theme` (`dotfiles/quickshell/.config/quickshell/Theme.qml`), which is bound to the generated theme written by `bbkos-theme`. No literal colours, no literal fonts, no private copies of a token in a module.
2. **Everything configurable goes through the settings table.** A look or behaviour the owner may want to change is a key in `bbkos_theme/settings.py` (`DEFAULTS` + `RANGES`), shown on a settings page, and changed with `bbkos-theme set`. Never hand-edit generated files.
3. **The wallpaper drives the colour.** Colours are derived from the wallpaper (matugen) and leaned toward by the `shell.tint` setting. A feature must look right for any palette, light or dark, and for any `shell.barPosition`.
3a. **Grid mode is a second look, not a second theme.** `shell.gridMode` (`modules/grid-mode.md`) makes the renderers hand over radii, gaps and shadows as 0, so use the tokens (`Theme.radius`, `Theme.controlRadius`, `Theme.barItemGap`, `Theme.cardEdge`) and never a literal radius or gap, or the new thing stays rounded in grid mode; where a literal is unavoidable (a knob, a bar), write `Theme.gridSquare ? 0 : N` (`Theme.gridSquare` = grid mode without `shell.gridRoundControls`, so popups and controls may stay round; use `Theme.gridMode` only for things that are always square: the bar, windows, stage cards).
4. **Cheap when idle.** Event-driven (D-Bus, inotify, Wayland events, IPC) over timers. Windows, scanners and processes exist only while shown (`LazyLoader`, `Process.running` bound to visibility). Continuous animation, blur and polling need a written reason (`principles.md`, resource impact).
5. **Fail closed, and say so.** Bad input falls back to a default with a warning; a missing helper shows "not installed", not a crash; a failure produces one readable line, never a silent no-op.
6. **Calm and compact.** Few colours at a time, hairlines instead of heavy borders, text at one size, motion only where it explains a state change.
7. **Prove it on screen.** A visual change is checked with a `grim` screenshot for every bar position (top, bottom, left, right) and mode (dark, light, pills off/grouped/individual) before it is called done.

## 2. Colour

Tokens, in `Theme.qml`. Use the token that names the *role*, not the one that looks right today.

| Token | Role |
|---|---|
| `bg` | window and bar base; text on an accent fill; the shell's deepest colour |
| `surface` | base of raised areas |
| `fg` / `dim` | primary text / secondary text, hints, placeholders |
| `accent` | the wallpaper's primary tone: selection, fills, focus, active state |
| `accent2`, `accent3` | two more hues (the accent turned -40 / +40 degrees), for variety between widgets |
| `accentSoft`, `accent2Soft`, `accent3Soft` | deep shade of each: hover and pressed backgrounds, pills |
| `warn` / `crit` | caution / error or destructive. Meaning only, never decoration |
| `popupBg` | opaque background of popups, cards, dialogs, the OSD and pickers |
| `inset` | sunken shade inside a popup: tracks, selected rows, inputs, off-switch track, dividers |
| `control` | raised shade inside a popup: buttons, chips, hover rows |
| `surfaceHigh` | a raised surface outside a popup |
| `pillBg` | background behind bar widgets in pill mode |
| `cardEdge` | hairline edge of every floating card (popup, picker, notification, OSD): `fg` at 8 % |
| `shadow` | tinted shadow under floating cards (`CardShadow`), strength from `shell.popupShadow` |
| `barBg` | the bar itself (opacity follows `shell.barOpacity`) |

Layering inside a popup: `popupBg` is the floor; `inset` goes down from it, `control` goes up from it. Do not stack a third level; do not use `surface` inside a popup.

Rules:
- Text on the bar uses `Txt.fgColor` / `Txt.dimColor` (they flip to stay readable on a bright wallpaper behind a translucent bar), never `Theme.fg` / `Theme.dim`. Tint a widget with `Txt.tone(Theme.accentN)`; the tint switches itself off when the bar flipped its text colour.
- Text on an accent fill is `Theme.bg`.
- Translucent edges are `Qt.rgba(Theme.fg.r, Theme.fg.g, Theme.fg.b, a)`: 0.08 card edge, 0.10 row divider, 0.16-0.20 control edge, 0.4 hovered edge, 0.55 off-switch outline.
- The theme engine lifts every text colour to 4.5:1 and every control part and focus ring to 3:1 on **every surface it is drawn on** (WCAG 2.2; table in `modules/theme.md` section 4a, `bbkos-theme contrast` measures it). A new colour role is added in `a11y.py` / `render.py` with the surfaces it sits on, not in a module; a module never picks a colour that is not a token. `Theme.qml`'s derived surfaces and `a11y.surfaces` are the same arithmetic.
- State is never colour alone: a selected chip is also bold, an enabled switch also shows a tick.

## 3. Typography and icons

- One family: `Theme.font` (default JetBrainsMono Nerd Font). Never set `font.family` to a literal.
- Base size `Theme.fontSize` (13). Secondary text, hints and buttons are `fontSize - 1`; a section title is `fontSize + 1` bold; the search field of a picker is `fontSize + 2`. Nothing else.
- Start from `Txt` (`components/Txt.qml`) for all text. A raw `Text` is only for the rare place `Txt`'s bar colours must not apply (it then sets `font.family: Theme.font` itself).
- Icons are Nerd Font glyphs in text, not image files. Bar widgets with several looks keep their glyph sets in `components/BarIcons.js`, keyed by the setting's value; the first entry of each set is its default, and `none` is offered except where hiding the widget would strand the user (the settings gear).
- Long text elides (`Text.ElideRight`); hints wrap (`Text.WordWrap`).

## 4. Shape, size and spacing

- Corner radii: `Theme.radius` (12) for popups, cards, dialogs; `Theme.controlRadius` (6) for rows, buttons, chips, inputs; `Theme.pillRadius` for bar pills. Never a literal radius, except a fully round control (`height / 2`).
- Hairlines: `Theme.hair` (one physical pixel). A logical 1 px blurs at fractional scale.
- **Even logical sizes.** The panel runs at 1.5x, where odd logical sizes land between physical pixels. Heights, widths and margins are even (round up: `Math.ceil(x / 2) * 2`).
- Control sizes: button 30 high, padded 12 px each side; chip 30 high, 24 px padding, even width; toggle 46x26; step bar 30 high with 30 px − and + ends (every number: settings and popups, the popup slider is gone since 2026-10-29); tabs 36 high with a 2 px accent line; settings row 12 px above and below its content with a hairline between rows; card inner margin 20; space between a row's label and control 16; between controls in a row 8.
- Window sizes seen by the owner: settings window tiled, filling the workspace (was 1120x720 floating until 2026-10-28), terminal UIs 760x480, picker panel 520 wide at 20 % of the screen height.
- Everything that sits near a screen edge clears the bar: use `Theme.barEdge` and `Theme.barInset` (0 when the bar is hidden), never a fixed top margin.

## 5. Components

Use these; add a new one to `components/` only when none fits, and add it here.

| Component | Use |
|---|---|
| `Txt` | all text |
| `Button { text; tint; onClicked }` | text button: `control` fill, accentSoft on hover and press, hairline edge |
| `Toggle { checked; onToggled }` | on/off switch; never changes `checked` itself |
| `StepBar { value; from; to; step; text; onMoved }` | a number in the settings window: − and + at the ends, a bar filled to the value (soft accent, 2 px accent edge) with the value and its unit in it; press or drag sets, − / + step and repeat while held |
| `Tabs { model; current; onPicked }` | the tabs under a settings page title: they choose a place, not a value, so they look unlike Chips |
| `Chips { model; current; onChosen }` | one value out of a short list (segmented row that wraps) |
| `Picker` | full-screen search-and-pick overlay (clipboard, emoji style; the bbkOS menu, `modules/menu.md`, has its own window in the same look) |
| `CardShadow {}` | first child of a floating card: its tinted shadow; the card's window needs `Theme.shadowPad` room (`modules/motion.md`) |
| `PopupHeader { title; status; statusColor }` | the title line of a bar popup, in the section-title style (bold, one size up); `status` dim text and children (a `Toggle`, a mute button) at the right |
| `PopupSection { title; first }` | one part of a bar popup: the settings hairline above (unless `first`), an optional section title, children 8 apart. The popup card is the card: no `SettingsSection` inside a popup |
| `SettingsSection { title }` | titled rounded card of settings rows; "Reset these" at the title while a row in it differs from its default |
| `SettingRow { label; hint; key; link }` | the frame of one setting: label and dim hint left, control right; with `key`, a dot while changed (on hover a two-click "Default") and "Set by grid mode" when grid mode replaces it; `link` opens the page that owns the setting |
| `SettingToggle / SettingSlider / SettingChoice / SettingText { key }` | a setting bound to a `settings.py` key. Which one: on/off is a toggle, 2-6 named values (or a short uneven set such as the four display scales) are chips, a continuous number is a slider (a StepBar, with its unit: `suffix`, `percent`). `SettingChoice { compact: true }` for a long list on one of many rows |
| `KeyCapture`, `ActionPicker` | key chord capture and action choice (keybindings) |
| `BadgeDot` | small dot on a bar widget's icon ("something waiting", `bar.iconsOnly`) |
| `BarItem`, `BarHit`, `BarSection` | bar placement; a bar widget needs no styling of its own (`modules/bar.md`) |

State and interaction rules shared by all of them:
- **The model owns the state.** A control shows what it is given and emits a signal; it keeps no copy of the value. Setting controls read `SettingsStore.shown(key)` and write with `SettingsStore.set`.
- Hover: `accentSoft` background and a brighter edge. Pointer: `Qt.PointingHandCursor` on every clickable thing. Disabled: `opacity: 0.4` and no mouse handling. A row that depends on another setting is disabled (dimmed), not hidden, and its hint says what it needs.
- Destructive or hard-to-reverse actions (log out, reboot, power off, clear history, reset) need a second click within 4 s (`disarm` timer); the button changes its text to say so. The first click never does the thing.
- Selected state: accent fill, `Theme.bg` bold text.

## 6. Motion

The full rules, the reference (Emil Kowalski) and what moves where are in `modules/motion.md`. In short:
- Use the tokens: `Theme.easeOut` (default), `easeInOut` (moving across the screen), `easeDrawer` (large surfaces) with `Easing.BezierSpline`, and `Theme.durFast` (120, state changes), `durEnter` (200), `durExit` (140, exit is quicker than enter), `durLarge` (300). No literal curve or duration in a module.
- Decide by frequency: something opened from the keyboard many times a day (the pickers) has no animation; popups and cards animate in and out.
- Enter from 96 % scale with a fade, never from nothing, out of the point nearest what opened it; buttons and chips shrink to 97 % while pressed. Animate opacity and transforms, use a `Behavior` so a change can reverse mid-way.
- `Theme.reduceMotion` (`shell.reduceMotion`): keep fades, drop scale and slides.
- Notification cards and the OSD are short-lived: the OSD is gone about 1.5 s after the last change, a card after 6 s unless the sender gives a timeout (critical cards stay).
- No looping animation, no animation that runs while nothing changed. Anything that must appear instantly (the screenshot selection layer, pickers) is excluded from layer animations by a Hyprland layer rule.
- Window and workspace animations belong to Hyprland (generated from the same curves, `windows.animations` switches them off); do not duplicate them in QML.

## 7. Surfaces

- **Bar** (`modules/bar`): per screen, three sections (start, centre, end), position top/bottom/left/right, optional translucency, blur, pills (off, grouped, individual) and hide/show. Widgets stay narrow so they work in a vertical bar: icon only, or icon and value on two lines. A widget with nothing to show some of the time sets `active` on its `BarItem`.
- **Popups** (`modules/panels`): one popup per bar widget, opened at the widget that was clicked (centred on it along the bar, clear of the bar, kept on screen; the widget passes `hit.center()` to `PanelState.toggle`), hosted by `Panels.qml` with one transparent full-screen overlay per screen so a click anywhere or Esc closes it. The window and anything costly in it (a Wi-Fi scanner, Bluetooth discovery, a pairing agent) exist only while open. `qs ipc call panel status` shows what is on. Inside, the settings look (2026-10-29): `PopupHeader`, `PopupSection` parts with the settings hairline, `SettingRow` without `key` for a label with a toggle or button, chip rows labelled above in the row-label style, `StepBar` for every number, content margin 20 like a settings card.
- **Notifications** (`modules/notifications`): the shell is the notification daemon. At most 5 live cards; history of the newest 100 entries with a read state; plain text only, no markup from apps.
- **OSD** (`modules/osd`): volume and brightness, on the focused monitor, about 1.5 s.
- **Settings window** (`modules/settings`): sidebar of 16 pages in four groups (`Pages.js`), a fixed header with the page title and its tabs, each tab a `SettingsPage` of `SettingsSection` cards, at most 960 px wide and centred. A new setting goes on the page and tab where someone would look for it (`modules/settings-app.md`, "Reorganisation"), then `python3 scripts/build-settings-index.py` so the search finds it. Window background `bg`, cards `popupBg`.
- **Lock screen** (`hyprlock`): rendered from the `lock.*` settings; it must always be able to fall back to the static config.
- **Terminal UIs** (`bbkos-tui`): for rare advanced tasks (nmtui, bluetui, updates), in a floating kitty window that is focused instead of duplicated. The graphical surface covers the common case.
- **Notifications from scripts**: `notify-send -a bbkos` (low urgency for information, critical only when work can be lost). One short sentence that says what happened and what to do.

## 8. Text and tone

Sentence case, no full stops on labels, short hints in the dim colour under the label that say what the setting does or what it needs ("Needs an opacity below 100%"). Errors name the thing and the next step ("helper not installed: run scripts/install-power-helper.sh with sudo"). Units are shown ("30 W", "5 s"). No jargon the owner has not used.

## 9. Adding a feature: the checklist

**A setting**
1. Add the key to `DEFAULTS` and `RANGES` in `bbkos_theme/settings.py` (range, step, enum values). The table validates, clamps and drives `bbkos-theme set`.
2. Render it where it takes effect (`render.py`, a service) and add a unit test next to the existing ones in `tests/theme`.
3. Add a row on a settings page with the matching `Setting*` control; copy `from`/`to`/`step` from `RANGES` and give a number its unit. Then run `python3 scripts/build-settings-index.py` (the search index; `tests/theme` fails until you do).
4. Update `modules/theme.md` and the module doc, and add a changelog entry.

**A bar widget, popup or settings page**: follow `modules/bar.md` ("Layout and adding a widget") and `modules/panels.md`. Use `BarHit` for clicks (give it an `id` and pass `hit.center()` when it opens a popup), `fgColor` / `dimColor` for text, lazy-load heavy content, add a test hook (`IpcHandler`) that prints the widget's state.

**A command (`bbkos-*`)**
- Lives in `dotfiles/bin/.local/bin/`, thin; logic in `bbkos_theme/` with unit tests. `--help` text, exit codes (0 ok, 1 failed, 2 usage), one line of output per fact.
- Every external call has a timeout. Output goes through a notification only when the user is not looking at a terminal.
- Test hooks (`BBKOS_DRY_RUN`, path overrides) are honoured only where they cannot redirect a privileged write.

**A privileged action**: a self-contained root-owned helper in `power/` or `touchpad/`, an installer in `scripts/` that runs `visudo -cf` before installing a sudoers rule allowing exactly that file with no arguments, and a `bbkos-check` line that compares the installed copy with the repo. It never imports code from the home directory and treats the settings file as untrusted input.

**A background service**: a user unit with `Restart=on-failure` and a non-zero exit on any unexpected end (a clean exit is not restarted), `RestartSec` long enough that a missing device cannot make it spin, and comments on their own lines (systemd does not allow a trailing comment after a value). Say in the unit what happens when it is down.

**State on disk**: under `~/.local/state/bbkos/` (flags, generated files) or `$XDG_STATE_HOME/quickshell/` (shell state), written atomically (temp file in the same directory, fsync, `os.replace`), validated on read, bounded in size, and rebuildable. Nothing in `/tmp`. Never store secrets; truncate free text.

**Docs**: a module doc in `docs/modules/`, a `docs/changelog.md` entry (what was verified, what was not), and `python3 scripts/build-skill-index.py` when a doc is added.

## 10. Rules that came from real bugs

- **No QML property named `on<Capital>`.** QML reads it as a signal handler and the binding never runs; and the matching `onOnBatteryChanged` handler of a property that does not exist is silently dead (found twice on 2026-10-21 in `ScreenTime.qml` and `BatteryAlerts.qml`). When renaming a property, grep for `on<Name>Changed`.
- **A watcher must not exit 0 when its source disappears.** `Restart=on-failure` leaves a cleanly exited service stopped for good (`bbkos-camera watch`, fixed 2026-10-21).
- **An empty answer is not a valid list.** A cleaner that deletes "everything not installed" must refuse to run when the installed list is empty (`bbkos-clean`, fixed 2026-10-21).
- **One-shot installers must not undo later decisions.** `scripts/task*.sh` are marked idempotent: they must not overwrite a value the owner changed afterwards (`task04-grub.sh` and `GRUB_TOP_LEVEL`, fixed 2026-10-21).
- **Bound everything an outside program can make large** (notification text, clipboard history, recordings, logs, wallpapers).
- **The live system is the working tree.** `~/.config/quickshell`, `~/.local/bin` and the Hyprland config are symlinks into `~/.local/share/bbkos/repo`, and Quickshell reloads on file change: a half-finished edit is live at once. Make QML edits complete and consistent, run `bbkos-qml-audit`, and restart the service to check the log.
- **Hardware names are assumptions.** `eDP-1`, `LID0`, `platform::kbd_backlight`, `BAT*`, `wlp0s20f3`, `intel_pstate` and `intel-rapl-mmio:0` are this laptop's. A new use keeps the name in one place with a fallback that does nothing, and a missing device is "skipped", not an error.
- **Root helpers are installed copies.** Editing the repo file changes nothing until the installer is run again; `bbkos-check` fails when they differ.
- **A test that runs a real tool must not reach the live session.** A temp HOME does not isolate D-Bus: `gsettings` from a test switched the live GTK theme to one inside a deleted temp dir (2026-10-23). Live-session writers check that HOME is the real home; test environments set `GSETTINGS_BACKEND=memory`.
- **Check the log after a restart**, not just that the unit is active: `journalctl --user -u quickshell` for `ERROR` and `WARN scene`.

## 11. Nice to have (not done)

- **A redesign of the whole UI and its components (considered 2026-10-23, left for later by the owner).** Not a component
  library: the QML ones (Qt Quick Controls styles, Kirigami, FluentUI-QML) bring their own theming and would fight
  `Theme.qml`, the wallpaper-derived colours and the generated GTK theme (Thunar). The plan if it is taken up: borrow a
  design system's rules and keep our own components. **Material 3** for the structure of the tokens (tonal roles,
  surface levels, state layers for hover and press, a shape scale), **Radix/shadcn** for restraint (few colours,
  hairline borders, quiet focus rings), **libadwaita** for spacing and density (already followed on the GTK side). Read
  first, as the reference-first rule asks, the Quickshell shells that already did this (end-4's dots-hyprland, Caelestia,
  Noctalia, DankMaterialShell: named from memory, not read yet). Order: audit every panel with screenshots, restructure
  `Theme.qml` into roles, rebuild the shared components one panel at a time checked at every bar position and in light
  and dark. Open question for the owner: what bothers them in the
  current look.
