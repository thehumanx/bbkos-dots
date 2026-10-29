# Keybindings

Design: `docs/specs/2026-10-19-keybindings-design.md`.

**MERGE PROCEDURE (required, in this order).** `~/.config/hypr/hyprland.lua` is a Stow symlink into the main checkout and Hyprland autoreloads, so merging by itself makes the new `hyprland.lua` live; from then on every bind except the lid switch is missing until step 4 has run. That is why steps 1 and 2 must happen in this order.

1. Before merging, from the worktree, run `dotfiles/bin/.local/bin/bbkos-keybinds render`. The old config ignores the file, so this is harmless.
2. Merge `feat/keybindings` into `main`.
3. Re-stow the bin package with `stow --no-folding ... bin`, so `~/.local/bin/bbkos-keybinds` exists. Until then the settings page's Keybindings actions fail with "could not start".
4. Run `bbkos-keybinds apply` (renders and runs `hyprctl reload`); this is the step that restores the binds. Then run `bbkos-theme apply` so `bbkos-check` passes (it does not reload binds: it only evals `hypr-theme.lua`).

The editable keybindings of the desktop live in one user file, are changed only by the tool `bbkos-keybinds` and are shown and edited on the Shortcuts tab of the Keyboard page of the settings app (`settings-app.md`; its own Keybindings page until 2026-10-28).

## Files

| File | Role |
|---|---|
| `~/.config/bbkos/keybinds.json` | The user's binds. Written only by `bbkos-keybinds`. Previous text is kept beside it as `keybinds.json.bak`; `keybinds.json.lock` is the `flock` file |
| `dotfiles/bin/.local/lib/bbkos_theme/keybinds.defaults.json` | The shipped defaults. Used when `keybinds.json` does not exist, and by `restore` / `restore-all` |
| `~/.local/state/bbkos/theme/hypr-binds.lua` | Generated: one `hl.bind(...)` per enabled bind. Loaded by `hyprland.lua` with `bbkos_load` (a `pcall` that records a failure in `~/.local/state/bbkos/hypr-load-errors`). Do not edit |

Code: `dotfiles/bin/.local/bin/bbkos-keybinds` (stdlib Python), `bbkos_theme/{keybinds,keybinds_cli,keybind_actions}.py`; QML `services/KeybindStore.qml`, `modules/settings/PageKeybindings.qml`, `components/{KeyCapture,ActionPicker}.qml`. Tests: `tests/keybinds/`.

## File format

```json
{
  "version": 1,
  "binds": [
    {
      "id": "launch-terminal",
      "keys": { "mods": ["SUPER"], "key": "Q" },
      "action": { "type": "exec", "command": "uwsm app -T" },
      "flags": { "locked": false, "repeating": false, "mouse": false },
      "enabled": true
    }
  ]
}
```

- `id`: stable slug. Presets keep their id across edits, so restore can find the shipped entry.
- `keys.mods`: any of `SUPER`, `SHIFT`, `CTRL`, `ALT`; stored in canonical order SUPER, CTRL, ALT, SHIFT.
- `keys.key`: an xkb key name (`Q`, `Print`, `XF86AudioRaiseVolume`, `mouse:272`, `left`, `comma`). Aliases are normalised before comparing: `Return`/`Enter`, `Prior`/`Page_Up`, `Next`/`Page_Down`, `comma`/`,`, letters and digits upper case, `f5` to `F5`. Known names: A-Z, 0-9, F1-F12, `left right up down`, `Print Return Escape Tab space comma Page_Up Page_Down Home End Delete BackSpace`, the `XF86Audio*` keys, `XF86MonBrightnessUp/Down`, `XF86PowerOff`, `mouse:272`, `mouse:273`, `mouse_down`, `mouse_up`, `switch:on:Lid Switch`, `switch:off:Lid Switch`.
- `action` is one of:
  - `{ "type": "exec", "command": "..." }`: shell command, run through Hyprland's `exec_cmd`.
  - `{ "type": "dispatch", "name": "focus", "args": { "direction": "left" } }`: a Hyprland dispatcher. Names: `exec_cmd`, `focus`, `window.close`, `window.float`, `window.pseudo`, `window.move`, `window.drag`, `window.resize`, `layout`, `workspace.toggle_special`.
    The four directional focus binds (`focus` with a `direction`) render as Lua functions that cycle windows (`layout cycleprev` for left/up, `cyclenext` for right/down) while the active workspace's layout (`hl.get_active_workspace().tiled_layout`, stage mode is per workspace since
    2026-10-23) is `monocle` (`stage.md`) and are the normal directional focus otherwise.
    `window.cycle` (arg `direction`: `next` or `prev`; made most-recently-used on 2026-10-26, earlier Hyprland window order via `cycle_next`) renders as `bbkos_cycle(1)` / `bbkos_cycle(-1)`, Lua functions defined once at the top of the generated file (`_CYCLE_LUA` in `keybinds.py`). The generated file keeps its own most-recently-used list `BBKOS_MRU` (window addresses): a `window.active` subscription moves the focused window to the front (skipped while a cycle runs), and the list is seeded from `focus_history_id` when the config first loads. The first press collects the active workspace's mapped windows in that order (active window first) and focuses the previous one; each further press while the modifier is held steps one deeper (Shift+Tab steps back, wrapping to the least recent). Each step really focuses the window (`hl.dsp.focus` by address, then `bring_to_top`), so it works in monocle (stage mode) and for floating windows. A `input.keyboard.key` subscription (arguments: xkb keycode, time, state 1/0) calls `bbkos_cycle_end()` when a held modifier of a cycle bind is released (Alt 64/108, Super 133/134, Ctrl 37/105; Shift only picks the direction), which moves the chosen window to the front. A cycle bind with no modifier besides Shift ends after each press. Windows on other workspaces are not in the cycle. Two measured dead ends: a `release = true` bind on the modifier key never fires once Tab was pressed in between (with or without `ignore_mods`), and in monocle only the first of several `hl.dsp.focus` calls in one Lua call takes effect, so the focus history cannot be repaired by replaying focuses. Both subscriptions are removed before they are made again, so a config reload does not stack them.
  - `{ "type": "preset", "id": "brightness-up" }`: a catalogue entry that expands to one of the above, so the UI shows a label instead of a raw command.
- `flags`: `locked`, `repeating`, `mouse`; no others. Missing flags are false.
- `enabled`: `false` keeps the row but does not render it. Missing means true.

The lid switch binds (`switch:on/off:Lid Switch`) and the `hl.on(...)` hooks stay in `hyprland.lua`, outside this file; the page does not list them.

## Capture binds (2026-10-21)

Presets in the Screenshots group (`capture.md`): `screenshot-region` = `omasnap` (Super+Shift+S) and `record-menu` =
`bbkos-record stop || qs ipc call panel toggle record` (Super+Shift+R: stops a running recording, otherwise opens the options
panel; the exec command runs through a shell, so `||` works). The Print-key binds, and the presets that went with them
(`screenshot-full`, `screenshot-window`, `record-toggle`, `record-screen`, `record-panel`), were removed again the same day
(see below); the laptop's physical Print key sends Super+Shift+S anyway (`system-profile.md`).

## Imported from the old Omarchy setup (2026-10-21)

Source: `configs/hypr/bindings.lua` of `github.com/thehumanx/omarchy-setup` (97 lines: about 10 bindings, the rest `hl.unbind`
lines that remove Omarchy defaults). Each binding was compared with the live `keybinds.json` and decided one by one:

| Old binding | Decision |
|---|---|
| `SUPER+SHIFT+S` Screenshot | already here, same result (omasnap) |
| `SUPER+SPACE` Apps menu | already here, same result (the launcher, since 2026-10-23 the bbkOS menu, `menu.md`) |
| `SUPER+Q` Close window | already here, same result (live `close-window`; the shipped defaults file has Terminal there: the live file differs) |
| `SUPER+E` File manager (Nautilus) | skipped: `SUPER+E` already opens Thunar; Nautilus (42 packages, about 46 MiB) not installed |
| `SUPER+L` System menu | imported as the Power menu panel (`system-menu`); **Lock moved to `SUPER+CTRL+L`** |
| `SUPER+SHIFT+L` Toggle workspace layout | skipped (Omarchy's script cycles the workspace through dwindle, scrolling and floating; nothing equivalent here) |
| `SUPER+;` Emoji picker | imported: new Quickshell picker (`emoji.md`), types with `wtype` |
| `SUPER+CTRL+X` Dictation (start or stop) | preset `dictation-toggle` (2026-10-29): `voxtype record toggle`, or a notification when the Voxtype service is not running (`dictation.md`). Not bound while locked. A new shipped default is not added to the owner's existing file by itself: `bbkos-keybinds restore dictation-toggle` |
| `SUPER+SHIFT+R` Screen recording | imported as `record-menu`; the Print-key recording binds were removed in favour of it |
| `SUPER+CTRL+SHIFT+S` Capture menu | skipped (no combined menu) |
| `SUPER+ALT+SPACE` Omarchy menu | skipped; own menu hub to be built later (nice to have, below) |
| ~30 `hl.unbind(...)` lines (webapps, Tmux, Herdr, Calculator, reminders, ...) | nothing to do: those Omarchy defaults do not exist in bbkOS |
| `PRINT`, `ALT+PRINT` unbound ("no Print key needed") | all Print-key binds removed (Print, Shift+Print, Ctrl+Print and the recording ones) |

The shipped defaults (`keybinds.defaults.json`) follow the same decisions: 60 binds at the time (73 on 2026-10-26). Removing the presets before the live rows
made the tool refuse every change ("unknown preset"; it changes nothing then): the six rows were dropped with the tool's own
library after a backup, the rest of the file kept.

Key names: the validator now accepts the punctuation keys the Keybindings page's recorder can produce (`semicolon`, `period`,
`minus`, `equal`, `slash`, `backslash`, `apostrophe`, `bracketleft`, `bracketright`, `grave`, `Insert`) and the one-character
forms (`;`, `.`, ...) as aliases. Before, recording `;` produced a key the validator rejected.

### Omarchy's own defaults were not in that file

The file only holds the owner's *overrides*, so every binding Omarchy ships by default was invisible to the import. Found when
`Super+F` (fullscreen) did not work: it is an Omarchy default (`default/hypr/bindings/tiling.lua`:
`hl.dsp.window.fullscreen({ mode = "fullscreen" })`), never bound in bbkOS. Added 2026-10-21: preset `toggle-fullscreen`
(dispatcher `window.fullscreen`, arg `mode`) on `Super+F`, shipped and live. Omarchy's neighbours are `Super+Alt+F` (maximized,
`mode = "maximized"`) and `Super+Ctrl+F` (a script for tiled fullscreen); both added below.

#### Omarchy defaults compared and imported (2026-10-21)

The rest of the defaults (`default/hypr/bindings/*.lua`) were compared one by one with the live binds; the owner chose per bind.
Imported (shipped and live):

| Keys | Preset | Does |
|---|---|---|
| `Super+Ctrl+V` | `clipboard` (moved from `Super+Shift+V`) | clipboard history |
| `Super+Alt+F` | `toggle-maximize` | `window.fullscreen` mode `maximized` |
| `Super+Ctrl+F` | `toggle-tiled-fullscreen` | flips the client fullscreen state (0 / 2) of the active window, a Lua function |
| `Super+Backspace` | `toggle-opaque` | `set_prop opaque toggle` on the active window |
| `Super+Shift+Backspace` | `toggle-gaps` | gaps to 0 and back to the configured values (saved in the Lua global `BBKOS_GAPS`; a reload forgets the saved copy but re-applies the settings) |
| `Super+Shift+Space` | `toggle-bar` | `qs ipc call bar toggle` (see `bar.md`, "Hide or show") |
| `Super+Alt+S` | `stage-workspace` | `qs ipc call stagews toggle ''`: stage mode for the focused workspace until the next boot (`stage.md`, added 2026-10-23) |
| `Super+Shift+T` | `ocr-text` | `bbkos-ocr`: pick a region, its text goes to the clipboard (`capture.md`) |
| `Alt+XF86AudioRaise/LowerVolume` | `volume-up/down-precise` | 1% steps |
| `Alt+XF86MonBrightnessUp/Down` | `brightness-up/down-precise` | 1% steps (`bbkos-brightness up1|down1`) |

Dispatchers that need more than one call (`tiled_fullscreen`, `toggle_opaque`, `toggle_gaps`) are rendered as Lua functions
by `_LUA_FUNCTIONS` in `keybinds.py`. Skipped by the owner: browser and app launchers, universal copy/paste keys, close-all,
pop-out, window width, silent move, extra scratchpad keys, monitor and swap keys, keyboard resize, grouping, scaling keys,
wallpaper, notification and idle keys, colour picker, zoom and the hardware extras.

### Claude Code in bbkOS (2026-10-26)

Preset `claude-bbkos` (group Apps) on `Super+Ctrl+Enter`: `uwsm app -- kitty --directory "$HOME/.local/share/bbkos/repo" claude`, a new kitty
in the repo running Claude Code (own scope, as `launch-terminal`). The same action is a menu command (`menu.md`) and the
fish function `bbk` (`fish.md`). `Super+Enter` stays the plain terminal.

### Nice to have

- A bbkOS menu hub (Omarchy's `SUPER+ALT+SPACE`): one menu for apps, style, setup and system. The owner plans to build it later.
- A per-workspace layout cycle (dwindle, scrolling, floating), like Omarchy's `omarchy-hyprland-workspace-layout-toggle`.

## Tab binds (2026-10-21)

Shipped defaults (ids `cycle-window-next`, `cycle-window-prev`, `workspace-next-tab`, `workspace-prev-tab`): `Alt+Tab` / `Alt+Shift+Tab` switch like a browser's Ctrl+Tab (most recently used order, 2026-10-26): a tap goes to the previous window of the current workspace, and while Alt is held each further Tab (Shift+Tab to go back) steps deeper, committing when Alt is released (presets `cycle-window-next` / `-prev`, dispatcher `window.cycle`); `Super+Tab` / `Super+Shift+Tab` go to the next / previous existing workspace (the `scroll-workspace-next` / `-prev` presets, `focus workspace e+1 / e-1`). Measured: `e+1` wraps from the last existing workspace to the first and `e-1` from the first to the last. There is no preview overlay: each step focuses the window at once. The owner's live `keybinds.json` got the four binds through `bbkos-keybinds add`.

## Commands

`bbkos-keybinds COMMAND` (the tool's own `--help` text):

```
status                                  binds, warnings, conflicts, the action catalogue and shipped ids as JSON
add [--replace] --json FILE|-           add a bind (a full bind object)
set ID [--replace] --json FILE|-        replace the bind ID
remove ID                               delete a bind
enable ID [--replace] | disable ID      turn a bind on or off
restore ID [--replace]                  put a shipped bind back to its default
restore-all                             replace every bind with the defaults
render                                  write hypr-binds.lua only
apply                                   render, then hyprctl reload
--replace disables any other enabled bind on the same keys (otherwise a clash exits 3).
environment: BBKOS_KEYBINDS, BBKOS_STATE_DIR override the paths
```

Details from the code:

- `--json -` reads the bind from stdin. For `set`, an object without `id` gets the id from the command line; a different `id` in the object is an error.
- `add` refuses an id that exists (use `set`). `restore` of an id that was removed adds it back; an id that is not shipped is an error.
- `restore-all` does not read the old file, so it is the way out of a damaged `keybinds.json`.
- Every other write first loads strictly: if the file is unusable or a row would be dropped, nothing is changed (see the messages below).
- `status` prints JSON: `binds`, `warnings`, `conflicts` (pairs of ids), `actions` (the catalogue, each with `missing`, the tools not found in `PATH`) and `shipped` (ids of the shipped binds). A preset whose tool is missing still saves.
- Exit codes: 0 success; 1 failure (`KeybindError`, I/O); 2 usage or validation error; 3 combo conflict; 130 interrupted. The error is the first line of stderr; rollback warnings follow it; warnings from validation print as `warning: ...` after a successful run.
- A missing `hyprctl` or no `HYPRLAND_INSTANCE_SIGNATURE`: the files are written, the reload is skipped and the tool prints `saved; reload skipped (Hyprland not running)`.
- Mutations run under an `flock` on `keybinds.json.lock`, so two runs never interleave.

## Validation rules and messages

Validation messages are prefixed with the bind id (`<id>: ...`) when a bind has an id.

Errors (nothing is written):

| Rule | Message |
|---|---|
| Not an object | `bind is not an object` |
| No id | `bind has a missing or non-string id` |
| `keys` not exactly `{mods, key}` | `keys must be {mods, key}` |
| `mods` not a list of strings | `mods must be a list of names` |
| Modifier not SUPER/CTRL/ALT/SHIFT | `unknown modifier X` |
| `key` not a string | `key must be a string` |
| Key not in the known list | `unknown key X` |
| `flags` not an object | `flags must be an object` |
| Flag other than locked/repeating/mouse | `unknown flag X` |
| Flag not a boolean | `flag X must be true or false` |
| `enabled` not a boolean | `enabled must be true or false` |
| `action` not an object | `action must be an object` |
| Action type not exec/dispatch/preset | `action type must be exec, dispatch or preset` |
| Empty command | `command is empty` |
| Newline in command | `command has a newline` |
| Command over 512 characters | `command is longer than 512 characters` |
| Dispatch name empty | `dispatch name is empty` |
| Dispatch name not in the list above | `unknown dispatcher X` |
| Dispatch args not an object | `dispatch args must be an object` |
| Preset not in the catalogue | `unknown preset 'X'` |
| `mouse:` key without the `mouse` flag | `mouse trigger needs the mouse flag` |
| `XF86PowerOff` with `locked` | `the power key cannot be locked` |

CLI errors:

| Situation | Message (exit code) |
|---|---|
| Unreadable `--json` source | `cannot read SRC: reason` (2) |
| Not JSON | `not valid JSON: reason` (2) |
| `add` with an existing id | `a bind with id 'X' already exists (use set)` (2) |
| `set` with a different id in the object | `bind id 'X' does not match 'Y'` (2) |
| `restore` of a non-shipped id | `'X' is not a shipped bind` (2) |
| Unknown id (`set`, `remove`, `enable`, `disable`) | `no bind with id 'X'` (1) |
| Two enabled binds on the same keys, without `--replace` | `conflict: SUPER + Q is already bound to a, b (use --replace)` (3). With `--replace` the other binds are disabled |
| Damaged file on a write | `skipped bind: ...; fix or remove PATH or run restore-all (nothing was changed)`, or `keybinds.json is invalid, using defaults; fix or remove ...` (1) |
| Shipped defaults broken | `shipped defaults are broken: ...` (1) |
| Bad arguments | `bbkos-keybinds: unknown command 'X' (try --help)`, `missing command`, `add needs --json FILE|-`, `set needs ID --json FILE|-`, `remove needs ID`, `enable needs ID [--replace]`, `disable needs ID`, `restore needs ID`, `status takes no arguments` (and the same for `restore-all`, `render`, `apply`), `unexpected option '--x'`, `--json needs FILE or -` (2) |
| `hyprctl` missing or failing | `hyprctl not found`, `hyprctl failed: ...`, `hyprctl reload failed` or the first line of its output (1) |
| Config errors after reload | `Hyprland config errors: <first line>` (1) |

Warnings (shown, allowed):

- `<id>: combo is commonly reserved by other software` for `ALT + F4`, `CTRL + ALT + Delete`, `CTRL + ALT + BackSpace`, `CTRL + ALT + Escape`.
- `<id>: locked bind on a non-media key runs from the lock screen` (a `locked` bind whose key does not start with `XF86`).
- On load, a bad row is skipped with `skipped bind: <message>`, a repeated id with `skipped bind: <id>: duplicate id`. A file that cannot be read, is not a JSON object or has no `binds` list falls back to the defaults with `keybinds.json is invalid, using defaults` (plus the error type when the file cannot be read or parsed).

## Apply flow and rollback

`render` loads and validates the binds, then writes only `hypr-binds.lua` (temp file and rename, so Hyprland never reads half a file). Any write command does the same and also writes `keybinds.json` (the old text goes to `keybinds.json.bak`), then reloads Hyprland: `hyprctl configerrors`, `hyprctl reload`, `hyprctl configerrors` again. `apply` re-renders and reloads without changing `keybinds.json`.

Rollback: if the render, a write or the reload fails (non-zero reload, or a config error that was not there before), `keybinds.json`, its `.bak` and `hypr-binds.lua` are put back exactly as they were (a file that did not exist is deleted), Hyprland is reloaded once more from the restored files (best effort), and the original error is reported first. If a restore itself fails, `warning: could not restore PATH: reason` is printed after the error line. The text is rendered before any file is touched, so a render error writes nothing.

## The Keybindings page

Keyboard › Shortcuts since 2026-10-28 (`qs ipc call settings page keyboard/shortcuts`). See `settings-app.md`. The page calls `KeybindStore`, which queues `bbkos-keybinds` runs; the IPC test hook is `qs ipc call keybinds status` (returns `{"status": ..., "binds": N}`).

## Known limits

- **Key capture cannot record combos Hyprland already binds.** A key that Hyprland itself binds (for example `Super+Q`) never reaches the settings window, so "Record" cannot capture it. Type such a combo through the CLI, or free it first.
- **Restore on the settings page works for shipped ids only.** The page offers Restore on rows whose id is in `status.shipped`; a bind you added yourself has nothing to restore to.
- **The editor's duplicate check is local; the CLI is authoritative.** The page compares the recorded combo with the binds it last read. The CLI checks again under the lock and answers with a conflict (exit 3) if the file changed meanwhile. The page lowercases every key name and folds Enter/Return, Prior/Page_Up and Next/Page_Down, so letter and F-key case already match; the only alias it does not fold is `comma` versus `,`, which the CLI folds.
- **Flags are checked for `mouse:` keys only.** The design spec (line 73) asks for the matching flag on mouse and switch triggers. The code enforces it only when the key starts with `mouse:` (`mouse trigger needs the mouse flag`); `mouse_down`, `mouse_up` and the `switch:` keys are not checked for flags.
- **Follow-up:** dispatch argument values are not type-checked in `validate_bind`; a bad value makes Hyprland drop the rest of the bind file. Since 2026-10-28 that is no longer silent: `hyprland.lua` shows a notification, `bbkos-theme apply` warns and `bbkos-check` fails with the error (`hypr-load-errors`, see `theme.md`). The type check itself is still open.
- Only the keys in the list above can be bound; any other name is rejected rather than sent to Hyprland.
- `bbkos-keybinds` does not check that the commands you type exist; only catalogue presets report missing tools.
- Not tested by the agents: pressing the binds on the real keyboard after a reload, and the page's clicks (see the owner checklist in `settings-app.md`).

## Rescue

`bbkos-keybinds restore-all` puts the shipped binds back and reloads. If the tool cannot run: delete `~/.config/bbkos/keybinds.json` and `~/.local/state/bbkos/theme/hypr-binds.lua`, run `bbkos-keybinds apply` (the defaults are used when the file is missing), or restore `keybinds.json.bak`.
