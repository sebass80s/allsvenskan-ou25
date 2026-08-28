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

st.set_page_config(page_title="Offline-kontroller", page_icon="🧪", layout="wide")
st.title("🧪 Offline-kontroller")
st.caption(
    "Datakvalitet och walk-forward-backtest för V1. "
    "Sidan använder endast lokala filer och gör 0 API-anrop."
)


def run_script(script):
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )


c1, c2 = st.columns(2)
with c1:
    run_audit = st.button("🔎 Kör datakvalitetskontroll", use_container_width=True)
with c2:
    run_backtest = st.button("📊 Kör V1 walk-forward-backtest", use_container_width=True)

if run_audit:
    with st.spinner("Kontrollerar historikfilen…"):
        result = run_script(AUDIT_SCRIPT)
    if result.returncode == 0:
        st.success("Datakvalitetskontrollen är klar.")
    else:
        st.error("Datakvalitetskontrollen misslyckades.")
    with st.expander("Körlogg", expanded=result.returncode != 0):
        st.code((result.stdout + "\n" + result.stderr).strip() or "Ingen output")

if run_backtest:
    with st.spinner("Kör walk-forward genom 2026…"):
        result = run_script(BACKTEST_SCRIPT)
    if result.returncode == 0:
        st.success("Backtestet är klart.")
    else:
        st.error("Backtestet misslyckades.")
    with st.expander("Körlogg", expanded=result.returncode != 0):
        st.code((result.stdout + "\n" + result.stderr).strip() or "Ingen output")

st.divider()
st.subheader("Datakvalitet")

if not AUDIT_FILE.exists():
    st.info("Ingen rapport ännu. Kör datakvalitetskontrollen ovan.")
else:
    audit = pd.read_csv(AUDIT_FILE)
    errors = int((audit["severity"] == "ERROR").sum())
    warnings = int((audit["severity"] == "WARN").sum())
    checks_ok = int((audit["severity"] == "OK").sum())

    a1, a2, a3 = st.columns(3)
    a1.metric("OK", checks_ok)
    a2.metric("Varningar", warnings)
    a3.metric("Fel", errors)

    display = audit.rename(columns={
        "check": "Kontroll",
        "severity": "Status",
        "count": "Antal",
        "details": "Detaljer",
    })
    st.dataframe(display, use_container_width=True, hide_index=True)

    if SEASON_FILE.exists():
        seasons = pd.read_csv(SEASON_FILE).rename(columns={
            "Season_num": "Säsong",
            "matches": "Matcher",
            "first_date": "Första match",
            "last_date": "Senaste match",
        })
        st.markdown("#### Säsongstäckning")
        st.dataframe(seasons, use_container_width=True, hide_index=True)

st.divider()
st.subheader("V1 walk-forward-backtest")
st.caption(
    "Varje 2026-match predikteras med enbart tidigare matcher. "
    "V1-zonen 55–60 % är oförändrad och optimeras inte här."
)

if not BACKTEST_FILE.exists():
    st.info("Inget backtest ännu. Kör backtestet ovan.")
else:
    summary = pd.read_csv(BACKTEST_FILE)
    if summary.empty:
        st.warning("Backtestfilen är tom.")
    else:
        row = summary.iloc[0]
        scored = int(row.get("scored_matches", 0))
        zone = int(row.get("zone_matches", 0))
        actual = row.get("overall_actual_over_rate")
        pred = row.get("overall_mean_prediction")
        brier = row.get("overall_brier")

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Predikterade matcher", scored)
        b2.metric("I V1-zonen", zone)
        b3.metric("Faktisk Over 2.5", f"{actual * 100:.1f}%" if pd.notna(actual) else "—")
        b4.metric("Snittprediktion", f"{pred * 100:.1f}%" if pd.notna(pred) else "—")
        b5.metric("Brier", f"{brier:.4f}" if pd.notna(brier) else "—")

        zone_actual = row.get("zone_actual_over_rate")
        zone_pred = row.get("zone_mean_prediction")
        zone_brier = row.get("zone_brier")

        st.markdown("#### Frysta V1-zonen 55–60 %")
        z1, z2, z3 = st.columns(3)
        z1.metric("Faktisk Over 2.5", f"{zone_actual * 100:.1f}%" if pd.notna(zone_actual) else "—")
        z2.metric("Snittprediktion", f"{zone_pred * 100:.1f}%" if pd.notna(zone_pred) else "—")
        z3.metric("Brier", f"{zone_brier:.4f}" if pd.notna(zone_brier) else "—")

    if DETAIL_FILE.exists():
        detail = pd.read_csv(DETAIL_FILE)
        if not detail.empty:
            detail["p_over25"] = pd.to_numeric(detail["p_over25"], errors="coerce") * 100
            detail = detail.rename(columns={
                "date": "Datum",
                "home_team": "Hemma",
                "away_team": "Borta",
                "expected_goals": "Förv. mål",
                "p_over25": "Modell Over %",
                "in_model_zone": "V1-zon",
                "actual_over25": "Faktisk Over",
                "total_goals": "Mål",
                "brier": "Brier",
            })
            with st.expander(f"Visa alla {len(detail)} walk-forward-prediktioner"):
                st.dataframe(
                    detail[["Datum", "Hemma", "Borta", "Förv. mål", "Modell Over %", "V1-zon", "Faktisk Over", "Mål", "Brier"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Förv. mål": st.column_config.NumberColumn(format="%.2f"),
                        "Modell Over %": st.column_config.NumberColumn(format="%.1f%%"),
                        "Brier": st.column_config.NumberColumn(format="%.4f"),
                    },
                )

st.divider()
st.caption(
    "Offline-diagnostiken ändrar inte V1-regeln eller forward-loggen. "
    "Den är till för kvalitetskontroll och utvärdering under speluppehåll."
)
