import json

with open("data/archive.json", "r", encoding="utf-8") as f:
    archive = json.load(f)

with open("data/archive_ozerna_result.txt", "w", encoding="utf-8") as out_f:
    for rec in archive:
        sett = rec.get("settlement", "")
        streets = rec.get("streets", [])
        streets_detailed = rec.get("streets_detailed", [])
        all_streets = list(set(streets + [sd["name"] for sd in streets_detailed if sd.get("name")]))
        for s in all_streets:
            if "Озерн" in s or "озерн" in s.lower():
                out_f.write(f"Settlement: {sett} | Date: {rec.get('created_date')} {rec.get('start_datetime')} | Street: {s} | Houses: {[sd.get('houses') for sd in streets_detailed if sd.get('name') == s]}\n")

print("Done writing archive_ozerna_result.txt")
