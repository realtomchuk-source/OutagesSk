import json

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    data = json.load(f)

ostrozkogo = data.get("м. Старокостянтинів", {}).get("вул. Острозького", {})
print("вул. Острозького houses:")
print(ostrozkogo.get("houses", []))
