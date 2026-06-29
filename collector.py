import json
import time
import re
import sys
import traceback
import os
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Фікс для Windows консолі (щоб коректно відображалися українські літери та емодзі)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ------------------------------------------------------------
# 1. Завантаження довідника населених пунктів
# ------------------------------------------------------------
with open("data/villages.json", "r", encoding="utf-8") as f:
    villages = json.load(f)

def write_update_log(entry):
    log_path = "data/update_log.json"
    logs = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except:
        pass
    logs.append(entry)
    logs = logs[-100:]
    try:
        os.makedirs("data", exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as err:
        print(f"Помилка запису логу: {err}")

def extract_settlement(city_text, villages_list):
    text = city_text.strip()
    hromada_match = re.search(r'\((.*?)\)', text)
    if not hromada_match:
        # Питання 3: якщо немає чіткого маркування нашої громади в дужках — ігноруємо запис
        return None
        
    hromada = hromada_match.group(1).strip()
    # Якщо в дужках вказана інша громада (не Старокостянтинівська), ігноруємо її
    if "Старокостянтинівська" not in hromada:
        return None
        
    name_part = text.split('(')[0].strip()
    
    # Видаляємо префікси м., с., смт. на початку кожного населеного пункту в списку (якщо є розділювачі)
    # Але для надійності будемо шукати назви сіл як цілі слова у всьому name_part
    matched = []
    normalized_name_part = name_part.lower()
    for v in villages_list:
        v_norm = v.lower()
        # Шукаємо назву села як ціле слово з межами слів для уникнення хибних часткових збігів
        pattern = r'(?<![a-zA-Zа-яА-ЯіІїЇєЄґҐ])' + re.escape(v_norm) + r'(?![a-zA-Zа-яА-ЯіІїЇєЄґҐ])'
        if re.search(pattern, normalized_name_part):
            matched.append(v)
            
    if not matched:
        return None
        
    # Повертаємо знайдені населені пункти через кому
    return ", ".join(matched)


# ------------------------------------------------------------
# 2. Налаштування Selenium (безголовий режим)
# ------------------------------------------------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

print("Запуск браузера...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_page_load_timeout(45)
driver.set_script_timeout(30)
wait = WebDriverWait(driver, 10)

all_records = []  # сюди зберемо всі знайдені записи

os.makedirs("html_dumps", exist_ok=True)

try:
    # ------------------------------------------------------------
    # 3. Відкриваємо сайт
    # ------------------------------------------------------------
    driver.get("https://hoe.com.ua/shutdown/all")
    time.sleep(2)

    # ------------------------------------------------------------
    # 4. Обробка вкладки "Аварійні" (TypeId=1)
    # ------------------------------------------------------------
    print("Обробляю аварійні відключення...")
    emergency_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panel_emergancy select.select-rem")))
    Select(emergency_select).select_by_value("12")
    time.sleep(1)  # чекаємо поки почнеться AJAX (з'явиться loader)
    WebDriverWait(driver, 30).until(lambda d: "loader" not in d.find_element(By.ID, "panel_emergancy").get_attribute("class"))
    time.sleep(1)  # пауза для повної відмальовки ДОМ

    # Розгортаємо всі "Показати вулиці"
    for btn in driver.find_elements(By.CSS_SELECTOR, "#panel_emergancy a.show-street"):
        try:
            btn.click()
            time.sleep(0.2)
        except:
            pass

    # Парсимо HTML
    emergency_html = driver.find_element(By.ID, "panel_emergancy").get_attribute("outerHTML")
    
    # Зберігаємо сирий HTML-зліпок для глибокого аналізу
    dump_filename = f"html_dumps/emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(dump_filename, "w", encoding="utf-8") as f:
        f.write(emergency_html)
        
    soup = BeautifulSoup(emergency_html, "html.parser")
    table = soup.find("table", class_="table-shutdowns")
    if table:
        rows = table.find_all("tr")
        i = 0
        while i < len(rows):
            row = rows[i]
            city_tag = row.find("p", class_="city")
            if not city_tag:
                i += 1
                continue

            city_text = city_tag.get_text(strip=True)
            settlement = extract_settlement(city_text, villages)
            if not settlement:
                i += 1
                continue

            # Тип (з наступної комірки)
            tds = row.find_all("td")
            work_type = "Аварійні"
            if len(tds) >= 2:
                work_type = tds[1].get_text(strip=True)

            # Дати та час
            stimes = row.find_all("div", class_="stime")
            created_date = stimes[0].get_text(strip=True) if len(stimes) > 0 else ""
            start_str = stimes[1].get_text(strip=True) if len(stimes) > 1 else ""
            end_str = stimes[2].get_text(strip=True) if len(stimes) > 2 else ""

            # Збираємо вулиці (наступний рядок з класом street)
            streets = []
            streets_detailed = []
            if i + 1 < len(rows) and "street" in rows[i + 1].get("class", []):
                street_row = rows[i + 1]
                for p in street_row.find_all("p"):
                    house_span = p.find("span", class_="house")
                    if house_span:
                        houses = house_span.get_text(strip=True)
                        house_span.decompose()  # Видаляємо тег з номерами, щоб залишилась лише вулиця
                        
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True).strip(" ,")
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            
                        streets.append(street_name)
                        streets_detailed.append({"name": street_name, "houses": houses})
                    else:
                        # Fallback (якщо структура зміниться)
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True)
                            streets.append(street_name)
                            full_text = p.get_text(separator=" ", strip=True)
                            houses = full_text.replace(street_name, "").strip(" ,")
                            streets_detailed.append({"name": street_name, "houses": houses})
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            if street_name:
                                streets.append(street_name)
                                streets_detailed.append({"name": street_name, "houses": ""})
                i += 2  # перестрибуємо рядок з вулицями
            else:
                i += 1

            # Формуємо запис
            all_records.append({
                "settlement": settlement,
                "type": work_type,
                "created_date": created_date,
                "start_datetime": start_str,
                "end_datetime": end_str,
                "streets": streets,
                "streets_detailed": streets_detailed
            })

    # ------------------------------------------------------------
    # 5. Обробка вкладки "Планові" (TypeId=2)
    # ------------------------------------------------------------
    print("Обробляю планові відключення...")
    planned_tab = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='#panel_planned']")))
    driver.execute_script("arguments[0].click();", planned_tab)
    time.sleep(1)

    planned_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panel_planned select.select-rem")))
    Select(planned_select).select_by_value("12")
    time.sleep(1)
    WebDriverWait(driver, 30).until(lambda d: "loader" not in d.find_element(By.ID, "panel_planned").get_attribute("class"))
    time.sleep(1)

    for btn in driver.find_elements(By.CSS_SELECTOR, "#panel_planned a.show-street"):
        try:
            btn.click()
            time.sleep(0.2)
        except:
            pass

    planned_html = driver.find_element(By.ID, "panel_planned").get_attribute("outerHTML")
    
    # Зберігаємо сирий HTML-зліпок для глибокого аналізу
    dump_filename = f"html_dumps/planned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(dump_filename, "w", encoding="utf-8") as f:
        f.write(planned_html)
        
    soup = BeautifulSoup(planned_html, "html.parser")
    table = soup.find("table", class_="table-shutdowns")
    if table:
        rows = table.find_all("tr")
        i = 0
        while i < len(rows):
            row = rows[i]
            city_tag = row.find("p", class_="city")
            if not city_tag:
                i += 1
                continue

            city_text = city_tag.get_text(strip=True)
            settlement = extract_settlement(city_text, villages)
            if not settlement:
                i += 1
                continue

            tds = row.find_all("td")
            work_type = "Планові"
            if len(tds) >= 2:
                work_type = tds[1].get_text(strip=True)

            stimes = row.find_all("div", class_="stime")
            created_date = stimes[0].get_text(strip=True) if len(stimes) > 0 else ""
            start_str = stimes[1].get_text(strip=True) if len(stimes) > 1 else ""
            end_str = stimes[2].get_text(strip=True) if len(stimes) > 2 else ""

            streets = []
            streets_detailed = []
            if i + 1 < len(rows) and "street" in rows[i + 1].get("class", []):
                street_row = rows[i + 1]
                for p in street_row.find_all("p"):
                    house_span = p.find("span", class_="house")
                    if house_span:
                        houses = house_span.get_text(strip=True)
                        house_span.decompose()  # Видаляємо тег з номерами, щоб залишилась лише вулиця
                        
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True).strip(" ,")
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            
                        streets.append(street_name)
                        streets_detailed.append({"name": street_name, "houses": houses})
                    else:
                        # Fallback (якщо структура зміниться)
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True)
                            streets.append(street_name)
                            full_text = p.get_text(separator=" ", strip=True)
                            houses = full_text.replace(street_name, "").strip(" ,")
                            streets_detailed.append({"name": street_name, "houses": houses})
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            if street_name:
                                streets.append(street_name)
                                streets_detailed.append({"name": street_name, "houses": ""})
                i += 2
            else:
                i += 1

            all_records.append({
                "settlement": settlement,
                "type": work_type,
                "created_date": created_date,
                "start_datetime": start_str,
                "end_datetime": end_str,
                "streets": streets,
                "streets_detailed": streets_detailed
            })

    # Helper functions for street name normalization and auto-correction
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

    def get_street_dict_key(settlement):
        if not settlement:
            return "м. Старокостянтинів"
        settlement = settlement.strip()
        if settlement in ["Старокостянтинів", "м. Старокостянтинів"]:
            return "м. Старокостянтинів"
        if settlement.startswith("с. "):
            return settlement
        return "с. " + settlement

    def find_best_official_match(raw_name, official_list, threshold=0.85):
        import difflib
        if not official_list:
            return None
        raw_norm = normalize_street_name(raw_name)
        if not raw_norm:
            return None
            
        exact_matches = []
        for off_name in official_list:
            if raw_name.strip().lower() == off_name.strip().lower():
                return off_name
            if raw_norm == normalize_street_name(off_name):
                exact_matches.append(off_name)
                
        if len(exact_matches) == 1:
            return exact_matches[0]
        elif len(exact_matches) > 1:
            is_raw_prov = "пров" in raw_name.lower()
            for match in exact_matches:
                is_match_prov = "пров" in match.lower()
                if is_raw_prov == is_match_prov:
                    return match
            return exact_matches[0]
            
        best_match = None
        best_ratio = 0.0
        for off_name in official_list:
            off_norm = normalize_street_name(off_name)
            if not off_norm:
                continue
            ratio = difflib.SequenceMatcher(None, raw_norm, off_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = off_name
                
        if best_ratio >= threshold:
            return best_match
        return None

    def expand_house_ranges(houses_str):
        if not houses_str:
            return []
        parts = [p.strip() for p in houses_str.split(",") if p.strip()]
        expanded = set()
        for part in parts:
            part_lower = part.lower()
            if any(w in part_lower for w in ["опора", "будка", "гараж", "блок", "каб", "оп"]):
                continue
            match = re.match(r"^(\d+)-(\d+)$", part)
            if match:
                start = int(match.group(1))
                end = int(match.group(2))
                if start > end:
                    start, end = end, start
                if end - start <= 50:
                    for i in range(start, end + 1):
                        expanded.add(str(i))
                else:
                    expanded.add(part)
            else:
                cleaned = re.sub(r"[^\d/a-zA-Zа-яА-Я\-]", "", part)
                if cleaned:
                    expanded.add(cleaned)
        return list(expanded)

    def is_technical_object(street_name):
        if not street_name:
            return False
        name_lower = street_name.lower().strip()
        # Паттерни для КТП, ТП, ЗТП, ПЛ, КЛ, ПС, фідерів, опор тощо
        tech_patterns = [
            r"\b(к?тп|зтп|пс|пл|кл)\b[- ]?\d+",  # КТП-12, ТП 5, ПЛ-10
            r"\b(опора|оп)\b[- ]?\d+",           # опора 12, оп. 45
            r"\b(фідер|трансформатор)\b",       # фідер, трансформатор
            r"\b[а-яа-я\d]+-\d+кв\b",            # Л-10кВ, ПЛ-10кВ
            r"\b(ктп|зтп|тп|пс|пл|кл)\b$"        # поодинокі абревіатури в кінці
        ]
        for pattern in tech_patterns:
            if re.search(pattern, name_lower):
                return True
        return False

    def apply_street_corrections(records):
        official_streets_path = "data/clean_official_streets.json"
        corrections_path = "data/street_corrections.json"
        districts_path = "data/districts.json"
        
        from geocoder import OSMGeocoder
        geocoder = OSMGeocoder()
        
        official_data = {}
        if os.path.exists(official_streets_path):
            try:
                with open(official_streets_path, "r", encoding="utf-8") as f:
                    official_data = json.load(f)
            except Exception as e:
                print(f"[ERROR] Не вдалося завантажити clean_official_streets.json: {e}")
                
        districts_data = {}
        if os.path.exists(districts_path):
            try:
                with open(districts_path, "r", encoding="utf-8") as f:
                    districts_data = json.load(f)
            except Exception as e:
                print(f"[ERROR] Не вдалося завантажити districts.json: {e}")
                
        corrections_data = {}
        if os.path.exists(corrections_path):
            try:
                with open(corrections_path, "r", encoding="utf-8") as f:
                    corrections_data = json.load(f)
            except Exception as e:
                print(f"[ERROR] Не вдалося завантажити street_corrections.json: {e}")

        corrected_count = 0
        new_records = []
        for rec in records:
            settlement = rec.get("settlement")
            sett_candidates = [s.strip() for s in settlement.split(",") if s.strip()]
            if not sett_candidates:
                sett_candidates = ["м. Старокостянтинів"]
            dict_key = get_street_dict_key(sett_candidates[0])
            
            sett_corrections = corrections_data.get(dict_key, {})
            
            streets = rec.get("streets", [])
            streets_detailed = rec.get("streets_detailed", [])
            
            s_det_map = {}
            for s_det in streets_detailed:
                name = s_det.get("name")
                if name:
                    s_det_map[name] = s_det
                    
            moved_streets = {} # target_settlement -> { "streets": [], "streets_detailed": [] }
            remaining_streets = []
            remaining_detailed = []
            
            all_streets_set = list(dict.fromkeys(streets + list(s_det_map.keys())))
            
            for s in all_streets_set:
                s_det = s_det_map.get(s)
                
                # Перевіряємо чи є назва технічним об'єктом обленерго (КТП, ТП, опора тощо)
                if is_technical_object(s):
                    # Технічні об'єкти ігноруємо, вони не є житловими вулицями
                    corrected_count += 1
                    continue
                    
                houses_str = s_det.get("houses", "") if s_det else ""
                
                # Пошук правил для вулиці у всіх розпарсених кандидатах населених пунктів
                rule = None
                for cand in sett_candidates:
                    cand_key = get_street_dict_key(cand)
                    rule = corrections_data.get(cand_key, {}).get(s)
                    if rule:
                        break
                        
                if not rule:
                    is_official_here = False
                    official_matches = []  # список (candidate_sett, official_name)
                    for cand in sett_candidates:
                        cand_key = get_street_dict_key(cand)
                        off_dict = official_data.get(cand_key, {})
                        if isinstance(off_dict, dict):
                            for off_name in off_dict.keys():
                                if s.strip().lower() == off_name.strip().lower() or normalize_street_name(s) == normalize_street_name(off_name):
                                    official_matches.append((cand, off_name))
                                    break
                                    
                    if official_matches:
                        is_official_here = True
                        # Якщо парсованих н.п. кілька, або якщо збіг відрізняється від первинного села
                        if len(sett_candidates) > 1 or official_matches[0][0] != sett_candidates[0]:
                            if len(official_matches) == 1:
                                rule = {
                                    "action": "move_to_settlement",
                                    "target_settlements": [official_matches[0][0]],
                                    "target_street": official_matches[0][1],
                                    "auto": True
                                }
                            else:
                                # Перевіряємо будинки для вибору правильного села (Питання 1 - Варіант А)
                                expanded_houses = expand_house_ranges(houses_str)
                                house_matches = []
                                for cand, off_name in official_matches:
                                    cand_key = get_street_dict_key(cand)
                                    off_houses = official_data.get(cand_key, {}).get(off_name, {}).get("houses", [])
                                    matched_houses = [h for h in expanded_houses if h in off_houses]
                                    if matched_houses:
                                        house_matches.append((cand, off_name))
                                        
                                if len(house_matches) == 1:
                                    rule = {
                                        "action": "move_to_settlement",
                                        "target_settlements": [house_matches[0][0]],
                                        "target_street": house_matches[0][1],
                                        "auto": True
                                    }
                                else:
                                    # Амбівалентність або немає номерів будинків — у Пісочницю
                                    rule = {
                                        "action": "move_to_settlement",
                                        "target_settlements": ["Пісочниця"],
                                        "target_street": s,
                                        "auto": True
                                    }
                                    
                    if not is_official_here:
                        # Auto-routing fallback: шукаємо по всій громаді (Питання 2)
                        community_matches = []
                        norm_s = normalize_street_name(s)
                        for other_sett, other_streets_dict in official_data.items():
                            if other_sett == "Пісочниця":
                                continue
                            for off_name in other_streets_dict.keys():
                                if s.strip().lower() == off_name.strip().lower() or norm_s == normalize_street_name(off_name):
                                    clean_sett = re.sub(r"^(с\.|м\.|c\.|m\.)\s*", "", other_sett).strip()
                                    community_matches.append((clean_sett, off_name))
                                    break
                                    
                        if len(community_matches) == 1:
                            rule = {
                                "action": "move_to_settlement",
                                "target_settlements": [community_matches[0][0]],
                                "target_street": community_matches[0][1],
                                "auto": True
                            }
                        elif len(community_matches) > 1:
                            # Перевіряємо будинки для вибору правильного села у всій громаді
                            expanded_houses = expand_house_ranges(houses_str)
                            house_matches = []
                            for other_sett_name, off_name in community_matches:
                                other_sett_key = get_street_dict_key(other_sett_name)
                                off_houses = official_data.get(other_sett_key, {}).get(off_name, {}).get("houses", [])
                                matched_houses = [h for h in expanded_houses if h in off_houses]
                                if matched_houses:
                                    house_matches.append((other_sett_name, off_name))
                                    
                            if len(house_matches) == 1:
                                rule = {
                                    "action": "move_to_settlement",
                                    "target_settlements": [house_matches[0][0]],
                                    "target_street": house_matches[0][1],
                                    "auto": True
                                }
                            else:
                                rule = {
                                    "action": "move_to_settlement",
                                    "target_settlements": ["Пісочниця"],
                                    "target_street": s,
                                    "auto": True
                                }
                        else:
                            # Вулицю взагалі не знайдено в локальному реєстрі.
                            # Спробуємо підтвердити її через онлайн-геокодер OpenStreetMap.
                            target_sett = sett_candidates[0]
                            if geocoder.verify_street_in_settlement(target_sett, s):
                                print(f"[AUTO-OSM] Вулиця '{s}' підтверджена в OSM для '{target_sett}'")
                                
                                # Додаємо нову вулицю до реєстру в пам'яті
                                target_key = get_street_dict_key(target_sett)
                                if target_key not in official_data:
                                    official_data[target_key] = {}
                                    
                                expanded_houses = expand_house_ranges(houses_str)
                                official_data[target_key][s] = {
                                    "type": "вулиця",
                                    "houses": sorted(list(set(expanded_houses))),
                                    "blacklist": []
                                }
                                
                                # Зберігаємо оновлений реєстр на диск
                                try:
                                    with open(official_streets_path, "w", encoding="utf-8") as f:
                                        json.dump(official_data, f, ensure_ascii=False, indent=2)
                                    print(f"[AUTO-OSM] Базу '{official_streets_path}' успішно оновлено новою вулицею '{s}'")
                                except Exception as e:
                                    print(f"[ERROR] Не вдалося зберегти оновлений реєстр: {e}")
                                    
                                rule = {
                                    "action": "rename",
                                    "target": s,
                                    "auto": True
                                }
                            else:
                                # Перевіряємо чи є правило у Пісочниці в corrections_data
                                rule = corrections_data.get("Пісочниця", {}).get(s)
                                if not rule:
                                    rule = {
                                        "action": "move_to_settlement",
                                        "target_settlements": ["Пісочниця"],
                                        "target_street": s,
                                        "auto": True
                                    }
                                
                if not rule:
                    if s in streets:
                        remaining_streets.append(s)
                    if s_det:
                        remaining_detailed.append(s_det)
                    continue
                    
                action = rule.get("action")
                if action == "delete":
                    corrected_count += 1
                    continue
                elif action == "hide":
                    if s in streets:
                        remaining_streets.append(s)
                    if s_det:
                        remaining_detailed.append(s_det)
                    continue
                elif action == "unverified":
                    if s in streets:
                        remaining_streets.append(s)
                    if s_det:
                        remaining_detailed.append(s_det)
                    continue
                elif action == "rename" and rule.get("target"):
                    target_name = rule.get("target")
                    if s in streets:
                        remaining_streets.append(target_name)
                    if s_det:
                        new_det = dict(s_det)
                        new_det["name"] = target_name
                        remaining_detailed.append(new_det)
                    corrected_count += 1
                    continue
                elif action == "move_to_settlement":
                    target_street = rule.get("target_street", s)
                    target_sett_val = rule.get("target_settlements") or rule.get("target_settlement")
                    
                    if isinstance(target_sett_val, list):
                        candidates = [c.strip() for c in target_sett_val if c.strip()]
                    elif isinstance(target_sett_val, str):
                        candidates = [c.strip() for c in target_sett_val.split(",") if c.strip()]
                    else:
                        candidates = []
                        
                    if not candidates:
                        if s in streets:
                            remaining_streets.append(s)
                        if s_det:
                            remaining_detailed.append(s_det)
                        continue
                        
                    if len(candidates) == 1:
                        target_sett = candidates[0]
                        if target_sett not in moved_streets:
                            moved_streets[target_sett] = {"streets": [], "streets_detailed": []}
                        moved_streets[target_sett]["streets"].append(target_street)
                        if s_det:
                            new_det = dict(s_det)
                            new_det["name"] = target_street
                            moved_streets[target_sett]["streets_detailed"].append(new_det)
                        corrected_count += 1
                    else:
                        # 3-level selection logic
                        expanded = expand_house_ranges(houses_str)
                        
                        # Level 1: House matching
                        cand_matches = {}
                        any_match = False
                        for cand in candidates:
                            cand_key = get_street_dict_key(cand)
                            off_dict = official_data.get(cand_key, {})
                            off_street = find_best_official_match(target_street, off_dict.keys()) if off_dict else None
                            if off_street:
                                off_houses = off_dict[off_street].get("houses", [])
                                matched = [h for h in expanded if h in off_houses]
                                if matched:
                                    cand_matches[cand] = set(matched)
                                    any_match = True
                                    
                        if any_match:
                            assigned = {c: [] for c in candidates}
                            active_cands = [c for c, m in cand_matches.items() if m]
                            
                            for h in expanded:
                                matched_any = False
                                for c in candidates:
                                    if c in cand_matches and h in cand_matches[c]:
                                        assigned[c].append(h)
                                        matched_any = True
                                if not matched_any:
                                    for c in active_cands:
                                        assigned[c].append(h)
                                        
                            for cand, h_list in assigned.items():
                                if h_list:
                                    if cand not in moved_streets:
                                        moved_streets[cand] = {"streets": [], "streets_detailed": []}
                                    moved_streets[cand]["streets"].append(target_street)
                                    
                                    # Sort house list
                                    h_list.sort(key=lambda x: (int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0, x))
                                    moved_streets[cand]["streets_detailed"].append({
                                        "name": target_street,
                                        "houses": ", ".join(h_list)
                                    })
                            corrected_count += 1
                        else:
                            # Level 2: Neighborhood match
                            votes = {c: 0 for c in candidates}
                            other_streets = [st for st in all_streets_set if st != s and st in streets]
                            
                            for other in other_streets:
                                for cand in candidates:
                                    cand_key = get_street_dict_key(cand)
                                    off_dict = official_data.get(cand_key, {})
                                    if off_dict:
                                        matched_other = find_best_official_match(other, off_dict.keys())
                                        if matched_other:
                                            votes[cand] += 1
                                            
                            max_votes = max(votes.values()) if votes else 0
                            if max_votes > 0:
                                winners = [c for c, v in votes.items() if v == max_votes]
                                for cand in winners:
                                    if cand not in moved_streets:
                                        moved_streets[cand] = {"streets": [], "streets_detailed": []}
                                    moved_streets[cand]["streets"].append(target_street)
                                    if s_det:
                                        new_det = dict(s_det)
                                        new_det["name"] = target_street
                                        moved_streets[cand]["streets_detailed"].append(new_det)
                                corrected_count += 1
                            else:
                                # Level 3: Fallback (Duplicate)
                                for cand in candidates:
                                    if cand not in moved_streets:
                                        moved_streets[cand] = {"streets": [], "streets_detailed": []}
                                    moved_streets[cand]["streets"].append(target_street)
                                    if s_det:
                                        new_det = dict(s_det)
                                        new_det["name"] = target_street
                                        moved_streets[cand]["streets_detailed"].append(new_det)
                                corrected_count += 1
                                
            # Update original record
            rec["streets"] = remaining_streets
            rec["streets_detailed"] = remaining_detailed
            
            # If original record still has streets, keep it
            if len(remaining_streets) > 0 or len(remaining_detailed) > 0:
                new_records.append(rec)
                
            # Create new records for moved streets
            for target_sett, data in moved_streets.items():
                moved_rec = dict(rec)
                moved_rec["settlement"] = target_sett
                if target_sett == "Пісочниця":
                    moved_rec["original_settlement"] = rec.get("settlement", "")
                moved_rec["streets"] = list(dict.fromkeys(data["streets"]))
                moved_rec["streets_detailed"] = data["streets_detailed"]
                new_records.append(moved_rec)
                
        # Now apply fuzzy match against official list for all records,
        # and move unmatched/doubtful streets to the "Пісочниця" settlement.
        records = new_records
        final_records = []
        for rec in records:
            settlement = rec.get("settlement")
            if settlement == "Пісочниця":
                final_records.append(rec)
                continue
                
            dict_key = get_street_dict_key(settlement)
            official_list = official_data.get(dict_key, {})
            if isinstance(official_list, dict):
                official_list = list(official_list.keys())
                
            streets = rec.get("streets", [])
            streets_detailed = rec.get("streets_detailed", [])
            
            # Fuzzy match first
            matched_streets = []
            for s in streets:
                match = find_best_official_match(s, official_list)
                if match and match != s:
                    matched_streets.append(match)
                    corrected_count += 1
                else:
                    matched_streets.append(s)
            
            s_det_map = {}
            for s_det in streets_detailed:
                name = s_det.get("name")
                if name:
                    match = find_best_official_match(name, official_list)
                    if match and match != name:
                        s_det["name"] = match
                        corrected_count += 1
                    s_det_map[s_det["name"]] = s_det
            
            # Now divide into verified and unverified (sandbox)
            verified_streets = []
            verified_detailed = []
            sandbox_streets = []
            sandbox_detailed = []
            
            # Combine all unique streets in this record
            all_rec_streets = list(dict.fromkeys(matched_streets + list(s_det_map.keys())))
            
            for s in all_rec_streets:
                s_det = s_det_map.get(s)
                # Check if it is in official list
                is_official = False
                for off_name in official_list:
                    if s.strip().lower() == off_name.strip().lower() or normalize_street_name(s) == normalize_street_name(off_name):
                        is_official = True
                        break
                
                # Check if original settlement is a community settlement
                is_community = False
                if settlement:
                    sett_clean = re.sub(r"^(с\.|м\.|c\.|m\.)\s*", "", settlement.strip()).strip()
                    if sett_clean in ["Старокостянтинів", "м. Старокостянтинів", "Старокостянтинівська громада"]:
                        is_community = True
                    else:
                        for villages in districts_data.values():
                            if any(v.lower().replace(" ", "") == sett_clean.lower().replace(" ", "") for v in villages):
                                is_community = True
                                break
                                
                # вул. Озерна always goes to Sandbox
                is_ozerna = (s.strip().lower() == "вул. озерна" or normalize_street_name(s) == "озерна")
                
                if is_official or (is_community and not is_ozerna):
                    if s in matched_streets:
                        verified_streets.append(s)
                    if s_det:
                        verified_detailed.append(s_det)
                else:
                    if s in matched_streets:
                        sandbox_streets.append(s)
                    if s_det:
                        sandbox_detailed.append(s_det)
            
            # If there are verified streets, keep the original record with them (with standardized settlement name)
            if verified_streets or verified_detailed:
                rec_ver = dict(rec)
                rec_ver["settlement"] = dict_key
                rec_ver["streets"] = verified_streets
                rec_ver["streets_detailed"] = verified_detailed
                final_records.append(rec_ver)
                
            # If there are sandbox streets, create a new record under "Пісочниця"
            if sandbox_streets or sandbox_detailed:
                rec_box = dict(rec)
                rec_box["settlement"] = "Пісочниця"
                rec_box["original_settlement"] = rec.get("settlement", "")
                rec_box["streets"] = sandbox_streets
                rec_box["streets_detailed"] = sandbox_detailed
                final_records.append(rec_box)
                
        records = final_records
        if corrected_count > 0:
            print(f"[CORRECTOR] Успішно автокоректовано {corrected_count} назв вулиць на основі бази!")
        return records

    # Застосовуємо автокорекцію вулиць на основі офіційного словника перед збереженням
    all_records = apply_street_corrections(all_records)

    # Запускаємо ШІ-суддю для автоматичної обробки та розпізнавання адрес із Пісочниці
    # На GitHub Actions запускається автоматично, а локально - тільки за запитом з адмінки
    if os.environ.get("GITHUB_ACTIONS") == "true":
        try:
            from ai_judge import AIJudge
            judge = AIJudge()
            all_records = judge.judge_sandbox_records(all_records)
        except Exception as e:
            print(f"[WARN] Не вдалося виконати ШІ-суддю для Пісочниці: {e}")

    # ------------------------------------------------------------
    # 6. Зберігаємо результат
    # ------------------------------------------------------------
    with open("data/outages_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"✅ Готово! Зібрано {len(all_records)} записів. Дані збережено в data/outages_snapshot.json")

    # ------------------------------------------------------------
    # 7. Оновлення Архіву (archive.json)
    # ------------------------------------------------------------
    archive_path = "data/archive.json"
    archive_records = []
    try:
        with open(archive_path, "r", encoding="utf-8") as f:
            archive_records = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Створюємо унікальний підпис (ключ) для кожного запису без вулиць
    def get_rec_signature(rec):
        return f"{rec.get('settlement')}-{rec.get('type')}-{rec.get('start_datetime')}-{rec.get('end_datetime')}"

    # Створюємо словник для швидкого пошуку існуючих записів
    archive_dict = {get_rec_signature(r): r for r in archive_records}
    
    for rec in all_records:
        sig = get_rec_signature(rec)
        if sig in archive_dict:
            # Оновлюємо масив вулиць (можливо Обленерго додали нові будинки)
            archive_dict[sig]["streets"] = rec.get("streets", [])
            archive_dict[sig]["streets_detailed"] = rec.get("streets_detailed", [])
            # Оновлюємо last_seen_at, щоб бачити, коли запис ще був актуальним
            archive_dict[sig]["last_seen_at"] = datetime.now().isoformat()
        else:
            # Додаємо новий запис із фіксацією точного часу виявлення
            rec["first_seen_at"] = datetime.now().isoformat()
            rec["last_seen_at"] = datetime.now().isoformat()
            archive_records.append(rec)
            archive_dict[sig] = rec

    # Очищення старих записів (>40 днів)
    cutoff_date = datetime.now() - timedelta(days=40)
    filtered_archive = []
    for rec in archive_records:
        start_str = rec.get("start_datetime", "")
        # Фікс формату дати якщо немає пробілу
        if len(start_str) >= 5 and not " " in start_str[-6:]:
            start_str = f"{start_str[:-5]} {start_str[-5:]}"
            
        try:
            dt = datetime.strptime(start_str, "%d.%m.%Y %H:%M")
            if dt >= cutoff_date:
                filtered_archive.append(rec)
        except ValueError:
            filtered_archive.append(rec)

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(filtered_archive, f, ensure_ascii=False, indent=2)
    print(f"✅ Архів оновлено (всього {len(filtered_archive)} записів у archive.json)")

    write_update_log({
        "timestamp": datetime.now().isoformat(),
        "stage": "collector",
        "status": "ok",
        "records_count": len(all_records),
        "message": f"Збір успішно завершено. Знайдено записів: {len(all_records)}."
    })

except Exception as e:
    print(f"\n❌ СТАЛАСЯ ПОМИЛКА під час збору даних: {e}")
    traceback.print_exc()
    error_msg = str(e)
    status = "error"
    if "WebDriver" in error_msg or "Timeout" in error_msg or "http" in error_msg or "connection" in error_msg.lower():
        status = "http_error"
    elif "BeautifulSoup" in error_msg or "find" in error_msg or "structure" in error_msg.lower():
        status = "structure_error"
    write_update_log({
        "timestamp": datetime.now().isoformat(),
        "stage": "collector",
        "status": status,
        "records_count": 0,
        "message": f"Помилка збору: {error_msg}"
    })
    try:
        driver.quit()
    except:
        pass
    sys.exit(1)
finally:
    try:
        driver.quit()
    except:
        pass