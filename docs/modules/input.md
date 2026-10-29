# Keyboard, mouse and cursor

Added 2026-10-24. Settings: **Keyboard › Typing** (`PageKeyboard`) and **Mouse and touchpad › Mouse and cursor** (`PageMouse`) since 2026-10-28 (one Keyboard and mouse page, `PageKeyboardMouse`, sidebar index 16, before), keys `keyboard.*`,
`mouse.*` and `cursor.*` (`settings.py`). The touchpad has its own page (`touchpad.md`). Reference: the Keyboard, Mouse and
Appearance pages of COSMIC, GNOME and DankMaterialShell.

## What it sets

| Key | Default | Range / values |
|---|---|---|
| `keyboard.layout` | `us` | xkb names, lowercase, comma separated (`us,np`); the first is active. A value that is not that shape is refused |
| `keyboard.variant` | empty | xkb variants, one per layout, comma separated |
| `keyboard.options` | `none` | `none`, `caps:escape`, `ctrl:nocaps`, `ctrl:swapcaps` (presets only, never free text) |
| `keyboard.repeatRate` / `repeatDelay` | 25 / 600 | 10-60 keys a second / 150-1000 ms step 50 |
| `keyboard.numlock` | off | Num Lock on at login |
| `mouse.sensitivity` | 0.0 | -1.0 to 1.0 (Hyprland's `input.sensitivity`, which also moves the touchpad) |
| `mouse.accelProfile` | `default` | `default` (left out, libinput decides), `flat`, `adaptive` |
| `mouse.naturalScroll`, `leftHanded` | off | `input.natural_scroll` (mice; the touchpad has its own), `input.left_handed` |
| `cursor.theme` / `cursor.size` | `Afterglow-cursors` / 24 | an icon theme name (letters, digits, `._-`) / 16-48 step 2 |

## How it works

- `render.render_input_extra` adds the keyboard and mouse lines to the `input` block of the generated `hypr-theme.lua`, and
  `render.render_cursor_env` adds `hl.env` lines (`XCURSOR_THEME/SIZE`, `HYPRCURSOR_THEME/SIZE`) for apps started later.
  Every value was validated first, so none can break out of its Lua string (a test tries one that would).
- `hypr-theme.lua` is loaded before the static `input` block of `hyprland.lua`, so the static block no longer sets
  `kb_layout`, `kb_variant`, `kb_options` or `sensitivity` (a later key would override the generated one); it keeps
  `kb_model`, `kb_rules` and `follow_mouse`.
- `reload.reload_cursor` changes what is already running: `hyprctl setcursor THEME SIZE` and gsettings (`cursor-theme`,
  `cursor-size`) for GTK. It runs only when the choice differs from `cursor-active` in the state directory, and never without a
  Hyprland session or when HOME is not the real home (a test or dry run).
- The page applies each change at once (a full Hyprland reload, as every look setting).

## Verified (2026-10-24)

7 tests in `tests/theme/test_input_settings.py` (defaults render the old values, choices, an injection attempt, ranges, the
cursor reload once and again on change, never from a temporary HOME), the snapshot of `hypr-theme.lua` updated for the new lines
(the diff was only the nine input lines and four env lines), the whole theme suite (449). Live: `hyprctl getoption` showed
the generated values after a reload; `keyboard.repeatRate 40` gave `input:repeat_rate 40` and back to 25; `cursor.size 30` gave
`hyprctl setcursor`, gsettings 30 and the marker, back to 24; a bad layout was refused (rc 1, "invalid string"); the page on screen.

**Not verified:** a second keyboard layout actually switching (needs a group-switch option, not offered here), the Caps Lock
remaps with a real key press, left-handed and flat acceleration on a real mouse (none attached), the cursor theme chooser (a text
field: only Afterglow is installed besides Adwaita), the cursor looking right in Xwayland apps, a reboot.

## Not done

Per-device settings (`hl.device`), a group-switch key for several layouts, key remaps beyond Caps Lock, a cursor theme list.
