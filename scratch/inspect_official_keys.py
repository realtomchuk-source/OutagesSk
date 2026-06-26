import json

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Total settlements in official_streets.json: {len(data)}")
print("First 30 keys:")
for k in sorted(list(data.keys()))[:30]:
    print(f"  {k!r}")
