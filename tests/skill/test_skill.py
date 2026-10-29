"""The bbkOS skill (.claude/skills/bbkos): its frontmatter, structure, and that everything it names exists, so it
cannot silently go stale (docs/specs/2026-10-20-bbkos-skill-design.md)."""
import contextlib
import importlib.util
import io
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / ".claude/skills/bbkos"
SKILL = SKILL_DIR / "SKILL.md"
STOW = "stow --no-folding -d ~/.local/share/bbkos/repo/dotfiles -t ~"
HEADINGS = ["## What bbkOS is", "## Rules", "## Where things live", "## Tools", "## Example requests",
            "## Where to read", "## Finishing a change"]
PATH_PREFIXES = ("docs/", "scripts/", "tests/", "dotfiles/", "touchpad/", "power/", ".claude/")


def text():
    return SKILL.read_text(encoding="utf-8")


def backticked():
    return re.findall(r"`([^`\n]+)`", text())


class SkillTest(unittest.TestCase):
    def test_index_is_current(self):
        spec = importlib.util.spec_from_file_location("build_skill_index", ROOT / "scripts/build-skill-index.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = mod.main(["--check"])
        self.assertEqual(rc, 0, err.getvalue())

    def test_frontmatter(self):
        t = text()
        m = re.match(r"---\nname: (\S+)\ndescription: (.+)\n---\n", t)
        self.assertIsNotNone(m, "frontmatter must be exactly name then description")
        self.assertEqual(m.group(1), "bbkos")
        self.assertEqual(m.group(1), SKILL_DIR.name)
        self.assertTrue(0 < len(m.group(2)) <= 1024, len(m.group(2)))

    def test_description_names_the_paths_and_triggers_that_load_the_skill(self):
        desc = re.match(r"---\nname: \S+\ndescription: (.+)\n---\n", text()).group(1)
        for needle in ("~/.config/hypr", "~/.config/quickshell", "~/.config/bbkos", "bbkos-*"):
            self.assertIn(needle, desc, needle)

    def test_theme_keys_in_examples_exist(self):
        source = (ROOT / "dotfiles/bin/.local/lib/bbkos_theme/settings.py").read_text(encoding="utf-8")
        keys = re.findall(r"bbkos-theme set (\w+\.\w+)", text())
        self.assertGreater(len(keys), 1, "the examples should use real settings")
        for key in keys:
            self.assertIn(f'"{key}"', source, key)

    def test_line_limit(self):
        self.assertLessEqual(len(text().splitlines()), 200)

    def test_section_headings_in_order(self):
        found = [l for l in text().splitlines() if l.startswith("## ")]
        self.assertEqual(found, HEADINGS)

    def test_named_repo_paths_exist(self):
        checked = 0
        for tok in backticked():
            if not tok.startswith(PATH_PREFIXES) or any(c in tok for c in "*< "):
                continue
            checked += 1
            self.assertTrue((ROOT / tok.rstrip("/")).exists(), f"{tok} does not exist")
        self.assertGreater(checked, 5, "the skill should name real paths")

    def test_named_commands_exist(self):
        dirs = [ROOT / "dotfiles/bin/.local/bin", ROOT / "scripts"]
        checked = 0
        for tok in backticked():
            if not tok.startswith("bbkos-") or "*" in tok:
                continue
            name = tok.split()[0]
            checked += 1
            self.assertTrue(any((d / name).exists() for d in dirs), f"{name} is not a command in this repo")
        self.assertGreater(checked, 5, "the skill should name the tools")

    def test_stow_command_matches_the_readme(self):
        self.assertIn(STOW, text())
        self.assertIn(STOW, (ROOT / "dotfiles/README.md").read_text(encoding="utf-8"))

    def test_required_rules_present(self):
        t = text()
        for needle in ("-t ~", "sudo", "&&", "changelog", "verified", "settings.json", "push",
                       "configerrors", "hl.meta.lua", "/usr/local/sbin", "quickshell.md"):
            self.assertIn(needle, t, needle)


if __name__ == "__main__":
    unittest.main()
