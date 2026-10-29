# Network page

Added 2026-10-24. Settings page **Network** (`PageNetwork`, place `network`, group Devices; sidebar index 22 until 2026-10-28), the command `bbkos-network`
(`bbkos_theme/network.py`, nmcli underneath). The Wi-Fi and Bluetooth popups in the bar stay the quick way; this page adds what they
do not have. Reference: the Network pages of GNOME, COSMIC and DankMaterialShell (NetworkWifi, NetworkVpn).

- **Wi-Fi:** the radio on or off (`nmcli radio wifi`).
- **Saved connections:** every saved Wi-Fi, ethernet, VPN, WireGuard and Bluetooth connection (loopback and the Tailscale interface are
  not listed), the connected ones first. A Connect automatically switch (`connection.autoconnect`) and Forget (`nmcli connection
  delete id NAME`, a second click within 4 s confirms). Names are passed as one argument, a name that starts with `-` or has control
  characters is refused, and nmcli's first error line is shown on the page.
- **Tailscale:** state, this device's address and the number of other devices (`tailscale status --json`), and an on and off switch
  (added 2026-10-25; `bbkos-network tailscale on|off` runs `tailscale up` / `tailscale down`). tailscaled keeps the choice across
  reboots: off stays off at the next boot, on reconnects. The switch needs the tailscale CLI's operator rights for this user, set once
  by the owner with `sudo tailscale set --operator=$USER`. The status reads them from `tailscale debug prefs` (`OperatorUser`, no
  root needed); without them the switch is greyed and the row shows that command, and an "access denied" from tailscale is replaced
  by it. Cost: tailscaled itself stays running (it measured 0 wakeups/s idle on 2026-10-25); off only drops the tunnel and its
  keepalives. The phone mirror needs Tailscale running, so its switch is greyed while Tailscale is off.
- **Phone mirror:** the `bbkos-mirror` on and off switch (needs Tailscale running), the address, the client count, and Copy password
  (`bbkos-mirror password | wl-copy`; the password is never shown on screen). See `remote-screen.md`.

Verified (2026-10-24): 6 tests in `tests/theme/test_about_network.py` with a fake nmcli, tailscale and bbkos-mirror (the escaped
colons of `nmcli -t`, the status, the three commands as nmcli calls, bad input refused with no call, a failing nmcli, the JSON) and
the page on screen with the real connections (a connected network, two saved ones, the Bluetooth network), Tailscale connected and the
mirror on. Not verified: any click (switching Wi-Fi, Forget, auto-connect, the mirror switch, Copy password), a VPN connection.
Note: the mirror was still on from the earlier phone test when the page was checked.

Tailscale switch verified (2026-10-25): 2 more tests (`tailscale down` / `tailscale up` called; an access-denied error turned into the
setup command, another error passed through), bad arguments refused; `bbkos-network status` on the live system reports
`operator: false`; a `grim` screenshot of the page shows "Connected", the greyed switch and the setup command. After the owner ran
`sudo tailscale set --operator=$USER` (it needs a real terminal: the `!` prompt in Claude Code cannot ask for the password): status
`operator: true`; `bbkos-network tailscale off` gave `BackendState` Stopped and `WantRunning` false, the page showed "Off" with the
switch enabled and off; `tailscale on` gave Running and `WantRunning` true. Not verified: a click on the switch itself (the command it
runs was), the state after a reboot.
