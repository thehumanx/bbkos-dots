import errno
import json
import os
import signal
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import apply as A  # noqa: E402
from bbkos_theme import reload as R  # noqa: E402
from bbkos_theme import settings as S  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
FAKE_BIN = FIX / "fake-bin"
SAMPLE = (FIX / "matugen-sample.json").read_text()
GENERATED = ("clipboard.conf", "colors.json", "gtk.css", "hypr-binds.lua", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf", "palette.json")


def ok_runner(calls):
    def run(argv):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=SAMPLE, stderr="")
    return run


def fail_runner(argv):
    return SimpleNamespace(returncode=1, stdout="", stderr="Error: \n   0: Failed to get source color.\n")


def snapshot(d):
    return {p.name: p.read_bytes() for p in sorted(Path(d).iterdir()) if p.is_file()}


class Env:
    """Temp settings/state/share dirs."""

    def __init__(self, tc):
        self.tmp = tempfile.TemporaryDirectory()
        tc.addCleanup(self.cleanup)
        base = Path(self.tmp.name)
        self.settings = base / "config/settings.json"
        self.state = base / "state"
        self.share = base / "share"
        self.settings.parent.mkdir(parents=True)
        S.save_atomic(self.settings, S.DEFAULTS)

    def cleanup(self):
        for p in (self.state, Path(self.tmp.name)):
            if p.exists():
                os.chmod(p, 0o755)
        self.tmp.cleanup()

    def apply(self, **kw):
        kw.setdefault("reload", False)
        return A.apply(self.settings, self.state, self.share, **kw)


class ApplyTest(unittest.TestCase):
    def test_apply_writes_the_omasnap_config_only_where_told_to(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        self.assertFalse(any(Path(e.tmp.name).rglob("omasnap.conf")))     # a settings file outside ~/.config/bbkos: no write
        conf = Path(e.tmp.name) / "omasnap/omasnap.conf"
        with mock.patch.dict(os.environ, {"BBKOS_OMASNAP_CONF": str(conf)}):
            e.apply(runner=ok_runner([]))
            self.assertIn("autosave = true", conf.read_text())
            s, _ = S.load(e.settings)
            S.save_atomic(e.settings, S.set_value(s, "capture.autosave", "false"))
            e.apply(runner=ok_runner([]))
            self.assertIn("autosave = false", conf.read_text())
        real = Path(e.tmp.name) / "home/.config"
        (real / "bbkos").mkdir(parents=True)
        S.save_atomic(real / "bbkos/settings.json", S.DEFAULTS)
        A.apply(real / "bbkos/settings.json", e.state, e.share, reload=False, runner=ok_runner([]))
        self.assertTrue((real / "omasnap/omasnap.conf").is_file())         # the real layout: written beside bbkos

    def test_apply_writes_all_files_and_palette_inputs(self):
        e = Env(self)
        calls = []
        e.apply(runner=ok_runner(calls))
        for name in GENERATED:
            self.assertTrue((e.state / name).is_file(), name)
        doc = json.loads((e.state / "colors.json").read_text())
        self.assertEqual(doc["shell"]["gap"], 12)
        pal = json.loads((e.state / "palette.json").read_text())
        self.assertEqual(pal["inputs"]["mode"], "dark")
        self.assertEqual(pal["inputs"]["scheme"], "tonal-spot")
        self.assertIsNone(pal["inputs"]["wallpaper"])
        self.assertEqual(len(pal["palette"]), 19)
        self.assertEqual(len(calls), 1)
        # no temp files left behind
        self.assertEqual(sorted(p.name for p in e.state.iterdir()),
                         sorted(GENERATED + ("apply.lock", "stamp.json")))

    def test_apply_writes_hyprlock_conf(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        text = (e.state / "hyprlock.conf").read_text()
        self.assertIn("background {", text)
        self.assertIn("input-field {", text)
        self.assertIn("position = 0, -70", text)

    def test_apply_writes_hypr_binds_lua(self):
        e = Env(self)
        warns = e.apply(runner=ok_runner([]))
        text = (e.state / "hypr-binds.lua").read_text()
        self.assertIn('hl.bind(', text)
        self.assertIn('"SUPER + Q"', text)
        self.assertEqual(warns, [])

    def test_apply_renders_user_keybinds_json(self):
        e = Env(self)
        kb = e.settings.parent / "keybinds.json"
        kb.write_text(json.dumps({"version": 1, "binds": [
            {"id": "term", "keys": {"mods": ["SUPER"], "key": "T"},
             "action": {"type": "preset", "id": "launch-terminal"},
             "flags": {"locked": False, "repeating": False, "mouse": False}, "enabled": True}]}))
        e.apply(runner=ok_runner([]))
        text = (e.state / "hypr-binds.lua").read_text()
        self.assertIn('"SUPER + T"', text)
        self.assertNotIn('"SUPER + Q"', text)

    def test_broken_keybinds_json_writes_defaults_and_warns(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        defaults = (e.state / "hypr-binds.lua").read_bytes()
        (e.settings.parent / "keybinds.json").write_text("{not json")
        warns = e.apply(runner=ok_runner([]))
        self.assertEqual((e.state / "hypr-binds.lua").read_bytes(), defaults)
        self.assertTrue(any("keybinds.json" in w for w in warns), warns)
        self.assertTrue((e.state / "colors.json").is_file())

    def test_apply_reuses_palette_when_colour_inputs_unchanged(self):
        e = Env(self)
        calls = []
        e.apply(runner=ok_runner(calls))
        e.apply(runner=ok_runner(calls))
        self.assertEqual(len(calls), 1)
        s, _ = S.load(e.settings)
        S.save_atomic(e.settings, S.set_value(s, "colors.contrast", "0.5"))
        e.apply(runner=ok_runner(calls))
        self.assertEqual(len(calls), 2)
        e.apply(runner=ok_runner(calls), only="colors")
        self.assertEqual(len(calls), 3)

    def test_only_shape_does_not_run_matugen(self):
        e = Env(self)
        calls = []
        e.apply(runner=ok_runner(calls))
        s, _ = S.load(e.settings)
        s = S.set_value(s, "colors.mode", "light")
        S.save_atomic(e.settings, S.set_value(s, "shell.gap", "20"))
        e.apply(runner=ok_runner(calls), only="shape")
        self.assertEqual(len(calls), 1)
        self.assertEqual(json.loads((e.state / "colors.json").read_text())["shell"]["gap"], 20)

    def test_only_shape_runs_matugen_when_palette_missing_or_corrupt(self):
        e = Env(self)
        calls = []
        e.apply(runner=ok_runner(calls), only="shape")
        self.assertEqual(len(calls), 1)
        (e.state / "palette.json").write_text("{not json")
        e.apply(runner=ok_runner(calls), only="shape")
        self.assertEqual(len(calls), 2)
        (e.state / "palette.json").write_text(json.dumps({"inputs": {}, "palette": {"primary": "red"}}))
        e.apply(runner=ok_runner(calls), only="shape")
        self.assertEqual(len(calls), 3)

    def test_bad_only_value_raises(self):
        e = Env(self)
        with self.assertRaises(A.ApplyError):
            e.apply(runner=ok_runner([]), only="bogus")

    def test_apply_swaps_atomically_and_keeps_old_on_failure(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        before = snapshot(e.state)
        settings_before = e.settings.read_bytes()
        with self.assertRaises(A.ApplyError) as cm:
            e.apply(runner=fail_runner, only="colors")
        self.assertEqual(str(cm.exception), "Failed to get source color.")
        self.assertEqual(snapshot(e.state), before)
        self.assertEqual(e.settings.read_bytes(), settings_before)
        # update() path: candidate settings never reach settings.json
        with self.assertRaises(A.ApplyError):
            A.update(e.settings, e.state, e.share,
                     lambda s: S.set_value(s, "colors.contrast", "0.7"),
                     runner=fail_runner, reload=False)
        self.assertEqual(snapshot(e.state), before)
        self.assertEqual(e.settings.read_bytes(), settings_before)

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_apply_unwritable_state_dir_keeps_previous(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        before = snapshot(e.state)
        settings_before = e.settings.read_bytes()
        os.chmod(e.state, 0o500)
        with self.assertRaises(A.ApplyError) as cm:
            A.update(e.settings, e.state, e.share,
                     lambda s: S.set_value(s, "shell.gap", "20"),
                     runner=ok_runner([]), reload=False)
        msg = str(cm.exception)
        self.assertNotIn("\n", msg)
        self.assertIn("Permission denied", msg)
        os.chmod(e.state, 0o755)
        self.assertEqual(snapshot(e.state), before)
        self.assertEqual(e.settings.read_bytes(), settings_before)

    def test_apply_disk_full_mid_write_keeps_previous(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        before = snapshot(e.state)
        settings_before = e.settings.read_bytes()
        real_fsync = os.fsync
        n = {"calls": 0}

        def fsync(fd):
            n["calls"] += 1
            if n["calls"] == 3:
                raise OSError(errno.ENOSPC, "No space left on device")
            return real_fsync(fd)

        with mock.patch("os.fsync", fsync), self.assertRaises(A.ApplyError) as cm:
            A.update(e.settings, e.state, e.share,
                     lambda s: S.set_value(s, "shell.gap", "20"),
                     runner=ok_runner([]), reload=False)
        self.assertIn("No space left on device", str(cm.exception))
        self.assertEqual(snapshot(e.state), before)   # also: no temp files left
        self.assertEqual(e.settings.read_bytes(), settings_before)
        self.assertEqual(sorted(p.name for p in e.settings.parent.iterdir()),
                         ["settings.json", "settings.json.bak"])

    def test_dry_run_writes_only_out_dir(self):
        e = Env(self)
        out = Path(e.tmp.name) / "out"
        settings_before = e.settings.read_bytes()
        e.apply(runner=ok_runner([]), out_dir=out, reload=True)
        self.assertFalse(e.state.exists())
        self.assertFalse(e.share.exists())
        self.assertEqual(e.settings.read_bytes(), settings_before)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["clipboard.conf", "colors.json", "gtk.css", "hypr-binds.lua", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf", "stamp.json"])
        json.loads((out / "colors.json").read_text())

    def test_update_writes_settings_and_promotes_backup(self):
        e = Env(self)
        A.update(e.settings, e.state, e.share,
                 lambda s: S.set_value(s, "shell.gap", "21"), runner=ok_runner([]), reload=False)
        s = json.loads(e.settings.read_text())
        self.assertEqual(s["shell"]["gap"], 20)  # step 2 (round half to even)
        bak = e.settings.with_name("settings.json.bak")
        self.assertEqual(bak.read_text(), e.settings.read_text())
        self.assertEqual(json.loads((e.state / "colors.json").read_text())["shell"]["gap"], 20)

    def test_plain_apply_does_not_promote_corrupt_settings(self):
        e = Env(self)
        e.apply(runner=ok_runner([]))
        good = e.settings.read_text()
        bak = e.settings.with_name("settings.json.bak")
        bak.write_text(good)
        e.settings.write_text("{corrupt")
        warns = e.apply(runner=ok_runner([]))
        self.assertTrue(any("unreadable" in w for w in warns), warns)
        self.assertEqual(bak.read_text(), good)

    def test_settings_symlink_survives_update(self):
        e = Env(self)
        real = Path(e.tmp.name) / "repo/settings.json"
        real.parent.mkdir()
        S.save_atomic(real, S.DEFAULTS)
        e.settings.unlink()
        e.settings.symlink_to(real)
        A.update(e.settings, e.state, e.share,
                 lambda s: S.set_value(s, "shell.gap", "16"), runner=ok_runner([]), reload=False)
        self.assertTrue(e.settings.is_symlink())
        self.assertEqual(json.loads(real.read_text())["shell"]["gap"], 16)
        self.assertTrue(e.settings.with_name("settings.json.bak").is_file())
        self.assertFalse(real.with_name("settings.json.bak").exists())

    def test_settings_replace_failure_puts_old_wallpaper_copy_back(self):
        e = Env(self)
        src = Path(e.tmp.name) / "a.png"
        src.write_bytes(b"old-bytes")
        A.update(e.settings, e.state, e.share, wallpaper_src=src, reload=False, runner=ok_runner([]))
        settings_before = e.settings.read_bytes()
        src.write_bytes(b"new-bytes")
        real = A.commit_files

        def commit(staged):
            if any(Path(t).name == e.settings.name for _, t in staged):
                raise A.ApplyError("cannot replace settings.json: injected")
            return real(staged)

        with mock.patch.object(A, "commit_files", commit), self.assertRaises(A.ApplyError):
            A.update(e.settings, e.state, e.share, wallpaper_src=src, reload=False, runner=ok_runner([]))
        self.assertEqual(snapshot(e.share), {"current.png": b"old-bytes"})
        self.assertEqual(e.settings.read_bytes(), settings_before)

    def test_dangling_settings_link_is_an_error_and_creates_nothing(self):
        e = Env(self)
        base = Path(e.tmp.name)
        target = base / "repo/defaults/settings.json"
        e.settings.unlink()
        e.settings.symlink_to(target)
        for call in (lambda: e.apply(runner=ok_runner([])),
                     lambda: A.update(e.settings, e.state, e.share, lambda s: s, reload=False,
                                      runner=ok_runner([]))):
            with self.assertRaises(A.ApplyError) as cm:
                call()
            self.assertIn("broken link", str(cm.exception))
            self.assertIn(str(target), str(cm.exception))
            self.assertIn("re-stow", str(cm.exception))
            self.assertFalse((base / "repo").exists())
            self.assertTrue(e.settings.is_symlink())

    def test_missing_wallpaper_file_falls_back_to_colour_source(self):
        e = Env(self)
        s = S.set_value(S.DEFAULTS, "wallpaper.path", "/nonexistent/x.png")
        S.save_atomic(e.settings, s)
        calls = []
        warns = e.apply(runner=ok_runner(calls))
        self.assertIn("color", calls[0])
        self.assertTrue(any("wallpaper" in w for w in warns), warns)

    def test_the_lock_screen_measure_is_reused_while_the_wallpaper_is_unchanged(self):
        # Decoding a large wallpaper was most of every apply (0.6 s of 0.68 s for a 4096x2048 PNG, 2026-10-28).
        e = Env(self)
        wp = Path(e.tmp.name) / "wall.png"
        wp.write_bytes(b"one")
        S.save_atomic(e.settings, S.set_value(S.DEFAULTS, "wallpaper.path", str(wp)))
        with mock.patch.object(A.a11y, "measure_wallpaper", return_value=(255, 255, 255)) as m:
            e.apply(runner=ok_runner([]))
            first = (e.state / "hyprlock.conf").read_text()
            e.apply(runner=ok_runner([]))
            self.assertEqual(m.call_count, 1)                                  # second apply: from palette.json
            self.assertEqual((e.state / "hyprlock.conf").read_text(), first)
            self.assertIn("capped", first)
            wp.write_bytes(b"other picture")                                   # same path, new bytes: measured again
            e.apply(runner=ok_runner([]))
            self.assertEqual(m.call_count, 2)
            doc = json.loads((e.state / "palette.json").read_text())
            doc["lockCell"]["cell"] = ["x", 300]                               # a broken record is measured again
            (e.state / "palette.json").write_text(json.dumps(doc))
            e.apply(runner=ok_runner([]))
            self.assertEqual(m.call_count, 3)
        with mock.patch.object(A.a11y, "measure_wallpaper", return_value=None) as m:
            wp.write_bytes(b"unreadable")                                      # nothing measured: nothing stored
            e.apply(runner=ok_runner([]))
            self.assertNotIn("lockCell", json.loads((e.state / "palette.json").read_text()))


class CameraHomeTest(unittest.TestCase):
    """The camera is the owner's hardware: apply sets it only when HOME is the owner's home, as the GTK, cursor, idle and
    night-light reloads already check (2026-10-29: the shell tests' temp home set the real webcam to the defaults)."""

    def run_update(self, home):
        from unittest import mock
        e = Env(self)
        with mock.patch.dict(os.environ, {"HOME": str(home)}), \
                mock.patch.object(A.R, "reload_all", return_value=[]), \
                mock.patch.object(A.CAM, "apply", return_value=[]) as cam:
            A.update(e.settings, e.state, e.share, lambda s: s, runner=ok_runner([]), reload=True)
        return cam

    def test_another_home_leaves_the_camera_alone(self):
        with tempfile.TemporaryDirectory() as t:
            self.run_update(t).assert_not_called()

    def test_the_owner_home_sets_the_camera(self):
        import pwd
        self.run_update(pwd.getpwuid(os.getuid()).pw_dir).assert_called_once()


class ChangedOnlyReloadTest(unittest.TestCase):
    """Owner (2026-10-31): every settings change reloaded Hyprland, so the windows flashed even for a bar setting. A settings
    change now reloads Hyprland and kitty only when a file they read changed; an explicit apply still reloads everything."""

    def changed_by(self, mutate):
        from unittest import mock
        e = Env(self)
        A.update(e.settings, e.state, e.share, lambda s: s, runner=ok_runner([]), reload=False)    # a first full render
        with mock.patch.object(A.R, "reload_all", return_value=[]) as ra:
            A.update(e.settings, e.state, e.share, mutate, runner=ok_runner([]), reload=True)
        return ra.call_args.kwargs.get("changed")

    def test_a_bar_setting_changes_no_hyprland_or_kitty_file(self):
        def bar(s):
            s["shell"]["barHeight"] += 2
            return s
        changed = self.changed_by(bar)
        self.assertIsNotNone(changed)
        self.assertIn("colors.json", changed)
        self.assertFalse({"hypr-theme.lua", "hypr-binds.lua", "kitty-theme.conf"} & changed)

    def test_a_window_setting_changes_hypr_theme(self):
        def gaps(s):
            s["windows"]["gapsOut"] = 3 if s["windows"]["gapsOut"] != 3 else 5
            return s
        self.assertIn("hypr-theme.lua", self.changed_by(gaps))

    def test_unchanged_generated_files_are_not_rewritten(self):
        """Hyprland's autoreload watches the files it loaded: rewriting an unchanged hypr-theme.lua reloaded it anyway."""
        e = Env(self)
        A.update(e.settings, e.state, e.share, lambda s: s, runner=ok_runner([]), reload=False)
        before = (e.state / "hypr-theme.lua").stat()
        def bar(s):
            s["shell"]["barHeight"] += 2
            return s
        A.update(e.settings, e.state, e.share, bar, runner=ok_runner([]), reload=False)
        after = (e.state / "hypr-theme.lua").stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))

    def test_explicit_apply_reloads_everything(self):
        from unittest import mock
        e = Env(self)
        with mock.patch.object(A.R, "reload_all", return_value=[]) as ra:
            A.apply(e.settings, e.state, e.share, runner=ok_runner([]))
        self.assertIsNone(ra.call_args.kwargs.get("changed"))


class ReloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.log = self.base / "hyprctl.log"
        self.env = {"PATH": f"{FAKE_BIN}:/usr/bin:/bin", "GSETTINGS_BACKEND": "memory",
                    "HYPRLAND_INSTANCE_SIGNATURE": "fake",
                    "FAKE_HYPRCTL_LOG": str(self.log)}

    def state_with_lua(self, name="state"):
        d = self.base / name
        d.mkdir()
        (d / "hypr-theme.lua").write_text("-- x\n")
        return d

    def test_reload_runs_hyprctl_reload_then_configerrors(self):
        d = self.state_with_lua()
        warns = R.reload_all(d, env=self.env, proc_root=self.base / "noproc")
        lines = [l.split("\t") for l in self.log.read_text().splitlines()]
        self.assertEqual(lines[0], ["reload"])
        self.assertEqual(lines[1], ["configerrors"])
        self.assertEqual(warns, [])

    def test_unchanged_hyprland_files_skip_the_reload(self):
        d = self.state_with_lua()
        R.reload_all(d, env=self.env, proc_root=self.base / "noproc", changed={"colors.json"})
        self.assertFalse(self.log.exists() and self.log.read_text().strip(), "hyprctl ran for a change Hyprland does not read")
        R.reload_all(d, env=self.env, proc_root=self.base / "noproc", changed={"hypr-binds.lua"})
        self.assertEqual(self.log.read_text().splitlines()[0], "reload")

    def test_reload_warns_on_configerrors(self):
        d = self.state_with_lua()
        env = dict(self.env, FAKE_HYPRCTL_CONFIGERRORS="line 3: bad thing\nmore\n")
        warns = R.reload_all(d, env=env, proc_root=self.base / "noproc")
        self.assertEqual(len(warns), 1)
        self.assertIn("line 3: bad thing", warns[0])
        self.assertNotIn("\n", warns[0])

    def test_reload_warns_when_a_generated_file_did_not_load(self):
        # hyprland.lua loads them under pcall (configerrors stays empty) and records failures next to the state dir
        d = self.state_with_lua()
        (self.base / "hypr-load-errors").write_text("hypr-theme.lua: hypr-theme.lua:4: bad argument\nhypr-binds.lua: x\n")
        warns = R.reload_all(d, env=self.env, proc_root=self.base / "noproc")
        self.assertEqual(len(warns), 1)
        self.assertIn("hypr-theme.lua:4: bad argument", warns[0])
        self.assertIn("2 generated file(s)", warns[0])
        (self.base / "hypr-load-errors").write_text("")
        self.assertEqual(R.reload_all(d, env=self.env, proc_root=self.base / "noproc"), [])

    def test_reload_quotes_lua_string(self):
        self.assertEqual(R.lua_quote('a"b\\c\nd'), '"a\\"b\\\\c\\nd"')

    def test_reload_skips_hyprland_without_signature_or_file(self):
        d = self.state_with_lua()
        env = {k: v for k, v in self.env.items() if k != "HYPRLAND_INSTANCE_SIGNATURE"}
        self.assertEqual(R.reload_all(d, env=env, proc_root=self.base / "noproc"), [])
        empty = self.base / "empty"
        empty.mkdir()
        self.assertEqual(R.reload_all(empty, env=self.env, proc_root=self.base / "noproc"), [])
        self.assertFalse(self.log.exists())
        env = dict(self.env, PATH=str(self.base))  # signature set, no hyprctl anywhere
        self.assertEqual(R.reload_all(d, env=env, proc_root=self.base / "noproc"), [])

    def test_reload_kitty_by_comm_and_uid_only(self):
        d = self.base / "state"
        d.mkdir()
        (d / "kitty-theme.conf").write_text("x\n")
        proc = self.base / "proc"
        me = os.getuid()
        for pid, comm in ((101, "kitty\n"), (102, "python3\n"), (103, "kitty\n"), (104, "kittyx\n")):
            (proc / str(pid)).mkdir(parents=True)
            (proc / str(pid) / "comm").write_text(comm)
            (proc / str(pid) / "cmdline").write_bytes(b"kitty\0--session\0")
        (proc / "self").mkdir()
        (proc / "meminfo").write_text("")
        uids = {"101": me, "102": me, "103": me + 1, "104": me}
        real_stat = os.stat

        def fake_stat(p, *a, **kw):
            st = real_stat(p, *a, **kw)
            name = Path(p).name
            if Path(p).parent == proc and name in uids:
                return SimpleNamespace(st_uid=uids[name], st_mode=st.st_mode)
            return st

        sent = []
        with mock.patch("os.stat", fake_stat):
            warns = R.reload_all(d, env={"PATH": str(self.base)}, proc_root=proc,
                                 kill=lambda pid, sig: sent.append((pid, sig)))
        self.assertEqual(warns, [])
        self.assertEqual(sent, [(101, signal.SIGUSR1)])

    def test_reload_kitty_skipped_without_theme_file(self):
        proc = self.base / "proc"
        (proc / "5").mkdir(parents=True)
        (proc / "5" / "comm").write_text("kitty\n")
        empty = self.base / "empty"
        empty.mkdir()
        sent = []
        R.reload_all(empty, env={"PATH": str(self.base)}, proc_root=proc,
                     kill=lambda pid, sig: sent.append(pid))
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
