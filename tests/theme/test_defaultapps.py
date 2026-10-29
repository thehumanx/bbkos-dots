"""bbkos-defaults (bbkos_theme/defaultapps.py) against temp desktop entries and a temp mimeapps.list."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))
from bbkos_theme import defaultapps as D  # noqa: E402


class DefaultAppsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        b = Path(self.tmp.name)
        self.env = {"HOME": str(b), "XDG_CONFIG_HOME": str(b / "config"), "XDG_DATA_HOME": str(b / "user"),
                    "XDG_DATA_DIRS": str(b / "sys")}
        self.user, self.sys = b / "user/applications", b / "sys/applications"
        self.user.mkdir(parents=True)
        self.sys.mkdir(parents=True)
        self.entry(self.sys, "imv", "imv", "image/png;image/jpeg;", extra="NoDisplay=true\n")
        self.entry(self.sys, "gone", "Gone", "image/png;", extra="Hidden=true\n")
        self.entry(self.sys, "vivaldi-stable", "Vivaldi", "text/html;x-scheme-handler/https;")
        # A hand-made entry with MimeType after its action group (the owner's Zen).
        (self.user / "zen.desktop").write_text("[Desktop Entry]\nType=Application\nName=Zen Browser\n"
                                               "[Desktop Action new]\nName=New Window\n"
                                               "MimeType=x-scheme-handler/https;text/html;\n")
        self.list = Path(self.env["XDG_CONFIG_HOME"]) / "mimeapps.list"

    def entry(self, d, id_, name, mime, extra=""):
        (d / f"{id_}.desktop").write_text(f"[Desktop Entry]\nType=Application\nName={name}\nMimeType={mime}\n{extra}")

    def cat(self, key):
        return next(c for c in D.status(self.env) if c["key"] == key)

    def test_candidates_include_nodisplay_handlers_not_hidden(self):
        self.assertEqual([c["id"] for c in self.cat("images")["candidates"]], ["imv.desktop"])
        self.assertEqual({c["id"] for c in self.cat("browser")["candidates"]}, {"zen.desktop", "vivaldi-stable.desktop"})

    def test_set_writes_every_type_and_keeps_other_lines(self):
        self.list.parent.mkdir(parents=True)
        self.list.write_text("[Default Applications]\ninode/directory=thunar.desktop\ntext/html=old.desktop\n\n"
                             "[Added Associations]\nx-scheme-handler/slack=slack.desktop;\n")
        self.assertEqual(D.main(["set", "browser", "zen"], self.env), 0)
        text = self.list.read_text()
        for m in ("x-scheme-handler/https", "x-scheme-handler/http", "text/html", "application/xhtml+xml"):
            self.assertIn(f"{m}=zen.desktop", text)
        self.assertNotIn("old.desktop", text)
        self.assertIn("inode/directory=thunar.desktop", text)
        self.assertIn("[Added Associations]\nx-scheme-handler/slack=slack.desktop;", text)
        self.assertLess(text.index("text/html=zen"), text.index("[Added Associations]"))   # inside its section
        self.assertEqual(self.cat("browser")["current"], "zen.desktop")

    def test_set_creates_the_file(self):
        self.assertEqual(D.main(["set", "images", "imv.desktop"], self.env), 0)
        self.assertTrue(self.list.read_text().startswith("[Default Applications]\nimage/png=imv.desktop"))

    def test_refuses_apps_that_cannot_open_the_category(self):
        self.assertEqual(D.main(["set", "images", "zen"], self.env), 1)
        self.assertEqual(D.main(["set", "nope", "zen"], self.env), 1)
        self.assertEqual(D.main(["set", "images", "missing"], self.env), 1)
        self.assertFalse(self.list.exists())

    def test_terminal_list(self):
        for id_, extra in (("kitty", ""), ("foot", ""), ("footclient", ""), ("kitty-open", "NoDisplay=true\n")):
            self.entry(self.sys, id_, id_, "", extra="Categories=System;TerminalEmulator;\n" + extra)
        cat = next(c for c in D.status(self.env) if c["key"] == "terminal")
        self.assertEqual([c["id"] for c in cat["candidates"]], ["foot.desktop", "kitty.desktop"])
        self.assertEqual(cat["current"], "")
        path = Path(self.env["XDG_CONFIG_HOME"]) / "xdg-terminals.list"
        path.parent.mkdir(parents=True)
        path.write_text("# mine\nkitty.desktop\n")
        self.assertEqual(D.main(["set", "terminal", "foot"], self.env), 0)
        self.assertEqual(path.read_text(), "foot.desktop\n# mine\nkitty.desktop\n")    # first wins, the rest kept
        self.assertEqual(next(c for c in D.status(self.env) if c["key"] == "terminal")["current"], "foot.desktop")
        self.assertEqual(D.main(["set", "terminal", "imv"], self.env), 1)                  # not a terminal

    def test_status_is_json_with_every_category(self):
        out = D.status(self.env)
        self.assertEqual([c["key"] for c in out], ["terminal"] + [c[0] for c in D.CATEGORIES])
        json.dumps(out)


if __name__ == "__main__":
    unittest.main()
