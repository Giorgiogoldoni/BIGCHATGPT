import unittest
import numpy as np
import pandas as pd
import entry_exit_research as R


def sample_df(n=360):
    idx = pd.bdate_range("2023-01-02", periods=n)
    x = np.arange(n, dtype=float)
    close = 100*np.exp(.0005*x + .02*np.sin(x/9))
    prev = np.r_[close[0], close[:-1]]
    opn = prev*(1+.001*np.sin(x/4))
    high = np.maximum(opn, close)*1.015
    low = np.minimum(opn, close)*.985
    return pd.DataFrame({"Open":opn,"High":high,"Low":low,"Close":close,
                         "Adj Close":close*1.2,"Volume":100000}, index=idx)


class EntryExitResearchTests(unittest.TestCase):
    def test_entry_next_open_and_forward_horizons(self):
        df = sample_df()
        i = 20
        ev = [(str(df.index[i].date()), "core", "BUY", float(df.Close.iloc[i]), "test")]
        result = R.analyze_ticker("TEST.MI", df, ev, ["core"])
        row = next(x for x in result["entry"] if x["horizon"] == 5)
        self.assertEqual(row["n"], 1)
        expected = (df.Close.iloc[i+5]/df.Open.iloc[i+1]-1)*100-.1
        self.assertAlmostEqual(row["mean"], expected, places=3)

    def test_fixed_cohort_is_independent_of_exit_rule(self):
        df = sample_df()
        ev = [(str(df.index[i].date()), "core", "BUY", float(df.Close.iloc[i]), "test") for i in (20, 40, 80, 140, 220)]
        result = R.analyze_ticker("TEST.MI", df, ev, ["core"])
        counts = {x["cohort_signals"] for x in result["exit"]}
        self.assertEqual(counts, {len(R._fixed_cohort([20,40,80,140,220], len(df), 60))})

    def test_stop_gap_executes_at_open_not_impossible_stop_price(self):
        df = sample_df(120)
        entry_i = 21
        entry = float(df.Open.iloc[entry_i])
        df.iloc[22, df.columns.get_loc("Open")] = entry*.85
        df.iloc[22, df.columns.get_loc("Low")] = entry*.84
        f = R._features(df)
        result = R._exit_one(df, entry_i, entry, "stop_8", f)
        self.assertEqual(result[0], 22)
        self.assertAlmostEqual(result[1], entry*.85, places=5)

    def test_close_based_exit_executes_next_open(self):
        df = sample_df()
        entry_i = 40
        f = R._features(df)
        # Force a valid EMA bearish cross at j=60; exit must be next day's open.
        f["ema20"][:] = f["ema50"] + 1
        f["ema20"][60] = f["ema50"][60] - 1
        result = R._exit_one(df, entry_i, float(df.Open.iloc[entry_i]), "ema20_50", f)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 61)
        self.assertAlmostEqual(result[1], float(df.Open.iloc[61]), places=6)

    def test_adjusted_close_does_not_affect_raw_returns(self):
        df = sample_df()
        ev = [(str(df.index[20].date()), "core", "BUY", float(df.Close.iloc[20]), "test")]
        a = R.analyze_ticker("TEST.MI", df, ev, ["core"])
        df["Adj Close"] *= 9
        b = R.analyze_ticker("TEST.MI", df, ev, ["core"])
        self.assertEqual(a["entry"], b["entry"])

    def test_all_exit_rules_share_same_cohort(self):
        df = sample_df()
        ev = [(str(df.index[i].date()), "core", "BUY", float(df.Close.iloc[i]), "test") for i in (20, 90, 160, 230)]
        result = R.analyze_ticker("TEST.MI", df, ev, ["core"])
        self.assertEqual(len(result["exit"]), len(R.EXIT_MODES))
        self.assertEqual(len({r["cohort_signals"] for r in result["exit"]}), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
