"""Genera il Bollettino quotidiano BIGCHATGPT integrando RAPTOR GEOGRAFIA e i motori BIG."""
import json
import datetime as dt
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GEO_URL = "https://raw.githubusercontent.com/Giorgiogoldoni/raptor-geografia/main/geografia.json"
HISTORY_URL = "https://giorgiogoldoni.github.io/BIGCHATGPT/data/bollettino_storico.json"

AREAS = {
    "Nord America": {
        "weight": 15, "tickers": ["CSCA.MI", "CAHEUA.MI", "VUSA.MI", "WSPX.MI", "SPY5.MI", "LGUS.MI", "FLXU.MI", "NQSE.DE", "WNAS.MI", "CSNDX.MI", "QTOP.MI", "SXRU.DE", "NTSZ.DE", "DJE.PA", "WRTY.MI", "IUSE.MI", "SPXE.MI", "WSPE.MI"]
    },
    "Europa": {
        "weight": 12, "tickers": ["MEUD.PA", "WS5X.MI", "C40.PA", "EXS1.DE", "IS3U.DE", "IAEX.AS", "XESD.DE", "UKE.MI", "CN1.PA", "XSMI.MI", "SVE.MI", "EST.MI", "WMIB.MI", "IMIB.MI", "FMI.MI", "CSMIB.MI"]
    },
    "Asia-Pacifico": {
        "weight": 15, "tickers": ["INDO.PA", "FLXI.MI", "SPXJ.MI", "CSPXJ.MI", "SAUS.MI", "AUHEUA.MI", "MCHN.MI", "LCCN.MI", "HSTE.MI", "XCS3.DE", "XCS4.DE", "XBAS.DE", "XFVT.DE", "XPQP.DE", "XCHA.DE", "VJPE.MI", "SJPA.MI", "IJPE.MI", "FLXT.MI", "IQQF.DE", "SEMA.MI", "CSEMAS.MI"]
    },
    "America Latina": {
        "weight": 10, "tickers": ["D5BI.DE", "IBZL.MI", "ALAT.MI", "LTAM.MI"]
    },
    "Medio Oriente": {
        "weight": 4, "tickers": ["SAUDI.MI", "TUR.PA"]
    },
    "Africa": {
        "weight": 4, "tickers": ["SRSA.MI", "LAFRI.MI"]
    },
}
GLOBAL = ["WRD.PA", "ISAC.MI", "NTSG.MI", "JRGE.MI"]
FACTORS = ["LEER.DE", "WWRD.MI", "NTSX.MI", "SP1E.MI", "XDEE.DE", "IAPD.MI"]


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BIGCHATGPT-bulletin/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def num(value):
    try:
        x = float(value)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def average(rows, key):
    values = [num(r.get(key)) for r in rows]
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


def compact_row(row):
    return {
        "ticker": row.get("ticker"), "name": row.get("name"),
        "price": num(row.get("price")), "score": num(row.get("score")),
        "trend": row.get("trend"), "trend_rs": row.get("trend_rs"),
        "buy_level": row.get("buy_level"), "perf7": num(row.get("perf7")),
        "perf30": num(row.get("perf30")), "rsi": num(row.get("rsi")),
        "adx": num(row.get("adx")), "k_pct": num(row.get("k_pct")), "er": num(row.get("er")),
        "ao": num(row.get("ao")), "sar_bullish": bool(row.get("sar_bullish")),
        "vortex_bullish": bool(row.get("vortex_bullish")), "rvi_bullish": bool(row.get("rvi_bullish")),
        "stress_score": num(row.get("stress_score")),
        "stress_flags": row.get("stress_flags") or [],
        "mm_aligned": bool(row.get("mm_aligned")),
        "regime": row.get("regime") or {},
    }


def area_view(name, cfg, by_ticker):
    rows = [by_ticker[t] for t in cfg["tickers"] if t in by_ticker]
    rows.sort(key=lambda r: (num(r.get("score")) if num(r.get("score")) is not None else -999), reverse=True)
    green = sum(r.get("trend") == "VERDE" for r in rows)
    red = sum(r.get("trend") == "ROSSO" for r in rows)
    buy = [r for r in rows if r.get("buy_level") == "BUY" and r.get("trend") == "VERDE" and r.get("trend_rs") == "VERDE" and r.get("mm_aligned") and r.get("sar_bullish") and r.get("vortex_bullish") and r.get("rvi_bullish") and num(r.get("stress_score")) is not None and num(r.get("stress_score")) <= 1]
    watch = [r for r in rows if r.get("buy_level") == "WATCH"]
    if buy:
        stance = "SEGNALI POSITIVI"
        reason = "Almeno uno strumento combina BUY, trend verde e stress contenuto."
    elif rows and red / len(rows) >= 0.5:
        stance = "DIFESA"
        reason = "Prevalgono trend rossi: evitare anticipazioni e attendere stabilizzazione."
    elif watch:
        stance = "OSSERVARE"
        reason = "Sono presenti strumenti in WATCH, ma manca una conferma piena per un segnale operativo."
    else:
        stance = "ATTENDERE"
        reason = "Non emerge una confluenza sufficiente di segnali positivi."
    return {
        "name": name, "weight": cfg["weight"], "count": len(rows),
        "green": green, "red": red, "avg_score": average(rows, "score"),
        "avg_perf7": average(rows, "perf7"), "avg_perf30": average(rows, "perf30"),
        "avg_stress": average(rows, "stress_score"), "stance": stance,
        "reason": reason, "leaders": [compact_row(r) for r in rows[:5]],
    }


def build():
    DATA.mkdir(exist_ok=True)
    try:
        geo = fetch_json(GEO_URL)
        (DATA / "geografia.json").write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        geo_source = "RAPTOR GEOGRAFIA live"
    except Exception as exc:
        geo = load_json(DATA / "geografia.json", {})
        geo_source = "ultimo RAPTOR disponibile" if geo else "non disponibile"
        print("ATTENZIONE: download RAPTOR non riuscito:", repr(exc)[:180])

    paesi = (geo.get("paesi") or {}).get("all") or []
    new_area = (geo.get("new_area") or {}).get("all") or []
    by_ticker = {}
    for row in paesi + new_area:
        if row.get("ticker"):
            by_ticker[row["ticker"]] = row

    big = load_json(DATA / "index.json", {}) or {}
    score = load_json(DATA / "score.json", {}) or {}
    audit = load_json(DATA / "reversion_audit.json", {}) or {}
    score_rows = [r for r in score.get("rows", []) if r.get("eligible") is True]
    score_rows.sort(key=lambda r: num(r.get("score")) if num(r.get("score")) is not None else -999, reverse=True)

    areas = [area_view(name, cfg, by_ticker) for name, cfg in AREAS.items()]
    global_rows = [compact_row(by_ticker[t]) for t in GLOBAL if t in by_ticker]
    factor_rows = [compact_row(by_ticker[t]) for t in FACTORS if t in by_ticker]
    area_tickers = {ticker for cfg in AREAS.values() for ticker in cfg["tickers"]}
    all_geo = [by_ticker[t] for t in area_tickers if t in by_ticker]
    trend_counts = {s: sum(r.get("trend") == s for r in all_geo) for s in ("VERDE", "GRIGIO", "ROSSO")}
    vix = num(geo.get("vix"))
    vix_regime = geo.get("vix_regime", "n.d.")
    if vix is not None and vix >= 25:
        risk_label = "RISCHIO ELEVATO"
        risk_text = "VIX sopra 25: regime di volatilità elevata. Ridurre l'aggressività e pretendere conferme."
    elif vix is not None and vix >= 20:
        risk_label = "PRUDENZA"
        risk_text = "Volatilità sopra la fascia tranquilla: privilegiare ingressi graduali e segnali confermati."
    else:
        risk_label = "REGIME ORDINARIO"
        risk_text = "Volatilità non elevata secondo la soglia del bollettino; restano validi i filtri tecnici."
    if not all_geo:
        risk_text += " Dati geografici non disponibili: non formulare decisioni per area."

    big_rows = big.get("righe", [])
    recent_signals = []
    for row in big_rows:
        dates = row.get("s") or {}
        if dates:
            last = max(str(d) for d in dates.values())
            recent_signals.append({"ticker": row.get("t"), "name": row.get("n"), "date": last, "count": len(dates)})
    recent_signals.sort(key=lambda r: r["date"], reverse=True)

    audit_rows = audit.get("tickers", [])
    mr = {"trades": 0, "open": 0, "closed": 0}
    smr = {"trades": 0, "open": 0, "closed": 0}
    for row in audit_rows:
        system = row.get("system")
        target = mr if system == "mr" else smr if system == "smr" else None
        if target is None:
            continue
        trades = row.get("trades") or []
        target["trades"] += len(trades)
        target["open"] += sum(t.get("status") == "open" for t in trades)
        target["closed"] += sum(t.get("status") == "closed" for t in trades)

    today = dt.datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = (
        f"Il quadro geografico registra {trend_counts['VERDE']} strumenti in trend verde, "
        f"{trend_counts['GRIGIO']} grigi e {trend_counts['ROSSO']} rossi. "
        + (f"Il VIX a {vix:.2f} impone prudenza." if vix is not None and vix >= 25 else
           f"Il VIX è a {vix:.2f}." if vix is not None else "Il VIX non è disponibile.")
    )
    payload = {
        "date": today, "generated": generated, "geo_updated": geo.get("updated_display") or geo.get("updated_at"),
        "geo_source": geo_source, "vix": vix, "vix_regime": vix_regime,
        "risk_label": risk_label, "risk_text": risk_text, "summary": summary,
        "trend_counts": trend_counts, "areas": areas,
        "global": global_rows, "factors": factor_rows,
        "big": {"generated": big.get("gen"), "universe": len(big_rows),
                "recent_signals": recent_signals[:12]},
        "top20": {"generated": score.get("generated"), "period": score.get("period"),
                  "rows": [{k: r.get(k) for k in ("t", "name", "score", "score20", "score40", "score60", "roc20", "roc40", "roc60", "rsi14", "adx14", "atr_pct", "date", "coverage")} for r in score_rows[:20]]},
        "mean_reversion": {"generated": audit.get("generated"), "mr": mr, "smr": smr},
        "method": {
            "geography": "RAPTOR GEOGRAFIA: KAMA, Kaufman ER, Awesome Oscillator, SAR, Vortex, RVI, RSI, ADX, performance 7/30 sedute e stress flags.",
            "big": "BIGCHATGPT: segnali dei sistemi Trend, Momentum, Indicatori, Inversione e Breakout.",
            "top20": "Score tecnico 0–100 sui tre orizzonti 20/40/60 sedute; non è una previsione di rendimento.",
            "decision": "Le etichette sono filtri tecnici descrittivi. BUY richiede livello BUY, trend e forza relativa VERDE, medie allineate, SAR/Vortex/RVI rialzisti e stress score ≤1; WATCH non equivale a comprare.",
        },
    }
    (DATA / "bollettino.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    history = []
    try:
        history = fetch_json(HISTORY_URL).get("issues", [])
    except Exception:
        pass
    history = [x for x in history if x.get("date") != today]
    history.append(payload)
    history.sort(key=lambda x: x.get("date", ""))
    history = history[-365:]
    (DATA / "bollettino_storico.json").write_text(json.dumps({"updated": generated, "issues": history}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("Bollettino generato:", today, "| geo:", geo_source, "| aree:", len(areas), "| storico:", len(history))


if __name__ == "__main__":
    build()
