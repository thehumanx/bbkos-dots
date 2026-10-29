# Startup apps

Added 2026-10-24. Settings: **Apps › Startup** (`PageStartup`, place `apps/startup`; the Startup apps page, sidebar index 19, until 2026-10-28), the command `bbkos-autostart`
(`bbkos_theme/autostart.py`). Reference: COSMIC's Startup applications page and GNOME's, which use the same standard.

## What it does

Apps in the freedesktop autostart folder `~/.config/autostart` start at login: the session runs under uwsm and systemd, and
`systemd-xdg-autostart-generator` turns each entry into a unit under `xdg-desktop-autostart.target` (active here). The page lists the
user entries and the system ones (`/etc/xdg/autostart`: the keyring and accessibility services today), switches one off or on,
adds an installed app and removes one the owner added. Changes take effect at the next login.

- `bbkos-autostart status` prints JSON: `entries` (id, name, exec, icon, enabled, source `user` / `system` / `override`) and
  `apps` (installed apps that can still be added; hidden ones, with NoDisplay, are not offered).
- `add ID` copies the installed app's desktop file into `~/.config/autostart`. `disable ID` sets `Hidden=true` in the user file;
  for a system entry it writes a user file of the same name that only says `Hidden=true` (the XDG way to override). `enable ID`
  removes `Hidden`, or deletes that override file. `remove ID` deletes a user entry; a system entry cannot be removed.
- IDs must look like desktop file names (`[A-Za-z0-9._@+-]+.desktop`, no slashes), and writes are atomic.

## Verified (2026-10-24)

8 tests in `tests/theme/test_autostart.py` (the listing, add, disable and enable, the system override, remove, bad ids, the `Hidden`
key inside the main group only, the command line) in a temporary home, and the whole theme suite (467). Live from the shell: the
status of the three system entries and 29 addable apps; add, disable (`Hidden=true`), enable, remove of Thunar's bulk rename and
the autostart folder removed again (it did not exist before); an unknown id refused with rc 1.

**Not verified:** the page on screen (the screen was in use when I got to it), a clicked toggle, Remove or Add, and an entry really
starting at the next login.

## Not done

Start delays, a command that is not an installed app, and per-entry environment: the page only handles desktop entries.
