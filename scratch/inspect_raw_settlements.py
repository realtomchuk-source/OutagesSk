import json

with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Group by settlement
outages_today = [r for r in data if r.get("start_datetime", "").startswith("21.06.2026")]

outages_info = []
for r in outages_today:
    outages_info.append({
        "settlement": r.get("settlement"),
        "type": r.get("type"),
        "start": r.get("start_datetime"),
        "end": r.get("end_datetime"),
        "streets_count": len(r.get("streets", []))
    })

with open("scratch/raw_settlements.txt", "w", encoding="utf-8") as f:
    json.dump(outages_info, f, ensure_ascii=False, indent=2)

print("Done! View scratch/raw_settlements.txt")
