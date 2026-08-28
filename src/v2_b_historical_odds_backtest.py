"""Historical market backtest for frozen V2-B candidate.

Uses the already generated regular-season cross-season prediction detail and
actual O/U 2.5 odds stored in allsvenskan_raw.csv. No API calls.

Frozen candidate conditions:
- both teams have reached match 6
- unchanged V1 P(Over 2.5) in [55%, 60%)
- observed historical Over 2.5 odds >= 1.85

Runs every available standard Football-Data Over 2.5 odds column separately.
This is deliberate: we report the market-source sensitivity rather than select
the most flattering odds series after seeing outcomes.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
HISTORY=ROOT/"data"/"allsvenskan_raw.csv"
DETAIL=ROOT/"data"/"allsvenskan_v2_cross_season_detail.csv"
OUT_DETAIL=ROOT/"data"/"allsvenskan_v2_b_historical_odds_detail.csv"
OUT_SUMMARY=ROOT/"data"/"allsvenskan_v2_b_historical_odds_summary.csv"

MODEL_MIN=.55
MODEL_MAX=.60
MIN_ODDS=1.85
MIN_MATCH=6
OVER_COLUMNS=["MaxC>2.5","AvgC>2.5","B365C>2.5","PC>2.5","Max>2.5","Avg>2.5","B365>2.5","P>2.5"]
UNDER_PAIR={
    "MaxC>2.5":"MaxC<2.5","AvgC>2.5":"AvgC<2.5","B365C>2.5":"B365C<2.5","PC>2.5":"PC<2.5",
    "Max>2.5":"Max<2.5","Avg>2.5":"Avg<2.5","B365>2.5":"B365<2.5","P>2.5":"P<2.5",
}


def metrics(g):
    if g.empty:
        return {"bets":0,"wins":0,"win_rate":np.nan,"mean_odds":np.nan,"profit_units":0.0,"roi_pct":np.nan,"mean_model_p":np.nan,"mean_market_implied_p":np.nan,"mean_no_vig_over_p":np.nan,"mean_model_edge_pp":np.nan}
    wins=int(g.actual_over25.sum())
    profit=np.where(g.actual_over25.eq(1),g.odds-1.0,-1.0)
    return {
        "bets":len(g),"wins":wins,"win_rate":float(g.actual_over25.mean()),"mean_odds":float(g.odds.mean()),
        "profit_units":float(profit.sum()),"roi_pct":float(profit.mean()*100),"mean_model_p":float(g.p_over25.mean()),
        "mean_market_implied_p":float((1.0/g.odds).mean()),
        "mean_no_vig_over_p":float(g.no_vig_over_p.mean()) if g.no_vig_over_p.notna().any() else np.nan,
        "mean_model_edge_pp":float(((g.p_over25-g.no_vig_over_p)*100).mean()) if g.no_vig_over_p.notna().any() else np.nan,
    }


def main():
    if not HISTORY.exists(): raise RuntimeError(f"Saknar {HISTORY}")
    if not DETAIL.exists(): raise RuntimeError("Kör v2_cross_season_cold_start.py först.")
    hist=pd.read_csv(HISTORY)
    det=pd.read_csv(DETAIL)
    hist["Season"]=pd.to_numeric(hist["Season"],errors="coerce")
    hist["date_key"]=pd.to_datetime(hist["Date"],dayfirst=True,errors="coerce").dt.date.astype(str)
    hist["home_team"]=hist["Home"].astype(str); hist["away_team"]=hist["Away"].astype(str)
    available=[c for c in OVER_COLUMNS if c in hist.columns and pd.to_numeric(hist[c],errors="coerce").notna().any()]
    print("ALLSVENSKAN V2-B HISTORICAL ODDS BACKTEST")
    print("="*92)
    print("Frysta villkor: match 6+; P(Over) 55-60%; odds >= 1.85.")
    if not available:
        print("Inga kända Football-Data Over 2.5-kolumner med värden hittades i råfilen.")
        pd.DataFrame().to_csv(OUT_DETAIL,index=False); pd.DataFrame().to_csv(OUT_SUMMARY,index=False)
        return

    base=det.copy()
    base["season"]=pd.to_numeric(base["season"],errors="coerce")
    base["date"]=base["date"].astype(str)
    base=base[(base.min_match_no>=MIN_MATCH)&(base.p_over25>=MODEL_MIN)&(base.p_over25<MODEL_MAX)].copy()
    summaries=[]; details=[]
    keys=["season","date","home_team","away_team"]
    for overcol in available:
        cols=["Season","date_key","home_team","away_team",overcol]
        undercol=UNDER_PAIR.get(overcol)
        if undercol in hist.columns: cols.append(undercol)
        h=hist[cols].rename(columns={"Season":"season","date_key":"date",overcol:"odds"}).copy()
        h["odds"]=pd.to_numeric(h["odds"],errors="coerce")
        if undercol in h.columns: h[undercol]=pd.to_numeric(h[undercol],errors="coerce")
        x=base.merge(h,on=keys,how="left",validate="one_to_one")
        x["odds_source"]=overcol
        x["market_implied_p"]=1.0/x["odds"]
        x["no_vig_over_p"]=np.nan
        if undercol in x.columns:
            under_imp=1.0/x[undercol]
            over_imp=1.0/x["odds"]
            x["no_vig_over_p"]=over_imp/(over_imp+under_imp)
        x["qualifies_odds"]=x["odds"]>=MIN_ODDS
        q=x[x.qualifies_odds & x.odds.notna()].copy()
        if len(q):
            q["profit"]=np.where(q.actual_over25.eq(1),q.odds-1.0,-1.0)
        details.append(x)
        for season,g in q.groupby("season"):
            summaries.append({"odds_source":overcol,"season":int(season),**metrics(g)})
        summaries.append({"odds_source":overcol,"season":"POOLED",**metrics(q)})

    detail=pd.concat(details,ignore_index=True) if details else pd.DataFrame()
    summary=pd.DataFrame(summaries)
    OUT_DETAIL.parent.mkdir(parents=True,exist_ok=True); detail.to_csv(OUT_DETAIL,index=False); summary.to_csv(OUT_SUMMARY,index=False)
    print("Tillgängliga oddsserier:",", ".join(available))
    print("\nResultat per oddsserie och säsong")
    print(summary.to_string(index=False))
    print("\nOBS: jämför oddsserier som marknadskänslighet. Välj inte i efterhand den serie som råkar ge högst ROI.")
    print("Detaljer:",OUT_DETAIL)
    print("Sammanfattning:",OUT_SUMMARY)

if __name__=="__main__": main()
