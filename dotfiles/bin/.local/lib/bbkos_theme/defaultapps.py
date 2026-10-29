"""Default apps (the settings page "Default apps", docs/modules/settings-app.md): which app opens web links, folders,
images, video, music, PDFs, text and mail. Reads the installed desktop entries (their MimeType lines) and writes the
freedesktop `~/.config/mimeapps.list`, [Default Applications], the file xdg-open, GTK and Qt apps and Thunar read.
One choice sets every MIME type of its category (a browser takes http, https, text/html ...); other lines and sections
of the file are kept. Written atomically.

The terminal is not a MIME type: it is the first entry of `~/.config/xdg-terminals.list` (the proposed freedesktop
default-terminal spec, which `uwsm app -T` reads; Super+Enter runs that), offered from the entries in the
TerminalEmulator category.

    bbkos-defaults status            JSON: the categories, the current app of each, the apps that can do it
    bbkos-defaults set CATEGORY ID   make desktop entry ID the default for CATEGORY
"""
import json
import os
import sys
import tempfile
from pathlib import Path

# key, label, the MIME types set together. The first one decides which apps are offered (they must list it).
CATEGORIES = [
    ("browser", "Web browser", ["x-scheme-handler/https", "x-scheme-handler/http", "text/html", "application/xhtml+xml",
                                "x-scheme-handler/about", "x-scheme-handler/unknown"]),
    ("files", "Files", ["inode/directory"]),
    ("images", "Images", ["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "image/tiff",
                          "image/svg+xml", "image/avif", "image/heic"]),
    ("video", "Video", ["video/mp4", "video/x-matroska", "video/webm", "video/quicktime", "video/x-msvideo",
                        "video/mpeg", "video/ogg"]),
    ("audio", "Music", ["audio/mpeg", "audio/flac", "audio/ogg", "audio/x-vorbis+ogg", "audio/x-wav", "audio/wav",
                        "audio/aac", "audio/mp4", "audio/opus"]),
    ("pdf", "PDF documents", ["application/pdf"]),
    ("text", "Text files", ["text/plain", "text/markdown"]),
    ("mail", "Email links", ["x-scheme-handler/mailto"]),
]
TERMINAL = ("terminal", "Terminal", "TerminalEmulator")
TERMINALS_LIST = "xdg-terminals.list"
# Not a terminal window of their own: foot's server (a background daemon) and client (needs that server running).
NOT_TERMINALS = {"foot-server.desktop", "footclient.desktop"}


def is_terminal(i, e):
    """A terminal you can open: in TerminalEmulator, shown in menus (kitty's URL helper is hidden), not foot's halves."""
    return TERMINAL[2] in e["categories"] and not e["nodisplay"] and i not in NOT_TERMINALS
SECTION = "[Default Applications]"


def config_home(env):
    return Path(env.get("XDG_CONFIG_HOME") or Path(env.get("HOME", "~")).expanduser() / ".config")


def app_dirs(env):
    """Desktop entry folders, most important first (a user entry hides a system one with the same id)."""
    home = Path(env.get("XDG_DATA_HOME") or Path(env.get("HOME", "~")).expanduser() / ".local/share")
    dirs = [home] + [Path(d) for d in (env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":") if d]
    return [d / "applications" for d in dirs]


def read_entry(path):
    """{name, mime, icon, categories} of an application entry, else None. NoDisplay entries count: they are hidden from menus but
    still open files (imv and zathura ship that way); Hidden=true means deleted. MimeType is taken from any section:
    some hand-made entries (the owner's Zen from its tarball) put it after the action groups."""
    name = icon = None
    mime, cats, in_main, hidden, nodisplay = [], [], False, False, False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            in_main = line == "[Desktop Entry]"
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k == "MimeType":
            mime += [m for m in v.split(";") if m and m not in mime]
            continue
        if not in_main:
            continue
        if k == "Name" and name is None:
            name = v
        elif k == "Icon":
            icon = v
        elif k == "Categories":
            cats = [c for c in v.split(";") if c]
        elif k == "Hidden" and v.strip().lower() == "true":
            hidden = True
        elif k == "NoDisplay" and v.strip().lower() == "true":
            nodisplay = True
        elif k == "Type" and v != "Application":
            return None
    if hidden or not name:
        return None
    return {"name": name, "mime": mime, "icon": icon or "", "categories": cats, "nodisplay": nodisplay}


def entries(env):
    seen = {}
    for d in app_dirs(env):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.desktop")):
            if p.name in seen:
                continue
            e = read_entry(p)
            seen[p.name] = e        # None also hides lower entries with that id (a user entry that hides a system one)
    return {k: v for k, v in seen.items() if v}


def read_defaults(path):
    """The [Default Applications] section as {mime: [ids]}."""
    out, cur = {}, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            cur = s
        elif cur == SECTION and "=" in s and not s.startswith("#"):
            k, v = s.split("=", 1)
            out[k.strip()] = [x for x in v.split(";") if x]
    return out


def write_defaults(path, updates):
    """Set mime=id for each pair in `updates` inside [Default Applications], keeping every other line."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    out, cur, done, found = [], None, set(), False
    for line in lines:
        s = line.strip()
        if s.startswith("["):
            if cur == SECTION:
                out += [f"{m}={i}" for m, i in updates.items() if m not in done]
                done.update(updates)
            cur = s
            found = found or s == SECTION
            out.append(line)
            continue
        if cur == SECTION and "=" in s and s.split("=", 1)[0].strip() in updates:
            m = s.split("=", 1)[0].strip()
            if m not in done:
                out.append(f"{m}={updates[m]}")
                done.add(m)
            continue
        out.append(line)
    if cur == SECTION:
        out += [f"{m}={i}" for m, i in updates.items() if m not in done]
    elif not found:
        if out and out[-1].strip():
            out.append("")
        out += [SECTION] + [f"{m}={i}" for m, i in updates.items()]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".mimeapps.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_terminals(path):
    try:
        return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    except OSError:
        return []


def terminal_status(env, apps):
    cands = sorted(({"id": i, "name": e["name"], "icon": e["icon"]} for i, e in apps.items() if is_terminal(i, e)),
                   key=lambda c: c["name"].lower())
    ids = {c["id"] for c in cands}
    listed = [l for l in read_terminals(config_home(env) / TERMINALS_LIST) if l and not l.startswith(("#", "-", "+", "/"))]
    current = next((l for l in listed if l in ids), "")
    return {"key": TERMINAL[0], "label": TERMINAL[1], "current": current, "candidates": cands}


def set_terminal(env, app_id, apps):
    """Put app_id first in xdg-terminals.list; other lines (comments, exclusions, other terminals) stay after it."""
    if app_id not in apps or not is_terminal(app_id, apps[app_id]):
        raise ValueError(f"not a terminal: {app_id}")
    path = config_home(env) / TERMINALS_LIST
    rest = [l for l in read_terminals(path) if l and l != app_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".xdg-terminals.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join([app_id] + rest) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def status(env):
    apps = entries(env)
    defaults = read_defaults(config_home(env) / "mimeapps.list")
    out = [terminal_status(env, apps)]
    for key, label, mimes in CATEGORIES:
        probe = mimes[0]
        cands = sorted(({"id": i, "name": e["name"], "icon": e["icon"]} for i, e in apps.items() if probe in e["mime"]),
                       key=lambda c: c["name"].lower())
        names = [c["name"] for c in cands]
        for c in cands:                                   # two entries with one name (zathura's): show which is which
            if names.count(c["name"]) > 1:
                c["name"] += f" ({c['id'].removesuffix('.desktop')})"
        current = next((i for i in defaults.get(probe, []) if i in apps), "")
        out.append({"key": key, "label": label, "current": current, "candidates": cands})
    return out


def set_default(env, key, app_id):
    if key == TERMINAL[0]:
        return set_terminal(env, app_id, entries(env))
    cat = next((c for c in CATEGORIES if c[0] == key), None)
    if cat is None:
        raise ValueError(f"no such category: {key}")
    apps = entries(env)
    if app_id not in apps:
        raise ValueError(f"no such app: {app_id}")
    if cat[2][0] not in apps[app_id]["mime"]:
        raise ValueError(f"{apps[app_id]['name']} cannot open {cat[1].lower()}")
    write_defaults(config_home(env) / "mimeapps.list", {m: app_id for m in cat[2]})


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    if argv[:1] == ["status"] and len(argv) == 1:
        print(json.dumps(status(env)))
        return 0
    if argv[:1] == ["set"] and len(argv) == 3:
        try:
            set_default(env, argv[1], argv[2] if argv[2].endswith(".desktop") else argv[2] + ".desktop")
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    print("usage: bbkos-defaults status | set CATEGORY DESKTOP_ID", file=sys.stderr)
    return 2
