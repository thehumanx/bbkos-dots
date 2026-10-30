# Theme engine

Colours come from the wallpaper; every look setting (radii, gaps, blur, fonts) is one value in one file. A small Python tool turns that file into generated theme files, and Quickshell, Hyprland and kitty only read those. The settings window (`docs/modules/settings-app.md`) is a front end for the same tool. Design: `docs/specs/2026-10-18-theme-engine-settings-app-design.md`; plan: `docs/plans/2026-10-18-theme-engine-settings-app.md`.

Labels used below: **verified** = observed on this machine on 2026-10-18 and the evidence is stated; **by design / inferred** = follows from the code or an inference, not observed; **untested** = nobody has done it.

## 1. Purpose and flow

```
settings.json  --(bbkos-theme: validate, clamp)-->  matugen palette (only if colour inputs changed)
                                                      |
                               render in memory (tokens, contrast floors, OKLCH ANSI colours)
                                                      |
              per-file atomic replace into ~/.local/state/bbkos/theme/ (only the files whose text changed)
   colors.json   hypr-theme.lua   kitty-theme.conf   gtk.css   palette.json   stamp.json
        |               |                 |
 Quickshell        hyprctl reload    SIGUSR1 to kitty
 FileView watch    (and loaded at     (include in kitty.conf)
 (ThemeStore)       login by bbkos_load)
```

**Only what changed is written and reloaded (2026-10-31).** Owner: "everytime i make any of the changes on this page or other pages, the windows reloads". Every settings change used to rewrite every generated file and run a full `hyprctl reload`, which re-applies every window (they flashed), even for a bar setting that changes only `colors.json` (confirmed by a dry run: `hypr-theme.lua`, `hypr-binds.lua` and `kitty-theme.conf` byte-identical). Rewriting alone was enough to reload Hyprland: its autoreload (`misc:disable_autoreload` false) watches the files it loaded, and an identical but replaced `hypr-theme.lua` set it off about a second later. Now `apply._run` writes only the generated files whose text changed and passes that set to `reload.reload_all`, which runs `hyprctl reload` only when `hypr-theme.lua` or `hypr-binds.lua` changed and signals kitty only when `kitty-theme.conf` did (`HYPR_FILES`, `KITTY_FILES`); GTK, idle, cursor and night light already skipped an unchanged choice. An explicit `bbkos-theme apply` still reloads everything. Measured on the live session (Hyprland's `configreloaded` events, 3.5 s after each change): `shell.barHeight` and `stage.railPadding` changes 0, `windows.gapsOut` 1 each.

| Path | Tracked | Purpose |
|---|---|---|
| `~/.config/bbkos/settings.json` | yes (Stow package `bbkos-settings`, `--no-folding`; it is a symlink into the repo) | The owner's choices, a `version` field. The tracked file is the owner's live config, not a copy of the defaults |
| `~/.config/bbkos/matugen.toml` | yes | matugen config: empty `[templates]` plus the seven custom colours (`red green yellow blue magenta cyan warn`, `blend=true`); fallback colour `#7aa2f7` is passed on the command line, not in the file |
| `~/.config/bbkos/settings.json.bak` | no | Last settings that parsed and applied; the fallback when the file is corrupt |
| `~/.local/state/bbkos/theme/{colors.json,hypr-theme.lua,kitty-theme.conf}` | no | Generated, rebuilt on demand |
| `.../theme/palette.json` | no | The last palette, kept so `apply --only shape` does not run matugen again, and the lock screen's wallpaper sample (`lockCell`) |
| `.../theme/stamp.json` | no | Freshness stamp (section 6) |
| `.../theme/apply.lock` | no | flock file; one apply at a time, the latest request wins |
| `~/.local/share/bbkos/wallpaper/current.<ext>` | no | A **copy** of the chosen wallpaper (a deleted original or unplugged drive cannot break the desktop) |
| `~/.local/bin/bbkos-theme`, `~/.local/lib/bbkos_theme/` | yes (Stow package `bin`) | The tool (Python 3 stdlib only). The entry script sets `sys.dont_write_bytecode` because the package is reached through Stow symlinks |

Modules of the tool: `settings.py` (defaults, `RANGES`, validate/clamp, load with `.bak`, atomic save), `palette.py` (matugen call), `contrast.py` (WCAG ratio, lightness nudging, OKLCH helpers), `render.py` (three output texts), `wallpaper.py`, `reload.py`, `apply.py`, `cli.py`. Tests: `python3 -m unittest discover -s tests/theme -v` from `~/.local/share/bbkos/repo` (133 tests at the end of Task 15; 329 on 2026-10-21).

## 2. Commands

| Command | Effect |
|---|---|
| `bbkos-theme apply [--only shape\|colors] [--out-dir DIR]` | Render and reload. `--only shape` reuses `palette.json` (falls back to matugen when it is missing or unreadable). `--out-dir DIR` is a dry run: writes only into DIR and does not reload |
| `bbkos-theme set KEY VALUE` | Validate and clamp one setting (`windows.rounding 12`), apply, then write `settings.json`. `set wallpaper.path` is rejected with a pointer to `wallpaper set/clear` |
| `bbkos-theme wallpaper set [--] FILE` | Copy FILE in as `current.<ext>` (png, jpg, jpeg, webp, bmp, gif; 40 MB cap), store the copy's path in `wallpaper.path`, apply. `--` guards a leading dash |
| `bbkos-theme wallpaper clear` | No wallpaper (plain colour, colours from the fallback `#7aa2f7`), apply |
| `bbkos-theme reset [TARGET...]` | Defaults for each TARGET, a section (`--help` lists all 27) or one key (`windows.rounding`; since 2026-10-28), in one write and one apply; no TARGET: everything. `reset wallpaper` and `reset` also delete the wallpaper copy; `wallpaper.path` alone is refused. An unknown target exits 2 and changes nothing |
| `bbkos-theme avatar set [--] FILE` / `avatar clear` | (2026-10-28.) The lock screen avatar: copies FILE (png, jpg, jpeg, webp; at most 10 MB) to `~/.local/share/bbkos/avatar/avatar-<first 12 hex of its SHA-256>.<ext>` (`BBKOS_AVATAR_DIR` overrides; `avatar.py`), records the path in `lock.avatar`, applies, then removes older copies; a failed apply removes the new copy. `clear` goes back to the shipped picture. `set lock.avatar` is refused |
| `bbkos-theme defaults` | (2026-10-28.) JSON `{"defaults": ..., "gridMode": ..., "gridRoundOff": ...}`: the built-in defaults, the values grid mode puts in place (`GRID_OVERRIDES`) and the radii it also squares unless `shell.gridRoundControls` is on (`GRID_ROUND_OFF`). The settings window reads it once to mark changed rows and to show "Set by grid mode" |
| `bbkos-theme status` | Paths, whether the three generated files exist, `fresh: yes\|no (run bbkos-theme apply)\|unknown`, wallpaper, mode, scheme |
| `bbkos-theme contrast` | Measures the generated `colors.json` against the WCAG table of section 4a: prints how many colour pairs pass and the tightest one, lists any that fail, exit 1 when one does. `bbkos-check` runs it |

Exit 0 on success; 1 on failure with the first informative error line on stderr (the settings window shows that line). Hooks (environment): `BBKOS_SETTINGS`, `BBKOS_STATE_DIR`, `BBKOS_SHARE_DIR` override the three default paths; `BBKOS_KITTY_COMM` overrides the kitty process name (default `kitty`; test hook that is also honoured in production); `BBKOS_MATUGEN` was proposed in a brief but **does not exist**: matugen is found through `PATH` (tests put a fake first).

Rescue from any terminal or TTY: `bbkos-theme reset` (defaults, a plain colour, today's look). Only `status` was run during the documentation pass; the other commands were exercised during Tasks 5 to 15.

## 3. Settings schema (final ranges; `settings.py` `RANGES` is the single table)

The tool clamps; the UI uses the same ranges. Keys are flat (`windows.shadowEnabled`, not a nested `windows.shadow` object).

| Key | Default | Range / step |
|---|---|---|
| `wallpaper.path`, `wallpaper.fit` | `""` (none), `cover` | absolute path (relative is dropped to `""`), only `cover` |
| `colors.mode` | dark | dark, light |
| `colors.scheme` | tonal-spot | content, expressive, fidelity, fruit-salad, monochrome, neutral, rainbow, tonal-spot, vibrant |
| `colors.sourceIndex` | 0 | **0-3** (which dominant colour of the image). matugen 4.2.0's `--help` says 0-4, but 4 is rejected on any image (clap error `4 is not in 0..4`, rc 2): verified with a dry run on a scratch image, indexes 0-3 rc 0 If the image has fewer distinct colours than the index, `matugen` exits 1; `palette.generate` then retries once with index 0 (the dominant colour) instead of failing (test `test_missing_source_colour_retries_with_the_dominant_one`). |
| `colors.contrast` | 0.0 | -1.0 to 1.0 |
| `colors.accentStrength` | 1.0 | 0.0-1.0; (2026-10-29.) how vivid the wallpaper's colour is in the accent and the tints: `render.mute` multiplies the OKLCH chroma of matugen's `primary` and `tertiary` and the two primary tones (`tone_primary`, `soft_primary`) by it before anything is derived or lifted to its contrast floor, keeping lightness and hue; 0 = grey. It drives `accent`, `accentSoft` (the active page, slider fills, pressed buttons), `secondary`/`tertiary` and their soft shades, the focus ring and the GTK accent. Not scaled: `warn`, `crit`, the ANSI colours, background, surface and text (the floor lift can move warn a hair). The turned-hue tints keep slightly more than the scaled chroma, because they were gamut-clipped at 1.0. `shell.tint` is a different control (how far bar icons lean toward the tints) |
| `colors.folderIcons` | true | bool; folder icons in GTK apps take the accent's hue ("GTK apps" below) |
| `colors.auto`, `colors.lightFrom`, `colors.darkFrom` | false, `07:00`, `19:00` | bool; 24 h `H:MM` times (anything else is refused). While `auto` is on, `modules/theme/ThemeSchedule.qml` runs `bbkos-theme set colors.mode light\|dark` when it is turned on, at shell start, and when the time crosses a switch time (light from `lightFrom` until `darkFrom`, which may wrap past midnight; `components/ScheduleMath.js`); a mode picked by hand stays until the next switch. Minute-precision `SystemClock`, enabled only while `auto` is on. `qs ipc call themeschedule status` |
| `shell.barHeight` | 30 | 24-48 step 2 |
| `shell.gap` | 12 | 0-32 step 2 |
| `shell.radius` (popups, cards) | 12 | 0-24 step 2 |
| `shell.controlRadius` | 6 | 0-16 step 2 |
| `shell.fontSize` / `shell.font` | 13 / JetBrainsMono Nerd Font | 10-20 / non-empty string up to 512 chars |
| `shell.barPosition` | top | top, bottom, left, right |
| `shell.barOpacity` | 1.0 | 0.2-1.0 (floor so the bar is never invisible) |
| `shell.barBlur` | false | bool; the bar draws its own blur (`modules/bar/BarBlur.qml`) when true and opacity < 1. There is no Hyprland layer rule any more (2026-10-21) |
| `shell.barBlurAmount` | 0.5 | 0.05-1.0; strength of that blur. Hyprland's layer blur reuses the windows' `decoration.blur` size and passes, so it could not be tuned apart from the windows |
| `shell.tint` | 0.8 | 0.0-1.0; how far bar icons and highlights lean toward the wallpaper tints (see "Tints" below); 0 = plain text colour |
| `shell.barPills` | off | off, grouped, individual |
| `shell.pillRadius` | 8 | 0-16 step 2 |
| `shell.barItemGap` | 12 | 0-32 step 2; spacing between bar widgets |
| `shell.barItemPad` | 0 | 0-24 step 2; extra space inside each widget along the bar, in every bar mode, added to an individual pill's own 8 px |
| `shell.barFloat` | 0 | 0-24 step 2; space between the bar and the screen edges (0 = attached) |
| `shell.barRadius` | 0 | 0-24 step 2; corner radius of the bar itself, capped at half its thickness |
| `shell.gridRoundControls` | false | bool; (2026-10-29.) grid mode keeps the saved `radius`, `controlRadius` and `pillRadius` (popups, buttons, controls round) instead of squaring them; the bar stays square; windows, the pinned tiles and the rail's cards follow the window corner radius (`grid-mode.md`) |
| `shell.gridMode` | false | bool; flat grid look: while on, the renderers use `settings.GRID_OVERRIDES` (gaps, shadows, bar and stage radii 0; popup and control radii too unless `gridRoundControls`; individual pills, 1 px window border, `gapsIn` half of `gapsOut` so the gap between tiled windows equals the margin around them; stage rail padding and tile gap = the margin, dock on. `windows.gapsOut` and `windows.rounding` are not overridden: your margin and corner radius apply) in place of the saved values, which stay as they are (`grid-mode.md`) |
| `shell.barHug` | false | bool; the bar is only as long as its widgets and sits in the middle of the edge |
| `shell.popupShadow` | 0.5 | 0.0-1.0; strength of the tinted shadow under popups, pickers, notifications and the OSD (0 = none), `modules/motion.md` |
| `shell.reduceMotion` | false | bool; fades only: no popup grow, card slide, press scale, window pop-in or workspace slide (Hyprland too) |
| `shell.pillOpacity` | 1.0 | 0.0-1.0; opacity of the pill background (`grouped` or `individual`) |
| `windows.gapsIn` / `gapsOut` | 5 / 20 | 0-20 / 0-40 |
| `windows.borderSize` | 2 | 0-8 |
| `windows.activeBorder` | true | bool; off: the focused window's border has the inactive colour (no highlight); the border size still applies |
| `windows.rounding` | 10 | 0-24 |
| `windows.activeOpacity` / `inactiveOpacity` | 1.0 / 1.0 | 0.6-1.0 |
| `windows.shadowEnabled` / `shadowRange` | true / 4 | bool / 0-20 |
| `windows.blurEnabled` / `blurSize` / `blurPasses` | true / 3 / 1 | bool / 1-12 / 1-4 |
| `windows.animations` | true | bool |
| `bar.layout` | left: workspaces; centre: clock; right: the rest (`settings.py` `BAR_LAYOUT_DEFAULT`) | list of `section:widget` entries, sections start/center/end; each widget once; order in a list is the order on the bar; unknown and repeated entries dropped, missing widgets appended at their default section |
| `bar.hidden` | empty | list of widget names switched off (2026-10-31): left off the bar (not created) but kept in `bar.layout`, so one switched on again is back in its place; unknown and repeated names dropped; `bbkos-theme set bar.hidden tray,updates`, an empty value shows them all |
| `bar.iconGap` | 2 | 1-6 spaces between a widget's icon and its text (`bar.md`) |
| `bar.iconsOnly` | false | bool; every bar widget draws its icon only, and notifications and updates show a dot instead of a count (`bar.md`) |
| `capture.autosave` / `directory` / `editorMode` | true / `~/Pictures/Screenshots` / overlay | bool / `~/...` or absolute path / overlay, window; written to `~/.config/omasnap/omasnap.conf` by `apply` (`capture.md`) |
| `capture.recordArea` / `recordAudio` / `recordCamera` | region / desktop / false | region, screen / none, desktop, mic, both / bool |
| `capture.recordCameraSize` / `recordCameraMirror` | medium / true | small, medium, large / bool |
| `capture.recordQuality` / `recordFps` / `recordDirectory` | very_high / 60 / `~/Videos` | medium, high, very_high, ultra / 30 or 60 / path as `directory` |
| `terminal.fontSize` / `padding` / `opacity` | 11 / 0 / 1.0 | 8-20 / 0-24 / 0.6-1.0 |
| `touchpad.naturalScroll` / `flipX` / `flipY` | false | bool |
| `touchpad.scrollFactor` | 1.0 | 0.1-2.0 (Hyprland `scroll_factor`) |
| `touchpad.scrollMethod` | auto | auto (Hyprland default), 2fg, edge, on_button_down, no_scroll |
| `touchpad.tapToClick` / `tapAndDrag` / `disableWhileTyping` | true / true / true | bool |
| `touchpad.dragLock` / `drag3fg` | 0 / 0 | 0-2 |
| `touchpad.tapButtonMap` | auto | auto, lrm, lmr |
| `touchpad.clickfingerBehavior` / `middleButtonEmulation` | false / false | bool |
| `touchpad.wsSwipeDistance` | 300 | 50-2000 step 10 (px) |
| `touchpad.wsSwipeCancelRatio` | 0.5 | 0.0-1.0 |
| `touchpad.wsSwipeInvert` / `wsSwipeDirectionLock` / `wsSwipeCreateNew` | true / true / true | bool |
| `touchpad.wsSwipeForever` | false | bool |
| `touchpad.swipe3Up` / `swipe3Down` | none | none, workspace, close, fullscreen, float, special, overview, overview-close |
| `touchpad.swipe4Up` / `swipe4Down` / `swipe4Left` / `swipe4Right` | none | none, workspace, close, fullscreen, float, special |

Touchpad values are written into `hypr-theme.lua` (one `hl.config` call) and applied with a full `hyprctl reload`.
Three-finger left and right are Hyprland's built-in workspace swipe and cannot be set per direction: Hyprland ignores
a per-direction gesture for the same finger count when the horizontal one exists.

The `overview` / `overview-close` swipe actions (2026-10-20, for the workspace overview, docs/modules/overview.md)
are not stock Hyprland gesture actions: `render.py` emits them as Lua-function actions calling the overview's IPC
through the compositor, e.g.
`hl.gesture({ fingers = 3, direction = "up", action = function() hl.dsp.exec_cmd("qs ipc call overview toggle") end })`.
The dispatcher form (`hl.dsp.exec_cmd`) is used because it was verified live with `hyprctl dispatch …`; the wiki's
`hl.exec_cmd` direct-call form was never proven on this compositor (0.56.2). Because these functions only run at
gesture time, the compositor accepting the gesture line (`hyprctl configerrors` empty) does not prove the call works
at swipe time — the owner's swipe is the end-to-end check.

Wrong types, NaN, huge numbers, unknown keys and control characters never raise: the value falls back to its default with a warning. Blur, shadow and animations are plain settings (the battery profile that switched them off on battery was removed; decision 0003).

### Calendar section (`calendar.*`)

`weekStart` (`mon`, `sun`, `sat`; default `mon`), `weekNumbers` (bool, off), `moon` (bool, on). Read by the calendar popup only, nothing is rendered into a generated file (docs/modules/calendar.md).

### Lock section (`lock.*`, rendered into `hyprlock.conf`)

`settings.py` `RANGES` is the table. Per element in `avatar`, `welcome`, `date`, `time`, `battery`: `<e>Show` (bool), `<e>X` and `<e>Y` (int -1200..1200, px from the screen centre, y up), `<e>Size` (avatar diameter 32..300, others font size 8..200). Field (always shown): `fieldX` -600..600, `fieldY` -500..500 (so the field stays on a 1000 px high screen), `fieldWidth` 120..800, `fieldHeight` 30..120, `fieldRadius` -1..60 (-1 = pill), `fieldOpacity` 0.0..1.0. Background: `blurPasses` 0..5, `blurSize` 1..15, `brightness` 0.2..1.0, `autoDim` (bool, default on: lower the brightness when the wallpaper is too bright for the text, section 4a). Avatar picture: `avatar` ("" = the shipped `~/.config/hypr/lock-avatar.png`, a Stow link into the repo that is never written; otherwise only an absolute path ending in `/avatar-<12 hex>.png|jpg|jpeg|webp` without `#` or control characters, the copy `bbkos-theme avatar set` makes: the path goes into `hyprlock.conf`, where `#` starts a comment; a hand-edited value is replaced by ""; a copy that has gone falls back to the shipped picture at render). Text: `font`, `textColor` (`#rrggbb`, stored lower-case), `welcomeText` (may be empty; only `$USER` is kept as a variable), `timeFormat` (`24h`, `12h`), `dateFormat` (`weekday-long`, `weekday-short`, `numeric`). `<e>Align` (`left`, `center`, `right`; default `center`) for the five elements and `fieldAlign`, and `edgeMargin` (int 0..40, default 10, percent of the screen width): left/right render as `halign` with `position = ±edgeMargin%` (verified in a real lock: `10%` and the pixel equivalent land at the same x, right aligned `-10%` is 10% in from the right edge), X is unused then. Defaults reproduce the original lock screen. `render.render_hyprlock` writes `hyprlock.conf` into the state directory on every apply.

## 4. Token mapping

- `bg` / `surface` from Material `surface` / `surface_container`; `fg` from `on_surface`; `accent` from `primary`; `crit` from `error`; `warn` and the six ANSI hues from matugen custom colours with `blend=true` (Material harmonize).
- **`dim` from `outline`** (not `on_surface_variant`): the first mapping made `dim` (`#c5c6d0`) too close to `fg` (`#e2e2e9`) and flattened the secondary text tier across the shell (seen on a bar screenshot). The spec section 5.2 was amended accordingly. Every text and control colour is lifted to its WCAG floor on every surface it is drawn on (section 4a).
- **Terminal ANSI colours**: colour 7 from `on_surface_variant`, colour 8 from `dim` (a test requires 7 and 8 to differ by at least 1.25:1; colour 8 is `outline` lifted to 4.5:1, since it carries comments and other secondary text). The other ANSI colours are **muted through OKLCH**: normals at lightness 0.72 (dark) / 0.52 (light), brights plus or minus 0.07, chroma and hue kept, except near-grey roles, which get a canonical hue and a minimum chroma (below OKLCH chroma 0.04 a role takes a fixed hue: red 29, green 142, yellow 100, blue 264, magenta 328, cyan 195 degrees, and chroma 0.09; the only case where the output chroma can exceed the source chroma); chroma reduced to fit the gamut, no channel clipping. The repair exists because matugen returned `ansi_yellow` and `ansi_cyan` as `#ffffff` (and `ansi_green` as `#e8ffea`) for the owner's wallpaper under scheme fidelity, which rendered colours 3 = 6 and 11 = 14 as the same grey; with the repair that palette renders 3/6/11/14 as `#b2a662`/`#57b6b6`/`#c8bc77`/`#6ecdcc` (dry run with a copy of the live settings and wallpaper). Whether matugen returns grey custom colours for other schemes or images is not known: only this palette was observed. Two earlier HLS-based attempts produced neon or washed-out colours and were rejected after reading the actual hex values.
- Hyprland: active border gradient `primary` to `tertiary` (each lifted to 3:1 against `bg`, the focus ring), inactive `outline_variant`, `misc.background_color` from the surface, plus every `windows.*` knob.

### 4a. Accessibility (WCAG 2.2, 2026-10-21)

The palette comes from a wallpaper, so nothing about its contrast can be assumed. `render.tokens` therefore lifts every text and control colour until it clears its floor on **every surface it is drawn on**, moving only OKLCH lightness (the wallpaper's hue and chroma are kept; a colour that already passes is not touched). `a11y.py` holds the table; `bbkos-theme contrast` and `bbkos-check` measure the generated files against the same table.

| Colour | Floor | Surfaces it is checked on |
|---|---|---|
| `fg` (text) | 4.5:1 (SC 1.4.3) | bg, surface, popup, inset, control, pill, surfaceHigh, accentSoft |
| `dim` (secondary text, terminal colour 8) | 4.5:1 | bg, surface, popup, inset, control, pill, surfaceHigh |
| `accent`, `secondary`, `tertiary` as text or glyphs | 4.5:1 | bg, popup, inset, control, pill |
| `warn`, `crit` as text | 4.5:1 | bg, popup, inset, control |
| text on an accent fill (`bg` on `accent`: selected chip, selection) | 4.5:1 | accent |
| terminal colours 1 to 15 | 4.5:1 | bg |
| `accent` glyph on `accentSoft` (active page, hovered button); accent fills (slider, selected switch, progress) | 3:1 (SC 1.4.11) | accentSoft, popup, inset |
| `crit` edge, switch outline (text colour at 55%), switch knob (85%) | 3:1 | popup, inset |
| active window border (the focus ring) | 3:1 (SC 2.4.11) | bg |

popup, inset, control and pill are the surfaces `Theme.qml` derives at run time from the palette and `shell.tint` (`a11y.surfaces` is the same arithmetic; keep the two in step). `control` mixes 12% of `fg` into the popup, so `fg` and `control` are settled together in a few rounds. A raised surface is lighter than `bg` in a dark theme, so `dim` ends up closer to `fg` than a floor against `bg` alone gave (tier ratio about 1.7:1 in the fixture, was 2.0).

**Lock screen.** hyprlock draws light text over the blurred wallpaper, dimmed by `lock.brightness`. `apply` samples the wallpaper's centre with ffmpeg (64 x 36, one frame, 95th percentile of luminance) and writes the largest brightness at which the faintest text (the date, 80%) reads at 4.5:1 over the password field's lighter backing; with `lock.autoDim` off, no ffmpeg or a wallpaper ffmpeg cannot read, the setting is used as it is. The cap shows as a comment in `hyprlock.conf`. Dark text colours are left alone (the owner's choice). The sample is stored in `palette.json` (`lockCell`, keyed by the image's path, mtime and size) and reused while the file is unchanged: decoding the owner's 4096x2048 PNG took 0.6 s of every 0.68 s apply before 2026-10-28; a dry run (`--out-dir`) always measures.

**Run time.** The bar on a translucent bar without pills picks its text colour from the wallpaper strip behind it (`BarContrast.qml`): `fg` at 4.5:1, `dim` at 4.5:1 (else `fg`). Tinted bar text (the text colour leaned toward an accent) was checked over every palette in the sweep: lowest 5.46:1.

**Verified (2026-10-21).** A sweep of 1,620 real matugen palettes (10 seed colours incl. pure red, green, yellow, cyan, white, black, grey; dark and light; all 9 schemes; contrast -1, 0, 1; tint 0, 0.7, 1) times 62 pairs: 0 failures (before the change: 25 distinct pairs failed, worst 2.0:1, mostly at contrast -1). The same checks run as unit tests on random synthetic palettes (`tests/theme/test_a11y.py`). The owner's live palette (fidelity, contrast 1.0) already passed all 62 pairs.

**Not covered.** The wallpaper behind translucent windows, the window border against what lies behind it, and text over the wallpaper in a bar with pills but opacity under 100% (the pill is the backing, which is checked). Disabled controls (40%) are exempt in WCAG. The shell's own controls show no focus ring: keyboard focus visibility (SC 2.4.7) and keyboard operation of the settings controls were not audited.

Pixel-perfect rules for shell sizes (even sizes, `Theme.hair` hairlines, radius tokens): `docs/modules/quickshell.md`, section "Pixel-perfect rules".

### Tints (2026-10-21)

Before this change the shell used one accent (`primary`) and plain text colours everywhere, so a palette looked monochrome. The owner's palette made it worse: scheme `vibrant` with contrast 1.0 turns every scheme colour (primary, secondary, tertiary, error, ...) almost white (`#b4fdff`, `#e1f2ff`, `#ffece9`).

New tokens in `colors.json`: `gridEdge` (2026-10-30: grid mode's opaque cell border, `grid-mode.md`), `secondary`, `tertiary` (two more accent hues), `accentSoft`, `secondarySoft`, `tertiarySoft` (deep shades, for backgrounds) and `surfaceHigh` (raised surface). Where they come from:
- `palette.py` reads two tones of matugen's **primary tonal palette** (`palettes.primary.<tone>`, which does not collapse with the contrast setting): `tone_primary` (tone 80 dark / 40 light) and `soft_primary` (tone 30 dark / 90 light), plus `colors.surface_container_high`. A matugen output without `palettes` falls back to `primary`. A `palette.json` written before this change lacks the new keys and is regenerated by `apply` (`P.ROLES` has 19 entries).
- `render.tints`: `secondary` / `tertiary` are `tone_primary` with its OKLCH hue turned -40 / +40 degrees (same lightness and chroma, chroma only cut to fit the gamut), floored at 3:1 like the accent; the `*Soft` ones are the same rotation of `soft_primary`. matugen's own secondary and tertiary tones were tried first and rejected: nearly grey (`#b0cccc`, `#b4c7e9`) for this wallpaper, so the widgets would not have changed visibly. A grey wallpaper keeps every tint grey (test).
- For the owner's wallpaper: accent `#b4fdff`, secondary `#79d9a5` (green-teal), tertiary `#7dccff` (sky blue), accentSoft `#004f51`.

Quickshell: `Theme.accent2/accent3`, `accent2Soft/accent3Soft`, `accentSoft`, `surfaceHigh`, `Theme.tint` and `Theme.tinted(tone, base)` (base leaned toward the tone by `shell.tint`). Bar widgets call `Txt.tone(Theme.accentN)` (clock and workspaces and audio: accent3; display, battery, updates, notifications: accent2; overview, network: accent; gear and Bluetooth: accent3). When a translucent bar flips its text colour for a bright wallpaper (`BarContrast`) the tints stay off, because they are made for the dark palette background. The pill colour leans toward `accentSoft` by up to 45% of the tint. Popups, notification cards, the volume OSD, the polkit dialog and the pickers use `Theme.popupBg`: `surface` leaned toward `accentSoft` by up to 50% of the tint (opaque; was the plain `surface`, 2026-10-21). Inside a popup or card two more tokens derive from `popupBg`: `Theme.inset` (toward `bg` by 55%: progress tracks, selected rows, notification cards, inputs, dividers, the toggle's off track) and `Theme.control` (toward `fg` by 12%: buttons, chips, hover rows), so every layer follows the tint. The settings window's sidebar and cards use `popupBg` too; its own background stays `bg`. Controls use `accentSoft` (buttons, chips, hover rows).

## 5. matugen findings (verified 2026-10-18)

matugen 4.2.0 (installed from `extra`, `/usr/bin/matugen`). Used as a palette engine only (`--json hex --dry-run`). All probes used a throwaway `--config`. Fixture: `tests/theme/fixtures/matugen-sample.json` (640x400 `testsrc` PNG, dark, tonal-spot, all 7 custom colours).

Command the tool builds (wrapped in `systemd-run --user --scope --quiet -p MemoryMax=1G` and `timeout 20`, image capped at 40 MB):

```
matugen image IMG --json hex -m dark -t scheme-tonal-spot --source-color-index 0 --fallback-color '#7aa2f7' --dry-run --config CFG
matugen color hex '#7aa2f7' ...      # no image: colour source
```

- **Config gotcha**: a config with only `[config.custom_colors]` fails (rc 1, `missing field 'templates'`). It needs a `[templates]` table, even if empty.
- **Custom colours are in the JSON, blended** at `colors.<name>.<mode>.color` (`mode` = `dark`, `light`, `default`; lowercase `#rrggbb`). For each custom colour X: `X`, `X_container`, `on_X`, `on_X_container`, `X_source`, `X_value` (the last two are the unblended input). So the template fallback of spec 8 item 1 was not needed. Blend example (dark, test image): red `#ffb595` blended vs `#ffb4a8` unblended. The fixture's dominant colour is pure green, so green blends to itself: palette tests must not assert blend differences from the fixture (image dependent, not a bug).
- Other keys: `colors` has 92 keys; roles used: `surface`, `surface_container`, `on_surface`, `on_surface_variant`, `primary`, `tertiary`, `error`, `outline`, `outline_variant`, `source_color`. Also `palettes.*` and `base16.*`.
- **Hostile inputs** (all with `--source-color-index 0`): 1x1 grey, 64x64 grey and fully transparent PNGs exit 0 with a complete JSON but **silently fall back to `#4285f4`** (Google blue) with empty stderr; with `--fallback-color '#7aa2f7'` the fallback is ours. The caller can only detect the fallback by comparing `colors.source_color` (the tool does not do this; it just accepts the palette). A missing file is rc 1 with empty stdout.
- Without `--source-color-index` (or `--prefer`) a multi-colour image with no TTY exits 1 (`Multiple source colors found ...`): the tool always passes the index.
- Accepted `-t` types: the nine in the schema plus `scheme-smart`; `-m`: light, dark, smart; invalid values are clap errors (rc 2). Only `--json hex` was exercised. `--contrast` takes -1..1.
- Error text: real matugen failures print a multi-line anyhow-style message whose first line is a bare `Error:`; the tool skips that line and returns the first informative one (for example the decode cause), so the settings window never shows just "Error:".

## 6. Freshness by stamp

`apply` writes `stamp.json`: `{"settings_sha256", "files": [...], "applied": <UTC ISO-8601>}`. The hash is the sha256 of `settings.dumps()` of the validated settings that were applied, so whitespace or key-order edits do not make it stale. mtimes are **not** used: `settings.json` is committed last, so the generated files always look older (an earlier `newer than settings: no` quirk).

Commit order: render everything in memory; write and fsync ALL temp files (generated files, new stamp, `settings.json`) first (a new wallpaper is already staged as `current.new.<ext>`); then remove the **old stamp**; replace the generated files one by one; replace the **new stamp**; when the wallpaper changes, replace its copy now (the old copy moves to `previous.<ext>`); replace `settings.json` last. Consequences:

- A failure while staging (full or unwritable disk) leaves old files and old stamp byte-identical: `fresh: yes`.
- A failure in the middle of the replaces leaves no (or an old-removed) stamp, so `status` reads `fresh: unknown` and never `yes` over a mix of old and new files (fails closed). A reader can briefly see no stamp during a normal apply (`bbkos-check` then prints its `unknown` note).
- `status`: `fresh: no` when the settings changed since the last apply (for example a hand edit), also when `settings.json` is unreadable and the tool is only reading `.bak`; `unknown` when the stamp is missing or unreadable.
- `bbkos-check` section "Theme engine" uses this (see `update-safety.md`).
- A failure before the wallpaper step (staging, dropping the old stamp, any generated-file replace) leaves the old wallpaper copy byte-identical (`test_wallpaper_kept_when_a_generated_file_replace_fails`). If the wallpaper replace fails, the old copy is put back and `settings.json` stays old; the generated files and stamp are already new. `status` then reads `fresh: no`, EXCEPT when the new image has the same extension as the old one: the settings hash is unchanged, so `status` reads `fresh: yes` although `palette.json` and the generated files come from the new image (reproduced by the final reviewer, not fixed; `bbkos-theme apply` repairs it because the stored palette inputs no longer match the file). If the final `settings.json` replace fails, the new copy is removed and the old one moved back from `previous.<ext>` (`test_settings_replace_failure_puts_old_wallpaper_copy_back`, injected failure). A kill or power loss between the wallpaper replace and `settings.json` is not covered: with the same extension the state is consistent (the settings content is identical); with a different extension `settings.json` still points at the old `current.<ext>`, which has moved to `previous.<ext>`, so the desktop shows the plain colour (`fresh: no`); `bbkos-theme wallpaper set -- <share>/previous.<ext>` restores the old image. Not tested live (an injected failure was tested, a real kill was not).
- Tested by `test_half_commit_leaves_no_stamp` (it distinguishes the new order from the old one) and the unit suite.

## 7. Failure handling and recovery

| Case | Handling | Evidence |
|---|---|---|
| Bad, unsupported or corrupt image; matugen missing or failing; 20 s timeout | Nothing is replaced; the previous theme and `settings.json` stay; one error line on stderr | Unit tests with a fake matugen; a non-image through the real wrapper (`Format error decoding Png: Invalid PNG signature.`) kept the old wallpaper (Task 12, live) |
| Disk full / unwritable state dir | All temp files staged first, so nothing live is touched | Unit test with a read-only dir; real disk-full not tried |
| Corrupt or hand-edited `settings.json` | Validated per key; unparsable falls back to `.bak`, then defaults, with a warning | Unit tests; `status` reads `fresh: no` while only `.bak` is readable |
| Racing applies (slider plus Thunar) | flock; latest wins; per-file atomic replace so no torn file | Unit tests incl. 50-apply stress test; live: five requests in 0.1 s gave 2 tool runs, last won |
| Hyprland, kitty or Quickshell not running | Each reload is skipped quietly | Unit test with no hyprctl and no kitty |
| Broken generated Hyprland file | `hyprland.lua`'s `bbkos_load` runs each file under `pcall` (the rest of the config still loads), shows Hyprland's own notification, and writes the error to `~/.local/state/bbkos/hypr-load-errors`; `bbkos-theme apply` warns with it after the reload and `bbkos-check` fails on it. `pcall` alone kept the error out of `hyprctl configerrors` (checked 2026-10-28) | Tested 2026-10-28: the loader through `hyprctl eval` on a scratch file that raises (recorded with its message; a good and a missing file not), unit tests for `reload.py` and `bbkos-check`. A broken real generated file was not tried |
| Generated files missing | Quickshell shows the built-in look; kitty logs `Could not find included config file ..., ignoring` and carries on | Verified (Tasks 7, 8) |

- **Recovery**: `bbkos-theme reset` from any terminal (needs a working matugen: it changes the colour inputs). `settings.json.bak` is a copy of the settings as last applied successfully (every successful change rewrites it): it guards against a corrupt or missing file, it is no restore point for earlier choices.
- **Backups of your choices**: the committed `settings.json` holds the defaults unless you commit your own; app changes show as an uncommitted change in `~/.local/share/bbkos/repo` (`bbkos-check` notes it) and are backed up only when you commit and push them. `git checkout`/`stash`/`reset --hard` in `~/.local/share/bbkos/repo` reverts the live settings file. Recommended: copy `settings.json` before experiments (and `previous.<ext>` keeps one wallpaper undo, below). The agents' tests restore the values they found and never reset them.
- **Wallpaper undo (`previous.<ext>`)**: setting, clearing or resetting the wallpaper moves the old copy to `~/.local/share/bbkos/wallpaper/previous.<ext>` (replacing any older `previous.*`; never read as the current wallpaper). One step back: `bbkos-theme wallpaper set -- ~/.local/share/bbkos/wallpaper/previous.jpg` (use the extension that is there). Costs one extra wallpaper file on disk (up to the 40 MB cap).
- **Last resort without matugen** (expected from reading the code, not tested): `mv ~/.local/state/bbkos/theme ~/.local/state/bbkos/theme.off && hyprctl reload`. Quickshell falls back to its built-in look, kitty ignores the missing include (logs one notice), Hyprland keeps its own values from `hyprland.lua` (`bbkos_load` skips a missing file; with the whole directory gone the load record `hypr-load-errors` is still written, empty). Undo: move the directory back and run `bbkos-theme apply`.
- Do not stow `bbkos-settings` without `--no-folding`: `.bak` and temp files would land in the repo. `.gitignore` hides stray `.*.tmp` next to the tracked file (its `*.bak` pattern matches nothing today; harmless).
- `stow -R` does not prune dangling links: after removing a script from the repo, remove its link by hand.
- A missing `settings.json` (or a dangling link) is read from `settings.json.bak` when that exists (warning `settings.json missing, trying backup`), else defaults. A dangling `settings.json` symlink makes every apply and change fail with `settings.json is a broken link to <target>: re-stow (stow -R --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ bbkos-settings)`, so nothing recreates the link target's directories or overwrites `.bak` (unit tests `test_missing_file_uses_bak_when_present`, `test_dangling_settings_link_is_an_error_and_creates_nothing`).

## 8. Consumers

### Hyprland (`dotfiles/hypr/.config/hypr/hyprland.lua`)
- Loaded with `bbkos_load("hypr-theme.lua")` (a `pcall` that records failures, see the failure table) right after the main `hl.config` block; applied live by a full `hyprctl reload` (not an `eval`: a gesture added by an eval cannot be removed), then `hyprctl configerrors` and the load record are read. (Before 2026-10-28 this line described an `eval` of `pcall(dofile, ...)`, which `reload.py` no longer did.)
- Verified (Task 6): `hyprctl configerrors` with no errors prints two newline characters and nothing else (`od -c`: `\n \n`), before and after an apply. The tool reduces output to its first non-blank line, so that counts as no errors (spec 8 item 2). That **any non-blank output is an error report** is an inference from this empty case, not observed (no real error report was provoked).
- The `ok` that `hyprctl eval` should print on success was **expected, never observed**: the tool consumes it. The effect is confirmed by read-back with `hyprctl getoption` (`general:gaps_in` 5, `gaps_out` 20, `border_size` 2, `decoration:rounding` 10, `blur:enabled` / `shadow:enabled` / `animations:enabled` true, opacities 1.0, equal to the settings).
- Colour change at the first apply (fallback `#7aa2f7`): `general:col.active_border` `ee33ccff ee00ff99 45deg` -> `eeaec6ff eedfbbde 45deg`; `inactive_border` `aa595959` -> `aa44474f`; `misc:background_color` 0xff101014 -> 0xff121318.
- With `windows.rounding` 16, one `hyprctl reload` kept 16 (the file is applied at config load, as at login); `bbkos-theme reset windows` restored 10. `windows.blurEnabled false` switched blur off; reset restored it.
- Settings window rule and `Super+,` bind: see `settings-app.md`.

### kitty (`dotfiles/kitty/.config/kitty/kitty.conf`)
- The file ends with `include ~/.local/state/bbkos/theme/kitty-theme.conf`. **The include must stay LAST**: a later line setting the same key would win over the theme.
- The tool sends SIGUSR1 to processes whose `/proc/<pid>/comm` is exactly `kitty` and which are owned by the current user (never a command-line match). Kitty's own docs (`/usr/share/doc/kitty/html/conf.html`, `glossary.html`) document `kill -SIGUSR1 $KITTY_PID` as the config reload.
- `kitty --debug-config` does not exist in 0.49.2; the config was parsed headlessly with `kitty +runpy` and `kitty.config.load_config`. Effective values came from the generated file (foreground `#e2e2e9`, background `#121318`, cursor `#aec6ff`, font_size 11, padding 0, opacity 1.0).
- Live reload (spec 8 item 3) **verified for colours only**, on a throwaway kitty (own `--class`, own socket) read through `kitten @ get-colors`: after `bbkos-theme set colors.contrast 0.5` foreground `#e2e2e9` -> `#ffffff`, color0 `#1e1f25` -> `#26282d`, cursor `#aec6ff` -> `#cfdcff`, background unchanged; `reset colors` restored all. That the SIGUSR1 was sent by the tool is **by the tool's design, not observed directly** (the reload was seen only in the throwaway's reported colours). The owner's kitty PIDs were unchanged.
- **Not tested here**: reload of `background_opacity`, font size and padding on a running terminal (changing them would visibly alter the owner's real terminals). Whether kitty's documentation says `background_opacity` is reloadable was not checked.

### Quickshell (`ThemeStore`, `Theme`)
- `services/ThemeStore.qml` (singleton) reads `~/.local/state/bbkos/theme/colors.json` and `~/.config/bbkos/settings.json` (paths from `Quickshell.env("HOME")`, matching the tool, which ignores `XDG_*`). It exposes `colors`, `colorsDoc` (incl. the `ansi` list), `shell`, `settings` (the whole parsed settings file, one FileView) and `wallpaperPath`. `Theme.qml` binds every token to it and adds `radius` and `controlRadius`. IPC: `qs ipc call theme status` (JSON of the tokens as the shell resolves them) and `qs ipc call theme reload` (manual and test hook).
- API read from the installed type files (Quickshell 0.3.2): `FileView.path/watchChanges/blockLoading/printErrors`, `loaded`, signals `loaded()`, `loadFailed`, `fileChanged()`, methods `text()`, `reload()`. `fileChanged` does not reload by itself, so the handler calls `reload()`. Plain `JSON.parse` in try/catch keeps the last good document on bad input.
- Fallback rules: missing file gives today's built-in values; an unparsable or non-object file keeps the last good values (one `WARN qml: ThemeStore: ...` per bad read, deliberately); a missing, wrong-typed or invalid key falls back to that key's default while the others still apply. ThemeStore's size sanity ranges are wider than the schema.
- **Spec 8 item 4: `FileView` with `watchChanges: true` survives an atomic rename (verified).** Evidence: the inode of `colors.json` changes on every apply (73423 -> 73477 -> 73485 -> 73493 -> 73501); each new value (`colors.contrast 0.5`, `-0.5`, `0.3`, `reset colors`, `shell.radius 20`, `reset shell`) appeared in `qs ipc call theme status` by the first poll after the command returned (115-230 ms including the tool's own run time), no restart. The same held after a cold `systemctl --user restart quickshell.service` (three more renames), after the file was moved away and back, and through the `settings.json` symlink (the tool replaces the link's target). So `reload.py` does not call `qs ipc call theme reload`.
- Before/after at the default settings: bg `#101014` -> `#121318`, surface `#1b1b22` -> `#1e1f25`, fg `#e6e6ea` -> `#e2e2e9`, dim `#7d7d88` -> `#8e9099`, accent `#7aa2f7` -> `#aec6ff`, warn `#e0af68` -> `#ffb778`, crit `#f7768e` -> `#ffb4ab`. Sizes unchanged.
- Radii: containers at 12 use `Theme.radius`, rows/buttons/inputs at 6 `Theme.controlRadius`, the two 8 px elements `controlRadius + 2`, pills stay height-derived. The last hard-coded radius 6 (`NetworkRow.qml` reveal toggle) uses `Theme.controlRadius` since the final fix pass; light-colour mode and some states are click-only (Polkit dialog, critical-notification border, hover states, captive-portal card).

### Wallpaper module (`modules/wallpaper/Wallpaper.qml`)
Verified 2026-10-18 on Quickshell 0.3.2, GPU renderer, one screen (eDP-1, 1920x1200 at 1.5).
- A `Scope`, instantiated first in `shell.qml`: `Variants { model: Quickshell.screens }` of `PanelWindow` on `WlrLayer.Background` (namespace `bbkos-wallpaper`, no keyboard focus, all four anchors, `ExclusionMode.Ignore`, `mask: Region {}` so no input, colour `Theme.bg`). Two `Image`s (`PreserveAspectCrop`, `asynchronous`, `cache: false`, `sourceSize` = window size times `devicePixelRatio`) crossfade over 400 ms; the first image of a window appears without a fade. Nothing loads before the window has a size (a 0 `sourceSize` would decode at full size).
- File URL: each path segment percent-encoded (`components/FileUrl.js`, shared with the settings page). A windowless probe loaded `odd dir #1/a #b ?c %d 日本 (1).png`. A non-absolute `wallpaper.path` gives the plain colour and one WARN. Known gap: `encodeURIComponent` throws on a lone surrogate (hand-edited settings); a directory path or surrogate is not covered by the WARN.
- **Same path, new bytes**: `wallpaper set` (since the final fix pass) moves the old copy away to `previous.<ext>` and then renames the new `current.<ext>` in, so the path does not change but is briefly absent (the file-watch evidence below was recorded BEFORE that change and has not been re-observed). A `FileView` on the copy with `preload: false` and `watchChanges: true` only watches (it never read the file in a probe) and its `fileChanged` fired for create, rename-over (three times), in-place rewrite (twice, hence a 150 ms debounce), delete and re-create. Each change bumps a serial; the spare `Image` is reset to `""` and set again so the bytes are re-read. Rejected: reloading on every `settings.json` change (every slider step would re-decode) and watching `palette.json`.
- **Failures**: a missing file, garbage bytes or a decode error give `Image.Error`; the window shows `Theme.bg` (fade out). Qt logs one line per window and failure; the module adds none and never retries.
- **Memory (PSS of the shell)**: plain 160.7 MB; 1920x1200 PNG 173.2 MB (**+12.4 MB**); then a 4000x2500 PNG 208.7 MB (**+48 MB** over plain, although `decoded` was 1920x1200) and still 206.5 MB two hours later. The image on screen is screen-sized, but the process keeps the memory of the large decode (an anonymous heap region of 26-35 MB appeared, likely a glibc arena holding freed decode buffers; Qt's PNG reader has no scaled decode, so a 4000x2500 PNG is decoded at full size, 40 MB, then scaled). It is a high-water mark, flat afterwards, not a per-change leak. **The spec's former "about 9 MB per screen" is true only for screen-sized images** (corrected in the spec). These are measurements, not a limit: on 2026-10-18 the PSS was 226.8 MB after 42 min of the owner's use (window closed, a 7 MB JPEG wallpaper), +66 MB over plain, more than the +48 MB of the PNG test (read by the final reviewer; what the 66 MB consists of was not broken down). Accepted by the owner's controller as allocator retention on a 30 GiB machine. Mitigations deferred: pre-scaling at `wallpaper set`, `MALLOC_ARENA_MAX=2` / `MALLOC_TRIM_THRESHOLD_` in the unit. Not separated: how much came from the 2880x1200 step versus the 4000x2500 step; a large JPEG (scaled decode possible) was not measured.
- **Hotplug**: `hyprctl output create headless` gave `HEADLESS-1`; `wallpaper status` listed a second window at once (decoded 1920x1200 to cover 1920x1080); after removal only eDP-1 was listed; same PID, `NRestarts=0`.
- **Seen on screen** once (session unlocked): with the 1920x1200 test gradient the gaps around a window showed the gradient's sienna end and the window border had the new palette colour. On 2026-10-18 17:06 the owner picked a real wallpaper (`current.jpg`, 1.2 MB) in the app; `wallpaper status` showed it decoded at 1920x1257 (status JSON only; the look was not judged by the agents).
- IPC: `qs ipc call wallpaper status` gives `{path, screens: [{name, width, height, logical, scale, shown: image|plain, opacity, decoded, status}]}`.
- **Animated GIF**: a GIF wallpaper is accepted; it is documented (spec) to show its first frame only. Not tested here.
- **Not tested**: the crossfade's smoothness by eye, the first image without a fade at login (only the `settled` logic through IPC), a second real monitor with a different scale, the look under transparent or blurred windows.
- Hot reload note: Suspected trigger (unconfirmed): hot reload after adding a new QML type file, or after a multi-file edit, or an edit while the settings window was open; the shell then answers "Not ready to accept queries yet" until `systemctl --user restart quickshell.service`. Cause not found, not reproducible on demand. Sources: `task-9-report.md`, `task-12-report.md` (see failure-modes.md).

## 9. Verified vs not verified

| Item | State |
|---|---|
| Tool: validation, clamping, atomic per-file replace, lock, stamp, `.bak` fallback, `previous.<ext>` | Verified by the unit suite (145 tests after the final fix pass; one-off mutation checks during the reviews are not part of the count) and live applies |
| matugen JSON path, blended custom colours, `sourceIndex` 0-3 | Verified (section 5) |
| Hyprland values read back after apply, reload keeps them | Verified (`hyprctl getoption`) |
| `hyprctl eval` printing `ok`; non-blank `configerrors` text being an error report | Expected / inferred, never observed |
| kitty colour reload via SIGUSR1 | Verified on a throwaway kitty; signal sending "by design", not observed directly |
| kitty opacity / font / padding reload | Untested |
| Quickshell FileView follows atomic rename | Verified |
| Wallpaper module: set, clear, replace at same path, hotplug, failure to plain colour | Verified through IPC/status; seen on screen once |
| Wallpaper crossfade by eye, GIF, second monitor | Untested |
| Settings window and every page rendered / clicked | Untested (screen was locked; see the owner checklist in `settings-app.md`) |
| Thunar menu entry | Untested (no click) |
| `bbkos-check` theme section | Verified live once (5 ok, rc 0) and by tests |
| Battery cost of blur/shadow/animations | Not measured |
| Boot / login with the theme (first login errors) | Not yet observed |

### Spec section 8: the six verification outcomes

1. **matugen `--json hex` includes the blended custom colours**: yes (`colors.<name>.<mode>.color`, section 5); the template fallback was not needed.
2. **`hyprctl eval` of a `dofile` with `hl.config{...}` applies every knob**: yes, read back with `hyprctl getoption`, `configerrors` empty (section 8). The `ok` reply was never observed (the tool consumes it).
3. **kitty reloads on SIGUSR1 with an included theme file and keeps running**: verified for colours on a throwaway kitty; opacity, font size and padding reload untested (section 8).
4. **`FileView` `watchChanges` fires on atomic rename**: verified (inode changes on every apply, each new value seen at the first poll, also after a restart and through the settings symlink; section 8).
5. **Settings window class/title for the Hyprland rule**: class `org.quickshell` (shared by every Quickshell window), title `bbkOS Settings`; the rule matches both and the window opened floating at 900x640 (`settings-app.md`).
6. **Thunar custom action**: `~/.config/Thunar/uca.xml` existed and was merged (stock action kept first, backup `uca.xml.pre-bbkos`); image-only through extension patterns plus `<image-files/>`. Whether Thunar combines those as AND or OR, and the menu itself, are untested (click-only; `settings-app.md`).

## Appendix: per-task live evidence (compact)

- **Task 1** (matugen): see section 5. Decision gate: JSON path; template fallback not needed.
- **Task 6** (Hyprland): stow `--no-folding` of `bbkos-settings`: `~/.config/bbkos` a real directory, `settings.json` and `matugen.toml` symlinks. First `apply`: rc 0, silent, about 0.2 s. `hyprland.lua` loads the file with `pcall(dofile, ...)`. `bbkos-power-profile` removed (its link had to be removed by hand: `stow -R` does not prune).
- **Task 7** (kitty): section 8. Missing include logs one notice and the rest of the config applies.
- **Task 8** (ThemeStore): section 8. One restart used; `reload.py` unchanged.
- **Task 9** (wallpaper): section 8. A grim run hung on the locked screen (screen locked during most tests); no process was signalled.
- **Task 10 to 13**: see `settings-app.md`.
- **Task 14**: Thunar action, see `settings-app.md`.
- **Task 15**: stamp and `bbkos-check`; one live `apply` changed `fresh` from unknown to yes; the owner's settings were byte-identical before and after.

## GTK apps (Thunar and the rest), added 2026-10-21, live since 2026-10-23

`gtk.css` is the fourth generated file: `@define-color` lines for the libadwaita names (`window_bg_color`, `accent_bg_color`,
`headerbar_bg_color` ...) and the older `theme_*` names, all from the same tokens as the shell (so the text colours already meet the
contrast floors), plus comment markers `mode`, `accent` and `folders` that `reload.reload_gtk` reads back.
**Surfaces (2026-10-23):** as in the shell's settings window: the content area (`view_bg_color`) is the window colour `bg`; the
frame around it (window, header bar, menu and tool bars, sidebar, dialogs, also when unfocused) is the shell's tinted popup surface
(`a11y.surfaces` "popup"); a selected sidebar row is `accentSoft` with the normal text colour (`bbkos_selection_color` and
the GTK 3 rules in `render.GTK3_RULES`, for GtkPlacesSidebar and Thunar's tree view with class `sidebar`).
**Every selection (2026-10-23):** selected files in Thunar's icon and list views, list rows and text are also
`accentSoft` with `fg` (and `theme_selected_bg_color` / `_fg_color` likewise): adw-gtk3 drew Thunar's selected icon in
the full accent behind white text, unreadable with a light accent (the owner's screenshot). The pair is one the engine
lifts to 4.5:1 (a11y.FG_ON includes accentSoft; 9.35:1 on the owner's palette). Checked with a GTK 3 probe window
(a selected icon-view item: deep teal behind white text). Before, every surface was
`bg` (the darkest shade) and adw-gtk3 drew the selection grey, so Thunar read as plain dark mode (the owner's report).
**GTK 3 recolours live (2026-10-23).** GTK 3 reads `~/.config/gtk-3.0/gtk.css` once at start, and definitions there win over the
theme's, so an open app kept its colours until restarted. Now the colours live in a generated theme: `reload_gtk` writes
`~/.local/share/themes/bbkos-a` or `bbkos-b` (`gtk-3.0/gtk.css`: `@import` of `adw-gtk3` or `adw-gtk3-dark`, then of the generated
`gtk.css`, then the rules; later definitions win) and switches `gtk-theme` to it. GTK reloads a theme only when the name changes,
so the two names alternate, and nothing is switched while the theme text is the same (a hash of the colours is in its first line),
so a slider in the settings app does not make GTK apps reload for nothing. `~/.config/gtk-3.0/gtk.css` (Stow package `gtk`) is now a
comment only and must stay free of `@define-color`; `gtk-4.0/gtk.css` still imports the generated file (libadwaita reads it at start;
`color-scheme` is still set). An app started before this change holds the old user file: restart it once.
**Folder icons (`colors.folderIcons`, default on, Appearance › Wallpaper and colours):** `~/.local/share/icons/bbkos-icons-a` / `-b`, an icon theme that
inherits Adwaita and holds only Adwaita's folder SVGs (`render.FOLDER_ICONS`, places, `inode-directory`, `folder-open`) with every
colour turned to the accent's OKLCH hue, lightness and chroma kept (a near-grey accent, chroma under 0.015, gives grey folders).
Same idea as Adwaita-colors (github.com/dpejoh/Adwaita-colors), generated instead of shipped per colour. Alternating names again:
open apps do not notice rewritten icon files (tried: no change), they do notice a new `icon-theme` name. Off: back to `Adwaita`.
**Safety:** `reload_gtk` does nothing when `HOME` is not the user's real home. Tests and dry runs run the real tool with a temp
HOME, and gsettings still reaches the live session over D-Bus: on 2026-10-23 a test run pointed the live `gtk-theme` at `bbkos-a`
inside a deleted temp dir. The CLI tests also use `GSETTINGS_BACKEND=memory`.
**Why a package:** the stock GTK 3 Adwaita bakes its colours into the stylesheet, so a `gtk.css` override changed nothing (tried:
`@define-color` in the user file, and after an `@import` of the Adwaita resource in a custom theme; a plain `window { background: red }` rule
did apply, so the file was being read). `adw-gtk-theme` (extra, 125 KiB, no dependencies, no process) is built on the libadwaita names
and takes the overrides. Reference: how matugen/Gradience theme GTK 3.
Verified 2026-10-21: Thunar in dark and in light on the screen (screenshots), the gsettings values flipping with `colors.mode`.
Verified 2026-10-23: a running GTK 3 window (a Python probe on the real session) followed a colour change at once (window colour
`#2b3336` -> red test colour -> back) and a folder icon followed an accent change (`#9dcdea` -> orange `#ebb8a4` -> back); a fresh
Thunar shows the tinted frame, the dark content area, the `accentSoft` sidebar selection and the generated folder colours
(screenshots); `GtkCssTest`, `GtkReloadTest`, `FolderIconTest`; live `gtk-theme` unchanged by a full test run.
Not verified: GTK 4 / libadwaita apps, the light theme with the new surfaces, the owner's own Thunar after a restart, a wallpaper whose
accent is very light or dark (the on-accent text is the window colour, not separately contrast-checked).
