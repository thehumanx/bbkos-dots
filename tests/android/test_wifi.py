"""bbkos-android pair, connect, disconnect (docs/modules/android.md)."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_list import A, Base  # noqa: E402


class WifiTest(Base):
    def main_out(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = A.main(argv, self.env)
        return code, json.loads(out.getvalue()) if out.getvalue() else None

    def adb_calls(self):
        return [c for c in self.fake.calls() if c[0] == "adb"]

    def test_pair(self):
        self.fake.prepend((["adb", "pair"], "Successfully paired to 192.168.1.5:37000 [guid=adb-XYZ]\n", 0, 0))
        code, res = self.main_out(["pair", "192.168.1.5:37000", "123456"])
        self.assertEqual((code, res["ok"]), (0, True))
        self.assertIn("Successfully paired", res["message"])
        self.assertEqual(self.adb_calls(), [["adb", "pair", "192.168.1.5:37000", "123456"]])

    def test_pair_failure(self):
        self.fake.prepend((["adb", "pair"], "Failed: Wrong password or connection was dropped.\n", 1, 0))
        code, res = self.main_out(["pair", "192.168.1.5:37000", "654321"])
        self.assertEqual((code, res["ok"]), (0, False))
        self.assertIn("Wrong password", res["message"])

    def test_connect_messages(self):
        for text, ok in (("connected to 192.168.1.5:41000", True), ("already connected to 192.168.1.5:41000", True),
                         ("failed to connect to '192.168.1.5:41000': Connection refused", False),
                         ("cannot connect to 192.168.1.5:41000: No route to host (113)", False)):
            self.fake.prepend((["adb", "connect"], text + "\n", 0, 0))
            _, res = self.main_out(["connect", "192.168.1.5:41000"])
            self.assertEqual(res["ok"], ok, text)
            self.assertEqual(res["message"], text)

    def test_disconnect(self):
        self.fake.prepend((["adb", "disconnect"], "disconnected 192.168.1.5:41000\n", 0, 0))
        _, res = self.main_out(["disconnect", "192.168.1.5:41000"])
        self.assertTrue(res["ok"])
        self.assertEqual(self.adb_calls()[-1], ["adb", "disconnect", "192.168.1.5:41000"])
        self.main_out(["disconnect"])
        self.assertEqual(self.adb_calls()[-1], ["adb", "disconnect"])

    def test_invalid_address_or_code_never_reaches_adb(self):
        err = io.StringIO()
        old, sys.stderr = sys.stderr, err
        try:
            for argv in (["pair", "192.168.1.5", "123456"], ["pair", "192.168.1.5:37000", "12345"],
                         ["pair", "192.168.1.5:37000", "abcdef"], ["connect", "x;reboot:5555"],
                         ["connect", "host:0"], ["connect", "host:70000"], ["connect", "-s:5555"]):
                code, res = self.main_out(argv)
                self.assertEqual(code, 1, argv)
                self.assertFalse(res["ok"], argv)
        finally:
            sys.stderr = old
        self.assertEqual(self.adb_calls(), [])

    def test_valid_address(self):
        for ok in ("192.168.1.5:5555", "[fe80::1]:5555", "phone.local:41000", "pixel:1"):
            self.assertTrue(A.valid_address(ok), ok)
        for bad in ("192.168.1.5", ":5555", "a b:5", "host:0", "host:65536", "-host:5", "host:5x"):
            self.assertFalse(A.valid_address(bad), bad)


if __name__ == "__main__":
    unittest.main()
