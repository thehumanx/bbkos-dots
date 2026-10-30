import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "dotfiles/quickshell/.config/quickshell/modules/settings"
spec = importlib.util.spec_from_file_location("build_settings_index", ROOT / "scripts/build-settings-index.py")
index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index)


class SettingsPagesTest(unittest.TestCase):
    """The settings window's page list (Pages.js), the window's component map and the search index agree."""

    def setUp(self):
        self.pages_js = (SETTINGS / "Pages.js").read_text(encoding="utf-8")
        self.places = index.places(self.pages_js)

    def test_search_index_is_fresh(self):
        self.assertEqual(index.main(["--repo", str(ROOT), "--check"]), 0,
                         "SearchIndex.js is stale: run python3 scripts/build-settings-index.py")

    def test_every_page_file_is_in_pages_js_and_in_the_window(self):
        named = {file for _, _, file in self.places}
        on_disk = {p.stem for p in SETTINGS.glob("Page*.qml")}
        self.assertEqual(on_disk - named, set(), "Page files no tab shows")
        self.assertEqual(named - on_disk, set(), "Pages.js names files that do not exist")
        window = (SETTINGS / "SettingsWindow.qml").read_text(encoding="utf-8")
        for file in named:
            self.assertRegex(window, r"\b%s: c%s\b" % (file, file))
            self.assertIn("Component { id: c%s; %s {} }" % (file, file), window)

    def test_places_are_unique_and_every_page_has_a_tab(self):
        places = [p for p, _, _ in self.places]
        self.assertEqual(len(places), len(set(places)))
        pages = re.findall(r'\{ id: "([\w-]+)", label: "[^"]+", group:', self.pages_js)
        self.assertEqual(len(pages), len(set(pages)))
        self.assertEqual(sorted(pages), sorted({p.split("/")[0] for p in places}))

    def test_rows_skip_chips_and_list_entries(self):
        qml = '''SettingsPage {
    SettingsSection {
        title: "Card"
        SettingChoice { label: "Mode"; hint: "Pick one"; key: "a.b"; model: [{ value: "x", label: "Chip" }] }
        SettingToggle { label: "On"; key: "a.c" }
    }
    readonly property var els: [{ id: "avatar", label: "Avatar" }]
}'''
        self.assertEqual(index.rows(qml), [("Mode", "Pick one", "Card"), ("On", "", "Card")])


    def test_bbkos_page_gathers_grid_rail_and_stage(self):
        """Owner (2026-10-31): what is particular to bbkOS is on one page, bbkOS, with these three tabs."""
        self.assertEqual([p for p, _, _ in self.places if p.startswith("bbkos/")], ["bbkos/grid", "bbkos/rail", "bbkos/stage"])
        rows = lambda f: [r[0] for r in index.rows((SETTINGS / f).read_text(encoding="utf-8"))]
        self.assertEqual(rows("PageGrid.qml"), ["Grid mode", "Round popups and controls in grid mode"])
        for label in ("Pinned apps", "Side", "Thickness", "Hug its contents", "Alignment"):
            self.assertIn(label, rows("PageRail.qml"))
        self.assertIn("Card length", rows("PageStage.qml"))
        self.assertNotIn("Grid mode", rows("PageShell.qml"))
        self.assertFalse(any(p == "windows/stage" for p, _, _ in self.places))


if __name__ == "__main__":
    unittest.main()
