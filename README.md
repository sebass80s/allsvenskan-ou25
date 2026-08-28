# Allsvenskan O/U 2.5

Separat Allsvenskan-projekt, fristående från Premier League-projektet.

## V1, fryst forward-test

Modellen uppskattar sannolikheten för **Over 2.5 mål** från aktuell målform, hemma/borta-form och ligans aktuella målmiljö.

En match är endast en V1-kandidat när modellens råa `P(Over 2.5)` ligger i intervallet **55–60 %**.

- **SPELA** om Bet365 Over 2.5 är **>= 1.85**
- **VÄNTA** om matchen är i modellzonen men oddset är lägre än 1.85
- **INGET SPEL** om modellens sannolikhet ligger utanför 55–60 %

V1-regeln och dess gamla forward-logg är frysta.

## V2-B, separat kandidat

Historisk walk-forward-diagnostik 2024–2026 visade ett stabilt cold-start-problem i V1. V2 Candidate B ändrar därför **inte sannolikhetsmodellen**. Den lägger bara till en mognadsregel:

> Ingen V2-B-signal innan båda lagen är framme vid sin sjätte ligamatch för säsongen.

Därefter används exakt V1-sannolikhet, samma 55–60 %-zon och samma oddsgräns 1.85.

V2-B har egen livefil och egen forward-logg. Gamla V1-signaler rekonstrueras inte retroaktivt.

## Datakällor och API-budget

- Historik: `data/allsvenskan_raw.csv`
- Färska resultat: Football-Data Sweden CSV, 0 OddsPapi-anrop
- Live fixtures och odds: OddsPapi tournament ID `40`
- Normalt live-budgetläge: **Bet365 endast**, cirka **2 OddsPapi-anrop per manuell uppdatering**
- Streamlit-sidorna läser lokala filer och gör i sig 0 API-anrop

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Skapa `.env` i projektroten:

```text
ODDSPAPI_API_KEY=din_api_nyckel
```

Lägg historikfilen i:

```text
data/allsvenskan_raw.csv
```

## Starta dashboard

```bash
streamlit run app.py
```

Den vanliga knappen **Uppdatera odds** kör hela livekedjan:

1. V1 live + resultat
2. V1 forward-logg
3. V2-B cold-start-overlay, 0 extra API-anrop
4. separat V2-B forward-logg
5. invariant-audit som stoppar körningen om V2-B bryter sin frysta regel

## Viktiga filer

- `src/live_ou25_v1.py` – fryst V1 live
- `src/forward_test_log.py` – fryst V1 forward-logg
- `src/live_v2_candidate_b.py` – V2-B live-overlay
- `src/v2_forward_test_log.py` – separat V2-B forward-logg
- `src/v2_invariant_audit.py` – säkerhetskontroll
- `src/v2_cross_season_cold_start.py` – historisk cold-start-validering
- `src/v2_b_zone_validation.py` – validering specifikt i 55–60 %-zonen
- `pages/3_V2_B_forward.py` – separat V2-B-dashboard

## Forskningsprincip

V1 ska inte justeras efter enskilda utfall. V2-idéer testas separat och får bara flyttas till forward-test efter walk-forward-validering. Historiska kval/playoff-rader exkluderas i den rena cross-season-diagnostiken utan att råfilen skrivs om.
