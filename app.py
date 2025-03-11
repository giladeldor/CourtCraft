from flask import Flask, render_template_string

app = Flask(__name__)

# Generate NBA seasons from 24/25 to 10/11
nba_seasons = [f"{y % 100:02d}/{(y + 1) % 100:02d}" for y in range(2024, 2010, -1)]

# Home Page with Carousel
home_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NBA Seasons Carousel</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { text-align: center; margin-top: 50px; }
        .carousel-item { font-size: 30px; font-weight: bold; height: 200px; }
        .carousel-inner { background: #f8f9fa; border-radius: 10px; }
        .season-button {
            display: inline-block;
            padding: 10px 20px;
            font-size: 20px;
            background-color: #007bff;
            color: white;
            border: none;
            cursor: pointer;
            text-decoration: none;
            border-radius: 5px;
            transition: 0.3s;
        }
        .season-button:hover {
            background-color: #0056b3;
        }
    </style>
</head>
<body>
    <h1>NBA Seasons</h1>
    <div id="seasonCarousel" class="carousel slide" data-bs-ride="false">
        <div class="carousel-inner">
            {% for season in seasons %}
                <div class="carousel-item {% if loop.first %}active{% endif %}">
                    <div class="d-flex justify-content-center align-items-center h-100">
                        <a href="/season/{{ season|replace('/', '-') }}" class="season-button">{{ season }}</a>
                    </div>
                </div>
            {% endfor %}
        </div>
        <button class="carousel-control-prev" type="button" data-bs-target="#seasonCarousel" data-bs-slide="prev">
            <span class="carousel-control-prev-icon" aria-hidden="true"></span>
        </button>
        <button class="carousel-control-next" type="button" data-bs-target="#seasonCarousel" data-bs-slide="next">
            <span class="carousel-control-next-icon" aria-hidden="true"></span>
        </button>
    </div>

    <!-- Bootstrap JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <!-- 100% Working Keyboard Controls for Carousel -->
    <script>
        document.addEventListener("DOMContentLoaded", function () {
            let carouselElement = document.querySelector("#seasonCarousel");
            let carousel = new bootstrap.Carousel(carouselElement, { interval: false });

            document.addEventListener("keydown", function (event) {
                if (event.key === "ArrowLeft") {
                    event.preventDefault();
                    carousel.prev(); // Move the carousel left
                } else if (event.key === "ArrowRight") {
                    event.preventDefault();
                    carousel.next(); // Move the carousel right
                }
            });
        });
    </script>
</body>
</html>
"""

# Season Page Template
season_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ season }} Season</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { text-align: center; margin-top: 50px; }
        .container { max-width: 600px; margin: auto; padding: 20px; background: #f8f9fa; border-radius: 10px; }
        .nav-button {
            display: inline-block;
            padding: 10px 20px;
            font-size: 20px;
            background-color: #28a745;
            color: white;
            border: none;
            cursor: pointer;
            text-decoration: none;
            border-radius: 5px;
            transition: 0.3s;
        }
        .nav-button:hover {
            background-color: #1e7e34;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{ season }} Season</h1>
        <p>Welcome to the {{ season }} NBA Season page.</p>
        <a href="/" class="nav-button">Back to Home</a>
    </div>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(home_template, seasons=nba_seasons)

@app.route("/season/<season>")
def season_page(season):
    formatted_season = season.replace("-", "/")  # Convert URL-friendly format back
    return render_template_string(season_template, season=formatted_season)

if __name__ == "__main__":
    app.run(debug=True)
