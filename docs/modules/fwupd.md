# Module: fwupd (firmware updates)

Applied: 2026-10-18 (Task 3).

## What is configured

`fwupd` installed. The daily `fwupd-refresh.timer` is deliberately **not** enabled (it is a background network job). Check for firmware updates manually as part of the update routine:

```
fwupdmgr refresh
fwupdmgr get-updates
fwupdmgr update          # only on AC power with the battery above 50%
```

Lenovo publishes BIOS/firmware through LVFS, so this replaces booting Windows for firmware updates.

## Dependency weight

fwupd pulled in 28 packages (about 96 MiB installed), notably `udisks2`, `mdadm` and `libqmi`/`libmbim` (modem support), plus a `passim` service. These are D-Bus-activated and should exit when idle. Observed 12 minutes after install: `fwupd` (about 55 MB RSS, kept alive by manual `fwupdmgr` use), `udisksd` (about 17 MB) and `passimd` (about 14 MB) were still running.

### passim

`passim` is a local caching server that can share firmware metadata with other machines on the LAN. It is not needed for firmware updates, so it is **masked** (`sudo systemctl mask --now passim.service`, applied 2026-10-18) to avoid a network-facing service and its memory use (about 14 MB).

## Firmware status (2026-10-18)

`fwupdmgr get-updates`: no updates available for any device, including BIOS and System Firmware. Nothing to apply.

## Hardware found with `lsusb`

| Device | ID |
|---|---|
| Integrated camera | Luxvisions Innotech `30c9:00ca` |
| Bluetooth | Intel AX211 `8087:0033` |

**No fingerprint reader** on USB.
