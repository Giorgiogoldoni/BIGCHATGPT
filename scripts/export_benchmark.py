"""Esporta benchmark: qualità dei segnali, uscite operative e dettaglio per ETF."""
import json
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SOURCE, TARGET = DATA / "benchmark.json", DATA / "benchmark.xlsx"
NAMES = {"mom":"Momentum","cd":"Compra dal","core":"Core BUY1/2/3","azb":"Az BUY2/3","inv":"Inversione",
"sbb":"Super Best Buy","psar":"Parabolic SAR","adx":"ADX","ema":"EMA 20/50","k5":"Kamal 5",
"mr":"Mean Reversion","smr":"Super Mean Reversion","chat_trend_pullback":"Trend Pullback (candidato ChatGPT)"}

def style(ws):
    ws.freeze_panes = "A2"
    if ws.max_row: ws.auto_filter.ref = ws.dimensions
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="263B59")
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for col in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = min(32, max(12, max((len(str(ws.cell(r,col).value or "")) for r in range(1,min(ws.max_row,300)+1)), default=12)+2))

def main():
    if not SOURCE.exists():
        print("benchmark.json assente"); return 0
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    wb = Workbook()
    ws = wb.active; ws.title = "Uscite operative"
    ws.append(["Sistema","Uscita","ETF","Trade","Mediana ETF mediana %","Mediana win rate %","Mediana PF","Mediana drawdown %","Durata mediana"])
    for x in data.get("ranking",[]):
        ws.append([NAMES.get(x["system"],x["system"]),x["exit"],x["tickers"],x["trades"],x["median_ticker_median"],
            x["median_ticker_win_rate"],x["median_ticker_pf"],x["median_ticker_drawdown"],x["median_duration"]])
    style(ws)
    fw=wb.create_sheet("Segnali forward")
    fw.append(["Sistema","Orizzonte","ETF","Segnali","Mediana rendimento segnali %","Win rate mediano %","Mediana baseline %","Edge mediano %"])
    for x in data.get("forward_ranking",[]):
        fw.append([NAMES.get(x["system"],x["system"]),x["horizon"],x["tickers"],x["signals"],x["median_ticker_return"],
            x["median_ticker_win_rate"],x["median_ticker_baseline"],x["median_edge"]])
    style(fw)
    detail=wb.create_sheet("Dettaglio ETF uscite")
    detail.append(["Ticker","Sistema","Uscita","Trade","Vincenti %","Media %","Mediana %","Profit factor","Max drawdown %","Durata media"])
    for x in data.get("rows",[]):
        detail.append([x["ticker"],NAMES.get(x["system"],x["system"]),x["exit"],x["n"],x["win_rate"],x["mean"],
            x["median"],x["profit_factor"],x["max_drawdown"],x["avg_bars"]])
    style(detail)
    fdet=wb.create_sheet("Dettaglio segnali")
    fdet.append(["Ticker","Sistema","Orizzonte","Segnali","Win rate %","Mediana segnali %","Media segnali %","Baseline mediana %","Baseline media %","Edge mediano %"])
    for x in data.get("forward_rows",[]):
        fdet.append([x["ticker"],NAMES.get(x["system"],x["system"]),x["horizon"],x["signals"],x["win_rate"],
            x["median_return"],x["mean_return"],x["baseline_median"],x["baseline_mean"],x["median_edge"]])
    style(fdet)
    method=wb.create_sheet("Metodo e note")
    for row in [["Voce","Descrizione"],["Generato",data.get("generated","")],["Periodo",data.get("period","")],
        ["Universo",data.get("universe_filter","")],["Esecuzione",data.get("execution","")],
        ["Costo",f'{data.get("cost_round_trip_bps","")} bp round-trip ipotetici'],
        ["Benchmark segnali",data.get("forward_method","")],
        ["Benchmark uscite",data.get("operational_method","")],
        ["Dividendi","Esclusi: prezzi Close non rettificati."],
        ["Lettura","L'edge forward confronta i segnali con finestre periodiche non sovrapposte dello stesso ETF. Non e' una prova causale definitiva: resta possibile dipendenza tra regimi e selezione multipla."],
        ["Uscite operative","Metriche dei trade sequenziali; non equivalgono a un portafoglio multi-ETF e non vanno confrontate direttamente con rendimenti buy-and-hold di durata diversa."],
        ["Limiti","Prezzi Yahoo, universo corrente (survivorship bias), costi ipotetici e assenza di spread/commissioni specifiche. Non e' una previsione."]]:
        method.append(row)
    style(method); method.column_dimensions["A"].width=24; method.column_dimensions["B"].width=115
    for row in method.iter_rows(min_row=2): row[1].alignment=Alignment(wrap_text=True,vertical="top")
    wb.save(TARGET)
    print(f"Excel creato: {TARGET} | uscite={len(data.get('ranking',[]))} | forward={len(data.get('forward_ranking',[]))}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
