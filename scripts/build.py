"""big: scarica barre, calcola segnali e benchmark."""
import json, os, re, sys, time, datetime as dt, urllib.request
from pathlib import Path
import pandas as pd
import yfinance as yf
import systems as S
import rank
import score as SC
import benchmark as BM
import reversion_audit as RA
import mercato as M
from issuers import issuer

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; CH = DATA / "charts"
UNIV_URL = "https://raw.githubusercontent.com/Giorgiogoldoni/core/main/data/tickers_universe.json"
ISHARES = re.compile(r"ISHARES|^ISH|^IS[. ]", re.I)
INVERSO = re.compile(r"-\s?\d\s?X|\bINVERSE\b|\bBEAR\b|(DAILY|DLY).*\bSHORT\b|\bSHORT\b.*(DAILY|DLY)|(DAILY|DLY).*\bINV\b|\d\s?X\s*(SHORT|INV)\b|\bSHORT[A-Z]*DAX", re.I)
BATCH, PAUSA, MIN_BARRE = 40, 3, 60
CLASSIFICA = os.environ.get("CLASSIFICA") == "1"
PERIODO = "5y" if CLASSIFICA else "2y"
LIVE = "https://giorgiogoldoni.github.io/BIGCHATGPT/data/"


def carica_universo():
    for k in range(3):
        try:
            return json.load(urllib.request.urlopen(UNIV_URL, timeout=60))["instruments"]
        except Exception as e:
            print("universo: tentativo", k + 1, repr(e)[:80]); time.sleep(5)
    sys.exit("ERRORE: impossibile leggere tickers_universe.json da core")


def seleziona(strumenti):
    mi = [x for x in strumenti if x["ticker_yf"].endswith(".MI")]
    isin_mi = {x["isin"] for x in mi}
    de = [x for x in strumenti if x["ticker_yf"].endswith(".DE") and ISHARES.search(x["name"]) and x["isin"] not in isin_mi]
    return [dict(t=x["ticker_yf"], n=x["name"], i=x["isin"], b="Borsa Italiana" if x["ticker_yf"].endswith(".MI") else "Xetra",
        e=issuer(x["name"]), lv=bool(x.get("is_leveraged")), inv=bool(INVERSO.search(x["name"])),
        tp=x.get("product_type"), ac=x.get("asset_class"), acd=x.get("asset_class_confidence") == "default_fallback") for x in mi + de]


def pulisci(d):
    if d is None or len(d) == 0: return None
    cols = ["Open", "High", "Low", "Close", "Volume"]
    if "Adj Close" in d.columns: cols.append("Adj Close")
    d = d[cols].dropna(subset=["Open", "High", "Low", "Close"]).copy()
    if getattr(d.index, "tz", None) is not None: d.index = d.index.tz_localize(None)
    d.index = pd.to_datetime(d.index).normalize()
    d = d[~((d["Volume"].fillna(0) == 0) & (d["High"] == d["Low"]))]
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d if len(d) >= MIN_BARRE else None


def scarica(tickers):
    out = {}
    for k in range(0, len(tickers), BATCH):
        b = tickers[k:k + BATCH]
        try: raw = yf.download(b, period=PERIODO, interval="1d", auto_adjust=False, group_by="ticker", threads=True, progress=False)
        except Exception as e: print("batch", k, "errore", repr(e)[:80]); raw = None
        for t in b:
            try:
                if raw is None or len(raw) == 0: continue
                d = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                d = pulisci(d)
                if d is not None: out[t] = d
            except Exception: pass
        print("scaricati", min(k + BATCH, len(tickers)), "/", len(tickers), flush=True); time.sleep(PAUSA)
    for t in [t for t in tickers if t not in out]:
        try:
            d = pulisci(yf.Ticker(t).history(period=PERIODO, interval="1d", auto_adjust=False))
            if d is not None: out[t] = d
        except Exception: pass
        time.sleep(1)
    return out


def scrivi(universo, dati):
    CH.mkdir(parents=True, exist_ok=True)
    gen = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    righe, errori, rank_rows, merc_rows, score_rows = [], [], [], [], []
    benchmark_rows, benchmark_forward = [], []
    reversion_rows = []
    for u in universo:
        full = dati.get(u["t"])
        if full is None: errori.append(u["t"]); continue
        d = full[full.index >= full.index[-1] - pd.DateOffset(years=2)]
        analisi_df = full if CLASSIFICA else d
        try:
            ev, meta = S.calcola(analisi_df)
            try: score_rows.append(SC.calculate(u, analisi_df, ev, meta))
            except Exception as score_error: print("ERRORE score", u["t"], repr(score_error)[:100])
            if CLASSIFICA:
                rank_rows.append(rank.riga(u["t"], full, ev))
                # Il benchmark esclude ETF/ETN/ETC a leva e inversi; score e motore BIG restano invariati.
                result = BM.ticker_benchmark(u["t"], full, ev, meta, instrument=u)
                benchmark_rows.extend(result["rows"])
                benchmark_forward.extend(result["forward"])
                if not u["lv"] and not u["inv"]:
                    reversion_rows.extend(RA.audit_ticker(u["t"], full, ev, meta))
                ev = [e for e in ev if e[0] >= str(d.index[0].date())]
                meta["tr"] = [t for t in meta["tr"] if t[1] >= str(d.index[0].date())]
        except Exception as e:
            print("ERRORE calcolo", u["t"], repr(e)[:100]); errori.append(u["t"]); continue
        last, prev = d.iloc[-1], d.iloc[-2]; ult = str(d.index[-1].date())
        r = lambda x: round(float(x), 4)
        ch = dict(t=u["t"], n=u["n"], i=u["i"], b=u["b"], gen=gen, u=ult,
            d=[[str(i.date()), r(a), r(b), r(c), r(e_)] for i, (a, b, c, e_) in zip(d.index, d[["Open", "High", "Low", "Close"]].values)],
            ev=[list(e) for e in ev], tr=meta["tr"])
        (CH / (u["t"].replace(".", "_") + ".json")).write_text(json.dumps(ch, separators=(",", ":")), encoding="utf-8")
        r_m = M.riga(u, d, ev, meta["tr"])
        if r_m: merc_rows.append(r_m)
        ultimi = {}
        for e in ev: ultimi[e[1]] = e[0]
        x = {t[0]: [t[1], t[6], t[3], t[5]] for t in meta["tr"]}
        righe.append(dict(t=u["t"], n=u["n"], i=u["i"], b=u["b"], e=u["e"], lv=u["lv"], inv=u["inv"], tp=u["tp"], ac=u["ac"], acd=u["acd"],
            p=r(last["Close"]), v=round(float(last["Close"] / prev["Close"] - 1) * 100, 2), u=ult, s=ultimi, x=x,
            sta=S.stato_etf(meta["tr"], ult), nuovo=bool(meta["nuovo"]), core=meta["core"], ne=len(ev)))
    sistemi = [dict(id=s["id"], nome=s["nome"], colore=s["colore"]) for s in S.SYSTEMS]
    (DATA / "index.json").write_text(json.dumps(dict(gen=gen, sistemi=sistemi, righe=righe), separators=(",", ":")), encoding="utf-8")
    (DATA / "errori.json").write_text(json.dumps(errori), encoding="utf-8")
    M.scrivi(DATA, merc_rows, gen)
    SC.write(DATA, score_rows, gen, PERIODO)
    print("titoli con dati:", len(righe), "| senza dati:", len(errori))
    if CLASSIFICA:
        rank.scrivi(DATA, rank_rows, gen)
        BM.write(DATA, benchmark_rows, benchmark_forward, gen, PERIODO)
        audit_payload = {
            "generated": gen, "period": PERIODO, "cost_round_trip_bps": 10,
            "universe_filter": "ETF non a leva e non inversi; stesso universo del benchmark.",
            "execution": "Segnale a Close t, ingresso Open t+1; prima verifica uscita alla Close di t+1; prezzi Close non rettificati, dividendi esclusi.",
            "methods": {
                "old_close_entry": "Ricostruzione delle posizioni originali BIG: ingresso al Close del segnale e uscita originale.",
                "open_next_day": "Simulazione indipendente: ingresso all'Open successiva, uscite ricalcolate sul prezzo effettivo; MR = Bollinger superiore o Chandelier 3 ATR; SMR = Bollinger superiore o stop close-based -15%.",
            },
            "summary": RA.aggregate_audit(reversion_rows),
            "yearly_summary": RA.aggregate_yearly_audit(reversion_rows),
            "tickers": reversion_rows,
        }
        (DATA / "reversion_audit.json").write_text(json.dumps(audit_payload, separators=(",", ":")), encoding="utf-8")
        print("audit MR/SMR ETF:", len({r["ticker"] for r in reversion_rows}),
              "| righe ETF/sistema:", len(reversion_rows))


def recupera_classifica():
    for nome in ("classifica.json", "classifica_sintesi.json", "benchmark.json"):
        try:
            dati = urllib.request.urlopen(LIVE + nome, timeout=60).read(); json.loads(dati)
            (DATA / nome).write_bytes(dati); print("classifica precedente recuperata:", nome, len(dati) // 1024, "KB")
        except Exception as e: print("classifica precedente non disponibile:", nome, repr(e)[:70])


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    uni = seleziona(carica_universo())
    (DATA / "universo.json").write_text(json.dumps(uni, ensure_ascii=False), encoding="utf-8")
    print("universo:", len(uni), "(.MI %d, iShares .DE %d)" % (sum(x["b"] == "Borsa Italiana" for x in uni), sum(x["b"] == "Xetra" for x in uni)))
    scrivi(uni, scarica([x["t"] for x in uni]))
    if not CLASSIFICA: recupera_classifica()
