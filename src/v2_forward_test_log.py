"""Separate forward-test logger for V2 Candidate B.

Only V2-B eligible fixtures can be frozen. No retroactive reconstruction is
performed. Existing V1 forward files are untouched.
"""
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "data" / "allsvenskan_live_v2_b.csv"
HISTORY = ROOT / "data" / "allsvenskan_raw.csv"
LOG = ROOT / "data" / "allsvenskan_v2_b_forward_log.csv"

MIN_ODDS = 1.85
MODEL_MIN_PCT = 55.0
MODEL_MAX_PCT = 60.0

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

COLS = [
    "record_id","record_type","counts_for_v2_b","logged_at","fixture_id","start_time",
    "home_team","away_team","home_2026_match_no","away_2026_match_no","min_2026_match_no",
    "p_over25","expected_goals","threshold_odds","observed_odds","bookmaker","status",
    "home_goals","away_goals","total_goals","won","profit",
]


def fid(v):
    if pd.isna(v): return ""
    try: return str(int(float(v)))
    except (TypeError, ValueError): return str(v)


def load_log():
    if LOG.exists():
        try: x = pd.read_csv(LOG)
        except pd.errors.EmptyDataError: x = pd.DataFrame(columns=COLS)
    else: x = pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in x.columns: x[c] = pd.NA
    return x[COLS].copy()


def history_results():
    if not HISTORY.exists(): return pd.DataFrame()
    h = pd.read_csv(HISTORY)
    h = h[pd.to_numeric(h["Season"], errors="coerce") == 2026].copy()
    h["HG"] = pd.to_numeric(h["HG"], errors="coerce"); h["AG"] = pd.to_numeric(h["AG"], errors="coerce")
    h = h.dropna(subset=["HG","AG"])
    h["match_date"] = pd.to_datetime(h["Date"].astype(str), dayfirst=True, errors="coerce").dt.date
    return h


def update_results(log, hist):
    if log.empty or hist.empty: return log, 0
    n = 0
    for i, r in log.iterrows():
        if str(r.get("status", "")) == "FINISHED": continue
        dt = pd.to_datetime(r.get("start_time"), utc=True, errors="coerce")
        if pd.isna(dt): continue
        date = dt.tz_convert("Europe/Stockholm").date()
        home = NAME_MAP.get(str(r.get("home_team", "")), str(r.get("home_team", "")))
        away = NAME_MAP.get(str(r.get("away_team", "")), str(r.get("away_team", "")))
        m = hist[(hist["match_date"] == date) & (hist["Home"].astype(str) == home) & (hist["Away"].astype(str) == away)]
        if m.empty: continue
        m = m.iloc[-1]; hg = int(m.HG); ag = int(m.AG); total = hg + ag; won = total >= 3
        odds = pd.to_numeric(pd.Series([r.get("observed_odds")]), errors="coerce").iloc[0]
        profit = pd.NA if pd.isna(odds) else (float(odds - 1) if won else -1.0)
        for c, v in {"status":"FINISHED","home_goals":hg,"away_goals":ag,"total_goals":total,"won":int(won),"profit":profit}.items():
            log.at[i,c] = v
        n += 1
    return log, n


def append(log, live):
    existing = set(log["record_id"].astype(str)) if not log.empty else set()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = []
    for _, r in live.iterrows():
        eligible = str(r.get("v2_b_eligible", "")).lower() in {"true","1"}
        if not eligible: continue
        p = pd.to_numeric(pd.Series([r.get("p_over25")]), errors="coerce").iloc[0]
        odds = pd.to_numeric(pd.Series([r.get("best_over25_odds")]), errors="coerce").iloc[0]
        if pd.isna(p) or not (MODEL_MIN_PCT <= p < MODEL_MAX_PCT) or pd.isna(odds): continue
        typ = "BET" if odds >= MIN_ODDS else "NEAR_MISS"
        rid = f"{fid(r.get('fixture_id'))}:{typ}"
        if rid in existing: continue
        new.append({
            "record_id":rid,"record_type":typ,"counts_for_v2_b":typ=="BET","logged_at":now,
            "fixture_id":fid(r.get("fixture_id")),"start_time":r.get("start_time"),
            "home_team":r.get("home_team"),"away_team":r.get("away_team"),
            "home_2026_match_no":r.get("home_2026_match_no"),"away_2026_match_no":r.get("away_2026_match_no"),
            "min_2026_match_no":r.get("min_2026_match_no"),"p_over25":float(p),
            "expected_goals":r.get("expected_goals"),"threshold_odds":MIN_ODDS,"observed_odds":float(odds),
            "bookmaker":r.get("best_bookmaker"),"status":"OPEN","home_goals":pd.NA,"away_goals":pd.NA,
            "total_goals":pd.NA,"won":pd.NA,"profit":pd.NA,
        })
        existing.add(rid)
    if new: log = pd.concat([log, pd.DataFrame(new)], ignore_index=True)
    return log, len(new)


def main():
    if not LIVE.exists(): raise RuntimeError(f"Saknar {LIVE}")
    live = pd.read_csv(LIVE); log = load_log(); hist = history_results()
    log, u1 = update_results(log, hist); log, added = append(log, live); log, u2 = update_results(log, hist)
    LOG.parent.mkdir(parents=True, exist_ok=True); log.to_csv(LOG, index=False)
    bets = log[log.record_type == "BET"].copy(); done = bets[bets.status == "FINISHED"].copy()
    profit = pd.to_numeric(done.profit, errors="coerce").sum() if len(done) else 0.0
    roi = profit / len(done) * 100 if len(done) else 0.0
    print("\nV2-B FORWARD-TEST LOG")
    print("="*70)
    print("Nya signaler:", added); print("Uppdaterade resultat:", u1+u2)
    print("V2-B bets totalt:", len(bets)); print("Färdigspelade:", len(done))
    print("Profit:", round(float(profit),2), "u | ROI:", round(float(roi),2), "%")
    print("Sparad:", LOG)

if __name__ == "__main__": main()
