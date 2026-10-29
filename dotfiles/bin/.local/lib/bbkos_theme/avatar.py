"""The lock screen avatar copy in <avatar_dir>/avatar-<hash>.<ext> (`bbkos-theme avatar set FILE`).

A copy, like the wallpaper, so a moved or deleted original cannot break the lock screen; `lock.avatar` holds its path
("" = the picture shipped with the dotfiles, ~/.config/hypr/lock-avatar.png). The name carries the first 12 hex digits of
the image's SHA-256, so a new picture is a new path: Qt's image cache in the settings preview and hyprlock both load it
fresh. The shipped picture is a Stow link into the repo, so it is never written to. Older copies are removed after a
successful change.
"""
import hashlib
import os
import re
from pathlib import Path

EXTENSIONS = ("png", "jpg", "jpeg", "webp")     # what hyprlock's image widget and Qt both read
MAX_BYTES = 10 * 1024 * 1024
NAME = re.compile(r"^avatar-[0-9a-f]{12}\.(png|jpg|jpeg|webp)$")


class AvatarError(Exception):
    pass


def default_dir(env=None):
    env = os.environ if env is None else env
    return Path(env.get("BBKOS_AVATAR_DIR") or Path.home() / ".local/share/bbkos/avatar")


def copy_in(src, avatar_dir):
    """Copy src into avatar_dir under its content name (atomic: a temp file, fsynced, then renamed). Returns the path."""
    src = Path(src).absolute()
    ext = src.suffix[1:].lower()
    if ext not in EXTENSIONS:
        raise AvatarError(f"{src.name}: not a supported image type ({', '.join(EXTENSIONS)})")
    try:
        if not src.is_file():
            raise AvatarError(f"{src.name}: not a regular file")
        if src.stat().st_size > MAX_BYTES:
            raise AvatarError(f"{src.name}: too large (cap {MAX_BYTES // (1024 * 1024)} MB)")
        data = src.read_bytes()
    except OSError as e:
        raise AvatarError(f"{src.name}: {e.strerror or e}") from e
    if len(data) > MAX_BYTES:                                      # grew after the check
        raise AvatarError(f"{src.name}: too large (cap {MAX_BYTES // (1024 * 1024)} MB)")
    avatar_dir = Path(avatar_dir).absolute()
    final = avatar_dir / f"avatar-{hashlib.sha256(data).hexdigest()[:12]}.{ext}"
    tmp = avatar_dir / f".{final.name}.tmp"
    try:
        avatar_dir.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise AvatarError(f"cannot copy {src.name}: {e.strerror or e}") from e
    return final


def remove_others(avatar_dir, keep=None):
    """Delete every avatar-*.<ext> copy except `keep` (a path or None). Only names this module makes are touched."""
    avatar_dir = Path(avatar_dir)
    if not avatar_dir.is_dir():
        return
    for p in avatar_dir.iterdir():
        if NAME.match(p.name) and p.is_file() and (keep is None or p != Path(keep)):
            p.unlink()
