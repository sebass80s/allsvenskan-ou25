from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
LIVE_FILE = PROJECT_ROOT / "data" / "allsvenskan_live_ou25.csv"

st.set_page_config(
    page_title="Allsvenskan O/U 2.5 V1",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Allsvenskan O/U 2.5 V1")
st.caption(
    "Fryst forward-test: modellzon 55–60 % Over 2.5 och minsta spelbara odds 1.85."
)

if not LIVE_FILE.exists():
    st.info(
        "Ingen livefil finns ännu. Kör `python3 src/live_ou25_v1.py` först."
    )
    st.stop()

try:
    df = pd.read_csv(LIVE_FILE)
except pd.errors.EmptyDataError:
    st.info("Livefilen är tom. Kör liveanalysen igen.")
    st.stop()

if df.empty:
    st.info("Inga matcher kunde modelleras i senaste körningen.")
    st.stop()

if "start_time" in df.columns:
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["Kickoff"] = df["start_time"].dt.tz_convert("Europe/Stockholm")

play = df[df["decision"] == "SPELA"].copy()
wait = df[df["decision"] == "VÄNTA"].copy()
no_bet = df[df["decision"] == "INGET SPEL"].copy()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Kommande matcher", len(df))
c2.metric("SPELA", len(play))
c3.metric("VÄNTA", len(wait))
c4.metric("INGET SPEL", len(no_bet))


def prepare_table(data):
    out = data.copy()
    out["Modell Over %"] = pd.to_numeric(out["p_over25"], errors="coerce") * 100
    out["Förväntade mål"] = pd.to_numeric(out["expected_goals"], errors="coerce")
    out["Spela från"] = pd.to_numeric(out["min_playable_odds"], errors="coerce")
    out["Bästa odds"] = pd.to_numeric(out["best_over25_odds"], errors="coerce")

    out = out.rename(
        columns={
            "home_team": "Hemma",
            "away_team": "Borta",
            "best_bookmaker": "Bookmaker",
            "decision": "Beslut",
        }
    )

    columns = [
        "Kickoff",
        "Hemma",
        "Borta",
        "Förväntade mål",
        "Modell Over %",
        "Spela från",
        "Bästa odds",
        "Bookmaker",
        "Beslut",
    ]

    return out[columns]


st.subheader("Aktuella beslut")

if len(play):
    st.success(f"{len(play)} match(er) uppfyller V1-regeln just nu.")
else:
    st.info("Inga matcher uppfyller V1-regeln just nu.")

st.dataframe(
    prepare_table(df),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Förväntade mål": st.column_config.NumberColumn(format="%.2f"),
        "Modell Over %": st.column_config.NumberColumn(format="%.1f%%"),
        "Spela från": st.column_config.NumberColumn(format="%.2f"),
        "Bästa odds": st.column_config.NumberColumn(format="%.2f"),
    },
)

st.divider()
st.subheader("V1-regeln")
st.markdown(
    "**SPELA Over 2.5** endast när modellens råa sannolikhet ligger mellan "
    "**55 % och 60 %** och bästa tillgängliga odds är **minst 1.85**. "
    "Om modellen ligger i zonen men oddset är lägre visas **VÄNTA**. "
    "Alla andra matcher är **INGET SPEL**."
)

st.caption(
    "Dashboarden visar ett forward-test. Regeln ska inte ändras efter enstaka utfall."
)
