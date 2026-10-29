import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "dotfiles/bin/.local/bin/bbkos-clean"


class CleanGuardTest(unittest.TestCase):
    def run_clean(self, installed_text):
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            cache = Path(d) / "yay"
            (cache / "somepkg").mkdir(parents=True)
            (cache / "somepkg" / "PKGBUILD").write_text("x")
            names = Path(d) / "installed"
            names.write_text(installed_text)
            env = dict(os.environ, BBKOS_YAY_CACHE=str(cache), BBKOS_INSTALLED_LIST=str(names))
            res = subprocess.run([str(CLEAN), "--apply"], env=env, capture_output=True, text=True)
            return res, (cache / "somepkg").exists()

    def test_an_empty_package_list_deletes_nothing(self):
        res, still_there = self.run_clean("")
        self.assertEqual(res.returncode, 1)
        self.assertIn("installed packages is empty", res.stderr)
        self.assertTrue(still_there)

    def test_an_uninstalled_package_folder_is_removed(self):
        res, still_there = self.run_clean("bash\n")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(still_there)


if __name__ == "__main__":
    unittest.main()
