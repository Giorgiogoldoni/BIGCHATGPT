"""Score tecnico BIGCHATGPT 0-100 per orizzonti 20/40/60 sedute.
Il punteggio misura la qualita' della configurazione corrente; non e' una previsione di rendimento.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import az_engine as A
import core_engine as G

ORIZZONTI = (20, 40, 60)
MIN_BARS_VALIDATION = 230
EXCLUDED_2026 = {
    "ACSW.MI", "ESWP.MI", "EUTA.MI", "IB36.MI", "IB37.MI",
    "VEZU.MI", "WBLD.MI", "WDAF.MI", "WDGF.MI", "WETFE.MI",
}
CRYPTO_TICKERS = {"ASUI.MI", "ATAO.MI", "CANTN.MI", "CBTC.MI", "HDRA.MI", "MORPH.MI", "SYRUP.MI", "WETH.MI"}
FAMILIES = {
    "Trend": {"core", "azb", "sbb", "psar", "adx", "ema"},
    "Momentum": {"mom"},
    "Indicatori": {"cd"},
    "Inversione": {"inv", "mr", "smr"},
    "Breakout": {"k5"},
}
FAMILY_POINTS = {"Trend": 6, "Momentum": 3, "Indicatori": 3, "Inversione": 3, "Breakout": 3}


def _rsi_points(value):
    if 50 <= value <= 68: return 5
    if 45 <= value < 50 or 68 < value <= 72: return 3
    if 40 <= value < 45 or 72 < value <= 75: return 1
    return 0


def _momentum_points(roc_pct, atr_pct, horizon, weight):
    """Punti continui per momentum corretto per la volatilita' dell'ETF."""
    if atr_pct <= 0 or not np.isfinite(atr_pct):
        return 0.0
    vol = atr_pct * np.sqrt(horizon)
    z = roc_pct / vol if vol > 0 else 0.0
    return float(weight * min(1.0, max(0.0, (z + 1.0) / 3.0)))


def _risk_points(atr_pct, drawdown_pct):
    if 0.3 <= atr_pct <= 2.5: atr_pts = 5
    elif 0.15 <= atr_pct < 0.3 or 2.5 < atr_pct <= 3.5: atr_pts = 4
    elif atr_pct <= 5: atr_pts = 2
    else: atr_pts = 0
    if drawdown_pct >= -3: dd_pts = 5
    elif drawdown_pct >= -6: dd_pts = 4
    elif drawdown_pct >= -10: dd_pts = 2
    else: dd_pts = 0
    return atr_pts + dd_pts


def _liquidity_points(df):
    if "Volume" not in df.columns:
        return 2.5, None
    turnover = (df["Close"].astype(float) * df["Volume"].fillna(0).astype(float)).tail(20)
    turnover = turnover[turnover > 0]
    if turnover.empty:
        return 0.0, 0.0
    med = float(turnover.median())
    pts = 5 if med >= 1_000_000 else 4 if med >= 250_000 else 3 if med >= 100_000 else 2 if med >= 25_000 else 1
    return float(pts), med


def _historical_edge(df, events, horizon):
    close = df["Close"].astype(float).to_numpy()
    if "Adj Close" in df.columns and df["Adj Close"].notna().sum() >= len(df) * 0.8:
        adj = df["Adj Close"].astype(float).fillna(df["Close"].astype(float)).to_numpy()
        total_return = True
    else:
        adj = close.copy()
        total_return = False
    n = len(close)
    if n <= horizon + 5:
        return {"n": 0, "excess": None, "hit": None, "points": 0.0, "total_return": total_return}
    base = adj[horizon:] / adj[:-horizon] - 1
    base_median = float(np.median(base)) if len(base) else 0.0
    pos = {str(d.date()): i for i, d in enumerate(df.index)}
    same_day = {}
    for event in events:
        date, _, _, price, _ = event
        i = pos.get(str(date))
        if i is None or i + horizon >= n or price <= 0 or close[i] <= 0:
            continue
        # Porta il prezzo grezzo del segnale sulla stessa scala adjusted del rendimento.
        adj_entry = float(price) * (adj[i] / close[i])
        if adj_entry > 0:
            same_day.setdefault(i, []).append(adj[i + horizon] / adj_entry - 1)
    samples = [(i, float(np.median(vals))) for i, vals in sorted(same_day.items())]
    non_overlap, last = [], -10**9
    for i, ret in samples:
        if i - last >= horizon:
            non_overlap.append((i, ret)); last = i
    if len(non_overlap) < 3:
        return {"n": len(non_overlap), "excess": None, "hit": None, "points": 0.0,
                "total_return": total_return, "baseline_median": base_median * 100}
    vals = np.array([x[1] for x in non_overlap], dtype=float)
    median = float(np.median(vals)); hit = float(np.mean(vals > 0))
    excess = median - base_median
    points = 0.0
    if excess > 0:
        hit_factor = min(1.0, max(0.0, (hit - 0.40) / 0.40))
        sample_factor = min(1.0, len(non_overlap) / 8.0)
        points = 5.0 * hit_factor * sample_factor
    return {"n": len(non_overlap), "median": median * 100, "baseline_median": base_median * 100,
            "excess": excess * 100, "hit": hit * 100, "points": points, "total_return": total_return}


def calculate(instrument, df, events, meta):
    """Ritorna una riga score. df deve avere OHLCV e indice DatetimeIndex."""
    ticker = instrument["t"]
    if df is None or len(df) < 65:
        return {"t": ticker, "name": instrument.get("n", ticker), "status": "dati_insufficienti", "eligible": False}
    d = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    o, h, l, c = (d[k].astype(float).to_numpy() for k in ("Open", "High", "Low", "Close"))
    n = len(c); last = n - 1
    if n < 65:
        return {"t": ticker, "name": instrument.get("n", ticker), "status": "dati_insufficienti", "eligible": False}

    kama = np.asarray(G.calc_kama(c.tolist()), dtype=float)
    sar, _, _ = A.parabolic_sar(d["High"], d["Low"], d["Close"])
    adx, plus_di, minus_di = A.adx(d["High"], d["Low"], d["Close"])
    rsi = A.rsi(d["Close"], 14)
    ema20 = d["Close"].ewm(span=20, adjust=False, min_periods=20).mean().to_numpy()
    ema50 = d["Close"].ewm(span=50, adjust=False, min_periods=50).mean().to_numpy()
    atr = A.calc_atr_series(h.tolist(), l.tolist(), c.tolist(), 14)
    atr_last = atr[-1] if atr else None
    if atr_last is None or not np.isfinite(atr_last): atr_pct = 0.0
    else: atr_pct = float(atr_last / c[last] * 100)
    dd20 = float((c[last] / np.max(c[max(0, n - 20):]) - 1) * 100)

    trend = 0
    trend += 5 * int(np.isfinite(kama[last]) and c[last] > kama[last])
    trend += 5 * int(last >= 5 and np.isfinite(kama[last]) and np.isfinite(kama[last - 5]) and kama[last] > kama[last - 5])
    trend += 5 * int(np.isfinite(ema20[last]) and np.isfinite(ema50[last]) and ema20[last] > ema50[last])
    trend += 5 * int(np.isfinite(ema20[last]) and c[last] > ema20[last])
    trend += 5 * int(c[last] > float(sar.iloc[-1]))
    adx_last = float(adx.iloc[-1]) if np.isfinite(adx.iloc[-1]) else 0.0
    pdi_last = float(plus_di.iloc[-1]) if np.isfinite(plus_di.iloc[-1]) else 0.0
    mdi_last = float(minus_di.iloc[-1]) if np.isfinite(minus_di.iloc[-1]) else 0.0
    strength = 10 * int(adx_last >= 20 and pdi_last > mdi_last)
    strength += 5 * int(len(adx) >= 4 and adx.iloc[-1] > adx.iloc[-4])
    rsi_last = float(rsi.iloc[-1]) if np.isfinite(rsi.iloc[-1]) else 50.0
    rsi_pts = _rsi_points(rsi_last)

    pos = {str(date.date()): i for i, date in enumerate(d.index)}
    signal_points = 0.0; signal_ages = {}
    for family, ids in FAMILIES.items():
        ages = [n - 1 - pos[str(e[0])] for e in events if e[1] in ids and str(e[0]) in pos]
        age = min(ages) if ages else None
        pts = FAMILY_POINTS[family] * (1.0 if age is not None and age <= 5 else 0.5 if age is not None and age <= 10 else 0.0)
        signal_points += pts
        if age is not None and age <= 10: signal_ages[family] = age
    core_bonus = 2.0 if meta.get("nuovo") and str(meta.get("core") or "").startswith("BUY") else 0.0
    signal_points += core_bonus

    momentum = {h: float((c[last] / c[last - h] - 1) * 100) if n > h else 0.0 for h in ORIZZONTI}
    risk = _risk_points(atr_pct, dd20)
    liquidity, turnover20 = _liquidity_points(d)
    edge = {h: _historical_edge(d, events, h) for h in ORIZZONTI}

    scores = {}
    for horizon in ORIZZONTI:
        others = [h for h in ORIZZONTI if h != horizon]
        momentum_points = (
            _momentum_points(momentum[horizon], atr_pct, horizon, 7)
            + _momentum_points(momentum[others[0]], atr_pct, others[0], 4)
            + _momentum_points(momentum[others[1]], atr_pct, others[1], 4)
            + rsi_pts
        )
        scores[horizon] = round(trend + strength + signal_points + risk + liquidity + momentum_points + edge[horizon]["points"], 1)
    overall = round(sum(scores.values()) / len(scores), 1)

    status = "ok"
    if instrument.get("ac") == "crypto" or ticker in CRYPTO_TICKERS:
        status = "escluso_cripto"
    elif ticker in EXCLUDED_2026:
        status = "escluso_emissione_2026"
    elif instrument.get("tp") != "ETF":
        status = "non_etf"
    elif instrument.get("lv") or instrument.get("inv"):
        status = "leva_o_inverso"
    elif n < MIN_BARS_VALIDATION:
        status = "storico_insufficiente"
    eligible = status == "ok"
    counts = [edge[h]["n"] for h in ORIZZONTI]
    confidence = "alta" if n >= 450 and min(counts) >= 5 else "media" if n >= MIN_BARS_VALIDATION and sum(v >= 3 for v in counts) >= 2 else "bassa"
    return {
        "t": ticker, "name": instrument.get("n", ticker), "isin": instrument.get("i"),
        "issuer": instrument.get("e"), "type": instrument.get("tp"), "asset_class": instrument.get("ac"),
        "price": round(float(c[last]), 4), "date": str(d.index[-1].date()), "bars": n,
        "score20": scores[20], "score40": scores[40], "score60": scores[60], "score": overall,
        "trend": trend, "strength": strength, "signals": round(signal_points, 1), "risk": risk,
        "liquidity": liquidity, "turnover20": round(turnover20, 0) if turnover20 is not None else None,
        "roc20": round(momentum[20], 2), "roc40": round(momentum[40], 2), "roc60": round(momentum[60], 2),
        "rsi14": round(rsi_last, 1), "adx14": round(adx_last, 1), "atr_pct": round(atr_pct, 2),
        "signal_ages": signal_ages, "edge": {str(h): edge[h] for h in ORIZZONTI},
        "confidence": confidence, "status": status, "eligible": eligible,
    }


def write(data_dir, rows, generated):
    rows = sorted(rows, key=lambda x: x.get("score", -1), reverse=True)
    payload = {
        "generated": generated, "horizons": list(ORIZZONTI),
        "min_bars_validation": MIN_BARS_VALIDATION,
        "weights": {"trend": 25, "momentum": 20, "strength": 15, "signals": 20, "risk": 10, "historical_edge": 5, "liquidity": 5},
        "rows": rows,
    }
    (Path(data_dir) / "score.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    eligible = sum(1 for x in rows if x.get("eligible"))
    print("score:", len(rows), "strumenti calcolati |", eligible, "ammessi alla Top20")
