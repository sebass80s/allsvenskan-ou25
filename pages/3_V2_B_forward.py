from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "data" / "allsvenskan_live_v2_b.csv"
FORWARD = ROOT / "data" / "allsvenskan_v2_b_forward_log.csv"

st.set_page_config(page_title="V2-B Forward", page_icon="🧪", layout="wide")
st.title("🧪 V2-B Forward-test")
st.caption("Candidate B • V1-sannolikheten oförändrad • inga signaler före båda lagens match 6 • samma modellzon 55–60 % • samma oddsgräns 1.85")
st.warning("V2-B är ett separat experiment. V1 är fortsatt fryst och dess historik/logg ändras inte.")

if not LIVE.exists():
    st.info("Ingen V2-B-livefil ännu. Kör den vanliga manuella uppdateringen på startsidan.")
else:
    try: live = pd.read_csv(LIVE)
    except pd.errors.EmptyDataError: live = pd.DataFrame()
    if len(live):
        live["start_time"] = pd.to_datetime(live["start_time"], utc=True, errors="coerce")
        live["Kickoff"] = live["start_time"].dt.tz_convert("Europe/Stockholm")
        for c in ["p_over25","best_over25_odds","home_2026_match_no","away_2026_match_no","min_2026_match_no"]:
            if c in live: live[c] = pd.to_numeric(live[c], errors="coerce")
        eligible = live[live["v2_b_eligible"].astype(str).str.lower().isin(["true","1"])].copy()
        play = live[live["v2_b_decision"] == "SPELA"].copy()
        wait = live[live["v2_b_decision"] == "VÄNTA"].copy()
        cold = live[live["v2_b_decision"] == "COLD START"].copy()
        a,b,c,d = st.columns(4)
        a.metric("Kommande matcher", len(live)); b.metric("V2-behöriga", len(eligible)); c.metric("🟢 SPELA", len(play)); d.metric("Cold start", len(cold))

        def table(x):
            y=x.copy().sort_values("Kickoff")
            y["Datum"]=y["Kickoff"].dt.strftime("%d/%m %H:%M")
            y["Match"]=y["home_team"].astype(str)+" – "+y["away_team"].astype(str)
            y["Lagmatch"] = y["home_2026_match_no"].fillna(0).astype(int).astype(str)+" / "+y["away_2026_match_no"].fillna(0).astype(int).astype(str)
            y["Modell Over %"]=y["p_over25"]; y["Bet365 odds"]=y["best_over25_odds"]; y["Beslut"]=y["v2_b_decision"]
            return y[["Datum","Match","Lagmatch","Modell Over %","Bet365 odds","Beslut"]]

        if len(play):
            st.subheader("🎯 V2-B spel nu")
            st.dataframe(table(play), use_container_width=True, hide_index=True, column_config={"Modell Over %":st.column_config.NumberColumn(format="%.1f%%"),"Bet365 odds":st.column_config.NumberColumn(format="%.2f")})
        else: st.info("Inga V2-B-spel just nu.")
        if len(wait):
            st.markdown("#### 🟡 V2-behöriga, men oddset är under 1.85")
            st.dataframe(table(wait), use_container_width=True, hide_index=True)
        with st.expander(f"Cold-start-blockerade matcher: {len(cold)}"):
            if len(cold): st.dataframe(table(cold), use_container_width=True, hide_index=True)
        with st.expander(f"Alla kommande matcher: {len(live)}"):
            st.dataframe(table(live), use_container_width=True, hide_index=True)

st.divider(); st.subheader("📈 V2-B forward-logg")
if not FORWARD.exists():
    st.info("V2-B-loggen startar vid nästa manuella liveuppdatering. Gamla V1-signaler rekonstrueras inte retroaktivt.")
else:
    try: f=pd.read_csv(FORWARD)
    except pd.errors.EmptyDataError: f=pd.DataFrame()
    if f.empty: st.info("Loggen finns men inga V2-B-signaler har frysts ännu.")
    else:
        for c in ["observed_odds","p_over25","profit","won","min_2026_match_no"]:
            if c in f: f[c]=pd.to_numeric(f[c],errors="coerce")
        f["start_time"]=pd.to_datetime(f["start_time"],utc=True,errors="coerce"); f["Kickoff"]=f["start_time"].dt.tz_convert("Europe/Stockholm")
        bets=f[f.record_type=="BET"].copy(); near=f[f.record_type=="NEAR_MISS"].copy(); done=bets[bets.status=="FINISHED"].copy()
        wins=int(done.won.fillna(0).sum()) if len(done) else 0; profit=float(done.profit.fillna(0).sum()) if len(done) else 0.0; roi=profit/len(done)*100 if len(done) else 0.0
        a,b,c,d,e=st.columns(5); a.metric("V2-B spel",len(bets)); b.metric("Avgjorda",len(done)); c.metric("Vunna",wins); d.metric("Profit",f"{profit:+.2f} u"); e.metric("ROI",f"{roi:+.1f}%")

        def ft(x):
            y=x.copy().sort_values("Kickoff",ascending=False); y["Datum"]=y.Kickoff.dt.strftime("%d/%m %H:%M"); y["Match"]=y.home_team.astype(str)+" – "+y.away_team.astype(str)
            y["Modell %"]=y.p_over25; y["Fryst odds"]=y.observed_odds; y["Min lagmatch"]=y.min_2026_match_no
            y["Resultat"]=y.apply(lambda r: f"{int(r.home_goals)}–{int(r.away_goals)}" if r.status=="FINISHED" and pd.notna(r.home_goals) and pd.notna(r.away_goals) else "—",axis=1)
            y["Utfall"]=y.apply(lambda r:"✅ Vinst" if r.status=="FINISHED" and r.won==1 else "❌ Förlust" if r.status=="FINISHED" and r.won==0 else "⏳ Öppen",axis=1); y["Profit"]=y.profit
            return y[["Datum","Match","Min lagmatch","Modell %","Fryst odds","Resultat","Utfall","Profit"]]
        if len(bets): st.dataframe(ft(bets),use_container_width=True,hide_index=True)
        with st.expander(f"V2-B nästan-spel: {len(near)}"):
            if len(near): st.dataframe(ft(near),use_container_width=True,hide_index=True)

st.divider(); st.markdown("**Fryst V2-B-regel:** ingen signal före båda lagens match 6. Därefter exakt V1-sannolikhet, modellzon 55–60 % och spelbar Over 2.5 från 1.85.")
