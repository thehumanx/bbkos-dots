# Privacy indicator

Added 2026-10-24. Settings page **Privacy and wellbeing** (`PagePrivacy`, place `privacy`; the Privacy page, sidebar index 28, until 2026-10-28), keys `privacy.*` (`settings.py`), the bar
widget `privacy` (`modules/bar/PrivacyWidget.qml`, section end, after the recording indicator in the default layout) and the service
`services/Privacy.qml`. Reference: DankMaterialShell's Privacy bar widget and the indicators of GNOME and COSMIC.

## Dictation (2026-10-29)

While Voxtype records (`dictation.md`) its input stream (`PipeWire ALSA [voxtype-vulkan]`) counts as the microphone and the glyph shows, then clears when the recording stops. Checked through `qs ipc call privacy status`; the glyph itself on screen was not looked at. This is why dictation has no bar widget of its own.

## What it shows

A glyph in the warning colour while an app is using the microphone, the camera or a screen share, and nothing at all (no space in the bar)
otherwise. It reads PipeWire's streams, as the audio popup reads devices:

| Glyph | Counts | PipeWire stream |
|---|---|---|
| microphone | an app has an open input stream | `Stream/Input/Audio` |
| camera | an app uses the camera, through PipeWire (portal) or by opening the device itself | `Stream/Input/Video` with `media.role` = `Camera`, or a program holding `/dev/video*` open (`bbkos-camera-users`) |
| screen | the compositor sends the screen to an app | `Stream/Output/Video` |

`privacy.mic`, `camera` and `screen` (default on) choose which of the three count. The page also lists what is in use right now and by
which app. The widget is placed on Bar › Layout like any other (the owner's saved layout got `end:privacy` after the settings button the
first time a setting was saved; move it where you like). `bbkos-record`'s own indicator is separate (it records through wf-recorder, not PipeWire).

Camera, second source (2026-10-26): Vivaldi, the web apps made from it, Electron apps and most call clients open `/dev/video*` themselves and never make a PipeWire camera stream (seen in a Google Meet call: `fuser /dev/video0` named Vivaldi's `video_capture.mojom.VideoCaptureService`, `pw-dump` had no `Stream/Input/Video`), so a PipeWire-only indicator missed them. `Privacy.qml` runs `inotifywait -m -e open,close /dev/video*` (kernel open and close events, no polling; it follows the udevadm monitor pattern of `Battery.qml`); each event, after 150 ms, runs `bbkos-camera-users`, which scans `/proc/*/fd` of the user's processes for `/dev/video*` and prints the program names as JSON (PipeWire and WirePlumber are left out: they probe the devices and their camera streams are already counted). The names join the PipeWire camera list. A program that holds the device open without streaming counts too.

Limits: Quickshell does not expose a stream's state, so an app that keeps an idle microphone stream open counts as using it; the PipeWire screen rule is the documented class and has not been seen on this machine; the device watch is set up when the shell starts, so a camera plugged in later (the built-in one is always there) is not watched until the shell restarts; an app that records the screen or microphone without PipeWire is not seen.

## Verified (2026-10-24)

The whole suites (505 theme tests). Live: `pw-record` (a microphone stream, state running) made `qs ipc call privacy status` report
`mic: true` with the app name, and an amber microphone glyph appeared at the right end of the bar (screenshot); `privacy.mic false` removed the glyph
while the stream still ran; `true` brought it back. A `pw-play` stream appeared as `Stream/Output/Audio` and is listed in the Sound page's Apps section
(screenshot). A first run showed nothing because the shell had hot-reloaded `Bar.qml` before `PrivacyWidget.qml` existed ("PrivacyWidget is not a type");
a service restart fixed it, so after adding a widget file, restart the shell.

**Camera by device (2026-10-26):** `qs ipc call privacy status` listed `vivaldi-bin` while a Meet call held `/dev/video0` (its process had 4 mappings of the device: streaming); a shell holding `/dev/video2` for 3 s appeared as `sleep` and was gone a second after it closed; a `grim` screenshot of the bar shows both the microphone and the camera glyph. A first restart failed (`Timer is not a type`: the singleton lacked `import QtQuick`), fixed.

**Not verified:** a screen-share stream (the screen row), the camera in an app other than Vivaldi (WhatsApp is a Vivaldi web app, so the same process), a camera plugged in after login, an app with an idle microphone stream, the Privacy page on screen,
the other bar positions and pill modes with the widget shown.

## Not done

A click action on the glyph (for example to open the sound page), a warning when something starts, and a log of which apps used the microphone.
