"""Leakage-free walk-forward evaluation of V2 Candidate A.

Candidate A:
- no V2 evaluation until both teams have reached match 6 of the 2026 season
- probability = 50% frozen V1 probability + 50% league Over 2.5 rate known before match day

The league prior deliberately uses STRICTLY EARLIER CALENDAR DATES. This avoids
same-day leakage from matches that may have kicked off earlier but not finished
before another fixture starts.

Evaluation-only. Does not change V1, live signals, odds thresholds, or forward logs.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DETAIL_FILE = ROOT / "data" / "allsvenskan_backtest_v1.csv"
HISTORY_FILE = ROOT / "data" / "allsvenskan_raw.csv"
DETAIL_OUT = ROOT / "data" / "allsvenskan_v2_candidate_a.csv"
SUMMARY_OUT = ROOT / "data" / "allsvenskan_v2_candidate_a_summary.csv"
CALIBRATION_OUT = ROOT / "data" / "allsvenskan_v2_candidate_a_calibration.csv"

MIN_MATCH_NO = 6
V1_WEIGHT = 0.50
BASE_WEIGHT = 0.50


def metrics(y, p):
    y=np.asarray(y,dtype=float); p=np.asarray(p,dtype=float)
    actual=float(y.mean()); brier=float(np.mean((p-y)**2)); baseline=float(np.mean((actual-y)**2))
    return {"matches":len(y),"mean_prediction":float(p.mean()),"actual_over_rate":actual,"brier":brier,"baseline_brier":baseline,"brier_skill_score":1-brier/baseline if baseline else np.nan}


def main():
    if not DETAIL_FILE.exists(): raise RuntimeError("Kör V1 walk-forward-diagnostiken först.")
    if not HISTORY_FILE.exists(): raise RuntimeError(f"Saknar {HISTORY_FILE}")

    detail=pd.read_csv(DETAIL_FILE)
    needed={"date","home_team","away_team","p_over25","actual_over25","min_2026_match_no"}
    if not needed.issubset(detail.columns): raise RuntimeError(f"V1-detaljfilen saknar: {sorted(needed-set(detail.columns))}")
    detail["date"]=pd.to_datetime(detail["date"],errors="coerce").dt.date.astype(str)

    hist=pd.read_csv(HISTORY_FILE)
    hist["Season"]=pd.to_numeric(hist["Season"],errors="coerce")
    hist["HG"]=pd.to_numeric(hist["HG"],errors="coerce"); hist["AG"]=pd.to_numeric(hist["AG"],errors="coerce")
    hist["match_date"]=pd.to_datetime(hist["Date"].astype(str),dayfirst=True,errors="coerce").dt.date
    h=hist[hist["Season"].eq(2026)].dropna(subset=["match_date","Home","Away","HG","AG"]).copy().sort_values("match_date")
    h["actual_over25"]=(h["HG"]+h["AG"]>=3).astype(int)

    # Build one prior per calendar date from all COMPLETED matches on earlier dates only.
    date_prior={}
    overs=[]
    for match_date, group in h.groupby("match_date",sort=True):
        date_prior[str(match_date)]={
            "prior_over_rate": float(np.mean(overs)) if overs else np.nan,
            "prior_league_matches": len(overs),
        }
        overs.extend(group["actual_over25"].astype(int).tolist())

    h["date"]=h["match_date"].astype(str)
    prior_df=pd.DataFrame([{"date":d,**v} for d,v in date_prior.items()])
    lookup=h[["date","Home","Away"]].rename(columns={"Home":"home_team","Away":"away_team"}).merge(prior_df,on="date",how="left",validate="many_to_one")

    x=detail.merge(lookup,on=["date","home_team","away_team"],how="left",validate="one_to_one")
    x["p_over25"]=pd.to_numeric(x["p_over25"],errors="coerce")
    x["min_2026_match_no"]=pd.to_numeric(x["min_2026_match_no"],errors="coerce")
    x=x.dropna(subset=["p_over25","actual_over25","min_2026_match_no","prior_over_rate"]).copy()
    x["candidate_a_eligible"]=x["min_2026_match_no"]>=MIN_MATCH_NO
    x["p_v2_a"]=V1_WEIGHT*x["p_over25"]+BASE_WEIGHT*x["prior_over_rate"]
    x["v1_brier"]=(x["p_over25"]-x["actual_over25"])**2
    x["v2_a_brier"]=(x["p_v2_a"]-x["actual_over25"])**2
    x.to_csv(DETAIL_OUT,index=False)

    eligible=x[x["candidate_a_eligible"]].copy()
    if eligible.empty: raise RuntimeError("Inga matcher uppfyller Candidate A:s cold-start-villkor.")
    y=eligible["actual_over25"].to_numpy()
    v1=metrics(y,eligible["p_over25"].to_numpy()); v2=metrics(y,eligible["p_v2_a"].to_numpy())
    summary=pd.DataFrame([{"model":"V1 same matches",**v1},{"model":"V2 Candidate A",**v2}])
    summary["delta_brier_vs_v1_same_matches"]=summary["brier"]-v1["brier"]
    summary.to_csv(SUMMARY_OUT,index=False)

    bins=[-np.inf,.50,.55,.60,.65,np.inf]; labels=["<50%","50–55%","55–60%","60–65%","65%+"]
    eligible["probability_band"]=pd.cut(eligible["p_v2_a"],bins=bins,labels=labels,right=False)
    cal=eligible.groupby("probability_band",observed=False).agg(matches=("actual_over25","size"),mean_prediction=("p_v2_a","mean"),actual_over_rate=("actual_over25","mean"),brier=("v2_a_brier","mean")).reset_index()
    cal.to_csv(CALIBRATION_OUT,index=False)

    print("ALLSVENSKAN V2 CANDIDATE A — LEAKAGE-FREE WALK-FORWARD")
    print("="*78)
    print(f"Regel: båda lagen minst match {MIN_MATCH_NO}; p = 50% V1 + 50% Over-bas från strikt tidigare kalenderdatum")
    print(f"Matcher: {len(eligible)}")
    print(f"V1 samma matcher: Brier {v1['brier']:.4f} | Skill {v1['brier_skill_score']*100:+.2f}% | pred {v1['mean_prediction']*100:.1f}% | utfall {v1['actual_over_rate']*100:.1f}%")
    print(f"V2 Candidate A: Brier {v2['brier']:.4f} | Skill {v2['brier_skill_score']*100:+.2f}% | pred {v2['mean_prediction']*100:.1f}% | utfall {v2['actual_over_rate']*100:.1f}%")
    print(f"Delta Brier V2−V1: {v2['brier']-v1['brier']:+.4f} (negativt är bättre)")
    print("\nV2-A kalibrering")
    print(cal.to_string(index=False))
    print("Detaljer:",DETAIL_OUT)

if __name__=="__main__": main()
