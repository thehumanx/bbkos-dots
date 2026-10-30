import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dotfiles/bin/.local/lib"))

from bbkos_theme import settings as S  # noqa: E402


class SettingsTest(unittest.TestCase):
    def test_defaults_match_today(self):
        d = S.DEFAULTS
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["wallpaper"], {"path": "", "fit": "cover"})
        self.assertEqual(d["colors"], {"mode": "dark", "scheme": "tonal-spot",
                                       "sourceIndex": 0, "contrast": 0.0, "accentStrength": 1.0, "folderIcons": True, "auto": False, "lightFrom": "07:00",
                                       "darkFrom": "19:00"})
        sh = d["shell"]
        self.assertEqual((sh["barHeight"], sh["gap"], sh["radius"], sh["controlRadius"],
                          sh["fontSize"], sh["font"]),
                         (30, 12, 12, 6, 13, "JetBrainsMono Nerd Font"))
        w = d["windows"]
        self.assertEqual((w["gapsIn"], w["gapsOut"], w["borderSize"], w["rounding"],
                          w["activeOpacity"], w["inactiveOpacity"]),
                         (5, 20, 2, 10, 1.0, 1.0))
        self.assertEqual((w["shadowEnabled"], w["shadowRange"], w["blurEnabled"],
                          w["blurSize"], w["blurPasses"], w["animations"]),
                         (True, 4, True, 3, 1, True))
        self.assertEqual(d["terminal"], {"fontSize": 11, "padding": 0, "opacity": 1.0})

    def test_touchpad_defaults_match_hyprland_defaults(self):
        tp = S.DEFAULTS["touchpad"]
        self.assertEqual((tp["naturalScroll"], tp["tapToClick"], tp["tapAndDrag"], tp["disableWhileTyping"]),
                         (False, True, True, True))
        self.assertEqual((tp["swipe3Up"], tp["swipe4Right"]), ("none", "none"))

    def test_tint_and_bar_blur_amount_are_clamped(self):
        s, _ = S.validate({"version": 1, "shell": {"tint": 3, "barBlurAmount": 0}})
        self.assertEqual((s["shell"]["tint"], s["shell"]["barBlurAmount"]), (1.0, 0.05))
        self.assertEqual(S.DEFAULTS["shell"]["tint"], 0.8)
        self.assertEqual(S.DEFAULTS["shell"]["barBlurAmount"], 0.5)

    def test_capture_defaults_and_directory_validation(self):
        c = S.DEFAULTS["capture"]
        self.assertEqual((c["autosave"], c["directory"], c["editorMode"]), (True, "~/Pictures/Screenshots", "overlay"))
        for good in ("~/Pictures/Shots", "/mnt/data/shots"):
            s, w = S.validate({"version": 1, "capture": {"directory": good}})
            self.assertEqual((s["capture"]["directory"], w), (good, []), good)
        for bad in ("", "relative/dir", "~", "/", "~/a\nb", 5):
            s, w = S.validate({"version": 1, "capture": {"directory": bad}})
            self.assertEqual(s["capture"]["directory"], "~/Pictures/Screenshots", repr(bad))
            self.assertTrue(w, repr(bad))

    def test_stage_defaults_are_off_with_a_left_rail(self):
        st = S.DEFAULTS["stage"]
        self.assertEqual((st["enabled"], st["railPosition"], st["railWidth"], st["reserveSpace"]),
                         (False, "left", 150, True))
        self.assertEqual(set(st), {k.split(".")[1] for k in S.RANGES if k.startswith("stage.")})

    def test_stage_values_are_clamped_and_enums_checked(self):
        out, warns = S.validate({"version": 1, "stage": {"railWidth": 9999, "railPosition": "up", "railOpacity": 3}})
        self.assertEqual((out["stage"]["railWidth"], out["stage"]["railPosition"], out["stage"]["railOpacity"]),
                         (320, "left", 1.0))
        self.assertTrue(warns)

    def test_bar_widgets_can_be_hidden(self):
        self.assertEqual(S.DEFAULTS["bar"]["hidden"], [])
        out, warns = S.validate({"version": 1, "bar": {"hidden": ["tray", "nope", "tray", "clock"]}})
        self.assertEqual(out["bar"]["hidden"], ["tray", "clock"])     # unknown and repeated names dropped
        self.assertTrue(warns)
        s = S.set_value(S.DEFAULTS, "bar.hidden", "updates, media")
        self.assertEqual(s["bar"]["hidden"], ["updates", "media"])
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "bar.hidden", "nope")
        self.assertEqual(S.set_value(S.DEFAULTS, "bar.hidden", "")["bar"]["hidden"], [])

    def test_rail_goes_on_any_edge_and_can_hug(self):
        st = S.DEFAULTS["stage"]
        self.assertEqual((st["railHug"], st["railAlign"]), (False, "start"))
        out, _ = S.validate({"version": 1, "stage": {"railPosition": "bottom", "railHug": True, "railAlign": "end"}})
        self.assertEqual((out["stage"]["railPosition"], out["stage"]["railHug"], out["stage"]["railAlign"]), ("bottom", True, "end"))

    def test_rail_align_rejects_unknown_values(self):
        out, warns = S.validate({"version": 1, "stage": {"railAlign": "middle"}})
        self.assertEqual(out["stage"]["railAlign"], "start")
        self.assertTrue(warns)

    def test_dock_is_off_and_empty_by_default_and_grid_mode_switches_it_on(self):
        self.assertEqual((S.DEFAULTS["stage"]["dock"], S.DEFAULTS["stage"]["dockApps"]), (False, []))
        g = S.effective(S.set_value(S.DEFAULTS, "shell.gridMode", "true"))
        self.assertTrue(g["stage"]["dock"])
        self.assertEqual((g["stage"]["railPadding"], g["stage"]["cardGap"]), (20, 20))    # the default margin, 20: the rail follows it
        self.assertEqual(g["stage"]["dockApps"], [])           # grid mode never touches the pins

    def test_the_rail_spacing_follows_the_window_margin_in_grid_mode(self):
        self.assertEqual((S.grid_rail_gap(8), S.grid_rail_gap(0), S.grid_rail_gap(40)), (8, 0, 32))      # capped at the rail's own maximum
        s = S.set_value(S.set_value(S.DEFAULTS, "shell.gridMode", "true"), "windows.gapsOut", "8")
        g = S.effective(s)
        self.assertEqual((g["stage"]["railPadding"], g["stage"]["cardGap"]), (8, 8))
        self.assertEqual((s["stage"]["railPadding"], s["stage"]["cardGap"]), (12, 12))                  # the saved values stay

    def test_dock_apps_are_a_cleaned_list_of_names(self):
        s = S.set_value(S.DEFAULTS, "stage.dockApps", "kitty,org.xfce.Thunar")
        self.assertEqual(s["stage"]["dockApps"], ["kitty", "org.xfce.Thunar"])
        self.assertEqual(S.validate({"version": 1, "stage": {"dockApps": ["kitty", "a,b", "", "kitty", "zen"]}})[0]["stage"]["dockApps"], ["kitty", "zen"])
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "stage.dockApps", "kitty,kitty")

    def test_the_window_title_widget_sits_after_the_workspaces_by_default(self):
        lay = S.DEFAULTS["bar"]["layout"]
        self.assertEqual(lay[lay.index("start:workspaces") + 1], "start:title")
        out, _ = S.validate({"version": 1, "bar": {"layout": ["start:overview", "start:workspaces"]}})
        self.assertIn("start:title", out["bar"]["layout"])     # an older saved layout gains it

    def test_stage_set_value_toggles_the_mode(self):
        out = S.set_value(S.DEFAULTS, "stage.enabled", "on")
        self.assertTrue(out["stage"]["enabled"])

    def test_touchpad_has_no_three_finger_left_right(self):
        self.assertNotIn("touchpad.swipe3Left", S.RANGES)
        self.assertNotIn("touchpad.swipe3Right", S.RANGES)

    def test_touchpad_swipe_action_must_be_known(self):
        out, warns = S.validate({"version": 1, "touchpad": {"swipe4Up": "launch-missiles"}})
        self.assertEqual(out["touchpad"]["swipe4Up"], "none")
        self.assertTrue(warns)

    def test_bar_layout_default_has_every_widget_once(self):
        layout = S.DEFAULTS["bar"]["layout"]
        self.assertEqual(sorted(e.split(":")[1] for e in layout), sorted(S.BAR_WIDGETS))
        self.assertIn("start:workspaces", layout)
        self.assertIn("center:clock", layout)
        self.assertLess(layout.index("center:clock"), layout.index("center:updates"))

    def test_bar_layout_keeps_order_and_sections(self):
        out, warns = S.validate({"version": 1, "bar": {"layout": ["end:clock", "start:tray"]}})
        self.assertEqual(out["bar"]["layout"][:2], ["end:clock", "start:tray"])
        self.assertEqual(warns, [])

    def test_bar_layout_drops_unknown_and_repeated_entries(self):
        out, warns = S.validate({"version": 1, "bar": {"layout": ["end:clock", "end:clock", "bogus:tray", "start:nope"]}})
        self.assertEqual(out["bar"]["layout"][0], "end:clock")
        self.assertEqual(out["bar"]["layout"].count("end:clock"), 1)
        self.assertNotIn("bogus:tray", out["bar"]["layout"])
        self.assertTrue(warns)

    def test_bar_layout_appends_missing_widgets_at_default_section(self):
        out, _ = S.validate({"version": 1, "bar": {"layout": ["end:tray"]}})
        self.assertEqual(sorted(e.split(":")[1] for e in out["bar"]["layout"]), sorted(S.BAR_WIDGETS))
        self.assertIn("center:clock", out["bar"]["layout"])

    def test_bar_layout_rejects_non_list(self):
        out, warns = S.validate({"version": 1, "bar": {"layout": "clock"}})
        self.assertEqual(out["bar"]["layout"], S.BAR_LAYOUT_DEFAULT)
        self.assertTrue(warns)

    def test_bar_icon_defaults_and_styles(self):
        self.assertEqual(S.DEFAULTS["bar"]["iconWifi"], "bars")
        self.assertEqual(S.DEFAULTS["bar"]["iconBluetooth"], "material")
        self.assertEqual(S.DEFAULTS["bar"]["iconAudio"], "fa")
        self.assertEqual(S.DEFAULTS["bar"]["iconDisplay"], "monitor")
        self.assertNotIn("none", S.RANGES["bar.iconSettings"][1])   # the gear must stay clickable

    def test_bar_icons_only_defaults_off_and_is_a_bool(self):
        self.assertIs(S.DEFAULTS["bar"]["iconsOnly"], False)
        self.assertIs(S.set_value(S.DEFAULTS, "bar.iconsOnly", "true")["bar"]["iconsOnly"], True)
        out, warns = S.validate({"version": 1, "bar": {"iconsOnly": "yes"}})
        self.assertIs(out["bar"]["iconsOnly"], False)
        self.assertTrue(any("bar.iconsOnly" in w for w in warns))

    def test_bar_icon_gap_default_and_range(self):
        self.assertEqual(S.DEFAULTS["bar"]["iconGap"], 2)
        self.assertEqual(S.set_value(S.DEFAULTS, "bar.iconGap", "4")["bar"]["iconGap"], 4)
        self.assertEqual(S.set_value(S.DEFAULTS, "bar.iconGap", "9")["bar"]["iconGap"], 6)     # clamped, as every int

    def test_accent_strength_default_and_range(self):
        self.assertEqual(S.DEFAULTS["colors"]["accentStrength"], 1.0)
        self.assertEqual(S.set_value(S.DEFAULTS, "colors.accentStrength", "0.5")["colors"]["accentStrength"], 0.5)
        self.assertEqual(S.set_value(S.DEFAULTS, "colors.accentStrength", "1.5")["colors"]["accentStrength"], 1.0)    # clamped
        self.assertEqual(S.set_value(S.DEFAULTS, "colors.accentStrength", "-0.2")["colors"]["accentStrength"], 0.0)

    def test_grid_mode_off_by_default_and_effective_is_identity(self):
        self.assertIs(S.DEFAULTS["shell"]["gridMode"], False)
        self.assertIs(S.effective(S.DEFAULTS), S.DEFAULTS)

    def test_grid_mode_overrides_a_copy_and_keeps_the_saved_values(self):
        s = S.set_value(S.DEFAULTS, "shell.gridMode", "true")
        s = S.set_value(s, "shell.radius", "20")
        g = S.effective(s)
        self.assertEqual((g["shell"]["radius"], g["shell"]["gap"], g["shell"]["barItemGap"], g["shell"]["barFloat"]), (0, 0, 0, 0))
        self.assertEqual((g["stage"]["cardGap"], g["stage"]["cardRadius"]), (20, 10))    # the margin and the window rounding (defaults)
        self.assertEqual(g["shell"]["barPills"], "individual")
        self.assertEqual(g["windows"]["borderSize"], 1)
        # The margin around the windows and their corner radius are the owner's own, in grid mode too (2026-10-30); the gap
        # between tiled windows follows the margin (Hyprland doubles gaps_in between two windows, so it is half of it).
        self.assertEqual((g["windows"]["gapsOut"], g["windows"]["rounding"], g["windows"]["gapsIn"]), (20, 10, 10))
        self.assertEqual(S.grid_gaps_in(8), 4)
        self.assertEqual(S.grid_gaps_in(7), 4)            # odd margins round up
        self.assertEqual(S.grid_gaps_in(0), 0)
        s8 = S.set_value(S.set_value(s, "windows.gapsOut", "8"), "windows.rounding", "6")
        self.assertEqual((S.effective(s8)["windows"]["gapsOut"], S.effective(s8)["windows"]["rounding"], S.effective(s8)["windows"]["gapsIn"]), (8, 6, 4))
        self.assertEqual(s8["windows"]["gapsIn"], 5)       # the saved inner gap is untouched
        self.assertFalse(g["windows"]["shadowEnabled"])
        self.assertEqual(g["lock"]["fieldRadius"], 0)
        self.assertEqual(s["shell"]["radius"], 20)                  # the owner's value is untouched
        self.assertEqual(s["windows"]["gapsOut"], 20)

    def test_grid_round_controls_keeps_the_popup_and_control_radii(self):
        self.assertIs(S.DEFAULTS["shell"]["gridRoundControls"], False)
        s = S.set_value(S.DEFAULTS, "shell.gridMode", "true")
        s = S.set_value(s, "shell.gridRoundControls", "true")
        s = S.set_value(s, "shell.radius", "20")
        g = S.effective(s)
        self.assertEqual((g["shell"]["radius"], g["shell"]["controlRadius"], g["shell"]["pillRadius"]), (20, 6, 8))
        self.assertEqual((g["shell"]["barRadius"], g["stage"]["cardRadius"]), (0, 10))
        self.assertEqual(g["shell"]["gap"], 0)
        off = S.effective(S.set_value(s, "shell.gridRoundControls", "false"))
        self.assertEqual((off["shell"]["radius"], off["shell"]["controlRadius"], off["shell"]["pillRadius"]), (0, 0, 0))

    def test_grid_overrides_name_real_keys_with_valid_values(self):
        for section, values in {**S.GRID_OVERRIDES, "shell": {**S.GRID_OVERRIDES["shell"], **S.GRID_ROUND_OFF["shell"]}}.items():
            for key, value in values.items():
                self.assertEqual(S.validate({"version": 1, section: {key: value}})[0][section][key], value, f"{section}.{key}")

    def test_bar_item_pad_default_range_and_grid_keeps_it(self):
        self.assertEqual(S.DEFAULTS["shell"]["barItemPad"], 0)
        s = S.set_value(S.DEFAULTS, "shell.barItemPad", "16")
        self.assertEqual(s["shell"]["barItemPad"], 16)
        self.assertEqual(S.set_value(S.DEFAULTS, "shell.barItemPad", "40")["shell"]["barItemPad"], 24)     # clamped
        s = S.set_value(s, "shell.gridMode", "true")
        self.assertEqual(S.effective(s)["shell"]["barItemPad"], 16)      # grid mode does not override the padding

    def test_bar_icon_rejects_unknown_style(self):
        out, warns = S.validate({"version": 1, "bar": {"iconWifi": "nope"}})
        self.assertEqual(out["bar"]["iconWifi"], "bars")
        self.assertTrue(any("bar.iconWifi" in w for w in warns))

    def test_bar_icon_set_from_text(self):
        out = S.set_value(S.DEFAULTS, "bar.iconBluetooth", "none")
        self.assertEqual(out["bar"]["iconBluetooth"], "none")
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "bar.iconSettings", "none")

    def test_bar_layout_set_from_text(self):
        out = S.set_value(S.DEFAULTS, "bar.layout", "end:clock,start:workspaces")
        self.assertEqual(out["bar"]["layout"][:2], ["end:clock", "start:workspaces"])
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "bar.layout", "end:clock,start:clock")
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "bar.layout", "middle:clock")

    def test_bar_defaults(self):
        sh = S.DEFAULTS["shell"]
        self.assertEqual((sh["barPosition"], sh["barOpacity"], sh["barBlur"], sh["barPills"], sh["pillRadius"]),
                         ("top", 1.0, False, "off", 8))

    def test_bar_keys_validate(self):
        out, warns = S.validate({"version": 1, "shell": {"barPosition": "middle", "barPills": 3, "barOpacity": 0,
                                                         "pillRadius": -4, "barBlur": "yes"}})
        sh = out["shell"]
        self.assertEqual((sh["barPosition"], sh["barPills"], sh["barBlur"]), ("top", "off", False))
        self.assertEqual((sh["barOpacity"], sh["pillRadius"]), (0.2, 0))
        for k in ("barPosition", "barPills", "barOpacity", "pillRadius", "barBlur"):
            self.assertTrue(any(f"shell.{k}" in w for w in warns), k)

    def test_old_file_without_bar_keys_no_warnings(self):
        old = {"version": 1, "shell": {"barHeight": 30, "gap": 12, "radius": 12, "controlRadius": 6,
                                       "fontSize": 13, "font": "JetBrainsMono Nerd Font"}}
        out, warns = S.validate(old)
        self.assertEqual(warns, [])
        self.assertEqual(out["shell"]["barPosition"], "top")

    def test_ranges_cover_every_default(self):
        flat = {f"{s}.{k}" for s, v in S.DEFAULTS.items() if isinstance(v, dict) for k in v}
        self.assertEqual(flat, set(S.RANGES))

    # The tracked settings.json is the owner's live config (Stow link), so it must be schema-valid, not equal to defaults.
    def test_tracked_settings_file_is_schema_valid(self):
        f = Path(__file__).resolve().parents[2] / "defaults/settings.json"
        out, warns = S.validate(json.loads(f.read_text()))
        self.assertEqual(warns, [])
        self.assertEqual(set(out), set(S.DEFAULTS))

    def test_invalid_settings_file_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            bad = copy.deepcopy(S.DEFAULTS)
            bad["shell"]["barHeight"] = 999
            bad["windows"]["rounding"] = "x"
            f = Path(d) / "settings.json"
            f.write_text(json.dumps(bad))
            out, warns = S.validate(json.loads(f.read_text()))
            self.assertTrue(warns)

    def test_dumped_defaults_round_trip_valid(self):
        out, warns = S.validate(json.loads(S.dumps(S.DEFAULTS)))
        self.assertEqual(warns, [])
        self.assertEqual(out, S.DEFAULTS)

    def test_validate_defaults_clean(self):
        out, warns = S.validate(copy.deepcopy(S.DEFAULTS))
        self.assertEqual(out, S.DEFAULTS)
        self.assertEqual(warns, [])

    def test_clamps_out_of_range(self):
        raw = copy.deepcopy(S.DEFAULTS)
        raw["shell"]["barHeight"] = 999
        raw["windows"]["rounding"] = -5
        out, warns = S.validate(raw)
        self.assertEqual(out["shell"]["barHeight"], 48)
        self.assertEqual(out["windows"]["rounding"], 0)
        self.assertTrue(warns)

    def test_even_step(self):
        raw = copy.deepcopy(S.DEFAULTS)
        raw["shell"]["radius"] = 13
        out, _ = S.validate(raw)
        self.assertIn(out["shell"]["radius"], (12, 14))
        self.assertEqual(out["shell"]["radius"] % 2, 0)

    def test_wrong_types_never_raise(self):
        junk = ["x", None, float("nan"), float("inf"), [1], {"a": {"b": 1}}, True, -1e999]
        for j in junk:
            raw = {"version": 1, "mystery": j,
                   **{s: {k: j for k in v} for s, v in S.DEFAULTS.items() if isinstance(v, dict)}}
            out, warns = S.validate(raw)
            self.assertTrue(warns, j)
            self.assertEqual(S.validate(out)[1], [], j)  # result is itself valid
            self.assertEqual(set(out), set(S.DEFAULTS))
        for raw in (None, "str", 5, [], {}, {"shell": "x"}):
            out, _ = S.validate(raw)
            self.assertEqual(out, S.DEFAULTS)

    def test_huge_integers_clamp_never_raise(self):
        for big in (10**400, -10**400):
            raw = {"version": 1, **{s: {k: big for k in v}
                   for s, v in S.DEFAULTS.items() if isinstance(v, dict)}}
            out, warns = S.validate(raw)
            self.assertTrue(warns)
            for dotted, spec in S.RANGES.items():
                sec, k = dotted.split(".")
                if spec[0] in ("int", "float"):
                    self.assertEqual(out[sec][k], spec[1] if big < 0 else spec[2], dotted)
            self.assertEqual(S.validate(out)[1], [])
            with tempfile.TemporaryDirectory() as t:
                p = Path(t) / "settings.json"
                old = sys.get_int_max_str_digits()
                sys.set_int_max_str_digits(0)
                try:
                    p.write_text(json.dumps(raw))
                    out2, _ = S.load(p)
                finally:
                    sys.set_int_max_str_digits(old)
                self.assertEqual(out2, out)

    def test_source_index_range_is_0_to_3(self):
        # matugen 4.2.0 --help says 0-4 but rejects 4 (rc 2, "4 is not in 0..4"): verified 2026-10-18
        self.assertEqual(S.RANGES["colors.sourceIndex"], ("int", 0, 3, 1))
        raw = copy.deepcopy(S.DEFAULTS)
        raw["colors"]["sourceIndex"] = 4
        out, warns = S.validate(raw)
        self.assertEqual(out["colors"]["sourceIndex"], 3)
        self.assertEqual(len(warns), 1)

    def test_enum_and_float_clamp(self):
        raw = copy.deepcopy(S.DEFAULTS)
        raw["colors"]["scheme"] = "nope"
        raw["colors"]["contrast"] = 5
        raw["windows"]["activeOpacity"] = 0.1
        out, warns = S.validate(raw)
        self.assertEqual(out["colors"]["scheme"], "tonal-spot")
        self.assertEqual(out["colors"]["contrast"], 1.0)
        self.assertEqual(out["windows"]["activeOpacity"], 0.6)
        self.assertEqual(len(warns), 3)

    def test_corrupt_json_falls_back_to_bak_then_defaults(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "settings.json"
            bak = Path(t) / "settings.json.bak"
            good = copy.deepcopy(S.DEFAULTS)
            good["shell"]["gap"] = 20
            bak.write_text(json.dumps(good))
            p.write_text("{not json")
            out, warns = S.load(p)
            self.assertEqual(out["shell"]["gap"], 20)
            self.assertTrue(warns)
            bak.write_text("also broken")
            out, warns = S.load(p)
            self.assertEqual(out, S.DEFAULTS)
            self.assertTrue(warns)
            p.unlink()
            bak.unlink()
            out, warns = S.load(p)
            self.assertEqual(out, S.DEFAULTS)

    def test_missing_file_uses_bak_when_present(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "settings.json"
            good = copy.deepcopy(S.DEFAULTS)
            good["shell"]["gap"] = 20
            (Path(t) / "settings.json.bak").write_text(json.dumps(good))
            out, warns = S.load(p)
            self.assertEqual(out["shell"]["gap"], 20)
            self.assertTrue(any("missing" in w and "backup" in w for w in warns), warns)
            # a dangling link counts as missing too
            p.symlink_to(Path(t) / "gone.json")
            out, _ = S.load(p)
            self.assertEqual(out["shell"]["gap"], 20)

    def test_atomic_save_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "settings.json"
            s = copy.deepcopy(S.DEFAULTS)
            s["shell"]["gap"] = 8
            S.save_atomic(p, s)
            S.save_atomic(p, s)
            self.assertEqual(os.listdir(t), ["settings.json"])
            self.assertEqual(json.loads(p.read_text())["shell"]["gap"], 8)
            self.assertTrue(p.read_text().endswith("\n"))
            S.promote_backup(p)
            self.assertEqual(sorted(os.listdir(t)), ["settings.json", "settings.json.bak"])
            self.assertEqual((Path(t) / "settings.json.bak").read_text(), p.read_text())

    def test_save_through_symlink_keeps_link_and_updates_target(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / "repo" / "settings.json"
            real.parent.mkdir()
            S.save_atomic(real, S.DEFAULTS)
            link = Path(d) / "config" / "settings.json"
            link.parent.mkdir()
            link.symlink_to(real)
            S.save_atomic(link, S.set_value(S.DEFAULTS, "shell.gap", "20"))
            self.assertTrue(link.is_symlink())
            self.assertEqual(json.loads(real.read_text())["shell"]["gap"], 20)
            self.assertEqual(os.listdir(real.parent), ["settings.json"])
            S.promote_backup(link)
            self.assertTrue((link.parent / "settings.json.bak").is_file())
            self.assertFalse((link.parent / "settings.json.bak").is_symlink())
            self.assertEqual(os.listdir(real.parent), ["settings.json"])
            self.assertTrue(link.is_symlink())

    def test_relative_wallpaper_path_is_dropped(self):
        raw = copy.deepcopy(S.DEFAULTS)
        raw["wallpaper"]["path"] = "relative.png"
        out, warns = S.validate(raw)
        self.assertEqual(out["wallpaper"]["path"], "")
        self.assertTrue(any("wallpaper.path" in w for w in warns), warns)
        raw["wallpaper"]["path"] = "/abs/current.png"
        out, warns = S.validate(raw)
        self.assertEqual(out["wallpaper"]["path"], "/abs/current.png")
        self.assertEqual(warns, [])
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "wallpaper.path", "rel.png")
        self.assertEqual(S.set_value(S.DEFAULTS, "wallpaper.path", "")["wallpaper"]["path"], "")

    def test_save_rejects_garbage_by_clamping(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "settings.json"
            s = copy.deepcopy(S.DEFAULTS)
            s["shell"]["barHeight"] = 999
            S.save_atomic(p, s)
            self.assertEqual(json.loads(p.read_text())["shell"]["barHeight"], 48)

    def test_set_value_parses_types(self):
        s = S.DEFAULTS
        self.assertIs(S.set_value(s, "windows.blurEnabled", "false")["windows"]["blurEnabled"], False)
        self.assertIs(S.set_value(s, "windows.blurEnabled", "true")["windows"]["blurEnabled"], True)
        self.assertEqual(S.set_value(s, "shell.gap", "16")["shell"]["gap"], 16)
        self.assertEqual(S.set_value(s, "windows.activeOpacity", "0.8")["windows"]["activeOpacity"], 0.8)
        self.assertEqual(S.set_value(s, "colors.mode", "light")["colors"]["mode"], "light")
        self.assertEqual(S.set_value(s, "shell.gap", "999")["shell"]["gap"], 32)
        self.assertEqual(s, S.DEFAULTS)  # input not mutated
        for key, text in (("colors.mode", "purple"), ("shell.gap", "abc"), ("shell.gap", "nan"),
                          ("windows.shadowEnabled", "maybe"), ("nope.key", "1"),
                          ("shell", "1"), ("shell.font", "")):
            with self.assertRaises(ValueError, msg=(key, text)):
                S.set_value(s, key, text)

    def test_power_defaults_override_nothing(self):
        self.assertEqual(S.DEFAULTS["power"], {
            "saverEpp": "default", "balancedEpp": "default", "performanceEpp": "default",
            "saverTurbo": "default", "balancedTurbo": "default", "performanceTurbo": "default",
            "saverCap": 0, "balancedCap": 0, "performanceCap": 0, "chargeMode": "default"})

    def test_power_enums_reject_unknown(self):
        out, warns = S.validate({"version": 1, "power": {"balancedEpp": "turbo-max", "saverTurbo": 1}})
        self.assertEqual(out["power"]["balancedEpp"], "default")
        self.assertEqual(out["power"]["saverTurbo"], "default")
        self.assertEqual(len([w for w in warns if w.startswith("power.")]), 2)

    def test_power_cap_clamps(self):
        for given, want in ((0, 0), (5, 10), (10, 10), (28, 28), (40, 28), (-3, 0), ("x", 0)):
            out, _ = S.validate({"version": 1, "power": {"saverCap": given}})
            self.assertEqual(out["power"]["saverCap"], want, msg=given)
        _, warns = S.validate({"version": 1, "power": {"saverCap": 5}})
        self.assertTrue(any(w.startswith("power.saverCap") for w in warns))

    def test_power_set_value_from_cli_text(self):
        s = copy.deepcopy(S.DEFAULTS)
        self.assertEqual(S.set_value(s, "power.balancedEpp", "balance_power")["power"]["balancedEpp"], "balance_power")
        self.assertEqual(S.set_value(s, "power.performanceCap", "5")["power"]["performanceCap"], 10)
        with self.assertRaises(ValueError):
            S.set_value(s, "power.saverTurbo", "maybe")

    def test_missing_power_section_is_defaults(self):
        out, warns = S.validate({"version": 1})
        self.assertEqual(out["power"], S.DEFAULTS["power"])
        self.assertFalse([w for w in warns if "power" in w])


class LockSettingsTest(unittest.TestCase):
    def _lock(self, **kw):
        out, warns = S.validate({"version": 1, "lock": kw})
        return out["lock"], warns

    def test_lock_defaults_present(self):
        d = S.DEFAULTS["lock"]
        for e, (x, y, size) in {"avatar": (0, 260, 84), "welcome": (0, 190, 18), "date": (0, 125, 14),
                                "time": (0, 50, 96), "battery": (0, -150, 13)}.items():
            self.assertEqual((d[e + "Show"], d[e + "X"], d[e + "Y"], d[e + "Size"]), (True, x, y, size), e)
        self.assertEqual((d["fieldX"], d["fieldY"], d["fieldWidth"], d["fieldHeight"], d["fieldRadius"],
                          d["fieldOpacity"]), (0, -70, 300, 50, -1, 0.14))
        self.assertEqual((d["blurPasses"], d["blurSize"], d["brightness"]), (3, 7, 0.75))
        self.assertEqual((d["font"], d["textColor"], d["welcomeText"], d["timeFormat"], d["dateFormat"]),
                         ("JetBrainsMono Nerd Font", "#f0f0f0", "Welcome $USER", "24h", "weekday-long"))

    def test_lock_out_of_range_clamped(self):
        d, _ = self._lock(avatarX=5000, blurPasses=9, fieldWidth=10, fieldX=-5000)
        self.assertEqual((d["avatarX"], d["blurPasses"], d["fieldWidth"], d["fieldX"]), (1200, 5, 120, -600))
        d, _ = self._lock(fieldY=-900)
        self.assertEqual(d["fieldY"], -500)     # the field stays on a 1000 px high screen

    def test_lock_bad_values_fall_back(self):
        d, warns = self._lock(textColor="red", timeFormat="99h", welcomeText=1, dateFormat="x")
        self.assertEqual((d["textColor"], d["timeFormat"], d["welcomeText"], d["dateFormat"]),
                         ("#f0f0f0", "24h", "Welcome $USER", "weekday-long"))
        self.assertEqual(len(warns), 4)

    def test_lock_colour_is_lowercased(self):
        d, warns = self._lock(textColor="#AABBCC")
        self.assertEqual(d["textColor"], "#aabbcc")
        self.assertEqual(warns, [])

    def test_lock_empty_welcome_text_allowed(self):
        d, warns = self._lock(welcomeText="")
        self.assertEqual((d["welcomeText"], warns), ("", []))

    def test_lock_missing_section_uses_defaults(self):
        out, warns = S.validate({"version": 1})
        self.assertEqual((out["lock"], warns), (S.DEFAULTS["lock"], []))

    def test_lock_align_defaults_and_values(self):
        d = S.DEFAULTS["lock"]
        for e in (*S.LOCK_ELEMENTS, "field"):
            self.assertEqual(d[e + "Align"], "center", e)
        self.assertEqual(d["edgeMargin"], 10)
        out, warns = self._lock(timeAlign="left", fieldAlign="right", avatarAlign="middle", edgeMargin=90)
        self.assertEqual((out["timeAlign"], out["fieldAlign"], out["avatarAlign"], out["edgeMargin"]),
                         ("left", "right", "center", 40))
        self.assertEqual(len(warns), 2)       # the bad enum and the clamped margin

    def test_no_field_show_key(self):
        self.assertNotIn("lock.fieldShow", S.RANGES)
        self.assertNotIn("fieldShow", S.DEFAULTS["lock"])


if __name__ == "__main__":
    unittest.main()


class CalendarSettingsTest(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(S.DEFAULTS["calendar"], {"weekStart": "mon", "weekNumbers": False, "moon": True})

    def test_junk_falls_back_per_key(self):
        out, warns = S.validate({"version": 1, "calendar": {"weekStart": "tue", "weekNumbers": "yes"}})
        self.assertEqual(out["calendar"], {"weekStart": "mon", "weekNumbers": False, "moon": True})
        self.assertEqual(len(warns), 2)

    def test_set_value(self):
        s = S.set_value(S.DEFAULTS, "calendar.weekStart", "sat")
        self.assertEqual(s["calendar"]["weekStart"], "sat")
        with self.assertRaises(ValueError):
            S.set_value(S.DEFAULTS, "calendar.weekStart", "wed")
