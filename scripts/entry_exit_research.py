"""Ricerca indipendente di ingressi, uscite e combinazioni.

Modulo sperimentale separato dal motore di produzione. Segnali a Close t,
ingresso a Open t+1. Le coorti operative sono selezionate una volta per
sistema con distanza minima fissa (60 barre), uguale per tutte le uscite.
"""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
import pandas as pd

HORIZONS = (5, 10, 20, 40, 60)
COST_BPS = 10.0
MIN_SIGNALS = 5
MIN_TOTAL_SIGNALS = 30
MAX_HOLD_BARS = 60
EXIT_MODES = ("chand_2.0", "chand_2.5", "chand_3.0", "chand_4.0", "stop_8", "ema20_50",
              "bb_upper", "target_10", "time_20", "time_40", "time_60")


def _features(df):
    h, l, c = (df[k].astype(float) for k in ("High", "Low", "Close"))
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean().to_numpy()
    mid = c.rolling(20, min_periods=20).mean()
    sd = c.rolling(20, min_periods=20).std(ddof=0)
    upper = (mid + 2*sd).to_numpy()
    ema20 = c.ewm(span=20, adjust=False, min_periods=20).mean().to_numpy()
    ema50 = c.ewm(span=50, adjust=False, min_periods=50).mean().to_numpy()
    return {"atr": atr, "upper": upper, "ema20": ema20, "ema50": ema50}


def _event_indices(df, events, system_id):
    pos = {str(d.date()): i for i, d in enumerate(df.index)}
    return sorted({pos[str(e[0])] for e in events
                   if len(e) >= 2 and e[1] == system_id and str(e[0]) in pos})


def _fixed_cohort(signal_indices, n, spacing=60):
    """Coorte indipendente dalle uscite: massimo un ingresso ogni spacing barre."""
    selected, last_entry = [], -10**9
    for si in signal_indices:
        entry_i = si + 1
        if entry_i < n and entry_i - last_entry >= spacing:
            selected.append(si)
            last_entry = entry_i
    return selected


def _forward_stats(df, signal_indices, horizon, cost_bps=COST_BPS):
    opn = df["Open"].to_numpy(float)
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    n = len(df)
    returns, maes, mfes, years = [], [], [], []
    for si in signal_indices:
        ei, xi = si + 1, si + horizon
        if xi >= n or not np.isfinite(opn[ei]) or opn[ei] <= 0:
            continue
        window_h, window_l = high[ei:xi+1], low[ei:xi+1]
        if not len(window_h) or not np.isfinite(close[xi]):
            continue
        entry = opn[ei]
        returns.append((close[xi] / entry - 1) * 100 - cost_bps / 100)
        maes.append((np.nanmin(window_l) / entry - 1) * 100)
        mfes.append((np.nanmax(window_h) / entry - 1) * 100)
        years.append(int(df.index[si].year))
    if not returns:
        return None
    vals = np.asarray(returns)
    baseline = []
    for entry_i in range(1, max(1, n-horizon), horizon):
        exit_i = entry_i + horizon - 1
        if exit_i < n and np.isfinite(opn[entry_i]) and opn[entry_i] > 0 and np.isfinite(close[exit_i]):
            baseline.append((close[exit_i]/opn[entry_i]-1)*100-cost_bps/100)
    baseline_median = float(np.median(baseline)) if baseline else None
    return {
        "n": len(vals), "baseline_n": len(baseline),
        "baseline_median": round(baseline_median, 3) if baseline_median is not None else None,
        "median_edge": round(float(np.median(vals))-baseline_median, 3) if baseline_median is not None else None,
        "win_rate": round(float(np.mean(vals > 0))*100, 2),
        "mean": round(float(np.mean(vals)), 3),
        "median": round(float(np.median(vals)), 3),
        "std": round(float(np.std(vals, ddof=1)), 3) if len(vals) > 1 else None,
        "mae_median": round(float(np.median(maes)), 3),
        "mfe_median": round(float(np.median(mfes)), 3),
        "yearly": [{"year": y, "n": int(sum(z == y for z in years)),
                    "median": round(float(np.median([v for v, yy in zip(vals, years) if yy == y])), 3)}
                   for y in sorted(set(years))]
    }


def _exit_one(df, entry_i, entry, mode, f):
    opn = df["Open"].to_numpy(float)
    high = df["High"].to_numpy(float)
    low = df["Low"].to_numpy(float)
    close = df["Close"].to_numpy(float)
    peak = entry  # massimo noto prima della barra corrente: evita look-ahead intraday
    n = len(df)
    for j in range(entry_i, n):
        if mode in ("stop_8",) or mode.startswith("chand_"):
            # Il trailing stop usa ATR e massimo disponibili alla chiusura precedente.
            prior_atr = f["atr"][j-1] if j > 0 else np.nan
            level = entry * .92 if mode == "stop_8" else peak - float(mode.split("_")[1]) * prior_atr
            if np.isfinite(level) and low[j] <= level:
                px = min(opn[j], level) if opn[j] > 0 else level
                return j, float(px), "intraday_stop_gap_aware"
        close_hit = False
        if mode == "ema20_50":
            close_hit = j > 0 and np.isfinite(f["ema20"][j]) and np.isfinite(f["ema50"][j]) and f["ema20"][j] < f["ema50"][j]
        elif mode == "bb_upper":
            close_hit = np.isfinite(f["upper"][j]) and close[j] >= f["upper"][j]
        elif mode == "target_10":
            close_hit = close[j] >= entry * 1.10
        elif mode.startswith("time_"):
            close_hit = j >= entry_i + int(mode.split("_")[1]) - 1
        if close_hit:
            # Segnale calcolato alla chiusura j: esecuzione non prima dell'Open j+1.
            if j + 1 < n and np.isfinite(opn[j+1]) and opn[j+1] > 0:
                return j+1, float(opn[j+1]), "close_signal_next_open"
            return None
        if j >= entry_i + MAX_HOLD_BARS - 1:
            if j + 1 < n and np.isfinite(opn[j+1]) and opn[j+1] > 0:
                return j+1, float(opn[j+1]), "max_hold_60_next_open"
            return None
        peak = max(peak, high[j])  # il massimo della barra diventa noto solo a fine seduta
    return None


def _trade_stats(trades):
    if not trades:
        return {"n": 0, "win_rate": None, "mean": None, "median": None,
                "profit_factor": None, "max_trade_sequence_dd": None, "avg_bars": None}
    vals = np.asarray([t["net_return"] for t in trades], dtype=float)
    wins, losses = vals[vals > 0], vals[vals < 0]
    eq = np.cumprod(1 + vals/100)
    path = np.r_[1.0, eq]
    dd = path / np.maximum.accumulate(path) - 1
    return {
        "n": len(vals), "win_rate": round(float(np.mean(vals > 0))*100, 2),
        "mean": round(float(np.mean(vals)), 3),
        "median": round(float(np.median(vals)), 3),
        "profit_factor": round(float(wins.sum()/abs(losses.sum())), 3) if len(losses) and abs(losses.sum()) else ("inf" if len(wins) else None),
        "max_trade_sequence_dd": round(float(dd.min())*100, 2),
        "avg_bars": round(float(np.mean([t["bars"] for t in trades])), 1)
    }


def analyze_ticker(ticker, df, events, system_ids, cost_bps=COST_BPS):
    """Ritorna entry, exit e matrix rows per un ETF; esclude prezzi rettificati."""
    if df is None or len(df) < 100 or not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return {"entry": [], "exit": [], "matrix": []}
    df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    f = _features(df)
    entry_rows, exit_rows, matrix_rows = [], [], []
    for sid in system_ids:
        raw = _event_indices(df, events, sid)
        cohort = _fixed_cohort(raw, len(df), 60)
        for horizon in HORIZONS:
            stats = _forward_stats(df, cohort, horizon, cost_bps)
            if stats:
                splits = {}
                n_bars = len(df)
                for label, lo, hi in (("train", 0, int(n_bars*.60)),
                                      ("validation", int(n_bars*.60), int(n_bars*.80)),
                                      ("test", int(n_bars*.80), n_bars)):
                    part = [si for si in cohort if lo <= si < hi]
                    part_stats = _forward_stats(df, part, horizon, cost_bps)
                    if part_stats:
                        splits[label] = {k: part_stats[k] for k in ("n", "mean", "median")}
                stats["splits"] = splits
                entry_rows.append({"ticker": ticker, "system": sid, "horizon": horizon, **stats})
        for mode in EXIT_MODES:
            trades = []
            open_marks = []
            for si in cohort:
                ei = si + 1
                entry = float(df["Open"].iloc[ei])
                if not np.isfinite(entry) or entry <= 0:
                    continue
                result = _exit_one(df, ei, entry, mode, f)
                if result is None:
                    mark = float(df["Close"].iloc[-1])
                    open_marks.append((mark/entry-1)*100-cost_bps/100)
                    continue
                xi, px, reason = result
                gross = (px/entry - 1)*100
                trades.append({
                    "signal_date": str(df.index[si].date()),
                    "entry_date": str(df.index[ei].date()),
                    "exit_date": str(df.index[xi].date()),
                    "entry_price": round(entry, 6), "exit_price": round(px, 6),
                    "bars": int(xi-ei+1), "gross_return": round(gross, 4),
                    "net_return": round(gross-cost_bps/100, 4), "reason": reason
                })
            stats = _trade_stats(trades)
            if stats:
                pos = {str(d.date()): i for i, d in enumerate(df.index)}
                splits = {}
                n_bars = len(df)
                for label, lo, hi in (("train", 0, int(n_bars*.60)),
                                      ("validation", int(n_bars*.60), int(n_bars*.80)),
                                      ("test", int(n_bars*.80), n_bars)):
                    part = [t for t in trades if lo <= pos.get(t["signal_date"], -1) < hi]
                    part_stats = _trade_stats(part)
                    if part_stats and part_stats["n"]:
                        splits[label] = {k: part_stats[k] for k in ("n", "mean", "median", "profit_factor")}
                stats["splits"] = splits
                stats["open_marked"] = len(open_marks)
                stats["open_mark_median"] = round(float(np.median(open_marks)), 3) if open_marks else None
                exit_rows.append({"ticker": ticker, "entry_system": sid, "exit": mode, **stats,
                                  "cohort_signals": len(cohort)})
                matrix_rows.append({"ticker": ticker, "entry": sid, "exit": mode, **stats})
    return {"entry": entry_rows, "exit": exit_rows, "matrix": matrix_rows}


def _rank_entries(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[(r["system"], r["horizon"])].append(r)
    out = []
    for (sid, h), items in groups.items():
        medians = [x["median"] for x in items]
        edges = [x["median"] - 0.0 for x in items]
        total_n = sum(x["n"] for x in items)
        out.append({"system": sid, "horizon": h, "tickers": len(items),
                    "signals": total_n, "median_ticker_return": round(float(np.median(medians)), 3),
                    "median_train_return": round(float(np.median([x["splits"]["train"]["median"] for x in items if "train" in x.get("splits", {})])), 3) if any("train" in x.get("splits", {}) for x in items) else None,
                    "median_test_return": round(float(np.median([x["splits"]["test"]["median"] for x in items if "test" in x.get("splits", {})])), 3) if any("test" in x.get("splits", {}) for x in items) else None,
                    "median_ticker_edge": round(float(np.median([x["median_edge"] for x in items if x.get("median_edge") is not None])), 3) if any(x.get("median_edge") is not None for x in items) else None,
                    "median_ticker_win_rate": round(float(np.median([x["win_rate"] for x in items])), 2),
                    "median_mae": round(float(np.median([x["mae_median"] for x in items])), 3),
                    "median_mfe": round(float(np.median([x["mfe_median"] for x in items])), 3),
                    "eligible": len(items) >= MIN_SIGNALS and total_n >= MIN_TOTAL_SIGNALS})
    return sorted(out, key=lambda x: (x["horizon"], x["median_train_return"] if x["median_train_return"] is not None else -1e9), reverse=True)


def _rank_exits(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["exit"]].append(r)
    out = []
    for mode, items in groups.items():
        items = [x for x in items if x.get("n", 0) > 0]
        if not items:
            continue
        ticker_count = len({x["ticker"] for x in items})
        trade_count = sum(x["n"] for x in items)
        out.append({"exit": mode, "tickers": ticker_count,
                    "entry_cohorts": len({x["entry_system"] for x in items}),
                    "trades": trade_count, "eligible": ticker_count >= MIN_SIGNALS and trade_count >= MIN_TOTAL_SIGNALS,
                    "median_ticker_return": round(float(np.median([x["median"] for x in items])), 3),
                    "median_train_return": round(float(np.median([x["splits"]["train"]["median"] for x in items if "train" in x.get("splits", {})])), 3) if any("train" in x.get("splits", {}) for x in items) else None,
                    "median_test_return": round(float(np.median([x["splits"]["test"]["median"] for x in items if "test" in x.get("splits", {})])), 3) if any("test" in x.get("splits", {}) for x in items) else None,
                    "median_ticker_pf": round(float(np.median([float(x["profit_factor"]) for x in items if isinstance(x["profit_factor"], (int, float))])), 3) if any(isinstance(x["profit_factor"], (int, float)) for x in items) else None,
                    "median_ticker_dd": round(float(np.median([x["max_trade_sequence_dd"] for x in items])), 2)})
    return sorted(out, key=lambda x: (x["median_train_return"] if x["median_train_return"] is not None else -1e9, x["median_ticker_pf"] or 0), reverse=True)


def _rank_matrix(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[(r["entry"], r["exit"])].append(r)
    out = []
    for (entry, mode), items in groups.items():
        items = [x for x in items if x.get("n", 0) > 0]
        if not items:
            continue
        ticker_count = len({x["ticker"] for x in items})
        trade_count = sum(x["n"] for x in items)
        out.append({"entry": entry, "exit": mode, "tickers": ticker_count,
                    "trades": trade_count, "eligible": ticker_count >= MIN_SIGNALS and trade_count >= MIN_TOTAL_SIGNALS,
                    "median_ticker_return": round(float(np.median([x["median"] for x in items])), 3),
                    "median_train_return": round(float(np.median([x["splits"]["train"]["median"] for x in items if "train" in x.get("splits", {})])), 3) if any("train" in x.get("splits", {}) for x in items) else None,
                    "median_test_return": round(float(np.median([x["splits"]["test"]["median"] for x in items if "test" in x.get("splits", {})])), 3) if any("test" in x.get("splits", {}) for x in items) else None,
                    "median_ticker_pf": round(float(np.median([float(x["profit_factor"]) for x in items if isinstance(x["profit_factor"], (int, float))])), 3) if any(isinstance(x["profit_factor"], (int, float)) for x in items) else None})
    return sorted(out, key=lambda x: (x["median_train_return"] if x["median_train_return"] is not None else -1e9, x["median_ticker_pf"] or 0), reverse=True)


def build_payload(entry_rows, exit_rows, matrix_rows, generated, period, coverage):
    entry_rank = _rank_entries(entry_rows)
    exit_rank = _rank_exits(exit_rows)
    # Top 10 entry definitions and exit rules; matrix remains detailed by ticker and system.
    top_entries = []
    for r in entry_rank:
        if r["horizon"] == 20 and r["eligible"] and r["system"] not in top_entries:
            top_entries.append(r["system"])
        if len(top_entries) == 10:
            break
    top_exits = [r["exit"] for r in exit_rank if r.get("eligible")][:10]
    matrix_top = [r for r in matrix_rows if r["entry"] in top_entries and r["exit"] in top_exits]
    matrix_rank = _rank_matrix(matrix_top)
    return {
        "generated": generated, "period": period, "cost_round_trip_bps": COST_BPS,
        "execution": "Segnale a Close t; ingresso Open t+1. Stop intraday gap-aware; regole close-based eseguite all'Open successiva. Prezzi OHLC non rettificati, dividendi esclusi.",
        "cohort_rule": "Per ogni sistema/ticker, segnali distanziati di almeno 60 sedute e durata massima 60 barre; l'eventuale uscita forzata avviene all'Open successiva. La stessa coorte è applicata a tutte le uscite. Non rappresenta un portafoglio multi-ETF.",
        "universe_filter": "Strumenti dell'universo BIG non a leva e non inversi; classificazione dello strumento ereditata dall'universo sorgente.",
        "coverage": coverage,
        "horizons": list(HORIZONS), "exit_modes": list(EXIT_MODES),
        "entry_ranking": entry_rank, "entry_rows": entry_rows,
        "exit_ranking": exit_rank, "exit_rows": exit_rows,
        "top_entries_20d": top_entries, "top_exits": top_exits,
        "matrix_ranking": matrix_rank, "matrix_rows": matrix_top
    }


def write_outputs(data_dir, payload):
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "entry_exit_research.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    try:
        with pd.ExcelWriter(path / "entry_exit_research.xlsx", engine="openpyxl") as writer:
            for key, sheet in (("entry_ranking", "Entry ranking"), ("exit_ranking", "Exit ranking"),
                               ("matrix_ranking", "Entry x Exit")):
                pd.DataFrame(payload.get(key, [])).to_excel(writer, sheet_name=sheet, index=False)
            pd.DataFrame(payload.get("entry_rows", [])).drop(columns=["yearly", "splits"], errors="ignore").to_excel(writer, sheet_name="Entry per ETF", index=False)
            pd.DataFrame(payload.get("exit_rows", [])).drop(columns=["splits"], errors="ignore").to_excel(writer, sheet_name="Exit per ETF", index=False)
            pd.DataFrame(payload.get("matrix_rows", [])).to_excel(writer, sheet_name="Matrix per ETF", index=False)
    except Exception as exc:
        payload["excel_error"] = repr(exc)
        (path / "entry_exit_research.json").write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
