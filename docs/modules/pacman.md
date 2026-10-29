# Module: pacman baseline and maintenance

Applied: 2026-10-18 (Task 1). Script: `scripts/task01-pacman.sh`, extras in `scripts/task01b-pacman-extras.sh`.

## What is configured

| Item | Where | Notes |
|---|---|---|
| `ParallelDownloads = 10` | `/etc/pacman.conf` | Edited directly. A drop-in was tested and rejected: the main file's own line must be removed for an `Include` to win, so it isolates nothing. `.pacnew` files are merged with `pacdiff`. |
| `ILoveCandy` | `/etc/pacman.conf` | **Cosmetic only** (Pac-Man progress bar). Remove the line if undesired; no functional effect. |
| `VerbosePkgLists` | `/etc/pacman.conf` | Task 1b. Old → new version table before upgrades. |
| Mirror refresh | `/etc/xdg/reflector/reflector.conf`, `reflector.timer` | Countries Nepal, India, Singapore; HTTPS; 10 fastest; weekly. |
| Mirror refresh retry | `/etc/systemd/system/reflector.service.d/50-bbkos-retry.conf` | Added 2026-10-28 (audit F5): `Restart=on-failure`, `RestartSec=2min`, at most 5 starts an hour. The weekly timer is `Persistent`, so after a sleep it fires at wake, before Wi-Fi is up, and failed on DNS (2026-10-26); it now retries. Written by the owner with `sudo tee`; not tracked as a file in the repo (the content is this row). |
| Cache cleanup | `paccache.timer` | Keeps the last 3 versions of each package, weekly. |
| `.pacnew` warning | `/etc/pacman.d/hooks/90-pacnew-warn.hook`, `/usr/local/bin/bbkos-pacnew-warn` | Prints a warning after any transaction if unmerged `.pacnew`/`.pacsave` files exist. |
| `makepkg.conf` | `/etc/makepkg.conf` | Task 1b. `!debug` in `OPTIONS` (no `-debug` AUR packages), `MAKEFLAGS="-j$(nproc)"`. `-march=native` deliberately not used (breaks portability, no benefit for prebuilt packages). makepkg has no drop-in directory, so the file is edited directly. |

## Backups of replaced files

`/etc/pacman.conf.bak-bbkos`, `/etc/pacman.d/mirrorlist.bak-bbkos`, `/etc/makepkg.conf.bak-bbkos`.

## Verification (2026-10-18)

- `pacman-conf ParallelDownloads` → `10`; `pacman-conf ILoveCandy` → set.
- `reflector.timer` and `paccache.timer` scheduled.
- Mirrorlist: 10 HTTPS mirrors (India, Nepal, Singapore).
- `paccache` and `pacdiff` on `PATH`; no stray `.pacnew` files.
- `.pacnew` hook firing is tested in Task 2 (script step 0).

## Undo

Restore the `.bak-bbkos` files, `systemctl disable --now reflector.timer paccache.timer`, delete the hook and `/usr/local/bin/bbkos-pacnew-warn`. Retry: `sudo rm -r /etc/systemd/system/reflector.service.d && sudo systemctl daemon-reload`.

## Routine

After updates: `pacdiff` to merge any `.pacnew`; check the Arch news before big upgrades. `checkupdates` (pacman-contrib) lists pending updates without touching the sync database.
