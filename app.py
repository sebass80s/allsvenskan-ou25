from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
LIVE_FILE = PROJECT_ROOT / "data" / "allsvenskan_live_ou25.csv"
LIVE_SCRIPT = PROJECT_ROOT / "src" / "live_ou25_v1.py"

st.set_page_config(
    page_title="Allsvenskan O/U 2.5 V1",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Allsvenskan O/U 2.5 V1")
st.caption("Forward-test • Modellzon 55–60 % • Spela Over 2.5 från odds 1.85")

# Manuell uppdatering: inga API-anrop sker bara för att dashboarden öppnas
# eller laddas om. En normal uppdatering använder 2 OddsPapi-anrop:
# 1 fixtures + 1 Bet365 odds.
refresh_col, info_col = st.columns([1, 3])
with refresh_col:
    refresh = st.button("🔄 Uppdatera odds", type="primary", use_container_width=True)
with info_col:
    st.caption("Manuell uppdatering • kostar normalt 2 API-anrop • sidan i sig använder 0")

if refresh:
    with st.spinner("Hämtar fixtures och Bet365-odds…"):
        result = subprocess.run(
            [sys.executable, str(LIVE_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )

    if result.returncode == 0:
        st.success("Oddsen är uppdaterade. 2 API-anrop användes normalt.")
    else:
        st.error("Uppdateringen misslyckades. Inga fler automatiska försök görs.")
        with st.expander("Visa felmeddelande"):
            st.code(result.stderr or result.stdout or "Okänt fel")

if not LIVE_FILE.exists():
    st.info("Ingen livefil finns ännu. Klicka på **Uppdatera odds** ovan.")
    st.stop()

try:
    df = pd.read_csv(LIVE_FILE)
except pd.errors.EmptyDataError:
    st.info("Livefilen är tom. Klicka på **Uppdatera odds** när du vill försöka igen.")
    st.stop()

if df.empty:
    st.info("Inga matcher kunde modelleras i senaste körningen.")
    st.stop()

# Visa när den lokala livefilen senast uppdaterades, utan API-anrop.
updated_at = pd.Timestamp(LIVE_FILE.stat().st_mtime, unit="s", tz="UTC").tz_convert("Europe/Stockholm")
st.caption(f"Senast uppdaterad: {updated_at.strftime('%d/%m/%Y %H:%M:%S')} • Visad data läses lokalt")

# Tider i svensk lokal tid.
df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
df["Kickoff"] = df["start_time"].dt.tz_convert("Europe/Stockholm")

# CSV-filen innehåller p_over25 i procent (t.ex. 55.353), inte 0.55353.
for col in ["p_over25", "expected_goals", "min_playable_odds", "best_over25_odds"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

play = df[df["decision"] == "SPELA"].copy()
wait = df[df["decision"] == "VÄNTA"].copy()
missing = df[df["decision"] == "SAKNAR ODDS"].copy()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Matcher", len(df))
c2.metric("🟢 SPELA", len(play))
c3.metric("🟡 VÄNTA", len(wait))
c4.metric("🔵 Saknar odds", len(missing))


def prepare_table(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    out["Match"] = out["home_team"] + " – " + out["away_team"]
    out["Datum"] = out["Kickoff"].dt.strftime("%d/%m %H:%M")
    out["Modell Over %"] = out["p_over25"]
    out["Förv. mål"] = out["expected_goals"]
    out["Spela från"] = out["min_playable_odds"].apply(
        lambda value: f"{value:.2f}" if pd.notna(value) else "Ej spelzon"
    )
    out["Bet365 odds"] = out["best_over25_odds"]
    out["Bookmaker"] = out["best_bookmaker"].fillna("—")
    out["Beslut"] = out["decision"].map({
        "SPELA": "🟢 SPELA",
        "VÄNTA": "🟡 VÄNTA",
        "SAKNAR ODDS": "🔵 SAKNAR ODDS",
        "INGET SPEL": "⚪ INGET SPEL",
    }).fillna(out["decision"])

    return out[[
        "Datum", "Match", "Modell Over %", "Förv. mål",
        "Spela från", "Bet365 odds", "Bookmaker", "Beslut"
    ]]


column_config = {
    "Modell Over %": st.column_config.NumberColumn(format="%.1f%%"),
    "Förv. mål": st.column_config.NumberColumn(format="%.2f"),
    "Spela från": st.column_config.TextColumn(),
    "Bet365 odds": st.column_config.NumberColumn(format="%.2f"),
}

st.subheader("🎯 Spelläget")

if len(play):
    st.success(f"{len(play)} match(er) uppfyller V1-regeln just nu.")
    st.dataframe(
        prepare_table(play),
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )
else:
    st.info("Inga spel just nu. Vi väntar på rätt kombination av modellsignal och odds.")

if len(wait):
    st.markdown("#### 🟡 I modellzonen – oddset är för lågt")
    st.dataframe(
        prepare_table(wait),
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )

if len(missing):
    st.markdown("#### 🔵 I modellzonen – odds saknas ännu")
    st.dataframe(
        prepare_table(missing),
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )

with st.expander(f"Visa alla {len(df)} kommande matcher"):
    st.dataframe(
        prepare_table(df),
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
    )

st.divider()
st.subheader("V1-regeln")
st.markdown(
    "**SPELA Over 2.5** endast när modellens råa sannolikhet ligger mellan "
    "**55 % och 60 %** och Bet365-oddset är **minst 1.85**. "
    "Om modellen ligger i zonen men oddset är lägre visas **VÄNTA**. "
    "Om modellen ligger i zonen men marknaden ännu saknar odds visas **SAKNAR ODDS**."
)
st.caption("Forward-test: regeln ska inte ändras efter enstaka utfall.")
