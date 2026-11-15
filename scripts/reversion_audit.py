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
    required = {"Open", "High", "Low", "Close"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError("Colonne OHLC mancanti: " + ", ".join(sorted(missing)))
    if df is None or len(df) < 2:
        return []

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
        # Non si valuta l'uscita sulla stessa barra dell'ingresso:
        # il segnale originale viene elaborato a fine seduta t+1.
        for j in range(entry_i + 1, len(df)):
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
