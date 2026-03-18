import argparse
import os
from datetime import datetime
import re
from io import StringIO
import urllib.parse
import urllib.request
import http.cookiejar

import pandas as pd

BBM_URL = "https://basketballmonster.com/playerrankings.aspx"
EXPECTED_COLS = [
    "Round", "Rank", "Value", "Name", "Team", "Pos", "Inj", "g", "m/g", "p/g",
    "3/g", "r/g", "a/g", "s/g", "b/g", "fg%", "fga/g", "ft%", "fta/g", "to/g", "USG",
    "pV", "3V", "rV", "aV", "sV", "bV", "fg%V", "ft%V", "toV"
]


def _season_key_from_year(year: int) -> str:
    return f"{year % 100:02d}-{(year + 1) % 100:02d}"


def _filename_for_season_key(season_key: str) -> str:
    a, b = season_key.split("-")
    return f"BBM_PlayerRankings{a}{b}_nopunt.xlsx"


def _runtime_filename_for_season_key(season_key: str) -> str:
    a, b = season_key.split("-")
    return f"BBM_PlayerRankings{a}{b}_nopunt_runtime.xlsx"


def _fetch_html(url: str) -> str:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    first = opener.open(url, timeout=30).read().decode("utf-8", "ignore")
    hidden = dict(re.findall(
        r"<input[^>]*type=['\"]hidden['\"][^>]*name=['\"]([^'\"]+)['\"][^>]*value=['\"]([^'\"]*)['\"]",
        first,
        flags=re.I,
    ))

    # Trigger ASP.NET postback to switch from "Only Top Players" to "All Players".
    payload = dict(hidden)
    payload["__EVENTTARGET"] = "PlayerFilterControl"
    payload["__EVENTARGUMENT"] = ""
    payload["PlayerFilterControl"] = "AllPlayers"

    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    html = opener.open(req, timeout=30).read().decode("utf-8", "ignore")
    return html


def fetch_bbm_rankings(url: str = BBM_URL) -> pd.DataFrame:
    html = _fetch_html(url)
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise RuntimeError("No tables found on Basketball Monster page.")

    df = tables[0].copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing expected columns: {missing}")

    df = df[EXPECTED_COLS].copy()
    df["Name"] = df["Name"].astype(str).str.strip()
    return df


def sync_nopunt_xlsx(output_dir: str, season_key: str, url: str = BBM_URL) -> str:
    df = fetch_bbm_rankings(url=url)
    if len(df) < 350:
        raise RuntimeError(f"Expected all-players dataset (>=350 rows), got {len(df)} rows.")
    os.makedirs(output_dir, exist_ok=True)

    # Keep a runtime copy that the app can read even when the main file is open in Excel.
    runtime_name = _runtime_filename_for_season_key(season_key)
    runtime_path = os.path.join(output_dir, runtime_name)
    df.to_excel(runtime_path, index=False, engine="openpyxl")

    # Best effort: also refresh the main export file. This can fail if the file is open in Excel.
    out_name = _filename_for_season_key(season_key)
    out_path = os.path.join(output_dir, out_name)
    try:
        df.to_excel(out_path, index=False, engine="openpyxl")
    except PermissionError:
        pass

    return runtime_path


def main() -> None:
    now = datetime.now()
    default_season = _season_key_from_year(now.year)

    parser = argparse.ArgumentParser(description="Sync BBM rankings into local Nopunts Excel file.")
    parser.add_argument("--season", default=default_season, help="Season key format YY-YY (default: current season).")
    parser.add_argument(
        "--output-dir",
        default=os.path.join(os.path.dirname(__file__), "Nopunts"),
        help="Directory to save the generated .xlsx file."
    )
    parser.add_argument("--url", default=BBM_URL, help="Basketball Monster rankings URL.")
    args = parser.parse_args()

    out_path = sync_nopunt_xlsx(output_dir=args.output_dir, season_key=args.season, url=args.url)
    print(f"Synced BBM rankings to: {out_path}")


if __name__ == "__main__":
    main()
