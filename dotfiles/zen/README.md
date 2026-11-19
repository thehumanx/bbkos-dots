# zen

Two files for the Zen browser profile, **not stowed**: a profile folder has a random name, so copy them in by hand and restart Zen.

- `user.js` → `<profile>/user.js` (lets `userContent.css` load)
- `chrome/userContent.css` → `<profile>/chrome/userContent.css` (text selection is blue with white text)

Why: the GTK theme's text selection is the accent at 25 % alpha. The accent is white and Firefox drops the alpha, so selected text showed as a white bar (Vivaldi was fine). The `ui.textSelectBackground` and `ui.textSelectForeground` prefs were tried and did nothing on GTK.
