"""The bbkOS menu's ranking and calculator (modules/launcher/Rank.js), run under node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

RANK = Path(__file__).resolve().parents[2] / "dotfiles/quickshell/.config/quickshell/modules/launcher/Rank.js"


def js(expr):
    src = RANK.read_text().replace(".pragma library", "", 1)
    out = subprocess.run(["node", "-e", src + "\nconsole.log(JSON.stringify(" + expr + "))"],
                         capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


ITEMS = [
    {"id": "app:firefox", "title": "Firefox", "kind": "app"},
    {"id": "app:files", "title": "Files", "subtitle": "Thunar", "keywords": ["thunar", "folder"], "kind": "app"},
    {"id": "app:kitty", "title": "kitty", "keywords": ["terminal"], "kind": "app"},
    {"id": "cmd:lock", "title": "Lock screen", "kind": "command"},
    {"id": "set:wallpaper", "title": "Wallpaper and colours", "kind": "settings"},
]
NOW = 1_800_000_000_000


@unittest.skipUnless(shutil.which("node"), "node not installed")
class RankTest(unittest.TestCase):
    def titles(self, query, usage=None):
        return [i["title"] for i in js(f"rank({json.dumps(ITEMS)}, {json.dumps(query)}, {json.dumps(usage or {})}, {NOW})")]

    def test_prefix_beats_scattered_match(self):
        self.assertEqual(self.titles("fi")[:2], ["Files", "Firefox"])     # tie broken by name; both prefixes

    def test_word_start_and_keywords(self):
        self.assertEqual(self.titles("wall")[0], "Wallpaper and colours")
        self.assertEqual(self.titles("colours")[0], "Wallpaper and colours")
        self.assertEqual(self.titles("terminal"), ["kitty"])
        self.assertIn("Files", self.titles("thunar"))

    def test_several_words_match_a_title_word_by_word(self):
        items = ITEMS + [{"id": "set:gap", "title": "Gap between cards", "kind": "settings", "subtitleOnly": True,
                          "subtitle": "Settings · Windows › Stage mode · Cards"}]
        def titles(q):
            return [i["title"] for i in js(f"rank({json.dumps(items)}, {json.dumps(q)}, {{}}, {NOW})")]
        self.assertEqual(titles("card gap")[0], "Gap between cards")
        self.assertEqual(titles("gap cards")[0], "Gap between cards")
        self.assertEqual(titles("lock zz"), [])                 # every word must start a word of the title
        self.assertEqual(titles("stage mode"), [])              # a subtitleOnly row is not found through its subtitle

    def test_unrelated_query_matches_nothing(self):
        self.assertEqual(self.titles("zzq"), [])

    def test_medium_threshold_drops_scattered_long_queries(self):
        self.assertEqual(js('fuzzy("lock screen", "lsn")') >= 0, True)
        self.assertTrue(js('accepted(fuzzy("wallpaper and colours", "wpcls"), 5)'))     # word starts: a fair match
        self.assertFalse(js('accepted(fuzzy("wallpaper and colours", "aeo"), 3)'))      # scattered middles: not

    def test_frecency_and_learned_terms(self):
        usage = {"app:firefox": {"visits": [NOW - 1000] * 5, "terms": ["f"]}}
        self.assertEqual(self.titles("f", usage)[0], "Firefox")            # learned: "f" opened Firefox before
        self.assertEqual(self.titles("", usage)[0], "Firefox")             # empty query: most used first

    def test_learned_term_brings_a_non_matching_item_and_expires(self):
        recent = {"app:kitty": {"visits": [NOW - 86400000], "terms": ["term"]}}
        self.assertEqual(self.titles("ter", recent)[0], "kitty")           # a learned term that starts with the query
        old = {"app:kitty": {"visits": [NOW - 20 * 86400000], "terms": ["zz"]}}
        self.assertNotIn("kitty", self.titles("zz", old))                   # 17 days later it is forgotten

    def test_record_is_bounded(self):
        u = js(f"(function(){{ var u = {{}}; for (var i = 0; i < 320; i++) u = record(u, 'id' + i, 'q', {NOW} + i); "
               f"for (var j = 0; j < 12; j++) u = record(u, 'id319', 'q' + j, {NOW} + 400 + j); return u }})()")
        self.assertEqual(len(u), 300)
        self.assertNotIn("id0", u)
        self.assertEqual(len(u["id319"]["visits"]), 10)
        self.assertEqual(len(u["id319"]["terms"]), 5)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class CalculatorTest(unittest.TestCase):
    def calc(self, text):
        return js(f"calculate({json.dumps(text)})")

    def test_arithmetic(self):
        self.assertEqual(self.calc("2+2*3"), 8)
        self.assertEqual(self.calc("(2+2)*3"), 12)
        self.assertEqual(self.calc("2^10"), 1024)
        self.assertEqual(self.calc("10 % 3"), 1)
        self.assertEqual(self.calc("1/3"), 0.3333333333)
        self.assertEqual(self.calc("-4 + 1"), -3)
        self.assertEqual(self.calc("12 × 3 ÷ 4"), 9)

    def test_not_a_calculation(self):
        for t in ("42", "-5", "firefox", "2+", "1/0", "alert(1)", "2+2; x", "process.exit()"):
            self.assertIsNone(self.calc(t), t)


if __name__ == "__main__":
    unittest.main()
