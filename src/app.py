from flask import Flask, render_template

app = Flask(__name__)

# Generate NBA seasons from 24/25 to 10/11
nba_seasons = [f"{y % 100:02d}/{(y + 1) % 100:02d}" for y in range(2024, 2010, -1)]

# Dictionary storing different content for each season
season_data = {
    "24-25": {
        "title": "2024/25 NBA Season",
        "headline": "The Future of the NBA",
        "description": "This season introduces new rookies and major trades.",
        "top_teams": ["Boston Celtics", "Denver Nuggets", "Milwaukee Bucks"],
        "image": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8f/Boston_Celtics.svg/285px-Boston_Celtics.svg.png"
    },
    # Add more seasons with custom data as needed...
}

@app.route("/")
def home():
    return render_template("home.html", seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    formatted_season = season.replace("-", "/")  # Convert URL-friendly format back if needed
    # Use season_data if available; otherwise, show a default page
    if season in season_data:
        return render_template("season.html", **season_data[season])
    else:
        return render_template("season.html", title=f"{formatted_season} NBA Season", 
                               headline="No Data Available",
                               description="Details for this season are not available yet.",
                               top_teams=[], image=None)

if __name__ == "__main__":
    app.run(debug=True)
