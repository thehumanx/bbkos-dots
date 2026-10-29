import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNINSTALL = ROOT / "dotfiles/bin/.local/bin/bbkos-uninstall"


class ProtectedPackagesTest(unittest.TestCase):
    def dry_run(self, pkg):
        """Run --dry-run for an entry owned by `pkg`, with a fake pacman and a private data dir."""
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            d = Path(d)
            apps = d / "share" / "applications"
            apps.mkdir(parents=True)
            (apps / "thing.desktop").write_text("[Desktop Entry]\nName=Thing\n")
            fakebin = d / "bin"
            fakebin.mkdir()
            pacman = fakebin / "pacman"
            pacman.write_text(f"#!/bin/sh\necho {pkg}\n")
            pacman.chmod(0o755)
            env = dict(
                os.environ,
                PATH=f"{fakebin}:{os.environ['PATH']}",
                XDG_DATA_HOME=str(d / "share"),
                XDG_DATA_DIRS=str(d / "none"),
            )
            env.pop("BBKOS_UNINSTALL_PROTECTED", None)
            return subprocess.run([str(UNINSTALL), "--dry-run", "thing"], env=env, capture_output=True, text=True)

    def test_runtime_dependencies_are_refused(self):
        for pkg in ("hyprlock", "hypridle", "grim", "cliphist", "bluez", "ddcutil", "wl-clipboard", "fish", "mpv"):
            with self.subTest(pkg=pkg):
                res = self.dry_run(pkg)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn("refused", res.stdout)

    def test_the_original_protected_packages_are_still_refused(self):
        for pkg in ("quickshell", "hyprland", "kitty", "thunar", "vivaldi"):
            with self.subTest(pkg=pkg):
                self.assertEqual(self.dry_run(pkg).returncode, 1)

    def test_an_ordinary_package_is_planned(self):
        res = self.dry_run("gimp")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "pacman gimp")


if __name__ == "__main__":
    unittest.main()
