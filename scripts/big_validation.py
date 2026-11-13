"""Confronto fuori campione tra Top20 base e Top20 BIG.
Training: tutte le barre fino a 12 mesi prima dell'ultima data comune.
Test: rendimento totale a +20/+40/+60 barre successive al cutoff.
Nessun dato successivo al cutoff entra nei punteggi.
"""
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

import systems as S
import rank
import score as SC
import big_score as BS


def _metrics(items):
    if not items:
        return {"n": 0, "mean": None, "median": None, "positive_pct": None, "tickers": []}
    values = np.asarray([x["forward_return"] for x in items], dtype=float)
    return {
        "n": len(items),
        "mean": round(float(np.mean(values)), 2),
        "median": round(float(np.median(values)), 2),
        "positive_pct": round(float(np.mean(values > 0) * 100), 1),
        "tickers": [x["t"] for x in items],
    }


def evaluate(universe, data):
    valid_dates = [df.index[-1] for df in data.values() if df is not None and len(df)]
    if not valid_dates:
        return {"error": "Nessun dato disponibile"}
    end_date = max(valid_dates)
    cutoff_target = end_date - pd.DateOffset(years=1)
    rows, skipped = [], 0
    for instrument in universe:
        ticker = instrument["t"]
        df = data.get(ticker)
        if df is None or len(df) < 300:
            skipped += 1
            continue
        train = df.loc[df.index <= cutoff_target]
        if len(train) < SC.MIN_BARS_VALIDATION:
            skipped += 1
            continue
        try:
            events, meta = S.calcola(train)
            base = SC.calculate(instrument, train, events, meta)
            if not base.get("eligible"):
                skipped += 1
                continue
            historical = rank.riga(ticker, train, events)
            enhanced = BS.build(
                {"generated": None, "period": "holdout", "rows": [base]},
                {"righe": [historical]},
            )["rows"][0]
            entry_idx = df.index.get_loc(train.index[-1])
            price_col = "Adj Close" if (
                "Adj Close" in df.columns
                and df["Adj Close"].notna().sum() >= len(df) * 0.8
            ) else "Close"
            prices = df[price_col].astype(float).to_numpy()
            entry = float(prices[entry_idx])
            if not np.isfinite(entry) or entry <= 0:
                skipped += 1
                continue
            for horizon in (20, 40, 60):
                target_idx = entry_idx + horizon
                if target_idx >= len(prices):
                    continue
                forward = (float(prices[target_idx]) / entry - 1.0) * 100
                if not np.isfinite(forward):
                    continue
                rows.append({
                    "t": ticker, "name": instrument.get("n", ticker),
                    "horizon": horizon, "split_date": str(train.index[-1].date()),
                    "test_date": str(df.index[target_idx].date()),
                    "price_basis": price_col,
                    "score_base": base["score%d" % horizon],
                    "score_big": enhanced["score_big%d" % horizon],
                    "forward_return": round(forward, 2),
                })
        except Exception as exc:
            skipped += 1
            print("VALIDAZIONE BIG", ticker, repr(exc)[:120])
    results = {}
    for horizon in (20, 40, 60):
        sample = [x for x in rows if x["horizon"] == horizon]
        base_top = sorted(sample, key=lambda x: x["score_base"], reverse=True)[:20]
        big_top = sorted(sample, key=lambda x: x["score_big"], reverse=True)[:20]
        base_m = _metrics(base_top)
        big_m = _metrics(big_top)
        all_m = _metrics(sample)
        results[str(horizon)] = {
            "base": base_m, "big": big_m, "universe": {
                k: v for k, v in all_m.items() if k != "tickers"
            },
            "delta": {
                "mean": round(big_m["mean"] - base_m["mean"], 2)
                if big_m["mean"] is not None and base_m["mean"] is not None else None,
                "median": round(big_m["median"] - base_m["median"], 2)
                if big_m["median"] is not None and base_m["median"] is not None else None,
                "positive_pct": round(big_m["positive_pct"] - base_m["positive_pct"], 1)
                if big_m["positive_pct"] is not None and base_m["positive_pct"] is not None else None,
            },
            "overlap": len(set(base_m["tickers"]) & set(big_m["tickers"])),
            "top20_base": [
                {"t": x["t"], "score": x["score_base"], "forward_return": x["forward_return"]}
                for x in base_top
            ],
            "top20_big": [
                {"t": x["t"], "score": x["score_big"], "forward_return": x["forward_return"]}
                for x in big_top
            ],
        }
    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "method": "single_temporal_holdout_12_months",
        "training_cutoff_target": str(cutoff_target.date()),
        "last_data_date": str(end_date.date()),
        "horizons": [20, 40, 60],
        "skipped_instruments": skipped,
        "eligible_observations": len(rows),
        "results": results,
        "warning": "Primo test fuori campione su una sola finestra temporale; descrittivo, senza costi, spread o slippage. Non e' ancora una validazione walk-forward multi-finestra.",
    }


def run(universe, data, data_dir):
    payload = evaluate(universe, data)
    path = Path(data_dir) / "validation_big.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    if "results" in payload:
        for h, result in payload["results"].items():
            print("HOLDOUT", h, "base mediana", result["base"]["median"],
                  "BIG mediana", result["big"]["median"],
                  "delta", result["delta"]["median"],
                  "overlap", result["overlap"])
    print("Validazione BIG scritta:", path)


if __name__ == "__main__":
    raise SystemExit("Eseguire da build.py dopo il download dei dati a 5 anni.")
