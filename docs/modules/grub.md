# Module: GRUB

Applied: 2026-10-18 (Task 4). Script: `scripts/task04-grub.sh`. Backup: `/etc/default/grub.bak-bbkos`.

## What is configured (`/etc/default/grub`)

| Setting | Value | Why |
|---|---|---|
| `GRUB_TIMEOUT` | `2` (was 5) | The 6 s "loader" time in the baseline was GRUB waiting out its countdown. The menu stays visible so snapshot recovery is reachable without relying on UEFI key-poll timing. |
| `GRUB_TOP_LEVEL` | `/boot/vmlinuz-linux` (was `/boot/vmlinuz-linux-lts` until 2026-10-20) | Pins mainline `linux` (7.2.11) as the default top-level entry. `linux-lts` (6.18.57) stays under "Advanced options" as the fallback. Flip this line back to `/boot/vmlinuz-linux-lts` to return to LTS. |
| `GRUB_DISABLE_OS_PROBER` | `false` | Keeps the Windows Boot Manager entry. `os-prober` only runs when `grub.cfg` is generated, never at boot, so it costs nothing at boot time. |
| `GRUB_DEFAULT` | `0` | Unchanged. |

## What was deliberately NOT used

`GRUB_DEFAULT=saved` with `GRUB_SAVEDEFAULT=true`: GRUB cannot write its environment file on btrfs, so it would silently not remember the choice. `GRUB_TOP_LEVEL` is deterministic instead.

## Regenerating

`sudo grub-mkconfig -o /boot/grub/grub.cfg` (after editing `/etc/default/grub`). `grub-btrfsd` also regenerates the snapshots submenu when snapshots change.

## Verification (2026-10-18)

- Settings present in `/etc/default/grub`; `grub.cfg` regenerated.
- `grub.cfg`: Windows entries 2, snapshot lines 3 (7 snapshots found), top-level entries: Arch Linux, Advanced options, Windows Boot Manager, Arch Linux snapshots.
- Loader time after the change (cold boot): **2.6 s** (baseline 6.0 s); total boot 14.3 s (baseline 16.7 s). Userspace rose 2.8 s to 3.8 s from the new services (snapper, zram, grub-btrfsd, fwupd deps); to watch.

## Observation (not acted on)

`efibootmgr` lists a stale `Fedora` entry (`\EFI\fedora\shim.efi`, Boot0000), after GRUB (0004) and Windows (0003) in boot order. It is harmless but could be removed with `efibootmgr -b 0000 -B` once confirmed unused.

## Undo

`sudo cp -a /etc/default/grub.bak-bbkos /etc/default/grub && sudo grub-mkconfig -o /boot/grub/grub.cfg`.

## Default kernel changed to mainline `linux` 7.2.11 (2026-10-20)
- **Why:** the owner wanted to run the newer kernel (the power-tuning notes had it as an open comparison).
- **Trial first, no config change:** booted 7.2.11 once from "Advanced options". Checked: no failed units; `bbkos-check` passed; kernel warnings the same as on LTS (one i915 warning in both) and errors 12 against 14, the only new line being "TDX not supported"; the GPU driver in use is `i915`; Wi-Fi, Bluetooth, brightness (laptop and external), HDMI hotplug (the touchpad kept working after the first connect: 801/134/24 one-, two- and three-finger events), suspend (s2idle entered and exited cleanly). Not tested on 7.2: hibernate.
- **Switch:** snapper snapshot `pre-kernel-7.2` (number 89), `GRUB_TOP_LEVEL` set to `/boot/vmlinuz-linux`, `sudo grub-mkconfig -o /boot/grub/grub.cfg` (all run by the owner). `grub.cfg` is root-only, so the menu order was not read back by the agent; the next boot shows it.
- **Undo:** set `GRUB_TOP_LEVEL` back to `/boot/vmlinuz-linux-lts` and regenerate. Or pick LTS in "Advanced options" at boot, with no change at all.
- The comment line above `GRUB_TOP_LEVEL` in `/etc/default/grub` may still say LTS is the default (cosmetic, no effect).
- `bbkos-check` now compares the running kernel with the package of its own flavour (it used to compare only with `linux-lts`).
