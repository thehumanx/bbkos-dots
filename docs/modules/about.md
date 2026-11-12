# About and updates

Added 2026-10-24; a profile card (picture, name) and a Signed in card added 2026-11-11. Settings: **About and system › About and updates** (`PageAbout`, place `about/about`; sidebar index 21 until 2026-10-28), the command `bbkos-about`
(`bbkos_theme/about.py`). Reference: COSMIC's About page and DankMaterialShell's About and SoftwareUpdates tabs.

- **Profile (2026-11-11):** a card at the top: a round picture, the name, `user@host`, Choose picture and Use the default. The picture
  is the lock screen's (`lock.avatar`, `bbkos-theme avatar set`; the shipped one until you pick), so there is one picture for both; the
  name is the new setting `profile.name` (`""` = the account's full name from `/etc/passwd`, else the user name; no root, no `chfn`).
  Under it: login shell, groups and session, from `bbkos-about` (`identity`). Reference: COSMIC's and DankMaterialShell's user card.
- **Signed in (2026-11-11):** a read-only list of who the command-line tools are signed in as, from local files only (no network, no
  sign-in or sign-out, no token kept): Git (`git config --global` name and email), GitHub (the `user:` line of `~/.config/gh/hosts.yml`;
  `gh auth status` is not run, it calls the network) and Claude (only whether `~/.claude/.credentials.json` exists; the file is never
  opened). A tool that is not set up is left out; with none, the card is hidden. Nothing syncs here, so this is a status list, not
  the account sync of Windows or macOS (`accounts` in the JSON).
- **Updates:** the pending count is the bar widget's (`services/Updates.qml`, `checkupdates`, no root, repository packages only),
  with Check now (`Updates.refresh()`), Update (the same floating terminal as the widget: `bbkos-tui bbkos-update`, which stops at
  yay's prompts) and the time of the last pacman transaction (`/var/log/pacman.log`, the last `transaction started`).
- **This computer:** read-only rows from `bbkos-about` (JSON): computer, model code and firmware (DMI), processor, memory, disk use of
  `/`, battery health (full over design capacity) and cycle count, system (`/etc/os-release`), kernel, Hyprland and Quickshell
  versions, the bbkOS commit and date (`git log -1` in `~/.local/share/bbkos/repo`) and the uptime. A row whose value is not available is left out.
- Snapshots are not listed: `snapper` needs root; see `snapshots.md`.

Verified (2026-10-24): 5 tests in `tests/theme/test_about_network.py` (the os, cpu and memory readers, uptime text, battery,
last update, the shape of the output) and the page on screen with live values (11 updates waiting, last update 10:33, the rows).

Verified (2026-11-11, profile and signed in): 3 new tests (the GitHub reader keeps only the user, accounts never contain the token,
the identity fields); the page by `grim` with the default picture and a typed name (restored to empty afterwards). Not verified: a click
on Choose picture (the same zenity flow as the lock page), another picture shape, a machine without gh or Claude.
Not verified (2026-10-24): a click on Check now or Update, a machine without a battery.
