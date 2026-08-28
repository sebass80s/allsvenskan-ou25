"""V2 sandbox for Allsvenskan O/U 2.5.

IMPORTANT: This module is diagnostic only. It does not change V1, forward logs,
or live betting signals. Experiments are evaluated on the existing leakage-free
2026 walk-forward output.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "allsvenskan_backtest_v1.csv"
OUTPUT = ROOT / "data" / "allsvenskan_v2_experiments.csv"


def metrics(df, probability):
    if df.empty:
        return {}
    y = df.actual_over25.astype(float).to_numpy()
    p = np.asarray(probability, dtype=float)
    actual = y.mean()
    brier = np.mean((p-y)**2)
    baseline = np.mean((actual-y)**2)
    return {"matches":len(df),"mean_prediction":p.mean(),"actual_over_rate":actual,"brier":brier,"baseline_brier":baseline,"brier_skill_score":1-brier/baseline if baseline else np.nan}


def add(rows, name, description, df, probability):
    row={"experiment":name,"description":description}; row.update(metrics(df, probability)); rows.append(row)


def main():
    if not INPUT.exists(): raise RuntimeError("Kör V1 walk-forward-diagnostiken först.")
    df=pd.read_csv(INPUT)
    if df.empty: raise RuntimeError("V1-backtestet är tomt.")
    df["p_over25"]=pd.to_numeric(df["p_over25"],errors="coerce")
    df=df.dropna(subset=["p_over25","actual_over25"]).copy()
    rows=[]
    add(rows,"V1 reference","Oförändrad V1 på alla predikterade matcher",df,df.p_over25)

    # Cold-start hypotheses. These are evaluation filters, not betting rules.
    if "min_2026_match_no" in df.columns:
        for threshold in (6,11,16):
            sub=df[df.min_2026_match_no>=threshold]
            add(rows,f"Maturity {threshold}+",f"Endast matcher där båda lagen nått match {threshold} i 2026",sub,sub.p_over25)

    # Simple shrinkage/calibration experiments. Fixed grid, reported transparently.
    base=float(df.actual_over25.mean())
    for weight in (0.25,0.50,0.75):
        p=weight*df.p_over25+(1-weight)*base
        add(rows,f"Shrink {weight:.2f}",f"{weight:.0%} V1-sannolikhet + {1-weight:.0%} 2026-basfrekvens (diagnostiskt, ej forward-säkert)",df,p)

    # Cap extremes to test whether overconfidence drives Brier loss.
    for lo,hi in ((.45,.65),(.50,.65),(.50,.70)):
        p=df.p_over25.clip(lo,hi)
        add(rows,f"Clip {lo:.2f}-{hi:.2f}",f"Klipper V1-sannolikheten till {lo:.0%}–{hi:.0%}",df,p)

    out=pd.DataFrame(rows).sort_values("brier")
    out.to_csv(OUTPUT,index=False)
    print("ALLSVENSKAN V2 SANDBOX")
    print("="*72)
    print("OBS: explorativ diagnostik. Inga V1-regler eller forward-signaler ändras.")
    print(out.to_string(index=False))
    print("Resultat:",OUTPUT)

if __name__=="__main__": main()
