"""Evaluate V2-B closing-line movement from archived manual Bet365 snapshots.

0 API calls. Closing snapshot is defined as the latest archived pre-kickoff
price for each fixture. This is a proxy for closing price, not an exchange or
true market close unless the last manual refresh was near kickoff.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SNAPS = ROOT / "data" / "allsvenskan_v2_b_market_snapshots.csv"
FORWARD = ROOT / "data" / "allsvenskan_v2_b_forward_log.csv"
DETAIL = ROOT / "data" / "allsvenskan_v2_b_clv_detail.csv"
SUMMARY = ROOT / "data" / "allsvenskan_v2_b_clv_summary.csv"


def main():
    if not SNAPS.exists():
        print("V2-B CLV: inga snapshots ännu")
        return
    try:
        s = pd.read_csv(SNAPS)
    except pd.errors.EmptyDataError:
        print("V2-B CLV: snapshotfilen är tom")
        return
    if s.empty:
        print("V2-B CLV: snapshotfilen är tom")
        return

    s["snapshot_at"] = pd.to_datetime(s["snapshot_at"], utc=True, errors="coerce")
    s["start_time"] = pd.to_datetime(s["start_time"], utc=True, errors="coerce")
    s["best_over25_odds"] = pd.to_numeric(s["best_over25_odds"], errors="coerce")
    s = s.dropna(subset=["fixture_id","snapshot_at","start_time","best_over25_odds"]).copy()
    s = s[s["snapshot_at"] < s["start_time"]].copy()
    if s.empty:
        print("V2-B CLV: inga giltiga pre-kickoff snapshots")
        return

    s["minutes_to_kickoff"] = (s["start_time"] - s["snapshot_at"]).dt.total_seconds() / 60.0
    closing = s.sort_values("snapshot_at").groupby("fixture_id", as_index=False).tail(1).copy()
    closing = closing[["fixture_id","best_over25_odds","snapshot_at","minutes_to_kickoff"]].rename(columns={
        "best_over25_odds":"closing_proxy_odds",
        "snapshot_at":"closing_snapshot_at",
        "minutes_to_kickoff":"closing_snapshot_minutes_to_kickoff",
    })

    if FORWARD.exists():
        try:
            f = pd.read_csv(FORWARD)
        except pd.errors.EmptyDataError:
            f = pd.DataFrame()
    else:
        f = pd.DataFrame()

    if f.empty:
        print("V2-B CLV: inga frysta V2-B-signaler ännu")
        return

    f = f[f["record_type"].eq("BET")].copy()
    f["observed_odds"] = pd.to_numeric(f["observed_odds"], errors="coerce")
    x = f.merge(closing, on="fixture_id", how="left")
    x["clv_pct"] = (x["observed_odds"] / x["closing_proxy_odds"] - 1.0) * 100.0
    x["implied_prob_at_bet"] = 1.0 / x["observed_odds"]
    x["implied_prob_at_close_proxy"] = 1.0 / x["closing_proxy_odds"]
    x["clv_prob_pp"] = (x["implied_prob_at_close_proxy"] - x["implied_prob_at_bet"]) * 100.0
    x.to_csv(DETAIL, index=False)

    valid = x.dropna(subset=["clv_pct"]).copy()
    summary = pd.DataFrame([{
        "bets": int(len(x)),
        "bets_with_closing_proxy": int(len(valid)),
        "mean_clv_pct": float(valid["clv_pct"].mean()) if len(valid) else np.nan,
        "median_clv_pct": float(valid["clv_pct"].median()) if len(valid) else np.nan,
        "positive_clv_share": float((valid["clv_pct"] > 0).mean()) if len(valid) else np.nan,
        "mean_closing_snapshot_minutes_to_kickoff": float(valid["closing_snapshot_minutes_to_kickoff"].mean()) if len(valid) else np.nan,
    }])
    summary.to_csv(SUMMARY, index=False)

    print("\nV2-B CLV EVALUATION")
    print("=" * 70)
    print("Frysta spel:", len(x))
    print("Med closing-proxy:", len(valid))
    if len(valid):
        print(f"Mean CLV: {valid['clv_pct'].mean():+.2f}%")
        print(f"Median CLV: {valid['clv_pct'].median():+.2f}%")
        print(f"Positiv CLV: {(valid['clv_pct'] > 0).mean()*100:.1f}%")
        print(f"Closing-proxy i snitt {valid['closing_snapshot_minutes_to_kickoff'].mean():.0f} min före kickoff")
    print("OBS: closing-proxy = sista manuella Bet365-snapshot före kickoff.")
    print("Detaljer:", DETAIL)


if __name__ == "__main__":
    main()
