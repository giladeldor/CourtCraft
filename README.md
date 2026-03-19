# CourtCraft - NBA Fantasy Calculator

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web%20App-000000?logo=flask&logoColor=white)
![Status](https://img.shields.io/badge/Status-Active%20Development-2EA44F)

CourtCraft is a category-based NBA fantasy companion app built with Flask.
It helps you assemble rosters, compare team strengths, evaluate trades, and run draft recommendations in a clean browser UI.

## Highlights

- Multi-user auth flow (register, login, logout)
- Assemble Team with 13 active spots and up to 2 IR slots
- Team persistence by user and season
- Team-vs-team comparison across category value columns
- Trade Analyzer with per-category impact and verdict summary
- Draft Board recommendations with punt-aware logic
- League Teams management with Power Rankings
- Optional mini player headshots (auto-fetched with fallback)

## Product Behavior

- Logged-out users:
  - League Teams is intentionally empty
  - Board starts empty and does not persist another user's taken list
- Logged-in users:
  - Can only see and edit their own League Teams
  - Board taken-player context is scoped to their own league data
- Latest Assemble Team roster is included as a special My Team row in League Power Rankings

## Tech Stack

- Python 3.12+
- Flask + Jinja2
- pandas
- SQLite
- Bootstrap 5

## Project Layout

- `src/app.py`: main Flask app, routes, scoring logic, ownership rules
- `src/templates/`: Jinja templates
- `src/static/css/courtcraft.css`: app styling
- `src/sync_bbm_rankings.py`: Basketball Monster sync helper
- `src/Nopunts/`: non-punt ranking files
- `src/Tovpunts/`: punt/tov ranking files

## Quick Start

1. Create a virtual environment.

```bash
python -m venv .venv
```

2. Activate it.

```powershell
.venv\Scripts\Activate.ps1
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Configure environment variables (optional but recommended).

```bash
copy .env.example .env
```

5. Run the app.

```bash
python src/app.py
```

Default URL: `http://127.0.0.1:5000`

## Environment Variables

Set these for safer local/public demos:

- `FLASK_SECRET_KEY`: session secret key
- `FLASK_DEBUG`: `1` for debug mode, `0` for off
- `FLASK_HOST`: default `127.0.0.1`
- `FLASK_PORT`: default `5000`

## Rankings Sync

Pull latest rankings into runtime files:

```bash
python src/sync_bbm_rankings.py --season 25-26
```

Sync flow:

- Forces All Players mode
- Validates row volume
- Writes export and runtime copy

## Privacy and Shareability

- Local database files are git-ignored
- Personal runtime data should never be committed
- No personal file paths are required in source