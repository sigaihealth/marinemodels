"""Regression checks for prospective wave coverage and the previously frozen detector."""

import os
import unittest
from datetime import timedelta
from pathlib import Path

import refresh_inputs as monitor


class ProspectiveWaveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        world_model = Path(
            os.environ.get("PIONEER_WORLD_MODEL", Path(__file__).resolve().parent.parent)
        )
        cls.weather = monitor.load_module(world_model / "pioneer-6h/sources/build_weather.py")

    def run_inventory(self, *, days=45, missing=(), sparse=(), include_january=False, as_of=None):
        onset = monitor.SEED_ONSET
        year_end = monitor.parse("2026-12-31T23:00:00Z")
        highs = {onset, onset + monitor.HOUR}
        if include_january:
            highs.update({year_end, year_end + monitor.HOUR, year_end + 2 * monitor.HOUR})
        cutoff = onset + days * monitor.DAY
        rows = []
        t = monitor.WAVE_START
        while t <= cutoff:
            if t not in missing:
                offsets = (5,) if t in sparse else (35, 5)
                rows.extend(
                    (t - timedelta(minutes=x), 4.0 if t in highs else 1.0, None) for x in offsets
                )
            t += monitor.HOUR
        return monitor.inventory(self.weather, rows, rows[-1][0], as_of or cutoff)

    def test_utc_year_rollover_remains_one_event(self):
        _, events, gaps = self.run_inventory(include_january=True)
        self.assertEqual(gaps, [])
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["onset"], "2026-12-31T23:00:00Z")
        self.assertEqual(events[1]["end"], "2027-01-01T01:00:00Z")
        self.assertEqual(events[1]["status"], "complete")
        self.assertEqual(events[1]["sequence_certain"], 1)

    def test_delayed_feed_cannot_close_storm(self):
        cutoff = monitor.SEED_ONSET + 12 * monitor.DAY
        _, events, _ = self.run_inventory(days=1, as_of=cutoff)
        self.assertEqual(events[0]["observed_through"], monitor.iso(monitor.SEED_ONSET + monitor.DAY))
        self.assertEqual(events[0]["status"], "provisional")

    def test_sparse_or_missing_bin_next_to_high_blocks_closure(self):
        t = monitor.SEED_ONSET - monitor.HOUR
        for k in ["sparse", "missing"]:
            with self.subTest(k=k):
                _, events, gaps = self.run_inventory(**{k: [t]})
                self.assertIn(t, gaps)
                self.assertEqual(events[0]["wave_window_closed"], 0)

    def test_two_missing_calm_hours_block_sequence_of_later_event(self):
        t = monitor.SEED_ONSET + 10 * monitor.DAY
        _, events, gaps = self.run_inventory(missing=(t, t + monitor.HOUR), include_january=True)
        self.assertEqual(gaps, [t, t + monitor.HOUR])
        self.assertEqual(events[0]["status"], "complete")
        self.assertEqual(events[1]["status"], "complete")
        self.assertEqual(events[1]["sequence_certain"], 0)

    def test_isolated_missing_calm_hour_cannot_hide_two_hour_run(self):
        t = monitor.SEED_ONSET + 10 * monitor.DAY
        _, events, gaps = self.run_inventory(missing=(t,), include_january=True)
        self.assertEqual(gaps, [])
        self.assertEqual(events[1]["sequence_certain"], 1)


if __name__ == "__main__":
    unittest.main()
