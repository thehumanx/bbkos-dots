"""Startup apps (the settings page "Startup apps", docs/modules/startup.md): the freedesktop autostart folder.

Apps in ~/.config/autostart are started at login by systemd-xdg-autostart-generator (uwsm runs the session under systemd).
This module lists the user entries and the system ones (/etc/xdg/autostart), switches one off or on, adds an installed app
and removes one. The XDG way, as COSMIC's and GNOME's startup pages do it:
  - an entry with Hidden=true does not start;
  - a user file with a system entry's name overrides it, so a system entry is switched off by a user file that only says
    Hidden=true, and on again by deleting that file.

    bbkos-autostart status | add ID | remove ID | enable ID | disable ID      (ID = desktop file name, firefox.desktop)
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from . import defaultapps as D

_ID = re.compile(r"^[A-Za-z0-9._@+-]{1,120}\.desktop$")


def user_dir(env):
    return D.config_home(env) / "autostart"


def system_dirs(env):
    dirs = (env.get("XDG_CONFIG_DIRS") or "/etc/xdg").split(":")
    return [Path(d) / "autostart" for d in dirs if d]


def check_id(app_id):
    if not _ID.match(app_id):
        raise ValueError(f"not a desktop file name: {app_id!r}")
    return app_id


def read(path):
    """{name, exec, icon, hidden} of an autostart entry, or None when it is not a readable application entry."""
    name = exec_ = icon = None
    hidden = in_main = False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            in_main = line == "[Desktop Entry]"
            continue
        if not in_main or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k == "Name" and name is None:
            name = v
        elif k == "Exec" and exec_ is None:
            exec_ = v
        elif k == "Icon":
            icon = v
        elif k == "Hidden":
            hidden = v.strip().lower() == "true"
        elif k == "Type" and v != "Application":
            return None
    return {"name": name or path.stem, "exec": exec_ or "", "icon": icon or "", "hidden": hidden}


def _system_entry(env, app_id):
    for d in system_dirs(env):
        if (d / app_id).is_file():
            return d / app_id
    return None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _set_hidden(text, hidden):
    """text with the Hidden key of the [Desktop Entry] group set (or removed when not hidden)."""
    out, in_main, done = [], False, False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            if in_main and hidden and not done:
                out.append("Hidden=true")
                done = True
            in_main = s == "[Desktop Entry]"
        elif in_main and s.split("=", 1)[0] == "Hidden":
            if hidden and not done:
                out.append("Hidden=true")
                done = True
            continue
        out.append(line)
    if in_main and hidden and not done:
        out.append("Hidden=true")
    return "\n".join(out) + "\n"


def status(env):
    seen = {}
    for d in reversed(system_dirs(env)):
        if d.is_dir():
            for p in sorted(d.glob("*.desktop")):
                e = read(p)
                if e:
                    seen[p.name] = {**e, "source": "system"}
    u = user_dir(env)
    if u.is_dir():
        for p in sorted(u.glob("*.desktop")):
            e = read(p)
            if e:
                seen[p.name] = {**e, "source": "override" if p.name in seen else "user"}
    entries = [{"id": i, "name": e["name"], "exec": e["exec"], "icon": e["icon"], "enabled": not e["hidden"],
                "source": e["source"]} for i, e in seen.items()]
    entries.sort(key=lambda e: (e["source"] != "user", e["name"].lower()))
    apps = [{"id": i, "name": e["name"], "icon": e["icon"]} for i, e in D.entries(env).items()
            if not e["nodisplay"] and i not in seen]
    apps.sort(key=lambda a: a["name"].lower())
    return {"entries": entries, "apps": apps}


def add(env, app_id):
    check_id(app_id)
    dest = user_dir(env) / app_id
    if dest.is_file():
        return enable(env, app_id)
    for d in D.app_dirs(env):
        src = d / app_id
        if src.is_file() and D.read_entry(src):
            text = src.read_text(encoding="utf-8", errors="replace")
            _write(dest, _set_hidden(text, False))
            return None
    raise ValueError(f"no such app: {app_id}")


def disable(env, app_id):
    check_id(app_id)
    dest = user_dir(env) / app_id
    if dest.is_file():
        _write(dest, _set_hidden(dest.read_text(encoding="utf-8", errors="replace"), True))
        return
    system = _system_entry(env, app_id)
    if system is None:
        raise ValueError(f"no such startup entry: {app_id}")
    e = read(system) or {"name": app_id}
    _write(dest, f"[Desktop Entry]\nType=Application\nName={e['name']}\nHidden=true\n")


def enable(env, app_id):
    check_id(app_id)
    dest = user_dir(env) / app_id
    if _system_entry(env, app_id) is not None:
        if dest.is_file():
            dest.unlink()                                  # the user file only overrode the system entry
        return
    if not dest.is_file():
        raise ValueError(f"no such startup entry: {app_id}")
    _write(dest, _set_hidden(dest.read_text(encoding="utf-8", errors="replace"), False))


def remove(env, app_id):
    check_id(app_id)
    dest = user_dir(env) / app_id
    if _system_entry(env, app_id) is not None:
        raise ValueError("a system startup entry cannot be removed, only switched off")
    if not dest.is_file():
        raise ValueError(f"no such startup entry: {app_id}")
    dest.unlink()


def main(argv, env=None):
    env = dict(os.environ if env is None else env)
    if argv == ["status"]:
        print(json.dumps(status(env)))
        return 0
    actions = {"add": add, "remove": remove, "enable": enable, "disable": disable}
    if len(argv) == 2 and argv[0] in actions:
        try:
            actions[argv[0]](env, argv[1] if argv[1].endswith(".desktop") else argv[1] + ".desktop")
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    print("usage: bbkos-autostart status | add ID | remove ID | enable ID | disable ID", file=sys.stderr)
    return 2
