"""Test dello score BIGCHATGPT: range, orizzonti, esclusioni e total-return."""
import unittest
import numpy as np
import pandas as pd
import score


def sample_df(n=600):
    rng = np.random.default_rng(20261113)
    idx = pd.bdate_range("2024-01-02", periods=n)
    ret = rng.normal(0.0003, 0.008, n)
    close = 100 * np.exp(np.cumsum(ret))
    prev = np.r_[close[0], close[:-1]]
    open_ = prev * (1 + rng.normal(0, 0.002, n))
    high = np.maximum(open_, close) * 1.008
    low = np.minimum(open_, close) * 0.992
    volume = rng.integers(50_000, 500_000, n)
    return pd.DataFrame({
        "Open": open_, "High": high, "Low": low, "Close": close,
        "Adj Close": close * np.linspace(1.0, 1.02, n), "Volume": volume,
    }, index=idx)


class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = sample_df()
        cls.events = [
            (str(cls.df.index[i].date()), "core", "CORE BUY2", float(cls.df["Close"].iloc[i]), "test")
            for i in range(60, len(cls.df) - 60, 35)
        ]
        cls.instrument = {
            "t": "TEST.MI", "n": "Test ETF", "i": "TESTISIN",
            "e": "Test issuer", "tp": "ETF", "ac": "equity",
            "lv": False, "inv": False,
        }

    def test_score_has_three_horizons_and_stays_in_range(self):
        result = score.calculate(self.instrument, self.df, self.events, {"nuovo": True, "core": "BUY2"})
        self.assertEqual(result["status"], "ok")
        for key in ("score20", "score40", "score60", "score"):
            self.assertGreaterEqual(result[key], 0)
            self.assertLessEqual(result[key], 100)
        self.assertIn("20", result["edge"])
        self.assertIn("40", result["edge"])
        self.assertIn("60", result["edge"])

    def test_2026_issues_remain_scored_but_are_not_eligible(self):
        instrument = dict(self.instrument, t="ACSW.MI")
        result = score.calculate(instrument, self.df, self.events, {"nuovo": False, "core": "HOLD"})
        self.assertEqual(result["status"], "escluso_emissione_2026")
        self.assertFalse(result["eligible"])
        self.assertEqual(result["edge"]["20"]["n"], 0)
        self.assertIsNotNone(result["score"])

    def test_crypto_remains_outside_validation(self):
        instrument = dict(self.instrument, t="ASUI.MI", ac="crypto")
        result = score.calculate(instrument, self.df, self.events, {"nuovo": False, "core": "HOLD"})
        self.assertEqual(result["status"], "escluso_cripto")
        self.assertFalse(result["eligible"])

    def test_currency_strategy_is_not_in_standard_etf_top20(self):
        instrument = dict(self.instrument, t="EUUS.MI")
        result = score.calculate(instrument, self.df, self.events, {"nuovo": False, "core": "HOLD"})
        self.assertEqual(result["status"], "strumento_valutario")
        self.assertFalse(result["eligible"])

    def test_known_bond_funds_have_correct_asset_class(self):
        instrument = dict(self.instrument, t="SXRH.DE")
        result = score.calculate(instrument, self.df, self.events, {"nuovo": False, "core": "HOLD"})
        self.assertEqual(result["asset_class"], "bond")

    def test_historical_edge_excludes_dividends_even_when_adjusted_close_exists(self):
        edge = score._historical_edge(self.df, self.events, 20)
        self.assertFalse(edge["total_return"])
        close_only = self.df.drop(columns=["Adj Close"])
        plain = score._historical_edge(close_only, self.events, 20)
        self.assertEqual(edge["median"], plain["median"])
        self.assertEqual(edge["baseline_median"], plain["baseline_median"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
