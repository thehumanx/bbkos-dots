# Sound page

Added 2026-10-24. Settings page **Sound** (`PageSound`, place `sound`, group Devices; sidebar index 18 until 2026-10-28; the music widget's width moved to Bar › Widgets). It has no settings of its own: it shows
and changes PipeWire's live state through `services/Audio.qml` (the same service as the bar's audio popup), and WirePlumber
remembers the choices. Reference: the Sound pages of GNOME, COSMIC and DankMaterialShell (Audio).

- **Output:** the default output device as chips (HDMI outputs, the speaker, Bluetooth devices when connected), its volume
  slider and Mute button.
- **Input:** the same for the default microphone.
- **Apps:** a volume slider and mute for every app that is playing (PipeWire nodes with `media.class` `Stream/Output/Audio`),
  named by `application.name`.

## Verified (2026-10-24)

The page on screen with live data: four outputs with Speaker selected, volume 0 % (the bar's value), two microphones with the
digital one selected at 100 %.

Later the same day, the Apps section on screen with a real stream: `pw-play` on a silent WAV listed as "pw-play" at 100 % with its own Mute (the
first attempt used an option `pw-play` does not have, which is why no stream appeared then; nothing was wrong with the page).

**Not verified:** a click on a device chip, a drag of a slider, Mute, and a Bluetooth device. The volume keys are separate (`wpctl`, `keybindings.md`).

## Not done

Alert sounds, a volume limit above 100 %, per-device volume for devices that are not the default, and the app list for recording apps.
