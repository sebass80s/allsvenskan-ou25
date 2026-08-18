from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
LIVE_FILE = PROJECT_ROOT / "data" / "allsvenskan_live_ou25.csv"
FORWARD_FILE = PROJECT_ROOT / "data" / "allsvenskan_forward_log.csv"
UPDATE_SCRIPT = PROJECT_ROOT / "src" / "run_live_update.py"

st.set_page_config(
    page_title="Allsvenskan O/U 2.5 V1",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Allsvenskan O/U 2.5 V1")
st.caption("Forward-test • Modellzon 55–60 % • Spela Over 2.5 från odds 1.85")

refresh_col, info_col = st.columns([1, 3])
with refresh_col:
    refresh = st.button("🔄 Uppdatera odds", type="primary", use_container_width=True)
with info_col:
    st.caption(
        "Manuell uppdatering • normalt 2 OddsPapi-anrop • "
        "resultat + forward-logg uppdateras samtidigt • sidan i sig använder 0"
    )

if refresh:
    with st.spinner("Uppdaterar resultat, fixtures, Bet365-odds och forward-test…"):
        result = subprocess.run(
            [sys.executable, str(UPDATE_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )

    if result.returncode == 0:
        st.success("Klart. Resultat, odds och forward-test är uppdaterade.")
    else:
        st.error("Uppdateringen misslyckades. Inga automatiska återförsök görs.")
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

updated_at = pd.Timestamp(LIVE_FILE.stat().st_mtime, unit="s", tz="UTC").tz_convert("Europe/Stockholm")
st.caption(
    f"Senast uppdaterad: {updated_at.strftime('%d/%m/%Y %H:%M:%S')} • "
    "Visad live-data läses lokalt"
)

df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
df["Kickoff"] = df["start_time"].dt.tz_convert("Europe/Stockholm")

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
    out = out.sort_values(
        by=["min_playable_odds", "Kickoff"],
        ascending=[True, True],
        na_position="last",
    )

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
st.subheader("📈 Forward-test V1")

if not FORWARD_FILE.exists():
    st.info(
        "Forward-testloggen skapas vid nästa **Uppdatera odds**. "
        "Från och med då fryses varje spelbar signal permanent."
    )
else:
    try:
        forward = pd.read_csv(FORWARD_FILE)
    except pd.errors.EmptyDataError:
        forward = pd.DataFrame()

    if forward.empty:
        st.info("Forward-testloggen finns men innehåller ännu inga signaler.")
    else:
        for col in ["observed_odds", "p_over25", "profit", "won"]:
            if col in forward.columns:
                forward[col] = pd.to_numeric(forward[col], errors="coerce")

        forward["start_time"] = pd.to_datetime(
            forward["start_time"], utc=True, errors="coerce"
        )
        forward["Kickoff"] = forward["start_time"].dt.tz_convert("Europe/Stockholm")

        bets = forward[forward["record_type"] == "BET"].copy()
        near_misses = forward[forward["record_type"] == "NEAR_MISS"].copy()
        finished = bets[bets["status"] == "FINISHED"].copy()

        wins = int(finished["won"].fillna(0).sum()) if len(finished) else 0
        profit = float(finished["profit"].fillna(0).sum()) if len(finished) else 0.0
        roi = (profit / len(finished) * 100.0) if len(finished) else 0.0

        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("V1-spel", len(bets))
        f2.metric("Avgjorda", len(finished))
        f3.metric("Vunna", wins)
        f4.metric("Profit", f"{profit:+.2f} u")
        f5.metric("ROI", f"{roi:+.1f}%")

        def prepare_forward_table(data: pd.DataFrame) -> pd.DataFrame:
            out = data.copy().sort_values("Kickoff", ascending=False)
            out["Datum"] = out["Kickoff"].dt.strftime("%d/%m %H:%M")
            out["Match"] = out["home_team"] + " – " + out["away_team"]
            out["Modell %"] = out["p_over25"]
            out["Fryst odds"] = out["observed_odds"]
            out["Resultat"] = out.apply(
                lambda r: (
                    f"{int(r['home_goals'])}–{int(r['away_goals'])}"
                    if r.get("status") == "FINISHED"
                    and pd.notna(r.get("home_goals"))
                    and pd.notna(r.get("away_goals"))
                    else "—"
                ),
                axis=1,
            )
            out["Utfall"] = out.apply(
                lambda r: (
                    "✅ Vinst" if r.get("status") == "FINISHED" and r.get("won") == 1
                    else "❌ Förlust" if r.get("status") == "FINISHED" and r.get("won") == 0
                    else "⏳ Öppen"
                ),
                axis=1,
            )
            out["Profit"] = out["profit"]
            return out[[
                "Datum", "Match", "Modell %", "Fryst odds",
                "Resultat", "Utfall", "Profit"
            ]]

        if len(bets):
            st.markdown("#### Frysta V1-spel")
            st.dataframe(
                prepare_forward_table(bets),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Modell %": st.column_config.NumberColumn(format="%.1f%%"),
                    "Fryst odds": st.column_config.NumberColumn(format="%.2f"),
                    "Profit": st.column_config.NumberColumn(format="%+.2f"),
                },
            )
        else:
            st.caption("Inga V1-spel har ännu nått odds 1.85.")

        with st.expander(f"Nästan-spel: {len(near_misses)}"):
            st.caption(
                "Matcher i modellzonen som observerades under odds 1.85. "
                "De räknas inte i V1-ROI men deras utfall sparas för senare tröskelanalys."
            )
            if len(near_misses):
                st.dataframe(
                    prepare_forward_table(near_misses),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Modell %": st.column_config.NumberColumn(format="%.1f%%"),
                        "Fryst odds": st.column_config.NumberColumn(format="%.2f"),
                        "Profit": st.column_config.NumberColumn(format="%+.2f"),
                    },
                )
            else:
                st.caption("Inga nästan-spel loggade ännu.")

st.divider()
st.subheader("V1-regeln")
st.markdown(
    "**SPELA Over 2.5** endast när modellens råa sannolikhet ligger mellan "
    "**55 % och 60 %** och Bet365-oddset är **minst 1.85**. "
    "När en match når detta villkor fryses signalen och oddset permanent i forward-loggen. "
    "Matcher i modellzonen under 1.85 sparas separat som **nästan-spel** och påverkar inte V1-resultatet."
)
st.caption("Forward-test: modellzon och oddsgräns är frysta och ska inte ändras efter enstaka utfall.")
