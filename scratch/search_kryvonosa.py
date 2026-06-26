import json

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for sett, streets in data.items():
    for street in streets.keys():
        if "Кривоноса" in street:
            print(f"Settlement: {sett} -> Street: {street}")
