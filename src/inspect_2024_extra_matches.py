"""Inspect why the 2024 raw Allsvenskan data contains more than 240 rows.
Diagnostic only. Does not modify data. 0 API calls.
"""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
FILE=ROOT/"data"/"allsvenskan_raw.csv"


def main():
    if not FILE.exists(): raise RuntimeError(f"Saknar {FILE}")
    df=pd.read_csv(FILE)
    df["Season"]=pd.to_numeric(df["Season"],errors="coerce")
    df["HG"]=pd.to_numeric(df["HG"],errors="coerce")
    df["AG"]=pd.to_numeric(df["AG"],errors="coerce")
    time=df["Time"].fillna("12:00") if "Time" in df.columns else pd.Series("12:00",index=df.index)
    df["datetime"]=pd.to_datetime(df["Date"].astype(str)+" "+time.astype(str),dayfirst=True,errors="coerce")
    x=df[df.Season==2024].sort_values("datetime").copy()
    print("ALLSVENSKAN 2024 EXTRA-MATCH INSPECTION")
    print("="*72)
    print("Rader i 2024:",len(x),"(ordinarie 16-lags dubbelserie = 240)")
    print("\nSista 15 matcherna kronologiskt")
    cols=[c for c in ["Date","Time","Home","Away","HG","AG"] if c in x.columns]
    print(x.tail(15)[cols].to_string(index=False))
    print("\nLag med annat än 30 matcher i filen")
    counts=pd.concat([x.Home,x.Away]).value_counts().sort_values(ascending=False)
    abnormal=counts[counts!=30]
    print(abnormal.to_string() if len(abnormal) else "Inga")
    if len(abnormal):
        teams=set(abnormal.index.astype(str))
        suspect=x[x.Home.astype(str).isin(teams)|x.Away.astype(str).isin(teams)]
        print("\nAlla 2024-matcher för lag med avvikande matchantal")
        print(suspect[cols].to_string(index=False))
    print("\nOBS: skriptet identifierar bara avvikelsen. Radera/ändra inga rader innan vi verifierat vilka matcher som är kval/playoff.")

if __name__=="__main__": main()
