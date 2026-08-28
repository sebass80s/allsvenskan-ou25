from pathlib import Path
import subprocess
import sys
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent.parent
SANDBOX_SCRIPT=ROOT/"src"/"v2_sandbox.py"
CANDIDATE_SCRIPT=ROOT/"src"/"v2_candidate_a.py"
RESULT=ROOT/"data"/"allsvenskan_v2_experiments.csv"
CANDIDATE_SUMMARY=ROOT/"data"/"allsvenskan_v2_candidate_a_summary.csv"
CANDIDATE_CAL=ROOT/"data"/"allsvenskan_v2_candidate_a_calibration.csv"

st.set_page_config(page_title="V2-sandlåda",page_icon="🧫",layout="wide")
st.title("🧫 V2-sandlåda")
st.warning("Explorativ miljö. V1-regeln, live-signalerna och forward-loggen ändras inte.")
st.caption("Här testar vi V2-idéer separat från V1. All diagnostik på denna sida gör 0 API-anrop.")

c1,c2=st.columns(2)
with c1:
    run_sandbox=st.button("🧪 Kör explorativa V2-experiment",use_container_width=True)
with c2:
    run_candidate=st.button("🔬 Kör V2 Candidate A walk-forward",use_container_width=True)

for clicked,script,label in [
    (run_sandbox,SANDBOX_SCRIPT,"V2-experimenten"),
    (run_candidate,CANDIDATE_SCRIPT,"V2 Candidate A"),
]:
    if clicked:
        with st.spinner(f"Kör {label}…"):
            r=subprocess.run([sys.executable,str(script)],cwd=str(ROOT),capture_output=True,text=True)
        if r.returncode==0: st.success(f"{label} är klara.")
        else: st.error(f"{label} misslyckades.")
        with st.expander("Körlogg",expanded=True): st.code((r.stdout+"\n"+r.stderr).strip())

if CANDIDATE_SUMMARY.exists():
    st.divider(); st.subheader("🔬 V2 Candidate A, läckagefri walk-forward")
    st.caption("Candidate A: båda lagen måste ha nått match 6. Därefter = 50 % V1 + 50 % ligans Over-frekvens som var känd före avspark.")
    s=pd.read_csv(CANDIDATE_SUMMARY)
    show=s.copy()
    for c in ["mean_prediction","actual_over_rate","brier_skill_score"]:
        show[c]=pd.to_numeric(show[c],errors="coerce")*100
    st.dataframe(show.rename(columns={"model":"Modell","matches":"Matcher","mean_prediction":"Snittpred. %","actual_over_rate":"Faktisk Over %","brier":"Brier","baseline_brier":"Baslinje Brier","brier_skill_score":"Skill %","delta_brier_vs_v1_same_matches":"Δ Brier mot V1"}),use_container_width=True,hide_index=True,column_config={"Snittpred. %":st.column_config.NumberColumn(format="%.1f%%"),"Faktisk Over %":st.column_config.NumberColumn(format="%.1f%%"),"Brier":st.column_config.NumberColumn(format="%.4f"),"Baslinje Brier":st.column_config.NumberColumn(format="%.4f"),"Skill %":st.column_config.NumberColumn(format="%+.2f%%"),"Δ Brier mot V1":st.column_config.NumberColumn(format="%+.4f")})
    if len(s)>=2:
        v1=s[s["model"]=="V1 same matches"].iloc[0]
        v2=s[s["model"]=="V2 Candidate A"].iloc[0]
        a,b,c,d=st.columns(4)
        a.metric("Matcher",int(v2["matches"]))
        b.metric("V1 Brier",f"{v1['brier']:.4f}")
        c.metric("V2-A Brier",f"{v2['brier']:.4f}",delta=f"{v2['brier']-v1['brier']:+.4f}",delta_color="inverse")
        d.metric("V2-A Skill",f"{v2['brier_skill_score']*100:+.2f}%")
    if CANDIDATE_CAL.exists():
        cal=pd.read_csv(CANDIDATE_CAL); cal["mean_prediction"]*=100; cal["actual_over_rate"]*=100
        st.markdown("#### Candidate A kalibrering")
        st.dataframe(cal.rename(columns={"probability_band":"Intervall","matches":"Matcher","mean_prediction":"Snittpred. %","actual_over_rate":"Faktisk Over %","brier":"Brier"}),use_container_width=True,hide_index=True)
        st.bar_chart(cal.set_index("probability_band")[["mean_prediction","actual_over_rate"]].rename(columns={"mean_prediction":"Modell","actual_over_rate":"Utfall"}))
    st.info("Candidate A är historiskt walk-forward-testad utan framtida 2026-information. Den är fortfarande en V2-kandidat, inte en ny live- eller spelregel.")

if RESULT.exists():
    st.divider(); st.subheader("Explorativ experimentjämförelse")
    df=pd.read_csv(RESULT); show=df.copy()
    for c in ["mean_prediction","actual_over_rate","brier_skill_score"]: show[c]=pd.to_numeric(show[c],errors="coerce")*100
    st.dataframe(show.rename(columns={"experiment":"Experiment","description":"Beskrivning","matches":"Matcher","mean_prediction":"Snittpred. %","actual_over_rate":"Faktisk Over %","brier":"Brier","baseline_brier":"Baslinje Brier","brier_skill_score":"Skill %"}),use_container_width=True,hide_index=True)
    st.bar_chart(show.set_index("experiment")[["brier_skill_score"]].rename(columns={"brier_skill_score":"Brier skill %"}))
    st.caption("Shrink-resultaten här använder slutlig 2026-basfrekvens och är bara hypotesgenerering. Candidate A ovan är den läckagefria versionen.")
