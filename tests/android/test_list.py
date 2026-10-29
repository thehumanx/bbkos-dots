"""bbkos-android status, list and the UAD list cache (docs/modules/android.md). Fake adb/scrcpy, temp HOME and XDG dirs."""
import ast
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbkos_theme import android as A  # noqa: E402
from fakebin import FIX, SERIAL, FakeBin, default_rules  # noqa: E402

UAD = (FIX / "uad_lists.json").read_bytes()


def offline(url, timeout):
    raise OSError("network is unreachable")


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fake = FakeBin(self._tmp.name)
        self.env = self.fake.env()

    def tearDown(self):
        self._tmp.cleanup()

    def seed_cache(self, data=UAD):
        p = A.cache_path(self.env)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def main_json(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = A.main(argv, self.env)
        return code, json.loads(out.getvalue())


class StatusTest(Base):
    def test_status_lists_devices_with_android_version(self):
        code, st = self.main_json(["status"])
        self.assertEqual(code, 0)
        self.assertTrue(st["adb"])
        self.assertEqual(st["devices"], [{"serial": SERIAL, "state": "device", "model": "V2503", "transport": "wifi",
                                          "brand": "vivo", "android": "16", "sdk": 36}])

    def test_status_without_adb(self):
        env = dict(self.env, PATH="/nonexistent")
        out = io.StringIO()
        with redirect_stdout(out):
            code = A.main(["status"], env)
        st = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertFalse(st["adb"])
        self.assertEqual(st["error"], "adb not found (install android-tools)")

    def test_unauthorized_device_has_no_version(self):
        self.fake.prepend((["adb", "devices"], "List of devices attached\nABC unauthorized usb:1 transport_id:1\n\n", 0, 0))
        _, st = self.main_json(["status"])
        self.assertEqual(st["devices"][0]["state"], "unauthorized")
        self.assertNotIn("sdk", st["devices"][0])


class PickDeviceTest(unittest.TestCase):
    D = {"serial": "a:1", "state": "device"}
    E = {"serial": "b:2", "state": "device"}

    def test_pick_device_errors(self):
        cases = [([], None, "no phone connected"),
                 ([{"serial": "x", "state": "unauthorized"}], None, "accept the USB debugging prompt on the phone"),
                 ([{"serial": "x", "state": "offline"}], None, "phone offline"),
                 ([self.D, self.E], None, "more than one phone"),
                 ([self.D], "zz:9", "not connected: zz:9")]
        for devs, serial, msg in cases:
            with self.assertRaises(A.AndroidError) as cm:
                A.pick_device(devs, serial)
            self.assertIn(msg.lower(), str(cm.exception).lower())

    def test_pick_device_ok(self):
        self.assertEqual(A.pick_device([self.D], None), self.D)
        self.assertEqual(A.pick_device([self.D, self.E], "b:2"), self.E)


class ListTest(Base):
    def rows(self, **kw):
        self.seed_cache()
        return {r["package"]: r for r in A.list_packages(self.env, **kw)["packages"]}

    def test_list_states(self):
        rows = self.rows()
        self.assertEqual(len(rows), 41)
        self.assertEqual(rows["com.vivo.quickpay"]["state"], "removed")
        self.assertEqual(rows["com.facebook.appmanager"]["state"], "disabled")
        self.assertEqual(rows["com.reddit.frontpage"]["state"], "installed")
        self.assertFalse(rows["com.reddit.frontpage"]["system"])
        self.assertTrue(rows["com.vivo.quickpay"]["system"])

    def test_list_joins_uad_and_marks_unlisted(self):
        rows = self.rows()
        dl = rows["com.android.providers.downloads"]
        self.assertEqual((dl["rating"], dl["list"]), ("Unsafe", "Aosp"))
        self.assertTrue(dl["description"].startswith("Downloads Manager"))
        self.assertEqual(rows["com.reddit.frontpage"]["rating"], "Unlisted")
        self.assertEqual(rows["com.reddit.frontpage"]["description"], "")
        self.assertEqual(rows["com.vivo.e2ee"]["rating"], "Unlisted")       # removal "Weird"

    def test_list_names_from_scrcpy(self):
        rows = self.rows()
        self.assertEqual(rows["com.reddit.frontpage"]["name"], "Reddit")
        self.assertEqual(rows["com.vivo.quickpay"]["name"], "")

    def test_list_names_empty_when_scrcpy_fails(self):
        self.fake.prepend((["scrcpy", "--list-apps"], "ERROR: boom", 1, 0))
        rows = self.rows()
        self.assertEqual(rows["com.reddit.frontpage"]["name"], "")

    def test_list_names_empty_when_scrcpy_is_not_installed(self):
        (self.fake.bin / "scrcpy").unlink()
        self.env["PATH"] = str(self.fake.bin)            # not /usr/bin, where the real scrcpy is
        rows = self.rows()
        self.assertEqual(rows["com.reddit.frontpage"]["name"], "")

    def test_list_uses_the_serial(self):
        self.rows()
        adb = [c for c in self.fake.calls() if c[0] == "adb" and "shell" in c]
        self.assertTrue(adb)
        self.assertTrue(all(c[1:3] == ["-s", SERIAL] for c in adb), adb)
        self.assertTrue(all("--user" in c and c[c.index("--user") + 1] == "0" for c in adb if "pm" in c))

    def test_list_offline_without_cache_sets_listError(self):
        res = A.list_packages(self.env, fetch=offline)
        self.assertIn("network is unreachable", res["listError"])
        self.assertTrue(all(r["rating"] == "Unlisted" for r in res["packages"]))
        self.assertIsNone(res["listAge"])

    def test_list_downloads_when_cache_missing(self):
        res = A.list_packages(self.env, fetch=lambda url, timeout: UAD)
        self.assertEqual(res["listError"], "")
        self.assertTrue(A.cache_path(self.env).exists())
        self.assertLess(res["listAge"], 60)

    def test_list_handles_3000_packages(self):
        names = [f"com.example.app{i}" for i in range(3000)]
        text = "".join(f"package:{n}\n" for n in names)
        self.fake.prepend((["adb", "list", "packages", "-u", "-s"], text, 0, 0),
                          (["adb", "list", "packages", "-u", "-3"], "", 0, 0),
                          (["adb", "list", "packages", "-u"], text, 0, 0),
                          (["adb", "list", "packages", "-d"], "", 0, 0),
                          (["adb", "list", "packages"], text, 0, 0))
        self.seed_cache()
        t = time.monotonic()
        res = A.list_packages(self.env)
        self.assertEqual(len(res["packages"]), 3000)
        self.assertLess(time.monotonic() - t, 10)

    def test_main_list_prints_json(self):
        self.seed_cache()
        code, res = self.main_json(["list"])
        self.assertEqual(code, 0)
        self.assertEqual(res["serial"], SERIAL)
        self.assertEqual(res["model"], "V2503")

    def test_main_list_without_device_is_a_json_error(self):
        self.fake.prepend((["adb", "devices"], "List of devices attached\n\n", 0, 0))
        code, res = self.main_json(["list"])
        self.assertEqual(code, 1)
        self.assertIn("no phone connected", res["error"].lower())

    def test_bad_usage_exits_2(self):
        err = io.StringIO()
        sys_stderr, sys.stderr = sys.stderr, err
        try:
            self.assertEqual(A.main(["frobnicate"], self.env), 2)
        finally:
            sys.stderr = sys_stderr
        self.assertIn("usage", err.getvalue())


class CacheTest(Base):
    def test_bad_download_keeps_old_cache(self):
        p = self.seed_cache(b'{"a.b": {"removal": "Recommended"}}')
        for bad in (b"<html>captive portal</html>", b"[]", b"{}", b'{"a.b": {"list": "Oem"}}'):
            err = A.update_list(self.env, fetch=lambda url, timeout, bad=bad: bad)
            self.assertTrue(err, bad)
            self.assertEqual(p.read_bytes(), b'{"a.b": {"removal": "Recommended"}}')

    def test_interrupted_download_is_an_error_not_a_crash(self):
        import http.client

        def cut(url, timeout):
            raise http.client.IncompleteRead(b"{", 1000)
        p = self.seed_cache(b'{"a.b": {"removal": "Recommended"}}')
        self.assertIn("Safety list unavailable", A.update_list(self.env, fetch=cut))
        self.assertEqual(p.read_bytes(), b'{"a.b": {"removal": "Recommended"}}')

    def test_update_list_replaces_cache_and_uses_the_uad_url(self):
        self.seed_cache(b'{"a.b": {"removal": "Recommended"}}')
        seen = []
        err = A.update_list(self.env, fetch=lambda url, timeout: seen.append((url, timeout)) or UAD)
        self.assertEqual(err, "")
        self.assertEqual(A.cache_path(self.env).read_bytes(), UAD)
        self.assertEqual(seen, [(A.LIST_URL, 20)])
        self.assertEqual(A.LIST_URL, "https://raw.githubusercontent.com/Universal-Debloater-Alliance/"
                                     "universal-android-debloater/main/resources/assets/uad_lists.json")

    def test_paths_follow_xdg(self):
        self.assertEqual(A.cache_path(self.env), Path(self.env["XDG_CACHE_HOME"], "bbkos/android/uad_lists.json"))
        self.assertEqual(A.history_path(self.env), Path(self.env["XDG_STATE_HOME"], "bbkos/android/history.jsonl"))
        env = {"HOME": self.env["HOME"]}
        self.assertEqual(A.cache_path(env), Path(self.env["HOME"], ".cache/bbkos/android/uad_lists.json"))


class RunTest(unittest.TestCase):
    def test_timeout_gives_124(self):
        r = A.run(["sleep", "5"], timeout=0.2)
        self.assertEqual((r.returncode, r.stderr), (124, "timed out"))

    def test_missing_binary_gives_127(self):
        r = A.run(["/nonexistent/tool"])
        self.assertEqual(r.returncode, 127)
        self.assertIn("not found", r.stderr)

    def test_every_subprocess_call_has_a_timeout(self):
        tree = ast.parse((ROOT / "dotfiles/bin/.local/lib/bbkos_theme/android.py").read_text())
        missing = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("run", "Popen", "check_output", "call") \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                if not any(k.arg == "timeout" for k in node.keywords):
                    missing.append(node.lineno)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
