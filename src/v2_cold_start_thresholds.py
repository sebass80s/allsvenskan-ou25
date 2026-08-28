"""Robustness test for V2 cold-start threshold. Diagnostic only, 0 API calls."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
INPUT=ROOT/"data"/"allsvenskan_backtest_v1.csv"
OUTPUT=ROOT/"data"/"allsvenskan_v2_cold_start_thresholds.csv"


def evaluate(df):
    y=df["actual_over25"].astype(float).to_numpy(); p=df["p_over25"].astype(float).to_numpy()
    actual=y.mean(); brier=np.mean((p-y)**2); baseline=np.mean((actual-y)**2)
    return len(df),p.mean(),actual,brier,baseline,(1-brier/baseline if baseline else np.nan)


def main():
    if not INPUT.exists(): raise RuntimeError("Kör V1 walk-forward-diagnostiken först.")
    df=pd.read_csv(INPUT)
    for c in ["p_over25","actual_over25","min_2026_match_no"]: df[c]=pd.to_numeric(df[c],errors="coerce")
    df=df.dropna(subset=["p_over25","actual_over25","min_2026_match_no"]).copy()
    rows=[]
    for threshold in range(3,11):
        sub=df[df["min_2026_match_no"]>=threshold]
        n,pred,actual,brier,base,skill=evaluate(sub)
        rows.append({"minimum_team_match_no":threshold,"matches":n,"mean_prediction":pred,"actual_over_rate":actual,"brier":brier,"baseline_brier":base,"brier_skill_score":skill})
    out=pd.DataFrame(rows)
    out.to_csv(OUTPUT,index=False)
    print("ALLSVENSKAN V2 COLD-START THRESHOLD ROBUSTNESS")
    print("="*78)
    print("Oförändrad V1-sannolikhet; endast starttröskeln varierar. Diagnostiskt, ej forward-test.")
    print(out.to_string(index=False))
    best=out.loc[out["brier"].idxmin()]
    print(f"\nLägst Brier i testgrid: match {int(best.minimum_team_match_no)}+ ({int(best.matches)} matcher, Brier {best.brier:.4f}, Skill {best.brier_skill_score*100:+.2f}%)")
    print("OBS: välj inte automatiskt bästa enskilda tröskel; leta efter en stabil platå över flera närliggande trösklar.")
    print("Resultat:",OUTPUT)

if __name__=="__main__": main()
