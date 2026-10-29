"""Thunar custom action "Set as wallpaper" (dotfiles/thunar/.config/Thunar/uca.xml).

Only the file and the command line are tested. Whether Thunar shows the entry
for images and whether a click works is click-only. The command is run the way
Thunar runs it as far as we know: %f replaced by the shell-quoted absolute path,
the result split like g_shell_parse_argv and spawned without a shell; plus the
same string through `sh -c`. HOME and the three BBKOS_* dirs are temp, the
Hyprland signature is removed, fake matugen/hyprctl/systemd-run and a fake
notify-send come first in PATH: the owner's session is never reached."""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UCA = ROOT / "dotfiles/thunar/.config/Thunar/uca.xml"
FAKE_BIN = Path(__file__).resolve().parent / "fixtures/fake-bin"

# Thunar's own stock action as it was in the owner's file (bytes preserved).
STOCK = """<action>
	<icon>utilities-terminal</icon>
	<name>Open Terminal Here</name>
	<submenu></submenu>
	<unique-id>1792283569536788-1</unique-id>
	<command>exo-open --working-directory %f --launch TerminalEmulator</command>
	<description>Example for a custom action</description>
	<range></range>
	<patterns>*</patterns>
	<startup-notify/>
	<directories/>
</action>
"""

NAMES = ["My Pic (1).png", "日本語.jpg", "-x.png", "it's.png", 'a b\'c"d.png', "X.png"]


def action(name):
    root = ET.parse(UCA).getroot()
    return next(a for a in root.findall("action") if a.findtext("name") == name)


class UcaFile(unittest.TestCase):
    def test_well_formed_and_stock_action_kept(self):
        text = UCA.read_text(encoding="utf-8")
        ET.fromstring(text.encode())
        self.assertIn(STOCK, text)
        self.assertEqual(text.index(STOCK) < text.index("Set as wallpaper"), True)

    def test_unique_ids(self):
        ids = [a.findtext("unique-id") for a in ET.parse(UCA).getroot().findall("action")]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 2)

    def test_new_action_shape(self):
        a = action("Set as wallpaper")
        self.assertEqual([c.tag for c in a], [
            "icon", "name", "submenu", "unique-id", "command", "description",
            "range", "patterns", "image-files"])
        self.assertEqual(a.findtext("range"), "")
        self.assertEqual(a.findtext("icon"), "image-x-generic")
        pats = a.findtext("patterns").split(";")
        self.assertEqual(len(pats), 12)
        self.assertEqual(sorted(set(p.lower() for p in pats)),
                         sorted("*." + e for e in ("png", "jpg", "jpeg", "webp", "bmp", "gif")))
        cmd = a.findtext("command")
        self.assertTrue(cmd.endswith(" sh %f"))
        self.assertEqual(cmd.count("%"), 1)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg missing")
class UcaCommand(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        for d in ("home", "pics", "bin", "config"):
            (self.base / d).mkdir()
        self.notes = self.base / "notify.log"
        fake = self.base / "bin/notify-send"
        fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.notes}"\n')
        fake.chmod(0o755)
        self.settings = self.base / "config/settings.json"
        shutil.copy(ROOT / "defaults/settings.json", self.settings)
        self.share = self.base / "share"
        env = {k: v for k, v in os.environ.items()
               if k != "HYPRLAND_INSTANCE_SIGNATURE" and not k.startswith("FAKE_")}
        env.update(PATH=f"{self.base / 'bin'}:{FAKE_BIN}:/usr/bin:/bin:{ROOT}/dotfiles/bin/.local/bin",
                   HOME=str(self.base / "home"), BBKOS_SETTINGS=str(self.settings),
                   BBKOS_STATE_DIR=str(self.base / "state"), BBKOS_SHARE_DIR=str(self.share),
                   BBKOS_KITTY_COMM="no-such-comm", PYTHONDONTWRITEBYTECODE="1")
        self.env = env
        self.cmd = action("Set as wallpaper").findtext("command")

    def image(self, name):
        p = self.base / "pics" / name
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x200",
                        "-frames:v", "1", str(p)], check=True)
        return p

    def run_cmd(self, path, how, relative=False):
        arg = path.name if relative else str(path)
        line = self.cmd.replace("%f", shlex.quote(arg))
        argv = ["sh", "-c", line] if how == "sh" else shlex.split(line)
        return subprocess.run(argv, env=self.env, cwd=path.parent, capture_output=True,
                              text=True, timeout=60)

    def test_success_no_notification(self):
        for how in ("sh", "argv"):
            for name in NAMES:
                with self.subTest(how=how, name=name):
                    p = self.image(name)
                    r = self.run_cmd(p, how)
                    self.assertEqual((r.returncode, r.stderr), (0, ""), r)
                    self.assertEqual([f.suffix for f in self.share.glob("current.*")], [p.suffix])
                    self.assertFalse(self.notes.exists())

    def test_leading_dash_relative(self):
        p = self.image("-x.png")
        r = self.run_cmd(p, "sh", relative=True)
        self.assertEqual(r.returncode, 0, r)
        self.assertFalse(self.notes.exists())

    def test_failure_notifies_once_with_one_line(self):
        bad = self.base / "pics/bad.png"
        bad.write_text("not an image\n")
        self.env["FAKE_MATUGEN_FAIL"] = "1"
        for how in ("sh", "argv"):
            with self.subTest(how=how):
                self.notes.unlink(missing_ok=True)
                r = self.run_cmd(bad, how)
                self.assertEqual(r.returncode, 0, r)  # the wrapper itself must not fail loudly
                lines = self.notes.read_text().splitlines()
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith("-u critical Set as wallpaper failed "), lines)
                self.assertGreater(len(lines[0]), len("-u critical Set as wallpaper failed "))

    def test_missing_file_notifies(self):
        r = self.run_cmd(self.base / "pics/gone.png", "sh")
        self.assertEqual(r.returncode, 0, r)
        self.assertIn("Set as wallpaper failed", self.notes.read_text())


if __name__ == "__main__":
    unittest.main()
