import json

with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
    data = json.load(f)

found = []
for r in data:
    if r.get("settlement") == "Волиця-Керекешина":
        found.append({
            "type": r.get("type"),
            "start": r.get("start_datetime"),
            "end": r.get("end_datetime"),
            "streets": r.get("streets")
        })

print(f"Found {len(found)} records for Волиця-Керекешина:")
for i, f in enumerate(found):
    print(f"Record {i+1}:")
    print(f"  Type: {f['type']}")
    print(f"  Start: {f['start']}")
    print(f"  End: {f['end']}")
    print(f"  Streets count: {len(f['streets'])}")
