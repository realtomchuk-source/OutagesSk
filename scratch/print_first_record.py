import json

with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
    data = json.load(f)

if data:
    first = data[0]
    print("First record keys & values:")
    for k, v in first.items():
        if isinstance(v, list):
            print(f"  {k}: list of length {len(v)} (first few: {v[:2]})")
        else:
            print(f"  {k}: {v!r}")
else:
    print("No data in snapshot")
