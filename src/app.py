import os
import itertools
import sqlite3
import json
import re
import urllib.parse
import urllib.request
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
from sync_bbm_rankings import sync_nopunt_xlsx

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
            ir_players TEXT NOT NULL DEFAULT '[]',
            data_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS league_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            season TEXT NOT NULL,
            team_name TEXT NOT NULL,
            players TEXT NOT NULL,
            ir_players TEXT NOT NULL,
            data_type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # Lightweight migration for existing DBs created before IR persistence.
    cols = [r[1] for r in db.execute("PRAGMA table_info(teams)").fetchall()]
    if "ir_players" not in cols:
        db.execute("ALTER TABLE teams ADD COLUMN ir_players TEXT NOT NULL DEFAULT '[]'")

    league_cols = [r[1] for r in db.execute("PRAGMA table_info(league_teams)").fetchall()]
    if "user_id" not in league_cols:
        db.execute("ALTER TABLE league_teams ADD COLUMN user_id INTEGER")

    db.commit()
    db.close()

init_db()

# -----------------------------------------------------------------------------
# Template globals
# -----------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year,
        'logged_in_user': session.get("user"),
        'player_headshot_url': player_headshot_url,
    }

# -----------------------------------------------------------------------------
# Data files
# -----------------------------------------------------------------------------
data_dirs = {"nopunts": "Nopunts", "tovpunt": "Tovpunts"}
data_files = {
    "25-26": {"nopunts": "BBM_PlayerRankings2526_nopunt_runtime.xlsx"},
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

PLAYER_HEADSHOT_CACHE = {}
RANKINGS_DF_CACHE = {}

def _strip_player_name(name: str) -> str:
    cleaned = re.sub(r"<[^>]*>", "", str(name or ""))
    cleaned = re.sub(r"\(\d+g\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("+", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def player_headshot_url(name: str) -> str:
    """Best-effort player headshot URL without needing local image files."""
    clean_name = _strip_player_name(name)
    if not clean_name:
        return ""

    key = clean_name.lower()
    if key in PLAYER_HEADSHOT_CACHE:
        return PLAYER_HEADSHOT_CACHE[key]

    fallback = (
        "https://ui-avatars.com/api/?name="
        + urllib.parse.quote(clean_name)
        + "&background=f5b448&color=1f2a44&rounded=true&size=64"
    )

    try:
        api = "https://www.balldontlie.io/api/v1/players?search=" + urllib.parse.quote(clean_name)
        with urllib.request.urlopen(api, timeout=2.5) as resp:
            payload = json.loads(resp.read().decode("utf-8", "ignore"))
        players = payload.get("data") or []
        if players:
            exact = next(
                (p for p in players if (p.get("first_name", "") + " " + p.get("last_name", "")).strip().lower() == key),
                players[0]
            )
            pid = exact.get("id")
            if pid:
                url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{pid}.png"
                PLAYER_HEADSHOT_CACHE[key] = url
                return url
    except Exception:
        pass

    PLAYER_HEADSHOT_CACHE[key] = fallback
    return fallback

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
    try_paths = [path]

    # Fallback to sibling extension when one file is missing/locked/unsupported.
    stem = os.path.splitext(path)[0]
    if ext == ".xls":
        xlsx_sibling = stem + ".xlsx"
        if os.path.exists(xlsx_sibling):
            try_paths.append(xlsx_sibling)
    elif ext == ".xlsx":
        xls_sibling = stem + ".xls"
        if os.path.exists(xls_sibling):
            try_paths.append(xls_sibling)

    for candidate in try_paths:
        _, c_ext = os.path.splitext(candidate.lower())
        try:
            if c_ext == ".xlsx":
                return pd.read_excel(candidate, engine="openpyxl")
            if c_ext == ".xls":
                return pd.read_excel(candidate, engine="xlrd")
            return pd.read_excel(candidate)
        except Exception:
            continue
    return None

def _read_rankings_cached(path: str):
    """Read and normalize rankings with a process-level mtime cache."""
    if not path or not os.path.exists(path):
        return None
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        mtime = None

    cached = RANKINGS_DF_CACHE.get(path)
    if cached and cached.get("mtime") == mtime:
        return cached["df"].copy()

    df = _read_excel_safe(path)
    if df is None or "Name" not in df.columns:
        return None
    df = _normalize_rankings_df(df)
    RANKINGS_DF_CACHE[path] = {"mtime": mtime, "df": df}
    return df.copy()

def _normalize_rankings_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize rankings columns so numeric comparisons/sums are always safe."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    if "Name" in out.columns:
        out["Name"] = out["Name"].astype(str).str.strip()
        # Basketball Monster export repeats header rows in the table body; drop placeholder names.
        out = out[~out["Name"].str.lower().isin({"name", "", "nan"})].copy()

    # Unify alternate value headers that may appear in exported files.
    rename_map = {}
    for c in out.columns:
        lc = c.lower()
        if lc in ("leagv", "leaguev"):
            rename_map[c] = "LeagV"
        if lc in ("puntv", "puntiv"):
            rename_map[c] = "puntV"
    if rename_map:
        out.rename(columns=rename_map, inplace=True)

    numeric_cols = [
        "Round", "Rank", "Value", "g", "m/g", "p/g", "3/g", "r/g", "a/g", "s/g", "b/g",
        "fg%", "fga/g", "ft%", "fta/g", "to/g", "USG",
        "pV", "3V", "rV", "aV", "sV", "bV", "fg%V", "ft%V", "toV",
        "LeagV", "puntV"
    ]
    for c in numeric_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")

    # Remove any residual non-player rows (e.g., repeated headers with no numeric values).
    if "Rank" in out.columns:
        out = out[out["Rank"].notna()].copy()

    return out

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

@app.route("/season/<season>/sync-bbm", methods=["POST"])
def sync_bbm_for_season(season):
    try:
        output_dir = os.path.join(os.path.dirname(__file__), data_dirs["nopunts"])
        out_path = sync_nopunt_xlsx(output_dir=output_dir, season_key=season)

        # Ensure the app points to the runtime copy (safe when the main file is open in Excel).
        out_name = os.path.basename(out_path)
        if season not in data_files:
            data_files[season] = {"nopunts": out_name}
        else:
            data_files[season]["nopunts"] = out_name

        flash(f"Synced latest BBM rankings: {out_name}", "success")
    except Exception as e:
        flash(f"BBM sync failed: {e}", "danger")
    return redirect(url_for("season_page", season=season))

@app.route("/season/<season>/data")
def season_data_page(season):
    flash("Stats Leaders was removed.", "info")
    return redirect(url_for("season_page", season=season))

# -----------------------------------------------------------------------------
# Assemble Team
# -----------------------------------------------------------------------------
@app.route("/season/<season>/team", methods=["GET","POST"])
def team_assemble_page(season):
    formatted = season.replace("-", "/")
    season_url = season
    raw_type = request.form.get("data_type", "nopunts") if request.method=="POST" else "nopunts"
    data_type = "tovpunt" if "tov" in raw_type else "nopunts"
    ir_players = []

    if request.method=="GET" and session.get("user_id"):
        db = get_db()
        row = db.execute(
            "SELECT players,ir_players,data_type FROM teams WHERE user_id=? AND season=? ORDER BY created_at DESC LIMIT 1",
            (session["user_id"], season)
        ).fetchone()
        if row:
            registered = json.loads(row["players"]); raw_type = row["data_type"]
            data_type = "tovpunt" if "tov" in raw_type else "nopunts"
            try:
                ir_players = json.loads(row["ir_players"]) or []
            except Exception:
                ir_players = []
        else:
            registered = []
    else:
        registered = []

    results = totals = analysis = None
    ir_rows = None
    punt_buttons = []

    if request.method=="POST":
        registered = [request.form.get(f"player{i}", "").strip()
                      for i in range(1,14) if request.form.get(f"player{i}", "").strip()]
        ir_players = [request.form.get("ir1", "").strip(), request.form.get("ir2", "").strip()]
        ir_players = [p for p in ir_players if p]

        if session.get("user_id"):
            db = get_db()
            db.execute(
                "INSERT INTO teams(user_id,season,players,ir_players,data_type,created_at) VALUES(?,?,?,?,?,?)",
                (
                    session["user_id"],
                    season,
                    json.dumps(registered),
                    json.dumps(ir_players),
                    raw_type,
                    datetime.now().isoformat(),
                )
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
            df, used_type = _load_df_for_recs(season, data_type)
            if used_type != data_type:
                data_type = used_type
                raw_type = used_type

        if df is None:
            flash("Could not read the rankings file. Install/upgrade xlrd (for .xls) and openpyxl (for .xlsx).", "danger")
            return render_template(
                "team_assemble.html",
                season=formatted, season_url=season,
                registered_players=registered,
                ir_players=ir_players, ir_rows=None,
                results=None, totals=None, analysis=None,
                punt_buttons=[], raw_type=raw_type, data_type=data_type
            )

        # Normalize columns and dtypes once to avoid string/int runtime issues.
        df = _normalize_rankings_df(df)

        clean = [n.lower() for n in registered]
        ir_clean = {n.lower() for n in ir_players}

        # IR players are tracked separately and excluded from active totals.
        df_ir = df[df['Name'].str.lower().isin(ir_clean)] if ir_clean else df.iloc[0:0]
        ir_rows = df_ir.to_dict(orient='records') if not df_ir.empty else []
        for r in ir_rows:
            r["plain_name"] = str(r.get("Name", "")).strip()
            r["Name"] = str(r.get("Name", "")) + Markup(" <span style='color:#946200;font-weight:bold;'>(IR)</span>")

        df_f = df[df['Name'].str.lower().isin(clean)]
        if ir_clean:
            df_f = df_f[~df_f['Name'].str.lower().isin(ir_clean)]
        results = df_f.to_dict(orient='records')

        exclude = ["Round","Rank","Value","Team","Inj","Pos","m/g","USG","fga/g", "fta/g","LeagV", "puntV", "g", "p/g","r/g","a/g","s/g","b/g","to/g","3/g","fg%","ft%"]
        for r in results:
            r["plain_name"] = str(r.get("Name", "")).strip()
            games = pd.to_numeric(r.get("g", 0), errors="coerce")
            if pd.notna(games) and games < 40:
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
        ir_players=ir_players, ir_rows=ir_rows,
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

        df = _normalize_rankings_df(df)
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
        df = _read_rankings_cached(path)
        if df is not None:
            return df, t
    return None, preferred_type or "nopunts"

def _current_totals(df, roster):
    sub = df[df["Name"].str.lower().isin([n.lower() for n in roster])]
    totals = sub[VAL_COLS].sum(numeric_only=True)
    return {c: float(totals.get(c, 0.0)) for c in VAL_COLS}

def _team_quality_label(count_positive: int) -> str:
    return "bad team" if count_positive < 2 else (
        "ok team" if count_positive < 3 else (
            "good team" if count_positive < 4 else "great team"
        )
    )

def _load_df_for_exact_type(season: str, data_type: str):
    try:
        path = os.path.join(os.path.dirname(__file__), data_dirs[data_type], data_files[season][data_type])
    except KeyError:
        return None
    return _read_rankings_cached(path)

def _compute_league_power_rankings(season: str, rows):
    df_cache = {}

    def _get_df_cached(dtype: str):
        if dtype in df_cache:
            return df_cache[dtype], dtype

        df = _load_df_for_exact_type(season, dtype)
        used_type = dtype
        if df is None:
            df, used_type = _load_df_for_recs(season, dtype)

        df_cache[dtype] = df
        if used_type != dtype:
            df_cache[used_type] = df
        return df, used_type

    teams = []
    for r in rows:
        is_my_team = False
        try:
            is_my_team = bool(r["is_my_team"])
        except Exception:
            is_my_team = False

        try:
            players = json.loads(r["players"]) or []
        except Exception:
            players = []
        try:
            ir_players = json.loads(r["ir_players"]) or []
        except Exception:
            ir_players = []

        data_type = r["data_type"] if r["data_type"] in ("nopunts", "tovpunt") else "nopunts"
        df, data_type = _get_df_cached(data_type)

        vals = {c: 0.0 for c in VAL_COLS}
        if df is not None:
            active = [n for n in players if n and n.strip() and n.lower() not in {x.lower() for x in ir_players}]
            sub = df[df["Name"].str.lower().isin([n.lower() for n in active])]
            sums = sub[VAL_COLS].sum(numeric_only=True)
            vals = {c: float(sums.get(c, 0.0)) for c in VAL_COLS}

        positive = sum(1 for c in VAL_COLS if vals.get(c, 0.0) > 0)
        power_score = round(sum(vals.get(c, 0.0) for c in VAL_COLS), 3)
        teams.append({
            "id": r["id"],
            "team_name": r["team_name"],
            "is_my_team": is_my_team,
            "players": players,
            "ir_players": ir_players,
            "data_type": data_type,
            "analysis": _team_quality_label(positive),
            "positive_cats": positive,
            "power_score": power_score,
            "totals": {k: round(v, 2) for k, v in vals.items()},
            "created_at": r["created_at"],
        })

    teams.sort(key=lambda t: (t["power_score"], t["positive_cats"]), reverse=True)
    for idx, t in enumerate(teams, start=1):
        t["power_rank"] = idx
    return teams

def _load_league_taken_players(season: str, user_id=None):
    if not user_id:
        return []
    db = get_db()
    rows = db.execute(
        "SELECT players, ir_players FROM league_teams WHERE season=? AND (user_id=? OR user_id IS NULL)",
        (season, user_id),
    ).fetchall()
    names = []
    seen = set()
    for r in rows:
        for col in ("players", "ir_players"):
            try:
                arr = json.loads(r[col]) or []
            except Exception:
                arr = []
            for n in arr:
                name = str(n).strip()
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    names.append(name)
    return names

@app.route("/season/<season>/league-teams", methods=["GET", "POST"])
def league_teams_page(season):
    formatted = season.replace("-", "/")
    user_id = session.get("user_id")
    form_data_type = request.form.get("data_type", "nopunts") if request.method == "POST" else "nopunts"
    form_team_name = (request.form.get("team_name") or "").strip() if request.method == "POST" else ""
    form_players = [request.form.get(f"player{i}", "").strip() for i in range(1, 14)] if request.method == "POST" else [""] * 13
    form_ir_players = [request.form.get("ir1", "").strip(), request.form.get("ir2", "").strip()] if request.method == "POST" else ["", ""]
    edit_team_id = (request.form.get("edit_team_id") or "").strip() if request.method == "POST" else (request.args.get("edit") or "").strip()

    if request.method == "POST":
        if not user_id:
            flash("Please log in to manage League Teams.", "warning")
            return redirect(url_for("auth"))

        action = request.form.get("action", "save")
        db = get_db()

        if action == "delete":
            team_id = request.form.get("team_id", "").strip()
            if team_id.isdigit():
                db.execute(
                    "DELETE FROM league_teams WHERE id=? AND season=? AND (user_id=? OR user_id IS NULL)",
                    (int(team_id), season, user_id),
                )
                db.commit()
                flash("League team removed.", "success")
            else:
                flash("Invalid team id.", "warning")
            return redirect(url_for("league_teams_page", season=season))

        team_name = form_team_name
        players = [p for p in form_players if p]
        ir_players = [p for p in form_ir_players if p]

        if not team_name:
            flash("Please provide a team name.", "warning")
        elif not players:
            flash("Please add at least one active player.", "warning")
        else:
            normalized_type = "tovpunt" if "tov" in form_data_type else "nopunts"
            if edit_team_id.isdigit():
                db.execute(
                    "UPDATE league_teams SET user_id=?, team_name=?, players=?, ir_players=?, data_type=?, created_at=? WHERE id=? AND season=? AND (user_id=? OR user_id IS NULL)",
                    (
                        user_id,
                        team_name,
                        json.dumps(players),
                        json.dumps(ir_players),
                        normalized_type,
                        datetime.now().isoformat(),
                        int(edit_team_id),
                        season,
                        user_id,
                    ),
                )
                flash(f"Updated league team: {team_name}", "success")
            else:
                db.execute(
                    "DELETE FROM league_teams WHERE season=? AND (user_id=? OR user_id IS NULL) AND lower(team_name)=lower(?)",
                    (season, user_id, team_name),
                )
                db.execute(
                    "INSERT INTO league_teams(user_id, season, team_name, players, ir_players, data_type, created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        user_id,
                        season,
                        team_name,
                        json.dumps(players),
                        json.dumps(ir_players),
                        normalized_type,
                        datetime.now().isoformat(),
                    ),
                )
                flash(f"Saved league team: {team_name}", "success")
            db.commit()
            return redirect(url_for("league_teams_page", season=season))

    if request.method == "GET" and edit_team_id.isdigit():
        if not user_id:
            edit_team_id = ""
        else:
            db = get_db()
            row = db.execute(
                "SELECT id, team_name, players, ir_players, data_type FROM league_teams WHERE id=? AND season=? AND (user_id=? OR user_id IS NULL)",
                (int(edit_team_id), season, user_id),
            ).fetchone()
            if row:
                form_team_name = row["team_name"]
                form_data_type = row["data_type"] if row["data_type"] in ("nopunts", "tovpunt") else "nopunts"
                try:
                    p = json.loads(row["players"]) or []
                except Exception:
                    p = []
                try:
                    ir = json.loads(row["ir_players"]) or []
                except Exception:
                    ir = []
                form_players = [p[i] if i < len(p) else "" for i in range(13)]
                form_ir_players = [ir[0] if len(ir) > 0 else "", ir[1] if len(ir) > 1 else ""]
            else:
                edit_team_id = ""

    rows = []
    if user_id:
        db = get_db()
        rows = list(db.execute(
            "SELECT id, team_name, players, ir_players, data_type, created_at FROM league_teams WHERE season=? AND (user_id=? OR user_id IS NULL) ORDER BY created_at DESC",
            (season, user_id),
        ).fetchall())

    # Also include the logged-in user's latest Assemble Team roster in rankings.
    if user_id:
        my_row = db.execute(
            "SELECT players, ir_players, data_type, created_at FROM teams WHERE user_id=? AND season=? ORDER BY datetime(created_at) DESC LIMIT 1",
            (user_id, season),
        ).fetchone()
        if my_row:
            rows.append({
                "id": None,
                "team_name": f"{session.get('user', 'My Team')} (My Team)",
                "players": my_row["players"],
                "ir_players": my_row["ir_players"],
                "data_type": my_row["data_type"],
                "created_at": my_row["created_at"],
                "is_my_team": True,
            })

    power_rankings = _compute_league_power_rankings(season, rows)

    return render_template(
        "league_teams.html",
        season=formatted,
        season_url=season,
        can_manage=bool(user_id),
        data_type=form_data_type,
        form_team_name=form_team_name,
        form_players=form_players,
        form_ir_players=form_ir_players,
        edit_team_id=edit_team_id,
        power_rankings=power_rankings,
    )

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
    cand = cand[~cand["Name"].str.lower().isin({"name", "", "nan"})].copy()

    # Do not recommend players marked with X in INJ (out for season).
    if "Inj" in cand.columns:
        inj_series = cand["Inj"].fillna("").astype(str).str.strip().str.upper()
        cand = cand[~inj_series.str.startswith("X")]

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
        display_name = row["Name"]

        # For injured/suspended players, show games in parentheses when available (e.g., INJ 8g / SUSP 4g).
        if "Inj" in cand.columns:
            inj_raw = str(row.get("Inj", "") or "").strip()
            m = re.search(r"(?:INJ|SUSP)\s*(\d+)\s*g", inj_raw, flags=re.IGNORECASE)
            if m:
                display_name = f"{display_name} ({m.group(1)}g)"

        top_items = sorted(((c, float(row[c])) for c in effective_cols if weights.get(c,0)>0),
                           key=lambda x: x[1], reverse=True)[:3]
        top_readable = []
        for c, v in top_items:
            label = next((lbl for lbl, vc in CAT_LABEL_TO_VALCOL.items() if vc == c), c)
            top_readable.append({"stat": label, "v": round(v, 2)})
        scores.append({"Name": display_name, "score": round(score, 3), "top": top_readable})

    scores.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"recommendations": scores[:25], "used_type": used_type})

# -----------------------------------------------------------------------------
# Board page
# -----------------------------------------------------------------------------
@app.route("/season/<season>/board", endpoint="board_page")
def board_page(season):
    try:
        team_players = []; team_data_type = "nopunts"
        user_id = session.get("user_id")
        if user_id:
            team_players, team_data_type = load_latest_team(user_id, season)
        league_taken_players = _load_league_taken_players(season, user_id=user_id)
        return render_template(
            "board.html",
            season=season,
            team_players=team_players,
            team_data_type=team_data_type,
            league_taken_players=league_taken_players,
        )
    except Exception:
        traceback.print_exc()
        flash("Internal server error while preparing the board page.", "danger")
        return render_template("board.html", season=season, team_players=[], team_data_type="nopunts", league_taken_players=[])

if __name__ == "__main__":
    app.run(debug=True)
