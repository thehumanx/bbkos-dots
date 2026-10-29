# xdg-apps

User-level `.desktop` overrides that hide launcher entries which are noise on this machine
(`Hidden=true` removes an entry from every XDG-compliant menu and launcher, and survives package updates).

| Entry | Why hidden |
|---|---|
| `avahi-discover`, `bssh`, `bvnc` | Avahi zeroconf browsers pulled in as dependencies |
| `xfce4-about` | Declares `OnlyShowIn=XFCE`; Quickshell does not apply that filter |
| `qv4l2`, `qvidcap` | Qt V4L2 camera test tools (run from a terminal when needed) |
| `jconsole-java21-openjdk`, `jshell-java21-openjdk` | JDK developer tools added by `jdk21-openjdk`; run `jconsole` / `jshell` from a terminal |

To show one again: delete its file here and re-run `stow`.
