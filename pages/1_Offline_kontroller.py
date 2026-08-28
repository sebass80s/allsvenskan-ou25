from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_SCRIPT = PROJECT_ROOT / "src" / "audit_data.py"
BACKTEST_SCRIPT = PROJECT_ROOT / "src" / "backtest_v1.py"
AUDIT_FILE = PROJECT_ROOT / "data" / "allsvenskan_data_quality.csv"
SEASON_FILE = PROJECT_ROOT / "data" / "allsvenskan_data_quality_summary.csv"
BACKTEST_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_summary.csv"
DETAIL_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_v1.csv"
CALIBRATION_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_calibration.csv"
MONTHLY_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_monthly.csv"
MISSING_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_missing.csv"

st.set_page_config(page_title="Offline-kontroller", page_icon="🧪", layout="wide")
st.title("🧪 Offline-kontroller")
st.caption("Datakvalitet och läckagefritt walk-forward-backtest. Endast lokala filer, 0 API-anrop.")

def run_script(script):
    return subprocess.run([sys.executable, str(script)], cwd=str(PROJECT_ROOT), capture_output=True, text=True)

c1, c2 = st.columns(2)
with c1: run_audit = st.button("🔎 Kör datakvalitetskontroll", use_container_width=True)
with c2: run_backtest = st.button("📊 Kör utökad V1-diagnostik", use_container_width=True)
for clicked, script, label in [(run_audit, AUDIT_SCRIPT, "Datakvalitetskontrollen"), (run_backtest, BACKTEST_SCRIPT, "V1-diagnostiken")]:
    if clicked:
        with st.spinner(f"Kör {label.lower()}…"): result = run_script(script)
        (st.success if result.returncode == 0 else st.error)(f"{label} är klar." if result.returncode == 0 else f"{label} misslyckades.")
        with st.expander("Körlogg", expanded=result.returncode != 0): st.code((result.stdout + "\n" + result.stderr).strip() or "Ingen output")

st.divider(); st.subheader("Datakvalitet")
if AUDIT_FILE.exists():
    audit = pd.read_csv(AUDIT_FILE); errors = int((audit.severity == "ERROR").sum()); warnings = int((audit.severity == "WARN").sum())
    a1,a2,a3=st.columns(3); a1.metric("OK", int((audit.severity=="OK").sum())); a2.metric("Varningar", warnings); a3.metric("Fel", errors)
    st.dataframe(audit.rename(columns={"check":"Kontroll","severity":"Status","count":"Antal","details":"Detaljer"}), use_container_width=True, hide_index=True)
    if SEASON_FILE.exists(): st.dataframe(pd.read_csv(SEASON_FILE), use_container_width=True, hide_index=True)
else: st.info("Ingen rapport ännu.")

st.divider(); st.subheader("V1 walk-forward-diagnostik")
st.caption("V1-zonen 55–60 % är fryst. Diagnostiken beskriver modellen, den optimerar inte regeln.")
if BACKTEST_FILE.exists():
    row = pd.read_csv(BACKTEST_FILE).iloc[0]
    cols=st.columns(6)
    vals=[("Prediktioner",int(row.get("scored_matches",0))), ("Utan prediktion",int(row.get("missing_matches",0))), ("V1-zon",int(row.get("zone_matches",0))), ("Faktisk Over",f"{row.get('overall_actual_over_rate')*100:.1f}%"), ("Brier",f"{row.get('overall_brier'):.4f}"), ("Brier skill",f"{row.get('brier_skill_score')*100:+.2f}%")]
    for c,(lab,val) in zip(cols,vals): c.metric(lab,val)
    st.caption(f"Baslinje-Brier: {row.get('baseline_brier'):.4f}. Positiv Brier skill betyder bättre än en konstant prognos med 2026 års faktiska Over-frekvens.")
    z1,z2,z3,z4=st.columns(4); z1.metric("Zon faktisk Over",f"{row.get('zone_actual_over_rate')*100:.1f}%"); z2.metric("Zon snittpred.",f"{row.get('zone_mean_prediction')*100:.1f}%"); z3.metric("Zon Brier",f"{row.get('zone_brier'):.4f}"); z4.metric("Zon skill",f"{row.get('zone_brier_skill_score')*100:+.2f}%")

    if CALIBRATION_FILE.exists():
        st.markdown("#### Kalibrering per sannolikhetsintervall")
        cal=pd.read_csv(CALIBRATION_FILE); cal["mean_prediction"]*=100; cal["actual_over_rate"]*=100
        st.dataframe(cal.rename(columns={"probability_band":"Intervall","matches":"Matcher","mean_prediction":"Snittpred. %","actual_over_rate":"Faktisk Over %","brier":"Brier"}), use_container_width=True, hide_index=True, column_config={"Snittpred. %":st.column_config.NumberColumn(format="%.1f%%"),"Faktisk Over %":st.column_config.NumberColumn(format="%.1f%%"),"Brier":st.column_config.NumberColumn(format="%.4f")})
        chart=cal.set_index("probability_band")[["mean_prediction","actual_over_rate"]].rename(columns={"mean_prediction":"Modell","actual_over_rate":"Utfall"}); st.bar_chart(chart)

    if MONTHLY_FILE.exists():
        st.markdown("#### Utveckling under 2026")
        monthly=pd.read_csv(MONTHLY_FILE); monthly["mean_prediction"]*=100; monthly["actual_over_rate"]*=100
        st.dataframe(monthly.rename(columns={"month":"Månad","matches":"Matcher","mean_prediction":"Snittpred. %","actual_over_rate":"Faktisk Over %","brier":"Brier"}), use_container_width=True, hide_index=True)
        st.line_chart(monthly.set_index("month")[["mean_prediction","actual_over_rate"]].rename(columns={"mean_prediction":"Modell","actual_over_rate":"Utfall"}))

    if MISSING_FILE.exists():
        missing=pd.read_csv(MISSING_FILE)
        st.markdown(f"#### Matcher utan prediktion ({len(missing)})")
        if len(missing): st.dataframe(missing.rename(columns={"date":"Datum","home_team":"Hemma","away_team":"Borta","reason":"Orsak"}), use_container_width=True, hide_index=True)
        else: st.caption("Alla 2026-matcher fick en prediktion.")

    if DETAIL_FILE.exists():
        detail=pd.read_csv(DETAIL_FILE); detail["p_over25"]*=100
        with st.expander(f"Visa alla {len(detail)} prediktioner"):
            st.dataframe(detail, use_container_width=True, hide_index=True)
else: st.info("Inget backtest ännu. Kör diagnostiken ovan.")

st.divider(); st.caption("Offline-diagnostiken ändrar inte V1-regeln, liveoddsen eller forward-loggen.")
