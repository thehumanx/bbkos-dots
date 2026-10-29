import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import palette as P  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
CONFIG = ROOT / "dotfiles/bbkos-settings/.config/bbkos/matugen.toml"
HEX = r"^#[0-9a-f]{6}$"
KW = dict(mode="dark", scheme="tonal-spot", source_index=0, contrast=0.0, config=CONFIG)


def ok_runner(calls):
    def run(argv):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=(FIX / "matugen-sample.json").read_text(),
                               stderr="")
    return run


def png(path, w, h, color_type, pixel):
    raw = b"".join(b"\x00" + pixel * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color_type, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PaletteTest(unittest.TestCase):
    def test_build_command_wraps_in_systemd_scope_and_timeout(self):
        argv = P.build_command(Path("/x/a.png"), **KW)
        s = " ".join(argv)
        self.assertTrue(s.startswith("systemd-run --user --scope --quiet -p MemoryMax=1G timeout 20 matugen image /x/a.png"), s)
        for tok in ("--json", "hex", "--dry-run", "--source-color-index", "--fallback-color", "--contrast=0.0",
                    "#7aa2f7", "--config", str(CONFIG), "scheme-tonal-spot"):
            self.assertIn(tok, argv)

    def test_tones_come_from_the_tonal_palettes_and_follow_the_mode(self):
        doc = json.loads((FIX / "matugen-sample.json").read_text())
        for mode, (tint, soft) in (("dark", ("80", "30")), ("light", ("40", "90"))):
            with self.subTest(mode=mode):
                kw = dict(KW, mode=mode)
                out = json.dumps(doc)
                pal = P.generate(None, runner=lambda argv: type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})(), **kw)
                self.assertEqual(pal["tone_primary"], doc["palettes"]["primary"][tint]["color"])
                self.assertEqual(pal["soft_primary"], doc["palettes"]["primary"][soft]["color"])

    def test_missing_palettes_fall_back_to_primary(self):
        doc = json.loads((FIX / "matugen-sample.json").read_text())
        del doc["palettes"]
        out = json.dumps(doc)
        pal = P.generate(None, runner=lambda argv: type("R", (), {"returncode": 0, "stdout": out, "stderr": ""})(), **KW)
        self.assertEqual(pal["tone_primary"], pal["primary"])
        self.assertEqual(set(pal), set(P.ROLES))

    def test_generate_parses_fixture(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "a.png"
            png(img, 1, 1, 2, b"\x10\x20\x30")
            pal = P.generate(img, runner=ok_runner(calls), **KW)
        self.assertEqual(set(pal), set(P.ROLES))
        self.assertEqual(len(P.ROLES), 19)
        for k, v in pal.items():
            self.assertRegex(v, HEX, k)
        fx = json.loads((FIX / "matugen-sample.json").read_text())["colors"]
        self.assertEqual(pal["primary"], fx["primary"]["dark"]["color"])
        self.assertEqual(pal["ansi_red"], fx["red"]["dark"]["color"])
        self.assertEqual(pal["warn"], fx["warn"]["dark"]["color"])
        self.assertEqual(len(calls), 1)

    def test_generate_uses_requested_mode(self):
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "a.png"
            png(img, 1, 1, 2, b"\x10\x20\x30")
            kw = dict(KW, mode="light")
            pal = P.generate(img, runner=ok_runner([]), **kw)
        fx = json.loads((FIX / "matugen-sample.json").read_text())["colors"]
        self.assertEqual(pal["surface"], fx["surface"]["light"]["color"])

    def test_none_image_uses_fallback_color(self):
        calls = []
        pal = P.generate(None, runner=ok_runner(calls), **KW)
        argv = calls[0]
        i = argv.index("matugen")
        self.assertEqual(argv[i + 1:i + 4], ["color", "hex", "#7aa2f7"])
        self.assertNotIn("image", argv)
        self.assertEqual(P.FALLBACK, "#7aa2f7")
        self.assertEqual(set(pal), set(P.ROLES))

    def test_matugen_failure_raises_palette_error_with_first_line(self):
        fake = str(FIX / "fake-matugen")
        def run(argv):
            import subprocess
            return subprocess.run([fake], capture_output=True, text=True)
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "a.png"
            png(img, 1, 1, 2, b"\x10\x20\x30")
            with self.assertRaises(P.PaletteError) as cm:
                P.generate(img, runner=run, **KW)
        self.assertEqual(str(cm.exception), "Failed to get source color.")

    def test_missing_source_colour_retries_with_the_dominant_one(self):
        # an image with fewer distinct colours than sourceIndex makes matugen exit 1: use colour 0 instead of failing
        calls = []

        def run(argv):
            calls.append(argv)
            if argv[argv.index("--source-color-index") + 1] != "0":
                return SimpleNamespace(returncode=1, stdout="", stderr="Failed to get source color.")
            return SimpleNamespace(returncode=0, stdout=(FIX / "matugen-sample.json").read_text(), stderr="")

        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "a.png"
            png(img, 1, 1, 2, b"\x10\x20\x30")
            pal = P.generate(img, runner=run, **dict(KW, source_index=3))
        self.assertEqual([c[c.index("--source-color-index") + 1] for c in calls], ["3", "0"])
        self.assertEqual(set(pal), set(P.ROLES))

    def test_no_retry_when_the_index_is_already_zero(self):
        calls = []

        def run(argv):
            calls.append(argv)
            return SimpleNamespace(returncode=1, stdout="", stderr="Failed to get source color.")

        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "a.png"
            png(img, 1, 1, 2, b"\x10\x20\x30")
            with self.assertRaises(P.PaletteError):
                P.generate(img, runner=run, **KW)
        self.assertEqual(len(calls), 1)

    def test_timeout_exit_124_message_mentions_timeout(self):
        run = lambda argv: SimpleNamespace(returncode=124, stdout="", stderr="")
        with self.assertRaises(P.PaletteError) as cm:
            P.generate(None, runner=run, **KW)
        self.assertIn("timed out", str(cm.exception))

    @unittest.skipUnless(shutil.which("matugen") and shutil.which("systemd-run"), "matugen/systemd-run missing")
    def test_real_wrapper_failure_carries_matugen_first_line(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "notimage.png"
            bad.write_text("hello\n")
            with self.assertRaises(P.PaletteError) as cm:
                P.generate(bad, **KW)
        msg = str(cm.exception)
        self.assertNotIn("Running as unit", msg)
        self.assertTrue(msg)

    def test_first_line_skips_bare_error_header_and_ansi(self):
        stderr = ("Error: \n   0: \x1b[91mFailed to read config file.\x1b[0m\n"
                  "   1: \x1b[91mCould not find the provided config file.\x1b[0m\n")
        run = lambda argv: SimpleNamespace(returncode=1, stdout="", stderr=stderr)
        with self.assertRaises(P.PaletteError) as cm:
            P.generate(None, runner=run, **KW)
        self.assertEqual(str(cm.exception), "Failed to read config file.")
        run = lambda argv: SimpleNamespace(returncode=1, stdout="", stderr="Error:\n\n")
        with self.assertRaises(P.PaletteError) as cm:
            P.generate(None, runner=run, **KW)
        self.assertEqual(str(cm.exception), "matugen failed (rc 1)")

    @unittest.skipUnless(shutil.which("matugen") and shutil.which("systemd-run"), "matugen/systemd-run missing")
    def test_real_wrapper_non_image_reports_cause(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "notimage.txt"
            bad.write_text("hello\n")
            with self.assertRaises(P.PaletteError) as cm:
                P.generate(bad, **KW)
        msg = str(cm.exception)
        self.assertIn("image format", msg)
        self.assertNotEqual(msg.strip(), "Error:")
        self.assertNotIn("\x1b", msg)

    def test_empty_stdout_or_bad_json_or_missing_role_raises(self):
        def r(out, rc=0):
            return lambda argv: SimpleNamespace(returncode=rc, stdout=out, stderr="")
        for out in ("", "not json", "{}", json.dumps({"colors": {"surface": {"dark": {"color": "#000000"}}}})):
            with self.assertRaises(P.PaletteError, msg=out):
                P.generate(None, runner=r(out), **KW)

    def test_bad_hex_value_raises(self):
        data = json.loads((FIX / "matugen-sample.json").read_text())
        data["colors"]["primary"]["dark"]["color"] = "red"
        run = lambda argv: SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        with self.assertRaises(P.PaletteError):
            P.generate(None, runner=run, **KW)

    def test_file_size_cap_rejects_over_40mb(self):
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "big.png"
            with open(img, "wb") as f:
                f.truncate(40 * 1024 * 1024 + 1)
            calls = []
            with self.assertRaises(P.PaletteError):
                P.generate(img, runner=ok_runner(calls), **KW)
            self.assertEqual(calls, [])

    def test_missing_image_raises_before_running(self):
        calls = []
        with self.assertRaises(P.PaletteError):
            P.generate(Path("/nonexistent/zzz.png"), runner=ok_runner(calls), **KW)
        self.assertEqual(calls, [])

    @unittest.skipUnless(shutil.which("matugen") and shutil.which("systemd-run"), "matugen/systemd-run missing")
    def test_monochrome_or_tiny_image_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            grey = Path(d) / "grey.png"
            png(grey, 1, 1, 2, b"\x80\x80\x80")
            clear = Path(d) / "clear.png"
            png(clear, 64, 64, 6, b"\x00\x00\x00\x00")
            for img in (grey, clear):
                for mode in ("dark", "light"):
                    pal = P.generate(img, **dict(KW, mode=mode))
                    self.assertEqual(set(pal), set(P.ROLES))
                    for v in pal.values():
                        self.assertRegex(v, HEX)


if __name__ == "__main__":
    unittest.main()
