"""RRG weekly snapshot (Yahoo Finance via yfinance); RS-ratio/momentum approximation, not proprietary JdK."""
import json, datetime as dt
from pathlib import Path
import pandas as pd, yfinance as yf
ROOT=Path(__file__).resolve().parent.parent; DATA=ROOT/"data"
UNIVERSE=json.loads((ROOT/"rrg_universe.json").read_text())
BENCH=["SPY","ACWI","QQQ","GLD","DBC"]
TICKERS=sorted(set(x["ticker"] for x in UNIVERSE)|set(BENCH))
raw=yf.download(TICKERS,period="5y",interval="1wk",auto_adjust=True,group_by="ticker",threads=True,progress=False)
close={}
for t in TICKERS:
 try:
  s=raw[t]["Close"] if isinstance(raw.columns,pd.MultiIndex) else raw["Close"]
  s=s.dropna()
  if len(s)>70: close[t]=s
 except Exception: pass
benchmarks={b:{"dates":[],"values":[]} for b in BENCH}
for b in BENCH:
 if b in close: benchmarks[b]={"dates":[d.strftime("%Y-%m-%d") for d in close[b].index],"values":[round(float(v),5) for v in close[b].values]}
rows=[]
for item in UNIVERSE:
 t=item["ticker"]; b=item["bench"]
 if t not in close or b not in close: continue
 df=pd.concat([close[t].rename("asset"),close[b].rename("bench")],axis=1).dropna()
 ratio=df.asset/df.bench
 roc12=ratio/ratio.shift(12)-1
 base=roc12.rolling(52,min_periods=26).mean(); sd=roc12.rolling(52,min_periods=26).std()
 rs=100+5*((roc12-base)/(sd.replace(0,float("nan"))))
 delta=rs-rs.shift(4); dstd=delta.rolling(52,min_periods=26).std()
 mom=100+5*(delta/(dstd.replace(0,float("nan"))))
 vals=pd.DataFrame({"rs":rs,"mom":mom}).dropna().tail(21)
 if vals.empty: continue
 rows.append({**item,"benchmark":b,"date":vals.index[-1].strftime("%Y-%m-%d"),"rs":round(float(vals.rs.iloc[-1]),2),"mom":round(float(vals.mom.iloc[-1]),2),"trail":[[round(float(x),2),round(float(y),2)] for x,y in vals.values],"quadrant":("Leading" if vals.rs.iloc[-1]>=100 and vals.mom.iloc[-1]>=100 else "Improving" if vals.rs.iloc[-1]<100 and vals.mom.iloc[-1]>=100 else "Weakening" if vals.rs.iloc[-1]>=100 and vals.mom.iloc[-1]<100 else "Lagging")})
payload={"generated":dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),"source":"Yahoo Finance via yfinance; weekly adjusted closes","method":"Approximate RRG: RS ratio uses 12-week relative return z-score (52-week rolling, min 26); momentum uses 4-week change in RS ratio, similarly standardized. Not proprietary JdK.","benchmarks":benchmarks,"rows":rows,"universe_count":len(UNIVERSE),"loaded_tickers":sorted(close)}
(DATA/"rrg.json").write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8")
print("RRG snapshot:",len(rows),"symbols from",len(close),"price series; as of",max((r["date"] for r in rows),default="NA"))
if len(rows)<20: raise SystemExit("ERROR: too few RRG assets loaded")
