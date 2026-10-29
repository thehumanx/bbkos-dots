"""bbkos-android disable, enable, remove, restore: safety checks, adb argv, results, history (docs/modules/android.md)."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_list import A, Base, SERIAL  # noqa: E402

REMOVABLE = "com.facebook.appmanager"          # Recommended, disabled on the recorded phone
UNSAFE = "com.android.providers.downloads"     # Unsafe
REMOVED = "com.vivo.quickpay"                  # in -u only


def pm_calls(fake):
    return [c for c in fake.calls() if c[0] == "adb" and ("pm" in c or "cmd" in c) and "list" not in c]


class ActionTest(Base):
    def setUp(self):
        super().setUp()
        self.seed_cache()
        self.fake.prepend((["adb", "uninstall"], "Success\n", 0, 0),
                          (["adb", "disable-user"], f"Package {REMOVABLE} new state: disabled-user\n", 0, 0),
                          (["adb", "enable"], f"Package {REMOVABLE} new state: enabled\n", 0, 0),
                          (["adb", "install-existing"], f"Package {REMOVED} installed for user: 0\n", 0, 0))

    def test_argv_for_each_action(self):
        expect = {"remove": ["pm", "uninstall"], "disable": ["pm", "disable-user"], "enable": ["pm", "enable"],
                  "restore": ["cmd", "package", "install-existing"]}
        for action, words in expect.items():
            pkg = REMOVED if action == "restore" else REMOVABLE
            A.act(action, [pkg], self.env)
            self.assertEqual(pm_calls(self.fake)[-1], ["adb", "-s", SERIAL, "shell", *words, "--user", "0", pkg])

    def test_success_detection(self):
        for action, pkg in (("remove", REMOVABLE), ("disable", REMOVABLE), ("enable", REMOVABLE), ("restore", REMOVED)):
            res = A.act(action, [pkg], self.env)
            self.assertEqual(res["results"], [{"package": pkg, "action": action, "ok": True, "error": ""}], action)

    def test_failure_text_is_the_error(self):
        self.fake.prepend((["adb", "uninstall"], "Failure [DELETE_FAILED_INTERNAL_ERROR]\n", 0, 0))
        r = A.act("remove", [REMOVABLE], self.env)["results"][0]
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "Failure [DELETE_FAILED_INTERNAL_ERROR]")

    def test_wrong_state_text_is_a_failure(self):
        self.fake.prepend((["adb", "disable-user"], f"Package {REMOVABLE} new state: enabled\n", 0, 0))
        self.assertFalse(A.act("disable", [REMOVABLE], self.env)["results"][0]["ok"])

    def test_invalid_name_never_reaches_adb(self):
        res = A.act("remove", ["foo; reboot", REMOVABLE], self.env)["results"]
        self.assertEqual(res[0], {"package": "foo; reboot", "action": "remove", "ok": False, "error": "invalid package name"})
        self.assertTrue(res[1]["ok"])
        self.assertFalse(any("foo; reboot" in " ".join(c) for c in self.fake.calls()))

    def test_unknown_package_refused(self):
        r = A.act("remove", ["com.not.there"], self.env)["results"][0]
        self.assertEqual((r["ok"], r["error"]), (False, "not on this phone"))
        self.assertEqual(pm_calls(self.fake), [])

    def test_unsafe_needs_force(self):
        for action in ("remove", "disable"):
            r = A.act(action, [UNSAFE], self.env)["results"][0]
            self.assertEqual((r["ok"], r["error"]), (False, "rated Unsafe: refused without --force"))
        self.assertEqual(pm_calls(self.fake), [])
        A.act("remove", [UNSAFE], self.env, force=True)
        self.assertEqual(pm_calls(self.fake)[-1][-1], UNSAFE)

    def test_without_safety_list_disable_and_remove_need_force(self):
        A.cache_path(self.env).unlink()
        r = A.act("remove", [REMOVABLE], self.env)["results"][0]
        self.assertEqual((r["ok"], r["error"]), (False, "no safety list: refused without --force"))
        self.assertTrue(A.act("enable", [REMOVABLE], self.env)["results"][0]["ok"])
        self.assertFalse(A.cache_path(self.env).exists())          # an action never downloads

    def test_remove_without_factory_copy_needs_force(self):
        self.fake.prepend((["adb", "dumpsys", "package", REMOVABLE], "@dumpsys_feedback.txt", 0, 0))
        r = A.act("remove", [REMOVABLE], self.env)["results"][0]
        self.assertEqual((r["ok"], r["error"]),
                         (False, "no factory copy on the phone: removing would delete it for good (use Disable, or --force)"))
        self.assertEqual(pm_calls(self.fake), [])
        self.assertTrue(A.act("disable", [REMOVABLE], self.env)["results"][0]["ok"])
        self.assertTrue(A.act("remove", [REMOVABLE], self.env, force=True)["results"][0]["ok"])

    def test_remove_of_updated_system_app_is_allowed(self):
        self.fake.prepend((["adb", "dumpsys", "package", REMOVABLE], "@dumpsys_gm.txt", 0, 0))
        self.assertTrue(A.act("remove", [REMOVABLE], self.env)["results"][0]["ok"])

    def test_restore_and_enable_never_need_force(self):
        self.fake.prepend((["adb", "enable"], f"Package {UNSAFE} new state: enabled\n", 0, 0))
        self.assertTrue(A.act("enable", [UNSAFE], self.env)["results"][0]["ok"])

    def test_history_line_per_package(self):
        A.act("remove", [REMOVABLE, "bad name"], self.env)
        lines = [json.loads(l) for l in A.history_path(self.env).read_text().splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(set(lines[0]), {"time", "serial", "model", "package", "action", "ok", "error"})
        self.assertEqual((lines[0]["serial"], lines[0]["model"], lines[0]["package"], lines[0]["ok"]),
                         (SERIAL, "V2503", REMOVABLE, True))
        self.assertFalse(lines[1]["ok"])

    def test_action_with_no_device_reports_each_package(self):
        self.fake.prepend((["adb", "devices"], "List of devices attached\n\n", 0, 0))
        out = io.StringIO()
        with redirect_stdout(out):
            code = A.main(["remove", REMOVABLE, "com.vivo.notes"], self.env)
        res = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertIn("no phone connected", res["error"].lower())
        self.assertEqual(pm_calls(self.fake), [])

    def test_two_devices_need_serial(self):
        two = ("List of devices attached\n192.168.1.31:45833 device model:V2503 transport_id:7\n"
               "adb-X._adb-tls-connect._tcp device model:V2503 transport_id:6\n\n")
        self.fake.prepend((["adb", "devices"], two, 0, 0))
        with self.assertRaises(A.AndroidError):
            A.act("remove", [REMOVABLE], self.env)
        self.assertEqual(pm_calls(self.fake), [])
        A.act("remove", [REMOVABLE], self.env, serial="adb-X._adb-tls-connect._tcp")
        self.assertEqual(pm_calls(self.fake)[-1][:3], ["adb", "-s", "adb-X._adb-tls-connect._tcp"])

    def test_timeout_is_a_failed_result(self):
        self.fake.prepend((["adb", "uninstall"], "Success\n", 0, 2))
        old, A.QUICK = A.QUICK, 0.3
        try:
            r = A.act("remove", [REMOVABLE], self.env)["results"][0]
        finally:
            A.QUICK = old
        self.assertEqual((r["ok"], r["error"]), (False, "timed out"))

    def test_main_action_prints_results(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = A.main(["disable", REMOVABLE, "--serial", SERIAL], self.env)
        res = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(res["serial"], SERIAL)
        self.assertTrue(res["results"][0]["ok"])

    def test_main_force_flag_and_empty_package_list(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(A.main(["remove", UNSAFE, "--force"], self.env), 0)
        self.assertTrue(json.loads(out.getvalue())["results"][0]["ok"])
        err = io.StringIO()
        old, sys.stderr = sys.stderr, err
        try:
            self.assertEqual(A.main(["remove"], self.env), 2)
        finally:
            sys.stderr = old


if __name__ == "__main__":
    unittest.main()
