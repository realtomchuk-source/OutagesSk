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

with open("scratch/osm_raw_streets.json", "r", encoding="utf-8") as f:
    osm = json.load(f)

print("Нормалізовані назви з OSM, які містять 'мир':")
for elem in osm:
    tags = elem.get("tags", {})
    for field in ["name", "old_name"]:
        name = tags.get(field)
        if name and "мир" in name.lower():
            norm = normalize_street_name(name)
            print(f"  Поле: {field} -> Оригінал: '{name}' -> Нормалізовано: '{norm}'")
