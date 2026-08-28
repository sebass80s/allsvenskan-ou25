from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "allsvenskan_raw.csv"
DETAIL_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_v1.csv"
SUMMARY_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_summary.csv"
CALIBRATION_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_calibration.csv"
MONTHLY_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_monthly.csv"
MISSING_FILE = PROJECT_ROOT / "data" / "allsvenskan_backtest_missing.csv"

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
    return weighted_mean([m["gf"] for m in matches], weights), weighted_mean([m["ga"] for m in matches], weights)


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
    return expected_goals, 1 - p0 - p1 - p2


def missing_reason(home, away, team_history, league_ready):
    if not league_ready:
        return "Ingen tidigare 2026-match för ligabaslinje"
    hh = team_history.get(home, [])
    ah = team_history.get(away, [])
    if not hh and not ah:
        return "Båda lagen saknar tidigare historik"
    if not hh:
        return f"{home} saknar tidigare historik"
    if not ah:
        return f"{away} saknar tidigare historik"
    if not any(m["venue"] == "H" for m in hh):
        return f"{home} saknar tidigare hemmamatch"
    if not any(m["venue"] == "A" for m in ah):
        return f"{away} saknar tidigare bortamatch"
    return "Otillräcklig historik för minst en feature"


def brier_skill(brier, baseline_brier):
    if pd.isna(brier) or pd.isna(baseline_brier) or baseline_brier == 0:
        return np.nan
    return 1.0 - brier / baseline_brier


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

    team_history, prior_home, prior_away, rows, missing = {}, [], [], [], []
    for _, match in df.iterrows():
        season, home, away = int(match["Season"]), str(match["Home"]), str(match["Away"])
        hg, ag = float(match["HG"]), float(match["AG"])
        if season == 2026:
            league_ready = bool(prior_home and prior_away)
            modeled = None
            if league_ready:
                modeled = predict(home, away, team_history, float(np.mean(prior_home)), float(np.mean(prior_away)))
            if modeled is None:
                missing.append({"date": match["datetime"].date().isoformat(), "home_team": home, "away_team": away, "reason": missing_reason(home, away, team_history, league_ready)})
            else:
                expected_goals, p_over = modeled
                actual = int(hg + ag >= 3)
                rows.append({"date": match["datetime"].date().isoformat(), "home_team": home, "away_team": away, "expected_goals": expected_goals, "p_over25": p_over, "in_model_zone": MODEL_MIN <= p_over < MODEL_MAX, "actual_over25": actual, "total_goals": int(hg + ag), "brier": (p_over - actual) ** 2})
        team_history.setdefault(home, []).append({"gf": hg, "ga": ag, "venue": "H"})
        team_history.setdefault(away, []).append({"gf": ag, "ga": hg, "venue": "A"})
        if season == 2026:
            prior_home.append(hg); prior_away.append(ag)

    detail = pd.DataFrame(rows)
    missing_df = pd.DataFrame(missing, columns=["date", "home_team", "away_team", "reason"])
    DETAIL_FILE.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_FILE, index=False)
    missing_df.to_csv(MISSING_FILE, index=False)

    if detail.empty:
        calibration = pd.DataFrame(columns=["probability_band", "matches", "mean_prediction", "actual_over_rate", "brier"])
        monthly = pd.DataFrame(columns=["month", "matches", "mean_prediction", "actual_over_rate", "brier"])
        summary = pd.DataFrame([{"scored_matches": 0, "missing_matches": len(missing_df)}])
    else:
        actual_rate = detail["actual_over25"].mean()
        baseline_brier = float(np.mean((actual_rate - detail["actual_over25"]) ** 2))
        overall_brier = detail["brier"].mean()
        zone = detail[detail["in_model_zone"]].copy()
        zone_rate = zone["actual_over25"].mean() if len(zone) else np.nan
        zone_baseline = float(np.mean((zone_rate - zone["actual_over25"]) ** 2)) if len(zone) else np.nan
        zone_brier = zone["brier"].mean() if len(zone) else np.nan
        summary = pd.DataFrame([{
            "scored_matches": len(detail), "missing_matches": len(missing_df), "zone_matches": len(zone),
            "overall_actual_over_rate": actual_rate, "overall_mean_prediction": detail["p_over25"].mean(),
            "overall_brier": overall_brier, "baseline_brier": baseline_brier, "brier_skill_score": brier_skill(overall_brier, baseline_brier),
            "zone_actual_over_rate": zone_rate, "zone_mean_prediction": zone["p_over25"].mean() if len(zone) else np.nan,
            "zone_brier": zone_brier, "zone_baseline_brier": zone_baseline, "zone_brier_skill_score": brier_skill(zone_brier, zone_baseline),
        }])
        detail["probability_band"] = pd.cut(detail["p_over25"], bins=[-np.inf, .50, .55, .60, .65, np.inf], labels=["<50%", "50–55%", "55–60%", "60–65%", "65%+"] , right=False)
        calibration = detail.groupby("probability_band", observed=False).agg(matches=("actual_over25", "size"), mean_prediction=("p_over25", "mean"), actual_over_rate=("actual_over25", "mean"), brier=("brier", "mean")).reset_index()
        detail["month"] = pd.to_datetime(detail["date"]).dt.to_period("M").astype(str)
        monthly = detail.groupby("month").agg(matches=("actual_over25", "size"), mean_prediction=("p_over25", "mean"), actual_over_rate=("actual_over25", "mean"), brier=("brier", "mean")).reset_index()

    summary.to_csv(SUMMARY_FILE, index=False)
    calibration.to_csv(CALIBRATION_FILE, index=False)
    monthly.to_csv(MONTHLY_FILE, index=False)

    row = summary.iloc[0]
    print("ALLSVENSKAN V1 WALK-FORWARD BACKTEST")
    print("=" * 70)
    print("2026-matcher med prediktion:", int(row.get("scored_matches", 0)))
    print("Matcher utan prediktion:", int(row.get("missing_matches", 0)))
    if not detail.empty:
        print("Matcher i frysta modellzonen 55–60 %:", int(row["zone_matches"]))
        print("Total faktisk Over 2.5:", round(row["overall_actual_over_rate"] * 100, 1), "%")
        print("Total snittprediktion:", round(row["overall_mean_prediction"] * 100, 1), "%")
        print("Brier:", round(row["overall_brier"], 4), "| Baslinje:", round(row["baseline_brier"], 4), "| Skill:", round(row["brier_skill_score"] * 100, 2), "%")
        if int(row["zone_matches"]):
            print("Zon faktisk Over 2.5:", round(row["zone_actual_over_rate"] * 100, 1), "%")
            print("Zon snittprediktion:", round(row["zone_mean_prediction"] * 100, 1), "%")
            print("Zon Brier:", round(row["zone_brier"], 4), "| Baslinje:", round(row["zone_baseline_brier"], 4), "| Skill:", round(row["zone_brier_skill_score"] * 100, 2), "%")
        print("\nKalibrering")
        print(calibration.to_string(index=False))
        print("\nMånadsvis")
        print(monthly.to_string(index=False))
    if len(missing_df):
        print("\nMatcher utan prediktion")
        print(missing_df.to_string(index=False))
    print("Detaljer:", DETAIL_FILE)


if __name__ == "__main__":
    main()
