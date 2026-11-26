"""Offline regression tests for the registered Pioneer salinity confirmation."""
import contextlib
import csv
import hashlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import score


H = score.H
START = score.FIRST_ISSUE


def event(start, end=None, onset=None):
    return {
        "onset": score.utc(onset or start),
        "window_start": score.utc(start),
        "window_end": score.utc(end or start),
        "status": "complete",
        "sequence_certain": "true",
        "observed_through": score.utc(START + 1200 * H),
    }


def ctd_row(t, salinity, deployment="4"):
    return dict(time=score.utc(t), source_time=score.utc(t), deployment=deployment,
                temperature_c="15", salinity=str(salinity))


def write_csv(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def write_inputs(data, events, ctd, current_issues):
    # A forecast needs three hourly currents and four astronomical tide predictions.
    current_times = sorted({t + k * H for t in current_issues for k in (-2, -1, 0)})
    tide_times = sorted({t + k * H for t in current_issues for k in (-3, 0, 3, 6)})
    write_csv(data / "events.csv", events)
    write_csv(data / "ctd_hourly.csv", [ctd[t] for t in sorted(ctd)])
    write_csv(data / "currents.csv", [
        dict(time=score.utc(t), source_time=score.utc(t - H / 2), deployment="4",
             u_ms="0.2", v_ms="0.1") for t in current_times
    ])
    write_csv(data / "tides.csv", [dict(time=score.utc(t), tide_m="0.8") for t in tide_times])
    write_csv(data / "wave_hourly.csv", [dict(time=e["onset"], wave_height_m=4) for e in events])
    hashes = {name: hashlib.sha256((data / name).read_bytes()).hexdigest() for name in score.INPUTS}
    (data / "refresh_provenance.json").write_text(json.dumps({"data_sha256": hashes}) + "\n")


def run_at(data, output, instant):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz or timezone.utc)

    with patch.object(score, "datetime", Clock), contextlib.redirect_stdout(io.StringIO()):
        score.main(data, output)
    return json.loads((output / "state.json").read_text())


class ScoreTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.data = Path(scratch.name) / "input"
        self.data.mkdir()
        self.output = Path(scratch.name) / "output"

    def test_paired_errors_and_capture_time_use_verified_hours_only(self):
        # One unmatched forecast has an extreme value. Another has a target from a
        # different deployment. Neither should affect either model's denominator.
        issues = [START + k * H for k in range(6)]
        persistence = [30, 31, 35, 29, 900, 800]
        fixed = [32, 32, 31, 36, 1000, 950]
        observed = [31, 34, 30, 32]
        ledger = {}
        ctd = {}
        for i, t in enumerate(issues):
            target = t + 6 * H
            captures = ["", score.utc(target - H / 60), score.utc(target), score.utc(target + H)]
            ledger[t] = dict(issue=score.utc(t), valid=score.utc(target), deployment="4",
                             persistence=persistence[i], fixed=fixed[i],
                             first_recorded=captures[i] if i < 4 else score.utc(t),
                             origin="previous_study" if i == 0 else "observation_refresh")
            if i < len(observed):
                ctd[target] = ctd_row(target, observed[i])
        ctd[issues[-1] + 6 * H] = ctd_row(issues[-1] + 6 * H, 0, deployment="5")

        stats, pairs = score.evaluate_event("November", event(issues[0], issues[-1]), ledger, ctd)
        self.assertEqual([p["issue"] for p in pairs], [score.utc(t) for t in issues[:4]])
        self.assertEqual((stats["paired"], stats["missing_pairs"], stats["additional_pairs"]), (4, 2, 3))
        self.assertEqual(stats["recorded_before_valid"], 1)
        self.assertEqual(stats["persistence_mae"], (1 + 3 + 5 + 3) / 4)
        self.assertEqual(stats["fixed_mae"], (1 + 2 + 1 + 4) / 4)
        self.assertEqual(stats["gain"], 1)
        self.assertAlmostEqual(stats["additional_persistence_mae"], (3 + 5 + 3) / 3)
        self.assertAlmostEqual(stats["additional_fixed_mae"], (2 + 1 + 4) / 3)

    def test_first_capture_is_immutable_when_inputs_are_revised(self):
        issue = START + 20 * H  # First hour beyond the 20 already examined.
        valid = issue + 6 * H
        events = [event(START, issue, score.ANCHOR)]
        events[0].update(status="open", observed_through=score.utc(issue + H))
        ctd = {START + k * H: ctd_row(START + k * H, 34) for k in range(6, 22)}
        ctd[issue] = ctd_row(issue, 33)
        write_inputs(self.data, events, ctd, [issue])
        state = run_at(self.data, self.output, issue + H)
        first = score.keyed(score.read(self.output / "predictions.csv"), "issue")[issue]
        self.assertEqual(first["first_recorded"], score.utc(issue + H))
        self.assertEqual(state["storms"][0]["additional_pairs"], 0)

        for k in range(22, 26):
            ctd[START + k * H] = ctd_row(START + k * H, 34)
        events[0]["observed_through"] = score.utc(valid + H)
        ctd[issue] = ctd_row(issue, 31)
        ctd[valid] = ctd_row(valid, 34.5)
        write_inputs(self.data, events, ctd, [issue])
        state = run_at(self.data, self.output, valid + H)
        ledger = score.keyed(score.read(self.output / "predictions.csv"), "issue")
        seeds = score.keyed(score.read(score.BASE / "initial_forecasts.csv"), "issue")
        self.assertEqual(ledger, {**seeds, issue: first})
        stats = state["storms"][0]
        self.assertEqual((stats["paired"], stats["additional_pairs"], stats["recorded_before_valid"]), (21, 1, 1))
        self.assertEqual(stats["additional_persistence_mae"], 1.5)
        self.assertAlmostEqual(stats["additional_fixed_mae"], abs(float(first["fixed"]) - 34.5))

        def snapshot():
            return {p.relative_to(self.output): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}

        before = snapshot()
        run_at(self.data, self.output, valid + 10 * H)
        self.assertEqual(snapshot(), before)

    def test_mixed_input_snapshot_is_rejected_before_publication(self):
        t = START + 20 * H
        now = t + 10 * H
        ctd = {t: ctd_row(t, 33), t + 6 * H: ctd_row(t + 6 * H, 34)}
        write_inputs(self.data, [event(START, t, score.ANCHOR)], ctd, [t])
        run_at(self.data, self.output, now)
        report = (self.output / "state.json").read_bytes()
        ledger = (self.output / "predictions.csv").read_bytes()
        with (self.data / "currents.csv").open("a") as f:
            f.write("\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch: currents.csv"):
            run_at(self.data, self.output, now + H)
        self.assertEqual((self.output / "state.json").read_bytes(), report)
        self.assertEqual((self.output / "predictions.csv").read_bytes(), ledger)

    def test_next_three_storms_stay_registered_when_an_earlier_pair_is_missing(self):
        november = event(START, START + 19 * H, score.ANCHOR)
        issues = [START + k * 168 * H for k in range(1, 5)]
        successors = [event(t) for t in issues]
        # Include both a historical storm and a fourth fully observable successor.
        events = [successors[3], successors[1], event(START - 168 * H),
                  november, successors[2], successors[0]]
        ctd = {START + k * H: ctd_row(START + k * H, 34) for k in range(6, 26)}
        for t in issues:
            ctd[t] = ctd_row(t, 33)
            ctd[t + 6 * H] = ctd_row(t + 6 * H, 34)
        missing = ctd.pop(issues[1] + 6 * H)
        now = issues[-1] + 100 * H
        write_inputs(self.data, events, ctd, issues)
        state = run_at(self.data, self.output, now)
        self.assertEqual([s["onset"] for s in state["storms"]], [e["onset"] for e in [november, *successors[:3]]])
        self.assertEqual([s["missing_pairs"] for s in state["storms"]], [0, 0, 1, 0])
        self.assertEqual(state["successor_summary"]["complete"], 2)
        self.assertFalse(state["study_complete"])

        ctd[issues[1] + 6 * H] = missing
        november_target = ctd.pop(START + 9 * H)
        write_inputs(self.data, events, ctd, issues)
        # Independent snapshot: all three successors verify, but one November hour does not.
        state = run_at(self.data, self.output.with_name("missing-november"), now)
        self.assertEqual(state["successor_summary"]["complete"], 3)
        self.assertEqual(state["storms"][0]["missing_pairs"], 1)
        self.assertFalse(state["study_complete"])

        ctd[START + 9 * H] = november_target
        write_inputs(self.data, events, ctd, issues)
        state = run_at(self.data, self.output, now + H)
        self.assertEqual(state["successor_summary"]["complete"], 3)
        self.assertTrue(state["study_complete"])


if __name__ == "__main__":
    unittest.main()
