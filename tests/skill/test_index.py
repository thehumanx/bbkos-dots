"""scripts/build-skill-index.py: the generated docs index of the bbkOS skill."""
import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-skill-index.py"


def load():
    spec = importlib.util.spec_from_file_location("build_skill_index", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.m = load()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        (self.repo / "docs/modules").mkdir(parents=True)
        (self.repo / "docs/decisions").mkdir(parents=True)

    def doc(self, rel, text):
        p = self.repo / rel
        p.write_text(text, encoding="utf-8")
        return p

    def check(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = self.m.main(["--repo", str(self.repo), "--check"])
        return rc, err.getvalue()

    def test_title_and_summary(self):
        text = "# Foo\n\nFirst sentence. Second.\n"
        self.assertEqual(self.m.title_of(text, "x"), "Foo")
        self.assertEqual(self.m.summary_of(text), "First sentence")

    def test_title_fallback_to_file_name(self):
        self.assertEqual(self.m.title_of("no heading here\n", "zram.md"), "zram.md")

    def test_summary_skips_tables_lists_and_subheadings(self):
        for body in ("| a | b |\n|---|---|\n", "- one\n- two\n", "## Sub\n", "1. step\n", "```\ncode\n```\n"):
            self.assertEqual(self.m.summary_of("# T\n\n" + body), "", body)

    def test_summary_skips_status_lines_and_takes_the_next_prose_line(self):
        for meta in ("Applied: 2026-10-18 (Task 3)", "Status: **Accepted**", "Design: `docs/specs/x.md`"):
            text = f"# T\n\n{meta}\n\nWhat it really is. More.\n"
            self.assertEqual(self.m.summary_of(text), "What it really is", meta)

    def test_summary_is_cut_at_160_with_ellipsis(self):
        out = self.m.summary_of("# T\n\n" + "word " * 100 + "\n")
        self.assertEqual(len(out), 160)
        self.assertTrue(out.endswith("…"))

    def test_build_is_sorted_and_ignores_non_markdown(self):
        self.doc("docs/modules/b.md", "# B\n\nBee.\n")
        self.doc("docs/modules/a.md", "# A\n\nAye.\n")
        self.doc("docs/decisions/0001-x.md", "# X\n\nEx.\n")
        self.doc("docs/modules/cache.pyc", "junk")
        (self.repo / "docs/modules/__pycache__").mkdir()
        self.doc("docs/modules/__pycache__/a.md", "# Hidden\n")
        out = self.m.build(self.repo)
        lines = [l for l in out.splitlines() if l.startswith("- `")]
        self.assertEqual([l.split("`")[1] for l in lines],
                         ["docs/decisions/0001-x.md", "docs/modules/a.md", "docs/modules/b.md"])
        self.assertIn("A. Aye", lines[1])
        self.assertNotIn("Hidden", out)
        self.assertNotIn("cache.pyc", out)

    def test_empty_summary_leaves_just_the_title(self):
        self.doc("docs/modules/t.md", "# Table only\n\n| a |\n")
        line = [l for l in self.m.build(self.repo).splitlines() if "t.md" in l][0]
        self.assertTrue(line.endswith("Table only"))

    def test_build_is_deterministic(self):
        self.doc("docs/modules/a.md", "# A\n\nAye.\n")
        self.assertEqual(self.m.build(self.repo), self.m.build(self.repo))

    def test_check_passes_after_write_and_fails_after_a_new_module(self):
        self.doc("docs/modules/a.md", "# A\n\nAye.\n")
        self.assertEqual(self.m.main(["--repo", str(self.repo)]), 0)
        self.assertEqual(self.check()[0], 0)
        self.doc("docs/modules/new.md", "# New\n\nNovel.\n")
        rc, err = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("python3 scripts/build-skill-index.py", err)

    def test_check_fails_when_the_file_is_missing(self):
        self.doc("docs/modules/a.md", "# A\n\nAye.\n")
        rc, err = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("python3 scripts/build-skill-index.py", err)

    def script(self, name, body):
        d = self.repo / "dotfiles/bin/.local/bin"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding="utf-8")

    def test_command_summary_forms(self):
        cases = {
            "# bbkos-a: does a thing. More text.\n": "does a thing",
            "# bbkos-b {up|down}\n# Changes the brightness. Then more.\n": "Changes the brightness",
            '"""bbkos-c: edits things (see docs/x.md)."""\nimport os\n': "edits things (see docs/x.md)",
            '"""Audit a config for missing lines.\n\nUsage: bbkos-d [DIR]\n"""\n': "Audit a config for missing lines",
        }
        for body, want in cases.items():
            name = "bbkos-" + body.split("bbkos-")[1][0] if "bbkos-" in body.split("\n")[0] else "bbkos-d"
            self.assertEqual(self.m.command_summary("#!/bin/sh\n" + body, name), want, body)

    def test_command_summary_joins_a_wrapped_first_sentence(self):
        text = "#!/bin/sh\n# bbkos-w: starts here and\n# continues here. Next sentence.\n"
        self.assertEqual(self.m.command_summary(text, "bbkos-w"), "starts here and continues here")

    def test_command_summary_without_a_comment_is_empty(self):
        self.assertEqual(self.m.command_summary("#!/bin/sh\necho hi\n", "bbkos-x"), "")

    def test_build_lists_every_bbkos_command_sorted(self):
        self.script("bbkos-zed", "#!/bin/sh\n# bbkos-zed: last one.\n")
        self.script("bbkos-alpha", "#!/bin/sh\n# bbkos-alpha: first one.\n")
        self.script("not-a-command", "#!/bin/sh\n# not-a-command: ignored.\n")
        out = self.m.build(self.repo)
        self.assertIn("## Commands", out)
        cmds = [l for l in out.split("## Commands")[1].splitlines() if l.startswith("- `")]
        self.assertEqual([l.split("`")[1] for l in cmds], ["bbkos-alpha", "bbkos-zed"])
        self.assertIn("first one", cmds[0])
        self.assertNotIn("not-a-command", out)

    def test_crlf_files_are_read_like_lf_files(self):
        self.doc("docs/modules/a.md", "# A\r\n\r\nAye. More.\r\n")
        self.assertIn("A. Aye\n", self.m.build(self.repo) + "\n")


if __name__ == "__main__":
    unittest.main()
