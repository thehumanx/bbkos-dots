import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import camera as C  # noqa: E402
from bbkos_theme import settings as S  # noqa: E402


def cam(**kw):
    s, _ = S.validate({"version": 1, "camera": kw})
    return s["camera"]


class ControlsTest(unittest.TestCase):
    def test_defaults_keep_automatic_exposure_and_a_steady_frame_rate(self):
        modes, values = C.controls(cam())
        self.assertEqual(dict(modes), {"auto_exposure": 3, "white_balance_automatic": 1,
                                       "exposure_dynamic_framerate": 0, "power_line_frequency": 1})
        names = [k for k, _ in values]
        self.assertNotIn("exposure_time_absolute", names)          # inactive while exposure is automatic
        self.assertNotIn("white_balance_temperature", names)

    def test_manual_modes_add_their_value(self):
        modes, values = C.controls(cam(exposure="manual", exposureTime=400, whiteBalance="manual", whiteBalanceTemp=5000))
        self.assertEqual(dict(modes)["auto_exposure"], 1)
        self.assertEqual(dict(modes)["white_balance_automatic"], 0)
        self.assertEqual(dict(values)["exposure_time_absolute"], 400)
        self.assertEqual(dict(values)["white_balance_temperature"], 5000)

    def test_out_of_range_values_are_clamped(self):
        self.assertEqual(cam(gamma=500)["gamma"], 150)


class ApplyTest(unittest.TestCase):
    def test_modes_are_written_before_values(self):
        calls = []

        def run(argv, **kw):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")
        self.assertEqual(C.apply(cam(exposure="manual"), "/dev/video9", run), [])
        self.assertEqual(len(calls), 2)
        self.assertIn("auto_exposure=1", calls[0][-1])
        self.assertIn("exposure_time_absolute=156", calls[1][-1])

    def test_a_refused_control_is_a_warning(self):
        def run(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, "", "VIDIOC_S_EXT_CTRLS: failed\nmore")
        self.assertEqual(C.apply(cam(), "/dev/video9", run), ["VIDIOC_S_EXT_CTRLS: failed"] * 2)

    def test_no_camera_raises(self):
        with self.assertRaises(C.CameraError):
            C.apply(cam(), None, lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))


class FindDeviceTest(unittest.TestCase):
    def test_skips_the_infrared_and_metadata_nodes(self):
        with tempfile.TemporaryDirectory() as d:
            for name, index in (("video0", "0"), ("video1", "1"), ("video2", "0"), ("video3", "1")):
                p = Path(d) / name
                p.mkdir()
                (p / "index").write_text(index + "\n")

            def run(argv, **kw):
                out = "[0]: 'GREY'" if argv[2] == "/dev/video0" else "[0]: 'MJPG'"
                return subprocess.CompletedProcess(argv, 0, out, "")
            self.assertEqual(C.find_device(d, run), "/dev/video2")


class WatchTest(unittest.TestCase):
    def test_exits_non_zero_when_the_camera_node_closes(self):
        """A clean exit would leave bbkos-camera.service (Restart=on-failure) stopped for good after a replug."""
        class Proc:
            stdout = iter(())                      # inotifywait ended at once
            def terminate(self): pass
        from unittest import mock
        with mock.patch.object(C, "find_device", return_value="/dev/video0"), \
                mock.patch.object(C.subprocess, "Popen", return_value=Proc()), \
                mock.patch.object(C, "_settings", return_value=cam()), \
                mock.patch.object(C, "apply", return_value=[]):
            self.assertEqual(C.watch(), 1)


if __name__ == "__main__":
    unittest.main()


class PreviewTest(unittest.TestCase):
    MON = (0, 0, 1500, 937)

    def test_preview_goes_right_of_the_settings_window_when_there_is_room(self):
        win = {"at": [100, 100], "size": [800, 600]}
        self.assertEqual(C.preview_layout(win, self.MON), (None, 910, 100))

    def test_tiled_settings_window_is_not_moved_and_the_preview_sits_in_its_corner(self):
        win = {"at": [10, 40], "size": [1480, 880], "floating": False}
        self.assertEqual(C.preview_layout(win, self.MON), (None, 1120, 50))

    def test_settings_window_moves_left_when_the_preview_does_not_fit(self):
        win = {"at": [190, 108], "size": [1120, 720]}           # centred on the laptop panel
        new_x, px, py = C.preview_layout(win, self.MON)
        self.assertEqual(new_x, 10)                              # 1500 - 1120 - 360 - 20 = 0, kept off the edge
        self.assertEqual((px, py), (1130, 108))
        self.assertLessEqual(px + C.PREVIEW_SIZE[0], 1500)

    def test_preview_stays_on_the_screen_when_even_that_is_not_enough(self):
        win = {"at": [0, 0], "size": [1400, 700]}
        new_x, px, _ = C.preview_layout(win, self.MON)
        self.assertEqual(px, 1500 - 360 - 10)                    # overlaps the settings window's edge; it can be dragged

    def test_command_asks_for_the_call_mode_and_mirrors(self):
        cmd = C.preview_command("/dev/video0")
        self.assertIn("av://v4l2:/dev/video0", cmd)
        self.assertTrue(any("video_size=1280x720" in a for a in cmd))
        self.assertIn("--vf=hflip", cmd)
        self.assertNotIn("--vf=hflip", C.preview_command("/dev/video0", mirror=False))
        self.assertIn(f"--wayland-app-id={C.PREVIEW_CLASS}", cmd)

    def test_device_users_skips_pipewire_and_other_users(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            for pid, comm, target in ((11, "vivaldi-bin", "/dev/video0"), (12, "wireplumber", "/dev/video0"),
                                      (13, "bash", "/dev/null")):
                os.makedirs(f"{d}/{pid}/fd")
                open(f"{d}/{pid}/comm", "w").write(comm + "\n")
                os.symlink(target, f"{d}/{pid}/fd/3")
            self.assertEqual(C.device_users(d), ["vivaldi-bin"])
            self.assertEqual(C.device_users(d, uid=os.getuid() + 1), [])


class TuneTest(unittest.TestCase):
    W, H = C.FRAME_W, C.FRAME_H

    def frame(self, bg, face):
        f = bytearray([bg]) * (self.W * self.H)
        for y in range(12, 33):                       # a face filling the lower middle
            for x in range(19, 45):
                f[y * self.W + x] = face
        return bytes(f)

    def test_brightness_follows_a_dark_face_not_the_bright_window(self):
        self.assertEqual(C.frame_brightness(self.frame(230, 40)), 40)
        self.assertEqual(C.frame_brightness(self.frame(100, 100)), 100)

    def test_search_finds_the_exposure_for_the_target(self):
        import math
        for gain in (20, 40, 80):                     # a dim, a normal and a bright room
            seen = lambda e, g=gain: min(255, g * math.log(e / 2))      # noqa: E731
            exposure, value = C.search_exposure(seen)
            at_limit = exposure in (C.TUNE_MIN_EXPOSURE, C.TUNE_MAX_EXPOSURE)
            self.assertTrue(abs(value - C.TUNE_TARGET) <= C.TUNE_TOLERANCE or at_limit, (gain, exposure, value))

    def test_search_returns_the_end_of_the_range_when_it_cannot_reach_the_target(self):
        self.assertEqual(C.search_exposure(lambda e: 10), (C.TUNE_MAX_EXPOSURE, 10))
        self.assertEqual(C.search_exposure(lambda e: 250), (C.TUNE_MIN_EXPOSURE, 250))

    def test_search_uses_few_measurements(self):
        calls = []
        C.search_exposure(lambda e: calls.append(e) or 30 * __import__("math").log(e / 2))
        self.assertLessEqual(len(calls), 9)
