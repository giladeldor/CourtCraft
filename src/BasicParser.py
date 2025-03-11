import pandas as pd
import os

def main(file_path):
    
    
    # Read the excel file
    df = pd.read_excel(file_path)

    print("Top 10 Leaders in each category:")
    print("Points:")
    print(df[['Name', 'Team', 'p/g']].sort_values(by='p/g', ascending=False).head(10))
    print("Rebounds:")
    print(df[['Name', 'Team', 'r/g']].sort_values(by='r/g', ascending=False).head(10))
    print("Assists:")
    print(df[['Name', 'Team', 'a/g']].sort_values(by='a/g', ascending=False).head(10))
    print("Steals:")
    print(df[['Name', 'Team', 's/g']].sort_values(by='s/g', ascending=False).head(10))
    print("Blocks:")
    print(df[['Name', 'Team', 'b/g']].sort_values(by='b/g', ascending=False).head(10))
    print("Turnovers:")
    print(df[['Name', 'Team', 'to/g']].sort_values(by='to/g', ascending=True).head(10))
    print("FG%:")
    print(df[['Name', 'Team', 'fg%']].sort_values(by='fg%', ascending=False).head(10))
    print("FT%:")
    print(df[['Name', 'Team', 'ft%']].sort_values(by='ft%', ascending=False).head(10))
    print("3P%:")
    print(df[['Name', 'Team', '3/g']].sort_values(by='3/g', ascending=False).head(10))


if __name__ == "__main__":
    file_path = os.path.join(os.path.dirname(__file__), "BBM_PlayerRankings2425_nopunt.xls")
    main(file_path=file_path)
