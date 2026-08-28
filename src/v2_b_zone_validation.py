"""Validate V2-B specifically inside the frozen 55-60% V1 model zone.

Uses the cross-season walk-forward detail. No odds are used here, so expected
return at 1.85 is descriptive only and must NOT be interpreted as a historical
betting backtest.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
DETAIL=ROOT/"data"/"allsvenskan_v2_cross_season_detail.csv"
OUTPUT=ROOT/"data"/"allsvenskan_v2_b_zone_validation.csv"
MIN_MATCH_NO=6
P_MIN=.55
P_MAX=.60
ODDS_REFERENCE=1.85


def metrics(g):
    if g.empty:
        return {"matches":0,"mean_prediction":np.nan,"actual_over_rate":np.nan,"brier":np.nan,"baseline_brier":np.nan,"brier_skill_score":np.nan,"empirical_fair_odds":np.nan,"descriptive_return_at_1_85":np.nan}
    y=pd.to_numeric(g.actual_over25,errors="coerce").to_numpy(float)
    p=pd.to_numeric(g.p_over25,errors="coerce").to_numpy(float)
    rate=float(np.mean(y)); b=float(np.mean((p-y)**2)); base=float(np.mean((rate-y)**2))
    return {"matches":len(g),"mean_prediction":float(np.mean(p)),"actual_over_rate":rate,"brier":b,"baseline_brier":base,"brier_skill_score":1-b/base if base else np.nan,"empirical_fair_odds":1/rate if rate else np.nan,"descriptive_return_at_1_85":rate*ODDS_REFERENCE-1}


def main():
    if not DETAIL.exists(): raise RuntimeError("Kör src/v2_cross_season_cold_start.py först.")
    d=pd.read_csv(DETAIL)
    for c in ["season","min_match_no","p_over25","actual_over25"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=["season","min_match_no","p_over25","actual_over25"]).copy()
    zone=d[(d.p_over25>=P_MIN)&(d.p_over25<P_MAX)].copy()
    rows=[]
    for season in sorted(zone.season.astype(int).unique()):
        z=zone[zone.season==season]
        rows.append({"season":season,"slice":"ZONE_ALL",**metrics(z)})
        rows.append({"season":season,"slice":"ZONE_COLD_1_5",**metrics(z[z.min_match_no<MIN_MATCH_NO])})
        rows.append({"season":season,"slice":"ZONE_MATURE_6_PLUS",**metrics(z[z.min_match_no>=MIN_MATCH_NO])})
    rows.append({"season":"POOLED","slice":"ZONE_ALL",**metrics(zone)})
    rows.append({"season":"POOLED","slice":"ZONE_COLD_1_5",**metrics(zone[zone.min_match_no<MIN_MATCH_NO])})
    rows.append({"season":"POOLED","slice":"ZONE_MATURE_6_PLUS",**metrics(zone[zone.min_match_no>=MIN_MATCH_NO])})
    out=pd.DataFrame(rows); out.to_csv(OUTPUT,index=False)

    print("ALLSVENSKAN V2-B VALIDATION IN FROZEN 55-60% MODEL ZONE")
    print("="*92)
    print("OBS: inga historiska odds används. 'Return @1.85' är endast utfallsfrekvens × 1.85 − 1, inte ett betting-backtest.")
    print(out.to_string(index=False))
    mature=out[out.slice=="ZONE_MATURE_6_PLUS"]
    print("\nNyckelrader, mature 6+ i spelzonen")
    print(mature[["season","matches","mean_prediction","actual_over_rate","brier_skill_score","empirical_fair_odds","descriptive_return_at_1_85"]].to_string(index=False))
    print("Resultat:",OUTPUT)

if __name__=="__main__": main()
