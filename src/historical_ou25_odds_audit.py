"""Audit historical O/U 2.5 odds columns in local Allsvenskan raw data.

Diagnostic only. 0 API calls. Does not alter source data.
"""
from pathlib import Path
import re
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
HISTORY=ROOT/"data"/"allsvenskan_raw.csv"
OUTPUT=ROOT/"data"/"allsvenskan_historical_ou25_odds_audit.csv"

KNOWN_OVER=["MaxC>2.5","AvgC>2.5","B365C>2.5","PC>2.5","Max>2.5","Avg>2.5","B365>2.5","P>2.5"]
KNOWN_UNDER=["MaxC<2.5","AvgC<2.5","B365C<2.5","PC<2.5","Max<2.5","Avg<2.5","B365<2.5","P<2.5"]


def looks_ou(col):
    s=str(col).lower().replace(" ","")
    return ("2.5" in s) or bool(re.search(r"(?:over|under).?25",s))


def main():
    if not HISTORY.exists(): raise RuntimeError(f"Saknar {HISTORY}")
    df=pd.read_csv(HISTORY)
    df["Season"]=pd.to_numeric(df["Season"],errors="coerce")
    candidates=[c for c in df.columns if looks_ou(c)]
    ordered=[]
    for c in KNOWN_OVER+KNOWN_UNDER+candidates:
        if c in df.columns and c not in ordered: ordered.append(c)
    rows=[]
    for season in sorted(df["Season"].dropna().astype(int).unique()):
        x=df[df["Season"].eq(season)]
        for c in ordered:
            v=pd.to_numeric(x[c],errors="coerce")
            rows.append({"season":season,"column":c,"non_null":int(v.notna().sum()),"coverage_pct":float(v.notna().mean()*100 if len(v) else 0),"mean_odds":float(v.mean()) if v.notna().any() else None,"min_odds":float(v.min()) if v.notna().any() else None,"max_odds":float(v.max()) if v.notna().any() else None})
    out=pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); out.to_csv(OUTPUT,index=False)
    print("ALLSVENSKAN HISTORICAL O/U 2.5 ODDS AUDIT")
    print("="*80)
    print("Identifierade O/U-kolumner:",", ".join(ordered) if ordered else "INGA")
    if ordered:
        focus=out[out.season.isin([2024,2025,2026]) & (out.non_null>0)]
        print("\nTillgänglighet 2024-2026")
        print(focus.to_string(index=False) if len(focus) else "Inga användbara odds i 2024-2026.")
        over=[c for c in KNOWN_OVER if c in df.columns]
        print("\nPrioriterade Over-kolumner som finns:",", ".join(over) if over else "inga kända standardkolumner")
    print("\nRapport:",OUTPUT)

if __name__=="__main__": main()
