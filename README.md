// ...existing code...
# CourtCraft 🏀 — NBA Fantasy Calculator

A small Flask + Bootstrap web app to explore NBA season stats, build fantasy teams, compare lineups, and get draft board recommendations. The app reads curated Excel rankings (multiple scoring variants), stores simple user rosters in SQLite, and exposes autocomplete and recommendation endpoints used by the UI.

> This README was updated to reflect the code tree and routes present in [src/app.py](src/app.py).

## Quick links
- App main: [src/app.py](src/app.py)
- Local parser / helper: [src/BasicParser.py](src/BasicParser.py)
- Templates: [src/templates/](src/templates/)
  - [base.html](src/templates/base.html), [home.html](src/templates/home.html), [season.html](src/templates/season.html), [team_assemble.html](src/templates/team_assemble.html), [compare_teams.html](src/templates/compare_teams.html), [board.html](src/templates/board.html), [teams.html](src/templates/teams.html), [auth.html](src/templates/auth.html)
- Static CSS: [src/static/css/courtcraft.css](src/static/css/courtcraft.css)
- Requirements: [requirements.txt](requirements.txt)

## Features
- Browse seasons and view stats pages.
- Assemble and save rosters (13 active + up to 2 IR) per season.
- Autocomplete for player names backed by season Excel files.
- Draft board UI: mark taken players, seed from saved team, calculate recommendations.
- Simple auth and per-user saved rosters stored in SQLite (`src/users.db`).

## Routes (handlers in [src/app.py](src/app.py))
- `/` — [`home`](src/app.py)
- `/season/<season>` — [`season_page`](src/app.py)
- `/season/<season>/data` — [`season_data_page`](src/app.py)
- `/season/<season>/team` (GET, POST) — [`team_assemble_page`](src/app.py)
- `/season/<season>/compare` (GET, POST) — [`compare_teams`](src/app.py)
- `/season/<season>/board` — board UI rendered by [`board_page`](src/app.py)
- `/season/<season>/board/recommend` (POST) — recommendation API [`board_recommend`](src/app.py)
- `/players/<season>` — returns canonical player names for a season [`load_all_player_names`](src/app.py)
- `/autocomplete/<season>` — autocomplete endpoint [`autocomplete`](src/app.py)
- `/auth`, `/register`, `/login`, `/logout` — auth endpoints (`register`, `login`, `logout` in [src/app.py](src/app.py))
- `/teams` — list saved teams for current user [`list_teams`](src/app.py)

## Project structure
```
README.md
requirements.txt
src/
  app.py
  BasicParser.py
  Nopunts/        # expected location for .xls/.xlsx datasets (nopunt scoring)
  Tovpunts/       # expected location for .xls/.xlsx datasets (tovpunt scoring)
  static/
    css/
      courtcraft.css
    img/
  templates/
    base.html
    home.html
    season.html
    team_assemble.html
    compare_teams.html
    board.html
    teams.html
    auth.html
```

## Quickstart (local dev)
1. Create and activate a virtualenv
```bash
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows
.venv\Scripts\activate
```

2. Install deps
```bash
pip install -r requirements.txt
```

3. Run the app
```bash
# Option A (recommended for dev)
python src/app.py

# Option B (Flask CLI)
# from project root:
flask --app src/app.py --debug run
```

## Configuration & data
- SQLite DB: `src/users.db` created automatically by [`init_db`](src/app.py).
- Excel datasets: filenames and locations are configured in `data_dirs` / `data_files` inside [src/app.py](src/app.py). Example folders: `src/Nopunts/` and `src/Tovpunts/`. The code reads XLS/XLSX via `_read_excel_safe` in [src/app.py](src/app.py).
- Allowed upload extensions: `.xls`, `.xlsx`. The safe reader picks engines (xlrd for .xls, openpyxl for .xlsx).

## Data ingestion / expected columns
- Rankings spreadsheets should include a `Name` column. App expects value columns like `pV`, `rV`, `aV`, `sV`, `bV`, `toV`, `fg%V`, `ft%V`, `3V` in the datasets used for scoring and recommendations.
- If you supply a custom Excel when assembling a team, it will be read temporarily and used for calculations.

## Key implementation notes
- Player name union loader: [`load_all_player_names`](src/app.py) merges names from both nopunts/tovpunt datasets for validation/autocomplete.
- Safe Excel reader: `_read_excel_safe` in [src/app.py](src/app.py) returns None on missing files or reader errors and selects engines by extension.
- Recommendation logic: [`board_recommend`](src/app.py) loads the best available dataset, builds candidate scores using weighted value columns, respects 8-cat scoring (ignores turnovers) and user punts.
- DB helpers: [`get_db`](src/app.py), [`init_db`](src/app.py), and [`load_latest_team`](src/app.py) manage user/team persistence.

## Troubleshooting
- If pages complain about reading datasets, ensure `xlrd` (for .xls) and `openpyxl` (for .xlsx) are installed in your environment.
- Ensure the expected Excel files are present under `src/Nopunts/` and `src/Tovpunts/` (filenames are defined in `data_files` in [src/app.py](src/app.py)).
- Console / server logs will show exceptions for failed reads; the UI surfaces friendly flash messages.

## Development tips
- UI templates are in `src/templates/`. The board UI is [src/templates/board.html](src/templates/board.html) and uses a small client-side localStorage state for taken players and a POST to `/season/<season>/board/recommend` to get suggestions.
- For a quick test of the parser, see [src/BasicParser.py](src/BasicParser.py).

## License & notes
- Do not commit real secrets. Replace `app.secret_key` in [src/app.py](src/app.py) with a secure value for production or use a `.env`.
- For production, serve via a WSGI server (gunicorn, uWSGI) behind a reverse proxy and use a proper DB.

Happy hacking!
{ changed code }
// ...existing code...