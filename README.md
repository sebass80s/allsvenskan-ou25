# Allsvenskan O/U 2.5 V1

Separat forward-test för Allsvenskan, fristående från Premier League-projektet.

## V1-regel

Modellen uppskattar sannolikheten för **Over 2.5 mål** från aktuell målform, hemma/borta-form och ligans aktuella målmiljö.

En match är endast en V1-kandidat när modellens råa `P(Over 2.5)` ligger i intervallet **55–60 %**.

- **SPELA** om bästa tillgängliga Over 2.5-odds är **>= 1.85**
- **VÄNTA** om matchen är i modellzonen men oddset är lägre än 1.85
- **INGET SPEL** om modellens sannolikhet ligger utanför 55–60 %

Regeln är fryst för forward-testet och ska inte ändras efter enstaka resultat.

## Datakällor

- Historisk Allsvenskan-data lokalt i `data/allsvenskan_raw.csv` (2024–2026 används av V1)
- Live fixtures och odds via OddsPapi, tournament ID `40`
- Bookmakers: Pinnacle, Bet365, Unibet och Betway

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

## Kör liveanalys

```bash
python3 src/live_ou25_v1.py
```

Resultatet sparas till:

```text
data/allsvenskan_live_ou25.csv
```

## Starta dashboard

```bash
streamlit run app.py
```
