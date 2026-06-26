import json

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    official_data = json.load(f)

print(f"Total keys: {len(official_data)}")
for k in official_data.keys():
    print(f"  Key: {k!r}, length: {len(k)}")
