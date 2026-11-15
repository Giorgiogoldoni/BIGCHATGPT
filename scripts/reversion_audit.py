"""Audit operativo indipendente per Mean Reversion e Super Mean Reversion.

Non modifica i segnali BIG, la Top 20 o il benchmark pubblicato. Simula invece
l'esecuzione coerente con il protocollo: segnale alla chiusura t, ingresso
all'Open di t+1, uscite ricalcolate sul prezzo effettivo di ingresso.
"""
import numpy as np
import az_engine as A

SUPPORTED = {"mr", "smr"}


def simulate_reversion_trades(df, events, system_id, cost_bps=10.0,
                              chand_atr=3.0, bb_upper=None, atr=None):
    """Restituisce trade chiusi e posizioni ancora aperte, senza scartare queste ultime.

    MR: uscita alla prima chiusura >= Bollinger superiore oppure alla prima
    chiusura sotto (massimo High dall'ingresso - chand_atr * ATR14).
    SMR: uscita alla prima chiusura >= Bollinger superiore oppure alla prima
    chiusura <= prezzo effettivo di ingresso * (1 - 15%).

    Le uscite sono valutate dalla seduta successiva all'ingresso, coerentemente
    con il fatto che il segnale si forma alla chiusura e l'acquisto avviene
    all'Open della seduta seguente. Gli stop sono close-based, come nel motore
    BIG attuale: un gap non viene riempito artificialmente al livello teorico.
    """
    if system_id not in SUPPORTED:
        raise ValueError("system_id deve essere 'mr' oppure 'smr'")
    if df is None or len(df) < 2:
        return []
    required = {"Open", "High", "Low", "Close"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError("Colonne OHLC mancanti: " + ", ".join(sorted(missing)))

    close = df["Close"].to_numpy(dtype=float)
    opn = df["Open"].to_numpy(dtype=float)
    high = df["High"].to_numpy(dtype=float)
    if bb_upper is None:
        bb_upper = A.bollinger_bands(df["Close"].astype(float))[0].to_numpy(dtype=float)
    else:
        bb_upper = np.asarray(bb_upper, dtype=float)
    if atr is None:
        atr = A.calc_atr_series(high.tolist(), df["Low"].to_numpy(dtype=float).tolist(), close.tolist())
    if len(bb_upper) != len(df) or len(atr) != len(df):
        raise ValueError("bb_upper e atr devono avere la stessa lunghezza di df")

    positions = {str(d.date()): i for i, d in enumerate(df.index)}
    selected = sorted((e for e in events if e[1] == system_id), key=lambda e: e[0])
    next_free = 0
    out = []

    for event in selected:
        signal_date = str(event[0])
        signal_i = positions.get(signal_date)
        if signal_i is None:
            continue
        entry_i = signal_i + 1
        if entry_i >= len(df) or entry_i < next_free:
            continue
        entry = float(opn[entry_i])
        if not np.isfinite(entry) or entry <= 0:
            continue

        peak = float(high[entry_i])
        result = None
        # L'ingresso avviene all'Open di t+1: la chiusura della stessa
        # seduta è già la prima osservazione valida per le regole di uscita.
        for j in range(entry_i, len(df)):
            peak = max(peak, float(high[j]))
            upper = bb_upper[j]
            upper_hit = np.isfinite(upper) and close[j] >= upper

            if system_id == "smr":
                stop_hit = close[j] <= entry * (1.0 + A.SMR_STOP_PCT)
                if stop_hit or upper_hit:
                    reason = "Stop -15% (close)" if stop_hit else "Banda Bollinger sup."
                    result = (j, float(close[j]), reason)
                    break
            else:
                a = atr[j]
                chand_hit = (a is not None and np.isfinite(a)
                             and close[j] < peak - chand_atr * float(a))
                if upper_hit or chand_hit:
                    reason = "Banda Bollinger sup." if upper_hit else "Chandelier %.1f ATR" % chand_atr
                    result = (j, float(close[j]), reason)
                    break

        if result is None:
            mark = float(close[-1])
            gross = (mark / entry - 1.0) * 100.0
            out.append({
                "system": system_id, "status": "open",
                "signal_date": signal_date, "entry_date": str(df.index[entry_i].date()),
                "entry_price": round(entry, 6), "exit_date": None, "exit_price": None,
                "mark_date": str(df.index[-1].date()), "mark_price": round(mark, 6),
                "gross_return_pct": round(gross, 4), "net_return_pct": None,
                "estimated_net_mark_return_pct": round(gross - cost_bps / 100.0, 4),
                "bars": len(df) - entry_i, "reason": "Posizione aperta: mark-to-market",
            })
            next_free = len(df)
            continue

        exit_i, exit_price, reason = result
        gross = (exit_price / entry - 1.0) * 100.0
        net = gross - cost_bps / 100.0
        out.append({
            "system": system_id, "status": "closed",
            "signal_date": signal_date, "entry_date": str(df.index[entry_i].date()),
            "entry_price": round(entry, 6), "exit_date": str(df.index[exit_i].date()),
            "exit_price": round(exit_price, 6), "mark_date": None, "mark_price": None,
            "gross_return_pct": round(gross, 4), "net_return_pct": round(net, 4),
            "estimated_net_mark_return_pct": None,
            "bars": exit_i - entry_i + 1, "reason": reason,
        })
        next_free = exit_i + 1

    return out


def _trade_stats(trades, return_key="net_return_pct"):
    """Metriche su trade chiusi; le posizioni aperte restano riportate a parte."""
    closed = [t for t in trades if t.get("status") == "closed" and t.get(return_key) is not None]
    vals = np.asarray([float(t[return_key]) for t in closed], dtype=float)
    if not len(vals):
        return {"closed": 0, "open": sum(t.get("status") == "open" for t in trades),
                "win_rate": None, "mean_return": None, "median_return": None,
                "profit_factor": None, "max_drawdown": None, "avg_bars": None,
                "compounded_return": None}
    wins, losses = vals[vals > 0], vals[vals < 0]
    eq = np.cumprod(1.0 + vals / 100.0)
    path = np.r_[1.0, eq]
    dd = path / np.maximum.accumulate(path) - 1.0
    return {
        "closed": int(len(vals)),
        "open": int(sum(t.get("status") == "open" for t in trades)),
        "win_rate": round(float(np.mean(vals > 0) * 100), 2),
        "mean_return": round(float(np.mean(vals)), 3),
        "median_return": round(float(np.median(vals)), 3),
        "profit_factor": round(float(wins.sum() / abs(losses.sum())), 3)
            if len(losses) and abs(losses.sum()) > 0 else (None if not len(wins) else "inf"),
        "max_drawdown": round(float(dd.min() * 100), 2),
        "avg_bars": round(float(np.mean([t["bars"] for t in closed if t.get("bars") is not None])), 1)\n            if any(t.get("bars") is not None for t in closed) else None,
        "compounded_return": round(float((np.prod(1.0 + vals / 100.0) - 1.0) * 100), 2),
    }


def audit_ticker(ticker, df, events, meta, cost_bps=10.0):
    """Confronta l'esecuzione storica originale con quella coerente Open(t+1).

    L'originale è letto da meta['tr'] (ingresso Close del segnale). La nuova
    simulazione ricalcola le uscite sul prezzo effettivo Open(t+1), inclusa la
    chiusura della stessa seduta d'ingresso. Le righe restano per ETF/sistema.
    """
    out = []
    original = {}
    for row in meta.get("tr", []):
        if len(row) >= 7 and row[0] in SUPPORTED:
            original.setdefault(row[0], []).append({
                "system": row[0], "status": "open" if row[3] is None else "closed",
                "signal_date": row[1], "entry_date": row[1],
                "entry_price": row[2], "exit_date": row[3], "exit_price": row[4],
                "reason": row[5], "gross_return_pct": row[6],
                "net_return_pct": (float(row[6]) - cost_bps / 100.0) if row[3] is not None else None,
                "bars": None,
            })
    for sid in ("mr", "smr"):
        trades = simulate_reversion_trades(df, events, sid, cost_bps=cost_bps)
        old = original.get(sid, [])
        new_stats = _trade_stats(trades)
        old_stats = _trade_stats(old)
        for t in trades:
            t["ticker"] = ticker
        out.append({
            "ticker": ticker, "system": sid,
            "old_close_entry": old_stats,
            "open_next_day": new_stats,
            "delta_median_return": (
                round(new_stats["median_return"] - old_stats["median_return"], 3)
                if new_stats["median_return"] is not None and old_stats["median_return"] is not None else None
            ),
            "trades": trades,
        })
    return out


def aggregate_audit(rows):
    """Aggrega per ETF con peso uguale; evita che gli ETF con più segnali dominino."""
    result = []
    for sid in ("mr", "smr"):
        items = [r for r in rows if r["system"] == sid]
        for mode in ("old_close_entry", "open_next_day"):
            metrics = [r[mode] for r in items if r[mode]["closed"] > 0]
            def med(key):
                vals = [m[key] for m in metrics if isinstance(m.get(key), (int, float))]
                return round(float(np.median(vals)), 3) if vals else None
            result.append({
                "system": sid, "method": mode, "tickers": len(metrics),
                "closed_trades": sum(m["closed"] for m in metrics),
                "open_positions": sum(m["open"] for m in (r[mode] for r in items)),
                "median_trades_per_etf": med("closed"),
                "median_win_rate": med("win_rate"),
                "median_return_per_etf": med("median_return"),
                "median_mean_return_per_etf": med("mean_return"),
                "median_profit_factor": med("profit_factor"),
                "median_max_drawdown": med("max_drawdown"),
                "median_duration": med("avg_bars"),
            })
    return result
