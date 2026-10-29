"""bbkos-autostart: the freedesktop autostart folder. Everything happens in a temporary home; nothing touches the real one."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import autostart as A  # noqa: E402

ENTRY = "[Desktop Entry]\nType=Application\nName={name}\nExec={exec}\nIcon=x\n"


class AutostartTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.sys = self.dir / "etc/xdg/autostart"
        self.apps = self.dir / "share/applications"
        for d in (self.sys, self.apps):
            d.mkdir(parents=True)
        self.env = {"HOME": str(self.dir / "home"), "XDG_CONFIG_HOME": str(self.dir / "home/.config"),
                    "XDG_CONFIG_DIRS": str(self.dir / "etc/xdg"), "XDG_DATA_HOME": str(self.dir / "home/.local/share"),
                    "XDG_DATA_DIRS": str(self.dir / "share")}
        (self.sys / "keyring.desktop").write_text(ENTRY.format(name="Secrets", exec="keyring --start"))
        (self.apps / "chat.desktop").write_text(ENTRY.format(name="Chat", exec="chat --background"))
        (self.apps / "hidden.desktop").write_text(ENTRY.format(name="Helper", exec="h") + "NoDisplay=true\n")
        self.user = Path(self.env["XDG_CONFIG_HOME"]) / "autostart"

    def status(self):
        return A.status(self.env)

    def test_lists_system_entries_and_the_apps_that_can_be_added(self):
        st = self.status()
        self.assertEqual([(e["id"], e["enabled"], e["source"]) for e in st["entries"]], [("keyring.desktop", True, "system")])
        self.assertEqual([a["id"] for a in st["apps"]], ["chat.desktop"])           # NoDisplay apps are not offered

    def test_add_copies_the_app_and_it_leaves_the_addable_list(self):
        A.add(self.env, "chat.desktop")
        self.assertIn("Exec=chat --background", (self.user / "chat.desktop").read_text())
        st = self.status()
        self.assertEqual([(e["id"], e["source"]) for e in st["entries"]][0], ("chat.desktop", "user"))
        self.assertEqual(st["apps"], [])

    def test_disable_and_enable_a_user_entry_keep_the_file(self):
        A.add(self.env, "chat.desktop")
        A.disable(self.env, "chat.desktop")
        self.assertIn("Hidden=true", (self.user / "chat.desktop").read_text())
        self.assertFalse(self.status()["entries"][0]["enabled"])
        A.enable(self.env, "chat.desktop")
        text = (self.user / "chat.desktop").read_text()
        self.assertNotIn("Hidden", text)
        self.assertIn("Exec=chat", text)
        self.assertTrue(self.status()["entries"][0]["enabled"])

    def test_a_system_entry_is_switched_off_by_an_override_and_on_by_deleting_it(self):
        A.disable(self.env, "keyring.desktop")
        self.assertEqual((self.user / "keyring.desktop").read_text(), "[Desktop Entry]\nType=Application\nName=Secrets\nHidden=true\n")
        e = self.status()["entries"][0]
        self.assertEqual((e["enabled"], e["source"]), (False, "override"))
        A.enable(self.env, "keyring.desktop")
        self.assertFalse((self.user / "keyring.desktop").exists())
        self.assertTrue(self.status()["entries"][0]["enabled"])

    def test_remove_deletes_a_user_entry_but_not_a_system_one(self):
        A.add(self.env, "chat.desktop")
        A.remove(self.env, "chat.desktop")
        self.assertFalse((self.user / "chat.desktop").exists())
        with self.assertRaises(ValueError):
            A.remove(self.env, "keyring.desktop")

    def test_bad_ids_and_unknown_entries_are_refused(self):
        for bad in ("../x.desktop", "a/b.desktop", "x", ".desktop", "x y.desktop"):
            with self.assertRaises(ValueError):
                A.add(self.env, bad)
        for fn in (A.add, A.enable, A.disable, A.remove):
            with self.assertRaises(ValueError):
                fn(self.env, "nothing.desktop")

    def test_hidden_key_is_set_inside_the_main_group_only(self):
        text = "[Desktop Entry]\nName=A\nHidden=false\n\n[Desktop Action x]\nName=B\n"
        out = A._set_hidden(text, True)
        self.assertEqual(out.count("Hidden=true"), 1)
        self.assertLess(out.index("Hidden=true"), out.index("[Desktop Action x]"))
        self.assertNotIn("Hidden", A._set_hidden(out, False))

    def test_main_prints_json_and_reports_errors(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(A.main(["status"], self.env), 0)
        self.assertIn("keyring.desktop", json.loads(buf.getvalue())["entries"][0]["id"])
        self.assertEqual(A.main(["disable", "nothing"], self.env), 1)
        self.assertEqual(A.main(["bogus"], self.env), 2)


if __name__ == "__main__":
    unittest.main()
