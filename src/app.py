import os
import math
import itertools
import sqlite3
import pandas as pd
from flask import (
    Flask, render_template, request, jsonify,
    session, flash, redirect, url_for
)
from datetime import datetime
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Replace with a secure secret key

# -----------------------------------------------------------------------------
# DATABASE SETUP
# -----------------------------------------------------------------------------
DATABASE = os.path.join(os.path.dirname(__file__), 'users.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("""
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
      )
    """)
    db.commit()
    db.close()

# Initialize the database at startup
init_db()

# -----------------------------------------------------------------------------
# CONTEXT PROCESSOR
# -----------------------------------------------------------------------------
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

# -----------------------------------------------------------------------------
# SETTINGS FOR DATA FILES
# -----------------------------------------------------------------------------
data_dirs = {
    "nopunts": "Nopunts",
    "tovpunt": "Tovpunts"
}
data_files = {
    "24-25": {
        "nopunts": "BBM_PlayerRankings2425_nopunt.xls",
        "tovpunt": "BBM_PlayerRankings2425_tovpunt.xls"
    },
    "23-24": {
        "nopunts": "BBM_PlayerRankings2324_nopunt.xls",
        "tovpunt": "BBM_PlayerRankings2324_tovpunt.xls"
    },
    "22-23": {
        "nopunts": "BBM_PlayerRankings2223_nopunt.xls",
        "tovpunt": "BBM_PlayerRankings2223_tovpunt.xls"
    },
    "21-22": {
        "nopunts": "BBM_PlayerRankings2122_nopunt.xls",
        "tovpunt": "BBM_PlayerRankings2122_tovpunt.xls"
    },
    "20-21": {
        "nopunts": "BBM_PlayerRankings2021_nopunt.xls",
        "tovpunt": "BBM_PlayerRankings2021_tovpunt.xls"
    }
}

# -----------------------------------------------------------------------------
# UTILITY FUNCTIONS
# -----------------------------------------------------------------------------
def get_color(value, min_val, max_val):
    if pd.isna(value):
        return "white"
    if math.isclose(min_val, max_val):
        return "hsl(60, 100%, 85%)"
    ratio = (value - min_val) / (max_val - min_val)
    hue = 120 * ratio
    return f"hsl({hue}, 100%, 85%)"

def process_season_data(season, data_type="nopunts"):
    if season not in data_files or data_type not in data_files[season]:
        return None
    file_path = os.path.join(
        os.path.dirname(__file__),
        data_dirs[data_type],
        data_files[season][data_type]
    )
    df = pd.read_excel(file_path)
    if data_type == "tovpunt":
        df.columns = [c.strip() for c in df.columns]
        rename_map = {}
        for c in df.columns:
            lc = c.lower()
            if lc in ("leagv", "leaguev"):
                rename_map[c] = "LeagV"
            elif lc in ("puntv", "puntiv"):
                rename_map[c] = "puntV"
        df.rename(columns=rename_map, inplace=True)

    # Build top-10 leaders
    results = {}
    stats = [
        ('p/g', False, 'Points'), ('r/g', False, 'Rebounds'), ('a/g', False, 'Assists'),
        ('s/g', False, 'Steals'), ('b/g', False, 'Blocks'), ('to/g', True, 'Turnovers'),
        ('fg%', False, 'FG%'), ('ft%', False, 'FT%'), ('3/g', False, '3PG')
    ]
    for col, asc, title in stats:
        results[title] = df[['Name','Team',col]] \
            .sort_values(by=col, ascending=asc) \
            .head(10) \
            .to_dict(orient='records')

    # Value columns
    for col in ["pV","rV","aV","sV","bV","toV","fg%V","ft%V","3V"]:
        asc = (col == 'toV')
        results[f"{col} Leaders"] = df[['Name','Team',col]] \
            .sort_values(by=col, ascending=asc) \
            .head(10) \
            .to_dict(orient='records')

    return results

# -----------------------------------------------------------------------------
# ROUTES: Home / Seasons / Data / Team
# -----------------------------------------------------------------------------
nba_seasons = [f"{y%100:02d}/{(y+1)%100:02d}" for y in range(2024, 2010, -1)]
season_data = {
    "24-25": {"title":"2024/25 NBA Season"},
    "23-24": {"title":"2023/24 NBA Season"},
    "22-23": {"title":"2022/23 NBA Season"},
    "21-22": {"title":"2021/22 NBA Season"},
    "20-21": {"title":"2020/21 NBA Season"}
}

@app.route("/")
def home():
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    formatted = season.replace("-","/")
    data = season_data.get(season, {})
    return render_template(
        "season.html",
        season=formatted,
        season_url=season,
        **data
    )

@app.route("/season/<season>/data")
def season_data_page(season):
    results = process_season_data(season, data_type="nopunts")
    return render_template(
        "data_calculation.html",
        season=season.replace("-","/"),
        results=results
    )

@app.route("/season/<season>/team", methods=["GET","POST"])
def team_assemble_page(season):
    formatted = season.replace("-","/")
    season_url = season
    data_type = request.form.get("data_type","nopunts") if request.method=="POST" else "nopunts"
    registered = session.get("registered_players", {})
    players = registered.get(season, [])

    results = totals = analysis = None
    punt_buttons = []

    if request.method=="POST":
        players = [request.form.get(f"player{i}","").strip() for i in range(1,14) if request.form.get(f"player{i}","").strip()]
        registered[season] = players
        session["registered_players"] = registered

        file_path = os.path.join(
            os.path.dirname(__file__),
            data_dirs[data_type],
            data_files[season][data_type]
        )
        df = pd.read_excel(file_path)
        if data_type=="tovpunt":
            df.columns = [c.strip() for c in df.columns]
            rm = {}
            for c in df.columns:
                lc=c.lower()
                if lc in ("leagv","leaguev"): rm[c]="LeagV"
                if lc in ("puntv","puntiv"):  rm[c]="puntV"
            df.rename(columns=rm, inplace=True)

        df_f = df[df['Name'].str.lower().isin([p.lower() for p in players])]
        results = df_f.to_dict(orient='records')
        # ... your existing logic for injuries, exclusions, rounding, coloring, analysis ...

    return render_template(
        "team_assemble.html",
        season=formatted,
        season_url=season_url,
        registered_players=players,
        results=results,
        totals=totals,
        analysis=analysis,
        punt_buttons=punt_buttons,
        data_type=data_type
    )

# -----------------------------------------------------------------------------
# ROUTES: Authentication
# -----------------------------------------------------------------------------
@app.route("/auth")
def auth():
    return render_template("auth.html")

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"].strip()
    password = request.form["password"]
    confirm  = request.form["confirm_password"]
    if password != confirm:
        flash("Passwords do not match", "danger")
        return redirect(url_for("auth"))

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username,password_hash) VALUES (?,?)",
            (username, generate_password_hash(password))
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("Username already taken", "warning")
        return redirect(url_for("auth"))

    flash("Registration successful! Please log in.", "success")
    return redirect(url_for("auth"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"].strip()
    password = request.form["password"]
    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        session["user"] = username
        flash(f"Welcome back, {username}!", "success")
        return redirect(url_for("home"))
    flash("Invalid credentials", "danger")
    return redirect(url_for("auth"))

# -----------------------------------------------------------------------------
# ROUTES: Autocomplete
# -----------------------------------------------------------------------------
@app.route("/autocomplete/<season>")
def autocomplete(season):
    term = request.args.get("term","").lower()
    suggestions = []
    db_type = "nopunts"
    file_path = os.path.join(
        os.path.dirname(__file__),
        data_dirs[db_type],
        data_files[season][db_type]
    )
    df = pd.read_excel(file_path)
    for name in df['Name'].dropna().unique():
        if term in name.lower():
            suggestions.append(name)
    return jsonify(suggestions)

if __name__ == "__main__":
    app.run(debug=True)
