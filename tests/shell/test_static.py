"""The static gate for the shell's QML (docs/specs/2026-10-29-shell-tests-design.md, layer 1).

- Every QML file parses (bbkos-qml-audit's qmlformat pass).
- qmllint's findings, counted per file and message id, are compared with tests/shell/qmllint-baseline.json. A count that
  goes up, or a file with findings that is not in the baseline, fails. A count that goes down (tidied code) passes and is
  printed as an improvement; fold it in with `python3 tests/shell/test_static.py --update-baseline` when convenient
  (owner's choice 2026-10-29: until then a harmless edit turned the suite red).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL_DIR = ROOT / "dotfiles/quickshell/.config/quickshell"
BASELINE = Path(__file__).resolve().parent / "qmllint-baseline.json"
QMLLINT = os.environ.get("BBKOS_QMLLINT", "/usr/lib/qt6/bin/qmllint")
AUDIT = ROOT / "dotfiles/bin/.local/bin/bbkos-qml-audit"


def lint_counts(root: Path) -> dict:
    """{rel path: {message id: count}} for every QML file under root with findings."""
    files = sorted(str(p) for p in root.rglob("*.qml"))
    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "lint.json"
        subprocess.run([QMLLINT, "-I", str(root), "--json", str(out), *files],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
        data = json.loads(out.read_text())
    result = {}
    for f in data.get("files", []):
        c = Counter(w.get("id") or w.get("type") or "?" for w in f.get("warnings", []))
        if c:
            result[str(Path(f["filename"]).resolve().relative_to(root.resolve()))] = dict(sorted(c.items()))
    return result


def _diff(base: dict, now: dict, worse: bool) -> list:
    out = []
    for rel in sorted(set(base) | set(now)):
        b, n = base.get(rel, {}), now.get(rel, {})
        for mid in sorted(set(b) | set(n)):
            bc, nc = b.get(mid, 0), n.get(mid, 0)
            if worse and nc > bc:
                out.append(f"{rel}: qmllint {mid} {bc} -> {nc} (new finding)")
            elif not worse and nc < bc:
                out.append(f"{rel}: qmllint {mid} {bc} -> {nc} (fewer: fold in with tests/shell/test_static.py --update-baseline)")
    return out


def compare(base: dict, now: dict) -> list:
    """Counts that went up against the baseline (failures), as messages."""
    return _diff(base, now, worse=True)


def improvements(base: dict, now: dict) -> list:
    """Counts that went down (not failures), as messages."""
    return _diff(base, now, worse=False)


class CompareTest(unittest.TestCase):
    BASE = {"a/A.qml": {"unqualified": 3, "import": 1}}

    def test_equal(self):
        self.assertEqual(compare(self.BASE, {"a/A.qml": {"import": 1, "unqualified": 3}}), [])

    def test_raised_count(self):
        p = compare(self.BASE, {"a/A.qml": {"unqualified": 4, "import": 1}})
        self.assertEqual(len(p), 1)
        self.assertIn("a/A.qml", p[0]); self.assertIn("unqualified", p[0]); self.assertIn("new finding", p[0])

    def test_lowered_count_is_not_a_failure(self):
        """Fewer findings (tidied code) pass; they are listed as improvements to fold into the baseline later."""
        now = {"a/A.qml": {"unqualified": 2, "import": 1}}
        self.assertEqual(compare(self.BASE, now), [])
        imp = improvements(self.BASE, now)
        self.assertEqual(len(imp), 1); self.assertIn("--update-baseline", imp[0])

    def test_new_file(self):
        p = compare(self.BASE, {**self.BASE, "b/B.qml": {"required": 1}})
        self.assertEqual(len(p), 1); self.assertIn("b/B.qml", p[0])

    def test_file_gone_is_an_improvement(self):
        self.assertEqual(compare(self.BASE, {}), [])
        self.assertEqual(len(improvements(self.BASE, {})), 2)


class ShellTest(unittest.TestCase):
    def test_shell_has_no_syntax_errors(self):
        r = subprocess.run([sys.executable, str(AUDIT), str(SHELL_DIR)], capture_output=True, text=True, timeout=300)
        self.assertNotIn("SYNTAX ", r.stdout, r.stdout)
        self.assertIn("syntax errors: 0", r.stdout, r.stdout + r.stderr)

    @unittest.skipUnless(shutil.which(QMLLINT) or Path(QMLLINT).exists(), "qmllint not installed")
    def test_lint_matches_baseline(self):
        base = json.loads(BASELINE.read_text())
        now = lint_counts(SHELL_DIR)
        for line in improvements(base, now):
            print(f"note: {line}", file=sys.stderr)
        self.assertEqual(compare(base, now), [])


if __name__ == "__main__":
    if sys.argv[1:] == ["--update-baseline"]:
        BASELINE.write_text(json.dumps(lint_counts(SHELL_DIR), indent=2, sort_keys=True) + "\n")
        print(f"wrote {BASELINE}")
    else:
        unittest.main()
