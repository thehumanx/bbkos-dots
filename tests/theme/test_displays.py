import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))

from bbkos_theme import displays as D  # noqa: E402
from bbkos_theme import brightness as BR  # noqa: E402
from bbkos_theme import display_cli as C  # noqa: E402
from bbkos_theme import reload as R  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def mon(name="eDP-1", desc="Samsung 0x4187", w=1920, h=1200, scale=1.5, **kw):
    m = {"name": name, "description": desc, "width": w, "height": h, "refreshRate": 59.999,
         "scale": scale, "x": 0, "y": 0, "disabled": False}
    m.update(kw)
    return m


class ScaleTest(unittest.TestCase):
    def test_scale_options_1920x1200(self):
        opts = D.scale_options(1920, 1200)
        self.assertEqual(opts, [1.0, 1.1, 1.2, 1.25])

    def test_clamp_scale_picks_nearest_valid(self):
        self.assertEqual(D.clamp_scale(1.17, 1920, 1200), 1.2)
        self.assertEqual(D.clamp_scale(2.5, 1920, 1200), 1.25)

    def test_odd_resolution_offers_the_same_scales(self):
        self.assertEqual(D.scale_options(1367, 769), D.scale_options(1920, 1200))


class KeyTest(unittest.TestCase):
    def test_key_is_description(self):
        self.assertEqual(D.monitor_key(mon(), [mon()]), "Samsung 0x4187")

    def test_monitor_key_fallbacks(self):
        a, b = mon("DP-1", "Dell X"), mon("DP-2", "Dell X")
        self.assertEqual(D.monitor_key(a, [a, b]), "name:DP-1")
        self.assertEqual(D.monitor_key(mon("HDMI-A-1", ""), [mon("HDMI-A-1", "")]), "name:HDMI-A-1")

    def test_combo_key_is_order_independent(self):
        self.assertEqual(D.combo_key(["b", "a"]), D.combo_key(["a", "b"]))


class FileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "displays.json"

    def test_load_missing_file_gives_defaults(self):
        data, warns = D.load(self.path)
        self.assertEqual(data, {"version": 1, "monitors": {}, "layouts": {}})
        self.assertEqual(warns, [])

    def test_load_corrupt_json_warns_and_returns_defaults(self):
        self.path.write_text("{not json")
        data, warns = D.load(self.path)
        self.assertEqual(data["monitors"], {})
        self.assertEqual(len(warns), 1)

    def test_load_wrong_shaped_sections_warn(self):
        self.path.write_text(json.dumps({"version": 1, "monitors": [1], "layouts": "x"}))
        data, warns = D.load(self.path)
        self.assertEqual(data["monitors"], {})
        self.assertEqual(len(warns), 2)

    def test_load_drops_invalid_entries(self):
        self.path.write_text(json.dumps({"version": 1,
            "monitors": {"ok": {"scale": 1.5, "mode": "1920x1200@60"}, "bad": {"scale": "x"}},
            "layouts": {"c": {"mode": "bogus", "primary": "ok", "position": "right"},
                        "d": {"mode": "mirror", "primary": "ok", "position": "right"}}}))
        data, warns = D.load(self.path)
        self.assertEqual(list(data["monitors"]), ["ok"])
        self.assertEqual(list(data["layouts"]), ["d"])
        self.assertEqual(len(warns), 2)

    def test_save_atomic_roundtrip_and_no_tmp_left(self):
        data = {"version": 1, "monitors": {"k": {"scale": 2.0, "mode": "1920x1200@60"}}, "layouts": {}}
        D.save_atomic(self.path, data)
        self.assertEqual(D.load(self.path)[0], data)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["displays.json"])


A = mon("eDP-1", "Samsung 0x4187")
B = mon("DP-1", "Dell U2720Q", w=2560, h=1440, scale=1.0)


def data_for(mode="extend", position="right", primary="Samsung 0x4187", monitors=None):
    d = {"version": 1, "monitors": monitors or {}, "layouts": {}}
    d["layouts"][D.combo_key(["Samsung 0x4187", "Dell U2720Q"])] = {"mode": mode, "primary": primary, "position": position}
    return d


def by_output(rules):
    return {r["output"]: r for r in rules}


class ResolveTest(unittest.TestCase):
    def test_unknown_monitor_gets_defaults(self):
        (r,) = D.resolve(D.load("/nonexistent")[0], [A])
        self.assertEqual(r, {"output": "eDP-1", "mode": "preferred", "position": "auto",
                             "scale": "auto", "disabled": False, "mirror": None})

    def test_saved_scale_and_mode_applied(self):
        d = {"version": 1, "layouts": {}, "monitors": {"Samsung 0x4187": {"scale": 1.25, "mode": "1920x1200@60"}}}
        (r,) = D.resolve(d, [A])
        self.assertEqual((r["scale"], r["mode"]), (1.25, "1920x1200@60"))

    def test_extend_right_positions_by_logical_width(self):
        r = by_output(D.resolve(data_for("extend", "right", monitors={"Samsung 0x4187": {"scale": 1.25, "mode": "1920x1200@60"}}), [A, B]))
        self.assertEqual(r["eDP-1"]["position"], "0x0")
        self.assertEqual(r["desc:Dell U2720Q"]["position"], "1536x0")

    def test_position_left_above_below(self):
        pos = lambda p: by_output(D.resolve(data_for("extend", p), [A, B]))["desc:Dell U2720Q"]["position"]
        self.assertEqual(pos("left"), "-2560x0")      # partner scale 1.0 -> 2560 wide
        self.assertEqual(pos("above"), "0x-1440")
        self.assertEqual(pos("below"), "0x800")       # primary 1200 / 1.5

    def test_primary_can_be_the_second_monitor(self):
        r = by_output(D.resolve(data_for("extend", "right", primary="Dell U2720Q"), [A, B]))
        self.assertEqual(r["desc:Dell U2720Q"]["position"], "0x0")
        self.assertEqual(r["eDP-1"]["position"], "2560x0")

    def test_mirror_sets_mirror_field(self):
        r = by_output(D.resolve(data_for("mirror"), [A, B]))
        self.assertEqual(r["desc:Dell U2720Q"]["mirror"], "eDP-1")
        self.assertIsNone(r["eDP-1"]["mirror"])

    def test_only_disables_partner(self):
        r = by_output(D.resolve(data_for("only"), [A, B]))
        self.assertTrue(r["desc:Dell U2720Q"]["disabled"])
        self.assertFalse(r["eDP-1"]["disabled"])

    def test_saved_only_with_partner_gone_falls_back_to_single_rule(self):
        (r,) = D.resolve(data_for("only"), [A])
        self.assertFalse(r["disabled"])
        (r,) = D.resolve(data_for("only", primary="Dell U2720Q"), [B])
        self.assertFalse(r["disabled"])

    def test_two_identical_descriptions_use_names(self):
        a, b = mon("DP-1", "Dell X"), mon("DP-2", "Dell X")
        rules = D.resolve({"version": 1, "monitors": {}, "layouts": {}}, [a, b])
        self.assertEqual([r["output"] for r in rules], ["DP-1", "DP-2"])

    def test_saved_scale_clamped_after_mode_change(self):
        d = {"version": 1, "layouts": {}, "monitors": {"Samsung 0x4187": {"scale": 2.5, "mode": "1280x800@60"}}}
        (r,) = D.resolve(d, [A])
        self.assertEqual(r["scale"], 1.25)

    def test_three_monitors_extend_with_auto_positions(self):
        c = mon("DP-2", "Third")
        rules = D.resolve({"version": 1, "monitors": {}, "layouts": {}}, [A, B, c])
        self.assertEqual([r["position"] for r in rules], ["auto"] * 3)


class LidTest(unittest.TestCase):
    def test_internal_panel_rule_uses_output_name(self):
        (r,) = D.resolve(D.load("/nonexistent")[0], [A])
        self.assertEqual(r["output"], "eDP-1")

    def test_external_monitor_rule_uses_description(self):
        (r,) = D.resolve(D.load("/nonexistent")[0], [B])
        self.assertEqual(r["output"], "desc:Dell U2720Q")

    def test_lid_closed_disables_internal_when_external_enabled(self):
        r = by_output(D.resolve(data_for("extend"), [A, B], lid_closed=True))
        self.assertTrue(r["eDP-1"]["disabled"])
        self.assertFalse(r["desc:Dell U2720Q"]["disabled"])

    def test_lid_closed_single_monitor_keeps_internal(self):
        (r,) = D.resolve(D.load("/nonexistent")[0], [A], lid_closed=True)
        self.assertFalse(r["disabled"])

    def test_lid_closed_never_disables_internal_when_external_is_off(self):
        r = by_output(D.resolve(data_for("only", primary="Samsung 0x4187"), [A, B], lid_closed=True))
        self.assertTrue(r["desc:Dell U2720Q"]["disabled"])
        self.assertFalse(r["eDP-1"]["disabled"])

    def test_lid_open_keeps_internal_enabled(self):
        r = by_output(D.resolve(data_for("extend"), [A, B], lid_closed=False))
        self.assertFalse(r["eDP-1"]["disabled"])


class BusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.drm = Path(self.tmp.name)

    def link(self, connector, target):
        d = self.drm / f"card1-{connector}"
        d.mkdir()
        (d / "ddc").symlink_to(target)

    def test_bus_for_follows_the_connector_link(self):
        self.link("HDMI-A-1", "../../../i2c-3")
        self.link("DP-1", "i2c-12")
        self.assertEqual(BR.bus_for("HDMI-A-1", self.drm), 3)
        self.assertEqual(BR.bus_for("DP-1", self.drm), 12)

    def test_bus_for_unknown_connector_is_none(self):
        self.link("DP-1", "i2c-12")
        self.assertIsNone(BR.bus_for("DP-9", self.drm))

    def test_bus_for_odd_link_target_is_none(self):
        self.link("DP-2", "whatever")
        self.assertIsNone(BR.bus_for("DP-2", self.drm))


class RenderTest(unittest.TestCase):
    def test_description_with_quote_pipe_backslash_unicode_is_valid_lua(self):
        desc = 'Odd "mon" | \\ \u00e9\u4e2d\nline'
        m = mon("DP-9", desc)
        text = D.render_lua(D.resolve({"version": 1, "monitors": {}, "layouts": {}}, [m]))
        self.assertIn(R.lua_quote("desc:" + desc), text)
        self.assertEqual(len(text.splitlines()), 2)   # header + one rule, no raw newline from the description

    def test_render_matches_golden(self):
        d = data_for("extend", "right", monitors={"Samsung 0x4187": {"scale": 1.25, "mode": "1920x1200@60"}})
        text = D.render_lua(D.resolve(d, [A, B]))
        self.assertEqual(text, (FIX / "expected-hypr-monitors.lua").read_text())


def hypr_mon(m, modes):
    out = dict(m)
    out["availableModes"] = modes
    out["mirrorOf"] = "none"
    return out


MODES_A = ["1920x1200@60.00Hz", "1920x1200@48.00Hz", "1280x800@60.00Hz"]
MODES_B = ["2560x1440@60.00Hz", "1920x1080@60.00Hz"]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.displays = self.base / "config/displays.json"
        self.state = self.base / "state"
        self.log = self.base / "hyprctl.log"
        self.set_monitors([hypr_mon(A, MODES_A)])
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("FAKE_")}
        self.env.update(PATH=f"{FIX / 'fake-bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                        BBKOS_DISPLAYS=str(self.displays), BBKOS_STATE_DIR=str(self.state),
                        FAKE_HYPRCTL_LOG=str(self.log), BBKOS_LID_STATE="open",
                        BBKOS_DRM_DIR=str(self.base / "drm"), BBKOS_BACKLIGHT_DIR=str(self.base / "backlight"), FAKE_HYPRCTL_MONITORS=str(self.base / "mons.json"),
                        XDG_RUNTIME_DIR=str(self.base))   # the DDC lock and the max-value cache stay in the test dir

    def add_drm(self, connector="DP-1", target="../../../i2c-3", edid=b"monitor-a"):
        d = self.base / "drm" / f"card1-{connector}"
        d.mkdir(parents=True, exist_ok=True)
        if not (d / "ddc").is_symlink():
            (d / "ddc").symlink_to(target)
        (d / "edid").write_bytes(edid)

    def add_backlight(self):
        (self.base / "backlight/fake_backlight").mkdir(parents=True)

    def tool_calls(self, name):
        return [c for c in self.calls() if c.startswith(name + "\t")]

    def set_monitors(self, mons):
        (self.base / "mons.json").write_text(json.dumps(mons))

    def two(self):
        self.set_monitors([hypr_mon(A, MODES_A), hypr_mon(B, MODES_B)])

    def run_cli(self, *args, **extra):
        env = dict(self.env, **extra)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = C.main(list(args), env)
        return rc, out.getvalue(), err.getvalue()

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def evals(self):
        return [c for c in self.calls() if c.startswith("eval\t")]

    def saved(self):
        return json.loads(self.displays.read_text())

    def test_status_json_shape(self):
        rc, out, _ = self.run_cli("status")
        self.assertEqual(rc, 0)
        s = json.loads(out)
        m = s["monitors"][0]
        self.assertEqual((m["name"], m["key"], m["mode"], m["scale"]), ("eDP-1", "Samsung 0x4187", "1920x1200@60", 1.5))
        self.assertEqual(m["modes"], ["1920x1200@60", "1920x1200@48", "1280x800@60"])
        self.assertEqual(m["scaleOptions"], D.scale_options(1920, 1200))
        self.assertIsNone(m["mirrorOf"])
        self.assertIsNone(s["layout"])
        self.assertFalse(s["pending"])

    def test_status_layout_with_two_monitors(self):
        self.two()
        s = json.loads(self.run_cli("status")[1])
        self.assertEqual(s["layout"], {"mode": "extend", "position": "right", "primary": "eDP-1"})

    def test_set_scale_persists_and_applies(self):
        rc, _, err = self.run_cli("set-scale", "eDP-1", "1.25")
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(self.saved()["monitors"]["Samsung 0x4187"]["scale"], 1.25)
        self.assertIn("scale = 1.25", (self.state / "hypr-monitors.lua").read_text())
        self.assertEqual(len(self.evals()), 1)
        self.assertTrue(json.loads(self.run_cli("status")[1])["pending"])

    def test_invalid_scale_rejected_nothing_written(self):
        rc, _, err = self.run_cli("set-scale", "eDP-1", "1.77")
        self.assertEqual(rc, 1)
        self.assertIn("1.77", err)
        self.assertFalse(self.displays.exists())
        self.assertFalse((self.state / "hypr-monitors.lua").exists())
        self.assertEqual(self.evals(), [])

    def test_unknown_monitor_name_errors(self):
        rc, _, err = self.run_cli("set-scale", "DP-9", "1.5")
        self.assertEqual(rc, 1)
        self.assertIn("unknown monitor", err)

    def test_apply_failure_restores_previous_files(self):
        self.run_cli("set-scale", "eDP-1", "1.25")
        self.run_cli("keep")
        before = (self.displays.read_bytes(), (self.state / "hypr-monitors.lua").read_bytes())
        rc, _, err = self.run_cli("set-scale", "eDP-1", "1.2", FAKE_HYPRCTL_FAIL="1")
        self.assertEqual(rc, 1)
        self.assertEqual((self.displays.read_bytes(), (self.state / "hypr-monitors.lua").read_bytes()), before)
        self.assertFalse((self.state / "displays-prev.json").exists())

    def test_failed_first_change_leaves_no_files(self):
        rc, _, _ = self.run_cli("set-scale", "eDP-1", "1.2", FAKE_HYPRCTL_FAIL="1")
        self.assertEqual(rc, 1)
        self.assertEqual(sorted(p.name for p in self.state.glob("*")) if self.state.exists() else [], [])
        self.assertFalse(self.displays.exists())

    def test_apply_with_corrupt_file_changes_nothing(self):
        self.displays.parent.mkdir(parents=True)
        self.displays.write_text("{not json")
        self.state.mkdir(parents=True)
        (self.state / "hypr-monitors.lua").write_text("-- old rules\n")
        rc, _, err = self.run_cli("apply")
        self.assertEqual(rc, 0)
        self.assertIn("displays.json", err)
        self.assertEqual(self.displays.read_text(), "{not json")
        self.assertEqual((self.state / "hypr-monitors.lua").read_text(), "-- old rules\n")
        self.assertEqual(self.evals(), [])

    def test_set_scale_refuses_when_file_has_invalid_entries(self):
        self.displays.parent.mkdir(parents=True)
        text = json.dumps({"version": 1, "monitors": {"bad": {"scale": "x"}}, "layouts": {}})
        self.displays.write_text(text)
        rc, _, err = self.run_cli("set-scale", "eDP-1", "1.25")
        self.assertEqual(rc, 1)
        self.assertIn("displays.json", err)
        self.assertEqual(self.displays.read_text(), text)
        self.assertEqual(self.evals(), [])

    def test_failed_eval_reapplies_the_previous_rules(self):
        self.run_cli("set-scale", "eDP-1", "1.25")
        self.run_cli("keep")
        self.log.unlink()
        rc, _, _ = self.run_cli("set-scale", "eDP-1", "1.2", FAKE_HYPRCTL_FAIL="1")
        self.assertEqual(rc, 1)
        ev = self.evals()
        self.assertEqual(len(ev), 2)                       # the failed one, then the restore
        self.assertIn("hypr-monitors.lua", ev[1])

    def test_failed_first_change_reapplies_the_fallback_rule(self):
        rc, _, _ = self.run_cli("set-scale", "eDP-1", "1.2", FAKE_HYPRCTL_FAIL="1")
        self.assertEqual(rc, 1)
        ev = self.evals()
        self.assertEqual(len(ev), 2)
        self.assertIn('output = ""', ev[1])

    def test_apply_lid_closed_disables_internal_with_external(self):
        self.two()
        rc, _, _ = self.run_cli("apply", "--lid", "closed")
        self.assertEqual(rc, 0)
        lua = (self.state / "hypr-monitors.lua").read_text()
        self.assertIn('output = "eDP-1", mode = "preferred", position = "auto", scale = "auto", disabled = true', lua)

    def test_lid_state_env_is_used(self):
        self.two()
        self.run_cli("apply", BBKOS_LID_STATE="closed")
        self.assertIn("disabled = true", (self.state / "hypr-monitors.lua").read_text())

    def test_apply_after_lid_opens_restores_internal_panel(self):
        self.two()
        self.run_cli("apply", "--lid", "closed")
        self.assertEqual(self.run_cli("apply", "--lid", "open")[0], 0)
        self.assertNotIn("disabled", (self.state / "hypr-monitors.lua").read_text())

    def test_keep_removes_prev(self):
        self.run_cli("set-scale", "eDP-1", "1.25")
        self.assertEqual(self.run_cli("keep")[0], 0)
        self.assertFalse(json.loads(self.run_cli("status")[1])["pending"])

    def test_revert_restores_previous_state_and_reapplies(self):
        self.run_cli("set-scale", "eDP-1", "1.25")
        rc, _, _ = self.run_cli("revert")
        self.assertEqual(rc, 0)
        self.assertEqual(self.saved()["monitors"], {})
        self.assertNotIn("1.25", (self.state / "hypr-monitors.lua").read_text())
        self.assertEqual(len(self.evals()), 2)
        self.assertFalse(json.loads(self.run_cli("status")[1])["pending"])

    def test_revert_without_pending_errors(self):
        rc, _, err = self.run_cli("revert")
        self.assertEqual(rc, 1)
        self.assertIn("nothing to revert", err)

    def test_second_change_while_pending_keeps_original_prev(self):
        self.run_cli("set-scale", "eDP-1", "1.25")
        self.run_cli("set-scale", "eDP-1", "1.2")
        self.run_cli("revert")
        self.assertEqual(self.saved()["monitors"], {})

    def test_apply_unchanged_makes_no_eval(self):
        self.assertEqual(self.run_cli("apply")[0], 0)
        self.assertEqual(len(self.evals()), 1)
        self.log.unlink()
        self.assertEqual(self.run_cli("apply")[0], 0)
        self.assertEqual(self.evals(), [])
        self.assertFalse(json.loads(self.run_cli("status")[1])["pending"])

    def test_set_mode_clamps_saved_scale(self):
        self.run_cli("set-scale", "eDP-1", "1.5")
        rc, _, _ = self.run_cli("set-mode", "eDP-1", "1280x800@60")
        self.assertEqual(rc, 0)
        e = self.saved()["monitors"]["Samsung 0x4187"]
        self.assertEqual(e["mode"], "1280x800@60")
        self.assertIn(e["scale"], D.scale_options(1280, 800))

    def test_set_mode_rejects_unlisted_mode(self):
        rc, _, err = self.run_cli("set-mode", "eDP-1", "3840x2160@60")
        self.assertEqual(rc, 1)
        self.assertFalse(self.displays.exists())

    def test_layout_refused_with_single_monitor(self):
        rc, _, err = self.run_cli("layout", "only")
        self.assertEqual(rc, 1)
        self.assertIn("two monitors", err)

    def test_layout_mirror_two_monitors(self):
        self.two()
        rc, _, _ = self.run_cli("layout", "mirror", "--primary", "eDP-1")
        self.assertEqual(rc, 0)
        self.assertIn('mirror = "eDP-1"', (self.state / "hypr-monitors.lua").read_text())
        self.assertEqual(list(self.saved()["layouts"].values())[0]["mode"], "mirror")

    def test_brightness_internal_reads_the_curve_percent(self):
        rc, out, _ = self.run_cli("brightness", "eDP-1")                    # raw 16 of 400
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"name": "eDP-1", "kind": "backlight", "percent": 25})
        self.assertEqual(self.tool_calls("brightnessctl"), ["brightnessctl\t-m"])

    def test_brightness_internal_percent_scale_runs_from_1_at_the_floor_to_100(self):
        for raw, percent in ((2, 1), (3, 5), (4, 8), (100, 60), (400, 100)):
            line = f"fake_backlight,backlight,{raw},0%,400"
            self.assertEqual(json.loads(self.run_cli("brightness", "eDP-1", FAKE_BRIGHTNESS_LINE=line)[1])["percent"],
                             percent)

    def test_brightness_internal_set(self):
        rc, out, _ = self.run_cli("brightness", "eDP-1", "60")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"name": "eDP-1", "kind": "backlight", "percent": 60})
        self.assertIn("brightnessctl\tset\t98", self.tool_calls("brightnessctl"))      # 60 % = raw 98 of 400

    def test_brightness_internal_set_never_goes_below_the_floor(self):
        self.run_cli("brightness", "eDP-1", "1")
        self.run_cli("brightness", "eDP-1", "0")
        self.assertEqual([c for c in self.tool_calls("brightnessctl") if "\tset\t" in c],
                         ["brightnessctl\tset\t2", "brightnessctl\tset\t2"])

    def test_brightness_external_get_uses_its_own_i2c_bus(self):
        self.two()
        self.add_drm()
        rc, out, _ = self.run_cli("brightness", "DP-1", FAKE_DDC_CUR="30")
        self.assertEqual((rc, json.loads(out)), (0, {"name": "DP-1", "kind": "ddc", "percent": 30}))
        self.assertEqual(self.tool_calls("ddcutil"), ["ddcutil\t--bus\t3\tgetvcp\t10\t--brief"])
        self.assertEqual(self.tool_calls("brightnessctl"), [])        # never touches the laptop backlight

    def test_brightness_external_set_scales_to_the_monitors_maximum(self):
        self.two()
        self.add_drm()
        rc, out, _ = self.run_cli("brightness", "DP-1", "50", FAKE_DDC_MAX="255")
        self.assertEqual((rc, json.loads(out)), (0, {"name": "DP-1", "kind": "ddc", "percent": 50}))
        self.assertIn("ddcutil\t--bus\t3\tsetvcp\t10\t128\t--noverify", self.tool_calls("ddcutil"))
        self.assertEqual(self.tool_calls("brightnessctl"), [])

    def test_brightness_external_set_reuses_the_known_maximum(self):
        """A set after a read skips the DDC read (about 90 ms on the G25F2): the maximum is remembered per bus and EDID."""
        self.two()
        self.add_drm()
        self.run_cli("brightness", "DP-1", FAKE_DDC_MAX="255")
        self.log.unlink()
        rc, out, _ = self.run_cli("brightness", "DP-1", "50", FAKE_DDC_MAX="255")
        self.assertEqual((rc, json.loads(out)), (0, {"name": "DP-1", "kind": "ddc", "percent": 50}))
        self.assertEqual(self.tool_calls("ddcutil"), ["ddcutil\t--bus\t3\tsetvcp\t10\t128\t--noverify"])

    def test_brightness_another_monitor_on_the_same_bus_is_read_again(self):
        self.two()
        self.add_drm()
        self.run_cli("brightness", "DP-1", FAKE_DDC_MAX="255")
        self.add_drm(edid=b"monitor-b")                    # a different monitor plugged into the same port
        self.log.unlink()
        self.run_cli("brightness", "DP-1", "50", FAKE_DDC_MAX="100")
        self.assertEqual(self.tool_calls("ddcutil"), ["ddcutil\t--bus\t3\tgetvcp\t10\t--brief",
                                                      "ddcutil\t--bus\t3\tsetvcp\t10\t50\t--noverify"])

    def test_brightness_external_without_ddc_bus_errors(self):
        self.two()
        rc, _, err = self.run_cli("brightness", "DP-1")
        self.assertEqual(rc, 1)
        self.assertIn("no DDC bus", err)

    def test_brightness_external_without_ddcutil_says_so(self):
        self.two()
        self.add_drm()
        bin_dir = self.base / "nobin"
        bin_dir.mkdir()
        for tool in ("hyprctl", "cat"):
            (bin_dir / tool).symlink_to(FIX / "fake-bin" / tool if tool == "hyprctl" else Path("/usr/bin/cat"))
        rc, _, err = self.run_cli("brightness", "DP-1", PATH=str(bin_dir))
        self.assertEqual(rc, 1)
        self.assertIn("ddcutil is not installed", err)

    def test_brightness_ddcutil_failure_reports_its_first_line(self):
        self.two()
        self.add_drm()
        rc, _, err = self.run_cli("brightness", "DP-1", FAKE_DDC_FAIL="Permission denied")
        self.assertEqual(rc, 1)
        self.assertIn("Permission denied", err)

    def side_by_side(self):
        """eDP-1 (1920x1200 @1.5 = 1280x800 logical) at 0,0 and DP-1 (2560x1440 @1 = 2560x1440) to its right."""
        a = hypr_mon(A, MODES_A)
        b = hypr_mon(dict(B, x=1280, y=0), MODES_B)
        a["focused"], b["focused"] = True, False
        self.set_monitors([a, b])

    def test_step_internal_moves_on_the_curve(self):
        rc, out, _ = self.run_cli("brightness", "eDP-1", "--step", "5")      # 25 % (raw 16) + 5 = 30 % = raw 21
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), {"name": "eDP-1", "kind": "backlight", "percent": 30})
        self.assertEqual(self.tool_calls("brightnessctl")[-1], "brightnessctl\tset\t21")
        self.run_cli("brightness", "eDP-1", "--step", "-5")                  # 20 % = raw 11
        self.assertEqual(self.tool_calls("brightnessctl")[-1], "brightnessctl\tset\t11")

    def test_step_internal_always_moves_a_raw_step_at_the_dark_end(self):
        at = lambda raw: f"fake_backlight,backlight,{raw},0%,400"
        out = json.loads(self.run_cli("brightness", "eDP-1", "--step", "1", FAKE_BRIGHTNESS_LINE=at(2))[1])
        self.assertEqual(self.tool_calls("brightnessctl")[-1], "brightnessctl\tset\t3")   # +1 % alone would stay on raw 2
        self.assertEqual(out["percent"], 5)
        self.run_cli("brightness", "eDP-1", "--step", "-1", FAKE_BRIGHTNESS_LINE=at(3))
        self.assertEqual(self.tool_calls("brightnessctl")[-1], "brightnessctl\tset\t2")
        out = json.loads(self.run_cli("brightness", "eDP-1", "--step", "-5", FAKE_BRIGHTNESS_LINE=at(2))[1])
        self.assertEqual((self.tool_calls("brightnessctl")[-1], out["percent"]), ("brightnessctl\tset\t2", 1))

    def test_key_steps_one_percent_at_the_dark_end_and_five_above(self):
        at = lambda raw: f"fake_backlight,backlight,{raw},0%,400"
        for raw, key, want in ((2, "up", "set\t3"), (3, "down", "set\t2"), (3, "up", "set\t5"),   # 5 % up = 10 % = raw 5
                               (16, "up", "set\t21"), (16, "down", "set\t11")):
            self.run_cli("brightness", "eDP-1", "--key", key, FAKE_BRIGHTNESS_LINE=at(raw))
            self.assertTrue(self.tool_calls("brightnessctl")[-1].endswith(want), (raw, key, want))

    def test_key_needs_up_or_down(self):
        self.assertEqual(self.run_cli("brightness", "eDP-1", "--key", "sideways")[0], 2)

    def test_key_delta_rule(self):
        from bbkos_theme import brightness as B
        self.assertEqual([B.key_delta(p, "up") for p in (1, 4, 5, 6, 50)], [1, 1, 5, 5, 5])
        self.assertEqual([B.key_delta(p, "down") for p in (1, 5, 6, 50)], [-1, -1, -5, -5])

    def test_step_external_changes_only_that_monitor(self):
        self.two()
        self.add_drm()
        rc, out, _ = self.run_cli("brightness", "DP-1", "--step", "5", FAKE_DDC_CUR="30")
        self.assertEqual((rc, json.loads(out)), (0, {"name": "DP-1", "kind": "ddc", "percent": 35}))
        self.assertIn("ddcutil\t--bus\t3\tsetvcp\t10\t35\t--noverify", self.tool_calls("ddcutil"))
        self.assertEqual(self.tool_calls("brightnessctl"), [])

    def test_step_external_scales_to_the_monitors_maximum(self):
        self.two()
        self.add_drm()
        rc, out, _ = self.run_cli("brightness", "DP-1", "--step", "5", FAKE_DDC_CUR="100", FAKE_DDC_MAX="255")
        self.assertIn("setvcp\t10\t113", self.tool_calls("ddcutil")[-1])
        self.assertEqual(json.loads(out)["percent"], 44)

    def test_step_external_clamps_at_both_ends(self):
        self.two()
        self.add_drm()
        self.assertEqual(json.loads(self.run_cli("brightness", "DP-1", "--step", "5", FAKE_DDC_CUR="98")[1])["percent"], 100)
        self.assertEqual(json.loads(self.run_cli("brightness", "DP-1", "--step", "-5", FAKE_DDC_CUR="3")[1])["percent"], 0)

    def test_at_cursor_picks_the_monitor_under_the_pointer(self):
        self.side_by_side()
        self.add_drm()
        rc, out, _ = self.run_cli("brightness", "@cursor", "--step", "5", FAKE_HYPRCTL_CURSORPOS="1500, 100", FAKE_DDC_CUR="30")
        self.assertEqual(json.loads(out)["name"], "DP-1")
        self.assertEqual(self.tool_calls("brightnessctl"), [])
        self.log.unlink()
        rc, out, _ = self.run_cli("brightness", "@cursor", "--step", "5", FAKE_HYPRCTL_CURSORPOS="100, 100")
        self.assertEqual(json.loads(out)["name"], "eDP-1")
        self.assertEqual(self.tool_calls("ddcutil"), [])

    def test_at_cursor_uses_logical_not_pixel_size(self):
        # x=1300 is inside eDP-1's 1920 pixels but outside its 1280 logical width: it is on DP-1
        self.side_by_side()
        self.add_drm()
        out = self.run_cli("brightness", "@cursor", FAKE_HYPRCTL_CURSORPOS="1300, 10")[1]
        self.assertEqual(json.loads(out)["name"], "DP-1")

    def test_at_cursor_outside_every_monitor_falls_back_to_the_focused_one(self):
        self.side_by_side()
        out = self.run_cli("brightness", "@cursor", FAKE_HYPRCTL_CURSORPOS="9000, 9000")[1]
        self.assertEqual(json.loads(out)["name"], "eDP-1")

    def test_at_cursor_unreadable_position_falls_back_to_the_focused_one(self):
        self.side_by_side()
        out = self.run_cli("brightness", "@cursor", FAKE_HYPRCTL_CURSORPOS="nonsense")[1]
        self.assertEqual(json.loads(out)["name"], "eDP-1")

    def test_step_and_percent_together_is_a_usage_error(self):
        self.assertEqual(self.run_cli("brightness", "eDP-1", "50", "--step", "5")[0], 2)
        self.assertEqual(self.run_cli("brightness", "eDP-1", "--step", "x")[0], 2)
        self.assertEqual(self.run_cli("brightness", "eDP-1", "--step", "0")[0], 2)

    def test_brightness_bad_percent_is_a_usage_error(self):
        self.assertEqual(self.run_cli("brightness", "eDP-1", "101")[0], 2)
        self.assertEqual(self.run_cli("brightness", "eDP-1", "-1")[0], 2)
        self.assertEqual(self.run_cli("brightness", "eDP-1", "abc")[0], 2)

    def test_brightness_unknown_monitor_errors(self):
        rc, _, err = self.run_cli("brightness", "DP-9")
        self.assertEqual(rc, 1)
        self.assertIn("unknown monitor", err)

    def test_status_reports_brightness_support_per_monitor(self):
        self.two()
        self.add_backlight()
        self.add_drm()
        mons = {m["name"]: m["brightness"] for m in json.loads(self.run_cli("status")[1])["monitors"]}
        self.assertEqual(mons, {"eDP-1": "backlight", "DP-1": "ddc"})

    def test_status_external_without_a_bus_has_no_brightness(self):
        self.two()
        self.add_backlight()
        mons = {m["name"]: m["brightness"] for m in json.loads(self.run_cli("status")[1])["monitors"]}
        self.assertEqual(mons, {"eDP-1": "backlight", "DP-1": None})

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.run_cli()[0], 2)
        self.assertEqual(self.run_cli("set-scale", "eDP-1", "abc")[0], 2)
        self.assertEqual(self.run_cli("layout", "sideways")[0], 2)


if __name__ == "__main__":
    unittest.main()
