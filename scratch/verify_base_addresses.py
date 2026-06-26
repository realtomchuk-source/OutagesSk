import json
import re

def advanced_normalize(name):
    if not name:
        return ""
    
    # 1. Приведення до нижнього регістру та очищення пробілів
    name = name.lower().strip()
    
    # 2. Нормалізація апострофів (заміна різних видів на єдиний стандартний ')
    name = re.sub(r"[’'`\u2019\u2018\u02bc]", "'", name)
    
    # 3. Виправлення латинської 'i' / 'e' на українські відповідники (поширені помилки друку)
    # латинська 'i' -> укр 'і', латинська 'e' -> укр 'е'
    name = name.replace("i", "і").replace("e", "е")
    
    # 4. Видалення префіксів та суфіксів типів вулиць
    types = [
        "вулиця", "вул", "провулок", "пров", "проспект", "просп", 
        "площа", "пл", "проїзд", "тупик", "шосе"
    ]
    # Регулярний вираз для видалення типів з крапками або без на початку/в кінці
    for t in types:
        name = re.sub(r"^\b" + t + r"\.?", "", name).strip()
        name = re.sub(r"\b" + t + r"\.?$", "", name).strip()
        
    # 5. Видалення закінчень числівників (наприклад, 1-й -> 1, 2-а -> 2, 3-тя -> 3)
    name = re.sub(r"(\d+)-(й|ша|а|е|я|го|ти|ка|ра|й|м|му)\b", r"\1", name)
    
    # 6. Очищення від крапок та зайвих символів (крім дефісів та апострофів)
    name = re.sub(r"[^\w\s\-\']", "", name)
    
    # 7. Сортування слів у назві для незалежності від порядку слів
    words = [w.strip() for w in name.split() if w.strip()]
    words.sort()
    
    return " ".join(words)

def clean_house_numbers(houses_list):
    """Очищення номерів будинків від технічного сміття обленерго."""
    if not houses_list:
        return []
    
    cleaned = set()
    for h in houses_list:
        h_str = str(h).strip().upper()
        h_lower = h_str.lower()
        if any(w in h_lower for w in ["опора", "будка", "гараж", "блок", "каб", "оп", "трансф", "ктп"]):
            continue
        
        # Видаляємо всі символи, крім цифр, літер, дефісів та дробів
        h_clean = re.sub(r"[^\d/A-ZА-ЯІЇЄ\-]", "", h_str)
        if h_clean:
            cleaned.add(h_clean)
            
    # Сортування номерів будинків (числові першими, літерні наступними)
    def house_sort_key(x):
        match = re.match(r"^(\d+)", x)
        num = int(match.group(1)) if match else 999999
        return (num, x)
        
    return sorted(list(cleaned), key=house_sort_key)

def verify_and_clean():
    # Завантаження поточної бази
    try:
        with open("data/official_streets.json", "r", encoding="utf-8") as f:
            official_data = json.load(f)
    except Exception as e:
        print(f"Помилка завантаження official_streets.json: {e}")
        return
        
    # Завантаження сирих даних з OSM
    try:
        with open("scratch/osm_raw_streets.json", "r", encoding="utf-8") as f:
            osm_elements = json.load(f)
    except Exception as e:
        print(f"Помилка завантаження osm_raw_streets.json: {e}")
        return

    # Завантаження списку офіційних сіл громади
    try:
        with open("data/villages.json", "r", encoding="utf-8") as f:
            villages = json.load(f)
        villages_set = {v.strip().lower() for v in villages}
    except Exception as e:
        print(f"Помилка завантаження villages.json: {e}")
        villages_set = set()

    # Створюємо словник нормалізованих назв з OSM
    osm_normalized = set()
    osm_original_map = {} # norm_name -> original_name from OSM
    
    for elem in osm_elements:
        tags = elem.get("tags", {})
        for field in ["name", "old_name", "name:uk"]:
            name = tags.get(field)
            if name:
                norm = advanced_normalize(name)
                osm_normalized.add(norm)
                osm_original_map[norm] = name

    print(f"Завантажено {len(osm_normalized)} унікальних нормалізованих вулиць з OpenStreetMap (об'єднана база).")

    clean_database = {}
    suspicious_streets = {}
    
    confirmed_count = 0
    suspicious_count = 0
    matched_by_subname_details = []

    for settlement, streets_dict in official_data.items():
        sett_name_only = re.sub(r"^(с\.|м\.|c\.|m\.)\s*", "", settlement).strip()
        
        if sett_name_only.lower() not in villages_set and sett_name_only != "Старокостянтинів":
            print(f"[ПОПЕРЕДЖЕННЯ] Населений пункт '{settlement}' відсутній у villages.json!")
            
        clean_database[settlement] = {}
        
        for street_name, street_info in streets_dict.items():
            raw_houses = street_info.get("houses", [])
            cleaned_houses = clean_house_numbers(raw_houses)
            
            street_type = street_info.get("type", "вулиця")
            blacklist = street_info.get("blacklist", [])
            
            norm_name = advanced_normalize(street_name)
            
            # Перевірка збігу в OSM
            is_confirmed = (norm_name in osm_normalized)
            match_reason = "Точний збіг в OSM"
            
            # Спроба знайти за прізвищем/підрядком, якщо точного збігу немає
            if not is_confirmed:
                for osm_name in osm_normalized:
                    osm_words = osm_name.split()
                    # Якщо наше нормалізоване ім'я є останнім словом (прізвищем) в OSM
                    if norm_name in osm_words:
                        is_confirmed = True
                        match_reason = f"Збіг по прізвищу з '{osm_original_map[osm_name]}' в OSM"
                        matched_by_subname_details.append(f"{settlement}: '{street_name}' -> '{osm_original_map[osm_name]}'")
                        break
                
            if is_confirmed:
                clean_database[settlement][street_name] = {
                    "type": street_type,
                    "houses": cleaned_houses,
                    "blacklist": blacklist
                }
                confirmed_count += 1
            else:
                if settlement not in suspicious_streets:
                    suspicious_streets[settlement] = {}
                suspicious_streets[settlement][street_name] = {
                    "type": street_type,
                    "houses": cleaned_houses,
                    "blacklist": blacklist,
                    "reason": "Відсутня в базі OpenStreetMap міста та громади"
                }
                suspicious_count += 1

    # Запис чистого файлу
    with open("data/clean_official_streets.json", "w", encoding="utf-8") as f:
        json.dump(clean_database, f, ensure_ascii=False, indent=2)
        
    # Запис підозрілих вулиць
    with open("data/suspicious_base_streets.json", "w", encoding="utf-8") as f:
        json.dump(suspicious_streets, f, ensure_ascii=False, indent=2)

    total_base = confirmed_count + suspicious_count
    
    print("\n=== ДЕТАЛІ ЗБІГІВ ПО ПРІЗВИЩАХ ===")
    print(f"Знайдено {len(matched_by_subname_details)} вулиць за спрощеним співпадінням прізвищ. Перші 15:")
    for detail in matched_by_subname_details[:15]:
        print(f"  {detail}")

    print("\n=== РЕЗУЛЬТАТИ ВЕРИФІКАЦІЇ ===")
    print(f"Всього перевірено вулиць у базі: {total_base}")
    print(f"Підтверджено (записано в clean_official_streets.json): {confirmed_count} ({confirmed_count/total_base*100:.1f}%)")
    print(f"Не підтверджено (записано в suspicious_base_streets.json): {suspicious_count} ({suspicious_count/total_base*100:.1f}%)")
    print("Обидва файли успішно збережено у папці data/.")

if __name__ == "__main__":
    verify_and_clean()
