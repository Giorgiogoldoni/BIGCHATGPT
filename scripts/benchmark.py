"""Benchmark BIG su ETF non a leva e non inversi.
Due misure distinte:
1) qualita' predittiva dei segnali a 20/40/60 sedute vs campione incondizionato non sovrapposto;
2) simulazione operativa delle uscite con trade sequenziali e costi.
Prezzi Close non rettificati: dividendi esclusi. Il benchmark non modifica il Top 20.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import systems as S
import az_engine as A

COST_BPS = 10.0
CHAND_MULTS = (2.0, 2.5, 3.0, 4.0)
TIME_EXITS = (20, 40, 60)
HORIZONS = (20, 40, 60)


def _candidate_events(df):
    c = df["Close"].astype(float)
    h, l = df["High"].astype(float), df["Low"].astype(float)
    ema20 = c.ewm(span=20, adjust=False, min_periods=50).mean()
    ema50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
    adx, _, _ = A.adx(h, l, c)
    flags = (ema20 > ema50) & (adx >= 20) & (l <= ema20) & (c > ema20) & (c.shift(1) <= ema20.shift(1))
    return [(str(df.index[i].date()), "chat_trend_pullback", "Trend Pullback", float(c.iloc[i]), "EMA20>EMA50, ADX>=20, pullback e recupero EMA20")
            for i in np.flatnonzero(flags.fillna(False).to_numpy())]


def _features(df):
    c = df["Close"].astype(float)
    return {
        "atr": A.calc_atr_series(df["High"].tolist(), df["Low"].tolist(), df["Close"].tolist()),
        "ema20": c.ewm(span=20, adjust=False, min_periods=50).mean().to_numpy(),
        "ema50": c.ewm(span=50, adjust=False, min_periods=50).mean().to_numpy(),
    }


def _forward_signal_rows(ticker, df, events):
    """Rendimento da Open t+1 a Close dopo h sedute; confronto con partenze periodiche non sovrapposte."""
    dates = {str(d.date()): i for i, d in enumerate(df.index)}
    opn, close = df["Open"].to_numpy(float), df["Close"].to_numpy(float)
    rows = []
    for sid in [s["id"] for s in S.SYSTEMS] + ["chat_trend_pullback"]:
        selected = sorted({dates[e[0]] for e in events if e[1] == sid and e[0] in dates})
        for h in HORIZONS:
            signal_returns, last_exit = [], -1
            for si in selected:
                entry_i, exit_i = si + 1, si + h
                if exit_i >= len(df) or entry_i <= last_exit:
                    continue
                entry = opn[entry_i]
                if not np.isfinite(entry) or entry <= 0 or not np.isfinite(close[exit_i]):
                    continue
                signal_returns.append(close[exit_i] / entry - 1)
                last_exit = exit_i
            # Baseline: periodic, non-overlapping Open-to-Close windows over the same ETF.
            base = []
            for entry_i in range(1, len(df) - h, h):
                exit_i = entry_i + h - 1
                entry = opn[entry_i]
                if np.isfinite(entry) and entry > 0 and np.isfinite(close[exit_i]):
                    base.append(close[exit_i] / entry - 1)
            if signal_returns and base:
                sr, br = np.asarray(signal_returns), np.asarray(base)
                rows.append({
                    "ticker": ticker, "system": sid, "horizon": h, "signals": len(sr),
                    "win_rate": round(float(np.mean(sr > 0)) * 100, 2),
                    "median_return": round(float(np.median(sr)) * 100, 3),
                    "mean_return": round(float(np.mean(sr)) * 100, 3),
                    "baseline_n": len(br), "baseline_median": round(float(np.median(br)) * 100, 3),
                    "baseline_mean": round(float(np.mean(br)) * 100, 3),
                    "median_edge": round(float((np.median(sr) - np.median(br)) * 100), 3),
                })
    return rows


def _exit_trade(df, entry_i, entry_price, mode, atr, ema20, ema50):
    high, low = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    opn, close = df["Open"].to_numpy(float), df["Close"].to_numpy(float)
    peak = high[entry_i]
    for j in range(entry_i, len(close)):
        peak = max(peak, high[j])
        if mode.startswith("chand_"):
            a = atr[j]
            if a is not None and np.isfinite(a) and close[j] < peak - float(mode.split("_")[1]) * a:
                return j, float(close[j]), "Chandelier %.1f ATR" % float(mode.split("_")[1])
        elif mode == "stop_8" and low[j] <= entry_price * 0.92:
            return j, float(min(opn[j], entry_price * 0.92)), "Stop -8%"
        elif mode == "ema20_50" and j > 0 and np.isfinite(ema20[j]) and np.isfinite(ema50[j]) and ema20[j] < ema50[j]:
            return j, float(close[j]), "EMA20 sotto EMA50"
        elif mode.startswith("time_") and j >= entry_i + int(mode.split("_")[1]) - 1:
            return j, float(close[j]), "Uscita dopo %d sedute" % int(mode.split("_")[1])
    return None


def _one_system(df, events, sid, original_map, modes, cost, features=None):
    dates = {str(d.date()): i for i, d in enumerate(df.index)}
    opn = df["Open"].to_numpy(float)
    f = features or _features(df)
    trades_by_mode = []
    selected = sorted((e for e in events if e[1] == sid), key=lambda e: e[0])
    for mode in modes:
        trades, next_free = [], 0
        for event in selected:
            si = dates.get(str(event[0]))
            if si is None or si + 1 >= len(df):
                continue
            entry_i = si + 1
            if entry_i < next_free:
                continue
            entry = float(opn[entry_i])
            if not np.isfinite(entry) or entry <= 0:
                continue
            if mode == "original":
                original = original_map.get((sid, str(event[0])))
                if not original or not original[0]:
                    continue
                exit_i = dates.get(str(original[0]))
                if exit_i is None or exit_i < entry_i:
                    continue
                exit_price, reason = float(original[1]), "Uscita originale BIG"
            else:
                result = _exit_trade(df, entry_i, entry, mode, f["atr"], f["ema20"], f["ema50"])
                if result is None:
                    continue
                exit_i, exit_price, reason = result
            if exit_i < entry_i or not np.isfinite(exit_price) or exit_price <= 0:
                continue
            gross = exit_price / entry - 1
            net = gross - cost / 10000.0
            trades.append({"in": str(df.index[entry_i].date()), "out": str(df.index[exit_i].date()),
                           "entry_price": round(entry, 6), "exit_price": round(exit_price, 6),
                           "bars": int(exit_i - entry_i + 1), "ret": round(net * 100, 3),
                           "gross": round(gross * 100, 3), "reason": reason})
            next_free = exit_i + 1
        if trades:
            vals = np.asarray([t["ret"] for t in trades], dtype=float)
            wins, losses = vals[vals > 0], vals[vals < 0]
            eq = np.cumprod(1 + vals / 100)
            dd = np.r_[1.0, eq] / np.maximum.accumulate(np.r_[1.0, eq]) - 1
            trades_by_mode.append({"system": sid, "exit": mode, "n": len(trades),
                "win_rate": round(float(np.mean(vals > 0)) * 100, 2),
                "mean": round(float(np.mean(vals)), 3), "median": round(float(np.median(vals)), 3),
                "profit_factor": round(float(wins.sum() / abs(losses.sum())), 3) if len(losses) and abs(losses.sum()) else None,
                "max_drawdown": round(float(dd.min()) * 100, 2),
                "avg_bars": round(float(np.mean([t["bars"] for t in trades])), 1), "trades": trades})
    return trades_by_mode


def ticker_benchmark(ticker, df, events, meta, cost_bps=COST_BPS, instrument=None):
    instrument = instrument or {}
    if instrument.get("lv") or instrument.get("inv") or df is None or len(df) < 80:
        return {"rows": [], "forward": []}
    all_events = list(events) + _candidate_events(df)
    original_map = {(t[0], t[1]): (t[3], t[4]) for t in meta.get("tr", [])}
    modes = ["original"] + ["chand_%.1f" % x for x in CHAND_MULTS] + ["stop_8", "ema20_50"] + ["time_%d" % x for x in TIME_EXITS]
    systems = [s["id"] for s in S.SYSTEMS] + ["chat_trend_pullback"]
    features = _features(df)
    rows = []
    for sid in systems:
        rows.extend(_one_system(df, all_events, sid, original_map, modes if sid != "chat_trend_pullback" else modes[1:], cost_bps, features))
    return {"rows": [{"ticker": ticker, **x} for x in rows],
            "forward": _forward_signal_rows(ticker, df, all_events)}


def aggregate(rows):
    """Aggrega prima per ETF e poi assegna uguale peso a ciascun ETF."""
    grouped = {}
    for r in rows:
        grouped.setdefault((r["system"], r["exit"]), []).append(r)
    out = []
    for (sid, mode), items in grouped.items():
        vals = [x["median"] for x in items]
        pf = [x["profit_factor"] for x in items if x.get("profit_factor") is not None]
        out.append({"system": sid, "exit": mode, "tickers": len(items),
            "trades": sum(x["n"] for x in items),
            "median_ticker_median": round(float(np.median(vals)), 3),
            "median_ticker_win_rate": round(float(np.median([x["win_rate"] for x in items])), 2),
            "median_ticker_pf": round(float(np.median(pf)), 3) if pf else None,
            "median_ticker_drawdown": round(float(np.median([x["max_drawdown"] for x in items])), 2),
            "median_duration": round(float(np.median([x["avg_bars"] for x in items])), 1)})
    return sorted(out, key=lambda x: (x["median_ticker_median"], x["median_ticker_pf"] or 0), reverse=True)


def aggregate_forward(rows):
    grouped = {}
    for r in rows:
        grouped.setdefault((r["system"], r["horizon"]), []).append(r)
    out = []
    for (sid, h), items in grouped.items():
        out.append({"system": sid, "horizon": h, "tickers": len(items),
            "signals": sum(x["signals"] for x in items),
            "median_ticker_return": round(float(np.median([x["median_return"] for x in items])), 3),
            "median_ticker_win_rate": round(float(np.median([x["win_rate"] for x in items])), 2),
            "median_ticker_baseline": round(float(np.median([x["baseline_median"] for x in items])), 3),
            "median_edge": round(float(np.median([x["median_edge"] for x in items])), 3)})
    return sorted(out, key=lambda x: (x["horizon"], x["median_edge"]), reverse=True)


def write(data_dir, rows, forward, generated, period="5y", cost_bps=COST_BPS):
    payload = {"generated": generated, "period": period, "cost_round_trip_bps": cost_bps,
        "universe_filter": "Solo ETF non a leva e non inversi (esclusi lv=true o inv=true).",
        "execution": "Segnale a Close t, ingresso Open t+1; uscita a Close/stop; Close non rettificato, dividendi esclusi.",
        "forward_method": "Rendimenti Open t+1 -> Close dopo 20/40/60 sedute; confronto con partenze periodiche non sovrapposte dello stesso ETF. Mediana per ETF, poi mediana tra ETF.",
        "operational_method": "Trade sequenziali, una posizione per sistema/ETF; costo round-trip 10 bp; metriche aggregate dando uguale peso agli ETF. Non e' un portafoglio multi-ETF.",
        "systems": [s["id"] for s in S.SYSTEMS] + ["chat_trend_pullback"],
        "exit_modes": ["original", "chand_2.0", "chand_2.5", "chand_3.0", "chand_4.0", "stop_8", "ema20_50", "time_20", "time_40", "time_60"],
        "ranking": aggregate(rows), "rows": rows,
        "forward_ranking": aggregate_forward(forward), "forward_rows": forward}
    (Path(data_dir) / "benchmark.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print("benchmark ETF non leva:", len({x["ticker"] for x in rows}), "| trade rows:", len(rows),
          "| forward rows:", len(forward), "| ranking:", len(payload["ranking"]))


if __name__ == "__main__":
    raise SystemExit("Importare benchmark da build.py; non eseguire standalone.")
