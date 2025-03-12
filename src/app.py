import os
import pandas as pd
from flask import Flask, render_template

app = Flask(__name__)

# Define a mapping from season URL (e.g., "24-25") to the corresponding Excel file.
data_files = {
    "24-25": "BBM_PlayerRankings2425_nopunt.xls",
    "23-24": "BBM_PlayerRankings2324_nopunt.xls",
    "22-23": "BBM_PlayerRankings2223_nopunt.xls",
    "21-22": "BBM_PlayerRankings2122_nopunt.xls",
    "20-21": "BBM_PlayerRankings2021_nopunt.xls"
    # Future seasons: "23-24": "BBM_PlayerRankings2324_nopunt.xls", etc.
}

# Generic function to process season data.
def process_season_data(season):
    if season in data_files:
        file_path = os.path.join(os.path.dirname(__file__), data_files[season])
        df = pd.read_excel(file_path)
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
        results["Poits Value"] = df[['Name', 'Team', 'pV']].sort_values(by='pV', ascending=False).head(10).to_dict(orient='records')
        results["Rebounds Value"] = df[['Name', 'Team', 'rV']].sort_values(by='rV', ascending=False).head(10).to_dict(orient='records')
        results["Assists Value"] = df[['Name', 'Team', 'aV']].sort_values(by='aV', ascending=False).head(10).to_dict(orient='records')
        results["Steals Value"] = df[['Name', 'Team', 'sV']].sort_values(by='sV', ascending=False).head(10).to_dict(orient='records')
        results["Blocks Value"] = df[['Name', 'Team', 'bV']].sort_values(by='bV', ascending=False).head(10).to_dict(orient='records')
        results["Turnovers Value"] = df[['Name', 'Team', 'toV']].sort_values(by='toV', ascending=True).head(10).to_dict(orient='records')
        results["FG% Value"] = df[['Name', 'Team', 'fg%V']].sort_values(by='fg%V', ascending=False).head(10).to_dict(orient='records')
        results["FT% Value"] = df[['Name', 'Team', 'ft%V']].sort_values(by='ft%V', ascending=False).head(10).to_dict(orient='records')
        results["3PG Value"] = df[['Name', 'Team', '3V']].sort_values(by='3V', ascending=False).head(10).to_dict(orient='records')
        return results
    else:
        return None

# List of NBA seasons (for the carousel)
nba_seasons = [f"{y % 100:02d}/{(y + 1) % 100:02d}" for y in range(2024, 2010, -1)]

# Season display data for season pages (currently only 24/25 defined)
season_data = {
    "24-25": {
        "title": "2024/25 NBA Season",
    },
    "23-24": {
        "title": "2023/24 NBA Season",
    },
    "22-23": {
        "title": "2022/23 NBA Season",
    },
    "21-22": {
        "title": "2021/22 NBA Season",
    },
    "20-21": {
        "title": "2020/21 NBA Season",
    },
    "19-20": {
        "title": "2019/20 NBA Season",
    },
    "18-19": {
        "title": "2018/19 NBA Season",
    },
    "17-18": {
        "title": "2017/18 NBA Season",
    },
    "16-17": {
        "title": "2016/17 NBA Season",
    },
    "15-16": {
        "title": "2015/16 NBA Season",
    },
    "14-15": {
        "title": "2014/15 NBA Season",
    },
    "13-14": {
        "title": "2013/14 NBA Season",
    },
    "12-13": {
        "title": "2012/13 NBA Season",
    },
    "11-12": {
        "title": "2011/12 NBA Season",
    }
}

@app.route("/")
def home():
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    # Convert URL-friendly season (e.g., "24-25") back to display format ("24/25")
    formatted_season = season.replace("-", "/")
    if season in season_data:
        return render_template("season.html", season=formatted_season, **season_data[season])
    else:
        return render_template("season.html", season=formatted_season,
                               title=f"{formatted_season} NBA Season",
                               headline="No Data Available",
                               description="Details for this season are not available yet.",
                               top_teams=[], image=None)

@app.route("/season/<season>/data")
def season_data_page(season):
    formatted_season = season.replace("-", "/")
    results = process_season_data(season)
    return render_template("data_calculation.html", season=formatted_season, results=results)

if __name__ == "__main__":
    app.run(debug=True)
