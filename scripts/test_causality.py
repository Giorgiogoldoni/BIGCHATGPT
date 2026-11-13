"""Test di causalita' dei 12 sistemi BIG: i segnali passati non devono cambiare
quando si aggiungono barre future. Eseguibile con: python -m unittest test_causality.py
"""
import unittest
import numpy as np
import pandas as pd

import systems as S
import core_engine as G


def serie_sintetica(n=1200, seed=20261113):
    """OHLCV deterministico, con trend, fasi laterali e shock di volatilita'."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-02", periods=n)
    regime = np.sin(np.arange(n) / 85.0) * 0.0007
    shocks = rng.normal(0.00015 + regime, 0.018, n)
    # Alcuni shock negativi/positivi controllati per stimolare i sistemi.
    shocks[180] -= 0.16
    shocks[181] += 0.09
    shocks[420] -= 0.12
    shocks[421] += 0.08
    shocks[760] += 0.13
    close = 100.0 * np.exp(np.cumsum(shocks))
    prev = np.r_[close[0], close[:-1]]
    open_ = prev * (1 + rng.normal(0, 0.004, n))
    spread_hi = rng.uniform(0.001, 0.025, n)
    spread_lo = rng.uniform(0.001, 0.025, n)
    high = np.maximum(open_, close) * (1 + spread_hi)
    low = np.minimum(open_, close) * (1 - spread_lo)
    volume = rng.integers(100_000, 2_000_000, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


class CausalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = serie_sintetica()

    def test_past_entries_do_not_change_when_future_bars_are_added(self):
        full_events, _ = S.calcola(self.df)
        cutoffs = (250, 400, 600, 800, 1000)
        for end in cutoffs:
            prefix = self.df.iloc[:end]
            prefix_events, _ = S.calcola(prefix)
            last_date = str(prefix.index[-1].date())

            expected = [
                (e[0], e[1], round(float(e[3]), 4))
                for e in full_events if e[0] <= last_date
            ]
            observed = [
                (e[0], e[1], round(float(e[3]), 4))
                for e in prefix_events
            ]
            self.assertEqual(
                observed, expected,
                msg=("Segnali storici modificati aggiungendo barre future "
                     f"(prefisso fino a {last_date})."),
            )

    def test_past_exits_do_not_change_when_future_bars_are_added(self):
        _, full_meta = S.calcola(self.df)
        cutoffs = (250, 400, 600, 800, 1000)
        for end in cutoffs:
            prefix = self.df.iloc[:end]
            _, prefix_meta = S.calcola(prefix)
            last_date = str(prefix.index[-1].date())

            def closed_by_cutoff(meta):
                return sorted(
                    (t[0], t[1], round(float(t[2]), 4), t[3],
                     round(float(t[4]), 4), t[5])
                    for t in meta["tr"]
                    if t[3] is not None and t[3] <= last_date
                )

            self.assertEqual(
                closed_by_cutoff(prefix_meta), closed_by_cutoff(full_meta),
                msg=("Uscite storiche modificate aggiungendo barre future "
                     f"(prefisso fino a {last_date})."),
            )

    def test_core_can_emit_buy2_and_buy3(self):
        # BUY3 soddisfa anche le condizioni di BUY2: deve quindi avere priorita'.
        result = G.calc_segnale_array(
            close=[110.0, 110.0],
            kama=[100.0, 100.0],
            er_arr=[0.80, 0.20],
            baff_arr=[4, 2],
            ao_imp_arr=[False, False],
            sar_bull_arr=[True, True],
            cross_arr=[10, 10],
            mm_arr=[True, False],
            rsi_arr=[50, 50],
        )
        self.assertEqual(result, ["BUY3", "BUY2"])

    def test_all_twelve_systems_are_registered(self):
        ids = [s["id"] for s in S.SYSTEMS]
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
