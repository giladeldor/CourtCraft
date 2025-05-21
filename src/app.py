import os
import math
import itertools
import sqlite3
import json
import pandas as pd
from flask import (
    Flask, render_template, request, jsonify,
    session, flash, redirect, url_for
)
from datetime import datetime
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Replace with a secure secret

# -----------------------------------------------------------------------------
# DATABASE SETUP
# -----------------------------------------------------------------------------
DATABASE = os.path.join(os.path.dirname(__file__), "users.db")

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
      );
    """)
    db.execute("""
      CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        season TEXT NOT NULL,
        players TEXT NOT NULL,
        data_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
      );
    """)
    db.commit()
    db.close()

init_db()

# -----------------------------------------------------------------------------
# CONTEXT PROCESSOR
# -----------------------------------------------------------------------------
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year, 'logged_in_user': session.get("user")}

# -----------------------------------------------------------------------------
# DATA FILE CONFIG
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
# UTILITIES
# -----------------------------------------------------------------------------
def get_color(value, min_val, max_val):
    if pd.isna(value) or min_val == max_val:
        return "hsl(60,100%,85%)"
    ratio = (value - min_val) / (max_val - min_val)
    hue = 120 * ratio
    return f"hsl({hue},100%,85%)"

# -----------------------------------------------------------------------------
# STATIC SEASONS
# -----------------------------------------------------------------------------
nba_seasons = [f"{y%100:02d}/{(y+1)%100:02d}" for y in range(2024,2010,-1)]
season_data = {
    "24-25": {"title": "2024/25 NBA Season"},
    "23-24": {"title": "2023/24 NBA Season"},
    "22-23": {"title": "2022/23 NBA Season"},
    "21-22": {"title": "2021/22 NBA Season"},
    "20-21": {"title": "2020/21 NBA Season"}
}

# -----------------------------------------------------------------------------
# ROUTES: Home, Seasons, Data Calculation
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    formatted = season.replace("-", "/")
    data = season_data.get(season, {})
    return render_template("season.html",
                           season=formatted,
                           season_url=season,
                           **data)

@app.route("/season/<season>/data")
def season_data_page(season):
    # placeholder: you already have this implemented
    results = process_season_data(season, data_type="nopunts")
    return render_template("data_calculation.html",
                           season=season.replace("-", "/"),
                           results=results)

# -----------------------------------------------------------------------------
# ROUTE: Compare Teams (with advice)
# -----------------------------------------------------------------------------
@app.route("/season/<season>/compare", methods=["GET","POST"])
def compare_teams(season):
    formatted = season.replace("-", "/")
    data_type = "nopunts"  # fixed for comparison

    # Team names
    teamA_name = request.form.get("teamA_name", "Team A") if request.method=="POST" else "Team A"
    teamB_name = request.form.get("teamB_name", "Team B") if request.method=="POST" else "Team B"

    teamA = []
    teamB = []
    comparison = None
    match_winner = None
    teamA_advice = []

    if request.method == "POST":
        # Collect rosters
        teamA = [
            request.form.get(f"A_player{i}", "").strip()
            for i in range(1,14)
            if request.form.get(f"A_player{i}", "").strip()
        ]
        teamB = [
            request.form.get(f"B_player{i}", "").strip()
            for i in range(1,14)
            if request.form.get(f"B_player{i}", "").strip()
        ]

        # Load the Excel
        fp = os.path.join(
            os.path.dirname(__file__),
            data_dirs[data_type],
            data_files[season][data_type]
        )
        df = pd.read_excel(fp)
        df['Name'] = df['Name'].astype(str).str.strip()

        # Value columns
        val_cols = ["pV","rV","aV","sV","bV","toV","fg%V","ft%V","3V"]
        def sum_stats(roster):
            sub = df[df['Name'].str.lower().isin([n.lower() for n in roster])]
            s = sub[val_cols].sum(numeric_only=True)
            return {c: round(s[c],2) for c in val_cols}

        totalsA = sum_stats(teamA)
        totalsB = sum_stats(teamB)

        # Build per-stat comparison + advice
        comp = []
        countA = countB = 0
        for c in val_cols:
            a = totalsA.get(c,0)
            b = totalsB.get(c,0)
            if a > b:
                winner = teamA_name
                countA += 1
            elif b > a:
                winner = teamB_name
                countB += 1
                teamA_advice.append(f"You need to improve {c}.")
            else:
                winner = "Tie"
            comp.append({"stat":c,"teamA":a,"teamB":b,"winner":winner})
        comparison = comp

        # Overall winner
        if countA > countB:
            match_winner = teamA_name
        elif countB > countA:
            match_winner = teamB_name
        else:
            match_winner = "Tie"

    return render_template("compare_teams.html",
                           season=formatted,
                           season_url=season,
                           teamA=teamA,
                           teamB=teamB,
                           teamA_name=teamA_name,
                           teamB_name=teamB_name,
                           comparison=comparison,
                           match_winner=match_winner,
                           teamA_advice=teamA_advice)

# -----------------------------------------------------------------------------
# ROUTES: Auth / Register / Login / Logout / List Saved Teams / Autocomplete
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
        flash("Passwords do not match","danger")
        return redirect(url_for("auth"))
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users(username,password_hash) VALUES(?,?)",
            (username, generate_password_hash(password))
        )
        db.commit()
        row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        session["user"] = username
        session["user_id"] = row["id"]
        flash("Registered & logged in!","success")
    except sqlite3.IntegrityError:
        flash("Username already taken","danger")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"].strip()
    password = request.form["password"]
    db = get_db()
    row = db.execute(
        "SELECT id,password_hash FROM users WHERE username=?", (username,)
    ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        session["user"] = username
        session["user_id"] = row["id"]
        flash(f"Welcome back, {username}!","success")
        return redirect(url_for("home"))
    flash("Invalid credentials","danger")
    return redirect(url_for("auth"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/teams")
def list_teams():
    if "user_id" not in session:
        flash("Please log in","warning")
        return redirect(url_for("auth"))
    db = get_db()
    rows = db.execute(
        "SELECT season,players,data_type,created_at FROM teams "
        "WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    teams = [{
        "season": r["season"].replace("-","/"),
        "players": json.loads(r["players"]),
        "data_type": r["data_type"],
        "created": r["created_at"]
    } for r in rows]
    return render_template("teams.html", teams=teams)

@app.route("/autocomplete/<season>")
def autocomplete(season):
    term = request.args.get("term","").lower()
    suggestions = []
    fp = os.path.join(
        os.path.dirname(__file__),
        data_dirs["nopunts"],
        data_files[season]["nopunts"]
    )
    df = pd.read_excel(fp)
    for name in df['Name'].dropna().unique():
        if term in name.lower():
            suggestions.append(name)
    return jsonify(suggestions)

if __name__ == "__main__":
    app.run(debug=True)
