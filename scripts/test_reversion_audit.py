"""Test automatici per l'audit esecutivo MR/SMR."""
import unittest
import numpy as np
import pandas as pd

from reversion_audit import simulate_reversion_trades, _pooled_trade_stats


def frame(opn, high, low, close):
    idx = pd.bdate_range("2025-01-02", periods=len(close))
    return pd.DataFrame({
        "Open": opn, "High": high, "Low": low, "Close": close,
        "Volume": np.full(len(close), 100000),
    }, index=idx)


def event(df, sid):
    return (str(df.index[0].date()), sid, sid.upper(), float(df["Close"].iloc[0]), "test")


class ReversionAuditTests(unittest.TestCase):
    def test_mr_chandelier_is_rebased_on_next_open_entry(self):
        df = frame(
            [100, 100, 100, 100, 100],
            [101, 102, 102, 102, 102],
            [99, 99, 99, 97, 97],
            [100, 101, 100, 98, 98],
        )
        trades = simulate_reversion_trades(
            df, [event(df, "mr")], "mr",
            bb_upper=np.full(5, 1000.0), atr=[None, None, 1.0, 1.0, 1.0],
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_date"], str(df.index[1].date()))
        self.assertEqual(trades[0]["entry_price"], 100.0)
        self.assertEqual(trades[0]["exit_date"], str(df.index[3].date()))
        self.assertEqual(trades[0]["reason"], "Chandelier 3.0 ATR")

    def test_mr_bollinger_exit_is_close_based(self):
        df = frame([100] * 5, [101, 102, 103, 106, 107],
                   [99, 99, 99, 104, 105], [100, 101, 102, 106, 106])
        trades = simulate_reversion_trades(
            df, [event(df, "mr")], "mr",
            bb_upper=[1000, 1000, 1000, 105, 105], atr=[None] * 5,
        )
        self.assertEqual(trades[0]["exit_date"], str(df.index[3].date()))
        self.assertEqual(trades[0]["exit_price"], 106.0)
        self.assertEqual(trades[0]["reason"], "Banda Bollinger sup.")

    def test_smr_stop_uses_actual_next_open_and_gap_exit_close(self):
        # Il segnale nasce a Close=100, ma l'esecuzione avviene a Open=120.
        # Il close successivo a 100 è -16,67% dall'ingresso effettivo:
        # lo stop close-based esce a 100, non al teorico livello 102.
        df = frame([100, 120, 90, 95], [101, 121, 100, 96],
                   [99, 119, 85, 94], [100, 120, 100, 95])
        trades = simulate_reversion_trades(
            df, [event(df, "smr")], "smr",
            bb_upper=np.full(4, 1000.0), atr=[None] * 4,
        )
        trade = trades[0]
        self.assertEqual(trade["entry_price"], 120.0)
        self.assertEqual(trade["exit_price"], 100.0)
        self.assertEqual(trade["reason"], "Stop -15% (close)")
        self.assertAlmostEqual(trade["gross_return_pct"], -16.6667, places=3)

    def test_exit_is_checked_at_close_of_entry_day(self):
        # Signal at day 0, fill at Open day 1. A close below the SMR stop
        # on day 1 must exit immediately, not one session later.
        df = frame([100, 120, 90, 95], [101, 121, 100, 96],
                   [99, 85, 85, 94], [100, 100, 90, 95])
        trades = simulate_reversion_trades(
            df, [event(df, "smr")], "smr",
            bb_upper=np.full(4, 1000.0), atr=[None] * 4,
        )
        self.assertEqual(trades[0]["entry_date"], str(df.index[1].date()))
        self.assertEqual(trades[0]["exit_date"], str(df.index[1].date()))
        self.assertEqual(trades[0]["exit_price"], 100.0)

    def test_open_position_is_reported_not_dropped(self):
        df = frame([100, 100, 101, 102], [101, 102, 103, 104],
                   [99, 99, 100, 101], [100, 101, 102, 103])
        trades = simulate_reversion_trades(
            df, [event(df, "smr")], "smr",
            bb_upper=np.full(4, 1000.0), atr=[None] * 4,
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["status"], "open")
        self.assertIsNone(trades[0]["exit_date"])
        self.assertEqual(trades[0]["mark_price"], 103.0)

    def test_only_supported_systems_are_accepted(self):
        df = frame([100, 100], [101, 101], [99, 99], [100, 100])
        with self.assertRaises(ValueError):
            simulate_reversion_trades(df, [], "core")

    def test_round_trip_cost_is_applied_only_to_closed_trade(self):
        df = frame([100, 100, 100, 100], [101, 102, 103, 106],
                   [99, 99, 100, 104], [100, 101, 102, 106])
        trades = simulate_reversion_trades(
            df, [event(df, "smr")], "smr", cost_bps=10,
            bb_upper=[1000, 1000, 1000, 105], atr=[None] * 4,
        )
        self.assertAlmostEqual(
            trades[0]["net_return_pct"],
            trades[0]["gross_return_pct"] - 0.10, places=4,
        )

    def test_pooled_profit_factor_uses_all_wins_and_losses(self):
        trades = [
            {"status": "closed", "net_return_pct": 10.0},
            {"status": "closed", "net_return_pct": -5.0},
            {"status": "closed", "net_return_pct": 5.0},
        ]
        stats = _pooled_trade_stats(trades)
        self.assertEqual(stats["pooled_closed_trades"], 3)
        self.assertAlmostEqual(stats["pooled_win_rate"], 66.67, places=2)
        self.assertEqual(stats["pooled_profit_factor"], 3.0)

    def test_open_positions_are_separate_from_pooled_profit_factor(self):
        trades = [
            {"status": "closed", "net_return_pct": 4.0},
            {"status": "open", "estimated_net_mark_return_pct": -2.0},
            {"status": "open", "estimated_net_mark_return_pct": 3.0},
        ]
        stats = _pooled_trade_stats(trades)
        self.assertEqual(stats["pooled_closed_trades"], 1)
        self.assertEqual(stats["pooled_open_positions"], 2)
        self.assertEqual(stats["open_negative_positions"], 1)
        self.assertEqual(stats["pooled_profit_factor"], "inf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
