"""The clipboard picker in the test shell: the preview beside the list shows a text entry in full (cliphist's list cuts
it at about 100 characters) and an image entry as the image, also an image too old to have a thumbnail; the decoded
files go to the test home, not the live picker's folder (layer 2). The history is the test home's own cliphist store."""
import json
import struct
import subprocess
import time
import unittest
import zlib

from tests.shell import harness
from tests.shell.harness import TestShell, skip_unless_session

LONG = "\n".join(f"line {i}: " + "word " * 30 for i in range(12))        # about 2 KB, 12 lines


def png(w: int, h: int) -> bytes:
    """A flat grey PNG of w x h."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\x00" + b"\x80\x80\x80" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def wait_for(fn, timeout=5.0):
    end = time.monotonic() + timeout
    while True:
        value = fn()
        if value or time.monotonic() >= end:
            return value
        time.sleep(0.1)


@skip_unless_session()
class ClipboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = TestShell().start()
        try:
            def store(data: bytes):
                subprocess.run(["cliphist", "store"], input=data, env=cls.shell._env(), check=True, timeout=10)
            # Oldest first. 21 newer images push the first one out of the 20 decoded at open.
            store(("BIGTEXT " + "x" * 30000).encode())                      # 30 KB: the preview shows the first 20 KB
            store(png(30, 20))
            for i in range(21):
                store(png(40 + i, 10))
            store(b"short text")
            store(LONG.encode())                                          # newest: row 0
            cls.shell.ipc("clipboard", "toggle")
            if not wait_for(lambda: cls.preview()["id"] != ""):
                raise RuntimeError("the clipboard picker did not open")
        except BaseException:
            cls.shell.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.shell.stop()

    @classmethod
    def preview(cls) -> dict:
        return json.loads(cls.shell.ipc("clipboard", "preview"))

    def select(self, index: int) -> dict:
        self.shell.ipc("clipboard", "select", str(index))
        return wait_for(lambda: (p := self.preview())["ready"] and p) or self.preview()

    def test_text_in_full(self):
        p = self.select(0)
        self.assertEqual(p["kind"], "text")
        self.assertEqual(p["text"], LONG)
        self.assertEqual(p["info"], f"{len(LONG)} characters  ·  12 lines")

    def test_image(self):
        p = self.select(2)                                                # the newest image
        self.assertEqual(p["kind"], "image")
        self.assertTrue(p["source"].startswith("file://" + str(self.shell.home / "clip") + "/"), p["source"])
        self.assertIn("60 × 10", p["info"])

    def test_image_without_thumbnail(self):
        self.shell.ipc("clipboard", "search", "30x20")                    # the oldest image: not among the 20 decoded at open
        p = self.select(0)
        self.assertEqual(p["kind"], "image", p)
        self.assertIn("30 × 20", p["info"])
        self.assertNotEqual(p["source"], "", p)
        self.shell.ipc("clipboard", "search", "")

    def test_selection_survives_decode(self):
        """Selecting an image too old to have a thumbnail decodes it, which rebuilds the list: the choice stays."""
        self.shell.ipc("clipboard", "search", "0x")                       # 60x10, 50x10, 40x10 (not decoded at open), 30x20
        wait_for(lambda: "60 × 10" in self.preview()["info"])
        p = self.select(2)
        self.assertIn("40 × 10", p["info"], p)
        time.sleep(1)
        self.assertIn("40 × 10", self.preview()["info"])
        self.assertTrue(self.preview()["ready"])
        self.shell.ipc("clipboard", "search", "")

    def test_whole_history_listed(self):
        """The list holds every entry and scrolls, not only the first 8 (the panel has a fixed height since the preview)."""
        p = self.select(15)                                               # row 15: the image 47x10
        self.assertIn("47 × 10", p["info"], p)
        self.select(0)

    def test_long_text_capped(self):
        self.shell.ipc("clipboard", "search", "BIGTEXT")
        p = self.select(0)
        self.assertEqual(p["kind"], "text", p)
        self.assertEqual(len(p["text"]), 20480)
        self.assertEqual(p["info"], "First 20 KB of 29 KB shown")
        self.shell.ipc("clipboard", "search", "")

    def test_zz_no_new_errors(self):
        log = self.shell.log()
        self.assertEqual(harness.unexpected_warnings(log), [], log)
        self.assertEqual([l for l in log.splitlines() if "ERROR" in l], [], log)


if __name__ == "__main__":
    unittest.main()
