"""clipboard.maxItems: the rendered clipboard.conf and bbkos-clip-store reading it. Fake wl-paste and cliphist record the calls."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
from bbkos_theme import render, settings as S  # noqa: E402

SCRIPT = ROOT / "dotfiles/bin/.local/bin/bbkos-clip-store"


class ClipboardTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.state.mkdir()
        self.log = self.dir / "cliphist.log"
        bin_ = self.dir / "bin"
        bin_.mkdir()
        (bin_ / "cliphist").write_text(f'#!/bin/sh\necho "$*" >> {self.log}\ncat > /dev/null\n')
        (bin_ / "wl-paste").write_text('#!/bin/sh\nprintf "%b\\n" "${FAKE_TYPES:-text/plain}"\n')
        for f in bin_.iterdir():
            f.chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "BBKOS_STATE_DIR": str(self.state)}

    def copy(self, *mode, data="hello", **extra):
        if self.log.exists():
            self.log.unlink()
        subprocess.run([str(SCRIPT), *mode], input=data.encode() if isinstance(data, str) else data,
                       env={**self.env, "XDG_RUNTIME_DIR": str(self.dir), **extra}, check=True, timeout=10)
        return self.log.read_text().strip() if self.log.exists() else ""

    def test_render(self):
        s, _ = S.validate({"version": 1, "clipboard": {"maxItems": 250}})
        self.assertIn("max-items = 250", render.render_clipboard_conf(s))
        s, warns = S.validate({"version": 1, "clipboard": {"maxItems": 3}})
        self.assertEqual((s["clipboard"]["maxItems"], len(warns)), (10, 1))

    def test_the_script_uses_the_rendered_number_and_100_without_it(self):
        self.assertEqual(self.copy(), "-max-items 100 store")
        self.log.unlink()
        (self.state / "clipboard.conf").write_text("# x\nmax-items = 40\n")
        self.assertEqual(self.copy(), "-max-items 40 store")

    def test_a_broken_file_falls_back_to_100(self):
        (self.state / "clipboard.conf").write_text("max-items = $(rm -rf x)\n")
        self.assertEqual(self.copy(), "-max-items 100 store")

    def test_secrets_are_still_not_stored(self):
        self.assertEqual(self.copy(FAKE_TYPES="x-kde-passwordManagerHint"), "")
        self.assertEqual(self.copy("image", FAKE_TYPES="image/png\\nx-kde-passwordManagerHint"), "")

    def test_images_are_stored_once_per_copy(self):
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 100
        self.assertEqual(self.copy("image", data=png, FAKE_TYPES="image/png"), "-max-items 100 store")      # a screenshot
        self.assertEqual(self.copy("image", data=png, FAKE_TYPES="text/plain;charset=utf-8\\nimage/png"), "")  # rich text
        self.assertEqual(self.copy("text", FAKE_TYPES="text/plain;charset=utf-8\\nimage/png"), "-max-items 100 store")
        self.assertEqual(self.copy("text", FAKE_TYPES="text/html\\nimage/png"), "")                        # "Copy image"

    def test_images_off_and_the_size_cap(self):
        (self.state / "clipboard.conf").write_text("max-items = 100\nimages = false\n")
        self.assertEqual(self.copy("image", data=b"\x89PNG", FAKE_TYPES="image/png"), "")
        self.assertEqual(self.copy("text"), "-max-items 100 store")                                        # text still kept
        (self.state / "clipboard.conf").write_text("max-items = 100\nimages = true\n")
        big = b"\0" * (10 * 1024 * 1024 + 1)
        self.assertEqual(self.copy("image", data=big, FAKE_TYPES="image/png"), "")
        self.assertEqual(list(self.dir.glob("bbkos-clip.*")), [])                                          # temp file gone

    def test_render_images(self):
        s, _ = S.validate({"version": 1, "clipboard": {"images": False}})
        self.assertIn("images = false", render.render_clipboard_conf(s))
        self.assertIn("images = true", render.render_clipboard_conf(S.DEFAULTS))


if __name__ == "__main__":
    unittest.main()
