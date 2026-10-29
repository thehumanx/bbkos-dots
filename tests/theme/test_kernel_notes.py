"""bbkos-kernel-notes: for pending kernel updates (checkupdates output on stdin) print the version jump and the
kernel.org changelog URL, so the owner can read what changed before upgrading. No network access: it only prints links."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "dotfiles/bin/.local/bin/bbkos-kernel-notes"
URL = "https://cdn.kernel.org/pub/linux/kernel"


def run(stdin):
    return subprocess.run([str(SCRIPT)], input=stdin, capture_output=True, text=True, timeout=20)


class KernelNotesTest(unittest.TestCase):
    def test_no_kernel_in_the_list_prints_nothing(self):
        r = run("firefox 1.0-1 -> 1.1-1\nlinux-firmware 2025-1 -> 2026-1\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "")

    def test_empty_input_prints_nothing(self):
        self.assertEqual(run("").stdout, "")

    def test_mainline_point_release_gets_the_changelog_link(self):
        r = run("linux 7.2.11.arch1-1 -> 7.2.12.arch1-1\n")
        self.assertIn("linux 7.2.11 -> 7.2.12", r.stdout)
        self.assertIn(f"{URL}/v7.x/ChangeLog-7.2.12", r.stdout)
        self.assertNotIn("new series", r.stdout)

    def test_lts_point_release_gets_the_changelog_link(self):
        r = run("linux-lts 6.18.57-2 -> 6.18.58-1\n")
        self.assertIn("linux-lts 6.18.57 -> 6.18.58", r.stdout)
        self.assertIn(f"{URL}/v6.x/ChangeLog-6.18.58", r.stdout)

    def test_packaging_only_change_says_so_and_has_no_link(self):
        r = run("linux-lts 6.18.57-2 -> 6.18.57-3\n")
        self.assertIn("same kernel 6.18.57, packaging change only", r.stdout)
        self.assertNotIn("ChangeLog", r.stdout)

    def test_new_series_is_called_out_with_both_changelogs(self):
        r = run("linux 7.2.14.arch1-1 -> 7.3.1.arch1-1\n")
        self.assertIn("new series 7.2 -> 7.3", r.stdout)
        self.assertIn(f"{URL}/v7.x/ChangeLog-7.3.1", r.stdout)

    def test_series_release_without_a_patch_number(self):
        r = run("linux 7.2.14.arch1-1 -> 7.3.arch1-1\n")
        self.assertIn(f"{URL}/v7.x/ChangeLog-7.3\n", r.stdout)

    def test_the_fallback_is_named_whenever_a_kernel_is_pending(self):
        r = run("linux 7.2.11.arch1-1 -> 7.2.12.arch1-1\n")
        self.assertIn("linux-lts", r.stdout)
        self.assertIn("Advanced options", r.stdout)

    def test_both_kernels_pending_lists_both(self):
        r = run("linux 7.2.11.arch1-1 -> 7.2.12.arch1-1\nlinux-lts 6.18.57-2 -> 6.18.58-1\n")
        self.assertIn("ChangeLog-7.2.12", r.stdout)
        self.assertIn("ChangeLog-6.18.58", r.stdout)

    def test_unparsable_version_still_names_the_package_and_never_crashes(self):
        r = run("linux 7.3.rc1.arch1-1 -> 7.3.rc2.arch1-1\n")
        self.assertEqual(r.returncode, 0)
        self.assertIn("linux 7.3.rc1.arch1-1 -> 7.3.rc2.arch1-1", r.stdout)
        self.assertNotIn("ChangeLog", r.stdout)

    def test_headers_and_blank_lines_are_ignored(self):
        r = run("\nPending:\nlinux 7.2.11.arch1-1 -> 7.2.12.arch1-1\n\n")
        self.assertEqual(r.returncode, 0)
        self.assertIn("ChangeLog-7.2.12", r.stdout)


class UpdateWiringTest(unittest.TestCase):
    """bbkos-update shows the kernel notes right after the pending list. Fake checkupdates, yay, qs and
    bbkos-progress stand in for the live system; yay fails so nothing is ever upgraded."""

    def run_update(self, pending):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fake = Path(tmp.name)
        scripts = {"checkupdates": f"#!/bin/sh\nprintf '%s' '{pending}'\n",
                   "yay": "#!/bin/sh\nexit 1\n", "qs": "#!/bin/sh\nexit 0\n",
                   "bbkos-progress": "#!/bin/sh\nexit 0\n"}
        for name, body in scripts.items():
            (fake / name).write_text(body)
            (fake / name).chmod(0o755)
        env = {"PATH": f"{fake}:{ROOT / 'dotfiles/bin/.local/bin'}:/usr/bin:/bin", "HOME": tmp.name}
        return subprocess.run([str(ROOT / "dotfiles/bin/.local/bin/bbkos-update")], env=env, input="\n",
                              capture_output=True, text=True, timeout=30)

    def test_kernel_notes_follow_the_pending_list(self):
        r = self.run_update("firefox 1.0-1 -> 1.1-1\nlinux 7.2.11.arch1-1 -> 7.2.12.arch1-1\n")
        out = r.stdout
        self.assertIn("firefox 1.0-1 -> 1.1-1", out)
        self.assertEqual(out.count("linux 7.2.11.arch1-1 -> 7.2.12.arch1-1"), 1, out)
        self.assertLess(out.index("Pending repo updates"), out.index("Kernel updates"))
        self.assertIn("ChangeLog-7.2.12", out)
        self.assertLess(out.index("ChangeLog-7.2.12"), out.index("Arch news"))

    def test_no_kernel_pending_prints_no_kernel_section(self):
        out = self.run_update("firefox 1.0-1 -> 1.1-1\n").stdout
        self.assertNotIn("Kernel updates", out)
        self.assertIn("firefox 1.0-1 -> 1.1-1", out)

    def test_nothing_pending_still_says_so(self):
        out = self.run_update("").stdout
        self.assertIn("none (or the check failed)", out)
        self.assertNotIn("Kernel updates", out)


if __name__ == "__main__":
    unittest.main()
