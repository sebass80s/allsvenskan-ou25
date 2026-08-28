from pathlib import Path
import subprocess
import sys
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent.parent
AUDIT_SCRIPT=ROOT/"src"/"historical_ou25_odds_audit.py"
BACKTEST_SCRIPT=ROOT/"src"/"v2_b_historical_odds_backtest.py"
AUDIT=ROOT/"data"/"allsvenskan_historical_ou25_odds_audit.csv"
SUMMARY=ROOT/"data"/"allsvenskan_v2_b_historical_odds_summary.csv"
DETAIL=ROOT/"data"/"allsvenskan_v2_b_historical_odds_detail.csv"

st.set_page_config(page_title="Historiska O/U-odds",page_icon="📚",layout="wide")
st.title("📚 Historiska O/U 2.5-odds")
st.caption("V2-B marknadsdiagnostik • 0 OddsPapi-anrop • ändrar inte V1 eller forward-test")
st.warning("Historisk diagnostik är inte forward-test. Jämför oddsserier för robusthet, inte för att välja den som råkar ge högst ROI.")

c1,c2=st.columns(2)
with c1: run_audit=st.button("🔎 Inventera oddsdata",use_container_width=True)
with c2: run_bt=st.button("🧮 Kör historiskt V2-B oddsbacktest",use_container_width=True)

for clicked,script,label in [(run_audit,AUDIT_SCRIPT,"Odds-inventering"),(run_bt,BACKTEST_SCRIPT,"Historiskt oddsbacktest")]:
    if clicked:
        r=subprocess.run([sys.executable,str(script)],cwd=str(ROOT),capture_output=True,text=True)
        if r.returncode==0: st.success(f"{label} klar.")
        else: st.error(f"{label} misslyckades.")
        with st.expander("Körlogg",expanded=True): st.code((r.stdout+"\n"+r.stderr).strip())

if AUDIT.exists():
    a=pd.read_csv(AUDIT)
    st.divider(); st.subheader("Oddsdatans täckning")
    focus=a[(pd.to_numeric(a["season"],errors="coerce").isin([2024,2025,2026])) & (pd.to_numeric(a["non_null"],errors="coerce")>0)].copy()
    if len(focus): st.dataframe(focus,use_container_width=True,hide_index=True)
    else: st.info("Ingen O/U 2.5-oddsdata hittades för 2024–2026 i den lokala råfilen.")

if SUMMARY.exists():
    try: s=pd.read_csv(SUMMARY)
    except pd.errors.EmptyDataError: s=pd.DataFrame()
    st.divider(); st.subheader("V2-B mot historiska marknadsodds")
    if s.empty:
        st.info("Ingen användbar standardiserad Over 2.5-oddsserie hittades i råfilen.")
    else:
        show=s.copy()
        for c in ["win_rate","mean_model_p","mean_market_implied_p","mean_no_vig_over_p"]:
            if c in show.columns: show[c]=pd.to_numeric(show[c],errors="coerce")*100
        st.dataframe(show,use_container_width=True,hide_index=True,column_config={
            "win_rate":st.column_config.NumberColumn("Vinst %",format="%.1f%%"),
            "roi_pct":st.column_config.NumberColumn("ROI %",format="%+.1f%%"),
            "profit_units":st.column_config.NumberColumn("Profit u",format="%+.2f"),
            "mean_model_p":st.column_config.NumberColumn("Modell %",format="%.1f%%"),
            "mean_market_implied_p":st.column_config.NumberColumn("Marknad implied %",format="%.1f%%"),
            "mean_no_vig_over_p":st.column_config.NumberColumn("No-vig Over %",format="%.1f%%"),
            "mean_model_edge_pp":st.column_config.NumberColumn("Modell-edge pp",format="%+.2f"),
        })
        pooled=s[s["season"].astype(str).eq("POOLED")].copy()
        if len(pooled):
            st.markdown("#### Poolat per oddsserie")
            st.bar_chart(pooled.set_index("odds_source")[["roi_pct"]].rename(columns={"roi_pct":"ROI %"}))
        st.caption("Spelvillkoren är frysta: båda lagen match 6+, modell 55–60 %, historiskt Over 2.5-odds minst 1.85.")

if DETAIL.exists():
    st.caption(f"Detaljfil: {DETAIL.name}")
