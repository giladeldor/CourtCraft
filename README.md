# CourtCraft 📸

> Craft your perfect fantasy lineup—powered by real NBA stats.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)  
[![Python version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)  
[![Flask](https://img.shields.io/badge/flask-2.0%2B-orange.svg)](https://flask.palletsprojects.com/)

---

## 🏀 What Is CourtCraft?

CourtCraft is a web application (built with **Flask** and **Pandas**) that lets you:

1. **Browse NBA season leaders** in nine statistical categories (points, rebounds, assists, steals, blocks, turnovers, FG%, FT%, 3-point makes).  
2. **Assemble a custom fantasy team** of up to 13 players and receive a color‐coded analysis that highlights your strengths and weaknesses.  
3. **Compare two fantasy teams** side‐by‐side and see which team “wins” each category.

All underlying data comes from Basketball Monster XLS files (converted to Pandas), so you always get accurate, up-to-date NBA stats.

---

## ✨ Features

- **Full-bleed basketball‐floor background** on every page for immersive NBA vibes  
- **Autocomplete** for player names, pulling directly from the season’s Excel roster  
- **Color‐coded “Value” columns** that show at a glance whether a stat is good (green) or below average (red)  
- **“Punts” detection** (automatically suggests if you are punting certain categories)  
- **Persistent user login** (username/password + SQLite) to save your favorite teams per season  
- **Responsive design** using Bootstrap 5, so it looks great on desktop and mobile

---

## 📦 Installation (Local Development)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/CourtCraft.git
cd CourtCraft
