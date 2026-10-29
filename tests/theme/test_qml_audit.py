import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "dotfiles/bin/.local/bin/bbkos-qml-audit"


def make_tree(root, files):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


BASE = {
    "Theme.qml": "pragma Singleton\nimport QtQuick\nQtObject {}\n",
    "services/PanelState.qml": "pragma Singleton\nimport QtQuick\nQtObject { property bool open }\n",
    "components/Card.qml": "import QtQuick\nimport qs\nRectangle { color: Theme.bg }\n",
}


def run(d):
    return subprocess.run([sys.executable, str(TOOL), str(d)], capture_output=True, text=True)


class AuditTest(unittest.TestCase):
    def test_missing_import_fails_naming_file(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE, "modules/Bar.qml":
                          "import QtQuick\nItem { visible: PanelState.open }\n"})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("MISSING qs.services for PanelState in", r.stdout)
            self.assertIn("Bar.qml", r.stdout)

    def test_missing_component_and_theme(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE, "modules/Bar.qml":
                          "import QtQuick\nItem { Card { color: Theme.bg } }\n"})
            r = run(t)
            self.assertEqual(r.returncode, 1)
            self.assertIn("MISSING qs.components for Card in", r.stdout)
            self.assertIn("MISSING qs for Theme in", r.stdout)

    def test_correct_tree_passes(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE,
                          "modules/Bar.qml": "import QtQuick\nimport qs\nimport qs.services\n"
                                             "import qs.components\nItem { Card {} x: PanelState.n; y: Theme.g }\n",
                          "services/Other.qml": "import QtQuick\nItem { v: PanelState.open }\n",
                          "components/Two.qml": "import QtQuick\nCard {}\n"})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("missing imports: 0", r.stdout)

    def test_comments_and_strings_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE, "modules/Bar.qml":
                          'import QtQuick\n// PanelState.open\n/* Card { } */\n'
                          'Item { property string s: "PanelState.x \\" Card {" ; '
                          "property string u: 'Theme.a' }\n"})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_non_identifier_uses_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE, "modules/Bar.qml":
                          "import QtQuick\nItem { x: foo.Theme.a; property var m: MyCard {} ; y: Card }\n"})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_bad_dir_exits_nonzero(self):
        r = run("/nonexistent-dir-xyz")
        self.assertNotEqual(r.returncode, 0)

    @unittest.skipUnless((Path.home() / ".config/quickshell").is_dir(), "no live tree")
    def test_real_tree_clean(self):
        r = subprocess.run([sys.executable, str(TOOL)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


BAD = "import QtQuick\nItem {\n    Item {}\n    }\n}\n"


class SyntaxTest(unittest.TestCase):
    """The qmlformat pass: a file that does not parse fails the audit, as the 2026-10-29 extra brace should have."""

    def test_syntax_error_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE, "modules/Good.qml": "import QtQuick\nItem {}\n", "modules/Bad.qml": BAD})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            lines = [l for l in r.stdout.splitlines() if l.startswith("SYNTAX ")]
            self.assertEqual(len(lines), 1, r.stdout)
            self.assertTrue(lines[0].startswith("SYNTAX modules/Bad.qml"), lines[0])
            self.assertNotIn("syntax errors: 0", r.stdout)

    def test_clean_tree_reports_zero(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, BASE)
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("syntax errors: 0", r.stdout)

    def test_no_qmlformat_skips_the_pass(self):
        with tempfile.TemporaryDirectory() as t:
            make_tree(t, {**BASE, "modules/Bad.qml": BAD})
            r = subprocess.run([sys.executable, str(TOOL), t], capture_output=True, text=True,
                               env={**os.environ, "BBKOS_QMLFORMAT": "/nonexistent/qmlformat"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("syntax check skipped", r.stdout)


if __name__ == "__main__":
    unittest.main()
