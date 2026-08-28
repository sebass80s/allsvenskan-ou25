from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "allsvenskan_raw.csv"
DETAIL_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_v1.csv"
SUMMARY_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_summary.csv"

MODEL_MIN = 0.55
MODEL_MAX = 0.60
MIN_HISTORY_SEASONS = {2024, 2025, 2026}


def weighted_mean(values, weights):
    return np.average(values, weights=weights) if values else np.nan


def recent_stats(matches, venue=None, n=10):
    if venue is not None:
        matches = [match for match in matches if match["venue"] == venue]
    matches = matches[-n:]
    if not matches:
        return np.nan, np.nan
    weights = np.linspace(1.0, 2.0, len(matches))
    return (
        weighted_mean([m["gf"] for m in matches], weights),
        weighted_mean([m["ga"] for m in matches], weights),
    )


def predict(home, away, team_history, league_home_goals, league_away_goals):
    hh = team_history.get(home, [])
    ah = team_history.get(away, [])

    home_gf10, home_ga10 = recent_stats(hh, n=10)
    away_gf10, away_ga10 = recent_stats(ah, n=10)
    home_home_gf5, home_home_ga5 = recent_stats(hh, venue="H", n=5)
    away_away_gf5, away_away_ga5 = recent_stats(ah, venue="A", n=5)

    required = [home_gf10, home_ga10, away_gf10, away_ga10, home_home_gf5, home_home_ga5, away_away_gf5, away_away_ga5]
    if any(pd.isna(v) for v in required):
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
    return expected_goals, p_over


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError(f"Saknar historikfilen {HISTORY_FILE}")

    df = pd.read_csv(HISTORY_FILE)
    required = {"Season", "Date", "Home", "Away", "HG", "AG"}
    if not required.issubset(df.columns):
        raise RuntimeError(f"Historikfilen saknar kolumner: {sorted(required - set(df.columns))}")

    df["Season"] = pd.to_numeric(df["Season"], errors="coerce")
    df["HG"] = pd.to_numeric(df["HG"], errors="coerce")
    df["AG"] = pd.to_numeric(df["AG"], errors="coerce")
    time_col = df["Time"].fillna("12:00") if "Time" in df.columns else pd.Series("12:00", index=df.index)
    df["datetime"] = pd.to_datetime(df["Date"].astype(str) + " " + time_col.astype(str), dayfirst=True, errors="coerce")
    df = df[df["Season"].isin(MIN_HISTORY_SEASONS)].dropna(subset=["datetime", "HG", "AG", "Home", "Away"]).copy()
    df = df.sort_values("datetime").reset_index(drop=True)

    team_history = {}
    prior_2026_home_goals = []
    prior_2026_away_goals = []
    rows = []

    for _, match in df.iterrows():
        season = int(match["Season"])
        home = str(match["Home"])
        away = str(match["Away"])
        hg = float(match["HG"])
        ag = float(match["AG"])

        # Only score 2026 matches, and only from information available before kickoff.
        if season == 2026 and prior_2026_home_goals and prior_2026_away_goals:
            league_home = float(np.mean(prior_2026_home_goals))
            league_away = float(np.mean(prior_2026_away_goals))
            modeled = predict(home, away, team_history, league_home, league_away)
            if modeled is not None:
                expected_goals, p_over = modeled
                actual_over = int(hg + ag >= 3)
                in_zone = MODEL_MIN <= p_over < MODEL_MAX
                rows.append({
                    "date": match["datetime"].date().isoformat(),
                    "home_team": home,
                    "away_team": away,
                    "expected_goals": expected_goals,
                    "p_over25": p_over,
                    "in_model_zone": in_zone,
                    "actual_over25": actual_over,
                    "total_goals": int(hg + ag),
                    "brier": (p_over - actual_over) ** 2,
                })

        # Update histories only after the prediction for this match.
        team_history.setdefault(home, []).append({"gf": hg, "ga": ag, "venue": "H"})
        team_history.setdefault(away, []).append({"gf": ag, "ga": hg, "venue": "A"})
        if season == 2026:
            prior_2026_home_goals.append(hg)
            prior_2026_away_goals.append(ag)

    detail = pd.DataFrame(rows)
    DETAIL_FILE.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_FILE, index=False)

    if detail.empty:
        summary = pd.DataFrame([{
            "scored_matches": 0,
            "zone_matches": 0,
            "overall_actual_over_rate": np.nan,
            "overall_mean_prediction": np.nan,
            "overall_brier": np.nan,
            "zone_actual_over_rate": np.nan,
            "zone_mean_prediction": np.nan,
            "zone_brier": np.nan,
        }])
    else:
        zone = detail[detail["in_model_zone"]].copy()
        summary = pd.DataFrame([{
            "scored_matches": len(detail),
            "zone_matches": len(zone),
            "overall_actual_over_rate": detail["actual_over25"].mean(),
            "overall_mean_prediction": detail["p_over25"].mean(),
            "overall_brier": detail["brier"].mean(),
            "zone_actual_over_rate": zone["actual_over25"].mean() if len(zone) else np.nan,
            "zone_mean_prediction": zone["p_over25"].mean() if len(zone) else np.nan,
            "zone_brier": zone["brier"].mean() if len(zone) else np.nan,
        }])

    summary.to_csv(SUMMARY_FILE, index=False)

    print("ALLSVENSKAN V1 WALK-FORWARD BACKTEST")
    print("=" * 70)
    print("2026-matcher med prediktion:", int(summary.iloc[0]["scored_matches"]))
    print("Matcher i frysta modellzonen 55–60 %:", int(summary.iloc[0]["zone_matches"]))
    if not detail.empty:
        print("Total faktisk Over 2.5:", round(float(summary.iloc[0]["overall_actual_over_rate"]) * 100, 1), "%")
        print("Total snittprediktion:", round(float(summary.iloc[0]["overall_mean_prediction"]) * 100, 1), "%")
        print("Brier:", round(float(summary.iloc[0]["overall_brier"]), 4))
        if int(summary.iloc[0]["zone_matches"]):
            print("Zon faktisk Over 2.5:", round(float(summary.iloc[0]["zone_actual_over_rate"]) * 100, 1), "%")
            print("Zon snittprediktion:", round(float(summary.iloc[0]["zone_mean_prediction"]) * 100, 1), "%")
            print("Zon Brier:", round(float(summary.iloc[0]["zone_brier"]), 4))
    print("Detaljer:", DETAIL_FILE)
    print("Sammanfattning:", SUMMARY_FILE)


if __name__ == "__main__":
    main()
