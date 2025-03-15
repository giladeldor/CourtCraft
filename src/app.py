import os
import math
import pandas as pd
from flask import Flask, render_template, request, jsonify, session
from markupsafe import Markup

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Replace with a secure secret key

# Mapping from season URL (e.g., "24-25") to the corresponding Excel file.
data_files = {
    "24-25": "BBM_PlayerRankings2425_nopunt.xls",
    "23-24": "BBM_PlayerRankings2324_nopunt.xls",
    "22-23": "BBM_PlayerRankings2223_nopunt.xls",
    "21-22": "BBM_PlayerRankings2122_nopunt.xls",
    "20-21": "BBM_PlayerRankings2021_nopunt.xls"
    # Future seasons: add more mappings here if desired.
}

def get_color(value, min_val, max_val):
    """
    Returns an HSL color from red (worst) to green (best).
    If there's no variation or the value is NaN, returns a neutral color.
    """
    if pd.isna(value):
        return "white"
    if math.isclose(min_val, max_val):
        # No variation => neutral yellowish color
        return "hsl(60, 100%, 85%)"
    ratio = (value - min_val) / (max_val - min_val)  # 0..1
    hue = 120 * ratio  # 0=red, 120=green
    return f"hsl({hue}, 100%, 85%)"

def process_season_data(season):
    """
    Returns a dictionary of top-10 stats for a given season (like "Points", "Rebounds", etc.).
    Used by /season/<season>/data for the data_calculation.html page.
    """
    if season in data_files:
        file_path = os.path.join(os.path.dirname(__file__), data_files[season])
        df = pd.read_excel(file_path)

        results = {}
        # Basic stats
        results["Points"]          = df[['Name', 'Team', 'p/g']].sort_values(by='p/g', ascending=False).head(10).to_dict(orient='records')
        results["Rebounds"]        = df[['Name', 'Team', 'r/g']].sort_values(by='r/g', ascending=False).head(10).to_dict(orient='records')
        results["Assists"]         = df[['Name', 'Team', 'a/g']].sort_values(by='a/g', ascending=False).head(10).to_dict(orient='records')
        results["Steals"]          = df[['Name', 'Team', 's/g']].sort_values(by='s/g', ascending=False).head(10).to_dict(orient='records')
        results["Blocks"]          = df[['Name', 'Team', 'b/g']].sort_values(by='b/g', ascending=False).head(10).to_dict(orient='records')
        results["Turnovers"]       = df[['Name', 'Team', 'to/g']].sort_values(by='to/g', ascending=True).head(10).to_dict(orient='records')
        results["FG%"]             = df[['Name', 'Team', 'fg%']].sort_values(by='fg%', ascending=False).head(10).to_dict(orient='records')
        results["FT%"]             = df[['Name', 'Team', 'ft%']].sort_values(by='ft%', ascending=False).head(10).to_dict(orient='records')
        results["3PG"]             = df[['Name', 'Team', '3/g']].sort_values(by='3/g', ascending=False).head(10).to_dict(orient='records')

        # Value columns
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
    else:
        return None

# List of NBA seasons for the carousel (home page).
nba_seasons = [f"{y % 100:02d}/{(y + 1) % 100:02d}" for y in range(2024, 2010, -1)]

# Season display data for season pages.
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

app = Flask(__name__)
app.secret_key = "your-secret-key"

@app.route("/")
def home():
    """
    Home page with a carousel of all seasons (2024/25 down to 2011/12).
    """
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    """
    Displays a page for the chosen season with “View Basic Stats” and “Team Assemble” buttons.
    """
    formatted_season = season.replace("-", "/")
    season_url = season
    if season in season_data:
        return render_template("season.html", season=formatted_season, season_url=season_url, **season_data[season])
    else:
        return render_template("season.html", season=formatted_season, season_url=season_url,
                               title=f"{formatted_season} NBA Season",
                               headline="No Data Available",
                               description="Details for this season are not available yet.",
                               top_teams=[], image=None)

@app.route("/season/<season>/data")
def season_data_page(season):
    """
    Shows top-10 stats (Points, Rebounds, etc.) for the chosen season.
    """
    formatted_season = season.replace("-", "/")
    results = process_season_data(season)
    return render_template("data_calculation.html", season=formatted_season, results=results)

@app.route("/season/<season>/team", methods=["GET", "POST"])
def team_assemble_page(season):
    """
    Team Assemble route:
    - Up to 13 players can be typed in.
    - If "g" < 40 => big red plus sign appended to Name.
    - 9 “value” columns color-coded from red to green.
    - If any single “value” < -1 => we suggest a “punt” for that stat.
    - Basic analysis: if # of “value” columns above 0 < 2 => bad team, etc.
    """
    formatted_season = season.replace("-", "/")
    season_url = season
    # Load registered players from session
    registered = session.get("registered_players", {})
    registered_players = registered.get(season, [])

    results = None
    totals = None
    analysis = None
    punts = []  # Store punt suggestions if any stat < -1

    if request.method == "POST":
        players = []
        for i in range(1, 14):
            name = request.form.get(f"player{i}", "").strip()
            if name:
                players.append(name)

        # Update session
        registered[season] = players
        session["registered_players"] = registered
        registered_players = players

        if season in data_files:
            # Read the Excel file for this season
            file_path = os.path.join(os.path.dirname(__file__), data_files[season])
            df = pd.read_excel(file_path)
            df_filtered = df[df['Name'].str.lower().isin([p.lower() for p in players])]

            # Convert rows to dict
            results = df_filtered.to_dict(orient="records")

            # Mark “g” < 40 => red plus
            for row in results:
                if "g" in row and row["g"] < 40:
                    row["Name"] = Markup(
                        row["Name"] + 
                        " <span style='color: red; font-size: 1.5em; font-weight: bold; text-shadow: 1px 1px 2px black;'>+</span>"
                    )

            # Exclude unwanted columns
            columns_to_exclude = ["Round", "Rank", "Value", "Team", "Inj", "Pos", "m/g", "USG", "fga/g", "g"]
            for row in results:
                for col in columns_to_exclude:
                    row.pop(col, None)

            # Compute totals row
            totals_series = df_filtered.select_dtypes(include="number").sum(numeric_only=True)
            totals = totals_series.to_dict()
            for col in columns_to_exclude:
                totals.pop(col, None)
            totals["Name"] = "Total"
            totals["Team"] = ""

            # Round numeric values
            for row in results:
                for k, val in row.items():
                    if isinstance(val, float):
                        row[k] = round(val, 2)
            for k, val in totals.items():
                if isinstance(val, float):
                    totals[k] = round(val, 2)

            # 9 “value” columns
            value_columns = ["pV", "rV", "aV", "sV", "bV", "toV", "fg%V", "ft%V", "3V"]

            # Color-coding
            col_min = {}
            col_max = {}
            for col in value_columns:
                if col in df_filtered.columns:
                    col_min[col] = df_filtered[col].min()
                    col_max[col] = df_filtered[col].max()
                else:
                    col_min[col] = 0
                    col_max[col] = 0

            # Assign background colors
            for row in results:
                for col in value_columns:
                    if col in row:
                        row[f"{col}_color"] = get_color(row[col], col_min[col], col_max[col])
                    else:
                        row[f"{col}_color"] = "white"
            for col in value_columns:
                if col in totals:
                    totals[f"{col}_color"] = get_color(totals[col], col_min[col], col_max[col])
                else:
                    totals[f"{col}_color"] = "white"

            # Basic analysis (count # of columns > 0)
            above_zero_count = sum(1 for col in value_columns if totals.get(col, 0) > 0)
            if above_zero_count < 2:
                analysis = "bad team"
            elif above_zero_count < 3:
                analysis = "ok team"
            elif above_zero_count < 4:
                analysis = "good team"
            else:
                analysis = "great team"

            # Punt suggestions if totals[col] < -1
            for col in value_columns:
                if totals.get(col, 0) < -1:
                    punts.append(col)

    return render_template(
        "team_assemble.html",
        season=formatted_season,
        season_url=season_url,
        registered_players=registered_players,
        results=results,
        totals=totals,
        analysis=analysis,
        punts=punts
    )

@app.route("/autocomplete/<season>")
def autocomplete(season):
    """
    Auto-complete route for the player names, called via jQuery UI.
    """
    term = request.args.get('term', '').lower()
    suggestions = []
    if season in data_files:
        file_path = os.path.join(os.path.dirname(__file__), data_files[season])
        df = pd.read_excel(file_path)
        names = df['Name'].dropna().unique()
        for name in names:
            if term in name.lower():
                suggestions.append(name)
    return jsonify(suggestions)

if __name__ == "__main__":
    app.run(debug=True)
