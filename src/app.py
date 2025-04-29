import os
import math
import itertools
import pandas as pd
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
from markupsafe import Markup

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Replace with a secure secret key

# Inject current_year into all templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

# Directories for each data type.
data_dirs = {
    "nopunts": "Nopunts",
    "tovpunt": "Tovpunts"
}

# Mapping from season to a dictionary mapping data type to the XLS filename.
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

def get_color(value, min_val, max_val):
    if pd.isna(value):
        return "white"
    if math.isclose(min_val, max_val):
        return "hsl(60, 100%, 85%)"
    ratio = (value - min_val) / (max_val - min_val)
    hue = 120 * ratio  # 0 = red, 120 = green.
    return f"hsl({hue}, 100%, 85%)"

def process_season_data(season, data_type="nopunts"):
    if season in data_files and data_type in data_files[season]:
        file_path = os.path.join(
            os.path.dirname(__file__),
            data_dirs[data_type],
            data_files[season][data_type]
        )
        df = pd.read_excel(file_path)
        if data_type == "tovpunt":
            # Normalize column names: trim spaces and rename variants for extra columns.
            df.columns = [col.strip() for col in df.columns]
            new_columns = {}
            for col in df.columns:
                lower = col.lower()
                if lower in ["leagv", "leaguev"]:
                    new_columns[col] = "LeagV"
                elif lower in ["puntv", "puntiv"]:
                    new_columns[col] = "puntV"
                else:
                    new_columns[col] = col
            df.rename(columns=new_columns, inplace=True)

        # Build results dictionary
        results = {}
        results["Points"]    = df[['Name', 'Team', 'p/g']].sort_values(by='p/g', ascending=False).head(10).to_dict(orient='records')
        results["Rebounds"]  = df[['Name', 'Team', 'r/g']].sort_values(by='r/g', ascending=False).head(10).to_dict(orient='records')
        results["Assists"]   = df[['Name', 'Team', 'a/g']].sort_values(by='a/g', ascending=False).head(10).to_dict(orient='records')
        results["Steals"]    = df[['Name', 'Team', 's/g']].sort_values(by='s/g', ascending=False).head(10).to_dict(orient='records')
        results["Blocks"]    = df[['Name', 'Team', 'b/g']].sort_values(by='b/g', ascending=False).head(10).to_dict(orient='records')
        results["Turnovers"] = df[['Name', 'Team', 'to/g']].sort_values(by='to/g', ascending=True).head(10).to_dict(orient='records')
        results["FG%"]       = df[['Name', 'Team', 'fg%']].sort_values(by='fg%', ascending=False).head(10).to_dict(orient='records')
        results["FT%"]       = df[['Name', 'Team', 'ft%']].sort_values(by='ft%', ascending=False).head(10).to_dict(orient='records')
        results["3PG"]       = df[['Name', 'Team', '3/g']].sort_values(by='3/g', ascending=False).head(10).to_dict(orient='records')
        results["Poits Value"]     = df[['Name', 'Team', 'pV']].sort_values(by='pV', ascending=False).head(10).to_dict(orient='records')
        results["Rebounds Value"]  = df[['Name', 'Team', 'rV']].sort_values(by='rV', ascending=False).head(10).to_dict(orient='records')
        results["Assists Value"]   = df[['Name', 'Team', 'aV']].sort_values(by='aV', ascending=False).head(10).to_dict(orient='records')
        results["Steals Value"]    = df[['Name', 'Team', 'sV']].sort_values(by='sV', ascending=False).head(10).to_dict(orient='records')
        results["Blocks Value"]    = df[['Name', 'Team', 'bV']].sort_values(by='bV', ascending=False).head(10).to_dict(orient='records')
        results["Turnovers Value"] = df[['Name', 'Team', 'toV']].sort_values(by='toV', ascending=True).head(10).to_dict(orient='records')
        results["FG% Value"]       = df[['Name', 'Team', 'fg%V']].sort_values(by='fg%V', ascending=False).head(10).to_dict(orient='records')
        results["FT% Value"]       = df[['Name', 'Team', 'ft%V']].sort_values(by='ft%V', ascending=False).head(10).to_dict(orient='records')
        results["3PG Value"]       = df[['Name', 'Team', '3V']].sort_values(by='3V', ascending=False).head(10).to_dict(orient='records')
        return results
    return None

nba_seasons = [f"{y % 100:02d}/{(y + 1) % 100:02d}" for y in range(2024, 2010, -1)]

season_data = {
    "24-25": {"title": "2024/25 NBA Season"},
    "23-24": {"title": "2023/24 NBA Season"},
    "22-23": {"title": "2022/23 NBA Season"},
    "21-22": {"title": "2021/22 NBA Season"},
    "20-21": {"title": "2020/21 NBA Season"},
    "19-20": {"title": "2019/20 NBA Season"},
    "18-19": {"title": "2018/19 NBA Season"},
    "17-18": {"title": "2017/18 NBA Season"},
    "16-17": {"title": "2016/17 NBA Season"},
    "15-16": {"title": "2015/16 NBA Season"},
    "14-15": {"title": "2014/15 NBA Season"},
    "13-14": {"title": "2013/14 NBA Season"},
    "12-13": {"title": "2012/13 NBA Season"},
    "11-12": {"title": "2011/12 NBA Season"}
}

@app.route("/")
def home():
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    formatted_season = season.replace("-", "/")
    season_url = season
    if season in season_data:
        return render_template("season.html", season=formatted_season, season_url=season_url, **season_data[season])
    else:
        return render_template(
            "season.html",
            season=formatted_season,
            season_url=season_url,
            title=f"{formatted_season} NBA Season",
            headline="No Data Available",
            description="No data for this season.",
            top_teams=[],
            image=None
        )

@app.route("/season/<season>/data")
def season_data_page(season):
    results = process_season_data(season, data_type="nopunts")
    return render_template("data_calculation.html", season=season.replace("-", "/"), results=results)

@app.route("/season/<season>/team", methods=["GET", "POST"])
def team_assemble_page(season):
    formatted_season = season.replace("-", "/")
    season_url = season
    data_type = request.form.get("data_type", "nopunts") if request.method == "POST" else "nopunts"
    registered = session.get("registered_players", {})
    registered_players = registered.get(season, [])

    results = totals = analysis = None
    punts = punt_buttons = []

    if request.method == "POST":
        players = [
            request.form.get(f"player{i}", "").strip()
            for i in range(1, 14)
            if request.form.get(f"player{i}", "").strip()
        ]
        registered[season] = players
        session["registered_players"] = registered
        registered_players = players

        if season in data_files and data_type in data_files[season]:
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

            df_filtered = df[df['Name'].str.lower().isin([p.lower() for p in players])]
            results = df_filtered.to_dict(orient="records")

            for row in results:
                if row.get("g", 0) < 40:
                    row["Name"] = Markup(
                        row["Name"] +
                        " <span style='color:red; font-size:1.5em; font-weight:bold; text-shadow:1px 1px 2px black;'>+</span>"
                    )

            exclude = ["Round", "Rank", "Value", "Team", "Inj", "Pos", "m/g", "USG", "fga/g", "g"]
            for row in results:
                for col in exclude:
                    row.pop(col, None)

            totals_series = df_filtered.select_dtypes(include="number").sum(numeric_only=True)
            totals = totals_series.to_dict()
            for col in exclude:
                totals.pop(col, None)
            totals["Name"] = "Total"
            totals["Team"] = ""
            for row in results:
                for k, v in row.items():
                    if isinstance(v, float):
                        row[k] = round(v, 2)
            for k, v in totals.items():
                if isinstance(v, float):
                    totals[k] = round(v, 2)

            value_cols = ["pV","rV","aV","sV","bV","toV","fg%V","ft%V","3V"]
            min_max = {c: (df_filtered[c].min() if c in df_filtered else 0,
                           df_filtered[c].max() if c in df_filtered else 0)
                       for c in value_cols}
            for row in results:
                for c in value_cols:
                    mn, mx = min_max[c]
                    row[f"{c}_color"] = get_color(row.get(c,0), mn, mx)
            for c in value_cols:
                mn, mx = min_max[c]
                totals[f"{c}_color"] = get_color(totals.get(c,0), mn, mx)

            cnt = sum(1 for c in value_cols if totals.get(c,0)>0)
            if cnt<2:   analysis="bad team"
            elif cnt<3: analysis="ok team"
            elif cnt<4: analysis="good team"
            else:       analysis="great team"

            punts = [c for c in value_cols if totals.get(c,0)<-1]
            if punts:
                for r in range(1,len(punts)+1):
                    for combo in itertools.combinations(punts,r):
                        punt_buttons.append("+".join(combo))
                punt_buttons.insert(0,"no punts")
            else:
                punt_buttons=["no punts"]

            if data_type=="nopunts":
                for row in results:
                    row["LeagV"] = ""
                    row["puntV"] = ""
                totals["LeagV"] = ""
                totals["puntV"] = ""

    return render_template(
        "team_assemble.html",
        season=formatted_season,
        season_url=season_url,
        registered_players=registered_players,
        results=results,
        totals=totals,
        analysis=analysis,
        punt_buttons=punt_buttons,
        data_type=data_type
    )

@app.route("/autocomplete/<season>")
def autocomplete(season):
    term = request.args.get("term","").lower()
    suggestions=[]
    data_type="nopunts"
    if season in data_files and data_type in data_files[season]:
        fp = os.path.join(os.path.dirname(__file__),
                          data_dirs[data_type],
                          data_files[season][data_type])
        df=pd.read_excel(fp)
        for name in df['Name'].dropna().unique():
            if term in name.lower():
                suggestions.append(name)
    return jsonify(suggestions)

if __name__=="__main__":
    app.run(debug=True)
