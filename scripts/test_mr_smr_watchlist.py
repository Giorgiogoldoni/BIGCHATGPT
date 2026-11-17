import unittest
import numpy as np
import pandas as pd
import mr_smr_watchlist as W


class WatchlistTests(unittest.TestCase):
    def sample_df(self):
        idx = pd.bdate_range("2026-09-28", periods=8)
        close = np.array([100, 99, 98, 97, 96, 97, 98, 99], dtype=float)
        opn = close - 0.5
        return pd.DataFrame({"Open": opn, "High": close + 1, "Low": opn - 1, "Close": close}, index=idx)

    def test_signal_uses_next_session_open_and_round_trip_cost(self):
        df = self.sample_df()
        trades = [["mr", "2026-10-01", 98.0, "2026-10-06", 99.0, "Banda Bollinger sup.", 1.02]]
        rows = W.ticker_rows("TEST.MI", "Test ETF", df, trades)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["execution_date"], "2026-10-02")
        self.assertAlmostEqual(rows[0]["entry_price"], float(df["Open"].iloc[4]))
        expected = (99.0 / float(df["Open"].iloc[4]) - 1) * 100 - 0.1
        self.assertAlmostEqual(rows[0]["return_net_pct"], round(expected, 3))

    def test_only_mr_smr_and_signals_from_start_date(self):
        df = self.sample_df()
        trades = [
            ["mr", "2026-09-30", 98, None, None, None, 1],
            ["smr", "2026-10-01", 98, None, None, None, 1],
            ["core", "2026-10-02", 98, None, None, None, 1],
        ]
        rows = W.ticker_rows("TEST.MI", "Test ETF", df, trades)
        self.assertEqual([r["system"] for r in rows], ["SMR"])

    def test_last_bar_signal_is_pending(self):
        df = self.sample_df()
        trades = [["smr", str(df.index[-1].date()), 99, None, None, None, 0]]
        rows = W.ticker_rows("TEST.MI", "Test ETF", df, trades)
        self.assertEqual(rows[0]["status"], "IN ATTESA")
        self.assertIsNone(rows[0]["entry_price"])

    def test_payload_counts(self):
        rows = [
            {"system":"MR","status":"ATTIVA","signal_date":"2026-10-01","ticker":"A"},
            {"system":"SMR","status":"CHIUSA","signal_date":"2026-10-02","ticker":"B"},
        ]
        payload = W.build_payload(rows, "2026-11-17")
        self.assertEqual(payload["summary"]["MR"]["active"], 1)
        self.assertEqual(payload["summary"]["SMR"]["closed"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
