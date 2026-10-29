# Window behaviour

Added 2026-10-24. Settings: **Windows › Behaviour** (`PageBehavior`, place `windows/behaviour`; the three cursor rows are on Mouse and touchpad › Mouse and cursor; the Window behaviour page, sidebar index 20, until 2026-10-28), keys `behavior.*` and
`windows.animationSpeed` (`settings.py`). Reference: COSMIC's Window management and Workspaces pages, GNOME's Multitasking page and
the option meanings in the Hyprland wiki's config reference (the values below are taken from there).

| Key | Default | Hyprland option |
|---|---|---|
| `behavior.followMouse` | `hover` | `input.follow_mouse`: `click` 0 (the mouse never changes focus), `hover` 1 (focus follows the mouse), `detached` 2 (the cursor's window and the keyboard's window differ until you click) |
| `behavior.focusOnActivate` | on | `misc.focus_on_activate`: an app that asks for focus gets it (the owner's choice, for OAuth hand-offs through the browser; the trade-off is that a background app could take typing focus) |
| `behavior.workspaceBackAndForth` | off | `binds.workspace_back_and_forth` |
| `behavior.hideCursorWhenTyping` | off | `cursor.hide_on_key_press` |
| `behavior.cursorHideAfter` | 0 | `cursor.inactive_timeout`, seconds 0-20 (0 never) |
| `behavior.cursorWarps` | on | `cursor.no_warps` is the opposite; off keeps keys and clicks from moving the cursor |
| `behavior.snap`, `snapGap` | off, 10 | `general.snap.enabled`, and `window_gap` and `monitor_gap` (0-100, step 5) |
| `windows.animationSpeed` | 1.0 | not a Hyprland option: every `hl.animation` speed (tenths of a second) is divided by it, so 2.0 is twice as quick; 1.0 renders the old numbers |

`bbkos-theme` renders them into the generated `hypr-theme.lua` (`render_behavior`, `render_input_extra`, the `snap` entry and
`focus_on_activate` in `render_hypr_lua`, `render_motion(reduce, factor)`). The static `hyprland.lua` no longer sets
`follow_mouse` or `focus_on_activate` (it is loaded after `hypr-theme.lua` and would override the page). The animation speed
changes the compositor's window and workspace animations only; the shell's own (`Theme.dur*`) are unchanged. Stage mode's rail
click still switches `cursor.no_warps` for one focus and restores what it read, so it respects this setting.

## Verified (2026-10-24)

6 tests in `tests/theme/test_behavior.py`, the `hypr-theme.lua` snapshot (diff reviewed: the snap line, `focus_on_activate`, the
binds and cursor blocks, `follow_mouse`), the whole theme suite (473). Live with `hyprctl getoption` after each `bbkos-theme set`:
follow_mouse 1 to 0 and back, snap on with gap 20 and back, `inactive_timeout` 5 and back, `no_warps` true and back; `hyprctl
configerrors` empty each time. Defaults read back as before (1, true, false, false, false).

**Not verified:** a real focus change with the mouse in each mode, the cursor hiding, snapping a dragged floating window, the
animation speed by eye (only the generated numbers were tested), the page on screen.

## Not done

Window rules (always float an app, a default workspace for an app), hot corners (Hyprland has none built in; the overview has its
own gestures), per-monitor workspace behaviour.
