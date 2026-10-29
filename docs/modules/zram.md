# Module: zram

Applied: 2026-10-18 (Task 3). Script: `scripts/task03-zram-fwupd-fish.sh`.

## What is configured

`/etc/systemd/zram-generator.conf`: `[zram0]`, `zram-size = ram / 2` (about 15.4 GiB), `compression-algorithm = zstd`, `swap-priority = 100`.

The kernel uses swap devices in priority order, so zram (100) is used before the on-disk swapfile (-2). The 32 GB swapfile is kept for **hibernation**: the kernel resumes from the `resume=`/`resume_offset` swapfile, not from zram.

## Why

| Option | Pros | Cons |
|---|---|---|
| **zram + swapfile** (chosen) | Fast compressed RAM swap under memory pressure, no SSD wear for swapped pages, hibernation unaffected | Uses a little RAM when swapping |
| swapfile only | Simplest | Slow, writes to the SSD under pressure |
| zswap | Compression in front of the swapfile | Still ends up on disk, and the pool is harder to reason about |

The size is a cap, not an allocation: zram uses RAM only for pages actually swapped (empty it costs a few KiB).

## Verification (2026-10-18)

- `zramctl` shows `/dev/zram0` zstd 15.4G; `swapon --show` lists zram0 at priority 100 above `/swap/swapfile` at -2.
- Hibernate/resume test (2026-10-18): `systemctl hibernate` then power on resumed the same boot (one boot ID across the hibernate, session intact) with zram active, so `resume=` from the swapfile is unaffected. Wake took about 10-15 s end to end, mostly firmware plus the GRUB menu countdown (see `grub.md`), not the image read.

## Undo

Delete `/etc/systemd/zram-generator.conf`, then `systemctl daemon-reload` and `swapoff /dev/zram0`.
