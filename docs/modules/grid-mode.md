# Grid mode

One switch (`shell.gridMode`, Appearance › Style, "Grid mode"; the Shell page until 2026-10-28) that turns the whole desktop into flat, touching cells separated by hairline borders: no gaps, no rounded corners, no shadows. Since 2026-10-29 the corners of popups, buttons and controls can stay round (`shell.gridRoundControls`, "Round popups and controls in grid mode", off by default); the bar, windows and stage previews are always square, and the stage previews touch (`stage.cardGap` 0). The owner's own gap, radius and shadow values are not changed; they come back when the mode is switched off. Design source: the owner's own keyboard (omakey), whose keys are flat tiles with a thin dark line between them. Added 2026-10-26.

## How it works

Two layers, so nothing has to be kept in step by hand:

1. **The renderer overrides the values** (`bbkos_theme/settings.py`: `GRID_OVERRIDES`, `effective()`; used by `apply.build`). While `shell.gridMode` is on, every generated file (`colors.json`, `hypr-theme.lua`, `hyprlock.conf`, the GTK colours) is rendered from a copy of the settings with these replaced; `settings.json` itself is never touched. Because the shell reads its radii, gaps and shadow from `colors.json`, every `Theme.barRadius`, `Theme.barFloat`, `Theme.barItemGap`, `Theme.gap` and `Theme.shadowStrength` is 0 without a line of QML, and so are `Theme.radius`, `Theme.controlRadius` and `Theme.pillRadius` unless `shell.gridRoundControls` is on.

   | Setting | Value in grid mode |
   |---|---|
   | `shell.radius`, `controlRadius`, `pillRadius` | 0, unless `shell.gridRoundControls` is on (`GRID_ROUND_OFF`; the saved values then apply) |
   | `shell.barRadius` | 0 |
   | `stage.cardGap`, `stage.cardRadius` | 0 (`Stage.qml` also reads `Theme.gridMode`, since the stage settings are not in `colors.json`) |
   | `shell.gap`, `barFloat`, `barItemGap` | 0 |
   | `shell.barHug` | false |
   | `shell.barPills` | individual (every widget is a cell) |
   | `shell.popupShadow` | 0 |
   | `windows.gapsIn`, `gapsOut`, `rounding` | 0 |
   | `windows.shadowEnabled` | false |
   | `windows.borderSize` | 1 |
   | `lock.fieldRadius` | 0 |

   Hyprland's inactive window border becomes the text colour at 25 % (`rgba(fg 40)`), the active border keeps the palette's accent gradient (a focus ring must stay visible).
2. **QML handles what a token cannot say** (`Theme.gridMode`, read from `colors.json`): the cell borders (`BarItem` draws a hairline `Theme.cardEdge` around each cell and fills the bar's thickness; `BarSection` overlaps neighbours by one hairline so two cells share one line; `Bar.qml` draws the line along the bar's inner edge, and fills every empty stretch between and around the groups with an empty cell of the same style (`body.gridFills`, from each group's `spanFrom`/`spanTo`), so the bar is one unbroken row of cells; the cells overlap their neighbours by one hairline like the widgets do), `Theme.cardEdge` itself (fg at 22 % instead of 8 %, so every card, popup, notification, OSD and settings card gets the stronger line), and the literal radii (toggle, slider track, halo and bead, the OSD, battery, calendar and timer progress bars, badge dots, the overview's add-workspace button, the stage cards) which are 0 (`Theme.gridSquare`, grid mode without `gridRoundControls`; the stage cards use `Theme.gridMode` and are always square).

## Not covered

- GTK apps (Thunar, libadwaita apps) keep their own rounding: they take colours from the generated `gtk.css`, but their corner radii are in the adw-gtk3 stylesheet and would need a long selector list to override.
- Windows get a 1 px border each, so two tiled windows show a 2 px line between them (Hyprland has no shared border).
- Spacing inside the settings window (between sections and rows) and inside popups is layout, not a gap setting, and is unchanged; the cards and rows are square with the stronger edge. Since 2026-10-28 a settings row whose key grid mode replaces shows "Set by grid mode" and the value used, in place of its control (`settings-app.md`).
- Kitty and other terminals: no rounding exists there.

## Checked

2026-10-29, on screen (top bar, eDP-1 + HDMI, the owner's settings): the stage rail with grid mode on has touching square cards, off has rounded cards 12 px apart; the calendar popup with `gridRoundControls` on has round corners, buttons and progress bars, off square ones; the bar is square in both. Not checked this day: other bar positions, the lock screen, the OSD and notification cards with the toggle on, light mode.

2026-10-26, on screen: top, left and bottom bar (touching cells with shared hairlines and the inner-edge line), the Wi-Fi popup, the settings window, a full-screen terminal window (no gaps, no rounding). Python: `settings.effective` and its overrides (tests), the generated Hyprland Lua (gaps 0, border 1, rounding 0, shadow off, light inactive border; parsed by Lua 5.4). Not checked: light mode, the right bar, grouped pills, hyprlock, the notification cards, the OSD, the overview, the stage rail and the menu in grid mode, a second monitor, a real reboot with grid mode on.
