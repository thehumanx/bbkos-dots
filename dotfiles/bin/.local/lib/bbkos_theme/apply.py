"""settings -> palette -> rendered files -> atomic swap -> reload.

Everything is rendered in memory first. Then every temp file is written and
fsynced next to its target, and only when all of them exist is each target
replaced with os.replace (per file: Quickshell watches these paths). A
failure at any point before that leaves the previous theme, settings.json and
the wallpaper exactly as they were. Replace order: the old stamp is removed,
then the generated files and palette.json, the new stamp, the wallpaper copy
(the old one moves to previous.<ext>), settings.json last; a failure among the
replaces leaves a mix that `status` reports as not fresh, never the old
wallpaper copy overwritten with settings.json still old. One exception: when
the wallpaper replace or the settings.json replace fails and the new image has
the same extension as the old one, the settings hash is unchanged, so `status`
can read `fresh: yes` over the new image's colours; `bbkos-theme apply`
repairs it (see theme.md, section 6). One flock on <state_dir>/apply.lock
serialises applies; a waiting apply reads settings after it gets the lock, so
the latest settings win.
"""
import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path

from . import a11y
from . import camera as CAM
from . import keybind_actions as KA
from . import keybinds as K
from . import keybinds_cli as KC
from . import palette as P
from . import reload as R
from . import render
from . import settings as S
from . import wallpaper as W

GENERATED = ("clipboard.conf", "colors.json", "hypr-binds.lua", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf", "gtk.css")
PALETTE = "palette.json"
STAMP = "stamp.json"
LOCK = "apply.lock"
ONLY = (None, "shape", "colors")
_HEX = re.compile(r"^#[0-9a-f]{6}$")


class ApplyError(Exception):
    pass


def _why(e):
    return e.strerror or str(e) if isinstance(e, OSError) else str(e)


@contextmanager
def locked(state_dir):
    state_dir = Path(state_dir)
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(state_dir / LOCK, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    except OSError as e:
        raise ApplyError(f"cannot lock {state_dir / LOCK}: {_why(e)}") from e
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # releases the lock


def colour_inputs(s, stat_path=None):
    """What the palette depends on. stat_path: where the wallpaper bytes are
    now (a staged copy) when it differs from the recorded path."""
    path = s["wallpaper"]["path"]
    wp = None
    if path:
        try:
            st = os.stat(stat_path or path)
            if os.path.isfile(stat_path or path):
                wp = {"path": path, "mtime_ns": st.st_mtime_ns, "size": st.st_size}
        except OSError:
            pass
    c = s["colors"]
    return {"wallpaper": wp, "mode": c["mode"], "scheme": c["scheme"],
            "sourceIndex": c["sourceIndex"], "contrast": c["contrast"]}


def read_stored(state_dir):
    """palette.json as {"inputs", "palette"}, or None when missing or unusable."""
    try:
        doc = json.loads((Path(state_dir) / PALETTE).read_text(encoding="utf-8"))
        inputs, pal = doc["inputs"], doc["palette"]
        if (isinstance(inputs, dict) and isinstance(pal, dict) and set(pal) == set(P.ROLES)
                and all(isinstance(v, str) and _HEX.match(v) for v in pal.values())):
            return {"inputs": inputs, "palette": pal}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _wallpaper_cell(path, state_dir):
    """a11y.measure_wallpaper, reused from palette.json's "lockCell" while the image file is unchanged (path, mtime, size):
    decoding a large wallpaper was most of every apply (0.6 s of 0.68 s for a 4096x2048 PNG, 2026-10-28).
    Returns (cell or None, the record to store or None)."""
    try:
        st = os.stat(path)
    except OSError:
        return None, None
    key = {"path": str(path), "mtime_ns": st.st_mtime_ns, "size": st.st_size}
    if state_dir is not None:
        try:
            rec = json.loads((Path(state_dir) / PALETTE).read_text(encoding="utf-8"))["lockCell"]
            cell = rec["cell"]
            if (rec["image"] == key and isinstance(cell, list) and len(cell) == 3
                    and all(type(v) is int and 0 <= v <= 255 for v in cell)):
                return tuple(cell), rec
        except (OSError, ValueError, KeyError, TypeError):
            pass
    cell = a11y.measure_wallpaper(path)
    return cell, ({"image": key, "cell": list(cell)} if cell is not None else None)


def _lock_brightness(s, image, state_dir=None):
    """(The lock screen brightness the wallpaper allows (a11y.lock_brightness), or None when there is no wallpaper or it
    cannot be measured; the measure record for palette.json). `image` is the staged copy while a new wallpaper is being
    applied."""
    path = image or s["wallpaper"]["path"]
    lk = s["lock"]
    if not lk["autoDim"] or not path or not os.path.isfile(path):
        return None, None
    cell, rec = _wallpaper_cell(path, state_dir)
    return a11y.lock_brightness(lk["brightness"], cell, lk["textColor"]), rec


def build(s, state_dir, *, only=None, runner=None, image=None, keybinds_path=None):
    """Render in memory. Returns ({filename: text}, palette.json text, warnings)."""
    warns = []
    inputs = colour_inputs(s, image)
    if s["wallpaper"]["path"] and inputs["wallpaper"] is None:
        warns.append(f"wallpaper {s['wallpaper']['path']} missing, using the fallback colour")
    stored = read_stored(state_dir)
    if stored and only == "shape":
        pal, inputs = stored["palette"], stored["inputs"]  # palette keeps its own inputs
    elif stored and only is None and stored["inputs"] == inputs:
        pal = stored["palette"]
    else:
        img = (image or s["wallpaper"]["path"]) if inputs["wallpaper"] else None
        c = s["colors"]
        try:
            pal = P.generate(img, mode=c["mode"], scheme=c["scheme"],
                             source_index=c["sourceIndex"], contrast=c["contrast"], runner=runner)
        except P.PaletteError as e:
            raise ApplyError(str(e)) from e
    s = S.effective(s)      # grid mode: the renderers see the grid values (settings.GRID_OVERRIDES); the saved ones stay
    t = render.tokens(pal, s)
    # same load path as bbkos-keybinds; a broken keybinds.json falls back to the shipped defaults (with a
    # warning) so a theme apply never depends on the bind file being valid
    binds, kb_warns = K.load_binds(keybinds_path or KC.paths({})[0], KC.DEFAULTS, actions=set(KA.ACTIONS))
    warns += kb_warns
    lock_b, lock_rec = _lock_brightness(s, image, state_dir)
    texts = {"clipboard.conf": render.render_clipboard_conf(s),
             "colors.json": render.render_colors_json(t, s),
             "hypr-binds.lua": K.render_lua(binds),
             "hypr-theme.lua": render.render_hypr_lua(t, s),
             "hypridle.conf": render.render_hypridle(s),
             "hyprlock.conf": render.render_hyprlock(s, lock_b),
             "kitty-theme.conf": render.render_kitty_conf(t, s),
             "gtk.css": render.render_gtk_css(t, s)}
    doc = {"inputs": inputs, "palette": pal}
    if lock_rec is not None:
        doc["lockCell"] = lock_rec
    pal_text = json.dumps(doc, indent=2) + "\n"
    return texts, pal_text, warns


def settings_hash(s):
    """sha256 of the canonical text of validated settings (cosmetic edits of
    the file do not change it)."""
    return hashlib.sha256(S.dumps(s).encode("utf-8")).hexdigest()


def stamp_text(s):
    """stamp.json: which settings the generated files were rendered from."""
    return json.dumps({
        "settings_sha256": settings_hash(s),
        "files": sorted(GENERATED + (PALETTE,)),
        "applied": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }, indent=2) + "\n"


def read_stamp_hash(state_dir):
    """The stamp's settings hash, or None when missing or unusable."""
    try:
        h = json.loads((Path(state_dir) / STAMP).read_text(encoding="utf-8"))["settings_sha256"]
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return None
    return h if isinstance(h, str) else None


def _unlink(p):
    try:
        os.unlink(p)
    except OSError:
        pass


def stage_files(pairs):
    """Write every (target, text) to a fsynced temp file beside the resolved
    target. All or nothing: on any error the temps are removed and ApplyError
    raised. Returns [(temp, target)] for commit_files."""
    staged = []
    try:
        for target, text in pairs:
            real = Path(os.path.realpath(target))  # keep symlinks (Stow) intact
            try:
                real.parent.mkdir(parents=True, exist_ok=True)
                try:
                    mode = os.stat(real).st_mode & 0o777
                except FileNotFoundError:
                    mode = 0o644
                fd, tmp = tempfile.mkstemp(dir=real.parent, prefix=f".{real.name}.", suffix=".tmp")
                staged.append((tmp, real))
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                    os.fchmod(f.fileno(), mode)
                    os.fsync(f.fileno())
            except OSError as e:
                raise ApplyError(f"cannot write {real}: {_why(e)}") from e
    except BaseException:
        for tmp, _ in staged:
            _unlink(tmp)
        raise
    return staged


def commit_files(staged):
    for i, (tmp, real) in enumerate(staged):
        try:
            os.replace(tmp, real)
        except OSError as e:
            for t, _ in staged[i:]:
                _unlink(t)
            raise ApplyError(f"cannot replace {real}: {_why(e)}") from e


def _drop_stamp(state_dir, staged):
    """Remove the old stamp just before the first replace (everything is staged
    already): a half-finished commit then reads as "unknown", never "fresh"."""
    try:
        os.unlink(Path(os.path.realpath(state_dir / STAMP)))
    except FileNotFoundError:
        pass
    except OSError as e:
        for tmp, _ in staged:
            _unlink(tmp)
        raise ApplyError(f"cannot remove old {STAMP}: {_why(e)}") from e


def _keybinds_path(settings_path):
    """BBKOS_KEYBINDS, else keybinds.json beside settings.json (the CLI default dir)."""
    env = os.environ.get("BBKOS_KEYBINDS")
    return Path(env) if env else Path(settings_path).parent / "keybinds.json"


def _hyprsunset_conf_path(settings_path):
    """Where hyprsunset reads its profiles: BBKOS_HYPRSUNSET_CONF, else ~/.config/hypr/hyprsunset.conf, only for the real
    ~/.config/bbkos/settings.json (as _omasnap_conf_path). None = do not write."""
    env = os.environ.get("BBKOS_HYPRSUNSET_CONF")
    if env:
        return Path(env)
    sp = Path(settings_path)
    if sp.parent.name == "bbkos":
        return sp.parent.parent / "hypr" / "hyprsunset.conf"
    return None


def _omasnap_conf_path(settings_path):
    """Where omasnap reads its config: BBKOS_OMASNAP_CONF, else ~/.config/omasnap/omasnap.conf, but only when the
    settings file is the real ~/.config/bbkos/settings.json (a settings file somewhere else, as in the tests, must not
    write into the home directory). None = do not write."""
    env = os.environ.get("BBKOS_OMASNAP_CONF")
    if env:
        return Path(env)
    sp = Path(settings_path)
    if sp.parent.name == "bbkos":
        return sp.parent.parent / "omasnap" / "omasnap.conf"
    return None


def _settings_file_ok(path):
    try:
        return isinstance(json.loads(Path(path).read_text(encoding="utf-8")), dict)
    except (OSError, ValueError, RecursionError):
        return False


def _run(settings_path, state_dir, share_dir, *, mutate=None, wallpaper_src=None,
         clear_wallpaper=False, only=None, out_dir=None, reload=True, runner=None, force_reload=False):
    if only not in ONLY:
        raise ApplyError(f"--only must be shape or colors, not {only!r}")
    settings_path, state_dir, share_dir = (Path(p).absolute() for p in
                                           (settings_path, state_dir, share_dir))
    if os.path.islink(settings_path) and not os.path.exists(settings_path):
        # writing through it would recreate the link target's directories (inside the repo)
        raise ApplyError(f"settings.json is a broken link to {os.readlink(settings_path)}: re-stow "
                         f"(stow -R --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ bbkos-settings)")
    s, warns = S.load(settings_path)
    changed = mutate is not None or wallpaper_src is not None
    promote = changed or _settings_file_ok(settings_path)
    if mutate is not None:
        try:
            s = mutate(s)
        except ValueError as e:
            raise ApplyError(str(e)) from e
        s, w = S.validate(s)
        warns += w
    staged_wp = final_wp = None
    if wallpaper_src is not None:
        try:
            staged_wp, final_wp = W.stage(wallpaper_src, share_dir)
        except W.WallpaperError as e:
            raise ApplyError(str(e)) from e
        s["wallpaper"]["path"] = str(final_wp)
    try:
        texts, pal_text, w = build(s, state_dir, only=only, runner=runner, image=staged_wp,
                                  keybinds_path=_keybinds_path(settings_path))
        warns += w
        if out_dir is not None:
            out_dir = Path(out_dir)
            pairs = [(out_dir / n, t) for n, t in texts.items()] + [(out_dir / STAMP, stamp_text(s))]
            commit_files(stage_files(pairs))
            return warns
        # Only the generated files whose text changes are written: Hyprland's autoreload watches the files it loaded, and a
        # rewritten but identical hypr-theme.lua reloaded it (every window re-applied) for a bar setting (2026-10-31). The
        # same set decides which consumers reload (reload.reload_all).
        written = {n for n, t in texts.items() if _read_text(state_dir / n) != t}
        pairs = [(state_dir / n, t) for n, t in texts.items() if n in written]
        conf = _omasnap_conf_path(settings_path)
        if conf is not None:
            conf.parent.mkdir(parents=True, exist_ok=True)
            pairs.append((conf, render.render_omasnap_conf(s)))
        sun = _hyprsunset_conf_path(settings_path)
        if sun is not None:
            sun.parent.mkdir(parents=True, exist_ok=True)
            pairs.append((sun, render.render_hyprsunset_conf(s)))
        pairs += [(state_dir / PALETTE, pal_text), (state_dir / STAMP, stamp_text(s))]
        if changed:
            pairs.append((settings_path, S.dumps(s)))
        staged = stage_files(pairs)
        _drop_stamp(state_dir, staged)
        if staged_wp is None:
            commit_files(staged)  # the new stamp is replaced after the generated files, settings.json last
        else:
            # The wallpaper copy is replaced only after the generated files and the new stamp
            # (a failure there leaves the old copy untouched), just before settings.json.
            commit_files(staged[:-1])
            try:
                retired = W.install(staged_wp, final_wp, share_dir)
            except OSError as e:
                _unlink(staged[-1][0])
                raise ApplyError(f"cannot install wallpaper: {_why(e)}") from e
            try:
                commit_files(staged[-1:])
            except BaseException:
                W.restore_retired(retired, installed=final_wp)
                raise
    except BaseException:
        if staged_wp is not None:
            W.discard(staged_wp)
        raise
    try:
        if final_wp is not None:
            W.remove_others(share_dir, keep=final_wp)
        if clear_wallpaper and not s["wallpaper"]["path"]:
            W.clear_wallpaper(share_dir)  # the old copy becomes previous.<ext>
    except OSError as e:
        warns.append(f"cannot tidy the wallpaper folder {share_dir}: {_why(e)}")
    if promote:
        try:
            S.promote_backup(settings_path)
        except OSError as e:
            warns.append(f"cannot update settings backup: {_why(e)}")
    if reload:
        warns += R.reload_all(state_dir, settings=s, changed=None if force_reload else written)
        if _owner_home():                  # the camera is the owner's hardware, not a temp home's (tests/shell)
            try:
                warns += [f"camera: {w}" for w in CAM.apply(s["camera"])]
            except CAM.CameraError:
                pass  # no camera (or no v4l2-ctl): nothing to set
    return warns


def apply(settings_path, state_dir, share_dir, *, only=None, out_dir=None, reload=True,
          runner=None):
    """Render settings into state_dir (or out_dir: a dry run, no lock, no
    reload) and reload consumers. Returns warnings; raises ApplyError."""
    if out_dir is not None:
        return _run(settings_path, state_dir, share_dir, only=only, out_dir=out_dir,
                    reload=False, runner=runner)
    with locked(state_dir):
        return _run(settings_path, state_dir, share_dir, only=only, reload=reload, runner=runner, force_reload=True)


def _read_text(path):
    """A file's text, or None when it is missing or unreadable (then it counts as changed)."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _owner_home():
    """True when HOME is the user's own home (pwd), as the GTK, cursor, idle and night-light reloads check."""
    import pwd
    home = os.environ.get("HOME", "")
    return bool(home) and os.path.realpath(home) == os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir)


def update(settings_path, state_dir, share_dir, mutate=None, *, wallpaper_src=None,
           clear_wallpaper=False, reload=True, runner=None):
    """Change settings and apply, under the lock. mutate(settings) -> settings
    runs on settings read after the lock is taken. settings.json is written
    only together with a fully successful apply."""
    with locked(state_dir):
        return _run(settings_path, state_dir, share_dir, mutate=mutate,
                    wallpaper_src=wallpaper_src, clear_wallpaper=clear_wallpaper,
                    reload=reload, runner=runner)
