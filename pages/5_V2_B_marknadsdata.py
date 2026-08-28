from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
SNAPS = ROOT / "data" / "allsvenskan_v2_b_market_snapshots.csv"
CLV_DETAIL = ROOT / "data" / "allsvenskan_v2_b_clv_detail.csv"
CLV_SUMMARY = ROOT / "data" / "allsvenskan_v2_b_clv_summary.csv"

st.set_page_config(page_title="V2-B Marknadsdata", page_icon="📈", layout="wide")
st.title("📈 V2-B marknadsdata & CLV")
st.caption("Egen prospektiv Bet365-historik från manuella uppdateringar • 0 extra API-anrop utöver den vanliga livekörningen")
st.info("Closing-proxy betyder sista manuella Bet365-snapshot före kickoff. Ju närmare kickoff sista uppdateringen ligger, desto bättre approximation av closing line.")

if not SNAPS.exists():
    st.warning("Inga marknadssnapshots ännu. Nästa vanliga 'Uppdatera odds' börjar bygga historiken.")
else:
    try:
        s = pd.read_csv(SNAPS)
    except pd.errors.EmptyDataError:
        s = pd.DataFrame()
    if s.empty:
        st.info("Snapshotfilen finns men är tom.")
    else:
        s["snapshot_at"] = pd.to_datetime(s["snapshot_at"], utc=True, errors="coerce")
        s["start_time"] = pd.to_datetime(s["start_time"], utc=True, errors="coerce")
        s["best_over25_odds"] = pd.to_numeric(s["best_over25_odds"], errors="coerce")
        s["Min till kickoff"] = (s["start_time"] - s["snapshot_at"]).dt.total_seconds() / 60
        a,b,c,d = st.columns(4)
        a.metric("Snapshots", len(s))
        b.metric("Fixtures", s["fixture_id"].astype(str).nunique())
        c.metric("Med odds", int(s["best_over25_odds"].notna().sum()))
        d.metric("Snapshot-tillfällen", s["snapshot_at"].nunique())

        latest = s.sort_values("snapshot_at").groupby("fixture_id", as_index=False).tail(1).copy()
        latest["Match"] = latest["home_team"].astype(str) + " – " + latest["away_team"].astype(str)
        latest["Snapshot"] = latest["snapshot_at"].dt.tz_convert("Europe/Stockholm").dt.strftime("%d/%m %H:%M")
        latest["Kickoff"] = latest["start_time"].dt.tz_convert("Europe/Stockholm").dt.strftime("%d/%m %H:%M")
        st.subheader("Senaste snapshot per fixture")
        st.dataframe(latest[["Snapshot","Kickoff","Match","p_over25","best_over25_odds","v2_b_decision","Min till kickoff"]],
                     use_container_width=True, hide_index=True,
                     column_config={"p_over25":st.column_config.NumberColumn("Modell %",format="%.1f%%"),
                                    "best_over25_odds":st.column_config.NumberColumn("Bet365 Over",format="%.2f"),
                                    "Min till kickoff":st.column_config.NumberColumn(format="%.0f")})

st.divider(); st.subheader("CLV för frysta V2-B-spel")
if not CLV_SUMMARY.exists():
    st.info("Ingen CLV-rapport ännu. Den skapas automatiskt när det finns både frysta V2-B-spel och senare pre-kickoff snapshots.")
else:
    try:
        summary = pd.read_csv(CLV_SUMMARY)
    except pd.errors.EmptyDataError:
        summary = pd.DataFrame()
    if summary.empty:
        st.info("CLV-rapporten är ännu tom.")
    else:
        r = summary.iloc[0]
        a,b,c,d = st.columns(4)
        a.metric("Spel med close-proxy", int(r.get("bets_with_closing_proxy",0)))
        a.caption(f"av {int(r.get('bets',0))} frysta spel")
        b.metric("Mean CLV", f"{r.get('mean_clv_pct', float('nan')):+.2f}%")
        c.metric("Median CLV", f"{r.get('median_clv_pct', float('nan')):+.2f}%")
        pos = r.get("positive_clv_share", float('nan'))
        d.metric("Positiv CLV", f"{pos*100:.1f}%" if pd.notna(pos) else "—")
        mins = r.get("mean_closing_snapshot_minutes_to_kickoff", float('nan'))
        if pd.notna(mins): st.caption(f"Sista snapshot låg i snitt {mins:.0f} minuter före kickoff.")

if CLV_DETAIL.exists():
    try: d = pd.read_csv(CLV_DETAIL)
    except pd.errors.EmptyDataError: d = pd.DataFrame()
    if len(d):
        for c in ["observed_odds","closing_proxy_odds","clv_pct","clv_prob_pp"]:
            if c in d: d[c] = pd.to_numeric(d[c], errors="coerce")
        d["Match"] = d["home_team"].astype(str)+" – "+d["away_team"].astype(str)
        st.dataframe(d[["Match","observed_odds","closing_proxy_odds","clv_pct","clv_prob_pp","closing_snapshot_minutes_to_kickoff"]],
                     use_container_width=True, hide_index=True,
                     column_config={"observed_odds":st.column_config.NumberColumn("Fryst odds",format="%.2f"),
                                    "closing_proxy_odds":st.column_config.NumberColumn("Closing-proxy",format="%.2f"),
                                    "clv_pct":st.column_config.NumberColumn("CLV %",format="%+.2f%%"),
                                    "clv_prob_pp":st.column_config.NumberColumn("CLV pp",format="%+.2f"),
                                    "closing_snapshot_minutes_to_kickoff":st.column_config.NumberColumn("Min före KO",format="%.0f")})

st.divider()
st.caption("CLV mäter prisrörelse, inte matchresultat. Positiv CLV över ett växande sample är ett viktigt komplement till ROI och Brier.")
