import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "dotfiles/bin/.local/lib"
sys.path.insert(0, str(LIB))

from bbkos_theme import keybinds_cli as C  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
WRAPPER = ROOT / "dotfiles/bin/.local/bin/bbkos-keybinds"
DEFAULTS = LIB / "bbkos_theme/keybinds.defaults.json"


def bind(id_, key="F12", mods=("SUPER", "SHIFT"), action=None, enabled=True, **flags):
    f = {"locked": False, "repeating": False, "mouse": False}
    f.update(flags)
    return {"id": id_, "keys": {"mods": list(mods), "key": key},
            "action": action or {"type": "exec", "command": f"notify-send {id_}"},
            "flags": f, "enabled": enabled}


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.kb = self.base / "config/keybinds.json"
        self.bak = self.base / "config/keybinds.json.bak"
        self.state = self.base / "state"
        self.lua = self.state / "hypr-binds.lua"
        self.log = self.base / "hyprctl.log"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FAKE_")}
        self.env.update(PATH=f"{FIX / 'fake-bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                        BBKOS_KEYBINDS=str(self.kb), BBKOS_STATE_DIR=str(self.state),
                        FAKE_HYPRCTL_LOG=str(self.log), HYPRLAND_INSTANCE_SIGNATURE="test")

    def run_cli(self, *args, env=None, **extra):
        env = dict(self.env if env is None else env, **extra)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = C.main(list(args), env)
        return rc, out.getvalue(), err.getvalue()

    def json_file(self, obj, name="bind.json"):
        p = self.base / name
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return str(p)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def saved(self):
        return {b["id"]: b for b in json.loads(self.kb.read_text())["binds"]}

    def read(self, p):
        return p.read_text() if p.exists() else None

    # status

    def test_status_prints_binds_warnings_conflicts_actions(self):
        rc, out, _ = self.run_cli("status")
        self.assertEqual(rc, 0)
        s = json.loads(out)
        self.assertEqual(set(s), {"binds", "warnings", "conflicts", "actions", "shipped"})
        defaults = json.loads(DEFAULTS.read_text())["binds"]
        self.assertEqual(len(s["binds"]), len(defaults))
        self.assertEqual(s["warnings"], [])
        self.assertEqual(s["conflicts"], [])
        launcher = next(a for a in s["actions"] if a["id"] == "launcher")
        self.assertIn("missing", launcher)
        self.assertFalse(self.kb.exists())

    def test_status_shipped_lists_exactly_the_shipped_ids(self):
        s = json.loads(self.run_cli("status")[1])
        self.assertEqual(s["shipped"], [b["id"] for b in json.loads(DEFAULTS.read_text())["binds"]])

    def test_status_lists_conflicts_as_pairs(self):
        rows = json.loads(DEFAULTS.read_text())["binds"][:1]
        rows.append(bind("dup", key=rows[0]["keys"]["key"], mods=rows[0]["keys"]["mods"]))
        self.kb.parent.mkdir(parents=True)
        self.kb.write_text(json.dumps({"version": 1, "binds": rows}))
        s = json.loads(self.run_cli("status")[1])
        self.assertEqual(s["conflicts"], [[rows[0]["id"], "dup"]])

    # add

    def test_add_writes_json_lua_bak_and_reloads(self):
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("note")))
        self.assertEqual(rc, 0, err)
        self.assertIn("note", self.saved())
        self.assertIn("notify-send note", self.lua.read_text())
        self.assertEqual(self.calls(), ["configerrors", "reload", "configerrors"])
        self.assertFalse(self.bak.exists())  # nothing to back up the first time
        old = self.kb.read_text()
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("two", key="F11")))[0], 0)
        self.assertEqual(self.bak.read_text(), old)

    def test_add_duplicate_is_refused_with_exit_3(self):
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("dup", key="q", mods=["SUPER"])))
        self.assertEqual(rc, 3)
        self.assertIn("launch-terminal", err)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertFalse(self.kb.exists())
        self.assertFalse(self.lua.exists())
        self.assertEqual(self.calls(), [])

    def test_add_duplicate_with_replace_disables_the_other(self):
        rc, _, err = self.run_cli("add", "--replace", "--json",
                                  self.json_file(bind("dup", key="Q", mods=["SUPER"])))
        self.assertEqual(rc, 0, err)
        rows = self.saved()
        self.assertFalse(rows["launch-terminal"]["enabled"])
        self.assertTrue(rows["dup"]["enabled"])
        self.assertIn("notify-send dup", self.lua.read_text())

    def test_add_existing_id_is_refused(self):
        rc, _, _ = self.run_cli("add", "--json", self.json_file(bind("launch-terminal")))
        self.assertEqual(rc, 2)
        self.assertFalse(self.kb.exists())

    def test_bad_json_argument_exits_2_and_writes_nothing(self):
        rc, _, err = self.run_cli("add", "--json", self.json_file("{not json"))
        self.assertEqual(rc, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertFalse(self.kb.exists())
        self.assertFalse(self.lua.exists())
        self.assertEqual(self.calls(), [])

    def test_invalid_bind_exits_2_and_writes_nothing(self):
        for raw in (bind("x", key="NoSuchKey"), bind("x", action={"type": "preset", "id": "nope"}),
                    bind("x", action={"type": "dispatch", "name": "no.such.dispatcher", "args": {}}),
                    [1, 2]):
            rc, _, err = self.run_cli("add", "--json", self.json_file(raw))
            self.assertEqual(rc, 2, (raw, err))
        self.assertFalse(self.kb.exists())
        self.assertFalse(self.lua.exists())

    def test_json_from_stdin_via_wrapper(self):
        res = subprocess.run([sys.executable, "-B", str(WRAPPER), "add", "--json", "-"],
                             input=json.dumps(bind("piped")), env=self.env, capture_output=True,
                             text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("piped", self.saved())

    # failure and rollback

    def test_failed_reload_restores_previous_files(self):
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("first")))[0], 0)
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("second", key="F11")))[0], 0)
        old_kb, old_lua, old_bak = self.kb.read_text(), self.lua.read_text(), self.bak.read_text()
        self.log.unlink()
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("third", key="F10")),
                                  FAKE_HYPRCTL_RC="1")
        self.assertNotEqual(rc, 0)
        self.assertTrue(err.strip())
        self.assertEqual(self.kb.read_text(), old_kb)
        self.assertEqual(self.lua.read_text(), old_lua)
        self.assertEqual(self.bak.read_text(), old_bak)
        self.assertEqual([c for c in self.calls() if c == "reload"], ["reload", "reload"])

    def test_failed_reload_from_nothing_deletes_new_files(self):
        rc, _, _ = self.run_cli("add", "--json", self.json_file(bind("first")), FAKE_HYPRCTL_RC="1")
        self.assertEqual(rc, 1)
        self.assertFalse(self.kb.exists())
        self.assertFalse(self.lua.exists())
        self.assertFalse(self.bak.exists())

    def test_new_config_errors_after_reload_roll_back(self):
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("first")),
                                  FAKE_HYPRCTL_CONFIGERRORS_AFTER_RELOAD="line 3: boom")
        self.assertEqual(rc, 1)
        self.assertIn("boom", err)
        self.assertFalse(self.kb.exists())
        self.assertFalse(self.lua.exists())
        self.assertEqual([c for c in self.calls() if c == "reload"], ["reload", "reload"])

    def test_existing_config_errors_do_not_fail(self):
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("first")),
                                  FAKE_HYPRCTL_CONFIGERRORS="old error")
        self.assertEqual(rc, 0, err)

    def test_failed_restore_does_not_stop_the_others(self):
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("first")))[0], 0)
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("second", key="F11")))[0], 0)
        old_lua, old_bak = self.lua.read_text(), self.bak.read_text()
        self.log.unlink()
        real_restore = C._restore

        def restore(path, text):
            if Path(path) == self.kb:                     # the first restore fails
                raise OSError(13, "Permission denied", str(path))
            real_restore(path, text)

        C._restore = restore
        self.addCleanup(setattr, C, "_restore", real_restore)
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("third", key="F10")),
                                  FAKE_HYPRCTL_RC="1")
        self.assertEqual(rc, 1)
        lines = err.strip().splitlines()
        self.assertEqual(lines[0], "fake hyprctl failure")     # the original error is the first line
        self.assertTrue(any("could not restore" in ln for ln in lines[1:]), lines)
        self.assertEqual(self.bak.read_text(), old_bak)
        self.assertEqual(self.lua.read_text(), old_lua)
        self.assertEqual([c for c in self.calls() if c == "reload"], ["reload", "reload"])

    @unittest.skipIf(os.geteuid() == 0, "root can read a mode-000 file")
    def test_unreadable_lua_is_never_deleted(self):
        self.lua.parent.mkdir(parents=True)
        self.lua.write_text("-- mine\n")
        self.lua.chmod(0)
        self.addCleanup(self.lua.chmod, 0o644)
        rc, _, err = self.run_cli("add", "--json", self.json_file(bind("first")))
        self.assertNotEqual(rc, 0)
        self.assertTrue(err.strip())
        self.lua.chmod(0o644)
        self.assertEqual(self.lua.read_text(), "-- mine\n")
        self.assertFalse(self.kb.exists())
        self.assertEqual(self.calls(), [])

    def test_failed_apply_restores_lua(self):
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("first")))[0], 0)
        old_kb, old_lua = self.kb.read_text(), self.lua.read_text()
        self.lua.write_text("-- stale\n")
        rc, _, _ = self.run_cli("apply", FAKE_HYPRCTL_RC="1")
        self.assertEqual(rc, 1)
        self.assertEqual(self.lua.read_text(), "-- stale\n")
        self.assertEqual(self.kb.read_text(), old_kb)
        self.assertNotEqual(old_lua, "-- stale\n")

    # Hyprland absent

    def test_no_hyprland_saves_and_skips_reload(self):
        env = {k: v for k, v in self.env.items() if k != "HYPRLAND_INSTANCE_SIGNATURE"}
        rc, out, err = self.run_cli("add", "--json", self.json_file(bind("note")), env=env)
        self.assertEqual(rc, 0, err)
        self.assertIn("saved; reload skipped (Hyprland not running)", out + err)
        self.assertIn("note", self.saved())
        self.assertIn("notify-send note", self.lua.read_text())
        self.assertEqual(self.calls(), [])

    def test_no_hyprctl_saves_and_skips_reload(self):
        empty = self.base / "empty-bin"
        empty.mkdir()
        rc, out, err = self.run_cli("add", "--json", self.json_file(bind("note")), PATH=str(empty))
        self.assertEqual(rc, 0, err)
        self.assertIn("reload skipped", out + err)
        self.assertIn("note", self.saved())

    # locking

    def test_concurrent_mutations_serialise(self):
        procs = []
        for id_, key in (("one", "F11"), ("two", "F12")):
            env = dict(self.env, FAKE_HYPRCTL_SLEEP="0.5")
            procs.append(subprocess.Popen(
                [sys.executable, "-B", str(WRAPPER), "add", "--json", self.json_file(bind(id_, key=key), f"{id_}.json")],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        for p in procs:
            _, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 0, err)
        rows = self.saved()
        self.assertIn("one", rows)
        self.assertIn("two", rows)
        lua = self.lua.read_text()
        self.assertIn("notify-send one", lua)
        self.assertIn("notify-send two", lua)

    def test_mutation_waits_for_the_lock(self):
        import fcntl
        import time
        self.kb.parent.mkdir(parents=True)
        with open(str(self.kb) + ".lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            p = subprocess.Popen([sys.executable, "-B", str(WRAPPER), "add", "--json", self.json_file(bind("late"))],
                                 env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda: p.poll() is None and p.kill())
            time.sleep(1.0)
            self.assertIsNone(p.poll(), "mutation ran while the lock was held")
            self.assertFalse(self.kb.exists())
            fcntl.flock(lock, fcntl.LOCK_UN)
        _, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, err)
        self.assertIn("late", self.saved())

    # other commands

    def test_set_replaces_row_and_checks_id(self):
        new = bind("launch-terminal", key="T", mods=["SUPER"])
        rc, _, err = self.run_cli("set", "launch-terminal", "--json", self.json_file(new))
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.saved()["launch-terminal"]["keys"], {"mods": ["SUPER"], "key": "T"})
        rc, _, _ = self.run_cli("set", "close-window", "--json", self.json_file(new))
        self.assertEqual(rc, 2)
        rc, _, _ = self.run_cli("set", "no-such-id", "--json", self.json_file(bind("no-such-id")))
        self.assertEqual(rc, 1)

    def test_set_conflict_exit_3(self):
        new = bind("launch-terminal", key="C", mods=["SUPER"])
        rc, _, err = self.run_cli("set", "launch-terminal", "--json", self.json_file(new))
        self.assertEqual(rc, 3)
        self.assertIn("close-window", err)
        self.assertFalse(self.kb.exists())

    def test_disable_enable_remove(self):
        self.assertEqual(self.run_cli("disable", "launch-terminal")[0], 0)
        self.assertFalse(self.saved()["launch-terminal"]["enabled"])
        self.assertEqual(self.run_cli("enable", "launch-terminal")[0], 0)
        self.assertTrue(self.saved()["launch-terminal"]["enabled"])
        self.assertEqual(self.run_cli("remove", "launch-terminal")[0], 0)
        self.assertNotIn("launch-terminal", self.saved())
        self.assertEqual(self.run_cli("remove", "launch-terminal")[0], 1)

    def test_enable_into_conflict_exit_3(self):
        self.assertEqual(self.run_cli("disable", "launch-terminal")[0], 0)
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("dup", key="Q", mods=["SUPER"])))[0], 0)
        rc, _, err = self.run_cli("enable", "launch-terminal")
        self.assertEqual(rc, 3)
        self.assertIn("dup", err)

    def test_restore_and_restore_all(self):
        self.assertEqual(self.run_cli("set", "launch-terminal", "--json",
                                      self.json_file(bind("launch-terminal", key="T", mods=["SUPER"])))[0], 0)
        self.assertEqual(self.run_cli("restore", "launch-terminal")[0], 0)
        self.assertEqual(self.saved()["launch-terminal"]["keys"]["key"], "Q")
        self.assertEqual(self.run_cli("restore", "no-such-id")[0], 2)
        self.assertEqual(self.run_cli("add", "--json", self.json_file(bind("extra")))[0], 0)
        self.assertEqual(self.run_cli("restore-all")[0], 0)
        self.assertEqual(json.loads(self.kb.read_text())["binds"], json.loads(DEFAULTS.read_text())["binds"])

    def test_render_writes_lua_only(self):
        rc, _, err = self.run_cli("render")
        self.assertEqual(rc, 0, err)
        self.assertTrue(self.lua.read_text().startswith("-- "))
        self.assertFalse(self.kb.exists())
        self.assertEqual(self.calls(), [])

    def test_mutation_refuses_broken_file_but_restore_all_fixes_it(self):
        self.kb.parent.mkdir(parents=True)
        self.kb.write_text("{broken")
        rc, _, err = self.run_cli("disable", "launch-terminal")
        self.assertEqual(rc, 1)
        self.assertIn("nothing was changed", err)
        self.assertEqual(self.kb.read_text(), "{broken")
        self.assertEqual(self.run_cli("restore-all")[0], 0)
        self.assertEqual(self.bak.read_text(), "{broken")
        self.assertIn("launch-terminal", self.saved())

    def test_usage_errors_exit_2(self):
        for args in ([], ["frobnicate"], ["add"], ["remove"], ["status", "x"], ["add", "--json"]):
            self.assertEqual(self.run_cli(*args)[0], 2, args)


if __name__ == "__main__":
    unittest.main()
