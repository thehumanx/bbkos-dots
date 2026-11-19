"""bbkos-touchpad-watch: finding the two touchpad nodes, telling mouse mode from touchpad mode in raw events, parsing
udev output, judging each event by the first touch after it, the report, and the installer. The device loop itself
needs root and real hardware, so it is not run here."""
import importlib.machinery
import importlib.util
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCH = ROOT / "touchpad/bbkos-touchpad-watch"
UNIT = ROOT / "touchpad/bbkos-touchpad-watch.service"
INSTALL = ROOT / "scripts/install-touchpad-watch.sh"

loader = importlib.machinery.SourceFileLoader("bbkos_touchpad_watch", str(WATCH))
spec = importlib.util.spec_from_loader(loader.name, loader)
W = importlib.util.module_from_spec(spec)
loader.exec_module(W)

# /proc/bus/input/devices as read on this machine on 2026-11-13 (trimmed)
DEVICES = """I: Bus=0018 Vendor=06cb Product=cef5 Version=0100
N: Name="SYNA2BA6:00 06CB:CEF5 Mouse"
P: Phys=i2c-SYNA2BA6:00
H: Handlers=event8 mouse0
B: EV=17

I: Bus=0018 Vendor=06cb Product=cef5 Version=0100
N: Name="SYNA2BA6:00 06CB:CEF5 Touchpad"
P: Phys=i2c-SYNA2BA6:00
H: Handlers=event9 mouse1
B: EV=1b

I: Bus=0005 Vendor=3434 Product=d044 Version=0001
N: Name="Keychron M7 Mouse"
H: Handlers=sysrq kbd event17 mouse2
"""


def ev(t, c, v):
    return struct.pack("llHHi", 0, 0, t, c, v)


class NodesTest(unittest.TestCase):
    def test_finds_both_nodes(self):
        self.assertEqual(W.find_nodes(DEVICES), {"mouse": "event8", "touchpad": "event9"})

    def test_other_mice_are_ignored(self):
        self.assertEqual(W.find_nodes(DEVICES.split("\n\n")[2]), {})

    def test_missing_during_reload(self):
        self.assertEqual(W.find_nodes(""), {})


class ClassifyTest(unittest.TestCase):
    def classify(self, node, *events):
        return W.classify(node, W.decode(b"".join(ev(*e) for e in events)))

    def test_mouse_node_motion_is_the_fault(self):
        self.assertEqual(self.classify("mouse", (W.EV_REL, W.REL_X, 3), (0, 0, 0)), "motion")

    def test_mouse_node_click_tells_nothing(self):
        self.assertIsNone(self.classify("mouse", (W.EV_KEY, 0x110, 1), (0, 0, 0)))

    def test_touchpad_one_finger(self):
        self.assertEqual(self.classify("touchpad", (W.EV_ABS, 0x35, 500), (W.EV_ABS, 0, 500)), "touch")

    def test_touchpad_second_finger(self):
        self.assertEqual(self.classify("touchpad", (W.EV_ABS, 0x35, 500), (W.EV_ABS, W.ABS_MT_SLOT, 1)), "multi")
        self.assertEqual(self.classify("touchpad", (W.EV_KEY, 0x14E, 1)), "multi")

    def test_partial_event_is_dropped(self):
        self.assertEqual(list(W.decode(ev(W.EV_REL, 0, 1) + b"\0" * 5)), [(W.EV_REL, 0, 1)])


class UdevTest(unittest.TestCase):
    def test_blocks_and_rest(self):
        text = ("monitor will print the received events for:\nUDEV - the event which udev sends out\n\n"
                "UDEV  [100.1] change   /devices/.../ADP1 (power_supply)\nACTION=change\nSUBSYSTEM=power_supply\n"
                "POWER_SUPPLY_NAME=ADP1\n\n"
                "UDEV  [101.2] add      /devices/.../input23 (input)\nACTION=add\nSUBSYSTEM=input\n"
                'NAME="Keychron M7 Mouse"\n\nUDEV  [102] change')
        blocks, rest = W.parse_udev(text)
        self.assertEqual([b["SUBSYSTEM"] for b in blocks], ["power_supply", "input"])
        self.assertEqual(blocks[1]["NAME"], '"Keychron M7 Mouse"')
        self.assertEqual(rest, "UDEV  [102] change")


class WatchTest(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.w = W.Watch(self.lines.append)

    def test_event_then_touch_is_ok(self):
        self.w.event(10, "charger plugged in", "ADP1")
        self.w.touch(25)
        self.assertEqual(self.lines[-1], "OK after: charger plugged in | touchpad mode at the first touch, 15 s later")
        self.w.touch(30)
        self.assertEqual(len(self.lines), 2)            # judged once

    def test_event_then_motion_is_a_fault(self):
        self.w.touch(5)
        self.w.event(10, "HDMI-A-1 connected")
        self.assertTrue(self.w.motion(40))
        self.assertIn("FAULT after: HDMI-A-1 connected | mouse mode at the first touch, 30 s later", self.lines[-1])
        self.assertIn("last touchpad-mode touch 35 s earlier", self.lines[-1])
        self.assertFalse(self.w.motion(41))              # one fault, not one per motion

    def test_fault_with_no_event(self):
        self.w.touch(5)
        self.w.motion(400)
        self.assertEqual(self.lines[-1], "FAULT after: nothing | no charger, monitor, sleep or input event since "
                                         "the last touchpad-mode touch 6.6 min earlier")

    def test_recovery_does_not_judge_events_seen_in_mouse_mode(self):
        self.w.motion(10)
        self.w.event(20, "input removed: SYNA2BA6:00 06CB:CEF5 Touchpad")
        self.w.touch(30)
        self.assertTrue(self.lines[-2].startswith("RECOVERED | touchpad mode again after 20 s"))
        self.assertTrue(self.lines[-1].startswith("NOT JUDGED"))
        self.assertFalse(any(l.startswith("OK") for l in self.lines))

    def test_report(self):
        log = [f"2026-11-13T18:00:0{i}+05:45 {l}" for i, l in enumerate([
            "OK after: charger plugged in | x", "FAULT after: HDMI-A-1 connected | x",
            "OK after: HDMI-A-1 connected | x", "FAULT after: nothing | x", "RECOVERED | x"])]
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("\n".join(log) + "\n")
        self.addCleanup(Path(f.name).unlink)
        r = subprocess.run([str(WATCH), "--report", f.name], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = {l.split("  ")[0].strip(): l.split()[-2:] for l in r.stdout.splitlines()[1:4]}
        self.assertEqual(rows, {"HDMI-A-1 connected": ["1", "1"], "nothing": ["0", "1"],
                                "charger plugged in": ["1", "0"]})
        self.assertIn("recoveries (touchpad mode again, e.g. after bbkos-touchpad-reset): 1", r.stdout)

    def test_refuses_without_root_and_extra_arguments(self):
        r = subprocess.run([str(WATCH)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs root", r.stderr)
        self.assertEqual(subprocess.run([str(WATCH), "x"], capture_output=True).returncode, 2)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.prefix = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.prefix, True)

    def run_script(self, *args):
        return subprocess.run(["bash", str(INSTALL), *args], capture_output=True, text=True)

    def test_install_and_uninstall(self):
        r = self.run_script("--prefix", self.prefix)
        self.assertEqual(r.returncode, 0, r.stderr)
        bin_ = Path(self.prefix, "usr/local/sbin/bbkos-touchpad-watch")
        unit = Path(self.prefix, "etc/systemd/system/bbkos-touchpad-watch.service")
        self.assertEqual(bin_.read_bytes(), WATCH.read_bytes())
        self.assertTrue(bin_.stat().st_mode & 0o100)
        self.assertEqual(unit.read_bytes(), UNIT.read_bytes())
        self.assertIn("ExecStart=/usr/local/sbin/bbkos-touchpad-watch\n", UNIT.read_text())
        r = self.run_script("--uninstall", "--prefix", self.prefix)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(bin_.exists() or unit.exists())

    def test_refuses_real_install_without_root(self):
        r = self.run_script()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("needs root", r.stderr)


if __name__ == "__main__":
    unittest.main()
