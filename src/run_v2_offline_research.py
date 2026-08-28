"""Run the core V2 research suite locally with 0 OddsPapi calls."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
SCRIPTS=[
    "audit_data.py",
    "backtest_v1.py",
    "v2_cold_start_thresholds.py",
    "v2_cross_season_cold_start.py",
    "v2_b_zone_validation.py",
    "historical_ou25_odds_audit.py",
    "v2_b_historical_odds_backtest.py",
    "v2_candidate_a.py",
]


def main():
    print("ALLSVENSKAN V2 OFFLINE RESEARCH SUITE")
    print("="*80)
    print("0 OddsPapi-anrop. V1/live/forward-regler ändras inte.\n")
    for name in SCRIPTS:
        script=ROOT/"src"/name
        print("\n"+"#"*80); print("Kör:",name); print("#"*80)
        r=subprocess.run([sys.executable,str(script)],cwd=str(ROOT))
        if r.returncode!=0:
            print(f"STOPP: {name} returnerade {r.returncode}")
            raise SystemExit(r.returncode)
    print("\n"+"="*80)
    print("KLART: hela V2 offline-sviten kördes utan OddsPapi-anrop.")

if __name__=="__main__": main()
