import unittest
from bollettino import AREAS, area_view


class BollettinoTests(unittest.TestCase):
    def test_area_weights_sum_to_equity_budget(self):
        self.assertEqual(sum(x["weight"] for x in AREAS.values()), 60)

    def test_area_universes_do_not_double_count_tickers(self):
        all_tickers = [t for area in AREAS.values() for t in area["tickers"]]
        self.assertEqual(len(all_tickers), len(set(all_tickers)))

    def test_buy_requires_multi_indicator_confirmation(self):
        ticker = "TEST.MI"
        row = {
            "ticker": ticker, "name": "Test ETF", "score": 80,
            "trend": "VERDE", "trend_rs": "VERDE", "buy_level": "BUY",
            "mm_aligned": True, "sar_bullish": True,
            "vortex_bullish": True, "rvi_bullish": True,
            "stress_score": 0, "perf7": 2, "perf30": 5,
        }
        result = area_view("Test", {"weight": 10, "tickers": [ticker]}, {ticker: row})
        self.assertEqual(result["stance"], "SEGNALI POSITIVI")

    def test_red_majority_takes_priority_over_watch(self):
        rows = {
            "A": {"ticker": "A", "trend": "ROSSO", "buy_level": "WATCH", "score": 20},
            "B": {"ticker": "B", "trend": "ROSSO", "buy_level": "SELL", "score": 10},
            "C": {"ticker": "C", "trend": "VERDE", "buy_level": "WATCH", "score": 30},
        }
        result = area_view("Test", {"weight": 10, "tickers": ["A", "B", "C"]}, rows)
        self.assertEqual(result["stance"], "DIFESA")


if __name__ == "__main__":
    unittest.main()
