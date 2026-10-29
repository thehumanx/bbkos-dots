# Module: snapshots

Applied: 2026-10-18 (Task 2). Script: `scripts/task02-snapshots.sh`. Decision: `docs/decisions/0001-foundation-and-safety.md`.

## What is configured

| Item | Where / value |
|---|---|
| Tool | `snapper` (config `root`, subvolume `/`), `snap-pac`, `grub-btrfs`, `inotify-tools` |
| Snapshot store | Subvolume `@snapshots`, mounted at `/.snapshots` (fstab, `subvol=/@snapshots`, `chmod 750`) |
| Scope | **Root (`@`) only.** `/home` is separate and not snapshotted. |
| Policy | `TIMELINE_CREATE=no`, `NUMBER_LIMIT=10`, `NUMBER_LIMIT_IMPORTANT=5`. Pre/post pairs on every pacman transaction (snap-pac); no timeline clutter. |
| Cleanup | `snapper-cleanup.timer` |
| GRUB integration | `grub-btrfsd.service` regenerates the "Arch Linux snapshots" submenu when snapshots change |
| Bootable read-only snapshots | `/etc/mkinitcpio.conf.d/bbkos.conf` (stock `HOOKS` plus `grub-btrfs-overlayfs`), initramfs rebuilt for both kernels |

Why it works: kernels live in `@/boot`, so a root snapshot contains a matching kernel and initramfs. `/boot` must not become a separate partition.

## Usage

- Manual snapshot before risky changes: `sudo snapper -c root create -d "pre-<thing>"`
- List: `sudo snapper -c root list`
- Compare: `sudo snapper -c root status <a>..<b>`
- Undo a transaction's file changes: `sudo snapper -c root undochange <pre>..<post>` (files only; use with care)
- Boot an old state: GRUB menu → "Arch Linux snapshots" → pick one. It boots read-only with an overlay, so changes are discarded on reboot.

## Verification (2026-10-18)

- `findmnt /.snapshots` → `subvol=/@snapshots`.
- `snapper list`: #1 manual, #2/#3 pre/post around `pacman -S tree`.
- `grub.cfg`: Windows Boot Manager entry present (2 matches), "Arch Linux snapshots" submenu present.
- `grub-btrfsd` and `snapper-cleanup.timer` active and enabled.
- Snapshot boot test (owner, 2026-10-18): booting snapshot #1 worked but showed plain `btrfs` on `@snapshots/1/snapshot`, because #1 was taken before the initramfs hook existed (a snapshot boots with its own initramfs). Booting snapshot #3 showed `findmnt /` = `overlay`. Recovery proven.
- Note: snapshots taken before the overlay hook (only #1) boot read-only without the overlay. Every later snapshot has it.

## Not covered

Snapshots live on the same disk. They protect against bad updates and config mistakes, not disk failure or theft. Backups of `/home` are an open item.

## Undo

Remove the fstab line and `/etc/mkinitcpio.conf.d/bbkos.conf`, rebuild with `mkinitcpio -P`, `grub-mkconfig -o /boot/grub/grub.cfg`, disable `grub-btrfsd` and `snapper-cleanup.timer`. Backups: `/etc/fstab.bak-bbkos`.
