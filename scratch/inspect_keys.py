import json

with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for i, rec in enumerate(data):
    if rec.get("settlement") == "Пісочниця":
        print(f"Record {i}: keys={list(rec.keys())}, original_settlement={rec.get('original_settlement')}")
        if i > 5:
            break
