"""Esporta il report storico indipendente Mean Reversion / Super Mean Reversion."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def fit(ws, header_row=1):
    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}"
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = min(48, max(12, max(len(str(x.value or "")) for x in col) + 2))
        ws.column_dimensions[letter].width = width
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="243B53")
        cell.alignment = Alignment(wrap_text=True)


def main():
    source = DATA / "reversion_audit.json"
    if not source.exists():
        raise SystemExit("reversion_audit.json non trovato: eseguire prima build.py con CLASSIFICA=1")
    payload = json.loads(source.read_text(encoding="utf-8"))
    wb = Workbook()
    ws = wb.active
    ws.title = "Sintesi"
    ws.append(["Generato", payload.get("generated")])
    ws.append(["Periodo", payload.get("period")])
    ws.append(["Costi round-trip (bp)", payload.get("cost_round_trip_bps")])
    ws.append(["Metodo", "Mediane per strumento; metriche pooled calcolate sui trade, con un peso per trade."])
    ws.append([])
    ws.append(["Sistema", "Metodo", "Strumenti con trade", "Trade chiusi", "Posizioni aperte",
               "Mediana trade/strumento", "Win rate mediano per strumento %", "Rendimento mediano per strumento %", "Media rendimento mediana %",
               "PF mediano (solo finiti)", "Strumenti con PF infinito", "DD mediano sequenza trade %", "Durata mediana sedute",
               "Win rate pooled %", "PF pooled", "Rendimento medio trade %", "Somma rendimenti netti %",
               "Posizioni aperte negative", "Mark medio aperte %", "Mark peggiore aperte %"])
    for row in payload.get("summary", []):
        ws.append([row.get(k) for k in ("system", "method", "tickers", "closed_trades", "open_positions",
            "median_trades_per_ticker", "median_win_rate_per_ticker", "median_return_per_ticker",
            "median_mean_return_per_ticker", "median_finite_profit_factor_per_ticker", "tickers_with_infinite_profit_factor",
            "median_trade_sequence_drawdown_per_ticker", "median_duration", "pooled_win_rate", "pooled_profit_factor",
            "pooled_mean_net_return", "pooled_net_return_sum_pct", "open_negative_positions",
            "open_mean_mark_return", "open_worst_mark_return")])
    fit(ws, header_row=6)

    ws2 = wb.create_sheet("Confronto strumenti")
    ws2.append(["Ticker", "Tipologia", "Sistema", "Metodo", "Trade chiusi", "Aperti", "Win rate %", "Rendimento mediano %",
                "Rendimento medio %", "PF finito", "Drawdown sequenza trade %", "Durata media", "Delta mediana vs Close %"])
    for row in payload.get("tickers", []):
        for method, label in (("old_close_entry", "Originale: Close segnale"),
                              ("open_next_day", "Corretto: Open successiva")):
            m = row.get(method, {})
            ws2.append([row.get("ticker"), row.get("instrument_type"), row.get("system"), label, m.get("closed"), m.get("open"),
                m.get("win_rate"), m.get("median_return"), m.get("mean_return"), m.get("profit_factor"),
                m.get("max_drawdown"), m.get("avg_bars"), row.get("delta_median_return") if method == "open_next_day" else None])
    fit(ws2)

    wsy = wb.create_sheet("Per anno")
    wsy.append(["Sistema", "Metodo", "Anno ingresso", "Strumenti", "Trade chiusi", "Win rate mediano per strumento %",
                "Rendimento mediano per strumento %", "Media rendimento mediana %", "PF mediano finito", "DD mediano sequenza trade %",
                "Win rate pooled %", "PF pooled", "Rendimento medio trade %", "Somma rendimenti netti %"])
    for row in payload.get("yearly_summary", []):
        wsy.append([row.get(k) for k in ("system", "method", "year", "tickers", "closed_trades",
            "median_win_rate_per_ticker", "median_return_per_ticker", "median_mean_return_per_ticker",
            "median_finite_profit_factor_per_ticker", "median_trade_sequence_drawdown_per_ticker",
            "pooled_win_rate", "pooled_profit_factor", "pooled_mean_net_return", "pooled_net_return_sum_pct")])
    fit(wsy)

    ws3 = wb.create_sheet("Trade Open T+1")
    ws3.append(["Ticker", "Sistema", "Stato", "Segnale", "Ingresso", "Prezzo ingresso",
                "Uscita", "Prezzo uscita", "Prezzo mark", "Rendimento lordo %", "Netto %", 
                "Netto mark stimato %", "Sedute", "Motivo"])
    for row in payload.get("tickers", []):
        for t in row.get("trades", []):
            ws3.append([t.get("ticker"), t.get("system"), t.get("status"), t.get("signal_date"),
                t.get("entry_date"), t.get("entry_price"), t.get("exit_date"), t.get("exit_price"),
                t.get("mark_price"), t.get("gross_return_pct"), t.get("net_return_pct"),
                t.get("estimated_net_mark_return_pct"), t.get("bars"), t.get("reason")])
    fit(ws3)

    ws4 = wb.create_sheet("Metodo e note")
    for line in [
        ["Tema", "Descrizione"],
        ["Ingresso", "Segnale calcolato alla Close t; esecuzione all'Open della seduta t+1."],
        ["Uscite", "La prima verifica avviene alla Close della stessa seduta t+1."],
        ["Mean Reversion", "Uscita alla prima tra Close sopra/sulla Bollinger superiore e Chandelier 3 ATR; massimo aggiornato con gli High dall'ingresso."],
        ["Super Mean Reversion", "Uscita alla prima tra Close sopra/sulla Bollinger superiore e Close <= prezzo effettivo d'ingresso -15%. Stop close-based, non garantisce perdita massima del 15%."],
        ["Costi", "10 punti base round-trip; sottratti una sola volta ai trade chiusi."],
        ["Prezzi", "OHLC non rettificati; dividendi esclusi."],
        ["Universo", "ETF, ETC ed ETP non a leva e non inversi; esclusi strumenti classificati lv o inv. La tipologia è riportata per ticker."],
        ["Confronto", "Originale: ingresso Close del segnale e uscita registrata dal motore BIG. Corretto: ingresso Open successiva e uscita ricalcolata sul prezzo effettivo."],
        ["Metriche", "Il report distingue mediane per singolo strumento da statistiche pooled su tutti i trade. PF pooled = somma profitti netti / valore assoluto somma perdite nette. I PF infiniti per strumento sono contati separatamente e non entrano nella mediana dei PF finiti. Le posizioni aperte sono riportate separatamente con mark-to-market stimato, non incluse nel PF pooled."],
        ["Drawdown", "Il drawdown riportato in questa fase è quello della sequenza dei trade chiusi per strumento; NON è un drawdown giornaliero mark-to-market del portafoglio. La curva giornaliera richiede un modello esplicito di capitale e pesi."],
        ["Tipologia", "Ogni ticker è accompagnato dalla classificazione ETF/ETC/ETP ricevuta dall'universo sorgente. L'audit non deve essere descritto come ETF-only."],
        ["Limiti", "Questo audit corregge la coerenza dei prezzi di esecuzione e conserva le posizioni aperte. Non è ancora una validazione walk-forward dei parametri e non modifica la Top 20."],
    ]:
        ws4.append(line)
    fit(ws4)
    target = DATA / "reversion_audit.xlsx"
    wb.save(target)
    print("Creato", target)


if __name__ == "__main__":
    main()
