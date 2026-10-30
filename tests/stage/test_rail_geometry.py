"""Where the stage rail's body sits on any edge, full length or hugging (modules/stage/RailGeometry.js), run under node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

GEO = Path(__file__).resolve().parents[2] / "dotfiles/quickshell/.config/quickshell/modules/stage/RailGeometry.js"


def js(expr):
    src = GEO.read_text().replace(".pragma library", "", 1)
    out = subprocess.run(["node", "-e", src + "\nconsole.log(JSON.stringify(" + expr + "))"],
                         capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class RailGeometryTest(unittest.TestCase):
    def test_full_length_side_rail_fills_the_window_less_the_float(self):
        self.assertEqual(js('body({edge:"left",hug:false,align:"centre",float:6,thickness:100,windowLength:1095,contentLength:300,px:1})'),
                         {"x": 6, "y": 6, "width": 100, "height": 1083})

    def test_hug_aligns_start_centre_end_on_a_bottom_rail(self):
        base = 'edge:"bottom",hug:true,float:0,thickness:100,windowLength:1800,contentLength:400,px:1'
        self.assertEqual(js(f'body({{{base},align:"start"}})')["x"], 0)
        self.assertEqual(js(f'body({{{base},align:"centre"}})')["x"], 700)
        self.assertEqual(js(f'body({{{base},align:"end"}})')["x"], 1400)
        self.assertEqual(js(f'body({{{base},align:"end"}})')["y"], 0)

    def test_hug_never_exceeds_the_edge(self):
        self.assertEqual(js('body({edge:"right",hug:true,align:"end",float:8,thickness:100,windowLength:1000,contentLength:5000,px:1})')["height"], 984)

    def test_grid_snaps_to_whole_physical_pixels(self):
        b = js('body({edge:"top",hug:true,align:"centre",float:0,thickness:105,windowLength:1800,contentLength:401,px:0.9375})')
        for v in b.values():
            self.assertAlmostEqual(v / 0.9375, round(v / 0.9375), places=6)

    def test_window_origin_on_the_bar_edge_and_beside_it(self):
        self.assertEqual(js('windowOrigin({edge:"top",screenWidth:1800,screenHeight:1125,windowThickness:100,barPosition:"top",barInset:30})'), {"x": 0, "y": 30})
        self.assertEqual(js('windowOrigin({edge:"right",screenWidth:1800,screenHeight:1125,windowThickness:100,barPosition:"top",barInset:30})'), {"x": 1700, "y": 30})

    def test_window_origin_without_reserve(self):
        self.assertEqual(js('windowMargins({edge:"bottom",reserve:false,barPosition:"bottom",barInset:30,gridPad:0})'), {"top": 0, "bottom": 30, "left": 0, "right": 0})
        self.assertEqual(js('windowMargins({edge:"right",reserve:true,barPosition:"right",barInset:30,gridPad:1})'), {"top": 0, "bottom": 0, "left": 0, "right": 1})

    def test_margins_match_todays_left_rail(self):
        # today's Stage.qml: a reserving left rail under a top bar keeps gridPad from it; not reserving it keeps the bar's inset
        self.assertEqual(js('windowMargins({edge:"left",reserve:true,barPosition:"top",barInset:30,gridPad:1})'), {"top": 1, "bottom": 0, "left": 0, "right": 0})
        self.assertEqual(js('windowMargins({edge:"left",reserve:false,barPosition:"right",barInset:30,gridPad:0})'), {"top": 0, "bottom": 0, "left": 0, "right": 0})


if __name__ == "__main__":
    unittest.main()
