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

def check_overlap():
    # 1. Завантажуємо поточні офіційні вулиці
    with open("data/official_streets.json", "r", encoding="utf-8") as f:
        official_data = json.load(f)
    
    # 2. Завантажуємо вулиці з OSM
    with open("scratch/osm_raw_streets.json", "r", encoding="utf-8") as f:
        osm_elements = json.load(f)
        
    # Створюємо множину нормалізованих назв з OSM
    osm_normalized = set()
    osm_raw_names = set()
    for elem in osm_elements:
        tags = elem.get("tags", {})
        name = tags.get("name")
        if name:
            osm_raw_names.add(name)
            osm_normalized.add(normalize_street_name(name))
        # Також перевіримо old_name, якщо є
        old_name = tags.get("old_name")
        if old_name:
            osm_normalized.add(normalize_street_name(old_name))
            
    print(f"Унікальних нормалізованих вулиць в OSM: {len(osm_normalized)}")
    
    # 3. Перевіряємо наші офіційні вулиці
    matched_count = 0
    unmatched_count = 0
    unmatched_by_settlement = {}
    
    for settlement, streets_dict in official_data.items():
        unmatched_by_settlement[settlement] = []
        for street_name in streets_dict.keys():
            norm_name = normalize_street_name(street_name)
            if norm_name in osm_normalized:
                matched_count += 1
            else:
                unmatched_count += 1
                unmatched_by_settlement[settlement].append(street_name)
                
    total_official = matched_count + unmatched_count
    print(f"Всього вулиць у нашому official_streets.json: {total_official}")
    print(f"Знайдено в OSM (успішний збіг назви): {matched_count} ({matched_count/total_official*100:.1f}%)")
    print(f"Не знайдено в OSM: {unmatched_count} ({unmatched_count/total_official*100:.1f}%)")
    
    # Виведемо декілька незбігів для аналізу
    print("\nПриклади вулиць, яких немає в OSM (по перших кількох н.п.):")
    limit = 5
    printed = 0
    for sett, list_streets in unmatched_by_settlement.items():
        if list_streets:
            print(f"  {sett}: {list_streets[:5]}")
            printed += 1
            if printed >= limit:
                break

if __name__ == "__main__":
    check_overlap()
