import unittest

import rank
from big_score import build, system_quality


class BigScoreTests(unittest.TestCase):
    def test_rank_includes_40_session_horizon(self):
        self.assertEqual(rank.ORIZZONTI, (5, 10, 20, 40, 60))

    def test_rank_exposes_non_overlapping_signal_statistics(self):
        import numpy as np
        close = np.arange(1.0, 301.0)
        base = {20: (0.02, 0.02, 0.02, 0.02)}
        signals = [(i, float(close[i])) for i in range(10, 260, 10)]
        stats = rank.stat_coppia(close, base, 20, signals, 150)
        self.assertEqual(len(stats), 17)
        self.assertGreaterEqual(stats[9], 5)
        self.assertIsNotNone(stats[12])

    def test_requires_minimum_sample_and_two_halves(self):
        self.assertIsNone(system_quality([9, 70, 3, 2, 1, 1, 5, 4, 2, 4, 2, 70, 2, 1, 1, 2, 2]))
        self.assertIsNone(system_quality([20, 70, 3, 2, None, 1, 10, 10, 2, 8, 3, 70, 3, None, 1, 4, 4]))

    def test_positive_stable_system_scores_above_neutral(self):
        q = system_quality([30, 65, 4, 3, 2, 2, 15, 15, 1.5, 8, 3, 65, 3, 2, 2, 4, 4])
        self.assertGreater(q, 50)

    def test_negative_unstable_system_scores_below_neutral(self):
        q = system_quality([30, 35, -4, -3, -2, -2, 15, 15, -1.5, 8, -3, 35, -3, -2, -2, 4, 4])
        self.assertLess(q, 50)

    def test_no_current_big_signal_preserves_base_score(self):
        base = {
            "t": "TEST.MI", "score": 80, "score20": 81,
            "score40": 80, "score60": 79, "eligible": True,
            "system_ages": {},
        }
        scores = {"generated": "test", "period": "5y", "rows": [base]}
        ranks = {"righe": []}
        out = build(scores, ranks)["rows"][0]
        self.assertEqual(out["score_big20"], 81)
        self.assertEqual(out["score_big40"], 80)
        self.assertEqual(out["score_big60"], 79)

    def test_active_signal_uses_matching_system_history(self):
        base = {
            "t": "TEST.MI", "score": 80, "score20": 80,
            "score40": 80, "score60": 80, "eligible": True,
            "system_ages": {"core": 1},
        }
        scores = {"generated": "test", "period": "5y", "rows": [base]}
        stat = [30, 70, 5, 4, 3, 3, 15, 15, 2.0, 8, 4, 70, 4, 3, 3, 4, 4]
        ranks = {"righe": [{"t": "TEST.MI", "st": {
            "20": {"core": stat}, "40": {"core": stat}, "60": {"core": stat}
        }}]}
        out = build(scores, ranks)["rows"][0]
        self.assertGreater(out["score_big20"], 80)
        self.assertEqual(out["big_signal_detail"]["20"]["active"][0]["id"], "core")


if __name__ == "__main__":
    unittest.main(verbosity=2)
