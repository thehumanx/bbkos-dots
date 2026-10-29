"""WCAG floors of the generated theme (a11y.py): every text, control and focus colour clears its floor on every surface it is
drawn on, whatever the wallpaper, mode or tint. The palettes are synthetic (no matugen needed): fixed seeds, many hues,
dark and light, and deliberately hostile inputs such as text colours equal to the background."""
import copy
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dotfiles/bin/.local/lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbkos_theme import a11y, contrast, render, settings  # noqa: E402
from test_render import make_palette  # noqa: E402


def rand_hex(rng, lo=0.0, hi=1.0):
    return contrast.from_oklch(rng.uniform(lo, hi), rng.uniform(0.0, 0.25), rng.uniform(0, 360))


def synthetic_palette(rng, mode):
    """A palette of the shape matugen returns, with random colours: dark or light surfaces, any hue, and text roles that
    may start far below their floors (a low-contrast scheme)."""
    p = make_palette(mode)
    dark = mode == "dark"
    surf = rand_hex(rng, 0.10, 0.30) if dark else rand_hex(rng, 0.90, 0.99)
    near = lambda d: contrast.set_oklch_lightness(surf, min(0.99, max(0.02, contrast.to_oklch(surf)[0] + (d if dark else -d))))
    p.update(surface=surf, surface_container=near(0.04), surface_high=near(0.08),
             on_surface=near(0.20 * rng.random()) if rng.random() < 0.3 else rand_hex(rng, 0.75, 0.95) if dark else rand_hex(rng, 0.10, 0.30),
             on_surface_variant=rand_hex(rng, 0.45, 0.7), outline=rand_hex(rng, 0.40, 0.65), outline_variant=rand_hex(rng, 0.3, 0.5),
             primary=rand_hex(rng), tertiary=rand_hex(rng), error=rand_hex(rng), warn=rand_hex(rng),
             tone_primary=rand_hex(rng, 0.7, 0.85) if dark else rand_hex(rng, 0.35, 0.5),
             soft_primary=rand_hex(rng, 0.25, 0.4) if dark else rand_hex(rng, 0.88, 0.95))
    for role in render.ANSI_ROLES:
        p[role] = rand_hex(rng)
    return p


def settings_for(mode, tint):
    s = copy.deepcopy(settings.DEFAULTS)
    s["colors"]["mode"] = mode
    s["shell"]["tint"] = tint
    return s


class FloorsTest(unittest.TestCase):
    def test_every_pair_clears_its_floor_on_random_palettes(self):
        rng = random.Random(20261021)
        checked = 0
        for mode in ("dark", "light"):
            for n in range(120):
                pal = synthetic_palette(rng, mode)
                for tint in (0.0, 0.5, 1.0):
                    t = render.tokens(pal, settings_for(mode, tint))
                    bad = a11y.failures(t, tint)
                    checked += len(a11y.pairs(t, tint))
                    self.assertEqual(bad, [], f"{mode} palette {n} tint {tint}: {bad[:3]}")
        self.assertGreater(checked, 20000)

    def test_the_fixture_palette_clears_every_floor_in_both_modes(self):
        for mode in ("dark", "light"):
            for tint in (0.0, 0.8, 1.0):
                with self.subTest(mode=mode, tint=tint):
                    t = render.tokens(make_palette(mode), settings_for(mode, tint))
                    self.assertEqual(a11y.failures(t, tint), [])

    def test_text_floors_cover_every_surface(self):
        names = {n for n, _, floor in a11y.pairs(render.tokens(make_palette("dark"), settings_for("dark", 0.8)), 0.8) if floor == 4.5}
        for must in ("text on popup", "text on control", "text on accentSoft", "dim text on inset", "accent text on pill",
                     "warn text on control", "crit text on popup", "text on accent fill", "terminal colour 8"):
            self.assertIn(must, names)

    def test_hostile_inputs_are_lifted(self):
        p = make_palette("dark")
        for role in ("on_surface", "on_surface_variant", "outline", "primary", "tertiary", "error", "warn", "tone_primary"):
            p[role] = p["surface"]
        t = render.tokens(p, settings_for("dark", 1.0))
        self.assertEqual(a11y.failures(t, 1.0), [])

    def test_a_colour_that_already_passes_is_not_touched(self):
        p = make_palette("dark")
        p.update(on_surface="#ffffff", primary="#ffffff")
        t = render.tokens(p, settings_for("dark", 0.8))
        self.assertEqual(t["fg"], "#ffffff")
        self.assertEqual(t["accent"], "#ffffff")

    def test_lifting_keeps_the_wallpaper_hue(self):
        rng = random.Random(7)
        for _ in range(60):
            pal = synthetic_palette(rng, "dark")
            pal["primary"] = contrast.from_oklch(0.30, 0.15, rng.uniform(0, 360))      # too dark to read: must be lifted
            t = render.tokens(pal, settings_for("dark", 0.8))
            src, out = contrast.to_oklch(pal["primary"]), contrast.to_oklch(t["accent"])
            if out[1] > 0.04:                                                           # a grey has no hue to keep
                d = abs(src[2] - out[2])
                self.assertLessEqual(min(d, 360 - d), 12, (pal["primary"], t["accent"]))


class BuiltInLookTest(unittest.TestCase):
    def test_the_fallback_colours_in_themestore_clear_every_floor(self):
        """ThemeStore.qml carries a hand-set palette for when no theme file exists (and Theme.qml's tint 0.8). It is not
        generated, so nothing but this test keeps it accessible."""
        import re
        text = (ROOT / "dotfiles/quickshell/.config/quickshell/services/ThemeStore.qml").read_text()
        block = text[text.index("defaultColors"):text.index("// [default, min, max]")]
        t = dict(re.findall(r'(\w+): "(#[0-9a-f]{6})"', block))
        self.assertGreaterEqual(len(t), 17)
        t["ansi"] = [t["fg"]] * 16                  # the terminal colours are generated, not part of this palette
        bad = [f for f in a11y.failures(t, 0.8) if not f[0].startswith("terminal")]
        self.assertEqual(bad, [])


class HelpersTest(unittest.TestCase):
    def test_blend_matches_qt_tint(self):
        self.assertEqual(contrast.blend("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(contrast.blend("#102030", "#ffffff", 0.0), "#102030")
        self.assertEqual(contrast.blend("#102030", "#ffffff", 1.0), "#ffffff")

    def test_ensure_all_clears_every_check_and_moves_only_as_far_as_needed(self):
        checks = [("#101010", 4.5), ("#303030", 4.5)]
        c = contrast.ensure_all("#404040", checks)
        for bg, floor in checks:
            self.assertGreaterEqual(contrast.ratio(c, bg), floor)
        self.assertEqual(contrast.ensure_all("#ffffff", checks), "#ffffff")
        # not lifted further than the harder background needs
        self.assertLess(contrast.ratio(c, "#303030"), 4.6)

    def test_ensure_all_handles_an_alpha_check(self):
        c = contrast.ensure_all("#606060", [("#202020", 3.0, 0.55)])
        self.assertGreaterEqual(contrast.ratio(contrast.blend("#202020", c, 0.55), "#202020"), 3.0)

    def test_ensure_all_returns_the_far_end_when_nothing_passes(self):
        self.assertEqual(contrast.ensure_all("#808080", [("#808080", 21.0)]), "#000000")


class LockTest(unittest.TestCase):
    TEXT = "#f0f0f0"

    def test_a_dark_wallpaper_keeps_the_setting(self):
        self.assertEqual(a11y.lock_brightness(0.75, (0, 0, 0), self.TEXT), 0.75)
        self.assertEqual(a11y.lock_brightness(1.0, (20, 30, 40), self.TEXT), 1.0)

    def test_a_bright_wallpaper_is_dimmed_until_the_text_reads(self):
        for cell in ((255, 255, 255), (200, 200, 200), (129, 181, 183), (120, 120, 120)):
            b = a11y.lock_brightness(0.75, cell, self.TEXT)
            self.assertLess(b, 0.75, cell)
            self.assertGreaterEqual(b, a11y.LOCK_MIN_BRIGHTNESS)
            backdrop = contrast.blend("#%02x%02x%02x" % tuple(round(c * b) for c in cell), "#ffffff", a11y.LOCK_FIELD_ALPHA)
            shown = contrast.blend(backdrop, self.TEXT, a11y.LOCK_TEXT_ALPHA)
            if b > a11y.LOCK_MIN_BRIGHTNESS:
                self.assertGreaterEqual(contrast.ratio(shown, backdrop), 4.5, cell)

    def test_it_never_goes_below_the_lowest_setting_or_above_the_setting(self):
        self.assertGreaterEqual(a11y.lock_brightness(0.75, (255, 255, 255), self.TEXT), a11y.LOCK_MIN_BRIGHTNESS)
        self.assertLessEqual(a11y.lock_brightness(0.4, (150, 150, 150), self.TEXT), 0.4)

    def test_dark_text_and_unmeasured_wallpapers_are_left_alone(self):
        self.assertEqual(a11y.lock_brightness(0.75, (255, 255, 255), "#101010"), 0.75)
        self.assertEqual(a11y.lock_brightness(0.75, None, self.TEXT), 0.75)

    def sample(self, colour, returncode=0, size=None):
        from types import SimpleNamespace
        w, h = a11y.LOCK_GRID
        data = bytes(colour) * (w * h) if size is None else b"\x00" * size
        return lambda argv, **kw: SimpleNamespace(returncode=returncode, stdout=data, stderr=b"")

    def test_measure_reads_the_centre_of_the_image(self):
        self.assertEqual(a11y.measure_wallpaper("x.png", run=self.sample((10, 200, 30))), (10, 200, 30))

    def test_measure_gives_up_quietly(self):
        self.assertIsNone(a11y.measure_wallpaper("x.png", run=self.sample((1, 1, 1), returncode=1)))
        self.assertIsNone(a11y.measure_wallpaper("x.png", run=self.sample((1, 1, 1), size=10)))

        def missing(argv, **kw):
            raise FileNotFoundError("ffmpeg")
        self.assertIsNone(a11y.measure_wallpaper("x.png", run=missing))

    def test_apply_measures_only_when_auto_dim_is_on(self):
        import tempfile
        from unittest import mock
        from bbkos_theme import apply as A
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            s = settings_for("dark", 0.8)
            s["wallpaper"]["path"] = f.name
            with mock.patch.object(A.a11y, "measure_wallpaper", return_value=(255, 255, 255)) as m:
                self.assertLess(A._lock_brightness(s, None)[0], 0.75)
                self.assertEqual(m.call_count, 1)
                s["lock"]["autoDim"] = False
                self.assertEqual(A._lock_brightness(s, None), (None, None))
                self.assertEqual(m.call_count, 1)                       # not even measured
            s["lock"]["autoDim"] = True
            s["wallpaper"]["path"] = ""
            self.assertEqual(A._lock_brightness(s, None), (None, None))  # no wallpaper: nothing to measure

    def test_hyprlock_gets_the_capped_brightness_and_says_why(self):
        s = settings_for("dark", 0.8)
        plain = render.render_hyprlock(s)
        self.assertIn("brightness = 0.75", plain)
        self.assertNotIn("capped", plain)
        capped = render.render_hyprlock(s, 0.4)
        self.assertIn("brightness = 0.4", capped)
        self.assertIn("# brightness capped to 0.4 (setting 0.75)", capped)
        self.assertIn("brightness = 0.75", render.render_hyprlock(s, 0.9))      # a cap above the setting does nothing


if __name__ == "__main__":
    unittest.main()
