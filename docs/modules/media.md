# Music widget and clock

Music widget added 2026-10-25, replacing the island (2026-10-24, removed the same day it was reworked: it hid the time whenever music played and its pill behaviour was not intuitive). Files: `modules/bar/MediaWidget.qml`, `services/Media.qml`, and for the clock `modules/bar/Clock.qml` and `modules/bar/DateHover.qml`. Settings: `media.*` (Sound page, "Music widget in the bar"), `clock.*` (Date and time page). No reference project: it is the bar's own widget pattern (`BarItem` plus `BarHit`).

## The clock

`Sun 25, 5:26` (`clock.date` adds the weekday and day; `clock.hour24` picks 24 h; no AM or PM, the hour says which; `clock.seconds` adds `:ss`). Qt only counts 12 hours when a format has AM or PM, so `Clock.qml` works the hour out itself. It is always visible: nothing replaces it.
Left click opens the calendar popup. While the pointer is on it (`clock.hoverDate`, default on) a small card appears at once under it (above a bottom bar, beside a side bar) with the full date and, with `calendar.nepali` on, the Nepali date (`कार्तिक ८, २०८३ BS`). `DateHover.qml` is a `PopupWindow` hung from the bar item inside a `LazyLoader`, so it exists only while shown. Its window keeps `shadowPad` free pixels on every side except the one facing the bar, where only 6 px are left so the card sits close. It hides when the calendar opens.

## The music widget

A normal bar widget (`media` in `bar.layout`, default centre, right after the clock; the layout editor moves it). Its `BarItem` is active while `Media.present` and the bar is horizontal; on a vertical bar it is hidden.

- **Look:** a note and `artist – title`. There is no progress line: one was tried and removed on 2026-10-25 because it cost battery (its 900 ms width animation on a 1 s tick kept the bar repainting at 60 Hz while a song played: Hyprland 10 % and Quickshell 7 % of a core against 3 % and 1 % without it), and the position needed a 1 s poll as MPRIS does not push it. The widget keeps the 8 px of height the line had. It is as wide as the song needs, up to `media.maxWidth` (default 220 px), and never narrower than the buttons plus 48 px of title.
- **Hover:** previous, play or pause, next appear, and the title is cut shorter to make room; the widget does not grow.
- **Paused:** the widget stays, dimmed to 55 %, so play can be pressed. It goes when the player does. A browser tab that paused its video therefore keeps it (this was the choice).
- **Clicks:** left opens the app the song plays in, middle skips to the next song, scrolling changes the volume by 5 % (`Audio.step`).
- **Open the app:** `Media.open()` finds the window whose class is the player's desktop entry (else contains it or the player's name), prefers one whose title contains the song, then the most recently used, and focuses it with `hl.dsp.focus` (switching workspace if needed; `cursor.no_warps` is on for that one focus, as for the stage rail). With no window it asks the player to raise itself, then starts its desktop entry. It does not look for the tab.
- **Hover and clicks:** one `MouseArea` (the `BarHit`) owns the hover and every click; the buttons are only drawn, and `hoverIdx` maps the pointer to a button (`0` previous, `1` play or pause, `2` next, `-1` none) by where it is over the controls row, which also gives the accent on the button under the pointer. Two earlier designs flickered (buttons vanishing and coming back in a loop): a `MouseArea` per button took the hover from the widget's as the pointer reached it, and counting the buttons' hover on top of the widget's still raced when the pointer moved (the owner saw it on a real pointer, my cursor warps did not).
- **Cost:** `Media.qml` takes the first MPRIS player that is playing, else the first paused one with a title. Nothing polls: the widget changes only when MPRIS reports a new track or play state, or on hover.
- **Test hooks:** `qs ipc call media status` (what is shown, the player's desktop entry and the window a click would focus) and `qs ipc call media open`.

## Timer, recording, updates and notifications

Unchanged by the rework: the Timer widget (its done state flashes red), the Recording widget and the Updates widget are normal bar widgets again (the island hid the first two). Notifications are back in the corner stack only (`notifications.md`).

## Verified, and not

Verified on the live system (laptop screen only: the external monitor was unplugged midway): the clock text at top, bottom, left and with pills off, grouped and individual; the hover card at top, bottom (above the bar) and left (beside it), at once and stable while hovered; the music widget playing Zen's YouTube, its hover buttons with the title cut and the width unchanged, held on each button position without collapsing; `qs ipc call media open` focused the Zen window from another window on the same workspace; the layout moved `media` beside the clock in the live settings; the settings written and validated (`tests/theme/test_media_settings.py`). Not verified: a real click on a button (no pointer injection; the mapping was read from logs), a paused song (the owner's music was not paused), the open on another workspace or monitor, a physical mouse or touchpad (the cursor was moved with `hyprctl dispatch`), the right bar, the music widget with Spotify.
