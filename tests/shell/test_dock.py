"""Pinned apps (docs/modules/dock.md) in a fresh test shell (layer 2): the dock is on in grid mode, and a pinned app's desktop
entry is found right after the shell starts. Regression: Quickshell loads desktop entries lazily, and a lookup made at start
found nothing for good, so every pinned tile was a "?" after each restart until the shell was restarted again."""
import json
import subprocess
import time
import unittest

from tests.shell.harness import TestShell, skip_unless_session

SETTINGS = {"shell": {"gridMode": True},
            "stage": {"dockApps": ["kitty", "no-such-app-installed"]}}


@skip_unless_session()
class DockTest(unittest.TestCase):
    def test_pins_resolve_after_a_fresh_start(self):
        with TestShell(settings=SETTINGS) as shell:
            deadline = time.time() + 20
            state = {}
            while time.time() < deadline:
                state = json.loads(shell.ipc("stage", "dock"))
                if state.get("resolved"):
                    break
                time.sleep(0.5)
            self.assertTrue(state["on"], "grid mode did not switch the dock on")
            self.assertEqual(state["apps"], ["kitty", "no-such-app-installed"])
            self.assertEqual(state["resolved"], ["kitty"])       # the uninstalled one stays a "?" tile

    @staticmethod
    def _layers(shell):
        """{namespace: (x, y, w, h)} of the bar and the rail in the test shell's compositor."""
        out = subprocess.run(["hyprctl", "layers", "-j"], capture_output=True, text=True, env=shell._env(), timeout=5).stdout
        found = {}
        for mon in json.loads(out).values():
            for level in mon["levels"].values():
                for l in level:
                    if l["namespace"] in ("bbkos-bar", "bbkos-stage"):
                        found[l["namespace"]] = (l["x"], l["y"], l["w"], l["h"])
        return found

    def _screen(self, shell):
        """The nested monitor's logical size (Hyprland reports physical pixels and the scale)."""
        out = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, env=shell._env(), timeout=5).stdout
        m = json.loads(out)[0]
        return round(m["width"] / m["scale"]), round(m["height"] / m["scale"])

    def _wait_layers(self, shell, n=2):
        deadline = time.time() + 20
        while time.time() < deadline and len(self._layers(shell)) < n:
            time.sleep(0.5)
        return self._layers(shell)

    def _body(self, shell):
        return json.loads(shell.ipc("stage", "status"))["screens"][0]["body"]

    def test_rail_edges(self):
        """The rail on each edge at full length, changed live; the bar (at the top here) keeps 0,0."""
        with TestShell(settings=SETTINGS) as shell:
            self._wait_layers(shell)
            shell.set("stage.railPosition", "left")     # the first set applies the nested monitor's scale; start after it
            time.sleep(3)
            for edge in ("right", "bottom", "left", "top", "right"):
                shell.set("stage.railPosition", edge)
                time.sleep(3)
                w, h = self._screen(shell)      # read each time: the nested monitor's scale is applied after the first set
                lay = self._layers(shell)
                bar, rail = lay["bbkos-bar"], lay["bbkos-stage"]
                self.assertEqual(bar[:2], (0, 0), f"{edge}: the bar moved: {lay}")
                if edge == "top":
                    self.assertEqual(rail[1], bar[3], f"top rail is not stacked under the bar: {lay}")
                if edge == "bottom":
                    self.assertEqual(rail[1] + rail[3], h, f"bottom rail is not on the bottom edge: {lay}")
                if edge == "right":
                    self.assertEqual(rail[0] + rail[2], w, f"right rail is not on the right edge: {lay}")
                if edge == "left":
                    self.assertEqual(rail[0], 0, f"left rail is not on the left edge: {lay}")

    def test_hug_keeps_the_reserved_space_and_aligns(self):
        s = {**SETTINGS, "stage": {**SETTINGS["stage"], "railPosition": "bottom", "railHug": True}}
        with TestShell(settings=s) as shell:
            self._wait_layers(shell)
            shell.set("stage.railAlign", "centre")      # the first set applies the nested monitor's scale; measure after it
            time.sleep(3)
            full = self._layers(shell)["bbkos-stage"]
            xs = {}
            for align in ("start", "centre", "end"):
                shell.set("stage.railAlign", align)
                time.sleep(2)
                self.assertEqual(self._layers(shell)["bbkos-stage"], full, "the window changed while hugging")
                xs[align] = self._body(shell)["x"]
            self.assertLess(xs["start"], xs["centre"])
            self.assertLess(xs["centre"], xs["end"])

    def test_hug_on_a_side_rail_is_as_long_as_its_tiles(self):
        """Regression (2026-10-31): the rail's Grid was given 1000 rows and reserved the spacing of each, so a hugging side
        rail was as tall as the screen (and a full-length one scrolled into 8000 px of nothing)."""
        s = {**SETTINGS, "stage": {**SETTINGS["stage"], "railPosition": "left", "railHug": True}}
        with TestShell(settings=s) as shell:
            self._wait_layers(shell)
            time.sleep(2)
            self.assertLess(self._body(shell)["height"], 400)

    def test_top_or_bottom_rail_is_one_row_of_tiles_thick(self):
        """Owner (2026-10-31): on a top or bottom rail the pinned apps are one row, and the rail is as thick as that row."""
        s = {**SETTINGS, "stage": {**SETTINGS["stage"], "railPosition": "bottom"}}
        with TestShell(settings=s) as shell:
            self._wait_layers(shell)
            shell.set("stage.railWidth", "150")          # the first set applies the nested monitor's scale; measure after it
            time.sleep(3)
            st = json.loads(shell.ipc("stage", "status"))["screens"][0]
            rail = self._layers(shell)["bbkos-stage"]
            self.assertEqual(st["dockSize"]["height"], st["tile"], "the pinned apps are not one row")
            self.assertEqual(rail[3], st["tile"] + 2 * st["padding"], f"the rail is not one row thick: {rail} {st}")

    def test_alignbar_only_for_a_full_left_rail(self):
        for extra in ({"railPosition": "top"}, {"railHug": True}):
            with TestShell(settings={**SETTINGS, "stage": {**SETTINGS["stage"], **extra}}) as shell:
                self._wait_layers(shell)
                self.assertFalse(json.loads(shell.ipc("stage", "dock"))["alignBar"], extra)

    def test_rail_on_the_bar_edge_restacks_after_hide(self):
        with TestShell(settings={**SETTINGS, "stage": {**SETTINGS["stage"], "railPosition": "top"}}) as shell:
            self._wait_layers(shell)
            shell.ipc("bar", "hide")
            time.sleep(1.5)
            shell.ipc("bar", "unhide")
            time.sleep(3)
            lay = self._layers(shell)
            bar, rail = lay["bbkos-bar"], lay["bbkos-stage"]
            self.assertEqual((bar[1], rail[1]), (0, bar[3]), lay)
            self.assertEqual((rail[0], rail[2]), (0, self._screen(shell)[0]), f"not a top rail across the screen: {lay}")

    def test_rail_follows_the_bar_style_outside_grid_mode(self):
        s = {"shell": {"gridMode": False, "barRadius": 12, "barFloat": 6, "barPills": "grouped"},
             "stage": {"dock": True, "dockApps": ["kitty"], "railWidth": 100}}
        with TestShell(settings=s) as shell:
            self._wait_layers(shell)
            st = json.loads(shell.ipc("stage", "status"))["screens"][0]
            self.assertEqual((st["style"]["radius"], st["style"]["pills"]), (12, "grouped"))
            self.assertEqual(st["body"]["x"], 6, "the body does not float off the left edge by barFloat")

    def test_rail_stays_below_the_bar_after_the_bar_is_hidden_and_shown(self):
        """Regression (2026-10-30): Hyprland gives a screen edge to the layer window mapped first. A rail that stayed mapped
        while the bar was hidden and shown again came before it, took the full height and pushed the bar aside."""
        with TestShell(settings=SETTINGS) as shell:
            deadline = time.time() + 20
            while time.time() < deadline and len(self._layers(shell)) < 2:
                time.sleep(0.5)
            before = self._layers(shell)
            self.assertEqual(len(before), 2, before)
            bar, rail = before["bbkos-bar"], before["bbkos-stage"]
            self.assertEqual((bar[0], bar[1]), (0, 0))
            # flush against the bar: grid mode makes the bar a whole number of physical pixels thick (Theme.barHeight), so the two
            # share no pixel row and need no gap; the 1 px gap of 2026-10-30 is only for a scale where no whole thickness is found
            self.assertEqual(rail[1], bar[1] + bar[3], f"the rail does not start where the bar ends: {before}")
            for _ in range(2):
                shell.ipc("bar", "hide")
                time.sleep(1.5)
                shell.ipc("bar", "unhide")
                time.sleep(3)
                after = self._layers(shell)
                self.assertEqual(after["bbkos-bar"][:2], (0, 0), f"the bar was pushed aside: {after}")
                self.assertEqual(after["bbkos-stage"][1], after["bbkos-bar"][3], f"the rail covers the bar or left a gap: {after}")

    def test_dock_is_off_without_grid_mode(self):
        with TestShell(settings={"shell": {"gridMode": False}}) as shell:
            time.sleep(3)
            self.assertFalse(json.loads(shell.ipc("stage", "dock"))["on"])


if __name__ == "__main__":
    unittest.main()
