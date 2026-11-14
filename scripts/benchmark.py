"""Benchmark operativo dei 12 sistemi BIG + candidato Trend Pullback.
Esecuzione causale: segnale a chiusura t, ingresso all'Open di t+1.
Prezzi Close non rettificati (nessun dividendo); costi/slippage configurabili.
Il benchmark non modifica il motore segnali né il Top 20.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import systems as S
import az_engine as A

COST_BPS = 10.0  # costo round-trip totale ipotetico: 10 bp, modificabile
CHAND_MULTS = (2.0, 2.5, 3.0, 4.0)
TIME_EXITS = (20, 40, 60)


def _candidate_events(df):
    c = df["Close"].astype(float)
    h, l = df["High"].astype(float), df["Low"].astype(float)
    ema20 = c.ewm(span=20, adjust=False, min_periods=50).mean()
    ema50 = c.ewm(span=50, adjust=False, min_periods=50).mean()
    # ADX Wilder, coerente con il DMI gia' usato in BIG.
    adx, pdi, mdi = A.adx(h, l, c)
    touch_reclaim = (l <= ema20) & (c > ema20) & (c.shift(1) <= ema20.shift(1))
    flags = (ema20 > ema50) & (adx >= 20) & touch_reclaim
    out = []
    for i in np.flatnonzero(flags.fillna(False).to_numpy()):
        out.append((str(df.index[i].date()), "chat_trend_pullback", "Trend Pullback", float(c.iloc[i]), "EMA20>EMA50, ADX>=20, pullback e recupero EMA20"))
    return out


def _exit_trade(df, entry_i, entry_price, mode, atr, ema20, ema50):
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    opn = df["Open"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    n = len(close)
    peak = high[entry_i]
    for j in range(entry_i, n):
        peak = max(peak, high[j])
        if mode.startswith("chand_"):
            mult = float(mode.split("_")[1])
            a = atr[j]
            if a is not None and np.isfinite(a):
                stop = peak - mult * a
                if close[j] < stop:
                    return j, float(close[j]), "Chandelier %.1f ATR" % mult
        elif mode == "stop_8":
            stop = entry_price * 0.92
            if low[j] <= stop:
                return j, float(min(opn[j], stop)), "Stop -8%"
        elif mode == "ema20_50":
            if j > 0 and np.isfinite(ema20[j]) and np.isfinite(ema50[j]) and ema20[j] < ema50[j]:
                return j, float(close[j]), "EMA20 sotto EMA50"
        elif mode.startswith("time_"):
            bars = int(mode.split("_")[1])
            if j >= entry_i + bars - 1:
                return j, float(close[j]), "Uscita dopo %d sedute" % bars
    return None


def _one_system(df, events, sid, original_map, modes, cost):
    dates = {str(d.date()): i for i, d in enumerate(df.index)}
    close = df["Close"].to_numpy(float)
    opn = df["Open"].to_numpy(float)
    atr = A.calc_atr_series(df["High"].tolist(), df["Low"].tolist(), df["Close"].tolist())
    c = df["Close"].astype(float)
    ema20 = c.ewm(span=20, adjust=False, min_periods=50).mean().to_numpy()
    ema50 = c.ewm(span=50, adjust=False, min_periods=50).mean().to_numpy()
    selected = sorted((e for e in events if e[1] == sid), key=lambda e: e[0])
    results = []
    for mode in modes:
        trades = []
        next_free = 0
        for event in selected:
            signal_i = dates.get(str(event[0]))
            if signal_i is None or signal_i + 1 >= len(df):
                continue
            entry_i = signal_i + 1  # no look-ahead: si compra all'apertura successiva
            if entry_i < next_free:
                continue
            entry = float(opn[entry_i])
            if not np.isfinite(entry) or entry <= 0:
                continue
            if mode == "original":
                original = original_map.get((sid, str(event[0])))
                if not original or not original[0]:
                    continue  # le posizioni ancora aperte non entrano nel confronto chiuso
                exit_i = dates.get(str(original[0]))
                if exit_i is None or exit_i < entry_i:
                    continue
                exit_price = float(original[1])
                reason = "Uscita originale BIG"
            else:
                result = _exit_trade(df, entry_i, entry, mode, atr, ema20, ema50)
                if result is None:
                    continue
                exit_i, exit_price, reason = result
            if exit_i < entry_i or exit_price <= 0:
                continue
            gross = exit_price / entry - 1
            net = gross - cost / 10000.0
            hold = close[exit_i] / entry - 1
            trades.append({
                "in": str(df.index[entry_i].date()), "out": str(df.index[exit_i].date()),
                "entry_price": round(entry, 6), "exit_price": round(exit_price, 6),
                "bars": int(exit_i - entry_i + 1), "ret": round(net * 100, 3),
                "gross": round(gross * 100, 3), "benchmark": round(hold * 100, 3),
                "excess": round((net - hold) * 100, 3), "reason": reason,
            })
            next_free = exit_i + 1
        if trades:
            vals = np.array([x["ret"] for x in trades], dtype=float)
            wins = vals[vals > 0]
            losses = vals[vals < 0]
            eq = np.cumprod(1 + vals / 100)
            peaks = np.maximum.accumulate(np.r_[1.0, eq])
            dd = np.r_[1.0, eq] / peaks - 1
            results.append({
                "system": sid, "exit": mode, "n": len(trades),
                "win_rate": round(float(np.mean(vals > 0)) * 100, 1),
                "mean": round(float(np.mean(vals)), 3),
                "median": round(float(np.median(vals)), 3),
                "mean_excess": round(float(np.mean([x["excess"] for x in trades])), 3),
                "profit_factor": round(float(wins.sum() / abs(losses.sum())), 3) if len(losses) and abs(losses.sum()) > 0 else None,
                "max_drawdown": round(float(dd.min()) * 100, 2),
                "avg_bars": round(float(np.mean([x["bars"] for x in trades])), 1),
                "trades": trades,
            })
    return results


def ticker_benchmark(ticker, df, events, meta, cost_bps=COST_BPS):
    if df is None or len(df) < 80:
        return []
    all_events = list(events) + _candidate_events(df)
    original_map = {}
    for t in meta.get("tr", []):
        # [system, date_in, price_in, date_out, price_out, reason, return]
        original_map[(t[0], t[1])] = (t[3], t[4])
    modes = ["original"] + ["chand_%.1f" % x for x in CHAND_MULTS] + ["stop_8", "ema20_50"] + ["time_%d" % x for x in TIME_EXITS]
    system_ids = [s["id"] for s in S.SYSTEMS] + ["chat_trend_pullback"]
    out = []
    for sid in system_ids:
        out.extend(_one_system(df, all_events, sid, original_map, modes if sid != "chat_trend_pullback" else modes[1:], cost_bps))
    return [{"ticker": ticker, **x} for x in out]


def aggregate(rows):
    grouped = {}
    for r in rows:
        grouped.setdefault((r["system"], r["exit"]), []).append(r)
    out = []
    for (sid, mode), items in grouped.items():
        trades = [t for x in items for t in x["trades"]]
        if not trades:
            continue
        vals = np.array([t["ret"] for t in trades], dtype=float)
        wins, losses = vals[vals > 0], vals[vals < 0]
        out.append({
            "system": sid, "exit": mode, "tickers": len(items), "trades": len(trades),
            "win_rate": round(float(np.mean(vals > 0)) * 100, 1),
            "mean": round(float(np.mean(vals)), 3), "median": round(float(np.median(vals)), 3),
            "mean_excess": round(float(np.mean([t["excess"] for t in trades])), 3),
            "profit_factor": round(float(wins.sum() / abs(losses.sum())), 3) if len(losses) and abs(losses.sum()) > 0 else None,
            "avg_bars": round(float(np.mean([t["bars"] for t in trades])), 1),
        })
    return sorted(out, key=lambda x: (x["mean_excess"], x["profit_factor"] or 0, x["trades"]), reverse=True)


def write(data_dir, rows, generated, period="5y", cost_bps=COST_BPS):
    payload = {
        "generated": generated, "period": period, "cost_round_trip_bps": cost_bps,
        "execution": "segnale a close t, ingresso Open t+1; uscite a close/stop; Close non rettificato, dividendi esclusi",
        "systems": [s["id"] for s in S.SYSTEMS] + ["chat_trend_pullback"],
        "exit_modes": ["original", "chand_2.0", "chand_2.5", "chand_3.0", "chand_4.0", "stop_8", "ema20_50", "time_20", "time_40", "time_60"],
        "ranking": aggregate(rows), "rows": rows,
    }
    (Path(data_dir) / "benchmark.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print("benchmark:", len(rows), "combinazioni ticker/sistema/uscita |", len(payload["ranking"]), "righe aggregate")


if __name__ == "__main__":
    raise SystemExit("Importare benchmark da build.py; non eseguire standalone.")
