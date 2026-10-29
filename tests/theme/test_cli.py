import hashlib
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import settings as S  # noqa: E402

BIN = ROOT / "dotfiles/bin/.local/bin/bbkos-theme"
LIB = ROOT / "dotfiles/bin/.local/lib"
FIX = Path(__file__).resolve().parent / "fixtures"
FAKE_BIN = FIX / "fake-bin"


def png(path, w=4, h=4, pixel=b"\x10\x80\x30"):
    raw = b"".join(b"\x00" + pixel * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def snapshot(d):
    d = Path(d)
    if not d.exists():
        return {}
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file()}


def wait_for(pred, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class Cli:
    """The real entry script against temp dirs, fake binaries first in PATH.

    Never reaches the live session: HOME and all three dirs are temp,
    HYPRLAND_INSTANCE_SIGNATURE is removed (Hyprland reload skipped) unless a
    test sets it, the kitty comm name is a fake one, and gsettings uses its in-memory
    backend (the GTK reload would otherwise switch the live session's gtk-theme to a
    theme that exists only in the temp HOME; it did on 2026-10-23)."""

    def __init__(self, tc):
        self.tmp = tempfile.TemporaryDirectory()
        tc.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.settings = self.base / "config/settings.json"
        self.state = self.base / "state"
        self.share = self.base / "share"
        self.src = self.base / "pictures"
        self.src.mkdir()
        (self.base / "home").mkdir()
        self.matugen_log = self.base / "matugen.log"
        self.hypr_log = self.base / "hyprctl.log"
        env = {k: v for k, v in os.environ.items()
               if k not in ("HYPRLAND_INSTANCE_SIGNATURE",) and not k.startswith("FAKE_")}
        env.update(PATH=f"{FAKE_BIN}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                   HOME=str(self.base / "home"),
                   BBKOS_SETTINGS=str(self.settings), BBKOS_STATE_DIR=str(self.state),
                   BBKOS_SHARE_DIR=str(self.share), BBKOS_KITTY_COMM="bbkos-nokitty",
                   FAKE_MATUGEN_LOG=str(self.matugen_log), FAKE_HYPRCTL_LOG=str(self.hypr_log),
                   GSETTINGS_BACKEND="memory", PYTHONDONTWRITEBYTECODE="1")
        self.env = env
        self.settings.parent.mkdir(parents=True)
        S.save_atomic(self.settings, S.DEFAULTS)

    def _env(self, extra):
        env = dict(self.env)
        for k, v in (extra or {}).items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v
        return env

    def run(self, *args, env=None, cwd=None):
        return subprocess.run([str(BIN), *args], env=self._env(env), cwd=cwd or self.base,
                              capture_output=True, text=True, timeout=60)

    def popen(self, *args, env=None):
        return subprocess.Popen([str(BIN), *args], env=self._env(env), cwd=self.base,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def load(self):
        return json.loads(self.settings.read_text())

    def colors(self):
        return json.loads((self.state / "colors.json").read_text())

    def matugen_calls(self):
        return len(self.matugen_log.read_text().splitlines()) if self.matugen_log.exists() else 0


class CliTest(unittest.TestCase):
    def ok(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def fails_one_line(self, r, code=1):
        self.assertEqual(r.returncode, code, (r.stdout, r.stderr))
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.strip())
        return r.stderr.strip()

    # --- wallpaper -------------------------------------------------------

    def test_wallpaper_name_with_space_unicode_and_leading_dash(self):
        c = Cli(self)
        names = ["My Pic (1).png", "日本.jpg", "-x.png", "$(touch pwned) `x`;.PNG"]
        for name in names:
            src = c.src / name
            png(src, pixel=bytes([len(name), 1, 2]))
            arg = name if name.startswith("-") else str(src)
            self.ok(c.run("wallpaper", "set", "--", arg, cwd=c.src))
            ext = name.rsplit(".", 1)[1].lower()
            dest = c.share / f"current.{ext}"
            self.assertEqual(c.load()["wallpaper"]["path"], str(dest))
            self.assertEqual(dest.read_bytes(), src.read_bytes())
            self.assertEqual(sorted(p.name for p in c.share.iterdir() if p.name.startswith("current.")),
                             [dest.name], name)
            self.assertTrue((c.state / "colors.json").is_file())
        self.assertFalse((c.src / "pwned").exists())
        self.assertFalse((c.base / "pwned").exists())
        # a single leading-dash filename without "--" is still a filename
        self.ok(c.run("wallpaper", "set", "-x.png", cwd=c.src))
        self.assertEqual(c.load()["wallpaper"]["path"], str(c.share / "current.png"))
        # palette.json records the copy, not the original
        inputs = json.loads((c.state / "palette.json").read_text())["inputs"]
        self.assertEqual(inputs["wallpaper"]["path"], str(c.share / "current.png"))

    def test_wallpaper_rejects_non_image_and_missing(self):
        c = Cli(self)
        before = c.settings.read_bytes()
        (c.src / "dir.png").mkdir()
        (c.src / "notes.txt").write_text("hi\n")
        big = c.src / "big.png"
        with open(big, "wb") as f:
            f.truncate(40 * 1024 * 1024 + 1)
        for arg in (c.src / "missing.png", c.src / "dir.png", c.src / "notes.txt", big):
            msg = self.fails_one_line(c.run("wallpaper", "set", "--", str(arg)))
            self.assertIn(arg.name, msg)
            self.assertEqual(c.settings.read_bytes(), before)
            self.assertEqual(snapshot(c.share), {})
        self.assertEqual(c.matugen_calls(), 0)

    def test_wallpaper_set_failure_keeps_old_wallpaper(self):
        c = Cli(self)
        a = c.src / "a.png"
        png(a)
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        settings_before = c.settings.read_bytes()
        state_before = snapshot(c.state)
        b = c.src / "b.jpg"
        b.write_bytes(b"not really a jpeg")
        msg = self.fails_one_line(c.run("wallpaper", "set", "--", str(b), env={"FAKE_MATUGEN_FAIL": "1"}))
        self.assertEqual(msg, "Failed to get source color.")
        self.assertEqual(snapshot(c.share), {"current.png": a.read_bytes()})
        self.assertEqual(c.settings.read_bytes(), settings_before)
        self.assertEqual(snapshot(c.state), state_before)

    def test_wallpaper_clear(self):
        c = Cli(self)
        a = c.src / "a.webp"
        png(a)
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        self.assertTrue((c.share / "current.webp").exists())
        self.ok(c.run("wallpaper", "clear"))
        self.assertEqual(c.load()["wallpaper"]["path"], "")
        self.assertEqual(snapshot(c.share), {"previous.webp": a.read_bytes()})  # one-step undo
        self.assertIn("color hex #7aa2f7", c.matugen_log.read_text().splitlines()[-1])
        self.ok(c.run("wallpaper", "set", "--", str(c.share / "previous.webp")))
        self.assertEqual(c.load()["wallpaper"]["path"], str(c.share / "current.webp"))
        # nothing was current, so the undo copy stays as well
        self.assertEqual(snapshot(c.share), {"current.webp": a.read_bytes(), "previous.webp": a.read_bytes()})

    def test_wallpaper_set_twice_keeps_previous_copy(self):
        c = Cli(self)
        a, b = c.src / "a.png", c.src / "b.png"
        png(a)
        png(b, pixel=b"\x90\x20\x20")
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        self.ok(c.run("wallpaper", "set", "--", str(b)))
        self.assertEqual(snapshot(c.share), {"current.png": b.read_bytes(), "previous.png": a.read_bytes()})
        self.assertEqual(c.load()["wallpaper"]["path"], str(c.share / "current.png"))
        inputs = json.loads((c.state / "palette.json").read_text())["inputs"]
        self.assertEqual(inputs["wallpaper"]["path"], str(c.share / "current.png"))

    def test_wallpaper_kept_when_a_generated_file_replace_fails(self):
        # the wallpaper copy is replaced after the generated files and the stamp: a failure
        # among those leaves the old copy byte-identical (same extension, so same path)
        c = Cli(self)
        a, b = c.src / "a.png", c.src / "b.png"
        png(a)
        png(b, pixel=b"\x90\x20\x20")
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        settings_before = c.settings.read_bytes()
        (c.state / "kitty-theme.conf").unlink()
        (c.state / "kitty-theme.conf").mkdir()  # os.replace of a file onto a directory fails
        r = c.run("wallpaper", "set", "--", str(b))
        (c.state / "kitty-theme.conf").rmdir()
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(snapshot(c.share), {"current.png": a.read_bytes()})
        self.assertEqual(c.settings.read_bytes(), settings_before)

    # --- apply / reload --------------------------------------------------

    def test_apply_skips_reload_when_targets_absent(self):
        c = Cli(self)
        r = self.ok(c.run("apply"))
        self.assertEqual(r.stderr, "")
        self.assertFalse(c.hypr_log.exists())
        for name in ("colors.json", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf"):
            self.assertTrue((c.state / name).is_file())

    def test_cli_reload_runs_fake_hyprctl_and_signals_fake_kitty(self):
        c = Cli(self)
        klog = c.base / "kitty.log"
        kitty = subprocess.Popen([str(FAKE_BIN / "fake-kitty")], env=dict(c.env, FAKE_KITTY_LOG=str(klog)))
        self.addCleanup(kitty.wait)
        self.addCleanup(kitty.terminate)
        self.assertTrue(wait_for(lambda: klog.exists() and "ready" in klog.read_text()))
        env = {"HYPRLAND_INSTANCE_SIGNATURE": "fake", "BBKOS_KITTY_COMM": "fake-kitty",
               "FAKE_HYPRCTL_CONFIGERRORS": "config error: line 9\n"}
        r = self.ok(c.run("apply", env=env))
        calls = [l.split("\t") for l in c.hypr_log.read_text().splitlines()]
        self.assertEqual(calls, [["reload"], ["configerrors"]])
        self.assertIn("config error: line 9", r.stderr)
        self.assertTrue(wait_for(lambda: "usr1" in klog.read_text()), klog.read_text())
        self.assertIsNone(kitty.poll())  # SIGUSR1 handled, still running

    def test_dry_run_cli_writes_only_out_dir(self):
        c = Cli(self)
        out = c.base / "out dir"
        before = c.settings.read_bytes()
        self.ok(c.run("apply", "--out-dir", str(out), env={"HYPRLAND_INSTANCE_SIGNATURE": "fake"}))
        self.assertFalse(c.state.exists())
        self.assertFalse(c.hypr_log.exists())
        self.assertEqual(c.settings.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["clipboard.conf", "colors.json", "gtk.css", "hypr-binds.lua", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf", "stamp.json"])

    def test_concurrent_applies_serialise_and_last_wins(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        S.save_atomic(c.settings, S.set_value(S.DEFAULTS, "shell.gap", "4"))
        a = c.popen("apply", "--only", "colors", env={"FAKE_MATUGEN_SLEEP": "1"})
        self.assertTrue(wait_for(lambda: c.matugen_calls() == 2))  # A holds the lock
        S.save_atomic(c.settings, S.set_value(S.DEFAULTS, "shell.gap", "8"))
        t0 = time.monotonic()
        b = c.popen("apply")
        _, berr = b.communicate(timeout=30)
        waited = time.monotonic() - t0
        _, aerr = a.communicate(timeout=30)
        self.assertEqual((a.returncode, b.returncode), (0, 0), (aerr, berr))
        self.assertGreater(waited, 0.3)  # B waited for A's lock
        self.assertEqual(c.colors()["shell"]["gap"], 8)
        out = c.base / "expect"
        self.ok(c.run("apply", "--out-dir", str(out)))
        for name in ("colors.json", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf"):
            self.assertEqual((c.state / name).read_bytes(), (out / name).read_bytes(), name)

    def test_set_concurrent_different_keys_both_survive(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        a = c.popen("set", "colors.contrast", "0.5", env={"FAKE_MATUGEN_SLEEP": "1"})
        self.assertTrue(wait_for(lambda: c.matugen_calls() == 2))
        b = c.popen("set", "shell.gap", "8")
        _, berr = b.communicate(timeout=30)
        _, aerr = a.communicate(timeout=30)
        self.assertEqual((a.returncode, b.returncode), (0, 0), (aerr, berr))
        s = c.load()
        self.assertEqual(s["colors"]["contrast"], 0.5)
        self.assertEqual(s["shell"]["gap"], 8)
        self.assertEqual(c.colors()["shell"]["gap"], 8)
        inputs = json.loads((c.state / "palette.json").read_text())["inputs"]
        self.assertEqual(inputs["contrast"], 0.5)

    def test_stress_50_applies_no_torn_file(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        stop = threading.Event()
        bad, reads = [], [0]

        def reader():
            p = c.state / "colors.json"
            while not stop.is_set():
                try:
                    json.loads(p.read_text())
                    reads[0] += 1
                except (OSError, ValueError) as e:
                    bad.append(repr(e))

        t = threading.Thread(target=reader)
        t.start()
        try:
            procs = []
            for i in range(50):
                if i % 10 == 9:
                    args = ("set", "colors.contrast", str(round((i % 20) / 20 - 0.5, 2)))
                else:
                    args = ("set", "shell.gap", str((i % 16) * 2))
                procs.append(c.popen(*args))
                if len(procs) >= 4:
                    p = procs.pop(0)
                    p.communicate(timeout=60)
                    self.assertEqual(p.returncode, 0)
            for p in procs:
                _, err = p.communicate(timeout=60)
                self.assertEqual(p.returncode, 0, err)
        finally:
            stop.set()
            t.join()
        self.assertEqual(bad, [])
        self.assertGreater(reads[0], 50)
        self.assertEqual(sorted(p.name for p in c.state.iterdir()),
                         ["apply.lock", "clipboard.conf", "colors.json", "gtk.css", "hypr-binds.lua", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf", "palette.json", "stamp.json"])

    @unittest.skipUnless(shutil.which("matugen") and shutil.which("systemd-run"), "matugen/systemd-run missing")
    def test_real_matugen_end_to_end(self):
        c = Cli(self)
        cfg = c.base / "home/.config/bbkos/matugen.toml"
        cfg.parent.mkdir(parents=True)
        shutil.copy(ROOT / "dotfiles/bbkos-settings/.config/bbkos/matugen.toml", cfg)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin").replace(f"{FAKE_BIN}:", "")}
        a = c.src / "green pic.png"
        png(a, 16, 16, b"\x20\xa0\x40")
        self.ok(c.run("wallpaper", "set", "--", str(a), env=env))
        self.assertRegex(c.colors()["colors"]["accent"], r"^#[0-9a-f]{6}$")
        self.assertFalse(c.matugen_log.exists())  # the real one ran, not the fake
        before = snapshot(c.state)
        bad = c.src / "bad.png"
        bad.write_text("not a png\n")
        msg = self.fails_one_line(c.run("wallpaper", "set", "--", str(bad), env=env))
        self.assertIn("PNG", msg)
        self.assertEqual(snapshot(c.state), before)
        self.assertEqual(snapshot(c.share), {"current.png": a.read_bytes()})

    # --- set / reset / status --------------------------------------------

    def test_set_clamps_and_applies(self):
        c = Cli(self)
        self.ok(c.run("set", "shell.barHeight", "999"))
        self.assertEqual(c.load()["shell"]["barHeight"], 48)
        self.assertEqual(c.colors()["shell"]["barHeight"], 48)
        self.ok(c.run("set", "colors.contrast", "-0.5"))
        self.assertEqual(c.load()["colors"]["contrast"], -0.5)
        self.ok(c.run("set", "windows.rounding", "3"))
        self.assertIn("rounding = 3,", (c.state / "hypr-theme.lua").read_text())
        before = c.settings.read_bytes()
        msg = self.fails_one_line(c.run("set", "windows.rounding", "abc"))
        self.assertIn("windows.rounding", msg)
        self.fails_one_line(c.run("set", "nope.key", "1"))
        self.assertEqual(c.settings.read_bytes(), before)
        self.assertEqual(c.settings.with_name("settings.json.bak").read_bytes(), before)

    def test_set_wallpaper_path_is_rejected(self):
        c = Cli(self)
        a = c.src / "a.png"
        png(a)
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        before = c.settings.read_bytes()
        share_before = snapshot(c.share)
        for value in ("/etc/hostname", "relative.png", ""):
            msg = self.fails_one_line(c.run("set", "wallpaper.path", value))
            self.assertIn("wallpaper set", msg)
            self.assertIn("wallpaper clear", msg)
            self.assertEqual(c.settings.read_bytes(), before)
            self.assertEqual(snapshot(c.share), share_before)

    def test_settings_json_unchanged_when_apply_fails(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        settings_before = c.settings.read_bytes()
        state_before = snapshot(c.state)
        msg = self.fails_one_line(c.run("set", "colors.contrast", "0.5", env={"FAKE_MATUGEN_FAIL": "1"}))
        self.assertEqual(msg, "Failed to get source color.")
        self.assertEqual(c.settings.read_bytes(), settings_before)
        self.assertEqual(snapshot(c.state), state_before)

    def test_touchpad_section_sets_and_resets(self):
        c = Cli(self)
        self.ok(c.run("set", "touchpad.swipe4Up", "close"))
        self.assertEqual(c.load()["touchpad"]["swipe4Up"], "close")
        self.assertIn('hl.gesture({ fingers = 4, direction = "up", action = "close" })',
                      (c.state / "hypr-theme.lua").read_text())
        self.ok(c.run("reset", "touchpad"))
        self.assertEqual(c.load()["touchpad"], S.DEFAULTS["touchpad"])

    def test_power_section_sets_and_resets(self):
        c = Cli(self)
        self.ok(c.run("set", "power.balancedEpp", "balance_power"))
        self.ok(c.run("set", "power.saverCap", "5"))
        self.assertEqual((c.load()["power"]["balancedEpp"], c.load()["power"]["saverCap"]), ("balance_power", 10))
        self.ok(c.run("reset", "power"))
        self.assertEqual(c.load()["power"], S.DEFAULTS["power"])

    def test_reset_restores_defaults_and_applies(self):
        c = Cli(self)
        self.ok(c.run("set", "shell.gap", "20"))
        self.ok(c.run("set", "windows.rounding", "3"))
        a = c.src / "a.png"
        png(a)
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        self.ok(c.run("reset", "shell"))
        s = c.load()
        self.assertEqual(s["shell"], S.DEFAULTS["shell"])
        self.assertEqual(s["windows"]["rounding"], 3)
        self.assertEqual(c.colors()["shell"]["gap"], 12)
        self.assertEqual(snapshot(c.share), {"current.png": a.read_bytes()})
        self.ok(c.run("reset"))
        self.assertEqual(c.load(), S.DEFAULTS)
        self.assertIn("rounding = 10,", (c.state / "hypr-theme.lua").read_text())
        self.assertEqual(snapshot(c.share), {"previous.png": a.read_bytes()})

    def test_reset_takes_keys_and_several_targets_in_one_apply(self):
        c = Cli(self)
        self.ok(c.run("set", "shell.gap", "20"))
        self.ok(c.run("set", "shell.radius", "4"))
        self.ok(c.run("set", "windows.rounding", "3"))
        self.ok(c.run("set", "idle.dim", "60"))
        self.ok(c.run("reset", "shell.gap", "idle"))
        s = c.load()
        self.assertEqual(s["shell"]["gap"], S.DEFAULTS["shell"]["gap"])
        self.assertEqual(s["shell"]["radius"], 4)                     # only the named key of the section
        self.assertEqual(s["windows"]["rounding"], 3)
        self.assertEqual(s["idle"], S.DEFAULTS["idle"])
        self.fails_one_line(c.run("reset", "shell.bogus"), code=2)
        self.fails_one_line(c.run("reset", "wallpaper.path"), code=2)  # only `wallpaper clear` / `reset wallpaper`
        self.assertEqual(c.load()["shell"]["radius"], 4)              # a bad target changes nothing

    def test_defaults_prints_the_table(self):
        c = Cli(self)
        r = self.ok(c.run("defaults"))
        doc = json.loads(r.stdout)
        self.assertEqual(doc["defaults"], json.loads(json.dumps(S.DEFAULTS)))
        self.assertEqual(doc["gridMode"], json.loads(json.dumps(S.GRID_OVERRIDES)))
        self.assertEqual(doc["gridRoundOff"], json.loads(json.dumps(S.GRID_ROUND_OFF)))
        self.fails_one_line(c.run("defaults", "x"), code=2)

    def test_reset_wallpaper_keeps_previous_copy(self):
        c = Cli(self)
        a = c.src / "a.jpg"
        png(a)  # PNG bytes, .jpg name: only the fake matugen reads it
        self.ok(c.run("wallpaper", "set", "--", str(a)))
        self.ok(c.run("reset", "wallpaper"))
        self.assertEqual(c.load()["wallpaper"]["path"], "")
        self.assertEqual(snapshot(c.share), {"previous.jpg": a.read_bytes()})
        self.fails_one_line(c.run("reset", "bogus"), code=2)

    def test_reset_recovers_corrupt_settings(self):
        c = Cli(self)
        c.settings.write_text("{corrupt")
        self.ok(c.run("reset"))
        self.assertEqual(c.load(), S.DEFAULTS)

    def test_status_reports(self):
        c = Cli(self)
        r = self.ok(c.run("status"))
        lines = dict(l.split(": ", 1) for l in r.stdout.splitlines())
        self.assertEqual(lines["settings"], str(c.settings))
        self.assertEqual(lines["state dir"], str(c.state))
        self.assertEqual(lines["colors.json"], "no")
        self.assertEqual(lines["fresh"], "unknown")
        self.assertNotIn("newer than settings", lines)
        self.ok(c.run("apply"))
        r = self.ok(c.run("status"))
        lines = dict(l.split(": ", 1) for l in r.stdout.splitlines())
        for name in ("colors.json", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf"):
            self.assertEqual(lines[name], "yes")
        self.assertEqual(lines["fresh"], "yes")
        self.assertEqual(lines["wallpaper"], "none")
        self.assertEqual(lines["mode"], "dark")
        self.assertEqual(lines["scheme"], "tonal-spot")

    def test_contrast_passes_on_a_fresh_apply_and_names_a_failing_pair(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        r = self.ok(c.run("contrast"))
        self.assertRegex(r.stdout, r"^\d+ of \d+ colour pairs pass")
        doc = json.loads((c.state / "colors.json").read_text())
        doc["colors"]["crit"] = doc["colors"]["bg"]
        (c.state / "colors.json").write_text(json.dumps(doc))
        r = c.run("contrast")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL crit text on popup", r.stdout)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        (c.state / "colors.json").unlink()
        self.fails_one_line(c.run("contrast"))

    # --- freshness stamp -------------------------------------------------

    def fresh(self, c):
        r = self.ok(c.run("status"))
        return next(l for l in r.stdout.splitlines() if l.startswith("fresh:"))

    def test_stamp_written_by_apply(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        st = json.loads((c.state / "stamp.json").read_text())
        self.assertEqual(set(st), {"settings_sha256", "files", "applied"})
        self.assertEqual(st["settings_sha256"], hashlib.sha256(S.dumps(c.load()).encode()).hexdigest())
        self.assertEqual(st["files"], ["clipboard.conf", "colors.json", "gtk.css", "hypr-binds.lua", "hypr-theme.lua", "hypridle.conf", "hyprlock.conf", "kitty-theme.conf", "palette.json"])
        self.assertRegex(st["applied"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|\+00:00)$")
        self.assertEqual([p.name for p in c.state.iterdir() if p.name.endswith(".tmp") or p.name.startswith(".")], [])

    def test_stamp_in_dry_run_out_dir(self):
        c = Cli(self)
        out = c.base / "out"
        self.ok(c.run("apply", "--out-dir", str(out)))
        self.assertTrue((out / "stamp.json").is_file())
        self.assertFalse((c.state / "stamp.json").exists())

    def test_fresh_after_apply_and_set(self):
        c = Cli(self)
        self.assertEqual(self.fresh(c), "fresh: unknown")
        self.ok(c.run("apply"))
        self.assertEqual(self.fresh(c), "fresh: yes")
        self.ok(c.run("set", "shell.gap", "20"))
        self.assertEqual(self.fresh(c), "fresh: yes")

    def test_stale_after_hand_edit(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        s = c.load()
        s["shell"]["gap"] = 30
        c.settings.write_text(json.dumps(s, indent=2) + "\n")
        self.assertEqual(self.fresh(c), "fresh: no (run bbkos-theme apply)")
        self.ok(c.run("apply"))
        self.assertEqual(self.fresh(c), "fresh: yes")

    def test_cosmetic_changes_stay_fresh(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        s = c.load()
        c.settings.write_text(json.dumps(dict(reversed(list(s.items()))), separators=(",", ":")) + "\n\n")
        self.assertEqual(self.fresh(c), "fresh: yes")

    def test_missing_or_corrupt_stamp_is_unknown(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        for content in (None, "{corrupt", "[]", "null", '{"settings_sha256": 5}', "{}", b"\xff\xfe"):
            with self.subTest(content=content):
                f = c.state / "stamp.json"
                if content is None:
                    f.unlink()
                else:
                    f.write_bytes(content if isinstance(content, bytes) else content.encode())
                r = c.run("status")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                self.assertIn("fresh: unknown", r.stdout)

    def test_half_commit_leaves_no_stamp(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        self.ok(c.run("set", "shell.gap", "20"))
        self.assertEqual(self.fresh(c), "fresh: yes")
        (c.state / "kitty-theme.conf").unlink()
        (c.state / "kitty-theme.conf").mkdir()  # os.replace of a file onto a directory fails
        r = c.run("set", "shell.gap", "22")
        (c.state / "kitty-theme.conf").rmdir()
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(c.load()["shell"]["gap"], 20)  # settings.json is written last
        self.assertFalse((c.state / "stamp.json").exists())
        self.assertEqual(self.fresh(c), "fresh: unknown")

    def test_staging_failure_keeps_old_state_and_stamp(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        self.ok(c.run("set", "shell.gap", "20"))
        blocker = c.base / "blocker"
        blocker.write_text("x")
        (c.state / "kitty-theme.conf").unlink()
        (c.state / "kitty-theme.conf").symlink_to(blocker / "sub" / "k.conf")  # parent cannot be created
        before = {k: v for k, v in snapshot(c.state).items() if k != "kitty-theme.conf"}
        r = c.run("set", "shell.gap", "22")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual({k: v for k, v in snapshot(c.state).items() if k != "kitty-theme.conf"}, before)
        self.assertEqual(c.load()["shell"]["gap"], 20)
        self.assertEqual(self.fresh(c), "fresh: yes")

    def test_successful_apply_replaces_stamp(self):
        c = Cli(self)
        self.ok(c.run("apply"))
        old = (c.state / "stamp.json").read_bytes()
        self.ok(c.run("set", "shell.gap", "20"))
        self.assertNotEqual((c.state / "stamp.json").read_bytes(), old)
        self.assertEqual(self.fresh(c), "fresh: yes")

    def test_usage_errors_exit_2(self):
        c = Cli(self)
        for args in ((), ("bogus",), ("apply", "--only", "bogus"), ("apply", "--out-dir"),
                     ("apply", "extra"), ("set", "only-one"), ("set", "a", "b", "c"),
                     ("wallpaper",), ("wallpaper", "set"), ("wallpaper", "set", "a", "b"),
                     ("wallpaper", "clear", "x"), ("status", "x"), ("reset", "a", "b")):
            self.fails_one_line(c.run(*args), code=2)
        r = self.ok(c.run("--help"))
        self.assertIn("wallpaper set", r.stdout)

    def test_cli_creates_no_pycache(self):
        c = Cli(self)
        def caches():
            return sorted(str(p) for p in LIB.rglob("__pycache__"))
        before = caches()
        env = {"PYTHONDONTWRITEBYTECODE": None}
        self.ok(c.run("status", env=env))
        self.ok(c.run("apply", "--out-dir", str(c.base / "o"), env=env))
        self.ok(c.run("apply", env=env))
        self.assertEqual(caches(), before)


if __name__ == "__main__":
    unittest.main()
