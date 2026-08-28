"""Archive every manual V2-B market snapshot for future CLV analysis.

Reads the already-generated V2-B live file, so this makes 0 API calls.
Each manual live refresh appends one immutable observation per fixture.
"""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "data" / "allsvenskan_live_v2_b.csv"
OUT = ROOT / "data" / "allsvenskan_v2_b_market_snapshots.csv"

COLS = [
    "snapshot_at","fixture_id","start_time","home_team","away_team",
    "home_2026_match_no","away_2026_match_no","min_2026_match_no",
    "v2_b_eligible","p_over25","expected_goals","best_over25_odds",
    "best_bookmaker","v2_b_decision",
]


def main():
    if not LIVE.exists():
        raise RuntimeError(f"Saknar {LIVE}")
    try:
        live = pd.read_csv(LIVE)
    except pd.errors.EmptyDataError:
        live = pd.DataFrame()
    if live.empty:
        print("V2-B market snapshot: livefilen är tom")
        return

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snap = live.copy()
    snap["snapshot_at"] = now
    for c in COLS:
        if c not in snap.columns:
            snap[c] = pd.NA
    snap = snap[COLS].copy()

    if OUT.exists():
        try:
            old = pd.read_csv(OUT)
        except pd.errors.EmptyDataError:
            old = pd.DataFrame(columns=COLS)
        for c in COLS:
            if c not in old.columns:
                old[c] = pd.NA
        out = pd.concat([old[COLS], snap], ignore_index=True)
    else:
        out = snap

    # Exact duplicate snapshot rows can happen if a command is accidentally
    # invoked twice within the same second. Keep only one.
    out = out.drop_duplicates(subset=["snapshot_at","fixture_id"], keep="last")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    print("\nV2-B MARKET SNAPSHOT ARCHIVE")
    print("=" * 70)
    print("Nya snapshot-rader:", len(snap))
    print("Totala snapshot-rader:", len(out))
    print("Unika fixtures:", out["fixture_id"].astype(str).nunique())
    print("Sparad:", OUT)


if __name__ == "__main__":
    main()
