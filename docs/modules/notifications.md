# Module: notifications

The notification daemon (Quickshell's `NotificationServer`, which owns `org.freedesktop.Notifications`) and the
history behind the bar's bell widget and the notification panel. Files:
`dotfiles/quickshell/.config/quickshell/services/Notifs.qml`, `modules/notifications/`, and the history sheet in
`modules/panels/Panels.qml`.

Cards slide 24 px in from the screen edge with a fade and have the hairline edge and tinted shadow of every floating
card; the popup window is larger than the stack by the shadow's room (`motion.md`).

## What is tracked, what is history

Quickshell only keeps **live** notifications: `NotificationServer.trackedNotifications` drops one when it expires,
is dismissed, or the app closes it. The `Notification` object is then destroyed. The history is therefore our own
list of plain copies (`appName`, `summary`, `body`, `urgency`, time, read) made in the server's `onNotification`
handler, newest first. It is not a view over Quickshell's live list.

- `transient` notifications bypass the history (the spec says they must not be persisted).
- On a shell reload Quickshell re-emits live notifications with `lastGeneration = true`; those are skipped, so they
  do not appear twice.
- Notification **replacements** (`replacesId`) update Quickshell's live object without emitting `notification`
  again, so the history keeps the original text. This is a known limitation, not a rendering bug.
- History is capped at 100 entries by default (`notifications.historySize`, 20 to 500, the Notifications settings page). With more, the oldest is dropped (the unread count follows).
- History is written to `$XDG_STATE_HOME/quickshell/by-shell/<shell-id>/notifications.json`, next to the shell's
  screen-time totals (`ScreenTime.qml`). The path is per shell config, so it survives a shell restart and a reboot.
  The home directory is mode 700 on this machine; the file itself contains notification text and is not encrypted.
- On load every `notifId` becomes `-1`: notification IDs belong to one server instance and can be reused after a
  reload, so an old history row must never dismiss a new notification. A row only dismisses a live popup when it
  was added in the current server instance.
- A missing or unreadable file starts an empty history; the next change writes a fresh one.

## Bar widget and panel

The bell (`modules/bar/NotificationsWidget.qml`) is in the bar's end section by default, before the settings gear, so
the history is always reachable. It shows the unread count in accent (`99+` above 99); with no unread it is just the
bell in the normal bar foreground. Click opens the panel on that bar's screen (`PanelState.toggle("notifications",
screenName)`).

The panel (`modules/notifications/NotificationHistoryPanel.qml`) is a full-height sheet on the right of the screen,
whatever edge the bar is on, and opens with the same backdrop/Esc/click-outside behaviour as the other panels. It
does not overlap the bar: for a top, bottom or right bar it clears the bar's thickness plus 6 px on that edge; for a
left bar the sheet is on the opposite side and uses `shell.gap`. Width 380 px. The list scrolls with the
wheel/trackpad; there is deliberately no scrollbar until it can be drawn without the default Qt scrollbar's
full-height line in an empty list.

Read state is manual (owner choice, "B"):

- Clicking a card marks **that** entry read (the accent dot disappears).
- `Mark all read` marks the whole history read and clears the badge; the entries stay in the list.
- `Clear all` is a two-click action (second click within 4 s); it removes the history. Live popups are not touched,
  because they are not history.
- `×` removes one entry. If its notification is still live, that popup is dismissed as well.
- Clicking a live popup marks its history entry read before dismissing it. A popup that expires unclicked leaves
  its history entry unread, which is what B means.

Critical entries get a `Theme.crit` hairline, like the live card. Time labels are `HH:mm` today, `Yesterday HH:mm`,
or `d MMM HH:mm`. Text is forced to `Text.PlainText` in both the popup and the history: the server does not
advertise markup, so an app's HTML is shown as text rather than rendered.

Short state notices (charger, sound output, VPN) are not notifications and never enter this history: `toast.md`.

## Closing a popup, and do not disturb

- **Right click (or a two-finger tap)** on a popup closes it: no default action, its history entry is marked read. Two-finger
  tap is the right button while the touchpad's tap-to-click is on (libinput's default tap map). A left click still marks it
  read, runs the sender's default action and dismisses it. Both go through `Notifs.activate(notifId, runDefault)`: the
  default action already closes a non-resident notification (Quickshell's `NotificationAction::invoke`), so the
  notification is dismissed only while it is still live (a second close logged `Cannot close destroyed notification` on
  every click on a kitty notification, fixed 2026-10-28).
- **Do not disturb** is a `DND` switch right of the panel title (no counts, no help text on the panel) (`Notifs.dnd`, state file `<shell state dir>/dnd`, so it survives a
  restart). While on: no popup is shown (the popup window is not created, and a live notification is expired at once so it
  does not stay tracked), the notification still enters the history and counts as unread, and `Notifs.soundAllowed` is
  false. The bar's bell becomes the slashed bell. Critical notifications are not an exception. bbkOS plays no
  notification sound itself today (the daemon is silent); `soundAllowed` is the gate for any sound added later. A sound an
  app makes on its own is not under the shell's control. IPC: `qs ipc call notifications dnd true|false`, and `status`
  reports `dnd`.

## App icon

Each popup and history row shows the sending app's icon (16 px) before the app name, when it sent one that exists in the
icon theme (`Notifs.iconUrl`, `Quickshell.iconPath(name, true)`); a file path works too. No icon is drawn otherwise, and no
guessing from the app name. With images supported Quickshell delivers a plain icon name as `image://icon/NAME`, so
`Notifs.iconOf` takes the name from there (then `appIcon`, then `desktopEntry`), and the popup's large thumbnail ignores
`image://icon/` values (it is for real pictures such as a screenshot). The name is stored in the history (`appIcon`), so rows
sent before this change have no icon.

**Attached pictures (2026-10-23):** a wide or tall picture (aspect over 4:3 either way: a screenshot) is a thumbnail across
the top of the card, at most 180 px high. A square-ish one is a logo or an avatar and is drawn as a 40 px tile left of the
text, as mako and swaync do: the Claude app sends its logo as the image, and it filled the card. Checked with
`image-data` notifications: the Claude logo as a tile, a screenshot as the thumbnail. To send one from Python, build the
pixel bytes with `GLib.Variant.new_from_bytes(GLib.VariantType("ay"), GLib.Bytes.new(pixels), True)`: `GLib.Variant("ay",
pixels)` took 7 s for a 1024 px picture, so the earlier popup's 6 s timeout ran out first and it looked as if the second
notification had replaced the first (it had not; tracked again when sent fast).

## Settings

**Notifications page (2026-10-24; place `notifications`, group Desktop since 2026-10-28, index 15 before):** `notifications.*` in `settings.py`, read live by
`Notifs.cfg`: `position` (auto = the bar's end corner, or top-right, top-left, bottom-right, bottom-left; the stack, its
shadow room and the slide-in side follow), `timeout` (2 to 30 s, default 6, the time for popups whose sender gave none),
`senderTimeout` (on: the sender's own time wins; off: every popup uses `timeout`), `criticalSticky` (on: a critical popup stays
until closed, as before; off: it expires like the rest), `maxPopups` (1 to 10, default 5), `historySize` (20 to 500 step 20,
default 100: the cap of the bell's list), `showPictures` (attached screenshots and logos), `mutedApps` (below). The page also has the Do not disturb
switch (the same `Notifs.dnd` as the panel). Reference: GNOME, COSMIC and DankMaterialShell notification pages. Not done: a notification sound, popup width, "always show" rules.

**Muting an app (2026-10-28):** `notifications.mutedApps` is a list of app names exactly as apps send them (`appName`); the
Apps card on the Notifications page lists every name in the history plus every muted one, each with a switch (off = muted), so
an app shows up after its first notification. `Notifs.isMuted` is checked first in the server's `onNotification`: a muted
notification is neither tracked nor recorded, so there is no popup, no history entry, no unread count and (as nothing is
tracked) no action to run. Do not disturb is different: it keeps the history. Critical notifications from a muted app are
muted too. Names are matched whole and case-sensitively; the settings code (`applist` kind) drops names with a comma or a control
character, over 64 characters, repeated, or beyond 200. CLI: `bbkos-theme set notifications.mutedApps Slack,Spotify` (empty
text unmutes all). Reference: GNOME's per-app notification switches. Verified: `notify-send -a` from two fake apps, one muted:
only the other reached the history (`status`), the page screenshot shows the three rows with the muted one marked. Not
verified: a real app's name spelling (some send a different `appName` than their window title), a click on a switch.

The widget and sheet have no other keys. `bar.layout` places `notifications` (the default is
`end:notifications`, before the settings gear; Bar › Layout in the settings app can move or remove it). The bar's
`barHeight`, `barPills`, `barOpacity`, `pillRadius` and edge apply through `BarItem` / `BarSection`, and the sheet
clears the bar automatically. There is no `bar.iconNotifications` key: the bell is fixed. With `bar.iconsOnly` (`bar.md`) the count becomes a dot. Removing the widget leaves
the history and IPC working, but the only way to open the sheet is then `qs ipc call panel toggle notifications`.

## Capabilities

The server advertises `body` (plain text) and now `persistence`, because the history really does retain
non-transient notifications after the popup goes away and across restarts. `body-markup`, `actions` and `image` stay
off; there is no grouping or search (apps can be muted by name, see Settings). Those are future work, not hidden
features.

`notify-send` check: `GetCapabilities` returns `["persistence","body"]`.

## IPC test hooks

Target `notifications` (`modules/notifications/Notifications.qml`):

| Call | Effect |
|---|---|
| `qs ipc call notifications status` | JSON: tracked, unread, history length, cap and every entry (key, notifId, app, summary, read, urgency, time) |
| `qs ipc call notifications markAllRead` | Same as the panel button |
| `qs ipc call notifications dismiss <key>` | Same as `×` |
| `qs ipc call notifications click <notifId> true\|false` | A left (true: default action, then close) or right (false: close only) click on a live popup |
| `qs ipc call notifications invoke <notifId>` | Only the default action, no dismiss |
| `qs ipc call notifications clear` | Clear the history without the two-click guard |

The panel itself is opened with `qs ipc call panel toggle notifications` or by clicking the bell.

## Verified (2026-10-20)

- Normal, critical, low-urgency and transient `notify-send` notifications: the first three entered the history, the
  transient one did not. `status` showed 4 tracked / 3 history immediately after sending, then unread 3.
- A shell restart reloaded all entries with `notifId: -1`, `unread` intact, from
  `~/.local/state/quickshell/by-shell/<id>/notifications.json` (version 1).
- `markAllRead` set every `read` to true, persisted after a second restart, and `unread` went to 0.
- `dismiss 4` removed that entry; `clear` emptied the list; a new notification then appeared as key 5, unread 1, and
  the file was rewritten with the new entry.
- The sheet was captured with a temporary QML `grabToImage` hook (removed again) at every bar position and pill mode:
  380x1154 px for top/bottom bars and 380x1192 px for left/right bars on the 1920x1200 screen with `barHeight` 36 and
  `gap` 4. Header, unread dots, critical border, card text, footer and all four layouts rendered.
- Empty history after `clear`: the sheet now keeps the header at the top, the buttons at y=24, the divider at y=60,
  the empty label centred in the list area (y=69, height 1038) and the footer at y=1115. Populated state rechecked
  after the fix with one notification.

**Not verified:** a real mouse click on the bell, a card, the buttons or a popup (no pointer injection here); the
history with 100 entries; the file after a real reboot; a second monitor; and `grim` screenshots. `grim` 1.5.0 hangs
on this Hyprland 0.56.2 build because the compositor advertises `ext_image_copy_capture_manager_v1` but never sends
`ready`; reproduced with no panel open, so it is a pre-existing compositor/grim issue, not this module. The QML grab
above was used instead.

## Failure modes fixed while building

| Problem | Cause | Fix |
|---|---|---|
| A history row could dismiss a new notification after a reload | IDs restart with the server instance; `notifId` from the saved file was kept | Reset every loaded `notifId` to `-1`; only entries from the current instance can dismiss live popups |
| Duplicate entries after a shell reload | Quickshell re-emits live notifications with `lastGeneration = true` | Skip that generation in `_record` |
| Notification text with HTML could render as rich text | `Txt` defaults to `Text.AutoText`, while the server advertises no markup | `textFormat: Text.PlainText` on popup and history text |
| Default Qt `ScrollBar` drew a full-height line with an almost empty list | ScrollBar thumb filled the viewport when content fitted | Removed; the list scrolls by wheel/trackpad |
| Clearing the history broke the sheet layout: header at y=85, buttons at y=343, divider at y=534, with large gaps | Hiding the `ListView` (`visible: count > 0`) removed the only `Layout.fillHeight` item and left the `ColumnLayout` with stale geometry | Keep a permanent fill-height host `Item`; the `ListView` and the empty label live inside it. Measured after the fix: header y=0, buttons y=24, divider y=60, list host y=69 h=1038, footer y=1115 |
