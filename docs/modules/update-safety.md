# Module: update safety (`bbkos-check` and the update routine)

Task 10, applied 2026-10-18. Script: `dotfiles/bin/.local/bin/bbkos-check` (on `PATH` as `bbkos-check`).

Arch is a rolling release and two parts of this system are young: Hyprland's Lua config (0.55+) and Quickshell (0.3.x, pre-1.0). Any update can break a config, so the routine below ends with a check.

## Update routine

The bar's Updates widget (beside the clock, `docs/modules/bar.md`) shows the count of pending repo updates and, on click, opens a floating terminal running `bbkos-update`: pending list, Arch news reminder, `yay -Syu`, then `bbkos-check`. It shows its progress with `bbkos-progress` (a `[████░░░░] 2/4 steps` bar, see `docs/modules/desktop-tools.md`). It is steps 1, 2 and 4 below; steps 3 and 5-8 stay manual (it prints the `pacdiff` reminder).

1. Read the Arch news (https://archlinux.org/news/) for manual-intervention notices.
   - **A pending kernel** (`linux` or `linux-lts`): `bbkos-update` also runs `bbkos-kernel-notes`, which prints the version jump and the kernel.org changelog link (`https://cdn.kernel.org/pub/linux/kernel/v<major>.x/ChangeLog-<version>`; the Arch kernel packages ship no changelog, `pacman -Qc linux` says so), calls out a new series (7.2 -> 7.3) and a packaging-only change, and reminds you that the upgrade replaces that package's old kernel, so the fallback is the OTHER kernel under GRUB's Advanced options. It prints links only, with no network access. The URL pattern was checked on 2026-10-20 (real versions answer 200, a fake one 404).
2. `yay -Syu` once AUR packages exist (otherwise `sudo pacman -Syu`). It upgrades repo and AUR packages together. **Read the PKGBUILD diff of every AUR update** (`yay --diffmenu`): the Arch news of 2026-06-12 reported malicious AUR packages. snap-pac takes a pre and a post snapshot automatically for the repo part. Never `-Sy` alone and never install against a stale database (partial upgrades).
3. `sudo pacdiff` to merge any `.pacnew`/`.pacsave` files (a warning hook also prints them after each transaction).
4. `bbkos-check`.
5. Reboot if the kernel or systemd changed (`bbkos-check` says so).
6. `bbkos-clean` (dry run) after AUR installs or updates; `bbkos-clean --apply` once the new version works. It removes build trees, downloaded source archives and finished packages of uninstalled AUR apps, and keeps the newest finished package per app (your rollback copy) and yay's git clones (your PKGBUILD diff baseline).
7. Zen Browser updates itself (tarball install in `~/.local/opt/zen`, see decision 0004): check Zen's About page now and then; yay does not cover it.
8. Occasionally `fwupdmgr refresh && fwupdmgr get-updates` (no background timer on purpose).

After any snapshot rollback (or a restore of an older root), run `sudo bbkos-grub-reinstall`: a rollback brings back the old GRUB modules in `/boot/grub` while the EFI partition keeps the newer image.

If an update breaks something:
- Config error or crash: `bbkos-check` names it; fix the config in `~/.local/share/bbkos/repo/dotfiles` (git shows what changed).
- Cannot log in or no desktop: GRUB, "Arch Linux snapshots", pick the post/pre snapshot from before the update (boots read-only with an overlay), or use the TTY (`Ctrl+Alt+F3`).
- Undo one transaction's file changes: `sudo snapper -c root undochange <pre>..<post>`.
- Do not pin packages with `IgnorePkg` (partial-upgrade breakage); hold a known-bad release only temporarily and record it.

## Unattended upgrades are off (`upgrade.service`)

The AUR package `upgrade 0.3.2-1` was installed on 2026-10-19. It ships `upgrade.timer` (15 minutes after boot, then hourly via `OnUnitInactiveSec=60min`) and `upgrade.service`, which runs as the system user `upgrade` (uid 1001, with the package's sudo rule): `pacman -Syu --noconfirm`, `yay --removemake -Syu --noconfirm`, `flatpak update`, then `pacman -Scc` because `/etc/upgrade.conf` has `clean_cache_on_success=true`.

It contradicts the routine above: no Arch-news check, no PKGBUILD diff review, a race with `bbkos-update` for the pacman lock, and `pacman -Scc` wipes the package cache that downgrades rely on. Its first run (during installation) failed on the pacman lock; every run after that failed at the last step because `pacman -Scc` refuses to remove empty `/var/cache/pacman/pkg/download-*` directories and `set -euo pipefail` fails the unit. By 2026-10-20 the cache held 0 package files.

**Owner decision (2026-10-20): the timer is off.** Applied and verified:

```
sudo systemctl disable --now upgrade.timer     # is-enabled: disabled, is-active: inactive
sudo systemctl reset-failed upgrade.service    # is-failed: inactive
sudo rmdir /var/cache/pacman/pkg/download-*    # 8 empty directories; rmdir cannot touch a live download
```

`bbkos-check` then passed with no failed units. The package and its `upgrade` user remain installed (removing them is a separate decision); nothing triggers the unit while the timer is disabled. Undo: `sudo systemctl enable --now upgrade.timer` — do not, unless the reasons above have changed first. On 2026-10-20 `/etc/upgrade.conf` was changed to `clean_cache_on_success=false` (verified), so a hand-started unit would no longer empty `/var/cache/pacman/pkg`. It would still upgrade with `--noconfirm`, so it must still not be started by hand. Undo: set the value back to `true`.

## What `bbkos-check` verifies

| Check | Why |
|---|---|
| No unmerged `.pacnew`/`.pacsave` files | Package config changes waiting to be merged |
| No failed system or user units | Anything broken by the update |
| `hyprctl configerrors` empty | A Hyprland update can break the Lua config |
| Every generated Lua file loaded (`~/.local/state/bbkos/hypr-load-errors` empty; a note while it does not exist yet) | They load under `pcall`, so their errors never reach `configerrors`: a Hyprland Lua API change would silently drop binds or theme |
| Theme engine: `matugen` installed; `colors.json`, `hypr-theme.lua`, `kitty-theme.conf`, `palette.json` exist in the state dir; `bbkos-theme status` says `fresh: yes` (FAIL on `no`, note on `unknown` = no stamp yet); `settings.json` readable (a broken Stow link fails); `bbkos-qml-audit ~/.config/quickshell` prints `missing imports: 0`. FAIL when `bbkos-theme` is not on `PATH` (the rest of the section is skipped) | A wallpaper-driven theme that is missing, stale against the settings, or a QML file that lost an import (fails at runtime, not at load) |
| `quickshell`, `hypridle`, `cliphist` active; no Quickshell errors **in this service run** (matched by `InvocationID`, so the previous session's logout noise does not count) | Quickshell's QML API can change before 1.0 |
| No coredumps since this graphical session started (each crashed program named with its path and count; any program counts, an app's crash as much as the shell's) | A crash in the current session; a logout that kills clients shows up in the next login's history, not here |
| The installed root helpers (`bbkos-power-apply`, `bbkos-logind-apply`, `bbkos-touchpad-reload`, `bbkos-grub-reinstall`) equal the repo copies | An edit in the repo does nothing until its installer is run again |
| No stray `hyprlock` (a hyprlock process while the session is unlocked, or more than one) | The 2026-10-18 incident: a stray made every later lock a no-op, so the laptop slept and hibernated unlocked |
| Sleep drop-in directory contains only `bbkos.conf` | A forgotten test drop-in (for example the 2-minute hibernate test) changes behaviour silently |
| Running kernel equals installed `linux-lts` | Reboot reminder |
| Latest snapshots (note only) | Needs `ALLOW_USERS=$USER` in `/etc/snapper/configs/root` (`sudo snapper -c root set-config ALLOW_USERS=$USER SYNC_ACL=yes`); otherwise the check prints a note, not a failure |

Exit status is 0 when everything passed, 1 otherwise. `BBKOS_ETC=<dir>` redirects the `.pacnew` search for testing. Theme section hooks: `BBKOS_STATE_DIR`, `BBKOS_SETTINGS`, `BBKOS_QS_DIR` override the three default paths; `BBKOS_CHECK_ONLY=theme` runs only that section (the other checks call the live `systemctl`/`hyprctl`/journal). Tests: `tests/theme/test_bbkos_check.py`.

## Verified (2026-10-18)

- Fake `.pacnew` in a scratch directory: FAIL, file named, exit 1.
- A fake stray `hyprlock` (a copy of `sleep` named `hyprlock`) while unlocked: FAIL; two strays: FAIL.
- Clean real run: all checks passed, exit 0 (snapshot line was the "needs ALLOW_USERS" note).
- Not yet verified through a real `pacman -Syu` run by `bbkos-update` (no updates were pending on 2026-10-18). One repo update (`electron44`) was applied on 2026-10-20 by the now-disabled `upgrade.service`, so the next manual update is still the first test of this routine.

**Update 2026-10-20:** the `upgrade` package was removed (`pacman -Q upgrade` finds nothing, no `/etc/upgrade.conf`, no `upgrade.*` units, no `upgrade` user). Everything above describes why; none of it applies any more, and `bbkos-update` is the only upgrade path.
