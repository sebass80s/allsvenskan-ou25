from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_FILE = PROJECT_ROOT / "data" / "allsvenskan_live_ou25.csv"
HISTORY_FILE = PROJECT_ROOT / "data" / "allsvenskan_raw.csv"
LOG_FILE = PROJECT_ROOT / "data" / "allsvenskan_forward_log.csv"

MIN_PLAYABLE_ODDS = 1.85
MODEL_MIN_PCT = 55.0
MODEL_MAX_PCT = 60.0

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

COLUMNS = [
    "record_id",
    "record_type",
    "counts_for_v1",
    "logged_at",
    "fixture_id",
    "start_time",
    "home_team",
    "away_team",
    "p_over25",
    "expected_goals",
    "threshold_odds",
    "observed_odds",
    "bookmaker",
    "status",
    "home_goals",
    "away_goals",
    "total_goals",
    "won",
    "profit",
]


def normalize_fixture_id(value):
    if pd.isna(value):
        return ""
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)


def load_log():
    if LOG_FILE.exists():
        try:
            log = pd.read_csv(LOG_FILE)
        except pd.errors.EmptyDataError:
            log = pd.DataFrame(columns=COLUMNS)
    else:
        log = pd.DataFrame(columns=COLUMNS)

    for column in COLUMNS:
        if column not in log.columns:
            log[column] = pd.NA

    return log[COLUMNS].copy()


def load_history_results():
    if not HISTORY_FILE.exists():
        return pd.DataFrame()

    history = pd.read_csv(HISTORY_FILE)
    history = history[pd.to_numeric(history["Season"], errors="coerce") == 2026].copy()

    history["HG"] = pd.to_numeric(history["HG"], errors="coerce")
    history["AG"] = pd.to_numeric(history["AG"], errors="coerce")
    history = history.dropna(subset=["HG", "AG"])

    history["match_date"] = pd.to_datetime(
        history["Date"].astype(str), dayfirst=True, errors="coerce"
    ).dt.date

    history["home_norm"] = history["Home"].astype(str)
    history["away_norm"] = history["Away"].astype(str)

    return history


def update_finished_results(log, history):
    if log.empty or history.empty:
        return log, 0

    updated = 0

    for idx, row in log.iterrows():
        if str(row.get("status", "")) == "FINISHED":
            continue

        start_time = pd.to_datetime(row.get("start_time"), utc=True, errors="coerce")
        if pd.isna(start_time):
            continue

        match_date = start_time.tz_convert("Europe/Stockholm").date()
        home = NAME_MAP.get(str(row.get("home_team", "")), str(row.get("home_team", "")))
        away = NAME_MAP.get(str(row.get("away_team", "")), str(row.get("away_team", "")))

        match = history[
            (history["match_date"] == match_date)
            & (history["home_norm"] == home)
            & (history["away_norm"] == away)
        ]

        if match.empty:
            continue

        match = match.iloc[-1]
        home_goals = int(match["HG"])
        away_goals = int(match["AG"])
        total_goals = home_goals + away_goals
        won = total_goals >= 3

        observed_odds = pd.to_numeric(pd.Series([row.get("observed_odds")]), errors="coerce").iloc[0]
        if pd.isna(observed_odds):
            profit = pd.NA
        else:
            profit = float(observed_odds - 1.0) if won else -1.0

        log.at[idx, "status"] = "FINISHED"
        log.at[idx, "home_goals"] = home_goals
        log.at[idx, "away_goals"] = away_goals
        log.at[idx, "total_goals"] = total_goals
        log.at[idx, "won"] = int(won)
        log.at[idx, "profit"] = profit
        updated += 1

    return log, updated


def append_new_signals(log, live):
    existing_ids = set(log["record_id"].astype(str)) if not log.empty else set()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new_rows = []

    for _, row in live.iterrows():
        p_over = pd.to_numeric(pd.Series([row.get("p_over25")]), errors="coerce").iloc[0]
        odds = pd.to_numeric(pd.Series([row.get("best_over25_odds")]), errors="coerce").iloc[0]

        if pd.isna(p_over) or not (MODEL_MIN_PCT <= p_over < MODEL_MAX_PCT):
            continue

        if pd.isna(odds):
            continue

        if odds >= MIN_PLAYABLE_ODDS:
            record_type = "BET"
            counts_for_v1 = True
        else:
            record_type = "NEAR_MISS"
            counts_for_v1 = False

        fixture_id = normalize_fixture_id(row.get("fixture_id"))
        record_id = f"{fixture_id}:{record_type}"
        if record_id in existing_ids:
            continue

        new_rows.append({
            "record_id": record_id,
            "record_type": record_type,
            "counts_for_v1": counts_for_v1,
            "logged_at": now,
            "fixture_id": fixture_id,
            "start_time": row.get("start_time"),
            "home_team": row.get("home_team"),
            "away_team": row.get("away_team"),
            "p_over25": float(p_over),
            "expected_goals": row.get("expected_goals"),
            "threshold_odds": MIN_PLAYABLE_ODDS,
            "observed_odds": float(odds),
            "bookmaker": row.get("best_bookmaker"),
            "status": "OPEN",
            "home_goals": pd.NA,
            "away_goals": pd.NA,
            "total_goals": pd.NA,
            "won": pd.NA,
            "profit": pd.NA,
        })
        existing_ids.add(record_id)

    if new_rows:
        log = pd.concat([log, pd.DataFrame(new_rows)], ignore_index=True)

    return log, len(new_rows)


def main():
    if not LIVE_FILE.exists():
        raise RuntimeError(f"Saknar livefilen {LIVE_FILE}")

    live = pd.read_csv(LIVE_FILE)
    log = load_log()
    history = load_history_results()

    log, updated_results = update_finished_results(log, history)
    log, new_signals = append_new_signals(log, live)

    # Kör resultatmatchning en gång till så att redan spelade matcher som råkar
    # loggas från en äldre livefil kan fyllas direkt.
    log, updated_results_2 = update_finished_results(log, history)
    updated_results += updated_results_2

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log.to_csv(LOG_FILE, index=False)

    bets = log[log["record_type"] == "BET"].copy()
    near = log[log["record_type"] == "NEAR_MISS"].copy()
    finished_bets = bets[bets["status"] == "FINISHED"].copy()

    profit = pd.to_numeric(finished_bets["profit"], errors="coerce").sum() if not finished_bets.empty else 0.0
    roi = (profit / len(finished_bets) * 100.0) if len(finished_bets) else 0.0

    print("\nFORWARD-TEST LOG")
    print("=" * 70)
    print("Nya signaler:", new_signals)
    print("Uppdaterade resultat:", updated_results)
    print("V1-bets totalt:", len(bets))
    print("Nästan-spel totalt:", len(near))
    print("Färdigspelade V1-bets:", len(finished_bets))
    print("Profit:", round(float(profit), 2), "units")
    print("ROI:", round(float(roi), 2), "%")
    print("Sparad:", LOG_FILE)


if __name__ == "__main__":
    main()
