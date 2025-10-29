# CourtCraft 🏀 — NBA Fantasy Calculator

A Flask + Bootstrap web app to explore NBA season stats, build fantasy teams, and compare lineups.
This repository contains a small SQLite-backed Flask server and a responsive UI styled with Bootstrap 5.

> _This README was auto-polished on 2025-10-29 12:52 UTC._

## ✨ Features
- Browse by season, with curated labels (e.g., **2022/23 NBA Season**)
- Assemble teams and compare them across stats
- Autocomplete helpers for player search
- Simple auth endpoints (register/login/logout) with SQLite
- Clean Bootstrap 5 layout with a custom `courtcraft.css` theme

## 🧰 Tech Stack
- **Backend:** Flask, SQLite (via Python stdlib)
- **Frontend:** Jinja templates, Bootstrap 5
- **Data:** pandas for CSV/Excel loading and transformations

## 🚀 Quickstart
```bash
# 1) Create a virtual env (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install deps
pip install -r requirements.txt

# 3) Configure environment (optional)
cp .env.example .env  # then edit SECRET_KEY

# 4) Run the app
flask --app NBAFantasyCalculator/src/app.py --debug run
# Or:
python NBAFantasyCalculator/src/app.py
```

## 🗂️ Project Structure
```
NBAFantasyCalculator/
├─ NBAFantasyCalculator/
│  ├─ src/
│  │  ├─ app.py
│  │  ├─ templates/
│  │  │  ├─ base.html
│  │  │  ├─ home.html
│  │  │  ├─ season.html
│  │  │  ├─ team_assemble.html
│  │  │  ├─ compare_teams.html
│  │  │  └─ auth.html
│  │  └─ static/
│  │     └─ css/courtcraft.css
└─ README.md
```

## 🌐 Routes
| Route Decorator | Handler |
|---|---|
| `"/"` | `home` |
| `"/season/<season>"` | `season_page` |
| `"/season/<season>/data"` | `season_data_page` |
| `"/season/<season>/team", methods=["GET","POST"]` | `team_assemble_page` |
| `"/season/<season>/compare", methods=["GET","POST"]` | `compare_teams` |
| `"/auth"` | `auth` |
| `"/register", methods=["POST"]` | `register` |
| `"/login", methods=["POST"]` | `login` |
| `"/logout"` | `logout` |
| `"/teams"` | `list_teams` |
| `"/autocomplete/<season>"` | `autocomplete` |

Common pages include:
- `/` — Home
- `/season/<season>` — Season page
- `/season/<season>/team` — Team assembly
- `/season/<season>/compare` — Team comparison
- `/auth` — Auth page

## ⚙️ Configuration
- **Database:** `users.db` in `src/` is created automatically (SQLite).
- **Environment:** `.env` file is supported (via `python-dotenv`) for local dev.

## 🧪 Data Ingestion
- pandas is used to load and process CSV/XLS files. Place sample data under a data folder (e.g., `NBAFantasyCalculator/data/`) and adjust the file paths in `app.py` if needed.

## 📸 Screenshots
Add a few screenshots or GIFs here to showcase the flows.

## 🛡️ Notes
- Do not commit real secrets. Keep `.env` local.
- For production, consider gunicorn/uvicorn behind a reverse proxy, and a proper database.

---
Happy hacking!
