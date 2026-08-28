from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / "data" / "allsvenskan_raw.csv"
REPORT_FILE = PROJECT_ROOT / "data" / "allsvenskan_data_quality.csv"
SUMMARY_FILE = PROJECT_ROOT / "data" / "allsvenskan_data_quality_summary.csv"

REQUIRED_COLUMNS = ["Season", "Date", "Home", "Away", "HG", "AG"]


def add_check(rows, check, severity, count, details):
    rows.append({
        "check": check,
        "severity": severity,
        "count": int(count),
        "details": details,
    })


def main():
    if not HISTORY_FILE.exists():
        raise RuntimeError(f"Saknar historikfilen {HISTORY_FILE}")

    df = pd.read_csv(HISTORY_FILE)
    rows = []

    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    add_check(
        rows,
        "Obligatoriska kolumner",
        "ERROR" if missing_columns else "OK",
        len(missing_columns),
        ", ".join(missing_columns) if missing_columns else "Alla finns",
    )
    if missing_columns:
        pd.DataFrame(rows).to_csv(REPORT_FILE, index=False)
        raise RuntimeError(f"Saknar obligatoriska kolumner: {missing_columns}")

    season = pd.to_numeric(df["Season"], errors="coerce")
    hg = pd.to_numeric(df["HG"], errors="coerce")
    ag = pd.to_numeric(df["AG"], errors="coerce")
    parsed_date = pd.to_datetime(df["Date"].astype(str), dayfirst=True, errors="coerce")

    bad_season = season.isna()
    bad_date = parsed_date.isna()
    missing_team = df["Home"].isna() | df["Away"].isna() | (df["Home"].astype(str).str.strip() == "") | (df["Away"].astype(str).str.strip() == "")
    missing_score = hg.isna() | ag.isna()
    invalid_score = ((hg < 0) | (ag < 0)) & ~missing_score
    non_integer_score = (((hg % 1) != 0) | ((ag % 1) != 0)) & ~missing_score

    duplicate_key = pd.DataFrame({
        "Season": season,
        "Date": df["Date"].astype(str).str.strip(),
        "Home": df["Home"].astype(str).str.strip(),
        "Away": df["Away"].astype(str).str.strip(),
    }).duplicated(keep=False)

    same_team = df["Home"].astype(str).str.strip().eq(df["Away"].astype(str).str.strip())

    add_check(rows, "Ogiltig säsong", "ERROR" if bad_season.any() else "OK", bad_season.sum(), "Season kunde inte tolkas numeriskt")
    add_check(rows, "Ogiltigt datum", "ERROR" if bad_date.any() else "OK", bad_date.sum(), "Date kunde inte tolkas")
    add_check(rows, "Saknat lagnamn", "ERROR" if missing_team.any() else "OK", missing_team.sum(), "Home eller Away saknas")
    add_check(rows, "Saknat slutresultat", "WARN" if missing_score.any() else "OK", missing_score.sum(), "HG eller AG saknas")
    add_check(rows, "Negativa mål", "ERROR" if invalid_score.any() else "OK", invalid_score.sum(), "HG/AG under 0")
    add_check(rows, "Icke-heltal mål", "ERROR" if non_integer_score.any() else "OK", non_integer_score.sum(), "HG/AG är inte heltal")
    add_check(rows, "Duplicerade matcher", "ERROR" if duplicate_key.any() else "OK", duplicate_key.sum(), "Samma Season/Date/Home/Away förekommer flera gånger")
    add_check(rows, "Samma hemma- och bortalag", "ERROR" if same_team.any() else "OK", same_team.sum(), "Home == Away")

    completed = df[~missing_score & ~bad_date & ~bad_season].copy()
    completed["Season_num"] = season[completed.index].astype(int)
    completed["date_parsed"] = parsed_date[completed.index]

    # Namn som endast skiljer sig i blanksteg eller versaler kan skapa dolda lagidentiteter.
    team_names = pd.concat([df["Home"], df["Away"]], ignore_index=True).dropna().astype(str)
    normalized = team_names.str.strip().str.casefold()
    variants = pd.DataFrame({"raw": team_names, "norm": normalized}).groupby("norm")["raw"].nunique()
    variant_groups = variants[variants > 1]
    add_check(
        rows,
        "Lagnamnsvarianter",
        "WARN" if len(variant_groups) else "OK",
        len(variant_groups),
        "Samma normaliserade namn förekommer i flera stavningar",
    )

    # Enkel säsongsöversikt, användbar för att upptäcka hål i datan.
    summary = (
        completed.groupby("Season_num", as_index=False)
        .agg(
            matches=("Season_num", "size"),
            first_date=("date_parsed", "min"),
            last_date=("date_parsed", "max"),
        )
        .sort_values("Season_num")
    )
    summary["first_date"] = summary["first_date"].dt.strftime("%Y-%m-%d")
    summary["last_date"] = summary["last_date"].dt.strftime("%Y-%m-%d")

    report = pd.DataFrame(rows)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(REPORT_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)

    errors = int((report["severity"] == "ERROR").sum())
    warnings = int((report["severity"] == "WARN").sum())
    print("ALLSVENSKAN DATA QUALITY")
    print("=" * 60)
    print(report.to_string(index=False))
    print("\nSäsongsöversikt")
    print(summary.to_string(index=False))
    print(f"\nKontroller med ERROR: {errors}")
    print(f"Kontroller med WARN: {warnings}")
    print("Rapport:", REPORT_FILE)


if __name__ == "__main__":
    main()
