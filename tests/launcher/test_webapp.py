"""bbkos-webapp against temp folders and a fake curl (no network, no browser)."""
import base64
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/bin/bbkos-webapp"
# A 1x1 PNG.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==")


class WebAppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / "bin").mkdir()
        (self.d / "icon.png").write_bytes(PNG)
        # Fake curl: the page links an apple-touch-icon; that URL returns the PNG; everything else fails.
        curl = self.d / "bin/curl"
        curl.write_text(f"""#!/usr/bin/env bash
out=""; url=""
while [ $# -gt 0 ]; do case "$1" in -o) out=$2; shift 2 ;; -*) shift ;; *) url=$1; shift ;; esac; done
echo "$url" >> {self.d}/curl.log
case "$url" in
  */touch.png) cp {self.d}/icon.png "$out" ;;
  https://site.example/*|https://site.example) echo '<html><link rel="apple-touch-icon" href="/touch.png"></html>' ;;
  *) exit 22 ;;
esac
""")
        curl.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.d}/bin:/usr/bin:/bin", BBKOS_WEBAPP_APPS=str(self.d / "apps"),
                        BBKOS_WEBAPP_ICONS=str(self.d / "icons"), BBKOS_WEBAPP_BROWSER="vivaldi")

    def run_w(self, *args):
        return subprocess.run([str(BIN), *args], env=self.env, capture_output=True, text=True, timeout=20)

    def test_install_writes_entry_and_icon(self):
        r = self.run_w("install", "My Site", "site.example/app?x=100%")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "my-site")
        desk = (self.d / "apps/bbkos-webapp-my-site.desktop").read_text()
        self.assertIn('Exec=bbkos-webapp launch "https://site.example/app?x=100%%"', desk)   # % doubled for Exec
        self.assertIn("StartupWMClass=vivaldi-site.example__app-Default", desk)
        self.assertIn(f"Icon={self.d}/icons/bbkos-webapp-my-site.png", desk)
        self.assertIn("X-bbkOS-WebApp=https://site.example/app?x=100%", desk)
        self.assertTrue((self.d / "icons/bbkos-webapp-my-site.png").is_file())
        self.assertIn("https://site.example/touch.png", (self.d / "curl.log").read_text())

    def test_no_icon_falls_back_to_a_theme_icon(self):
        r = self.run_w("install", "Other", "https://nothing.example")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Icon=web-browser", (self.d / "apps/bbkos-webapp-other.desktop").read_text())

    def test_refuses_unsafe_addresses_and_names(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,x", 'https://a.example/"x',
                    "https://a b.example", "https://a.example/$(id)", "https://a.example/`id`"):
            self.assertEqual(self.run_w("install", "X", url).returncode, 2, url)
            self.assertEqual(self.run_w("launch", url).returncode, 2, url)
        for name in ("", "a/b", "line\nbreak", "x" * 61):
            self.assertEqual(self.run_w("install", name, "site.example").returncode, 2, repr(name))
        self.assertFalse((self.d / "apps").exists() and any((self.d / "apps").glob("*.desktop")))

    def test_list_and_remove(self):
        self.run_w("install", "One", "site.example", str(self.d / "icon.png"))
        listed = [json.loads(l) for l in self.run_w("list").stdout.splitlines()]
        self.assertEqual(listed, [{"slug": "one", "name": "One", "url": "https://site.example"}])
        self.assertEqual(self.run_w("remove", "one").returncode, 0)
        self.assertEqual(self.run_w("list").stdout, "")
        self.assertFalse((self.d / "icons/bbkos-webapp-one.png").exists())
        self.assertEqual(self.run_w("remove", "../etc").returncode, 2)
        self.assertEqual(self.run_w("remove", "missing").returncode, 1)

    def test_remove_touches_only_web_apps(self):
        (self.d / "apps").mkdir()
        other = self.d / "apps/bbkos-webapp-mine.desktop"
        other.write_text("[Desktop Entry]\nName=Not a web app\n")
        self.assertEqual(self.run_w("remove", "mine").returncode, 1)
        self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main()
