# CourtCraft - NBA Fantasy Calculator

CourtCraft is a Flask web app for category-based NBA fantasy basketball.
It helps you build and evaluate your team, compare matchups, run draft board recommendations, and manage your private league context.

## What It Does

- Account system (register/login/logout)
- Assemble Team (13 active + up to 2 IR)
- Persisted team storage per user + season
- Team quality analysis based on category value columns
- Compare Teams head-to-head
- Trade Analyzer with category delta and verdict
- Draft Board with live recommendations
- League Teams manager with Power Rankings
- Basketball Monster sync for latest rankings
- Optional player mini-headshots (auto-fetched; no local image pack required)

## Recent Changes

### Added / Improved

- Per-user League Teams isolation:
  - Guests see an empty League Teams page
  - Logged-in users only see their own league teams
  - Board "taken players" now only includes the logged-in user's league teams
- Assemble Team integration into League Power Rankings:
  - Latest saved Assemble Team roster is included as a special "My Team" row in power rankings
- Performance:
  - Rankings dataframes are cached in-memory by file mtime to reduce repeated Excel parsing
- UI/UX:
  - Bright basketball theme and colorful action tiles
  - Compact season action cards
- Player photos:
  - Automatic best-effort headshot URL generation
  - Falls back to generated avatars when a headshot is unavailable

### Removed

- Waiver Wire feature removed (route + UI)
- Stats Leaders feature removed from season flow
  - Old `/season/<season>/data` now redirects back to season page with an info flash

## Stack

- Python 3.12+
- Flask
- pandas
- SQLite
- Bootstrap + Jinja templates

## Project Structure

- `src/app.py` - main Flask app and business logic
- `src/templates/` - Jinja templates
- `src/static/css/courtcraft.css` - app styling
- `src/sync_bbm_rankings.py` - BBM sync script
- `src/Nopunts/` - nopunt ranking files
- `src/Tovpunts/` - tovpunt ranking files
- `src/users.db` - SQLite database (created/updated automatically)

## Setup

1. Create virtual environment

```bash
python -m venv .venv
```

2. Activate environment

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Run app

```bash
python src/app.py
```

App runs at:

- `http://127.0.0.1:5000`

## Data Files

Configured in `src/app.py` via `data_files` and `data_dirs`.
The app supports `.xls` and `.xlsx`, with safe reader fallback logic.

## Basketball Monster Sync

Sync latest rankings into runtime file:

```bash
python src/sync_bbm_rankings.py --season 25-26
```

Behavior:

- Forces "All Players" mode
- Validates expected row volume
- Writes both:
  - main export file
  - runtime copy (used by app to avoid Excel lock issues)

## Auth + Data Ownership

- Teams in `teams` are always per-user
- League teams in `league_teams` are now per-user
- If not logged in:
  - League Teams view is intentionally empty
  - League team management is disabled

## Notes

- This is a dev server (`debug=True`) and not meant for production deployment as-is.
- Replace `app.secret_key` in `src/app.py` before production use.
