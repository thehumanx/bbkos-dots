# About and updates

Added 2026-10-24. Settings: **About and system › About and updates** (`PageAbout`, place `about/about`; sidebar index 21 until 2026-10-28), the command `bbkos-about`
(`bbkos_theme/about.py`). Reference: COSMIC's About page and DankMaterialShell's About and SoftwareUpdates tabs.

- **Updates:** the pending count is the bar widget's (`services/Updates.qml`, `checkupdates`, no root, repository packages only),
  with Check now (`Updates.refresh()`), Update (the same floating terminal as the widget: `bbkos-tui bbkos-update`, which stops at
  yay's prompts) and the time of the last pacman transaction (`/var/log/pacman.log`, the last `transaction started`).
- **This computer:** read-only rows from `bbkos-about` (JSON): computer, model code and firmware (DMI), processor, memory, disk use of
  `/`, battery health (full over design capacity) and cycle count, system (`/etc/os-release`), kernel, Hyprland and Quickshell
  versions, the bbkOS commit and date (`git log -1` in `~/.local/share/bbkos/repo`) and the uptime. A row whose value is not available is left out.
- Snapshots are not listed: `snapper` needs root; see `snapshots.md`.

Verified (2026-10-24): 5 tests in `tests/theme/test_about_network.py` (the os, cpu and memory readers, uptime text, battery,
last update, the shape of the output) and the page on screen with live values (11 updates waiting, last update 10:33, the rows).
Not verified: a click on Check now or Update, a machine without a battery.
