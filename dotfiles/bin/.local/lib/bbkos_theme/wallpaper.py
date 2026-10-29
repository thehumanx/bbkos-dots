"""The wallpaper copy in <share_dir>/current.<ext>.

A copy, so a deleted original or an unplugged drive cannot break the desktop.
Staging is separate from committing so the caller can build the new theme from
the staged copy and only then make it current.

Replacing or clearing the wallpaper moves the old copy to previous.<ext>
(replacing any older previous.*): a one-step undo, never read by the theme
(`bbkos-theme wallpaper set -- <share_dir>/previous.<ext>` brings it back).
"""
import os
from pathlib import Path

EXTENSIONS = ("png", "jpg", "jpeg", "webp", "bmp", "gif")
MAX_BYTES = 40 * 1024 * 1024
_CHUNK = 1 << 20


class WallpaperError(Exception):
    pass


def check_source(src):
    """Return (absolute path, lowercase extension). Raises WallpaperError."""
    src = Path(src).absolute()
    ext = src.suffix[1:].lower()
    if ext not in EXTENSIONS:
        raise WallpaperError(f"{src.name}: not a supported image type "
                             f"({', '.join(EXTENSIONS)})")
    try:
        st = src.stat()
    except OSError as e:
        raise WallpaperError(f"{src.name}: {e.strerror or e}") from e
    if not os.path.isfile(src):
        raise WallpaperError(f"{src.name}: not a regular file")
    if st.st_size > MAX_BYTES:
        raise WallpaperError(f"{src.name}: too large ({st.st_size} bytes, cap {MAX_BYTES})")
    return src, ext


def final_path(share_dir, ext):
    return Path(share_dir).absolute() / f"current.{ext}"


def stage(src, share_dir):
    """Copy src to <share_dir>/current.new.<ext> (fsynced). Returns (staged, final).

    The staged name keeps the image extension last: matugen picks its decoder
    from the extension and, for an undecodable file named *.new, reports
    "`.new` was not recognized as an image format" instead of the real cause."""
    src, ext = check_source(src)
    final = final_path(share_dir, ext)
    staged = final.with_name(f"current.new.{ext}")
    try:
        final.parent.mkdir(parents=True, exist_ok=True)
        with open(src, "rb") as fin, open(staged, "wb") as fout:
            copied = 0
            while chunk := fin.read(_CHUNK):
                copied += len(chunk)
                if copied > MAX_BYTES:  # grew after the check
                    raise WallpaperError(f"{src.name}: too large (cap {MAX_BYTES})")
                fout.write(chunk)
            fout.flush()
            os.fsync(fout.fileno())
    except OSError as e:
        discard(staged)
        raise WallpaperError(f"cannot copy {src.name}: {e.strerror or e}") from e
    except BaseException:
        discard(staged)
        raise
    return staged, final


def discard(staged):
    try:
        os.unlink(staged)
    except FileNotFoundError:
        pass


def _copies(share_dir, stem):
    """<share_dir>/<stem>.<ext> files (ext a supported image type). current.new.*
    (a staged copy) has the stem "current.new" and never matches "current"."""
    d = Path(share_dir)
    if not d.is_dir():
        return []
    return [p for p in d.iterdir()
            if p.stem == stem and p.suffix[1:] in EXTENSIONS and p.is_file()]


def retire_current(share_dir):
    """Move the current copy (the newest current.<ext>) to previous.<ext> and
    drop any other previous.*. Returns (old current path, previous path) for
    restore_retired, or None when there is no current copy. Raises OSError."""
    cur = _copies(share_dir, "current")
    if not cur:
        return None
    old = max(cur, key=lambda p: p.stat().st_mtime_ns)
    prev = old.with_name("previous" + old.suffix)
    os.replace(old, prev)
    for p in _copies(share_dir, "previous"):
        if p.name != prev.name:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
    return old, prev


def restore_retired(retired, installed=None):
    """Undo retire_current (best effort): drop the newly installed copy, move
    previous.<ext> back to its current name."""
    if installed is not None and (retired is None or Path(installed) != retired[0]):
        discard(installed)
    if retired is not None:
        try:
            os.replace(retired[1], retired[0])
        except OSError:
            pass


def install(staged, final, share_dir):
    """Make the staged copy current, the old one previous.<ext>. Returns the
    retire_current result. Raises OSError with everything put back."""
    retired = retire_current(share_dir)
    try:
        os.replace(staged, final)
    except OSError:
        restore_retired(retired)
        raise
    return retired


def commit(staged, final):
    """Install the staged copy, then drop every other current.* file."""
    install(staged, final, final.parent)
    remove_others(final.parent, keep=final)


def remove_others(share_dir, keep=None):
    """Delete stale current.* files (old extensions, staged leftovers) except
    keep. previous.* is never touched."""
    share_dir = Path(share_dir)
    if not share_dir.is_dir():
        return
    for p in share_dir.glob("current.*"):
        if keep is None or p.name != Path(keep).name:
            try:
                p.unlink()
            except FileNotFoundError:
                pass


def set_wallpaper(src, share_dir):
    """Copy src in as the current wallpaper. Returns the copy's path."""
    staged, final = stage(src, share_dir)
    try:
        commit(staged, final)
    except OSError as e:
        discard(staged)
        raise WallpaperError(f"cannot install wallpaper: {e.strerror or e}") from e
    return final


def clear_wallpaper(share_dir):
    """No current copy: the newest moves to previous.<ext>, stale ones go."""
    retire_current(share_dir)
    remove_others(share_dir)
