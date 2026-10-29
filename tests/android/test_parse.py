"""Parsers of adb and scrcpy output (docs/modules/android.md).

Fixtures were recorded on 2026-10-28 from the owner's phone (vivo V2503, Android 16, SDK 36, over Wi-Fi debugging) and
trimmed to 40 packages. Hand-added: com.vivo.quickpay in pm_all/pm_system only (a removed package; nothing was
removed on the phone when recorded), and the last two lines of devices.txt (an unauthorized and a USB device).
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
FIX = Path(__file__).resolve().parent / "fixtures"

from bbkos_theme import android as A  # noqa: E402


def fixture(name):
    return (FIX / name).read_text()


class ParseTest(unittest.TestCase):
    def test_devices_usb_wifi_unauthorized(self):
        devs = A.parse_devices(fixture("devices.txt"))
        self.assertEqual([(d["serial"], d["state"], d["model"], d["transport"]) for d in devs], [
            ("192.168.1.31:45833", "device", "V2503", "wifi"),
            ("adb-10BF7330P70015J-Jr5gD1._adb-tls-connect._tcp", "device", "V2503", "wifi"),
            ("0123456789ABCDEF", "unauthorized", "", "usb"),
            ("R5CT1234567", "device", "SM_A525F", "usb"),
        ])

    def test_devices_empty_list(self):
        self.assertEqual(A.parse_devices("List of devices attached\n\n"), [])

    def test_packages_strip_prefix(self):
        self.assertEqual(A.parse_packages("package:a.b\n\npackage:c.d\nnoise"), {"a.b", "c.d"})

    def test_packages_from_recording(self):
        pkgs = A.parse_packages(fixture("pm_all.txt"))
        self.assertEqual(len(pkgs), 41)
        self.assertIn("com.vivo.quickpay", pkgs)

    def test_scrcpy_apps_from_recording(self):
        apps = A.parse_scrcpy_apps(fixture("scrcpy_apps.txt"))
        self.assertEqual(apps["com.reddit.frontpage"], {"name": "Reddit", "system": False})
        self.assertEqual(len(apps), 14)
        self.assertTrue(any(a["system"] for a in apps.values()))

    def test_scrcpy_apps_ignores_log_lines_and_keeps_spaces(self):
        text = ("[server] INFO: Device: [vivo] vivo V2503 (Android 16)\n"
                "WARN: something odd\n"
                " * Android System Angle           com.android.angle\n"
                " - VWFNDR™ + MBL                  com.vwfndr.mbl\n"
                " - A very long application name that fills the column com.example.long\n"
                "INFO: ADB device found:\n"
                "INFO:     --> (tcpip)  192.168.1.31:45833              device  V2503\n")
        self.assertEqual(A.parse_scrcpy_apps(text), {
            "com.android.angle": {"name": "Android System Angle", "system": True},
            "com.vwfndr.mbl": {"name": "VWFNDR™ + MBL", "system": False},
            "com.example.long": {"name": "A very long application name that fills the column", "system": False},
        })

    def test_getprop(self):
        p = A.parse_getprop(fixture("getprop.txt"))
        self.assertEqual(p["ro.build.version.sdk"], "36")
        self.assertEqual(p["ro.build.version.release"], "16")
        self.assertEqual(p["ro.product.model"], "V2503")

    def test_factory_copy_from_dumpsys(self):
        # Recorded 2026-10-28 (grep of codePath and section lines): Gmail updated from the Play Store (factory copy in
        # /product), Compass in /system, vivo Feedback flagged SYSTEM but installed in /data (removing it deleted it),
        # Instagram installed by the owner.
        self.assertEqual(A.code_paths(fixture("dumpsys_gm.txt")),
                         ["/data/app/~~pq3KDcrNM3PBwGR3Zn7ALQ==/com.google.android.gm-YvfsX2IMdzAWzaVUjUrLew==",
                          "/product/app/Gmail2"])
        self.assertTrue(A.has_factory_copy(fixture("dumpsys_gm.txt")))
        self.assertTrue(A.has_factory_copy(fixture("dumpsys_compass.txt")))
        self.assertFalse(A.has_factory_copy(fixture("dumpsys_feedback.txt")))
        self.assertFalse(A.has_factory_copy(fixture("dumpsys_instagram.txt")))
        self.assertFalse(A.has_factory_copy(""))

    def test_valid_package(self):
        for ok in ("com.foo.bar", "a.b_c", "com.vivo.e2ee"):
            self.assertTrue(A.valid_package(ok), ok)
        for bad in ("foo", "foo; reboot", "../x", "a.`b`", "", ".a.b", "a..b", "com.x.y\n", "com.x y"):
            self.assertFalse(A.valid_package(bad), repr(bad))


if __name__ == "__main__":
    unittest.main()
