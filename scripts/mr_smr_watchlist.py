"""Registro giornaliero MR/SMR ricostruito dalle barre e dalle posizioni originali BIG."""
from __future__ import annotations

import datetime as dt
from typing import Iterable

SYSTEMS = {"mr": "MR", "smr": "SMR"}
DEFAULT_FROM_DATE = "2026-10-01"
DEFAULT_COST_BPS = 10


def ticker_rows(ticker: str, name: str, df, trades: Iterable[list],
                from_date: str = DEFAULT_FROM_DATE,
                cost_round_trip_bps: int = DEFAULT_COST_BPS) -> list[dict]:
    """Crea una riga per ogni trade MR/SMR con segnale dal from_date.

    Segnale rilevato a Close t; prezzo operativo teorico all'Open della seduta t+1.
    Uscita al Close della data d'uscita del motore originale. Se ancora aperto,
    mark-to-market all'ultimo Close. Il costo round-trip è espresso in basis point.
    """
    if df is None or df.empty:
        return []
    dates = [str(x.date()) for x in df.index]
    positions = {d: i for i, d in enumerate(dates)}
    last_date = dates[-1]
    last_price = float(df["Close"].iloc[-1])
    out = []

    for trade in trades or []:
        if len(trade) < 7:
            continue
        sid, signal_date, signal_close, exit_date, exit_price, reason, _ = trade[:7]
        if sid not in SYSTEMS or not signal_date or str(signal_date) < from_date:
            continue
        signal_i = positions.get(str(signal_date))
        if signal_i is None:
            continue

        execution_i = signal_i + 1
        base = {
            "id": f"{ticker}|{sid}|{signal_date}",
            "system": SYSTEMS[sid],
            "ticker": ticker,
            "name": name,
            "signal_date": str(signal_date),
            "signal_close": round(float(signal_close), 6),
            "last_date": last_date,
            "last_price": round(last_price, 6),
            "cost_round_trip_bps": int(cost_round_trip_bps),
        }
        if execution_i >= len(df):
            base.update({
                "execution_date": None, "entry_price": None, "return_net_pct": None,
                "status": "IN ATTESA", "exit_date": None, "exit_price": None,
                "exit_reason": "Segnale all'ultima seduta: attesa dell'apertura successiva",
                "sessions_held": 0,
            })
            out.append(base)
            continue

        entry_price = float(df["Open"].iloc[execution_i])
        execution_date = dates[execution_i]
        if exit_date:
            end_i = positions.get(str(exit_date))
            if end_i is None or end_i < execution_i:
                # Non inventare un prezzo d'uscita se la data non è presente nei dati.
                status, end_price, end_date, exit_reason = "DA VERIFICARE", last_price, last_date, "Data uscita non presente nello storico"
                end_i = len(df) - 1
            else:
                status, end_price, end_date, exit_reason = "CHIUSA", float(exit_price), str(exit_date), reason
        else:
            status, end_price, end_date, exit_reason = "ATTIVA", last_price, last_date, ""
            end_i = len(df) - 1

        gross_pct = (end_price / entry_price - 1) * 100 if entry_price else None
        net_pct = gross_pct - cost_round_trip_bps / 100 if gross_pct is not None else None
        base.update({
            "execution_date": execution_date,
            "entry_price": round(entry_price, 6),
            "return_net_pct": round(net_pct, 3) if net_pct is not None else None,
            "return_gross_pct": round(gross_pct, 3) if gross_pct is not None else None,
            "status": status,
            "exit_date": end_date if status in ("CHIUSA", "DA VERIFICARE") else None,
            "exit_price": round(end_price, 6) if status in ("CHIUSA", "DA VERIFICARE") else None,
            "exit_reason": exit_reason,
            "sessions_held": max(0, end_i - execution_i),
        })
        out.append(base)
    return out


def build_payload(rows: list[dict], generated: str,
                  from_date: str = DEFAULT_FROM_DATE,
                  cost_round_trip_bps: int = DEFAULT_COST_BPS) -> dict:
    rows = sorted(rows, key=lambda r: (r.get("signal_date", ""), r.get("ticker", "")), reverse=True)
    summary = {}
    for system in ("MR", "SMR"):
        subset = [r for r in rows if r["system"] == system]
        summary[system] = {
            "total": len(subset),
            "active": sum(r["status"] == "ATTIVA" for r in subset),
            "closed": sum(r["status"] == "CHIUSA" for r in subset),
            "pending": sum(r["status"] == "IN ATTESA" for r in subset),
        }
    return {
        "generated": generated,
        "from_date": from_date,
        "cost_round_trip_bps": cost_round_trip_bps,
        "execution_rule": "Segnale a Close t; ingresso teorico all'Open t+1; uscita alla Close secondo le regole originali MR/SMR. Mark-to-market all'ultimo Close per le posizioni aperte.",
        "cost_rule": f"Costo ipotetico {cost_round_trip_bps} bp round-trip sottratto al rendimento.",
        "summary": summary,
        "rows": rows,
    }
