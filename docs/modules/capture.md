# Capture: screenshots, OCR and screen recording

Added 2026-10-21. Screenshots, the annotation editor and OCR come from **omasnap**; screen recording is **`bbkos-record`**, a small
wrapper around `gpu-screen-recorder`. Both follow the Omarchy setup (they use the same programs), without Omarchy's scripts.
Settings: the `capture` section of `settings.json`, edited on the **Capture** page of the settings app (`settings-app.md`).

## Why these

The owner's requirements: crisp screenshots of a region, a window or the whole screen; screen recording with or without sound,
microphone and camera; editing a screenshot by clicking its notification; saving by default switchable; OCR. Chosen over
`grim` + `satty` (no OCR) and Flameshot / Spectacle (not evaluated). The research and the options considered are in the
conversation of 2026-10-21; the facts that matter are below.

**Crispness is the panel's, not the tool's.** The panel is 1920x1200 natively (EDID: one mode, 302 x 189 mm, about 161 PPI);
a 14-inch MacBook Pro is about 254 PPI and its screenshots have twice the pixel dimensions. `grim` and omasnap both write the
screen's pixels 1:1 (measured: a `grim` PNG is 1920x1200 with hard pixel edges; omasnap's full-screen export is the same size and
identical to `grim` on the pixels that did not change between the captures, 99.86% of 1.79 million). No tool adds detail the
panel does not draw. At a fractional scale (1.25, 1.5) XWayland apps are upscaled by the compositor and look soft in any
screenshot (`xwayland:force_zero_scaling` is false); the scale is 1.0 today. Not built: a 2x capture on a headless output.

## Screenshots: omasnap

- **Install:** `scripts/install-omasnap.sh` builds a pinned commit (6771b19, 2026-10-03) from `github.com/omacom/omasnap` into
  `~/.local` (binary `~/.local/bin/omasnap`, version string 1.21.0). After you install the packages yourself:
  `sudo pacman -S --needed cmake ninja layer-shell-qt tesseract-data-eng`. Not the v1.21.0 tag: it predates the `autosave` option.
  Its own smoke test (`make smoke`) stops with exit 130 at a UI-font check on this machine (after passing the capture, editor and
  OCR checks before it); the editor was looked at on screen and its fonts are fine. Qt6, tesseract; nothing stays running.
- **Key** (Keyboard › Shortcuts; preset `screenshot-region` in `keybind_actions.py`): `Super+Shift+S` = `omasnap` (smart selector: drag
  a region, click a window, click empty space for the monitor). The key toggles: a second press closes the overlay. There are no
  Print-key binds (removed 2026-10-21 at the owner's request; the laptop's Print key sends Super+Shift+S anyway). A window or the
  whole screen is chosen by clicking in the selector; `omasnap --capture-window` and `--capture-fullscreen` still work from a terminal.
- **After a capture:** the image is copied, saved (when autosave is on) and a floating preview appears for 10 s with Edit, Copy,
  Pin and drag-to-another-app. A notification with a thumbnail also appears; **clicking it opens the editor** (see below).
- **OCR:** in the editor `O` copies all text in the image, or use the toolbar's drag-region OCR. Tesseract with `tesseract-data-eng`
  (installed 2026-10-21; before that only Afrikaans and orientation data were present). Other languages: install the data and set
  `OMASNAP_OCR_LANGS` (not wired to a setting). A comparison on two screenshots of the settings window: Tesseract 85-91%
  of the visible words (96% / 91% on a 2x upscale), RapidOCR 98% / 100% but 2-3x slower and a 382 MB venv. Tesseract chosen.
- **Settings** (`capture.*`): `autosave` (default true; false = copied only, still saveable from the preview or editor),
  `directory` (`~/Pictures/Screenshots`; `~/...` or absolute), `editorMode` (`overlay` or `window`). `bbkos-theme apply` writes
  them into `~/.config/omasnap/omasnap.conf` (INI, generated, only when `settings.json` is the real
  `~/.config/bbkos/settings.json`; `BBKOS_OMASNAP_CONF` overrides the path). omasnap reads it when it starts.
- **Hyprland:** layer rule `bbkos-omasnap` (`no_anim`, hyprland.lua) so the overlay appears without a fade. Do not add
  `no_screen_share`: Hyprland blacks out the whole layer. omasnap floats and pins its own preview windows with Lua dispatchers.
- **Window screenshots** are a crop of the monitor frame: a window above it stays visible in the crop.
- Verified 2026-10-21: `omasnap --capture-fullscreen` copies a PNG to the clipboard and (autosave on) writes
  `screenshot-DATE_TIME-APP.png` to the configured folder; with autosave off nothing is written; `--save` writes to the
  configured folder; the editor opens on a file; the generated config follows `bbkos-theme set capture.*`.
  **Not verified:** dragging a region or clicking a window in the selector, real key presses, OCR output (no way to click),
  the clipboard image pasted into another app, a second monitor, a scaled (1.25 or 1.5) display.
- `bbkos-screenshot {region|full}` (grim + slurp) still exists and works; nothing binds it any more.

### Notification clicks

omasnap sends its notifications by running Omarchy's `omarchy-notification-send`, which bbkOS does not have. Shim
`dotfiles/bin/.local/bin/omarchy-notification-send` (stow package `bin`) understands the options omasnap uses
(`-g`, `--app-name`, `-t`, `-u`, `SUMMARY [BODY]`, `--image FILE`, `--exec PROGRAM ARG...`) and calls `notify-send`; for `--exec`
it adds a `default` action and `--wait`, and runs the command when the server reports the click.
The notification server (`services/Notifs.qml`) now has `actionsSupported` and `imageSupported` true; a popup click runs the
sender's `default` action (`Notifs.invokeDefault`) before it dismisses, and the popup card shows the image (a thumbnail at 2x
width). Test hook: `qs ipc call notifications invoke NOTIF_ID`. Verified: the shim notification shows with its thumbnail, and the
hook runs the `--exec` command (a marker file appeared). Not verified: a real mouse click on the popup, a click on the history entry
(history entries keep no actions).

## Screen recording: bbkos-record

`bbkos-record start|stop|toggle|status|camera` (`dotfiles/bin/.local/bin/bbkos-record`, code `bbkos_theme/record.py`).
- **Recorder:** `gpu-screen-recorder` 6.1.4 (installed before; `gsr-kms-server` has `cap_sys_admin`). `-k auto -f 60 -fm cfr -q
  very_high -fallback-cpu-encoding yes`, MP4. Intel VA-API H.264 and HEVC encode are available (`vainfo`). Region = `-w region
  -region WxH+X+Y` from `slurp -d` (logical pixels, the same space), whole screen = the focused monitor's name.
- **Sound:** none, desktop (`default_output`), microphone (`default_input`) or both, mixed into one AAC track (separate tracks
  play one at a time in most players).
- **Camera:** a floating, pinned mpv window (`class bbkos-camera`, window rule in hyprland.lua) in the bottom-right of the recorded
  area, so it is part of the video. 4:3 from the camera's native 640x480, small / medium / large = 240x180 / 320x240 / 480x360.
  **Mirrored by default** (`capture.recordCameraMirror`, mpv `--vf=hflip`; the recording shows it mirrored too).
  **Movable while recording:** drag the video itself, Super+drag, or `bbkos-record camera [next|tl|tr|bl|br]` (the panel's
  Move camera button) to jump to the next corner (br, bl, tl, tr). Keyboard focus is given back to the window that had it when
  the camera opens. `float` and `pin` are toggles in Hyprland: the tool sends them only when the rule did not apply.
- **Process model:** `start` picks the area, then forks a detached supervisor that runs the recorder, waits for its file, writes
  `$XDG_RUNTIME_DIR/bbkos-record/state.json`, and on exit (any reason) removes it, closes the camera, makes a thumbnail with
  ffmpeg and notifies "Recording saved - Click to play" (the click runs `xdg-open FILE`). `stop` sends SIGINT, the only way
  `gpu-screen-recorder` finalises the file. The recorder is identified by `/proc/PID/exe`, so a stale state never counts.
  The log is `gsr.log` beside the state file. Not done (Omarchy does): trimming the first 0.1 s, loudness normalisation.
- **Shell:** `services/Record.qml` mirrors `bbkos-record status` (event driven: the tool calls `qs ipc call record changed`; a
  1 s timer runs only while recording). `modules/bar/RecordWidget.qml` is a red dot and the elapsed time while recording
  (default end section, before the tray; click = stop). `modules/panels/RecordPanel.qml` (PanelState `record`): what, sound,
  camera, Start; while recording the time, Stop and Move camera. The dot is a fixed red (`#ff4d4d`), because `Theme.crit` is
  near-white at contrast 1.0.
- **Key:** `Super+Shift+R` (preset `record-menu`): stops a running recording, otherwise opens the options panel (as the old Omarchy
  key did). Earlier the same day Alt+Print, Ctrl+Alt+Print and Super+Print did this; removed at the owner's request.
  `bbkos-record toggle [--screen]` is still available from a terminal.
- **Settings** (`capture.record*`): `recordArea` (region/screen), `recordAudio`, `recordCamera`, `recordCameraSize`,
  `recordCameraMirror`, `recordQuality` (medium/high/very_high/ultra), `recordFps` (30 or 60), `recordDirectory` (`~/Videos`).
- Test hook: `BBKOS_RECORD_REGION="X,Y WxH"` replaces the `slurp` picker.
- **Verified 2026-10-21:** whole screen 1920x1200 H.264 at a constant 60 fps; a region 900x560 with desktop and microphone audio
  (AAC 48 kHz stereo) and the camera; the camera window floating, pinned, at the expected corner (656, 396) and moving through
  all four corners during a recording with `camera next` / `tl`; focus returned to the previous window; the camera is part of the
  video (frame checked); mirror on versus off differ by a left-right flip (PSNR 23.6 dB after flipping versus 10.9 dB);
  the bar indicator and the panel while recording and after stopping; the saved notification. Test recordings were deleted.
  **Not verified:** a real mouse drag of the camera window (and that mpv lets the drag start), picking a region with the mouse,
  recording a window on a second monitor, HEVC/AV1 choices, very long recordings, battery cost of recording, the notification
  click on the saved recording (the same shim path as screenshots), a scaled display.

## OCR from a region: bbkos-ocr (`Super+Shift+T`)

`bbkos-ocr`: `slurp` picks a region, `grim` captures it, `ffmpeg` upscales 2x (Lanczos), `tesseract --oem 1 --psm 6` reads it, `wl-copy` copies the text and a notification says so. `BBKOS_OCR_LANGS` sets the languages (default `eng`); `BBKOS_OCR_REGION="X,Y WxH"` skips the picker (test hook). Verified with that hook on a region of the terminal: the text on screen came back in the clipboard. Not verified: the interactive `slurp` selection.

## Nice to have

- **2x ("retina") window screenshots.** Asked 2026-10-21, tested, not built. The panel is 1x, so a real 2x image needs the app
  to redraw at 2x: create a headless Hyprland output (`hyprctl output create headless NAME`), set it with `hl.monitor({ output,
  mode = "3840x2400@60", position, scale = 2 })` (logical size stays 1920x1200), put the window on it, `grim -o NAME` gives a
  3840x2400 PNG, then move the window back and `hyprctl output remove NAME`. Measured with a throwaway kitty on the virtual
  output: the text was visibly smoother than the 1x capture (real curves and thin strokes, not repeated pixels). Findings for a
  future tool:
  - Adding the output moved the laptop screen from x=0 to x=3840 (positions reshuffle): pin positions, or `hyprctl reload` after.
  - A tool would be `bbkos-retina-shot`: record the window's workspace, geometry and floating state; move it over; wait for the
    redraw; `grim -o NAME -g` its rectangle; move it back; remove the output; then the omasnap-style save, copy and clickable
    notification.
  - Window shots only (not regions across windows or the whole screen). The window vanishes for about a second; in dwindle the
    other windows reflow and the restore may not give back the same split; floating windows and stage mode are safe.
  - Wayland-native apps only: XWayland apps stay upscaled and soft. Only a Wayland-native terminal was tested, not the browser,
    and moving and restoring a real window was not tried. The bar and wallpaper surfaces appear on the virtual output for a moment.
  - GPU cost of a 3840x2400 render for about a second was not measured. The 2x file looks crisp zoomed or on a high-density
    screen; at 100% on this panel it looks about the same.
  - Alternatives: AI upscaling at edit time (invents detail: not for text that must be accurate) or an external 4K monitor at
    scale 2 (real 2x screenshots of everything, no tricks).
- **Recording:** trim the first 0.1 s and normalise loudness (Omarchy does both), a window-only recording, a replay buffer
  (`gpu-screen-recorder -r`).
- **Screenshots:** a setting for OCR languages (`OMASNAP_OCR_LANGS` is an environment variable only), a clean per-window capture
  (omasnap crops the monitor frame).

## Files

| File | Role |
|---|---|
| `scripts/build-emoji-data.py`, `modules/emoji/` | emoji picker (`emoji.md`) |
| `scripts/install-omasnap.sh` | build and install omasnap at the pinned commit |
| `dotfiles/bin/.local/bin/omarchy-notification-send` | notify-send shim with click actions |
| `dotfiles/bin/.local/bin/bbkos-record`, `lib/bbkos_theme/record.py` | recorder tool |
| `lib/bbkos_theme/{settings,render,apply}.py` | `capture.*` keys, `render_omasnap_conf`, the config write |
| `services/Record.qml`, `modules/record/RecordIpc.qml`, `modules/bar/RecordWidget.qml`, `modules/panels/RecordPanel.qml` | shell side |
| `modules/settings/PageCapture.qml` | Capture and camera › Screenshots and recording (place `capture/capture`; the Capture page, index 11, until 2026-10-28) |
| `tests/theme/test_record.py` and the settings, render, apply, keybinds tests | unit tests |
