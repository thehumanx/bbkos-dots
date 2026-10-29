import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "dotfiles/quickshell/.config/quickshell/services/KeybindStore.qml"


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(STORE.is_file(), "KeybindStore.qml is missing")
        self.text = STORE.read_text()

    def test_singleton(self):
        self.assertTrue(self.text.startswith("pragma Singleton"))
        self.assertRegex(self.text, r"(?m)^Singleton \{")

    def test_functions(self):
        for fn in ("refresh", "add", "update", "remove", "setEnabled", "restore", "restoreAll"):
            self.assertRegex(self.text, rf"function {fn}\(", fn)

    def test_properties(self):
        for p in ("binds", "actions", "conflicts", "warnings", "shipped", "status"):
            self.assertRegex(self.text, rf"property \w+ {p}:", p)

    def test_watchdog_and_status(self):
        self.assertIn("watchdogMs: 60000", self.text)
        self.assertIn("signal(9)", self.text)
        self.assertIn('"error: "', self.text)
        self.assertIn('"applying"', self.text)

    def test_never_writes_files(self):
        self.assertNotIn("FileView", self.text)
        self.assertNotIn("setText", self.text)


QS = ROOT / "dotfiles/quickshell/.config/quickshell"


class PageTest(unittest.TestCase):
    def test_files_exist(self):
        for f in ("modules/settings/PageKeybindings.qml", "components/KeyCapture.qml", "components/ActionPicker.qml"):
            self.assertTrue((QS / f).is_file(), f)

    def test_sidebar_and_window(self):
        # Since 2026-10-28 the page is the Shortcuts tab of Keyboard (Pages.js); the window maps the name to the component.
        pages = (QS / "modules/settings/Pages.js").read_text()
        self.assertIn('{ id: "shortcuts", label: "Shortcuts", page: "PageKeybindings"', pages)
        self.assertIn("PageKeybindings: cPageKeybindings", (QS / "modules/settings/SettingsWindow.qml").read_text())

    def test_page_uses_store_functions(self):
        text = (QS / "modules/settings/PageKeybindings.qml").read_text()
        for fn in ("refresh", "add", "update", "remove", "setEnabled", "restore", "restoreAll"):
            self.assertRegex(text, rf"KeybindStore\.{fn}\(", fn)
        self.assertIn("KeybindStore.status", text)
        for bad in ("FileView", "setText", "Process"):
            self.assertNotIn(bad, text)

    def test_page_fix_round_1(self):
        text = (QS / "modules/settings/PageKeybindings.qml").read_text()
        self.assertIn("KeybindStore.shipped.includes(", text)
        self.assertNotIn('action?.type === "preset"\n', text.split("function restorable")[1].split("\n")[0] + "\n")
        self.assertIn("pendingSave", text)
        self.assertIn("active: page.editing", text)       # editor in a Loader: the picker is created fresh per edit
        picker = (QS / "components/ActionPicker.qml").read_text()
        self.assertRegex(picker, r"onChosen:[^\n]*picked\(null\)")   # a mode switch clears the chosen action

    def test_ipc_target_and_status_hook(self):
        text = (QS / "modules/settings/SettingsWindow.qml").read_text()
        self.assertIn('target: "keybinds"', text)
        self.assertRegex(text, r"function status\(\): string")
        self.assertIn("KeybindStore.binds.length", text)

    def test_components_are_pure_inputs(self):
        for f in ("KeyCapture", "ActionPicker"):
            text = (QS / f"components/{f}.qml").read_text()
            self.assertNotIn("KeybindStore.add", text, f)
            self.assertNotIn("KeybindStore.update", text, f)
            self.assertRegex(text, r"signal \w+\(", f)


if __name__ == "__main__":
    unittest.main()


class TouchpadSectionTest(unittest.TestCase):
    """The store must know every section, or resets of it are silently ignored (a fixed list of 9 fell behind 27 sections
    until 2026-10-28). It now reads them from settings.json itself; cards and rows reset their own keys."""

    def test_store_knows_every_section_of_the_file(self):
        src = (QS / "services" / "SettingsStore.qml").read_text()
        self.assertIn("Object.keys(values", src.split("readonly property var sections")[1].split("\n")[0])

    def test_cards_and_rows_reset_their_own_keys(self):
        self.assertIn("SettingsStore.resetMany(root.modifiedKeys)", (QS / "components" / "SettingsSection.qml").read_text())
        self.assertIn("SettingsStore.reset(root.key)", (QS / "components" / "SettingRow.qml").read_text())

    def test_store_keys_may_contain_digits(self):
        # touchpad.swipe4Up has a digit; a key rule without digits silently dropped every four-finger choice.
        src = (QS / "services" / "SettingsStore.qml").read_text()
        self.assertIn("A-Za-z0-9", src.split("function validKey")[1].split("\n")[0])


class BarLayoutTest(unittest.TestCase):
    def test_store_knows_the_bar_section(self):
        src = (QS / "services" / "SettingsStore.qml").read_text()
        self.assertIn("Object.keys(values", src.split("readonly property var sections")[1].split("\n")[0])
        self.assertIn('"bar.layout"', (QS / "modules" / "settings" / "BarLayoutEditor.qml").read_text())

    def test_bar_builds_sections_from_the_layout(self):
        src = (QS / "modules" / "bar" / "Bar.qml").read_text()
        self.assertIn('widgetsIn("start")', src)
        self.assertIn('widgetsIn("center")', src)
        self.assertIn('widgetsIn("end")', src)
