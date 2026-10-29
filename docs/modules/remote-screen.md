# Remote screen (the laptop screen on the phone)

Added 2026-10-24. Command `bbkos-mirror` (`dotfiles/bin/.local/bin/bbkos-mirror`), packages `wayvnc` and `tailscale` (official repos, installed by the owner).

## Why

Owner wish: see the laptop screen on the Android phone and use it by touch, also away from home. Chosen: wayvnc (the VNC server for wlroots-style compositors such as Hyprland) with bVNC on the phone, over Tailscale (WireGuard mesh) so no port is opened to the internet. Rejected: RustDesk and AnyDesk (weak Wayland support), Sunshine and Moonlight (lower latency but a much bigger setup; the fallback if VNC stays too slow), KDE Connect (no screen).

## How it works

- `bbkos-mirror on [OUTPUT]` starts wayvnc as the transient user unit `bbkos-mirror.service` (`Restart=on-failure`), bound to the Tailscale IPv4 address only, port 5900. Nothing runs until `on`; it does not survive a reboot.
- Credentials: `bbkos-mirror setup` (run by `on`) creates a self-signed certificate and a random password in `~/.config/wayvnc/` (mode 700/600, not in the repo, username `bbk`). `bbkos-mirror password` prints it; to rotate, delete `~/.config/wayvnc/config` and run `off`, `on`.
- `status` shows on/off and the number of established clients; `address` prints `ip:port`.
- Phone: Tailscale app (same account), bVNC, address and port from `address`, accept the certificate once, "direct touch" input.

## Measured (2026-10-24, phone on the same Wi-Fi)

Connected and live (one established session, direct Tailscale path). The picture painted slowly ("old CRT"): the laptop was on 2.4 GHz channel 1 at -69 dBm with a 26 Mbit/s uplink, the session sent about 8 Mbit/s, so a full 1920x1200 update takes about a second; wayvnc used 0 % CPU and 87 MB. Phone ping through Tailscale 225 ms against 13 ms direct.

## Not verified / open

- Mobile data (the real remote case), touch accuracy, and use while locked.
- The Network settings page has the mirror switch, the address and Copy password (`network.md`).
- Open: a phone-sized virtual (headless) screen to send fewer pixels; start at login (needed to reach a laptop remotely that you did not switch on); a menu entry.
- The laptop must be on and awake; closing the lid suspends it (`bbkos-lid`).
