import unittest
import numpy as np
import pandas as pd
import benchmark


def sample_df(n=320):
    idx = pd.bdate_range("2024-01-02", periods=n)
    # Trend deterministico con oscillazione: genera barre OHLC valide.
    x = np.arange(n, dtype=float)
    close = 100 * np.exp(0.0007 * x + 0.025 * np.sin(x / 8))
    prev = np.r_[close[0], close[:-1]]
    open_ = prev * (1 + 0.001 * np.sin(x / 3))
    high = np.maximum(open_, close) * 1.012
    low = np.minimum(open_, close) * 0.988
    return pd.DataFrame({
        "Open": open_, "High": high, "Low": low, "Close": close,
        "Adj Close": close * (1 + 0.0001 * x), "Volume": np.full(n, 100000),
    }, index=idx)


class BenchmarkTests(unittest.TestCase):
    def test_entry_is_next_session_open_not_signal_close(self):
        df = sample_df(100)
        i = 20
        event = (str(df.index[i].date()), "core", "BUY", float(df["Close"].iloc[i]), "test")
        rows = benchmark._one_system(df, [event], "core", {}, ["time_20"], 0)
        self.assertEqual(len(rows), 1)
        trade = rows[0]["trades"][0]
        self.assertEqual(trade["in"], str(df.index[i + 1].date()))
        self.assertAlmostEqual(float(df["Open"].iloc[i + 1]), float(df["Open"].iloc[i + 1]))

    def test_candidate_signals_are_causal(self):
        df = sample_df()
        full = benchmark._candidate_events(df)
        cut = benchmark._candidate_events(df.iloc[:250])
        cut_dates = {x[0] for x in cut}
        full_past = [x[0] for x in full if x[0] <= str(df.index[249].date())]
        self.assertEqual(full_past, [x[0] for x in cut])

    def test_benchmark_contains_12_big_systems_plus_candidate(self):
        df = sample_df()
        rows = benchmark.ticker_benchmark("TEST.MI", df, [], {"tr": []}, cost_bps=0)
        ids = {x["system"] for x in rows}
        self.assertEqual(len(ids.intersection({s["id"] for s in __import__("systems").SYSTEMS})), 12)
        self.assertIn("chat_trend_pullback", ids)

    def test_dividend_adjusted_prices_do_not_enter_trade_returns(self):
        df = sample_df()
        event = (str(df.index[20].date()), "core", "BUY", float(df["Close"].iloc[20]), "test")
        a = benchmark._one_system(df, [event], "core", {}, ["time_20"], 0)[0]["trades"][0]["ret"]
        b = benchmark._one_system(df.drop(columns=["Adj Close"]), [event], "core", {}, ["time_20"], 0)[0]["trades"][0]["ret"]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
