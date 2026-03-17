import os
import itertools
import sqlite3
import json
import pandas as pd
import traceback
from flask import (
    Flask, render_template, request, jsonify,
    session, flash, redirect, url_for
)
from datetime import datetime
    # markupsafe is used for tiny HTML markers in table cells
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your-secret-key"  # replace with a secure random key

# -----------------------------------------------------------------------------
# DB
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
# Template globals
# -----------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {'current_year': datetime.now().year, 'logged_in_user': session.get("user")}

# -----------------------------------------------------------------------------
# Data files
# -----------------------------------------------------------------------------
data_dirs = {"nopunts": "Nopunts", "tovpunt": "Tovpunts"}
data_files = {
    "25-26": {"nopunts": "BBM_PlayerRankings2526_nopunt.xls"},
    "24-25": {"nopunts": "BBM_PlayerRankings2425_nopunt.xls", "tovpunt": "BBM_PlayerRankings2425_tovpunt.xls"},
    "23-24": {"nopunts": "BBM_PlayerRankings2324_nopunt.xls", "tovpunt": "BBM_PlayerRankings2324_tovpunt.xls"},
    "22-23": {"nopunts": "BBM_PlayerRankings2223_nopunt.xls", "tovpunt": "BBM_PlayerRankings2223_tovpunt.xls"},
    "21-22": {"nopunts": "BBM_PlayerRankings2122_nopunt.xls", "tovpunt": "BBM_PlayerRankings2122_tovpunt.xls"},
    "20-21": {"nopunts": "BBM_PlayerRankings2021_nopunt.xls", "tovpunt": "BBM_PlayerRankings2021_tovpunt.xls"}
}

ALLOWED_EXT = {"xls", "xlsx"}
def allowed_file(filename): return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXT

def get_color(value, min_val, max_val):
    if pd.isna(value) or min_val == max_val: return "hsl(60,100%,85%)"
    ratio = (value - min_val) / (max_val - min_val); hue = 120 * ratio
    return f"hsl({hue},100%,85%)"

nba_seasons = [f"{y%100:02d}/{(y+1)%100:02d}" for y in range(2025, 2010, -1)]
season_data = {
    "25-26": {"title": "2025/26 NBA Season"},
    "24-25": {"title": "2024/25 NBA Season"},
    "23-24": {"title": "2023/24 NBA Season"},
    "22-23": {"title": "2022/23 NBA Season"},
    "21-22": {"title": "2021/22 NBA Season"},
    "20-21": {"title": "2020/21 NBA Season"}
}

# -----------------------------------------------------------------------------
# SAFE EXCEL READER (handles .xls/.xlsx and engine selection)
# -----------------------------------------------------------------------------
def _read_excel_safe(path: str):
    """
    Return a DataFrame or None. Picks the appropriate engine for .xls or .xlsx.
    Requires: xlrd==2.0.1 for .xls, openpyxl for .xlsx.
    """
    if not os.path.exists(path):
        return None
    _, ext = os.path.splitext(path.lower())
    try:
        if ext == ".xlsx":
            return pd.read_excel(path, engine="openpyxl")
        elif ext == ".xls":
            return pd.read_excel(path, engine="xlrd")
        else:
            return pd.read_excel(path)
    except Exception:
        return None

# ----- Player name loader (union of nopunts/tovpunt) -----
def load_all_player_names(season: str):
    names = set()
    for data_type in ("nopunts", "tovpunt"):
        try:
            fname = data_files[season][data_type]
            path = os.path.join(os.path.dirname(__file__), data_dirs[data_type], fname)
        except KeyError:
            continue
        df = _read_excel_safe(path)
        if df is None or "Name" not in df.columns:
            continue
        for n in df["Name"].dropna().astype(str).str.strip().unique():
            if n:
                names.add(n)
    return sorted(names, key=lambda s: s.lower())

@app.route("/players/<season>")
def players_for_season(season):
    """Return all valid player names for a season (used to validate Board inputs)."""
    return jsonify({"names": load_all_player_names(season)})

# -----------------------------------------------------------------------------
# Routes: basic pages
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    formatted = season.replace("-", "/")
    data = season_data.get(season, {})
    return render_template("season.html", season=formatted, season_url=season, **data)

@app.route("/season/<season>/data")
def season_data_page(season):
    fp = os.path.join(os.path.dirname(__file__), data_dirs["nopunts"], data_files[season]["nopunts"])
    df = _read_excel_safe(fp)
    if df is None:
        flash("Could not read default dataset. Please ensure xlrd/openpyxl are installed (see README).", "danger")
        return render_template("data_calculation.html", season=season.replace("-", "/"), results={})
    return render_template("data_calculation.html", season=season.replace("-", "/"), results={})

# -----------------------------------------------------------------------------
# Assemble Team
# -----------------------------------------------------------------------------
@app.route("/season/<season>/team", methods=["GET","POST"])
def team_assemble_page(season):
    formatted = season.replace("-", "/")
    season_url = season
    raw_type = request.form.get("data_type", "nopunts") if request.method=="POST" else "nopunts"
    data_type = "tovpunt" if "tov" in raw_type else "nopunts"

    if request.method=="GET" and session.get("user_id"):
        db = get_db()
        row = db.execute(
            "SELECT players,data_type FROM teams WHERE user_id=? AND season=? ORDER BY created_at DESC LIMIT 1",
            (session["user_id"], season)
        ).fetchone()
        if row:
            registered = json.loads(row["players"]); raw_type = row["data_type"]
            data_type = "tovpunt" if "tov" in raw_type else "nopunts"
        else:
            registered = []
    else:
        registered = []

    results = totals = analysis = None
    punt_buttons = []

    if request.method=="POST":
        registered = [request.form.get(f"player{i}", "").strip()
                      for i in range(1,14) if request.form.get(f"player{i}", "").strip()]
        if session.get("user_id"):
            db = get_db()
            db.execute(
                "INSERT INTO teams(user_id,season,players,data_type,created_at) VALUES(?,?,?,?,?)",
                (session["user_id"], season, json.dumps(registered), raw_type, datetime.now().isoformat())
            )
            db.commit()

        # ---- READ EXCEL (uploaded or default) via SAFE READER ----
        uploaded = request.files.get("custom_excel")
        if uploaded and allowed_file(uploaded.filename):
            tmp_ext = os.path.splitext(uploaded.filename)[1].lower()
            tmp_path = os.path.join(os.path.dirname(__file__), f"_upload{tmp_ext}")
            uploaded.save(tmp_path)
            df = _read_excel_safe(tmp_path)
            try: os.remove(tmp_path)
            except Exception: pass
        else:
            fp = os.path.join(os.path.dirname(__file__), data_dirs[data_type], data_files[season][data_type])
            df = _read_excel_safe(fp)

        if df is None:
            flash("Could not read the rankings file. Install/upgrade xlrd (for .xls) and openpyxl (for .xlsx).", "danger")
            return render_template(
                "team_assemble.html",
                season=formatted, season_url=season,
                registered_players=registered,
                results=None, totals=None, analysis=None,
                punt_buttons=[], raw_type=raw_type, data_type=data_type
            )

        # Normalize columns and names
        df.columns = [c.strip() for c in df.columns]
        df['Name'] = df['Name'].astype(str).str.strip()
        if data_type=="tovpunt":
            rename_map = {}
            for c in df.columns:
                lc = c.lower()
                if lc in ("leagv","leaguev"): rename_map[c] = "LeagV"
                if lc in ("puntv","puntiv"):  rename_map[c] = "puntV"
            df.rename(columns=rename_map, inplace=True)

        clean = [n.lower() for n in registered]
        df_f = df[df['Name'].str.lower().isin(clean)]
        results = df_f.to_dict(orient='records')

        exclude = ["Round","Rank","Value","Team","Inj","Pos","m/g","USG","fga/g", "fta/g","LeagV", "puntV", "g", "p/g","r/g","a/g","s/g","b/g","to/g","3/g","fg%","ft%"]
        for r in results:
            if r.get("g",0) < 40:
                r["Name"] += Markup(" <span style='color:red;font-weight:bold;'>+</span>")
            for c in exclude: r.pop(c, None)

        tot_s = df_f.select_dtypes(include="number").sum(numeric_only=True)
        totals = tot_s.to_dict()
        for c in exclude: totals.pop(c, None)
        totals["Name"] = "Total"; totals["Team"] = ""
        for k,v in totals.items():
            if isinstance(v,float): totals[k] = round(v,2)
        for r in results:
            for k,v in r.items():
                if isinstance(v,float): r[k] = round(v,2)
        val_cols = ["pV","rV","aV","sV","bV","toV","fg%V","ft%V","3V"]
        mins = {c: df_f[c].min() if c in df_f else 0 for c in val_cols}
        maxs = {c: df_f[c].max() if c in df_f else 0 for c in val_cols}
        for r in results:
            for c in val_cols:
                color = get_color(r.get(c,0), mins[c], maxs[c])
                r[f"{c}_style"] = f'style=\"background-color:{color}\"'
        for c in val_cols:
            color = get_color(totals.get(c,0), mins[c], maxs[c])
            totals[f"{c}_style"] = f'style=\"background-color:{color}\"'

        cnt = sum(1 for c in val_cols if totals.get(c,0)>0)
        analysis = "bad team" if cnt < 2 else ("ok team" if cnt < 3 else ("good team" if cnt < 4 else "great team"))

        punts = [c for c in val_cols if totals.get(c,0)<-1]
        if punts:
            for r in range(1,len(punts)+1):
                for combo in itertools.combinations(punts,r):
                    punt_buttons.append("+".join(combo))
            punt_buttons.insert(0,"nopunts")
        else:
            punt_buttons = ["nopunts"]

        if data_type=="nopunts":
            for r in results: r["LeagV"] = r["puntV"] = ""
            totals["LeagV"] = totals["puntV"] = ""

    return render_template(
        "team_assemble.html",
        season=formatted, season_url=season,
        registered_players=registered,
        results=results, totals=totals,
        analysis=analysis, punt_buttons=punt_buttons,
        raw_type=raw_type, data_type=data_type
    )

# -----------------------------------------------------------------------------
# Compare Teams
# -----------------------------------------------------------------------------
@app.route("/season/<season>/compare", methods=["GET","POST"])
def compare_teams(season):
    formatted = season.replace("-", "/")
    data_type = "nopunts"
    teamA_name = request.form.get("teamA_name","Team A") if request.method=="POST" else "Team A"
    teamB_name = request.form.get("teamB_name","Team B") if request.method=="POST" else "Team B"
    teamA=[]; teamB=[]; comparison=None; match_winner=None; teamA_advice=[]

    if request.method=="POST":
        teamA = [request.form.get(f"A_player{i}","").strip() for i in range(1,14) if request.form.get(f"A_player{i}","").strip()]
        teamB = [request.form.get(f"B_player{i}","").strip() for i in range(1,14) if request.form.get(f"B_player{i}","").strip()]
        fp = os.path.join(os.path.dirname(__file__), data_dirs[data_type], data_files[season][data_type])
        df = _read_excel_safe(fp)
        if df is None:
            flash("Could not read default dataset for comparison. Install/upgrade xlrd/openpyxl.", "danger")
            return render_template(
                "compare_teams.html",
                season=formatted, season_url=season,
                teamA=teamA, teamB=teamB,
                teamA_name=teamA_name, teamB_name=teamB_name,
                comparison=None, match_winner=None, teamA_advice=[]
            )

        df['Name'] = df['Name'].astype(str).str.strip()
        val_cols = ["pV","rV","aV","sV","bV","toV","fg%V","ft%V","3V"]
        def sum_stats(roster):
            sub = df[df['Name'].str.lower().isin([n.lower() for n in roster])]
            s   = sub[val_cols].sum(numeric_only=True)
            return {c:round(s[c],2) for c in val_cols}
        totalsA = sum_stats(teamA); totalsB = sum_stats(teamB)

        comp=[]; cntA=cntB=0
        for c in val_cols:
            a = totalsA.get(c,0); b = totalsB.get(c,0)
            if a>b: winner=teamA_name; cntA+=1
            elif b>a: winner=teamB_name; cntB+=1; teamA_advice.append(f"You need to improve {c}.")
            else: winner="Tie"
            comp.append({"stat":c,"teamA":a,"teamB":b,"winner":winner})
        comparison=comp; match_winner = teamA_name if cntA>cntB else (teamB_name if cntB>cntA else "Tie")

    return render_template(
        "compare_teams.html",
        season=formatted, season_url=season,
        teamA=teamA, teamB=teamB,
        teamA_name=teamA_name, teamB_name=teamB_name,
        comparison=comparison, match_winner=match_winner, teamA_advice=teamA_advice
    )

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
@app.route("/auth")
def auth(): return render_template("auth.html")

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"].strip()
    pwd      = request.form["password"]; conf = request.form["confirm_password"]
    if pwd != conf:
        flash("Passwords do not match","danger"); return redirect(url_for("auth"))
    db = get_db()
    try:
        db.execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (username, generate_password_hash(pwd)))
        db.commit()
        row = db.execute("SELECT id FROM users WHERE username=?", (username)).fetchone()  # type: ignore
        if not row:
            row = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        session["user"] = username; session["user_id"] = row["id"]; flash("Registered & logged in!","success")
    except sqlite3.IntegrityError:
        flash("Username already taken","danger")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"].strip(); pwd = request.form["password"]
    db = get_db()
    row = db.execute("SELECT id,password_hash FROM users WHERE username=?", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], pwd):
        session["user"] = username; session["user_id"] = row["id"]; flash(f"Welcome back, {username}!","success")
        return redirect(url_for("home"))
    flash("Invalid credentials","danger"); return redirect(url_for("auth"))

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("home"))

@app.route("/teams")
def list_teams():
    if "user_id" not in session:
        flash("Please log in","warning"); return redirect(url_for("auth"))
    db = get_db()
    rows = db.execute(
        "SELECT season,players,data_type,created_at FROM teams WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    teams = [{
        "season": r["season"].replace("-","/"),
        "players": json.loads(r["players"]),
        "data_type": r["data_type"],
        "created": r["created_at"]
    } for r in rows]
    return render_template("teams.html", teams=teams)

# -----------------------------------------------------------------------------
# Autocomplete (uses safe reader)
# -----------------------------------------------------------------------------
@app.route("/autocomplete/<season>")
def autocomplete(season):
    term = (request.args.get("term", "") or "").strip().lower()
    if len(term) < 2: return jsonify([])
    names = set()
    for data_type in ("nopunts", "tovpunt"):
        try:
            fname = data_files[season][data_type]
            path = os.path.join(os.path.dirname(__file__), data_dirs[data_type], fname)
        except KeyError:
            continue
        df = _read_excel_safe(path)
        if df is None or "Name" not in df.columns: continue
        try:
            series = df["Name"].dropna().astype(str).str.strip().unique()
        except Exception:
            continue
        for name in series:
            if term in name.lower(): names.add(name)
    return jsonify(sorted(names)[:50])

# -----------------------------------------------------------------------------
# Helper: latest team for a season
# -----------------------------------------------------------------------------
def load_latest_team(user_id: int, season: str):
    db = get_db()
    row = db.execute(
        "SELECT players, data_type FROM teams WHERE user_id=? AND season=? ORDER BY datetime(created_at) DESC LIMIT 1",
        (user_id, season)
    ).fetchone()
    if not row: return [], "nopunts"
    try: players = json.loads(row["players"]) or []
    except Exception: players = []
    return players, row["data_type"]

# -----------------------------------------------------------------------------
# Recommendation API
# -----------------------------------------------------------------------------
CAT_LABEL_TO_VALCOL = {
    "PTS": "pV", "REB": "rV", "AST": "aV", "STL": "sV", "BLK": "bV",
    "TO": "toV", "FG%": "fg%V", "FT%": "ft%V", "3PM": "3V"
}
VAL_COLS = ["pV","rV","aV","sV","bV","toV","fg%V","ft%V","3V"]

def _load_df_for_recs(season: str, preferred_type: str):
    order = []
    if preferred_type in ("nopunts","tovpunt"): order.append(preferred_type)
    if "nopunts" not in order: order.append("nopunts")
    if "tovpunt" not in order: order.append("tovpunt")
    for t in order:
        try:
            path = os.path.join(os.path.dirname(__file__), data_dirs[t], data_files[season][t])
        except KeyError:
            continue
        df = _read_excel_safe(path)
        if df is not None and "Name" in df.columns:
            df.columns = [c.strip() for c in df.columns]
            df["Name"] = df["Name"].astype(str).str.strip()
            return df, t
    return None, preferred_type or "nopunts"

def _current_totals(df, roster):
    sub = df[df["Name"].str.lower().isin([n.lower() for n in roster])]
    totals = sub[VAL_COLS].sum(numeric_only=True)
    return {c: float(totals.get(c, 0.0)) for c in VAL_COLS}

def _build_waiver_recommendations(df, roster, free_agents, scoring_mode, scoring_type, punt_labels, limit=12):
    punt_valcols = {CAT_LABEL_TO_VALCOL.get(lbl) for lbl in (punt_labels or [])}
    roster_l = {n.lower() for n in roster}
    fa_l = {n.lower() for n in free_agents}

    # Candidate pool is restricted to the provided free agents list.
    cand = df[df["Name"].str.lower().isin(fa_l)].copy()
    cand = cand[~cand["Name"].str.lower().isin(roster_l)]
    if cand.empty:
        return [], [], {}

    cols = [c for c in VAL_COLS if c in cand.columns]
    if not cols:
        return [], [], {}

    effective_cols = [c for c in cols if not (scoring_type == "8cat" and c == "toV")]
    totals = _current_totals(df, roster)
    weak_cols = sorted(
        [c for c in effective_cols if c not in punt_valcols],
        key=lambda c: totals.get(c, 0.0)
    )
    weak_focus = weak_cols[:3]

    weights = {c: (0.0 if c in punt_valcols else 1.0) for c in effective_cols}
    for c in weak_focus:
        if scoring_mode == "short_term":
            weights[c] = weights.get(c, 0.0) + 1.25
        else:
            weights[c] = weights.get(c, 0.0) + 0.65

    # In short-term mode, push counting stats and slightly reduce percentage impact.
    if scoring_mode == "short_term":
        for c in ("fg%V", "ft%V"):
            if c in weights and weights[c] > 0:
                weights[c] *= 0.8

    cand[effective_cols] = cand[effective_cols].fillna(0.0)
    scored = []
    for _, row in cand.iterrows():
        score = 0.0
        for c in effective_cols:
            score += float(row[c]) * weights.get(c, 0.0)

        top_stats = sorted(
            [(c, float(row[c])) for c in effective_cols if weights.get(c, 0.0) > 0],
            key=lambda x: x[1],
            reverse=True
        )[:3]

        strengths = []
        for c, v in top_stats:
            label = next((lbl for lbl, vc in CAT_LABEL_TO_VALCOL.items() if vc == c), c)
            strengths.append(f"{label}: {round(v, 2)}")

        scored.append({
            "name": row["Name"],
            "fit_score": round(score, 3),
            "strengths": strengths
        })

    scored.sort(key=lambda x: x["fit_score"], reverse=True)

    col_to_label = {v: k for k, v in CAT_LABEL_TO_VALCOL.items()}
    weak_labels = [col_to_label.get(c, c) for c in weak_focus]
    totals_labels = {col_to_label.get(c, c): round(float(totals.get(c, 0.0)), 2) for c in effective_cols}
    return scored[:limit], weak_labels, totals_labels

def _totals_for_players(df, players, cols):
    if not players:
        return {c: 0.0 for c in cols}
    subset = df[df["Name"].str.lower().isin({n.lower() for n in players})]
    sums = subset[cols].sum(numeric_only=True)
    return {c: float(sums.get(c, 0.0)) for c in cols}

def _analyze_trade_side(df, roster, send_players, receive_players, cols):
    before = _totals_for_players(df, roster, cols)

    send_l = {n.lower() for n in send_players}
    base_after = [p for p in roster if p.lower() not in send_l]
    existing = {p.lower() for p in base_after}
    for p in receive_players:
        if p.lower() not in existing:
            base_after.append(p)
            existing.add(p.lower())

    after = _totals_for_players(df, base_after, cols)
    delta = {c: round(after[c] - before[c], 2) for c in cols}
    return {
        "before": {c: round(before[c], 2) for c in cols},
        "after": {c: round(after[c], 2) for c in cols},
        "delta": delta,
        "roster_after": base_after,
    }

@app.route("/season/<season>/trade", methods=["GET", "POST"])
def trade_analyzer_page(season):
    formatted = season.replace("-", "/")
    my_roster = []
    opp_roster = []
    send_players = []
    receive_players = []

    data_type = "nopunts"
    scoring_type = "9cat"
    punts = []

    my_roster_text = ""
    opp_roster_text = ""
    send_text = ""
    receive_text = ""

    my_result = None
    opp_result = None
    verdict = None
    missing_names = []

    if session.get("user_id"):
        my_roster, data_type = load_latest_team(session["user_id"], season)
        my_roster_text = "\n".join(my_roster)

    if request.method == "POST":
        data_type = request.form.get("data_type", data_type or "nopunts")
        scoring_type = request.form.get("scoring_type", "9cat")
        punts = request.form.getlist("punts")

        my_roster_text = (request.form.get("my_roster") or "").strip()
        opp_roster_text = (request.form.get("opp_roster") or "").strip()
        send_text = (request.form.get("send_players") or "").strip()
        receive_text = (request.form.get("receive_players") or "").strip()

        my_roster = [n.strip() for n in my_roster_text.splitlines() if n.strip()]
        opp_roster = [n.strip() for n in opp_roster_text.splitlines() if n.strip()]
        send_players = [n.strip() for n in send_text.splitlines() if n.strip()]
        receive_players = [n.strip() for n in receive_text.splitlines() if n.strip()]

        if not my_roster:
            flash("Add your roster first (one name per line).", "warning")
        elif not send_players and not receive_players:
            flash("Add at least one player to send or receive.", "warning")
        else:
            df, _ = _load_df_for_recs(season, data_type)
            if df is None:
                flash("Could not read rankings dataset for trade analysis.", "danger")
            else:
                cols = [c for c in VAL_COLS if c in df.columns]
                if scoring_type == "8cat" and "toV" in cols:
                    cols = [c for c in cols if c != "toV"]

                punt_valcols = {CAT_LABEL_TO_VALCOL.get(lbl) for lbl in punts}
                eval_cols = [c for c in cols if c not in punt_valcols]

                all_names = {n.lower() for n in df["Name"].dropna().astype(str).str.strip().unique()}
                for n in set(my_roster + opp_roster + send_players + receive_players):
                    if n.lower() not in all_names:
                        missing_names.append(n)

                my_result = _analyze_trade_side(df, my_roster, send_players, receive_players, cols)
                if opp_roster:
                    opp_result = _analyze_trade_side(df, opp_roster, receive_players, send_players, cols)

                improved = sum(1 for c in eval_cols if my_result["delta"].get(c, 0.0) > 0)
                declined = sum(1 for c in eval_cols if my_result["delta"].get(c, 0.0) < 0)
                neutral = max(len(eval_cols) - improved - declined, 0)

                if improved > declined:
                    overall = "Good for your build"
                elif declined > improved:
                    overall = "Likely negative for your build"
                else:
                    overall = "Close to neutral"

                col_to_label = {v: k for k, v in CAT_LABEL_TO_VALCOL.items()}
                top_gains = sorted(
                    [(c, my_result["delta"].get(c, 0.0)) for c in eval_cols],
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
                top_losses = sorted(
                    [(c, my_result["delta"].get(c, 0.0)) for c in eval_cols],
                    key=lambda x: x[1]
                )[:3]

                verdict = {
                    "overall": overall,
                    "improved": improved,
                    "declined": declined,
                    "neutral": neutral,
                    "top_gains": [
                        {"cat": col_to_label.get(c, c), "delta": round(v, 2)}
                        for c, v in top_gains if v > 0
                    ],
                    "top_losses": [
                        {"cat": col_to_label.get(c, c), "delta": round(v, 2)}
                        for c, v in top_losses if v < 0
                    ]
                }

    return render_template(
        "trade_analyzer.html",
        season=formatted,
        season_url=season,
        my_roster_text=my_roster_text,
        opp_roster_text=opp_roster_text,
        send_text=send_text,
        receive_text=receive_text,
        data_type=data_type,
        scoring_type=scoring_type,
        punts=punts,
        my_result=my_result,
        opp_result=opp_result,
        verdict=verdict,
        missing_names=sorted(set(missing_names), key=lambda s: s.lower())
    )

@app.route("/season/<season>/waiver", methods=["GET", "POST"])
def waiver_wire_page(season):
    formatted = season.replace("-", "/")
    data_type = "nopunts"
    scoring_mode = "rest_season"
    scoring_type = "9cat"
    free_agents_text = ""
    punts = []
    roster_players = []
    recommendations = []
    weak_categories = []
    roster_totals = {}

    if session.get("user_id"):
        roster_players, data_type = load_latest_team(session["user_id"], season)

    if request.method == "POST":
        data_type = request.form.get("data_type", data_type or "nopunts")
        scoring_mode = request.form.get("scoring_mode", "rest_season")
        scoring_type = request.form.get("scoring_type", "9cat")
        punts = request.form.getlist("punts")
        free_agents_text = (request.form.get("free_agents") or "").strip()

        roster_text = (request.form.get("roster_players") or "").strip()
        if roster_text:
            roster_players = [n.strip() for n in roster_text.splitlines() if n.strip()]

        free_agents = [n.strip() for n in free_agents_text.splitlines() if n.strip()]
        if not roster_players:
            flash("Add your roster players first (one name per line).", "warning")
        elif not free_agents:
            flash("Add a free-agent pool (one name per line).", "warning")
        else:
            df, _ = _load_df_for_recs(season, data_type)
            if df is None:
                flash("Could not read rankings dataset for waiver recommendations.", "danger")
            else:
                recommendations, weak_categories, roster_totals = _build_waiver_recommendations(
                    df=df,
                    roster=roster_players,
                    free_agents=free_agents,
                    scoring_mode=scoring_mode,
                    scoring_type=scoring_type,
                    punt_labels=punts,
                    limit=15 if scoring_mode == "rest_season" else 10
                )
                if scoring_type == "8cat":
                    roster_totals.pop("TO", None)
                if not recommendations:
                    flash("No matching free agents found in the selected dataset.", "warning")

    return render_template(
        "waiver_wire.html",
        season=formatted,
        season_url=season,
        roster_players=roster_players,
        data_type=data_type,
        scoring_mode=scoring_mode,
        scoring_type=scoring_type,
        punts=punts,
        free_agents_text=free_agents_text,
        recommendations=recommendations,
        weak_categories=weak_categories,
        roster_totals=roster_totals
    )

@app.route("/season/<season>/board/recommend", methods=["POST"])
def board_recommend(season):
    payload = request.get_json(force=True, silent=True) or {}
    taken = { (n or "").strip().lower() for n in payload.get("taken", []) }
    my_team = [ (n or "").strip() for n in payload.get("my_team", []) if n ]
    data_type = payload.get("data_type", "nopunts")
    scoring = (payload.get("scoringType") or "9cat").lower()
    punts_labels = payload.get("punts", []) or []

    df, used_type = _load_df_for_recs(season, data_type)
    if df is None:
        return jsonify({"recommendations": [], "error": "Dataset not available for this season."})

    exclude = {n.lower() for n in my_team} | taken
    cand = df[~df["Name"].str.lower().isin(exclude)].copy()
    cols = [c for c in VAL_COLS if c in cand.columns]
    if not cols: return jsonify({"recommendations": [], "error": "Value columns not found in dataset."})
    cand[cols] = cand[cols].fillna(0.0)

    effective_cols = [c for c in cols if not (scoring == "8cat" and c == "toV")]
    punt_valcols = {CAT_LABEL_TO_VALCOL.get(lbl) for lbl in punts_labels}
    weights = {c: (0.0 if c in (punt_valcols or set()) else 1.0) for c in effective_cols}

    totals = _current_totals(df, my_team) if my_team else {c:0.0 for c in VAL_COLS}
    ordered_needs = sorted([c for c in effective_cols], key=lambda c: totals.get(c, 0.0))
    for c in set(ordered_needs[:3]):
        if weights.get(c,0) > 0: weights[c] += 0.35

    scores = []
    for _, row in cand.iterrows():
        contrib = {c: float(row[c]) * weights.get(c, 0.0) for c in effective_cols}
        score = sum(contrib.values())
        top_items = sorted(((c, float(row[c])) for c in effective_cols if weights.get(c,0)>0),
                           key=lambda x: x[1], reverse=True)[:3]
        top_readable = []
        for c, v in top_items:
            label = next((lbl for lbl, vc in CAT_LABEL_TO_VALCOL.items() if vc == c), c)
            top_readable.append({"stat": label, "v": round(v, 2)})
        scores.append({"Name": row["Name"], "score": round(score, 3), "top": top_readable})

    scores.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"recommendations": scores[:25], "used_type": used_type})

# -----------------------------------------------------------------------------
# Board page
# -----------------------------------------------------------------------------
@app.route("/season/<season>/board", endpoint="board_page")
def board_page(season):
    try:
        team_players = []; team_data_type = "nopunts"
        if session.get("user_id"):
            team_players, team_data_type = load_latest_team(session["user_id"], season)
        return render_template("board.html", season=season, team_players=team_players, team_data_type=team_data_type)
    except Exception:
        traceback.print_exc()
        flash("Internal server error while preparing the board page.", "danger")
        return render_template("board.html", season=season, team_players=[], team_data_type="nopunts")

if __name__ == "__main__":
    app.run(debug=True)
