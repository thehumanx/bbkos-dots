import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import record as R  # noqa: E402
from bbkos_theme import settings as S  # noqa: E402


class OptionsTest(unittest.TestCase):
    def test_options_come_from_settings_then_overrides(self):
        s, _ = S.validate({"version": 1})
        o = R.options(s)
        self.assertEqual((o["area"], o["audio"], o["camera"], o["quality"], o["fps"]), ("region", "desktop", False, "very_high", 60))
        self.assertEqual(o["directory"], Path.home() / "Videos")
        o = R.options(s, {"area": "screen", "audio": None, "camera": True})
        self.assertEqual((o["area"], o["audio"], o["camera"]), ("screen", "desktop", True))     # None = not given

    def test_record_settings_are_validated(self):
        s, w = S.validate({"version": 1, "capture": {"recordAudio": "loud", "recordFps": 50, "recordDirectory": "videos",
                                                       "recordQuality": "ultra", "recordCamera": "yes"}})
        c = s["capture"]
        self.assertEqual((c["recordAudio"], c["recordFps"], c["recordDirectory"], c["recordQuality"], c["recordCamera"]),
                         ("desktop", 60, "~/Videos", "ultra", False))
        self.assertGreaterEqual(len(w), 3)


class RegionTest(unittest.TestCase):
    def test_slurp_output_becomes_recorder_geometry(self):
        self.assertEqual(R.region_from_slurp("100,200 640x480\n"), "640x480+100+200")
        self.assertEqual(R.region_from_slurp("-1920,-40 800x600"), "800x600+-1920+-40")

    def test_cancelled_or_odd_picks_are_none(self):
        for bad in ("", None, "garbage", "10,10 0x50", "10,10 1x1", "10 10 50x50"):
            self.assertIsNone(R.region_from_slurp(bad), bad)


class CommandTest(unittest.TestCase):
    def opts(self, **kw):
        o = {"area": "screen", "audio": "none", "camera": False, "cameraSize": "medium", "quality": "very_high", "fps": 60,
             "directory": Path("/v")}
        o.update(kw)
        return o

    def test_screen_without_audio(self):
        cmd = R.build_command(self.opts(), "eDP-1", "/v/a.mp4")
        self.assertEqual(cmd, ["gpu-screen-recorder", "-w", "eDP-1", "-k", "auto", "-f", "60", "-fm", "cfr", "-q", "very_high",
                               "-fallback-cpu-encoding", "yes", "-o", "/v/a.mp4"])
        self.assertNotIn("-a", cmd)

    def test_region_target(self):
        cmd = R.build_command(self.opts(), ("region", "900x560+100+100"), "/v/a.mp4")
        self.assertEqual(cmd[1:5], ["-w", "region", "-region", "900x560+100+100"])

    def test_audio_sources_are_merged_into_one_track(self):
        for audio, want in (("desktop", "default_output"), ("mic", "default_input"), ("both", "default_output|default_input")):
            cmd = R.build_command(self.opts(audio=audio), "eDP-1", "/v/a.mp4")
            self.assertEqual(cmd[cmd.index("-a") + 1], want, audio)
            self.assertEqual(cmd[cmd.index("-ac") + 1], "aac")

    def test_quality_and_fps_pass_through(self):
        cmd = R.build_command(self.opts(quality="ultra", fps=30), "eDP-1", "/v/a.mp4")
        self.assertEqual((cmd[cmd.index("-q") + 1], cmd[cmd.index("-f") + 1]), ("ultra", "30"))

    def test_file_name_is_dated(self):
        self.assertEqual(R.output_path("/v", datetime(2026, 10, 21, 12, 45, 22)), Path("/v/screenrecording-2026-10-21_12-45-22.mp4"))

    def test_camera_sits_in_the_bottom_right_of_the_area(self):
        self.assertEqual(R.camera_corner((100, 100, 900, 560), (320, 240)), (656, 396))
        self.assertEqual(R.camera_corner((0, 0, 1920, 1200), (240, 180), margin=10), (1670, 1010))


class CameraTest(unittest.TestCase):
    def test_mirrored_by_default_and_unmirrored_on_request(self):
        mirrored = R.camera_command("/dev/video0", (320, 240), True)
        plain = R.camera_command("/dev/video0", (320, 240), False)
        self.assertIn("--vf=hflip", mirrored)
        self.assertNotIn("--vf=hflip", plain)
        self.assertIn("--geometry=320x240", mirrored)
        self.assertIn("--wayland-app-id=bbkos-camera", mirrored)

    def test_the_mirror_setting_defaults_on(self):
        s, _ = S.validate({"version": 1})
        self.assertTrue(R.options(s)["cameraMirror"])
        s, _ = S.validate({"version": 1, "capture": {"recordCameraMirror": False}})
        self.assertFalse(R.options(s)["cameraMirror"])

    def test_corners_and_the_walk_between_them(self):
        area, size = (100, 100, 900, 560), (320, 240)
        got = {c: R.corner_position(area, size, c) for c in R.CORNERS}
        self.assertEqual(got, {"br": (656, 396), "bl": (124, 396), "tl": (124, 124), "tr": (656, 124)})
        self.assertEqual([R.next_corner(c) for c in ("br", "bl", "tl", "tr")], ["bl", "tl", "tr", "br"])
        self.assertEqual(R.next_corner("nonsense"), "br")

    def test_nearest_corner_of_a_dragged_window(self):
        area = (0, 0, 1000, 600)
        self.assertEqual(R.nearest_corner(area, (10, 10, 320, 240)), "tl")
        self.assertEqual(R.nearest_corner(area, (700, 20, 320, 240)), "tr")
        self.assertEqual(R.nearest_corner(area, (20, 400, 320, 240)), "bl")
        self.assertEqual(R.nearest_corner(area, (690, 390, 320, 240)), "br")


class ParseTest(unittest.TestCase):
    def test_commands_and_overrides(self):
        self.assertEqual(R.parse(["toggle", "--screen", "--audio", "both", "--camera"]),
                         ("toggle", {"area": "screen", "audio": "both", "camera": True}))
        self.assertEqual(R.parse(["start", "--region", "--no-camera"]), ("start", {"area": "region", "camera": False}))
        self.assertEqual(R.parse(["stop"]), ("stop", {}))

    def test_camera_command(self):
        self.assertEqual(R.parse(["camera"]), ("camera", {"corner": "next"}))
        self.assertEqual(R.parse(["camera", "tl"]), ("camera", {"corner": "tl"}))
        for bad in (["camera", "middle"], ["camera", "tl", "tr"]):
            with self.assertRaises(R.RecordError):
                R.parse(bad)

    def test_bad_input_is_an_error(self):
        for argv in ([], ["bogus"], ["start", "--audio", "loud"], ["start", "--audio"], ["stop", "--screen"], ["start", "-x"]):
            with self.assertRaises(R.RecordError, msg=argv):
                R.parse(argv)

    def test_help_exits_zero(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(R.main(["--help"]), 0)
        self.assertIn("usage: bbkos-record", out.getvalue())


class StateTest(unittest.TestCase):
    def test_state_of_a_dead_recorder_is_removed(self):
        with tempfile.TemporaryDirectory() as d:
            rt = Path(d)
            (rt / "state.json").write_text(json.dumps({"recorder": 2 ** 22 - 1, "file": "x", "started": 1}))
            self.assertIsNone(R.read_state(rt))
            self.assertFalse((rt / "state.json").exists())

    def test_a_live_pid_that_is_not_the_recorder_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            rt = Path(d)
            (rt / "state.json").write_text(json.dumps({"recorder": os.getpid(), "file": "x", "started": 1}))
            self.assertIsNone(R.read_state(rt))

    def test_missing_or_broken_state_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(R.read_state(Path(d)))
            (Path(d) / "state.json").write_text("{not json")
            self.assertIsNone(R.read_state(Path(d)))

    def test_runtime_dir(self):
        self.assertEqual(R.runtime_dir({"XDG_RUNTIME_DIR": "/run/user/1"}), Path("/run/user/1/bbkos-record"))


class LowDiskTest(unittest.TestCase):
    def test_start_refuses_on_a_nearly_full_disk(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": d}), \
                mock.patch.object(R.shutil, "which", return_value="/usr/bin/x"), \
                mock.patch.object(R, "pick_target", return_value=("eDP-1", (0, 0, 1920, 1200))), \
                mock.patch.object(R.shutil, "disk_usage", return_value=mock.Mock(free=100 * 1024 ** 2)):
            s, _ = S.validate({"version": 1, "capture": {"recordDirectory": d, "recordArea": "screen"}})
            with self.assertRaises(R.RecordError) as cm:
                R.start(R.options(s))
            self.assertIn("free some space", str(cm.exception))


class RunQuickTest(unittest.TestCase):
    def test_a_hang_gives_a_failed_result_instead_of_blocking(self):
        import time
        t0 = time.monotonic()
        res = R.run_quick(["sleep", "5"], timeout=0.2)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertEqual((res.returncode, res.stdout), (124, ""))

    def test_normal_output_is_captured_as_text(self):
        res = R.run_quick(["echo", "hi"])
        self.assertEqual((res.returncode, res.stdout), (0, "hi\n"))

    def test_a_missing_binary_still_raises(self):
        with self.assertRaises(FileNotFoundError):
            R.run_quick(["bbkos-no-such-binary"])

    def test_no_untimed_subprocess_run_in_record_and_camera(self):
        """Every subprocess.run in these two modules has a timeout, except slurp (the owner is picking a region)."""
        import ast
        for name in ("record.py", "camera.py"):
            tree = ast.parse((ROOT / "dotfiles/bin/.local/lib/bbkos_theme" / name).read_text())
            for n in ast.walk(tree):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "run"
                        and getattr(n.func.value, "id", "") == "subprocess"
                        and "timeout" not in {k.arg for k in n.keywords}
                        and not (n.args and ast.unparse(n.args[0]).startswith("['slurp'"))):
                    self.fail(f"{name}:{n.lineno} subprocess.run without a timeout")


if __name__ == "__main__":
    unittest.main()
