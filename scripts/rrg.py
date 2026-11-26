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
benchmarks={}
for b in BENCH:
 benchmarks[b]={"dates":[d.strftime("%Y-%m-%d") for d in close[b].index],"values":[round(float(v),5) for v in close[b].values]} if b in close else {"dates":[],"values":[]}
rows=[]
for item in UNIVERSE:
 t=item["ticker"]
 if t not in close: continue
 for b in BENCH:
  if b not in close or t==b: continue
  df=pd.concat([close[t].rename("asset"),close[b].rename("bench")],axis=1).dropna()
  ratio=df.asset/df.bench
  roc12=ratio/ratio.shift(12)-1
  base=roc12.rolling(52,min_periods=26).mean(); sd=roc12.rolling(52,min_periods=26).std()
  rs=100+5*((roc12-base)/(sd.replace(0,float("nan"))))
  delta=rs-rs.shift(4); dstd=delta.rolling(52,min_periods=26).std()
  mom=100+5*(delta/(dstd.replace(0,float("nan"))))
  vals=pd.DataFrame({"rs":rs,"mom":mom}).dropna().tail(21)
  if vals.empty: continue
  latest_rs=float(vals.rs.iloc[-1]); latest_mom=float(vals.mom.iloc[-1])
  quad="Leading" if latest_rs>=100 and latest_mom>=100 else "Improving" if latest_rs<100 and latest_mom>=100 else "Weakening" if latest_rs>=100 and latest_mom<100 else "Lagging"
  rows.append({**item,"benchmark":b,"date":vals.index[-1].strftime("%Y-%m-%d"),"rs":round(latest_rs,2),"mom":round(latest_mom,2),"trail":[[round(float(x),2),round(float(y),2)] for x,y in vals.values],"quadrant":quad})
payload={"generated":dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),"source":"Yahoo Finance via yfinance; weekly adjusted closes","method":"Approximate RRG: RS ratio uses 12-week relative return z-score (52-week rolling, min 26); momentum uses 4-week change in RS ratio, similarly standardized. Not proprietary JdK.","benchmarks":benchmarks,"rows":rows,"universe_count":len(UNIVERSE),"loaded_tickers":sorted(close)}
(DATA/"rrg.json").write_text(json.dumps(payload,separators=(",",":")),encoding="utf-8")
print("RRG snapshot:",len(rows),"asset/benchmark pairs from",len(close),"price series; as of",max((r["date"] for r in rows),default="NA"))
if len(rows)<50: raise SystemExit("ERROR: too few RRG asset/benchmark pairs loaded")
