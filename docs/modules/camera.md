# Camera (webcam picture controls)

Added 2026-10-21. Settings: **Capture and camera › Camera** (`PageCamera`, place `capture/camera`; sidebar index 12 until 2026-10-28), keys `camera.*` (`settings.py`
`CAMERA_DEFAULTS` and `RANGES`), the command `bbkos-camera` (`bbkos_theme/camera.py`) and the user service `bbkos-camera.service`.

## Why

Owner report: in video calls the face was dark and contrasty, unrecognisable, worse than on Windows 11 (a backlit scene: bright
window behind the owner). Findings on this machine (Luxvision `30c9:00ca`, `uvcvideo`):

- The hardware is not limiting: 1080p MJPG at 30 fps. Meet used 1280x720 MJPG at 30 fps. The second node pair (`/dev/video2`)
  is the infrared face-unlock camera: greyscale, 640x360. Both are listed as "Integrated Camera (V4L2)" in PipeWire.
- The camera does all its image processing inside itself and exposes only the standard UVC controls. Defaults were auto exposure
  (aperture priority), `exposure_dynamic_framerate` on (the frame rate drops in dim light and the picture smears), backlight
  compensation 1.
- Windows adds software processing on top (Windows Studio Effects on the Intel NPU: auto framing, eye contact, blur; Frame Server
  denoise). Linux has none of it, so only the camera's own controls remain.
- Measured by screenshots of the live Meet preview in the owner's backlit room: auto exposure with backlight compensation 2,
  dynamic framerate off, gamma and brightness defaults: face still dark (the meter follows the bright window). Brightness 150 and
  gamma 150: face and everything else washed out. **Manual exposure (`exposure_time_absolute` 400) lit the
  face properly**; the window behind blows out, which is the price (the sensor cannot hold both).
- The camera's region-of-interest control (`region_of_interest_rectangle`) reports a 1x1 range and refused writes: not usable to
  meter on the face.

Note: the unit of `exposure_time_absolute` is 0.1 ms, so 400 is 40 ms per frame, which limits the frame rate to about 25 fps at
that value (the camera reported 30 fps while measured; not measured at 400).

## Settings

| Key | Range | Control set |
|---|---|---|
| `exposure` | auto / manual | `auto_exposure` 3 / 1 |
| `exposureTime` | 3-1250 | `exposure_time_absolute` (manual only) |
| `backlight` | 0-2 | `backlight_compensation` |
| `brightness` 0-255, `contrast` 0-100, `saturation` 0-100, `sharpness` 0-7, `gamma` 90-150 | | same names |
| `whiteBalance` | auto / manual | `white_balance_automatic` |
| `whiteBalanceTemp` | 2800-6500 | `white_balance_temperature` (manual only) |
| `steadyFramerate` | bool | `exposure_dynamic_framerate` off when on |
| `powerLine` | off / 50hz / 60hz | `power_line_frequency` (50 Hz default; 60 Hz in the Americas) |

Defaults are the camera's own (automatic) except `steadyFramerate` on. The owner's live file has `exposure` manual, `exposureTime`
400. Each card has "Reset these" (the Reset page's Camera row until 2026-10-28).

## How it is applied

- `bbkos-theme set camera.X V` (the settings app does the same) writes `settings.json` and then runs `camera.apply`, which writes
  the controls with `v4l2-ctl`: modes first (exposure time is inactive and refuses a write while exposure is automatic), then values.
  A failure is a warning, no camera is silent.
- The colour camera is found in `/sys/class/video4linux`: first node of index 0 that offers MJPG or YUYV (not the IR camera).
- `bbkos-camera.service` (`bbkos-camera watch`, enabled, started with the graphical session) applies once at start and again 1.5 s
  after each open of the camera node (inotify), because an app or a replug can bring the camera defaults back. Its own writes are
  ignored for 3 s so it does not loop.
- `bbkos-camera status` prints the device and the current controls. Needs `v4l-utils` and `inotify-tools` (both installed).
- Settings changes show at once in an open call (UVC controls act on the running stream).

## Live preview (2026-10-26)

The Camera page starts with a **Live preview** switch. On, it runs `bbkos-camera preview`, which opens an mpv window (class
`bbkos-camera-preview`, 360x203, window rule in `hyprland.lua`: floating, no shadow) showing the camera in the 1280x720 MJPG mode
a call gets, mirrored like a call's self-view (`--vf=hflip`). The window is placed to the right of the settings window, top
aligned (`preview_layout`; since 2026-10-28 the settings window is tiled, so it is not moved and the preview sits in its top right corner; the rest of this paragraph describes a floating settings window); when the monitor has no room there (the laptop panel: 1500 logical px, settings 1120 wide) the settings
window moves left to make it, and is centred again when the preview ends. The tool runs for as long as the window is open: the
page stops it (SIGTERM) when it is left or closed, and it also ends when the mpv window is closed. Keyboard focus goes back to the
window that had it.

Only one program can stream the camera: when another holds it (`bbkos-camera users`, also used by the privacy indicator, lists
the holders) the switch stays off and the row says "the camera is in use by X (that program already shows your picture)". The
controls still apply to that program live, so the call itself is the preview then. The preview opening the camera makes
`bbkos-camera.service` apply the settings again 1.5 s later (harmless: same values).
The reference for the approach is the recorder's own mpv camera window (`capture.md`); a camera widget inside the page needs
`qt6-multimedia` (not installed, 10 MB), which the owner declined in favour of the window.

## Tune for this light (2026-10-26)

The Light section has a **Tune** button (`bbkos-camera tune`, about 7-15 s). It finds the manual exposure that gives the face
region `TUNE_TARGET` (105 of 255) brightness and saves it with `bbkos-theme set camera.exposure manual`, `camera.exposureTime N`
(and `camera.gamma` when it had to change it), so the sliders show the result and `camera.apply` sets it.

- **Meter.** ffmpeg streams 64x36 grey frames from the camera (1280x720 MJPG, 10 fps); a reader thread keeps the newest, because
  the pipe holds a backlog of old frames. After each exposure change it waits 0.5 s, then averages the frames of the next 0.6 s.
  `bbkos-camera.service` is stopped meanwhile (it puts the saved values back each time the camera opens) and always started again.
- **Brightness measure** (`frame_brightness`): the 40th percentile of the lower middle (the middle 40 % across, from a third to
  92 % down). The first version used the mean of the centre and lit the ceiling and the window, not the face: in the owner's backlit
  room the face read 48, 97 and 117 at exposures 295, 600 and 900 while the centre's mean read 133, 189 and 213. The percentile
  tracked the face within about 10 on those three. It is a heuristic with no face detection: a dark shirt or doorway filling the
  lower middle pulls it down, and it assumes you sit in the middle, where a call puts you.
- **Search.** Bisection on a log scale of the exposure time over 3-400 (0.1 ms; 400 keeps the frame rate near 25 fps), 9 meter
  readings at most (`search_exposure`). If even 400 is too dark, gamma goes up in steps of 10 to 150, then exposure may go up to 800
  (frame rate about 12; the result then says `slowFrames`). `tooDark` is reported when 800 is still not enough: the room needs light on
  the face. A sensor-based "ambient light" source was not available: this machine has no iio light sensor.
- **Preview.** The camera has to be free, so a running preview is stopped and comes back after the tune. Another program holding the
  camera makes the tune refuse with its name.
- A bright window behind you stays blown out: the sensor cannot hold both, and the controls are all there is (see Why).

## Verified / not verified

Verified 2026-10-21: control writes with the camera streaming in Meet (screenshots, above); `bbkos-theme set camera.exposure manual`
reaches the camera; the watcher restored a wrong `gamma` after an open (about 6 s); the Camera page renders (screenshot); 7 unit tests.
Verified 2026-10-26 (tune): on the owner's backlit room the first version took 12.5 s and chose exposure 295 (face at 73 of 255,
dark in a captured frame); with the percentile measure it chose exposure 400 and gamma 148 in 6.5 s and a captured frame shows the
face lit, the window still white; 4 new unit tests (measure, search, the limits, number of readings); the Camera page renders with
the Tune button (screenshot). Not verified: the button by mouse, the preview-stop-and-resume path of the page, other lighting
(a dim room reaching the slow exposure step, a bright room reaching the minimum), another person's skin tone or seat.
Verified 2026-10-26 (preview): `bbkos-camera preview` with the Camera page open on the HDMI monitor: the preview window showed the owner
(screenshot), the settings window moved from x 470 to 420 and the preview sat at x 1550, right of it; stopping the tool closed mpv,
released the camera and put the settings window back at 470; with Vivaldi holding the camera the tool refused with the message above;
unit tests for the layout, the mpv command and the holders list. Not verified: the switch by mouse (the process was started from
the shell), the laptop panel layout on screen, a window closed by hand while the page stays open, Quickshell killed while previewing
(mpv would stay open).
Not verified earlier: the other sliders on the page by mouse; that the controls survive a reboot or USB suspend without the service;
Zoom or Teams (only Meet seen); the face with `exposureTime` other than 400; frame rate at 400.

## Not done / nice to have

- A virtual camera ("bbkOS Camera", v4l2loopback + ffmpeg or OBS) for 1080p, denoise, sharpen, tone mapping and background blur:
  needs root packages and costs CPU. The control-based fix was tried first.
- A backlit-room one-click preset.
- Automatic switching of exposure by ambient light as it changes (the button tunes once).
- If manual exposure is not enough: a virtual camera, as above (the owner said the controls suffice for now, 2026-10-21).
