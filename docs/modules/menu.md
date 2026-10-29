# The bbkOS menu (launcher, commands, web apps)

One search box for apps, web apps, bbkOS commands, settings pages and single settings, a calculator and a web search, ranked the way
Raycast ranks its root search and learning from what is opened. It replaced the app-only launcher on 2026-10-23, on
the same key (`Super+R`, `qs ipc call launcher toggle`). It also creates and removes web apps: a site in its own Vivaldi
window with its own entry. Source: `dotfiles/quickshell/.config/quickshell/modules/launcher/{Launcher,MenuWindow}.qml`,
`Rank.js`, `Commands.js`; command `bbkos-webapp`; tests `tests/launcher/`.

## References

- **oma-cast** (github.com/typecraft-dev/oma-cast, read 2026-10-23): a Raycast-style launcher plugin for Omarchy's
  Quickshell shell. It cannot be dropped in: it is a plugin for `omarchy-shell`, built on its menu (about 400 Omarchy
  actions) and theme; it describes itself as early; and the repository states no license, so nothing was copied.
  Taken as ideas: one ranked list of apps and system actions, the ranking (below, from the behaviour its SPEC documents
  for Raycast 2.8), frecency and learned search terms, Ctrl+1-9 quick picks, a calculator and a web-search fallback.
- **Omarchy** (MIT): `omarchy-webapp-install` and `omarchy-launch-webapp` for web apps (icon lookup, `--app=`,
  `StartupWMClass`, refusing non-http(s) addresses).
- **Emil Kowalski** (`motion.md`): something opened from the keyboard many times a day gets no animation, "Raycast has
  no open/close animation". The menu appears at once (layer namespace `bbkos-picker`, rule `bbkos-instant-layers`).

## What it finds

| Kind | Source | Enter does |
|---|---|---|
| App | every visible desktop entry (`DesktopEntries`) | `uwsm app -- ID.desktop` (own systemd scope, as before) |
| Web app | entries `bbkos-webapp-*.desktop` (shown with the tag "Web app") | the same: the entry runs `bbkos-webapp launch URL` |
| Command | `Commands.js`: lock, suspend, log out, restart, shut down, the three power modes, keep awake, update, health check, overview, stage mode for this workspace, hide the bar, clipboard, emoji, notifications, Wi-Fi, Bluetooth, sound, display, battery, calendar, Claude Code in bbkOS (a kitty in `~/.local/share/bbkos/repo` running `claude`, also `Super+Ctrl+Enter`), screenshot, screen recording, OCR, light mode, dark mode, Create web app; and "Remove web app: NAME" for each web app | the action, inside the shell where it can (`PanelState`, `Power`, `StageState`, `Awake`, `SettingsStore`), else a detached process |
| Settings | every settings page, and every tab of a page with tabs (`settings/Pages.js`, read by `Commands.settingsEntries()`; nothing to keep in step since 2026-10-28), and since 2026-10-29 every single setting (a row of `settings/SearchIndex.js`, the settings window's own search index, read by `Commands.settingRowEntries()`: title is the row label, subtitle "Settings · Page › Tab · Card"; the hint is not searched, and the subtitle is shown but not matched, `subtitleOnly`) | `SettingsStore.openPage("page/tab")`; a single setting also sets `SettingsStore.reveal`, so the tab opens scrolled to the row and lights it up (as the settings sidebar search does) |
| Calculator | a query made of numbers, `+ - * / % ^`, parentheses (also `×`, `÷`) | copies the result (`wl-copy`) |
| Web | always last while there is a query | DuckDuckGo in the default browser (`xdg-open`) |

**Uninstall (Delete, 2026-10-23):** with the cursor at the end of the search text (where Delete would remove nothing),
Delete on an app or web app turns the row red ("Press Delete again to uninstall NAME") for 4 s; a second Delete runs
`bbkos-uninstall DESKTOP_ID`: a web app is removed at once; a pacman app runs `sudo pacman -Rns PKG` in a floating
terminal (class `bbkos-tui-uninstall`), where pacman lists the package, the dependencies nothing else needs (`-s`) and
their saved configs (`-n`) and asks its own Y/n, so the owner sees exactly what goes before anything is removed (pacman
refuses on its own to remove what another package still requires); a Flatpak app runs `flatpak uninstall` and then
`flatpak uninstall --unused`. Refused, with a notification and nothing deleted: entries no package manager owns (the
owner's Zen from a tarball) and the packages bbkOS runs on (`quickshell hyprland uwsm kitty thunar vivaldi greetd
pipewire wireplumber networkmanager`, and since 2026-10-28 the tools the shell and the `bbkos-*` commands call: `hyprlock
hypridle hyprsunset grim slurp cliphist wl-clipboard bluez bluez-utils ddcutil matugen brightnessctl
power-profiles-daemon upower fish stow inotify-tools mpv socat jq libnotify gpu-screen-recorder tesseract
xdg-desktop-portal-hyprland polkit gnome-keyring pipewire-pulse`; the list is `DEFAULT_PROTECTED` in the script; remove
those with pacman by hand). Checked with `--dry-run` for Thunar
(refused), Vivaldi (refused), Stremio (Flatpak), Zen (refused: no package) and a web app; through the menu a test web app
was removed and Thunar was refused with the notification. A real pacman removal was not run.

**All apps (Tab, 2026-10-23):** Tab (or the "All apps" command) switches the list to a grid of every app and web app,
six to a row with their icons, alphabetical, four rows visible and scrolling; typing filters it (ranked as the list),
arrows move, Enter opens, Delete uninstalls as in the list, Tab goes back. For finding an app whose name you do not
remember. Not checked on screen yet (the session was locked when it was built).

Log out, restart, shut down and Remove web app ask first: the first Enter turns the row red ("Press Enter again to
...") for 4 s, as every destructive action in bbkOS. Keys: Up/Down, Enter, Ctrl+1-9 (the row with that number), Esc.

## Ranking (`Rank.js`)

Our own code after the behaviour oma-cast's SPEC documents for Raycast's root search (section 4):
- **Fuzzy title match:** every query character in order; 4 points for the very first character of the title, 3 at a word
  start, 2 elsewhere, minus 1 for each jump. Accepted at Raycast's "medium" sensitivity: `score >= 1.5 * (length - 2)
  + 4` (one or two characters: any match). A query found in the title as a whole word counts at least as a prefix.
- **Subtitle** fuzzy, **keywords only at a word start** (app keyword lists are long: Thunar's has 17, and a fuzzy match
  over them found unrelated apps); both count one point less than the title. The app's long description is not
  searched (it matched almost anything).
- **Several words (2026-10-29):** a query of two or more words also matches a title in which every word starts one of its words ("card gap" finds "Gap between cards"), scored like a keyword hit.
- **Order:** learned term, then text score, then frecency, then kind (apps before commands before settings), then name.
- **Frecency:** the newest 10 launches per item, each counting `exp(-age / 14 days)`; with an empty query the most used
  come first. **Learned terms:** the last 5 queries used to open an item; typing one again (or the start of one) puts
  that item first, for 17 days after its last use.
- **Storage:** `~/.local/state/quickshell/by-shell/<id>/launcher-usage.json`, at most 300 items (oldest dropped), written
  atomically on each launch, read when the menu opens. Calculator and web-search rows are not recorded.
- **Calculator:** a small recursive-descent parser, never `eval`; anything else in the query (letters, `;`) makes it
  not a calculation.

## Web apps (`bbkos-webapp`)

- **Create:** the menu's "Create web app" command opens a form (Name, Address; Enter or Create). It runs
  `bbkos-webapp install NAME URL`: the address gets `https://` if it has no scheme and must then be plain http(s) with no
  spaces, quotes, `$` or backticks (Chromium's `--app` would run `javascript:`, `file:` and `data:` as a document); the
  name 1-60 characters without `/` or control characters. The icon is the site's `apple-touch-icon`, else
  `/apple-touch-icon.png`, else Google's favicon service at 256 px, each kept only if it is a PNG (WhatsApp's own touch
  icon is WebP, so its logo comes from the favicon service); else the theme's `web-browser` icon. `Icon=` holds the
  icon's absolute path (the spec allows it), and the menu loads absolute icon paths as files: by name, the shell did not
  find icons in `~/.local/share/icons/hicolor` and showed the generic executable icon (the owner's WhatsApp, fixed
  2026-10-23; the existing entry was corrected by hand). Files: `~/.local/share/applications/bbkos-webapp-SLUG.desktop` (`Exec=bbkos-webapp launch "URL"`
  with `%` doubled, `StartupWMClass`, `X-bbkOS-WebApp=URL`) and
  `~/.local/share/icons/hicolor/256x256/apps/bbkos-webapp-SLUG.png`. The new app is in the menu at once.
- **Open:** `vivaldi --app=URL` (the owner's choice for every web app, 2026-10-23; `BBKOS_WEBAPP_BROWSER` overrides): a
  window without tabs or address bar, in the browser's own profile, so the owner is signed in as in Vivaldi. The window
  class is Chromium's for `--app` windows, `vivaldi-HOST_PATH-Default` with `/` as `_` (checked: `example.com` gives
  `vivaldi-example.com__-Default`), and the entry's `StartupWMClass` is the same.
- **Remove:** "Remove web app: NAME" in the menu (asks first), or `bbkos-webapp remove SLUG`. Only files that carry
  `X-bbkOS-WebApp` are touched.

## Settings (Launcher page, 2026-10-24)

**Apps › Launcher** (`PageLauncher`, place `apps/launcher`; sidebar index 27 until 2026-10-28) holds `launcher.*`, read live by `Launcher.qml` (`cfg`):
`webSearch` (`duckduckgo` default, `google`, `brave`, `startpage`, `ecosia`, or `off`: no "Search the web" result; the addresses are
the `engines` table in `Launcher.qml`), `calculator` (the "= value" result), `maxResults` (10 to 40 step 5, default 40), `commands` (the
bbkOS commands and settings pages: with it off only apps and web apps are searched) and `learn` (off: nothing is recorded and the ranking
ignores what was learned; the file is kept). **Forget** (two clicks) clears the learned usage through `qs ipc call launcher forget`. Reference:
DankMaterialShell's Launcher tab. Verified live through `qs ipc call launcher query`: the defaults gave the calculator and the web search; web search
off and calculator off removed both; commands off removed the command results; the engine switched to Google (the result title is the same, its
subtitle names the engine); every value was set back. Not verified: Enter on a Google result in a browser, the result cap with more than ten hits, the
page on screen, Forget.

## Test hooks

`qs ipc call launcher query TEXT` (the top 9 as the menu would show them), `type TEXT`, `form`, `create NAME URL`,
`run ID QUERY` (as Enter; "armed" for a command that asks first), `del ID QUERY` (as Delete). `launch DESKTOP_ID` as before.

## Verified (2026-10-23)

- Ranking through `qs ipc call launcher query`: "lock" gives Lock screen (command) then the Lock screen settings page,
  "thunar" Thunar File Manager first, "wifi" only the Wi-Fi command, "2+2*3" `= 8`, "dark" Dark mode, "wall" the
  Wallpaper settings page.
- Screenshots: the result list (glyphs, app icons, subtitles, tags, quick-pick numbers, footer), the Create web app form.
- Web app end to end through the menu's own code path: created "Example" from `example.com` (no site icon, so the
  theme icon), it appeared in the menu as a web app, Enter opened a Vivaldi app window with the class in its
  `StartupWMClass`, Remove asked once ("armed") and removed it on the second Enter. `bbkos-webapp install` against
  github.com fetched its 120 px apple-touch-icon.
- Tests: `tests/launcher/` (ranking, frecency, learned terms, bounds, calculator, `bbkos-webapp` validation, quoting,
  icon lookup, list and remove).

**Not verified:** real typing and clicks (IPC hooks used instead), the power and session commands (not run: they would
suspend or log out), a site whose icon is not a PNG (it falls back to Google's favicon), a second monitor.

## Known limits and decisions

- No action panel (Raycast's Ctrl+K, secondary actions per row) and no aliases or pinned favourites yet; the most used
  items rise by themselves.
- The web search uses DuckDuckGo, not a setting yet.
- Quickshell's live reload does not reload a changed `.pragma library` JavaScript file (`Rank.js`, `Commands.js`): the old
  code kept running until `systemctl --user restart quickshell` (seen while building this).
