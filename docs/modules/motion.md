# Motion and depth (animations and shadows)

One set of curves and durations for the whole desktop, in QML (`Theme.qml`) and Hyprland (generated into
`hypr-theme.lua` by `bbkos-theme`), following Emil Kowalski's animation rules; plus the tinted shadow and hairline edge
under every floating card. Added 2026-10-23. Settings: `shell.reduceMotion`, `shell.popupShadow` (Appearance › Style, "Motion and
depth"); `windows.animations` still switches all Hyprland animations off.

## Reference

[emilkowalski/skills](https://github.com/emilkowalski/skills) (MIT), `skills/emil-design-eng/SKILL.md`, read 2026-10-23,
and his articles "Great animations" and "7 practical animation tips" (emilkowal.ski). The rules taken from it:

- **Decide by frequency.** Something used 100+ times a day from the keyboard gets no animation ("Raycast has no
  open/close animation"); occasional surfaces (popups, toasts) get a standard one.
- **Ease-out for anything that enters or answers a press**, ease-in-out for something moving across the screen, never
  ease-in. Built-in easings are too weak; his curves: ease-out `cubic-bezier(0.23, 1, 0.32, 1)`, ease-in-out
  `(0.77, 0, 0.175, 1)`, drawer (iOS sheet, from Ionic) `(0.32, 0.72, 0, 1)`.
- **Under 300 ms** for UI; popovers 125-200 ms, modals and drawers 200-500 ms. **Exit faster than enter.**
- **Never from nothing:** start at scale 0.95-0.97 with opacity 0. **Origin-aware:** a popover grows from its trigger
  (modals stay centred).
- **Press feedback:** scale 0.97 while pressed.
- **Interruptible:** transitions (QML `Behavior`) that can reverse mid-way, not fixed sequences.
- **Reduced motion** means fewer and gentler, not none: keep opacity and colour, drop movement.

## The tokens (`Theme.qml`)

| Token | Value | Use |
|---|---|---|
| `easeOut` | `[0.23, 1, 0.32, 1]` | enter, press, hover, colour (default) |
| `easeInOut` | `[0.77, 0, 0.175, 1]` | something moving across the screen (not used yet) |
| `easeDrawer` | `[0.32, 0.72, 0, 1]` | large surfaces: the overview zoom |
| `durFast` | 120 ms | hover, press, switch, colour |
| `durEnter` | 200 ms | a popup or card arriving |
| `durExit` | 140 ms | a popup leaving |
| `durLarge` | 300 ms | the overview opening (closing is 260) |
| `reduceMotion` | `shell.reduceMotion` | fades only |
| `shadow`, `shadowStrength`, `shadowPad` (32) | `shell.popupShadow` | the card shadow, see below |
| `cardEdge` | `fg` at 8 % | hairline edge of every floating card |

In QML a curve is `easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeOut`. No module writes its own
duration or curve; the exceptions are the wallpaper cross-fade (400 ms, rare and decorative), the timer's done flash, and
two short values in the overview (card glide 140 ms, stage slide 240 ms).

## What moves, and how

| Surface | Motion | Why |
|---|---|---|
| Bar popups (`Panels.qml`) | in: opacity 0 to 1 and scale 0.96 to 1 in 200 ms, from the point of the card nearest the clicked widget (the bar edge at the widget; the corner at the bar's end without a widget; top right for the notification sheet); out: the same backwards in 140 ms | occasional, mouse-opened; origin-aware |
| Pickers (launcher, clipboard, emoji) | none | keyboard, many times a day |
| Notification cards | in: 24 px from the screen edge and a fade, 240 ms | occasional; enters from where it lives |
| OSD | the compositor's layer fade (160 ms in, 120 ms out) | appears for a key press; the fade is short |
| Buttons and chips | scale 0.97 while pressed, 120 ms | press feedback |
| Toggles, sliders, hover colours, bar highlight | 120 ms ease-out | state change |
| Overview | 300 ms open, 260 ms close, drawer curve | large surface |
| Windows (Hyprland) | open: pop in from 90 % in 220 ms; close: 140 ms; move/resize 260 ms; fades 180/140 ms | |
| Workspaces (Hyprland) | slide, 260 ms, drawer curve (vertical for the special workspace) | matches the three-finger horizontal swipe |
| Layers (Hyprland) | fade 160 ms in, 120 ms out, except `bbkos-panel` and `bbkos-picker` (layer rule `bbkos-instant-layers`) | the popup animates its own card; pickers are instant |

**Popup exit:** `Panels.qml` keeps the last panel name in `root.shown` for `durExit + 20` ms after `PanelState.open`
goes empty, so the card can leave before the windows are destroyed. While `leaving`, the overlay has an empty input
region and no keyboard focus, so a click during the exit reaches what is below. Reopening during the exit reverses the
animation (`Behavior` on the card's progress). Test hook: `qs ipc call panel status` shows `shown` and `leaving`.

**Hyprland:** `render.render_motion` writes the curves `bbkOut` and `bbkDrawer` (the same points as `Theme.qml`) and one
`hl.animation` per leaf into `hypr-theme.lua`; Hyprland's speed is in tenths of a second. The stock curve and animation
block was removed from `hyprland.lua`; without a generated theme Hyprland's built-in defaults apply.
**Reduce motion** turns off `windowsIn`, `windowsOut` and `windowsMove` (the window fades stay) and makes workspaces
cross-fade instead of slide; in the shell it removes the popup's grow, the notification slide and the press scale.

## Shadow and edge

`components/CardShadow.qml` is one `RectangularShadow` (Qt 6.9+, a single shader quad: nothing redraws while the card is
still), blur 24, 6 px down, placed inside a card as its first child (z -1, so it follows the card's scale and opacity).
Its colour is `Theme.shadow`: a near-black of the wallpaper's hue (lightness 5 %, saturation at most 50 %), at
`popupShadow` x 0.85 alpha on a dark theme and x 0.4 on a light one. A window that is exactly its card's size (OSD,
notifications) is made `shadowPad` larger on each side and the card inset by it; the notification window takes the pad
out of its margin on the anchored sides (never below 0), so the cards stay where they were. Used by: bar popups, pickers,
notification cards, the OSD. Every one of them also has the `cardEdge` hairline, so a card never melts into a
background of the same shade (the owner's report: popups blended with the window under them).

## Verified (2026-10-23)

- `hyprctl animations` after `bbkos-theme apply` and `hyprctl reload`: `windowsIn` bbkOut 2.2 popin 90 %, `workspaces`
  bbkDrawer 2.6 slide; `hyprctl configerrors` empty. `shell.reduceMotion true` turned `windowsIn` off, `false` on again.
- Popups: `qs ipc call panel status` right after `close` shows `shown: wifi, leaving: true`, 50 ms later still leaving,
  after 300 ms `shown: ""` and the Wi-Fi scanner off.
- Screenshots: the Wi-Fi, audio and battery popups (bar top) with the hairline edge and the shadow visible over the
  wallpaper; a notification card in the top right with edge and shadow, at its old position; the brightness OSD with its
  shadow over a light window, its card at the old place (`hyprctl layers`: window 324x116 at y 961, card 32 px inside).
- Tests: `tests/theme` (motion block, both reduce-motion states, through Lua), `bbkos-qml-audit`, no new warnings in the
  shell log.

**Not verified:** the animation frames themselves (grim cannot catch a 200 ms animation reliably; judged by eye is the
owner's call), the press scale under a real click, bottom, left and right bars, the light theme, the new settings rows
on screen, and battery cost (expected nil while idle: nothing runs when no card moves).

## Known limits

- Reduce motion does not change the overview zoom (it is the overview's whole design); turn `windows.animations` off
  for a static desktop.
- A notification card leaves without its own animation; only the last one fades with the window.
- The shadow cannot be seen over a very dark window: it is a darker shade, by nature.
