"""V2 Candidate B live overlay.

Reads the frozen V1 live output and adds only the validated cold-start rule:
no V2 signal until BOTH teams are about to play at least match 6 of the
current Allsvenskan season. The underlying V1 probability and 55-60% model
zone are left unchanged.

0 OddsPapi calls. Does not modify V1 files.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
V1_LIVE = ROOT / "data" / "allsvenskan_live_ou25.csv"
HISTORY = ROOT / "data" / "allsvenskan_raw.csv"
OUTPUT = ROOT / "data" / "allsvenskan_live_v2_b.csv"

SEASON = 2026
MIN_MATCH_NO = 6
MODEL_MIN_PCT = 55.0
MODEL_MAX_PCT = 60.0
MIN_PLAYABLE_ODDS = 1.85

NAME_MAP = {
    "AIK": "AIK", "BK Hacken": "Hacken", "Degerfors IF": "Degerfors",
    "Djurgardens IF": "Djurgarden", "IF Brommapojkarna": "Brommapojkarna",
    "IF Elfsborg": "Elfsborg", "IFK Goteborg": "Goteborg",
    "IFK Norrkoping": "Norrkoping", "IK Sirius": "Sirius", "GAIS": "GAIS",
    "Halmstads BK": "Halmstad", "Hammarby IF": "Hammarby",
    "Kalmar FF": "Kalmar", "Malmo FF": "Malmo FF", "Mjallby AIF": "Mjallby",
    "Vasteras SK": "Vasteras SK", "IFK Varnamo": "Varnamo", "Varnamo": "Varnamo",
    "Osters IF": "Oster", "Orgryte IS": "Orgryte",
}


def current_match_counts():
    h = pd.read_csv(HISTORY)
    h["Season"] = pd.to_numeric(h["Season"], errors="coerce")
    h["HG"] = pd.to_numeric(h["HG"], errors="coerce")
    h["AG"] = pd.to_numeric(h["AG"], errors="coerce")
    h = h[(h["Season"] == SEASON) & h["HG"].notna() & h["AG"].notna()].copy()
    # In-season live data before November contains regular-season matches only.
    # The counter deliberately uses completed current-season league rows only.
    counts = pd.concat([h["Home"].astype(str), h["Away"].astype(str)]).value_counts()
    return counts.to_dict()


def main():
    if not V1_LIVE.exists():
        raise RuntimeError(f"Saknar V1-livefilen {V1_LIVE}")
    if not HISTORY.exists():
        raise RuntimeError(f"Saknar historikfilen {HISTORY}")

    live = pd.read_csv(V1_LIVE)
    counts = current_match_counts()
    if live.empty:
        live.to_csv(OUTPUT, index=False)
        print("V2-B live: V1-livefilen är tom")
        return

    rows = []
    for _, r in live.iterrows():
        home_api = str(r.get("home_team", "")); away_api = str(r.get("away_team", ""))
        home = NAME_MAP.get(home_api, home_api); away = NAME_MAP.get(away_api, away_api)
        home_no = int(counts.get(home, 0)) + 1; away_no = int(counts.get(away, 0)) + 1
        min_no = min(home_no, away_no)
        eligible = min_no >= MIN_MATCH_NO

        p = pd.to_numeric(pd.Series([r.get("p_over25")]), errors="coerce").iloc[0]
        odds = pd.to_numeric(pd.Series([r.get("best_over25_odds")]), errors="coerce").iloc[0]
        in_zone = pd.notna(p) and MODEL_MIN_PCT <= p < MODEL_MAX_PCT

        if not eligible:
            decision = "COLD START"
        elif not in_zone:
            decision = "INGET SPEL"
        elif pd.isna(odds):
            decision = "SAKNAR ODDS"
        elif odds >= MIN_PLAYABLE_ODDS:
            decision = "SPELA"
        else:
            decision = "VÄNTA"

        out = r.to_dict()
        out.update({
            "home_2026_match_no": home_no,
            "away_2026_match_no": away_no,
            "min_2026_match_no": min_no,
            "v2_b_eligible": bool(eligible),
            "v2_b_decision": decision,
        })
        rows.append(out)

    out = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    print("\nALLSVENSKAN O/U 2.5 V2-B LIVE OVERLAY")
    print("=" * 78)
    print("Regel: ingen V2-signal före båda lagens match 6; V1-sannolikhet oförändrad")
    print("Matcher:", len(out))
    print("V2-behöriga:", int(out["v2_b_eligible"].sum()))
    print("SPELA:", int((out["v2_b_decision"] == "SPELA").sum()))
    print("VÄNTA:", int((out["v2_b_decision"] == "VÄNTA").sum()))
    print("COLD START:", int((out["v2_b_decision"] == "COLD START").sum()))
    print("Sparad:", OUTPUT)


if __name__ == "__main__":
    main()
