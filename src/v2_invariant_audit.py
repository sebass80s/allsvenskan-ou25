"""Safety audit for the V2-B overlay and forward log. 0 API calls.

Fails loudly if V2-B changes V1 probabilities, allows a cold-start fixture to
become playable, or freezes a forward bet outside the fixed V2-B rules.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
V1=ROOT/"data"/"allsvenskan_live_ou25.csv"
V2=ROOT/"data"/"allsvenskan_live_v2_b.csv"
LOG=ROOT/"data"/"allsvenskan_v2_b_forward_log.csv"


def num(s): return pd.to_numeric(s,errors="coerce")


def main():
    errors=[]; warnings=[]
    if not V1.exists() or not V2.exists():
        warnings.append("Livefiler saknas; inget att jämföra ännu.")
    else:
        a=pd.read_csv(V1); b=pd.read_csv(V2)
        if len(a)!=len(b): errors.append(f"V1/V2 antal live-rader skiljer: {len(a)} vs {len(b)}")
        if "fixture_id" in a and "fixture_id" in b:
            x=a[["fixture_id","p_over25"]].merge(b[["fixture_id","p_over25","v2_b_eligible","v2_b_decision","min_2026_match_no","best_over25_odds"]],on="fixture_id",suffixes=("_v1","_v2"),how="outer",indicator=True)
            if (x._merge!="both").any(): errors.append("V1/V2 fixture-set skiljer sig.")
            d=(num(x.p_over25_v1)-num(x.p_over25_v2)).abs()
            if (d.fillna(0)>1e-10).any(): errors.append("V2-B har ändrat minst en V1-sannolikhet.")
            eligible=x.v2_b_eligible.astype(str).str.lower().isin(["true","1"])
            minno=num(x.min_2026_match_no)
            if ((~eligible)&(minno>=6)).any() or (eligible&(minno<6)).any(): errors.append("V2-behörighet stämmer inte med match-6-regeln.")
            if ((~eligible)&x.v2_b_decision.isin(["SPELA","VÄNTA","SAKNAR ODDS"])).any(): errors.append("Cold-start-match har släppts igenom som V2-signal.")

    if LOG.exists():
        try: log=pd.read_csv(LOG)
        except pd.errors.EmptyDataError: log=pd.DataFrame()
        if len(log):
            if log.record_id.astype(str).duplicated().any(): errors.append("Duplicerade record_id i V2-B-loggen.")
            bets=log[log.record_type=="BET"].copy()
            if len(bets):
                if (num(bets.min_2026_match_no)<6).any(): errors.append("Fryst V2-B BET före match 6.")
                if (~num(bets.p_over25).between(55.0,60.0,inclusive="left")).any(): errors.append("Fryst V2-B BET utanför 55-60%.")
                if (num(bets.observed_odds)<1.85).any(): errors.append("Fryst V2-B BET under odds 1.85.")

    print("V2-B INVARIANT AUDIT")
    print("="*70)
    for w in warnings: print("WARN:",w)
    if errors:
        for e in errors: print("ERROR:",e)
        raise SystemExit(1)
    print("OK: V2-B håller sina frysta invariants.")

if __name__=="__main__": main()
