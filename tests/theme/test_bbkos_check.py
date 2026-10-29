"""bbkos-check, theme engine section (BBKOS_CHECK_ONLY=theme).

Runs the real script and the real bbkos-theme / bbkos-qml-audit against temp
dirs: HOME and the BBKOS_* paths are temp, the Hyprland signature is removed,
fake matugen first in PATH. The unrelated live checks (systemctl, hyprctl,
journal) are never run: the hook selects only the theme section."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "dotfiles/bin/.local/bin/bbkos-check"
BIN = ROOT / "dotfiles/bin/.local/bin"
FAKE_BIN = Path(__file__).resolve().parent / "fixtures/fake-bin"
QML_OK = {
    "Theme.qml": "pragma Singleton\nimport QtQuick\nQtObject {}\n",
    "services/PanelState.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool open }\n",
    "modules/Bar.qml": "import QtQuick\nimport qs.services\nItem { visible: PanelState.open }\n",
}
# what the script (and the tools it runs) need, without matugen
TOOLS = ("bash", "env", "python3", "grep", "sed", "head", "cat", "date", "sh", "dirname", "realpath")


class CheckTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        (self.base / "home").mkdir()
        self.settings = self.base / "config/settings.json"
        self.settings.parent.mkdir()
        shutil.copy(ROOT / "defaults/settings.json", self.settings)
        self.state = self.base / "state"
        self.qs = self.base / "qs"
        for rel, text in QML_OK.items():
            p = self.qs / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        self.minimal = self.base / "minimal-bin"
        self.minimal.mkdir()
        for tool in TOOLS:
            src = shutil.which(tool)
            if src:
                (self.minimal / tool).symlink_to(src)
        env = {k: v for k, v in os.environ.items()
               if k != "HYPRLAND_INSTANCE_SIGNATURE" and not k.startswith(("FAKE_", "BBKOS_"))}
        env.update(PATH=f"{FAKE_BIN}:{os.environ.get('PATH', '/usr/bin:/bin')}:{BIN}",
                   HOME=str(self.base / "home"), BBKOS_SETTINGS=str(self.settings),
                   BBKOS_STATE_DIR=str(self.state), BBKOS_SHARE_DIR=str(self.base / "share"),
                   BBKOS_QS_DIR=str(self.qs), BBKOS_KITTY_COMM="no-such-comm",
                   BBKOS_CHECK_ONLY="theme", PYTHONDONTWRITEBYTECODE="1")
        self.env = env
        r = subprocess.run([str(BIN / "bbkos-theme"), "apply"], env=env, capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def check(self, **env):
        e = dict(self.env)
        for k, v in env.items():
            if v is None:
                e.pop(k, None)
            else:
                e[k] = v
        return subprocess.run([str(CHECK)], env=e, capture_output=True, text=True, timeout=60)

    def lines(self, r, level):
        return [l.strip() for l in r.stdout.splitlines() if l.startswith(f"  {level}")]

    def test_healthy_state_passes(self):
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lines(r, "FAIL"), [])
        self.assertEqual(len(self.lines(r, "ok")), 7, r.stdout)
        self.assertIn("all checks passed", r.stdout)

    def test_low_contrast_colours_fail_the_check(self):
        import json
        doc = json.loads((self.state / "colors.json").read_text())
        doc["colors"]["dim"] = doc["colors"]["bg"]                     # invisible secondary text
        (self.state / "colors.json").write_text(json.dumps(doc))
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(any("colour contrast" in l for l in self.lines(r, "FAIL")), r.stdout)

    def test_corrupt_displays_file_fails_naming_it(self):
        bad = self.base / "displays.json"
        bad.write_text("{not json")
        r = self.check(BBKOS_DISPLAYS=str(bad))
        self.assertEqual(r.returncode, 1, r.stdout)
        fails = self.lines(r, "FAIL")
        self.assertEqual(len(fails), 1, r.stdout)
        self.assertIn(str(bad), fails[0])

    def test_valid_displays_file_passes(self):
        good = self.base / "displays.json"
        good.write_text('{"version": 1, "monitors": {}, "layouts": {}}')
        r = self.check(BBKOS_DISPLAYS=str(good))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_only_theme_section_runs(self):
        r = self.check()
        for word in ("pacnew", "systemd", "hyprland", "kernel", "snapshots"):
            self.assertNotIn(word, r.stdout.lower())

    def test_unknown_only_value_fails(self):
        r = self.check(BBKOS_CHECK_ONLY="bogus")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown BBKOS_CHECK_ONLY", r.stdout)

    def test_missing_generated_file_fails_naming_it(self):
        (self.state / "kitty-theme.conf").unlink()
        (self.state / "palette.json").unlink()
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout)
        fails = self.lines(r, "FAIL")
        self.assertEqual(len(fails), 1, r.stdout)
        self.assertIn("kitty-theme.conf", fails[0])
        self.assertIn("palette.json", fails[0])
        self.assertNotIn("colors.json", fails[0])

    def test_stale_stamp_fails(self):
        s = json.loads(self.settings.read_text())
        s["shell"]["gap"] += 2
        self.settings.write_text(json.dumps(s, indent=2) + "\n")
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout)
        fails = self.lines(r, "FAIL")
        self.assertEqual(len(fails), 1, r.stdout)
        self.assertIn("do not match settings.json: run bbkos-theme apply", fails[0])

    def test_cosmetic_settings_change_still_passes(self):
        s = json.loads(self.settings.read_text())
        self.settings.write_text(json.dumps(s, separators=(",", ":")) + "\n\n")
        self.assertEqual(self.check().returncode, 0)

    def test_missing_stamp_is_a_note(self):
        (self.state / "stamp.json").unlink()
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)
        notes = self.lines(r, "note")
        self.assertEqual(len(notes), 1, r.stdout)
        self.assertIn("no freshness stamp yet: run bbkos-theme apply once", notes[0])

    def test_corrupt_stamp_is_a_note_not_a_traceback(self):
        (self.state / "stamp.json").write_text("{corrupt")
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertEqual(len(self.lines(r, "note")), 1)

    def test_missing_settings_file_fails(self):
        self.settings.unlink()
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(any("settings file missing or unreadable" in l for l in self.lines(r, "FAIL")), r.stdout)

    def test_dangling_settings_symlink_fails(self):
        link = self.base / "config/link.json"
        link.symlink_to(self.base / "nowhere.json")
        r = self.check(BBKOS_SETTINGS=str(link))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertTrue(any("settings file missing or unreadable" in l for l in self.lines(r, "FAIL")), r.stdout)

    def test_missing_settings_hint_is_a_correct_stow_command(self):
        # no .stowrc: without -d/-t stow targets the parent of the cwd (~/.local/share/bbkos/repo), and the
        # package must not be folded (theme.md: --no-folding)
        self.settings.unlink()
        r = self.check()
        fail = next(l for l in self.lines(r, "FAIL") if "settings file missing" in l)
        self.assertIn("stow -R --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~ bbkos-settings", fail)
        self.assertNotIn("cd ~/.local/share/bbkos/repo/dotfiles", fail)

    def test_broken_qml_import_fails_with_offending_line(self):
        (self.qs / "modules/Bar.qml").write_text("import QtQuick\nItem { visible: PanelState.open }\n")
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("MISSING qs.services for PanelState in", r.stdout)
        self.assertEqual(len(self.lines(r, "FAIL")), 1)

    def test_missing_qs_dir_fails_not_crashes(self):
        r = self.check(BBKOS_QS_DIR=str(self.base / "no-such-dir"))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("QML import audit failed", r.stdout)

    def test_matugen_missing_fails(self):
        r = self.check(PATH=f"{self.minimal}:{BIN}")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        fails = self.lines(r, "FAIL")
        self.assertEqual(len(fails), 1, r.stdout)
        self.assertIn("matugen is not installed", fails[0])

    def test_bbkos_theme_missing_fails(self):
        r = self.check(PATH=str(self.minimal))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        fails = self.lines(r, "FAIL")
        self.assertEqual(len(fails), 1, r.stdout)
        self.assertIn("bbkos-theme not found on PATH", fails[0])
        self.assertNotIn("command not found", r.stdout + r.stderr)

    def test_unset_variables_do_not_crash(self):
        # no BBKOS_* overrides at all and an empty HOME: set -u must not trip
        e = {k: v for k, v in self.env.items() if not k.startswith("BBKOS_")}
        e["BBKOS_CHECK_ONLY"] = "theme"
        r = subprocess.run([str(CHECK)], env=e, capture_output=True, text=True, timeout=60)
        self.assertNotIn("unbound variable", r.stderr)
        self.assertIn(r.returncode, (0, 1))


class KernelCheckTest(unittest.TestCase):
    """The reboot-needed line must compare the running kernel with the package of its own flavour (linux-lts or linux),
    with fake uname and pacman first in PATH (BBKOS_CHECK_ONLY=kernel)."""

    def run_check(self, running, packages):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fake = Path(tmp.name)
        (fake / "uname").write_text(f"#!/bin/sh\necho '{running}'\n")
        lines = "".join(f"  {name}) echo '{name} {ver}';;\n" for name, ver in packages.items())
        (fake / "pacman").write_text(f"#!/bin/sh\ncase \"$2\" in\n{lines}  *) exit 1;;\nesac\n")
        for f in ("uname", "pacman"):
            (fake / f).chmod(0o755)
        env = {"PATH": f"{fake}:/usr/bin:/bin", "HOME": tmp.name, "BBKOS_CHECK_ONLY": "kernel"}
        return subprocess.run([str(CHECK)], env=env, capture_output=True, text=True, timeout=30)

    def test_lts_running_and_installed_is_ok(self):
        r = self.run_check("6.18.57-2-lts", {"linux-lts": "6.18.57-2", "linux": "7.2.11.arch1-1"})
        self.assertIn("ok    running kernel matches installed linux-lts (6.18.57-2)", r.stdout)

    def test_mainline_running_and_installed_is_ok_even_when_lts_differs(self):
        r = self.run_check("7.2.11-arch1-1", {"linux-lts": "6.18.57-2", "linux": "7.2.11.arch1-1"})
        self.assertIn("ok    running kernel matches installed linux (7.2.11.arch1-1)", r.stdout)
        self.assertNotIn("reboot", r.stdout)

    def test_mainline_older_than_installed_says_reboot(self):
        r = self.run_check("7.2.10-arch1-1", {"linux-lts": "6.18.57-2", "linux": "7.2.11.arch1-1"})
        self.assertIn("note  kernel 7.2.10-arch1-1 running, linux 7.2.11.arch1-1 installed: reboot", r.stdout)

    def test_lts_older_than_installed_says_reboot(self):
        r = self.run_check("6.18.56-1-lts", {"linux-lts": "6.18.57-2"})
        self.assertIn("note  kernel 6.18.56-1-lts running, linux-lts 6.18.57-2 installed: reboot", r.stdout)


class CrashCheckTest(unittest.TestCase):
    """The coredump line names the programs that crashed (BBKOS_CHECK_ONLY=crashes, fake systemctl and coredumpctl). It
    printed the size column instead (`awk '{print $NF}'`: "1 1.2G" for a Figma crash, 2026-10-28)."""

    def run_check(self, dumps_json):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fake = Path(tmp.name)
        (fake / "systemctl").write_text("#!/bin/sh\necho 'Wed 2026-10-28 09:00:00 +0545'\n")
        (fake / "coredumpctl").write_text(f"#!/bin/sh\ncat <<'EOF'\n{dumps_json}\nEOF\n")
        for f in ("systemctl", "coredumpctl"):
            (fake / f).chmod(0o755)
        env = {"PATH": f"{fake}:/usr/bin:/bin", "HOME": tmp.name, "BBKOS_CHECK_ONLY": "crashes"}
        return subprocess.run([str(CHECK)], env=env, capture_output=True, text=True, timeout=30)

    def test_names_each_crashed_program_and_counts_it(self):
        dumps = [{"exe": "/usr/lib/electron44/electron", "size": 1356241940},
                 {"exe": "/usr/lib/xdg-desktop-portal-hyprland", "size": 840000},
                 {"exe": "/usr/lib/xdg-desktop-portal-hyprland", "size": 841000}]
        r = self.run_check(json.dumps(dumps))
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  coredumps in this session:", r.stdout)
        self.assertRegex(r.stdout, r"\n +1 electron \(/usr/lib/electron44/electron\)\n")
        self.assertRegex(r.stdout, r"\n +2 xdg-desktop-portal-hyprland \(/usr/lib/xdg-desktop-portal-hyprland\)\n")
        self.assertNotIn("1.2G", r.stdout)

    def test_no_dumps_is_ok(self):
        r = self.run_check("")                       # coredumpctl prints nothing (and exits 1) when there are none
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("ok    no crashes (coredumps) in this session", r.stdout)


class HyprLoadCheckTest(unittest.TestCase):
    """hyprland.lua loads the generated files under pcall, which hides their errors from `hyprctl configerrors`; it writes
    them to hypr-load-errors instead (BBKOS_CHECK_ONLY=hyprload, BBKOS_HYPR_LOAD_ERRORS points at a temp file)."""

    def run_check(self, content):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "hypr-load-errors"
        if content is not None:
            path.write_text(content)
        env = {"PATH": "/usr/bin:/bin", "HOME": tmp.name, "BBKOS_CHECK_ONLY": "hyprload",
               "BBKOS_HYPR_LOAD_ERRORS": str(path)}
        return subprocess.run([str(CHECK)], env=env, capture_output=True, text=True, timeout=30)

    def test_empty_file_is_ok(self):
        r = self.run_check("")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("ok    hyprland loaded every generated file", r.stdout)

    def test_a_failed_file_fails_and_says_why(self):
        r = self.run_check("hypr-binds.lua: hypr-binds.lua:12: attempt to call a nil value (field 'bind')\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL  hyprland could not load a generated file", r.stdout)
        self.assertIn("hypr-binds.lua:12: attempt to call a nil value", r.stdout)

    def test_missing_file_is_a_note(self):
        r = self.run_check(None)                    # written by hyprland.lua at its next load
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("note  no record of the generated files loading", r.stdout)


class HelperCheckTest(unittest.TestCase):
    def test_every_installed_root_helper_is_compared(self):
        # The logind helper (2026-10-24) was never added to the list, so an edit that was not installed went unseen.
        text = CHECK.read_text()
        for helper in sorted((ROOT / "power").glob("bbkos-*")) + sorted((ROOT / "touchpad").glob("bbkos-*")):
            with self.subTest(helper=helper.name):
                self.assertIn(f"{helper.parent.name}/{helper.name}:/usr/local/sbin/{helper.name}:", text)


if __name__ == "__main__":
    unittest.main()
