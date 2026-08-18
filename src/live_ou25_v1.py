import time
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "allsvenskan_raw.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "allsvenskan_live_ou25.csv"
ENV_FILE = PROJECT_ROOT / ".env"

TOURNAMENT_ID = 40
FOOTBALL_DATA_URL = "https://www.football-data.co.uk/new/SWE.csv"

# API-budgetläge: använd bara Bet365 i den normala livekörningen.
# Det ger 2 OddsPapi-anrop per körning totalt: 1 fixtures + 1 odds.
BOOKMAKERS = ["bet365"]
MARKET_OU25 = "1010"

MODEL_MIN = 0.55
MODEL_MAX = 0.60
MIN_PLAYABLE_ODDS = 1.85

# OddsPapi -> historical CSV names.
NAME_MAP = {
    "AIK": "AIK",
    "BK Hacken": "Hacken",
    "Degerfors IF": "Degerfors",
    "Djurgardens IF": "Djurgarden",
    "IF Brommapojkarna": "Brommapojkarna",
    "IF Elfsborg": "Elfsborg",
    "IFK Goteborg": "Goteborg",
    "IFK Norrkoping": "Norrkoping",
    "IK Sirius": "Sirius",
    "GAIS": "GAIS",
    "Halmstads BK": "Halmstad",
    "Hammarby IF": "Hammarby",
    "Kalmar FF": "Kalmar",
    "Malmo FF": "Malmo FF",
    "Mjallby AIF": "Mjallby",
    "Vasteras SK": "Vasteras SK",
}


def read_api_key() -> str:
    if not ENV_FILE.exists():
        raise RuntimeError(
            "Saknar .env. Skapa filen i projektroten med "
            "ODDSPAPI_API_KEY=din_nyckel"
        )

    with open(ENV_FILE, "r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("ODDSPAPI_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value:
                    return value

    raise RuntimeError("Kunde inte läsa ODDSPAPI_API_KEY från .env")


def update_history_from_football_data() -> int:
    """Append newly completed 2026 Allsvenskan matches to local history.

    This uses Football-Data's public Sweden CSV and therefore consumes no
    OddsPapi quota. Existing historical rows are left untouched.
    """
    if not HISTORY_FILE.exists():
        raise RuntimeError(
            f"Saknar historikfilen {HISTORY_FILE}. "
            "Kopiera in data/allsvenskan_raw.csv först."
        )

    try:
        response = requests.get(FOOTBALL_DATA_URL, timeout=30)
        response.raise_for_status()
        fresh = pd.read_csv(StringIO(response.text))
    except Exception as exc:
        print(f"Historikuppdatering hoppades över: {exc}")
        return 0

    required = {"League", "Season", "Date", "Home", "Away", "HG", "AG"}
    if not required.issubset(fresh.columns):
        print("Historikuppdatering hoppades över: oväntade kolumner i SWE.csv")
        return 0

    fresh = fresh[
        (fresh["League"] == "Allsvenskan")
        & (pd.to_numeric(fresh["Season"], errors="coerce") == 2026)
    ].copy()

    fresh["HG"] = pd.to_numeric(fresh["HG"], errors="coerce")
    fresh["AG"] = pd.to_numeric(fresh["AG"], errors="coerce")
    fresh = fresh.dropna(subset=["HG", "AG"])

    if fresh.empty:
        print("Historikuppdatering: inga färdigspelade 2026-matcher hittades")
        return 0

    existing = pd.read_csv(HISTORY_FILE)
    key_cols = ["Season", "Date", "Home", "Away"]

    existing_keys = set(
        existing[key_cols]
        .astype(str)
        .agg("|".join, axis=1)
    )

    fresh["_key"] = (
        fresh[key_cols]
        .astype(str)
        .agg("|".join, axis=1)
    )
    new_rows = fresh[~fresh["_key"].isin(existing_keys)].drop(columns="_key")

    if new_rows.empty:
        print("Historikuppdatering: 0 nya matcher")
        return 0

    # Anpassa till den befintliga filens schema. Odds- eller övriga kolumner
    # som saknas i den färska filen lämnas tomma; mål/resultat räcker för
    # form- och målmodellen.
    all_columns = list(existing.columns)
    for column in new_rows.columns:
        if column not in all_columns:
            all_columns.append(column)

    existing = existing.reindex(columns=all_columns)
    new_rows = new_rows.reindex(columns=all_columns)

    updated = pd.concat([existing, new_rows], ignore_index=True)
    updated["_sort_dt"] = pd.to_datetime(
        updated["Date"].astype(str) + " " + updated["Time"].fillna("12:00"),
        dayfirst=True,
        errors="coerce",
    )
    updated = updated.sort_values("_sort_dt").drop(columns="_sort_dt")
    updated.to_csv(HISTORY_FILE, index=False)

    print(f"Historikuppdatering: {len(new_rows)} nya färdigspelade matcher")
    return len(new_rows)


def weighted_mean(values, weights):
    return np.average(values, weights=weights) if values else np.nan


def recent_stats(matches, venue=None, n=10):
    if venue is not None:
        matches = [match for match in matches if match["venue"] == venue]

    matches = matches[-n:]
    if not matches:
        return np.nan, np.nan

    weights = np.linspace(1.0, 2.0, len(matches))
    gf = weighted_mean([match["gf"] for match in matches], weights)
    ga = weighted_mean([match["ga"] for match in matches], weights)
    return gf, ga


def get_price(bookmaker_data, outcome_id):
    try:
        market = bookmaker_data["markets"][MARKET_OU25]
        outcome = market["outcomes"][str(outcome_id)]
        player = outcome["players"].get("0")

        if player is None or not player.get("active", False):
            return None

        return player.get("price")
    except (KeyError, TypeError):
        return None


def load_history():
    if not HISTORY_FILE.exists():
        raise RuntimeError(
            f"Saknar historikfilen {HISTORY_FILE}. "
            "Kopiera in data/allsvenskan_raw.csv först."
        )

    history = pd.read_csv(HISTORY_FILE)
    history = history[history["Season"].isin([2024, 2025, 2026])].copy()
    history["datetime"] = pd.to_datetime(
        history["Date"].astype(str) + " " + history["Time"].fillna("12:00"),
        dayfirst=True,
        errors="coerce",
    )
    return history.sort_values("datetime").reset_index(drop=True)


def build_team_history(history_df):
    team_history = {}

    for _, match in history_df.iterrows():
        home = match["Home"]
        away = match["Away"]
        team_history.setdefault(home, [])
        team_history.setdefault(away, [])

        team_history[home].append(
            {"gf": match["HG"], "ga": match["AG"], "venue": "H"}
        )
        team_history[away].append(
            {"gf": match["AG"], "ga": match["HG"], "venue": "A"}
        )

    return team_history


def fetch_fixtures(api_key):
    response = requests.get(
        "https://api.oddspapi.io/v4/fixtures",
        params={
            "apiKey": api_key,
            "tournamentId": TOURNAMENT_ID,
            "statusId": 0,
            "language": "en",
        },
        timeout=30,
    )
    response.raise_for_status()

    return {
        fixture.get("fixtureId"): {
            "fixture_id": fixture.get("fixtureId"),
            "start_time": fixture.get("startTime"),
            "home_team": fixture.get("participant1Name"),
            "away_team": fixture.get("participant2Name"),
        }
        for fixture in response.json()
    }


def fetch_odds(api_key):
    rows = []
    url = "https://api.oddspapi.io/v4/odds-by-tournaments"

    for bookmaker in BOOKMAKERS:
        response = requests.get(
            url,
            params={
                "apiKey": api_key,
                "tournamentIds": str(TOURNAMENT_ID),
                "bookmaker": bookmaker,
                "language": "en",
                "verbosity": 3,
                "oddsFormat": "decimal",
            },
            timeout=60,
        )

        if not response.ok:
            print(f"{bookmaker}: HTTP {response.status_code}")
            print(response.text[:500])
            time.sleep(1.5)
            continue

        for fixture in response.json():
            fixture_id = fixture.get("fixtureId")
            bookmaker_data = fixture.get("bookmakerOdds", {}).get(bookmaker)
            if bookmaker_data is None:
                continue

            rows.append(
                {
                    "fixture_id": fixture_id,
                    "bookmaker": bookmaker,
                    "over_25": get_price(bookmaker_data, 1010),
                    "under_25": get_price(bookmaker_data, 1011),
                }
            )

        time.sleep(1.5)

    return pd.DataFrame(rows)


def model_fixture(home, away, team_history, league_home_goals, league_away_goals):
    hh = team_history.get(home, [])
    ah = team_history.get(away, [])

    home_gf10, home_ga10 = recent_stats(hh, n=10)
    away_gf10, away_ga10 = recent_stats(ah, n=10)
    home_home_gf5, home_home_ga5 = recent_stats(hh, venue="H", n=5)
    away_away_gf5, away_away_ga5 = recent_stats(ah, venue="A", n=5)

    required = [
        home_gf10,
        home_ga10,
        away_gf10,
        away_ga10,
        home_home_gf5,
        home_home_ga5,
        away_away_gf5,
        away_away_ga5,
    ]
    if any(pd.isna(value) for value in required):
        return None

    expected_home_general = (home_gf10 + away_ga10) / 2
    expected_away_general = (away_gf10 + home_ga10) / 2
    expected_home_venue = (home_home_gf5 + away_away_ga5) / 2
    expected_away_venue = (away_away_gf5 + home_home_ga5) / 2

    lambda_home = 0.60 * expected_home_venue + 0.40 * expected_home_general
    lambda_away = 0.60 * expected_away_venue + 0.40 * expected_away_general

    lambda_home = 0.80 * lambda_home + 0.20 * league_home_goals
    lambda_away = 0.80 * lambda_away + 0.20 * league_away_goals

    lambda_home = np.clip(lambda_home, 0.20, 4.0)
    lambda_away = np.clip(lambda_away, 0.20, 4.0)
    expected_goals = lambda_home + lambda_away

    p0 = np.exp(-expected_goals)
    p1 = p0 * expected_goals
    p2 = p1 * expected_goals / 2
    p_over = 1 - p0 - p1 - p2

    return {
        "expected_goals": expected_goals,
        "p_over25": p_over,
    }


def main():
    api_key = read_api_key()

    # Uppdatera först resultatdelen av historiken utan att belasta OddsPapi.
    new_history_matches = update_history_from_football_data()

    # Modellen läser därefter den uppdaterade filen, så nya matcher påverkar
    # senaste form och 2026 års ligamiljö direkt i samma körning.
    history_df = load_history()
    team_history = build_team_history(history_df)

    current_2026 = history_df[history_df["Season"] == 2026]
    if current_2026.empty:
        raise RuntimeError("Historikfilen saknar matcher från 2026.")

    league_home_goals = current_2026["HG"].mean()
    league_away_goals = current_2026["AG"].mean()

    fixtures = fetch_fixtures(api_key)
    odds = fetch_odds(api_key)
    rows = []

    for fixture_id, fixture in fixtures.items():
        api_home = fixture["home_team"]
        api_away = fixture["away_team"]
        home = NAME_MAP.get(api_home, api_home)
        away = NAME_MAP.get(api_away, api_away)

        modeled = model_fixture(
            home,
            away,
            team_history,
            league_home_goals,
            league_away_goals,
        )
        if modeled is None:
            continue

        fixture_odds = odds[odds["fixture_id"] == fixture_id].copy()
        valid_over = fixture_odds.dropna(subset=["over_25"])

        best_odds = np.nan
        best_bookmaker = None
        if not valid_over.empty:
            best = valid_over.loc[valid_over["over_25"].idxmax()]
            best_odds = best["over_25"]
            best_bookmaker = best["bookmaker"]

        p_over = modeled["p_over25"]
        in_model_zone = MODEL_MIN <= p_over < MODEL_MAX

        if not in_model_zone:
            decision = "INGET SPEL"
        elif pd.isna(best_odds):
            decision = "SAKNAR ODDS"
        elif best_odds >= MIN_PLAYABLE_ODDS:
            decision = "SPELA"
        else:
            decision = "VÄNTA"

        rows.append(
            {
                "fixture_id": fixture_id,
                "start_time": fixture["start_time"],
                "home_team": api_home,
                "away_team": api_away,
                "expected_goals": modeled["expected_goals"],
                "p_over25": p_over * 100,
                "model_zone": in_model_zone,
                "min_playable_odds": MIN_PLAYABLE_ODDS if in_model_zone else np.nan,
                "best_over25_odds": best_odds,
                "best_bookmaker": best_bookmaker,
                "decision": decision,
            }
        )

    result = pd.DataFrame(rows)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not result.empty:
        result["start_time"] = pd.to_datetime(
            result["start_time"], utc=True, errors="coerce"
        )
        result = result.sort_values("start_time")

    result.to_csv(OUTPUT_FILE, index=False)

    print("\nALLSVENSKAN O/U 2.5 V1 – LIVE")
    print("=" * 100)
    print("API-budgetläge: Bet365 only (2 OddsPapi-anrop per full körning)")
    print(f"Nya historikmatcher denna körning: {new_history_matches}")

    if result.empty:
        print("Inga matcher kunde modelleras.")
    else:
        display = result[
            [
                "start_time",
                "home_team",
                "away_team",
                "expected_goals",
                "p_over25",
                "min_playable_odds",
                "best_over25_odds",
                "best_bookmaker",
                "decision",
            ]
        ].copy()
        print(display.round(3).to_string(index=False))

    print("\nV1-regel: P(Over) 55–60 % och Bet365-odds >= 1.85 => SPELA")
    print("Sparad:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
