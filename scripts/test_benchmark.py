import unittest
import numpy as np
import pandas as pd
import benchmark


def sample_df(n=320):
    idx = pd.bdate_range("2024-01-02", periods=n)
    x = np.arange(n, dtype=float)
    close = 100 * np.exp(0.0007 * x + 0.025 * np.sin(x / 8))
    prev = np.r_[close[0], close[:-1]]
    open_ = prev * (1 + 0.001 * np.sin(x / 3))
    high = np.maximum(open_, close) * 1.012
    low = np.minimum(open_, close) * 0.988
    return pd.DataFrame({"Open":open_,"High":high,"Low":low,"Close":close,
        "Adj Close":close*(1+0.0001*x),"Volume":np.full(n,100000)}, index=idx)


class BenchmarkTests(unittest.TestCase):
    def test_entry_is_next_session_open_not_signal_close(self):
        df=sample_df(100); i=20
        event=(str(df.index[i].date()),"core","BUY",float(df["Close"].iloc[i]),"test")
        rows=benchmark._one_system(df,[event],"core",{},["time_20"],0)
        self.assertEqual(len(rows),1)
        trade=rows[0]["trades"][0]
        self.assertEqual(trade["in"],str(df.index[i+1].date()))
        self.assertAlmostEqual(trade["entry_price"],float(df["Open"].iloc[i+1]),places=5)

    def test_candidate_signals_are_causal(self):
        df=sample_df(); full=benchmark._candidate_events(df); cut=benchmark._candidate_events(df.iloc[:250])
        full_past=[x[0] for x in full if x[0]<=str(df.index[249].date())]
        self.assertEqual(full_past,[x[0] for x in cut])

    def test_benchmark_contains_12_big_systems_plus_candidate(self):
        import systems
        self.assertEqual(len(systems.SYSTEMS),12)
        ids=[s["id"] for s in systems.SYSTEMS]+["chat_trend_pullback"]
        self.assertEqual(len(ids),13); self.assertEqual(len(set(ids)),13)

    def test_leveraged_and_inverse_products_are_excluded(self):
        df=sample_df()
        events=[(str(df.index[20].date()),"core","BUY",float(df["Close"].iloc[20]),"test")]
        meta={"tr":[]}
        self.assertEqual(benchmark.ticker_benchmark("LEV.MI",df,events,meta,instrument={"lv":True})["rows"],[])
        self.assertEqual(benchmark.ticker_benchmark("INV.MI",df,events,meta,instrument={"inv":True})["rows"],[])
        self.assertTrue(benchmark.ticker_benchmark("PLAIN.MI",df,events,meta,instrument={"lv":False,"inv":False})["rows"])

    def test_forward_signal_benchmark_uses_non_overlapping_baseline(self):
        df=sample_df()
        events=[(str(df.index[i].date()),"core","BUY",float(df["Close"].iloc[i]),"test") for i in (20,60,100)]
        rows=benchmark._forward_signal_rows("TEST.MI",df,events)
        h20=next(x for x in rows if x["system"]=="core" and x["horizon"]==20)
        self.assertGreater(h20["signals"],0)
        self.assertGreater(h20["baseline_n"],0)
        self.assertIn("median_edge",h20)

    def test_dividend_adjusted_prices_do_not_enter_trade_returns(self):
        df=sample_df()
        event=(str(df.index[20].date()),"core","BUY",float(df["Close"].iloc[20]),"test")
        a=benchmark._one_system(df,[event],"core",{},["time_20"],0)[0]["trades"][0]["ret"]
        b=benchmark._one_system(df.drop(columns=["Adj Close"]),[event],"core",{},["time_20"],0)[0]["trades"][0]["ret"]
        self.assertEqual(a,b)

    def test_trade_returns_do_not_include_circular_hold_excess(self):
        df=sample_df()
        event=(str(df.index[20].date()),"core","BUY",float(df["Close"].iloc[20]),"test")
        trade=benchmark._one_system(df,[event],"core",{},["time_20"],0)[0]["trades"][0]
        self.assertNotIn("excess",trade)
        self.assertNotIn("benchmark",trade)


if __name__=="__main__":
    unittest.main(verbosity=2)
