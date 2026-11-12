"""Tests for the panel layout at different widths: python3 -m unittest discover tests"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_loader = importlib.machinery.SourceFileLoader("herdr_issues_layout", os.path.join(ROOT, "bin", "herdr-issues"))
hi = importlib.util.module_from_spec(importlib.util.spec_from_loader("herdr_issues_layout", _loader))
_loader.exec_module(hi)

ISSUE = {"number": 116, "title": "Stream authenticated live events from self-hosted Actions runners to the panel",
         "state": "OPEN", "labels": [{"name": "ready-for-agent"}], "assignees": [{"login": "jhowliu"}],
         "author": {"login": "jhowliu"}, "updatedAt": "2026-10-01T00:00:00Z"}


def texts(lines):
    """Just the text of each line, for comparing layouts."""
    return [[text for _, text, _ in segs] for segs in lines]


class ItemLinesTest(unittest.TestCase):
    def setUp(self):
        self.panel = hi.Panel("/nonexistent")

    def test_a_wide_panel_keeps_one_title_line_and_the_age(self):
        lines = texts(self.panel.item_lines(ISSUE, 80))

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0][:2], ["●", "#116"])
        self.assertTrue(lines[0][2].endswith("…"))
        self.assertRegex(lines[0][3], r"^\d+(mo|d|h|m|y)$", "the age column")
        self.assertEqual(lines[1], ["ready-for-agent · @jhowliu"])

    def test_a_narrow_panel_wraps_the_title_onto_two_lines_and_drops_the_age(self):
        lines = texts(self.panel.item_lines(ISSUE, 30))

        self.assertEqual(lines[0], ["●", "#116", "Stream authenticated"])
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[1][0].startswith("live events"))
        self.assertTrue(lines[1][0].endswith("…"), "a title longer than two lines is cut")
        for segs in self.panel.item_lines(ISSUE, 30):
            for x, text, _ in segs:
                self.assertLessEqual(x + hi.text_width(text), 30, "nothing runs past the edge")

    def test_a_short_title_takes_one_line_even_when_narrow(self):
        lines = texts(self.panel.item_lines(dict(ISSUE, title="Add subtract()"), 24))

        self.assertEqual(lines, [["●", "#116", "Add subtract()"], ["ready-for-agent · @…"]])

    def test_the_run_state_leads_the_last_line(self):
        self.panel.runs = {116: {"status": "implementing", "finishedAt": None, "interrupted": False}}

        lines = texts(self.panel.item_lines(ISSUE, 30))

        self.assertEqual(lines[-1][0], "◐ implementing")


class FooterTest(unittest.TestCase):
    def test_the_longest_hint_that_fits_is_shown(self):
        panel = hi.Panel("/nonexistent")
        panel.cage = "/repo"

        self.assertIn("f filter", panel.footer_hint(120))
        self.assertEqual(panel.footer_hint(68), "⏎ view  c run  z zoom  ? keys  q quit")
        self.assertEqual(panel.footer_hint(30), "? keys  q quit")

    def test_c_is_listed_only_when_issues_can_run(self):
        panel = hi.Panel("/nonexistent")

        self.assertEqual(panel.footer_hint(68), "⏎ view  z zoom  ? keys  q quit")
        self.assertNotIn("c", [key for key, _ in panel.key_list()])
        panel.cage = "/repo"
        self.assertIn("c", [key for key, _ in panel.key_list()])

    def test_question_mark_opens_the_key_list_and_any_key_closes_it(self):
        panel = hi.Panel("/nonexistent")

        self.assertTrue(panel.handle("?", 40))
        self.assertTrue(panel.help)
        self.assertTrue(panel.handle("q", 40), "q closes the key list instead of quitting")
        self.assertFalse(panel.help)


class PlacementTest(unittest.TestCase):
    def test_toggle_opens_zoomed_beside_a_narrow_pane(self):
        self.assertEqual(hi.panel_placement(100), "zoomed")
        self.assertEqual(hi.panel_placement(hi.ZOOM_BELOW), "split")
        self.assertEqual(hi.panel_placement(None), "split", "unknown width keeps the old behavior")


class SavePanelsTest(unittest.TestCase):
    def test_panels_saving_at_the_same_time_do_not_race(self):
        with tempfile.TemporaryDirectory() as d:
            saved = hi.STATE_DIR, hi.PANELS_FILE
            hi.STATE_DIR, hi.PANELS_FILE = d, os.path.join(d, "panels.json")
            errors = []

            def save(i):
                try:
                    hi.save_panels({"w1:t%d" % i: "w1:p%d" % i})
                except OSError as e:
                    errors.append(e)

            try:
                threads = [threading.Thread(target=save, args=(i,)) for i in range(20)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                with open(hi.PANELS_FILE) as f:
                    self.assertEqual(len(json.load(f)), 1)
                self.assertEqual(errors, [])
                self.assertEqual(os.listdir(d), ["panels.json"], "no temp files are left behind")
            finally:
                hi.STATE_DIR, hi.PANELS_FILE = saved


if __name__ == "__main__":
    unittest.main()
