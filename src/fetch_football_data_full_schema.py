"""Fetch Football-Data's Sweden CSV without projecting away any columns.

Purpose: determine whether the upstream SWE.csv actually contains O/U 2.5 odds.
This is a public Football-Data request, not OddsPapi, so it consumes 0 OddsPapi calls.
The existing allsvenskan_raw.csv is NOT modified.
"""
from io import StringIO
from pathlib import Path
import re
import pandas as pd
import requests

ROOT=Path(__file__).resolve().parent.parent
URL="https://www.football-data.co.uk/new/SWE.csv"
OUT=ROOT/"data"/"football_data_swe_full.csv"
SCHEMA=ROOT/"data"/"football_data_swe_schema.csv"


def main():
    r=requests.get(URL,timeout=30)
    r.raise_for_status()
    df=pd.read_csv(StringIO(r.text))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(OUT,index=False)
    rows=[]
    for c in df.columns:
        v=df[c]
        rows.append({"column":c,"dtype":str(v.dtype),"non_null":int(v.notna().sum()),"example":str(v.dropna().iloc[0]) if v.notna().any() else ""})
    pd.DataFrame(rows).to_csv(SCHEMA,index=False)
    ou=[c for c in df.columns if "2.5" in str(c).lower().replace(" ","") or re.search(r"(?:over|under).?25",str(c).lower().replace(" ",""))]
    print("FOOTBALL-DATA SWEDEN FULL-SCHEMA AUDIT")
    print("="*80)
    print(f"Rader: {len(df)} | Kolumner: {len(df.columns)}")
    print("\nAlla kolumner:")
    print(", ".join(map(str,df.columns)))
    print("\nO/U 2.5-liknande kolumner:",", ".join(ou) if ou else "INGA")
    if "Season" in df.columns:
        print("\nRader per säsong:")
        print(pd.to_numeric(df["Season"],errors="coerce").value_counts().sort_index().tail(6).to_string())
    print("\nFull upstream-fil:",OUT)
    print("Schema:",SCHEMA)
    if not ou:
        print("\nSLUTSATS: den publika Sweden-källan verkar inte leverera O/U 2.5-odds. Då ska vi inte försöka konstruera historiska odds ur resultatfilen.")

if __name__=="__main__": main()
