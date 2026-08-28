from pathlib import Path
import subprocess
import sys
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent.parent
SCRIPT=ROOT/"src"/"v2_sandbox.py"
RESULT=ROOT/"data"/"allsvenskan_v2_experiments.csv"

st.set_page_config(page_title="V2-sandlåda",page_icon="🧫",layout="wide")
st.title("🧫 V2-sandlåda")
st.warning("Explorativ miljö. Resultaten får inte ändra den frysta V1-regeln eller räknas som forward-test.")
st.caption("Här testar vi cold-start och kalibreringsidéer separat från V1. 0 API-anrop.")

if st.button("🧪 Kör V2-experiment",use_container_width=True):
    with st.spinner("Kör experiment…"):
        r=subprocess.run([sys.executable,str(SCRIPT)],cwd=str(ROOT),capture_output=True,text=True)
    if r.returncode==0: st.success("V2-experimenten är klara.")
    else: st.error("Experimentet misslyckades.")
    with st.expander("Körlogg",expanded=r.returncode!=0): st.code((r.stdout+"\n"+r.stderr).strip())

if RESULT.exists():
    df=pd.read_csv(RESULT)
    show=df.copy()
    for c in ["mean_prediction","actual_over_rate","brier_skill_score"]: show[c]=pd.to_numeric(show[c],errors="coerce")*100
    st.subheader("Experimentjämförelse")
    st.dataframe(show.rename(columns={"experiment":"Experiment","description":"Beskrivning","matches":"Matcher","mean_prediction":"Snittpred. %","actual_over_rate":"Faktisk Over %","brier":"Brier","baseline_brier":"Baslinje Brier","brier_skill_score":"Skill %"}),use_container_width=True,hide_index=True,column_config={"Snittpred. %":st.column_config.NumberColumn(format="%.1f%%"),"Faktisk Over %":st.column_config.NumberColumn(format="%.1f%%"),"Brier":st.column_config.NumberColumn(format="%.4f"),"Baslinje Brier":st.column_config.NumberColumn(format="%.4f"),"Skill %":st.column_config.NumberColumn(format="%+.2f%%")})
    chart=show.set_index("experiment")[["brier_skill_score"]].rename(columns={"brier_skill_score":"Brier skill %"})
    st.bar_chart(chart)
    st.info("Shrink-experimenten använder 2026 års slutliga basfrekvens och är därför endast diagnostiska. De är inte giltiga som läckagefria forward-modeller. Nästa V2-steg blir att göra eventuell kalibrering walk-forward om resultaten motiverar det.")
else:
    st.info("Kör experimentet för att skapa första V2-jämförelsen.")
