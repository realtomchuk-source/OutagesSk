import json
import re

def normalize_street_name(name):
    if not name:
        return ""
    name = name.lower().strip()
    prefixes = [
        "вулиця", "вул.", "вул", 
        "провулок", "пров.", "пров", 
        "проспект", "просп.", "просп", 
        "площа", "пл.", "пл", 
        "тупик"
    ]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
        elif name.endswith(prefix):
            name = name[:-len(prefix)].strip()
    name = name.replace(".", "").strip()
    name = re.sub(r"\s+", " ", name)
    return name

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    official_data = json.load(f)

with open("scratch/osm_raw_streets.json", "r", encoding="utf-8") as f:
    osm_elements = json.load(f)

osm_normalized = set()
for elem in osm_elements:
    tags = elem.get("tags", {})
    name = tags.get("name")
    if name:
        osm_normalized.add(normalize_street_name(name))
    old_name = tags.get("old_name")
    if old_name:
        osm_normalized.add(normalize_street_name(old_name))

city = official_data.get("м. Старокостянтинів", {})
unmatched = []
for street_name in city.keys():
    norm_name = normalize_street_name(street_name)
    if norm_name not in osm_normalized:
        unmatched.append(street_name)

print(f"Неспівпалі вулиці для м. Старокостянтинів (всього {len(unmatched)}):")
for u in unmatched:
    print(f"  Name: '{u}' -> Norm: '{normalize_street_name(u)}' -> Codes: {[ord(c) for c in u]}")
