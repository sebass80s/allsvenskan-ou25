"""Cross-season validation of the V2 cold-start hypothesis.

Replays the unchanged V1 model separately for target seasons 2024, 2025 and 2026.
For completed seasons, promotion/relegation playoff rows are excluded in-memory by
removing matches involving teams with fewer than 30 appearances in that season.
The raw CSV is never modified.

Fixed candidate rule: both teams must have reached match 6+.
Diagnostic only. Does not touch V1/live/forward files. 0 API calls.
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
HISTORY=ROOT/"data"/"allsvenskan_raw.csv"
OUTPUT=ROOT/"data"/"allsvenskan_v2_cross_season_cold_start.csv"
DETAIL=ROOT/"data"/"allsvenskan_v2_cross_season_detail.csv"
EXCLUDED=ROOT/"data"/"allsvenskan_v2_excluded_playoffs.csv"
TARGETS=(2024,2025,2026)
THRESHOLD=6
REGULAR_MATCHES_PER_TEAM=30


def recent_stats(matches, venue=None, n=10):
    if venue is not None:
        matches=[m for m in matches if m["venue"]==venue]
    matches=matches[-n:]
    if not matches:
        return np.nan,np.nan
    w=np.linspace(1.0,2.0,len(matches))
    return np.average([m["gf"] for m in matches],weights=w),np.average([m["ga"] for m in matches],weights=w)


def predict(home,away,hist,league_home,league_away):
    hh,ah=hist.get(home,[]),hist.get(away,[])
    hgf,hga=recent_stats(hh,n=10); agf,aga=recent_stats(ah,n=10)
    hhgf,hhga=recent_stats(hh,"H",5); aagf,aaga=recent_stats(ah,"A",5)
    vals=[hgf,hga,agf,aga,hhgf,hhga,aagf,aaga]
    if any(pd.isna(v) for v in vals):
        return None
    lh=.60*((hhgf+aaga)/2)+.40*((hgf+aga)/2)
    la=.60*((aagf+hhga)/2)+.40*((agf+hga)/2)
    lh=np.clip(.80*lh+.20*league_home,.20,4.0)
    la=np.clip(.80*la+.20*league_away,.20,4.0)
    total=lh+la; p0=np.exp(-total); p1=p0*total; p2=p1*total/2
    return 1-p0-p1-p2


def metrics(g):
    if g.empty:
        return {"matches":0,"mean_prediction":np.nan,"actual_over_rate":np.nan,"brier":np.nan,"baseline_brier":np.nan,"brier_skill_score":np.nan}
    y=g.actual_over25.to_numpy(float); p=g.p_over25.to_numpy(float); rate=y.mean()
    b=np.mean((p-y)**2); base=np.mean((rate-y)**2)
    return {"matches":len(g),"mean_prediction":p.mean(),"actual_over_rate":rate,"brier":b,"baseline_brier":base,"brier_skill_score":1-b/base if base else np.nan}


def remove_completed_season_playoffs(df):
    """Remove playoff ties from completed seasons without touching raw data.

    A regular Allsvenskan team plays 30 league matches. A Superettan challenger
    appearing only in the two-leg playoff therefore has <30 appearances in the
    Football-Data season file. Any row involving such an outsider is excluded.
    Current incomplete season 2026 is left untouched.
    """
    keep=pd.Series(True,index=df.index)
    excluded=[]
    for season in sorted(int(s) for s in df.Season.dropna().unique() if int(s)<2026):
        s=df[df.Season.eq(season)]
        counts=pd.concat([s.Home.astype(str),s.Away.astype(str)]).value_counts()
        outsiders=set(counts[counts<REGULAR_MATCHES_PER_TEAM].index.astype(str))
        if not outsiders:
            continue
        mask=df.Season.eq(season) & (df.Home.astype(str).isin(outsiders)|df.Away.astype(str).isin(outsiders))
        for _,m in df[mask].iterrows():
            excluded.append({"season":season,"date":m.datetime.date().isoformat(),"home_team":m.Home,"away_team":m.Away,"home_goals":m.HG,"away_goals":m.AG,"reason":"playoff outsider <30 season appearances"})
        keep.loc[mask]=False
    return df[keep].copy(),pd.DataFrame(excluded)


def replay(df,target):
    use=df[df.Season.isin([target-2,target-1,target])].sort_values("datetime").copy()
    hist={}; prior_home=[]; prior_away=[]; season_games={}; rows=[]
    for _,m in use.iterrows():
        season=int(m.Season); home=str(m.Home); away=str(m.Away); hg=float(m.HG); ag=float(m.AG)
        if season==target:
            hno=season_games.get(home,0)+1; ano=season_games.get(away,0)+1
            if prior_home and prior_away:
                p=predict(home,away,hist,float(np.mean(prior_home)),float(np.mean(prior_away)))
                if p is not None:
                    actual=int(hg+ag>=3)
                    rows.append({"season":target,"date":m.datetime.date().isoformat(),"home_team":home,"away_team":away,"home_match_no":hno,"away_match_no":ano,"min_match_no":min(hno,ano),"p_over25":p,"actual_over25":actual})
        hist.setdefault(home,[]).append({"gf":hg,"ga":ag,"venue":"H"})
        hist.setdefault(away,[]).append({"gf":ag,"ga":hg,"venue":"A"})
        if season==target:
            prior_home.append(hg); prior_away.append(ag)
            season_games[home]=season_games.get(home,0)+1
            season_games[away]=season_games.get(away,0)+1
    return pd.DataFrame(rows)


def main():
    if not HISTORY.exists():
        raise RuntimeError(f"Saknar {HISTORY}")
    df=pd.read_csv(HISTORY)
    for c in ["Season","HG","AG"]:
        df[c]=pd.to_numeric(df[c],errors="coerce")
    time=df["Time"].fillna("12:00") if "Time" in df.columns else pd.Series("12:00",index=df.index)
    df["datetime"]=pd.to_datetime(df.Date.astype(str)+" "+time.astype(str),dayfirst=True,errors="coerce")
    df=df.dropna(subset=["Season","HG","AG","Home","Away","datetime"]).copy()

    df,excluded=remove_completed_season_playoffs(df)
    EXCLUDED.parent.mkdir(parents=True,exist_ok=True)
    excluded.to_csv(EXCLUDED,index=False)

    details=[]; summary=[]
    for season in TARGETS:
        d=replay(df,season)
        if d.empty:
            continue
        details.append(d)
        allm=metrics(d); cold=metrics(d[d.min_match_no<THRESHOLD]); mature=metrics(d[d.min_match_no>=THRESHOLD])
        summary.append({"season":season,"slice":"ALL","threshold":1,**allm})
        summary.append({"season":season,"slice":"COLD_1_5","threshold":THRESHOLD,**cold})
        summary.append({"season":season,"slice":"MATURE_6_PLUS","threshold":THRESHOLD,**mature})

    out=pd.DataFrame(summary)
    det=pd.concat(details,ignore_index=True) if details else pd.DataFrame()
    out.to_csv(OUTPUT,index=False); det.to_csv(DETAIL,index=False)

    print("ALLSVENSKAN V2 CROSS-SEASON COLD-START VALIDATION — REGULAR SEASON ONLY")
    print("="*90)
    print("Kval/playoff exkluderas i minnet; råfilen ändras inte.")
    if len(excluded):
        print("\nExkluderade rader")
        print(excluded.to_string(index=False))
    else:
        print("\nInga playoff-rader identifierades.")
    print("\nFast hypotes: båda lagen måste ha nått match 6. V1-sannolikheten är oförändrad.")
    print(out.to_string(index=False))
    print("\nNyckeljämförelse, MATURE_6_PLUS")
    mature=out[out.slice=="MATURE_6_PLUS"]
    print(mature[["season","matches","mean_prediction","actual_over_rate","brier","baseline_brier","brier_skill_score"]].to_string(index=False))
    if len(mature):
        positive=int((mature.brier_skill_score>0).sum())
        print(f"\nPositiv Brier skill efter match 6: {positive}/{len(mature)} säsonger")
    print("Resultat:",OUTPUT)
    print("Exkluderade playoff-rader:",EXCLUDED)

if __name__=="__main__":
    main()
