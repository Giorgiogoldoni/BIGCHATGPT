"""Esporta il benchmark BIG in Excel: classifica aggregata e dettaglio per ETF/sistema/uscita."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE = DATA / "benchmark.json"
TARGET = DATA / "benchmark.xlsx"

NAMES = {
    "mom": "Momentum", "cd": "Compra dal", "core": "Core BUY1/2/3",
    "azb": "Az BUY2/3", "inv": "Inversione", "sbb": "Super Best Buy",
    "psar": "Parabolic SAR", "adx": "ADX", "ema": "EMA 20/50",
    "k5": "Kamal 5", "mr": "Mean Reversion", "smr": "Super Mean Reversion",
    "chat_trend_pullback": "Trend Pullback (candidato ChatGPT)",
}

def style_sheet(ws, widths=None):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="263B59")
        cell.alignment = Alignment(horizontal="center")
    if widths:
        for col, width in widths.items():
            ws.column_dimensions[col].width = width
    else:
        for col in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col)].width = min(
                max(12, max((len(str(ws.cell(r, col).value or "")) for r in range(1, min(ws.max_row, 300) + 1)), default=12) + 2), 34
            )

def main():
    if not SOURCE.exists():
        print("benchmark.json assente: Excel non aggiornato")
        return 0
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    wb = Workbook()
    ws = wb.active
    ws.title = "Classifica"
    headers = ["Sistema", "Uscita", "ETF", "Trade", "Vincenti %", "Media %", "Mediana %",
               "Eccesso vs hold %", "Profit factor", "Max drawdown %", "Durata media (sedute)"]
    ws.append(headers)
    for x in data.get("ranking", []):
        ws.append([NAMES.get(x["system"], x["system"]), x["exit"], x.get("tickers"), x.get("trades"),
                   x.get("win_rate"), x.get("mean"), x.get("median"), x.get("mean_excess"),
                   x.get("profit_factor"), x.get("max_drawdown"), x.get("avg_bars")])
    style_sheet(ws, {"A": 30, "B": 18, "C": 10, "D": 12, "E": 14, "F": 12, "G": 12,
                     "H": 18, "I": 14, "J": 18, "K": 22})
    for row in ws.iter_rows(min_row=2, min_col=5, max_col=8):
        for c in row: c.number_format = '0.00'
    ws.conditional_formatting.add(f"H2:H{ws.max_row}", ColorScaleRule(
        start_type="min", start_color="F4CCCC", mid_type="percentile", mid_value=50,
        mid_color="FFF2CC", end_type="max", end_color="D9EAD3"))

    detail = wb.create_sheet("Dettaglio ETF")
    detail.append(["Ticker", "Sistema", "Uscita", "Trade", "Vincenti %", "Media %", "Mediana %",
                   "Eccesso vs hold %", "Profit factor", "Max drawdown %", "Durata media (sedute)"])
    for x in data.get("rows", []):
        detail.append([x.get("ticker"), NAMES.get(x["system"], x["system"]), x.get("exit"),
                       x.get("n"), x.get("win_rate"), x.get("mean"), x.get("median"),
                       x.get("mean_excess"), x.get("profit_factor"), x.get("max_drawdown"), x.get("avg_bars")])
    style_sheet(detail, {"A": 16, "B": 30, "C": 18, "D": 12, "E": 14, "F": 12, "G": 12,
                         "H": 18, "I": 14, "J": 18, "K": 22})
    for row in detail.iter_rows(min_row=2, min_col=5, max_col=8):
        for c in row: c.number_format = '0.00'

    method = wb.create_sheet("Metodo e note")
    notes = [
        ["Voce", "Descrizione"],
        ["Generato", data.get("generated", "")],
        ["Periodo dati", data.get("period", "")],
        ["Costo", f'{data.get("cost_round_trip_bps", "")} punti base round-trip ipotetici'],
        ["Esecuzione", data.get("execution", "")],
        ["Dividendi", "Esclusi: rendimenti calcolati sui prezzi Close non rettificati."],
        ["Universo", "ETF presenti nell'universo BIG e con dati storici sufficienti; i risultati dipendono dalla copertura dati."],
        ["Classifica", "Aggregazione dei trade disponibili: non è una simulazione di portafoglio con capitale, pesi e limiti di esposizione."],
        ["Ponderazione", "I trade sono aggregati a livello di operazione; gli ETF con più segnali possono pesare maggiormente."],
        ["Confronto hold", "Eccesso = rendimento netto del trade meno rendimento Close buy-and-hold dello stesso ETF per la stessa durata."],
        ["Uscite originali", "Le posizioni ancora aperte non entrano nel confronto della modalità original."],
        ["Candidato", "Trend Pullback è un candidato sperimentale aggiunto al confronto, non uno dei 12 sistemi BIG."],
        ["Interpretazione", "Risultati storici, sensibili a costi, slippage, universo e regole di uscita; non sono una previsione."],
        ["Validazione", "I test automatici verificano causalità e struttura del calcolo; non dimostrano redditività futura."],
    ]
    for row in notes: method.append(row)
    style_sheet(method, {"A": 24, "B": 110})
    method.freeze_panes = "A2"
    for row in method.iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(TARGET)
    print(f"Excel creato: {TARGET} | classifica={len(data.get('ranking', []))} | dettaglio ETF={len(data.get('rows', []))}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
