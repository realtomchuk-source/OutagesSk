import json
import os
import requests
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
import hashlib
import sys
import re

try:
    import google.generativeai as genai
    HAS_GOOGLE_AI = True
except ImportError:
    HAS_GOOGLE_AI = False

load_dotenv()

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not GOOGLE_API_KEY and not OPENROUTER_API_KEY:
    print("[ERROR] Жодного API-ключа не знайдено в .env (GEMINI_API_KEY або OPENROUTER_API_KEY)")
    sys.exit(1)

GOOGLE_MODEL = "gemini-2.0-flash"
OPENROUTER_MODEL = "google/gemini-2.5-flash"


# ------------------------------------------------------------
# Функція виклику ШІ
# ------------------------------------------------------------
def ask_ai(prompt):
    if HAS_GOOGLE_AI and GOOGLE_API_KEY:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(GOOGLE_MODEL)
            response = model.generate_content(prompt, request_options={"timeout": 30.0})
            return response.text.strip()
        except Exception as e:
            print(f"[WARN] Помилка Google AI: {e}")
            print("Перемикаюсь на OpenRouter...")

    if OPENROUTER_API_KEY:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"[ERROR] OpenRouter помилка {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[ERROR] OpenRouter виклик не вдався: {e}")
    return None

# ------------------------------------------------------------
# Налаштування системного часу для Києва
# ------------------------------------------------------------
def get_kyiv_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Kyiv")).replace(tzinfo=None)
    except Exception:
        # Резервний варіант: якщо середовище підтримує TZ env, datetime.now() буде правильним
        return datetime.now()

ai_called = False
warnings_list = []

def update_latest_log(status, message_append=None, stage="formatter"):
    log_path = "data/update_log.json"
    logs = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            pass
    if logs:
        latest = logs[-1]
        latest["stage"] = stage
        latest["status"] = status
        latest["timestamp"] = get_kyiv_now().isoformat()
        if message_append:
            if latest.get("message"):
                if message_append not in latest["message"]:
                    latest["message"] += " | " + message_append
            else:
                latest["message"] = message_append
    else:
        logs.append({
            "timestamp": get_kyiv_now().isoformat(),
            "stage": stage,
            "status": status,
            "message": message_append or ""
        })
    logs = logs[-100:]
    try:
        os.makedirs("data", exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as err:
        print(f"Помилка запису логу у formatter: {err}")

def exception_hook(exctype, value, tb):
    import traceback
    print(f"\n❌ СТАЛАСЯ ПОМИЛКА під час форматування: {value}")
    traceback.print_exception(exctype, value, tb)
    try:
        update_latest_log(status="error", message_append=f"Помилка форматування: {value}")
    except:
        pass
    sys.exit(1)

sys.excepthook = exception_hook

# ------------------------------------------------------------
# Завантаження даних
# ------------------------------------------------------------
try:
    snapshot_path = os.getenv("OUTAGES_SNAPSHOT_PATH", "data/outages_snapshot.json")
    with open(snapshot_path, "r", encoding="utf-8") as f:
        outages = json.load(f)
except FileNotFoundError:
    outages = []

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

_corrections_data_cache = None

def get_corrections_data():
    global _corrections_data_cache
    if _corrections_data_cache is None:
        corrections_path = os.getenv("STREET_CORRECTIONS_PATH", "data/street_corrections.json")
        if os.path.exists(corrections_path):
            try:
                with open(corrections_path, "r", encoding="utf-8") as f:
                    _corrections_data_cache = json.load(f)
            except Exception as e:
                print(f"[ERROR] Не вдалося завантажити street_corrections.json: {e}")
                _corrections_data_cache = {}
        else:
            _corrections_data_cache = {}
    return _corrections_data_cache

def is_street_hidden(settlement, street):
    corrections = get_corrections_data()
    dict_key = get_street_dict_key(settlement)
    rule = corrections.get(dict_key, {}).get(street)
    if rule and rule.get("action") == "hide":
        return True
    return False

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
def save_corrections_data(data):
    global _corrections_data_cache
    _corrections_data_cache = data
    corrections_path = os.getenv("STREET_CORRECTIONS_PATH", "data/street_corrections.json")
    try:
        with open(corrections_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Не вдалося зберегти street_corrections.json: {e}")

def run_auto_decolonization_check(settlement, street, official_list):
    """
    Checks if a street name is a communist/colonial/Soviet name and tries to match it
    with a modern official name from the whitelist (official_list).
    Returns the official name if a match is found, otherwise None.
    """
    if not GOOGLE_API_KEY and not OPENROUTER_API_KEY:
        return None
    if not official_list:
        return None
        
    official_streets_formatted = "\n".join([f"- {name}" for name in official_list])
    
    prompt = f"""You are an assistant for decolonizing and renaming streets in Ukraine.
Your task is to check if the given street name is an old communist/colonial/Soviet name (e.g., Леніна, Дзержинського, Кірова, Комсомольська, Жовтнева, Чапаєва, etc.) or a misspelled old name, and if so, map it to its modern official Ukrainian name from the provided whitelist of streets for that settlement.

Settlement: {settlement}
Old Street Name: {street}
Whitelist of Official Streets:
{official_streets_formatted}

Instructions:
1. If the old street name is NOT a communist/colonial/Soviet/Russian-colonial name, or is already neutral/modern, return "null".
2. If the old street name IS a colonial/communist name, find its new renamed counterpart in the Whitelist of Official Streets. The match must be exact (case and spelling) as it appears in the whitelist.
3. If the modern counterpart is NOT present in the whitelist, or you are not sure, return "null".
4. Do not invent any names. Only return a name from the whitelist or "null".
5. Return ONLY the matched street name from the whitelist, or the word "null" (without quotes, no markdown formatting, no explanations)."""

    try:
        response = ask_ai(prompt)
        if response:
            clean_resp = response.strip().replace('"', '').replace("'", "")
            # Remove any markdown wrapping if any
            clean_resp = clean_resp.replace('`', '')
            if clean_resp.lower() == "null" or not clean_resp:
                return None
            # Verify that the response is actually in the official_list
            for off_name in official_list:
                if (clean_resp.strip().lower() == off_name.strip().lower() or 
                    normalize_street_name(clean_resp) == normalize_street_name(off_name)):
                    return off_name
    except Exception as e:
        print(f"[ERROR] Помилка автодеколонізації для {street}: {e}")
    return None

def apply_street_corrections(records):
    official_streets_path = os.getenv("OFFICIAL_STREETS_PATH", "data/official_streets.json")
    corrections_path = os.getenv("STREET_CORRECTIONS_PATH", "data/street_corrections.json")
    
    official_data = {}
    if os.path.exists(official_streets_path):
        try:
            with open(official_streets_path, "r", encoding="utf-8") as f:
                official_data = json.load(f)
        except Exception as e:
            print(f"[ERROR] Не вдалося завантажити official_streets.json: {e}")
            
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
        dict_key = get_street_dict_key(settlement)
        
        sett_corrections = corrections_data.setdefault(dict_key, {})
        
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
            houses_str = s_det.get("houses", "") if s_det else ""
            
            rule = sett_corrections.get(s)
            if not rule:
                # Check if it is in official list
                official_list = official_data.get(dict_key, {})
                if isinstance(official_list, dict):
                    official_list = list(official_list.keys())
                
                if not official_list:
                    is_official = True
                else:
                    is_official = False
                    for off_name in official_list:
                        if s.strip().lower() == off_name.strip().lower() or normalize_street_name(s) == normalize_street_name(off_name):
                            is_official = True
                            break
                
                if not is_official and settlement != "Пісочниця":
                    # Run AI decolonization check
                    rename_target = run_auto_decolonization_check(settlement, s, official_list)
                    timestamp = datetime.now().isoformat() + "Z"
                    if rename_target:
                        print(f"[AI DECOLONIZATION] Вулиця '{s}' у '{settlement}' перейменована на '{rename_target}' за допомогою ШІ")
                        rule = {
                            "action": "rename",
                            "target": rename_target,
                            "timestamp": timestamp,
                            "auto": True
                        }
                        sett_corrections[s] = rule
                        save_corrections_data(corrections_data)
                    else:
                        print(f"[AI DECOLONIZATION] Вулиця '{s}' у '{settlement}' позначена як неверифікована за допомогою ШІ")
                        rule = {
                            "action": "unverified",
                            "timestamp": timestamp,
                            "auto": True
                        }
                        sett_corrections[s] = rule
                        save_corrections_data(corrections_data)
                else:
                    # Street is official or Sandbox, just keep it
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
            if not official_list:
                is_official = True
            else:
                is_official = False
                for off_name in official_list:
                    if s.strip().lower() == off_name.strip().lower() or normalize_street_name(s) == normalize_street_name(off_name):
                        is_official = True
                        break
            
            if is_official:
                if s in matched_streets:
                    verified_streets.append(s)
                if s_det:
                    verified_detailed.append(s_det)
            else:
                if s in matched_streets:
                    sandbox_streets.append(s)
                if s_det:
                    sandbox_detailed.append(s_det)
        
        # If there are verified streets, keep the original record with them
        if verified_streets or verified_detailed:
            rec_ver = dict(rec)
            rec_ver["streets"] = verified_streets
            rec_ver["streets_detailed"] = verified_detailed
            final_records.append(rec_ver)
            
        # If there are sandbox streets, create a new record under "Пісочниця"
        if sandbox_streets or sandbox_detailed:
            rec_box = dict(rec)
            rec_box["settlement"] = "Пісочниця"
            rec_box["streets"] = sandbox_streets
            rec_box["streets_detailed"] = sandbox_detailed
            final_records.append(rec_box)
            
    records = final_records
    if corrected_count > 0:
        print(f"[CORRECTOR] Успішно автокоректовано {corrected_count} назв вулиць на основі бази!")
        try:
            snapshot_path = os.getenv("OUTAGES_SNAPSHOT_PATH", "data/outages_snapshot.json")
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] Не вдалося зберегти оновлений outages_snapshot.json: {e}")
            
    return records

if __name__ == "__main__":
    # Застосовуємо автокорекцію вулиць на основі поточного стану бази
    outages = apply_street_corrections(outages)

    # ------------------------------------------------------------
    # Телеметрія змін (Smart Monitor)
    # ------------------------------------------------------------
    has_cardinal_changes = True
    prev_snapshot_path = os.getenv("PREVIOUS_SNAPSHOT_PATH", "data/previous_snapshot.json")
    try:
        with open(prev_snapshot_path, "r", encoding="utf-8") as f:
            previous_outages = json.load(f)
            
        # Порівняння за допомогою хешування JSON-рядків (ігноруючи порядок)
        # Щоб не реагувати на дрібниці, порівнюємо відсортовані представлення
        curr_str = json.dumps(sorted(outages, key=lambda x: str(x)), sort_keys=True)
        prev_str = json.dumps(sorted(previous_outages, key=lambda x: str(x)), sort_keys=True)
        
        if curr_str == prev_str:
            has_cardinal_changes = False
            print("[TELEMETRY] Кардинальних змін на сайті немає. Використовуються попередні дані.")
        else:
            print("[TELEMETRY] Виявлено зміни на сайті Обленерго!")
            # Записуємо лог
            log_entry = {"time": get_kyiv_now().isoformat(), "msg": "Detected changes in outages_snapshot"}
            try:
                with open("data/changelog.json", "r", encoding="utf-8") as clog:
                    changelog = json.load(clog)
            except (FileNotFoundError, json.JSONDecodeError):
                changelog = []
            changelog.append(log_entry)
            with open("data/changelog.json", "w", encoding="utf-8") as clog:
                json.dump(changelog, clog, ensure_ascii=False, indent=2)

    except FileNotFoundError:
        print(f"[TELEMETRY] Немає {prev_snapshot_path}, створюємо.")

    # Зберігаємо поточний снепшот як попередній для наступного запуску
    with open(prev_snapshot_path, "w", encoding="utf-8") as f:
        json.dump(outages, f, ensure_ascii=False, indent=2)

try:
    with open("data/districts.json", "r", encoding="utf-8") as f:
        districts_raw = json.load(f)
        districts = {}
        for d_name, villages in districts_raw.items():
            for v in villages:
                districts[v] = d_name
except FileNotFoundError:
    districts = {}

# ------------------------------------------------------------
# Допоміжні функції
# ------------------------------------------------------------
def fix_datetime(dt_string):
    if len(dt_string) >= 5 and not " " in dt_string[-6:]:
        return f"{dt_string[:-5]} {dt_string[-5:]}"
    return dt_string

def parse_datetime(dt_string):
    if not dt_string: return None
    fixed = fix_datetime(dt_string)
    try:
        return datetime.strptime(fixed, "%d.%m.%Y %H:%M")
    except:
        return None

def is_active_on_date(record, target_date):
    start = parse_datetime(record.get("start_datetime", ""))
    end = parse_datetime(record.get("end_datetime", ""))
    if not start or not end:
        return False
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)
    return start <= day_end and end >= day_start

def format_time_only(dt_string):
    if not dt_string: return ""
    return dt_string[-5:]

UKR_MONTHS = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
}

def extract_time_range(rec):
    start_str = rec.get("start_datetime", "")
    end_str = rec.get("end_datetime", "")
    
    start_dt = parse_datetime(start_str)
    end_dt = parse_datetime(end_str)
    
    if start_dt and end_dt:
        if start_dt.date() == end_dt.date():
            # Звичайне відключення в межах доби
            return f"з {start_dt.strftime('%H:%M')} до {end_dt.strftime('%H:%M')}"
        else:
            # Відключення переходить через опівніч
            sm = UKR_MONTHS.get(start_dt.month, "")
            em = UKR_MONTHS.get(end_dt.month, "")
            return f"з {start_dt.day} {sm} {start_dt.strftime('%H:%M')} до {end_dt.day} {em} {end_dt.strftime('%H:%M')}"
            
    # Fallback
    start = format_time_only(start_str)
    end = format_time_only(end_str)
    return f"з {start} до {end}"



def generate_with_validation(prompt, items, max_retries=2):
    for attempt in range(max_retries + 1):
        content = ask_ai(prompt)
        if not content:
            continue
        
        missing_streets = []
        for rec in items:
            for street in rec.get("streets", []):
                if street not in content:
                    missing_streets.append(street)
        
        has_partial = any(x in content.lower() for x in ["частково", "частков", "частк."])
        
        if not missing_streets and not has_partial:
            return content
            
        if missing_streets:
            print(f"[WARN] Спроба {attempt + 1}: ШІ загубив вулиці ({', '.join(missing_streets)}). Повторюю генерацію...")
        elif has_partial:
            print(f"[WARN] Спроба {attempt + 1}: ШІ використав скорочення 'частково'. Повторюю генерацію...")
    
    print("[ERROR] ШІ не зміг згенерувати повний список без втрат чи скорочень після всіх спроб.")
    return None

# ------------------------------------------------------------
# Допоміжні функції для очищення адрес стрічки
# ------------------------------------------------------------
def clean_house_numbers(houses_str):
    if not houses_str:
        return ""
    parts = [p.strip() for p in houses_str.split(",") if p.strip()]
    cleaned_parts = []
    for p in parts:
        p_lower = p.lower()
        if any(x in p_lower for x in ["опора", "будка", "каб", "оп"]):
            continue
        if p_lower in ["гараж", "блок", "бл."]:
            continue
        if any(p_lower.startswith(x) for x in ["гараж ", "бlock ", "бл. "]) or p_lower.startswith("гараж") or p_lower.startswith("блок"):
            continue
            
        # Розгортання діапазонів будинків (наприклад 1-10)
        range_match = re.match(r"^(\d+)-(\d+)$", p)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                start, end = end, start
            if end - start <= 50:
                for i in range(start, end + 1):
                    cleaned_parts.append(str(i))
                continue
                
        # Залишаємо лише число, дріб/дефіс та літеру (наприклад "32/15", "97", "8")
        match = re.match(r"^(\d+(?:[/\-][а-яА-Яa-zA-Z0-9]+)?|[а-яА-Яa-zA-Z]\d+)", p)
        if match:
            cleaned_parts.append(match.group(1))
        else:
            if not any(x in p_lower for x in ["гараж", "блок", "бл.", "опора", "оп"]):
                cleaned_parts.append(p)
    return ", ".join(cleaned_parts)

# ------------------------------------------------------------
# Генерація Стрічки (Алгоритмічна, без ШІ)
# ------------------------------------------------------------
# Групування та дедуплікація відключень
# ------------------------------------------------------------
def get_grouped_outages(items):
    grouped = {}
    if not items:
        return grouped
        
    for rec in items:
        settlement = rec.get("settlement", "Невідомо")
        # Виключаємо "Пісочницю" з генерації публічних повідомлень
        if settlement == "Пісочниця":
            continue
            
        typ = "Аварійні знеструмлення" if "Аварійні" in rec.get("type", "") else "Планові знеструмлення"
        time_range = extract_time_range(rec)
        
        key = (typ, settlement, time_range)
        if key not in grouped:
            grouped[key] = {}
            
        streets_detailed = rec.get("streets_detailed", [])
        if streets_detailed:
            for s in streets_detailed:
                name = s.get("name", "").strip()
                if not name:
                    continue
                if is_street_hidden(settlement, name):
                    continue
                # Пропускаємо вулиці, що містять технічні слова в назві
                if any(x in name.lower() for x in ["гараж", "опора", "будка"]):
                    continue
                    
                houses_str = s.get("houses", "").strip()
                cleaned_houses = clean_house_numbers(houses_str)
                
                # Якщо спочатку були будинки, але після очищення всі вони ігноровані (наприклад, тільки гаражі/опори)
                if houses_str and not cleaned_houses:
                    if any(x in houses_str.lower() for x in ["гараж", "опора", "будка", "бл."]):
                        continue # Пропускаємо вулицю повністю
                
                if name not in grouped[key]:
                    grouped[key][name] = set()
                if cleaned_houses:
                    for hp in cleaned_houses.split(", "):
                        grouped[key][name].add(hp)
        else:
            # Fallback
            for name in rec.get("streets", []):
                name = name.strip()
                if not name or any(x in name.lower() for x in ["гараж", "опора", "будка"]):
                    continue
                if is_street_hidden(settlement, name):
                    continue
                if name not in grouped[key]:
                    grouped[key][name] = set()
                    
    return grouped

# ------------------------------------------------------------
def group_streets_by_prefix(items, separator="; "):
    known_prefixes = ["вул. ", "пров. ", "пл. ", "проїзд ", "бульвар ", "автодорога "]
    groups = {}
    prefix_order = []
    
    for item in items:
        found_prefix = ""
        rest = item
        for p in known_prefixes:
            if item.startswith(p):
                found_prefix = p
                rest = item[len(p):]
                break
        if found_prefix not in groups:
            groups[found_prefix] = []
            prefix_order.append(found_prefix)
        groups[found_prefix].append(rest)
        
    parts = []
    sorted_prefixes = sorted(prefix_order, key=lambda p: (0 if p == "вул. " else 1 if p == "пров. " else 2, p))
    for p in sorted_prefixes:
        elements = sorted(groups[p])
        elements_str = separator.join(elements)
        if p:
            parts.append(f"{p}{elements_str}")
        else:
            parts.append(elements_str)
            
    return "; ".join(parts)

# ------------------------------------------------------------
def generate_feed_text(items, label):
    grouped = get_grouped_outages(items)
    if not grouped:
        return f"[{label}] Інформація про відключення відсутня."
        
    # Сортування
    sorted_keys = sorted(grouped.keys(), key=lambda k: (0 if "Аварійні" in k[0] else 1, 0 if k[1] == "Старокостянтинів" else 1, k[1], k[2]))
    
    parts = []
    for k in sorted_keys:
        typ, settlement, time_range = k
        streets_dict = grouped[k]
        
        regular_parts = []
        partial_streets = []
        for s_name in sorted(streets_dict.keys()):
            houses_set = streets_dict[s_name]
            if houses_set:
                sorted_houses = sorted(list(houses_set), key=lambda x: (int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 9999, x))
                if len(sorted_houses) <= 5:
                    regular_parts.append(f"{s_name} {', '.join(sorted_houses)}")
                else:
                    partial_streets.append(s_name)
            else:
                regular_parts.append(s_name)
                
        regular_str = group_streets_by_prefix(regular_parts, separator="; ") if regular_parts else ""
        partial_str = f"частково: {group_streets_by_prefix(partial_streets, separator=', ')}" if partial_streets else ""
        
        final_parts = []
        if regular_str:
            final_parts.append(regular_str)
        if partial_str:
            final_parts.append(partial_str)
            
        if final_parts:
            streets_str = "; ".join(final_parts)
            parts.append(f"{typ}: {settlement} ({time_range}): {streets_str}")
            
    return f"[{label}] " + " | ".join(parts) if parts else f"[{label}] Інформація про відключення відсутня."

# ------------------------------------------------------------
# Підготовка дат та перехідного вікна
# ------------------------------------------------------------
if __name__ == "__main__":
    now_kyiv = get_kyiv_now()

    # Якщо година 23:00 - 23:59, зміщуємо референсний день на наступну добу
    if now_kyiv.hour == 23:
        today = now_kyiv.date() + timedelta(days=1)
    else:
        today = now_kyiv.date()
    tomorrow = today + timedelta(days=1)

    # Пауза для аномалій (перехідне вікно з 23:00 до 01:00)
    is_transition_window = (now_kyiv.hour == 23) or (now_kyiv.hour == 0)

    # Фільтруємо дані для Telegram-постів
    items_today = [r for r in outages if is_active_on_date(r, today)]
    items_tomorrow = [r for r in outages if is_active_on_date(r, tomorrow)]

    # ------------------------------------------------------------
    # Робота з data/feed.json (Динамічна стрічка та тижнева сітка)
    # ------------------------------------------------------------
    FEED_PATH = os.getenv("FEED_PATH", "data/feed.json")

    try:
        with open(FEED_PATH, "r", encoding="utf-8") as f:
            feed_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        feed_data = {
            "current_feed": "",
            "last_updated": "",
            "days": [],
            "anomalies_log": []
        }

    if "days" not in feed_data: feed_data["days"] = []
    if "anomalies_log" not in feed_data: feed_data["anomalies_log"] = []

    # Отримуємо дати на наступні 7 днів (сьогодні + 6 днів)
    target_dates = [today + timedelta(days=i) for i in range(7)]
    new_days = []
    current_time_str = now_kyiv.strftime("%H:%M")

    for target_date in target_dates:
        date_str = target_date.strftime("%Y-%m-%d")
        items_for_date = [r for r in outages if is_active_on_date(r, target_date)]
        
        # Визначаємо, чи день за межами горизонту парсингу (> 5 днів)
        is_outside_horizon = (target_date - today).days > 4
        
        if not items_for_date and is_outside_horizon:
            label = "СЬОГОДНІ" if target_date == today else ("ЗАВТРА" if target_date == tomorrow else target_date.strftime("%d.%m.%Y"))
            new_text = f"[{label}] Немає даних (очікується оновлення)"
        else:
            label = "СЬОГОДНІ" if target_date == today else ("ЗАВТРА" if target_date == tomorrow else ("ПІСЛЯЗАВТРА" if target_date == today + timedelta(days=2) else target_date.strftime("%d.%m.%Y")))
            new_text = generate_feed_text(items_for_date, label)
            
        existing_day = next((d for d in feed_data["days"] if d["date"] == date_str), None)
        
        if is_transition_window:
            # У перехідний час формуємо стартову позицію: жодних аномалій, чистий контент
            new_days.append({
                "date": date_str,
                "planned_content": new_text,
                "actual_content": new_text,
                "baseline_created_at": now_kyiv.strftime("%H:%M"),
                "history": [{
                    "timestamp": now_kyiv.isoformat(),
                    "content": new_text,
                    "is_anomaly": False
                }]
            })
        else:
            if existing_day:
                history = existing_day.get("history", [])
                last_version = history[-1]["content"] if history else ""
                baseline_created_at = existing_day.get("baseline_created_at", "")
                
                # Порівнюємо контент без міток часу
                clean_last = re.sub(r"\s*\(Оновлено о \d{2}:\d{2}\)", "", last_version)
                clean_new = re.sub(r"\s*\(Оновлено о \d{2}:\d{2}\)", "", new_text)
                
                planned_content = existing_day.get("planned_content", clean_new)
                actual_content = clean_new
                
                if clean_last != clean_new:
                    # Зміна контенту є аномалією
                    history.append({
                        "timestamp": now_kyiv.isoformat(),
                        "content": clean_new,
                        "is_anomaly": True
                    })
                    feed_data["anomalies_log"].append({
                        "date": date_str,
                        "timestamp": now_kyiv.isoformat(),
                        "old_text": last_version,
                        "new_text": clean_new
                    })
                else:
                    # Історія залишається незмінною, actual_content дорівнює останній версії з історії
                    actual_content = clean_last
                    
                new_days.append({
                    "date": date_str,
                    "planned_content": planned_content,
                    "actual_content": actual_content,
                    "baseline_created_at": baseline_created_at,
                    "history": history
                })
            else:
                new_days.append({
                    "date": date_str,
                    "planned_content": new_text,
                    "actual_content": new_text,
                    "baseline_created_at": "",
                    "history": [{
                        "timestamp": now_kyiv.isoformat(),
                        "content": new_text,
                        "is_anomaly": False
                    }]
                })

    feed_data["days"] = new_days

    # Формуємо поточну стрічку (актуальну на тепер, очищену від [СЬОГОДНІ])
    today_day = next((d for d in new_days if d["date"] == today.strftime("%Y-%m-%d")), None)
    tomorrow_day = next((d for d in new_days if d["date"] == tomorrow.strftime("%Y-%m-%d")), None)

    # Визначаємо, чи є відключення на сьогодні та завтра
    today_has_outages = today_day and not ("Інформація про відключення відсутня" in today_day["actual_content"])
    tomorrow_has_outages = tomorrow_day and not ("Інформація про відключення відсутня" in tomorrow_day["actual_content"])

    if today_day and tomorrow_day:
        if not today_has_outages and not tomorrow_has_outages:
            combined_feed = "Інформація про відключення на сьогодні та завтра відсутня."
        elif not today_has_outages and tomorrow_has_outages:
            combined_feed = f"Інформація про відключення на сьогодні відсутня. | {tomorrow_day['actual_content']}"
        elif today_has_outages and not tomorrow_has_outages:
            clean_today = re.sub(r"^\[СЬОГОДНІ\]\s*", "", today_day["actual_content"])
            combined_feed = f"{clean_today} | [ЗАВТРА] Інформація про відключення відсутня."
        else:
            clean_today = re.sub(r"^\[СЬОГОДНІ\]\s*", "", today_day["actual_content"])
            combined_feed = f"{clean_today} | {tomorrow_day['actual_content']}"
    else:
        # Резервний варіант, якщо якісь об'єкти відсутні
        current_parts = []
        if today_day and today_day["actual_content"]:
            clean_today = re.sub(r"^\[СЬОГОДНІ\]\s*", "", today_day["actual_content"])
            current_parts.append(clean_today)
        if tomorrow_day and tomorrow_day["actual_content"]:
            current_parts.append(tomorrow_day["actual_content"])
        combined_feed = " | ".join(current_parts) if current_parts else "Інформація про відключення відсутня."

    # Визначаємо, чи потрібно додати мітку оновлення на самий початок стрічки
    update_time_str = ""
    if not is_transition_window:
        anomaly_timestamps = []
        # Шукаємо аномалії в історії Сьогодні та Завтра
        for day in [today_day, tomorrow_day]:
            if day:
                for h in day.get("history", []):
                    if h.get("is_anomaly") or h.get("is_manual_edit"):
                        anomaly_timestamps.append(h["timestamp"])
        if anomaly_timestamps:
            latest_ts_str = max(anomaly_timestamps)
            try:
                latest_dt = datetime.fromisoformat(latest_ts_str)
                update_time_str = latest_dt.strftime("%H:%M")
            except Exception:
                pass

    if update_time_str:
        feed_data["current_feed"] = f"(Оновлено о {update_time_str}) {combined_feed}"
    else:
        feed_data["current_feed"] = combined_feed

    feed_data["last_updated"] = now_kyiv.isoformat()

    # Очищення історії (зберігаємо за останні 60 днів)
    cutoff_dt = now_kyiv - timedelta(days=60)
    feed_data["days"] = [d for d in feed_data["days"] if datetime.strptime(d["date"], "%Y-%m-%d") >= cutoff_dt.replace(hour=0, minute=0, second=0, microsecond=0)]
    feed_data["anomalies_log"] = [a for a in feed_data["anomalies_log"] if datetime.fromisoformat(a["timestamp"]) >= cutoff_dt]

    # Зберігаємо структурований JSON
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        json.dump(feed_data, f, ensure_ascii=False, indent=2)
    print("[SUCCESS] feed.json збережено")

    # Зберігаємо чистий плоский текст у feed.txt для іншого додатка
    feed_txt_path = os.getenv("FEED_TXT_PATH", "data/feed.txt")
    with open(feed_txt_path, "w", encoding="utf-8") as txt_f:
        txt_f.write(feed_data["current_feed"])
    print("[SUCCESS] feed.txt збережено")

    # Для сумісності зшиваємо feed_today та feed_tomorrow
    day_after_tomorrow_day = next((d for d in new_days if d["date"] == (today + timedelta(days=2)).strftime("%Y-%m-%d")), None)
    feed_today_content = feed_data["current_feed"]
    feed_tomorrow_parts = []
    if tomorrow_day and tomorrow_day["actual_content"]:
        feed_tomorrow_parts.append(tomorrow_day["actual_content"])
    if day_after_tomorrow_day and day_after_tomorrow_day["actual_content"]:
        feed_tomorrow_parts.append(day_after_tomorrow_day["actual_content"])
    feed_tomorrow_content = " | ".join(feed_tomorrow_parts) if feed_tomorrow_parts else "[ЗАВТРА] Інформація про відключення відсутня."

# ------------------------------------------------------------
# Завантаження messages.json для Кешування
# ------------------------------------------------------------
try:
    messages_path = os.getenv("MESSAGES_PATH", "data/messages.json")
    with open(messages_path, "r", encoding="utf-8") as f:
        existing_messages = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    existing_messages = []

messages_dict = {m["id"]: m for m in existing_messages}

def add_message(m_id, m_date, m_type, m_content, m_hash=None, is_updated=False, updated_at=None):
    if m_content:
        old_created_at = messages_dict.get(m_id, {}).get("created_at")
        messages_dict[m_id] = {
            "id": m_id,
            "date": m_date,
            "type": m_type,
            "content": m_content,
            "hash": m_hash,
            "created_at": old_created_at if old_created_at else get_kyiv_now().isoformat(),
            "is_updated": is_updated,
            "updated_at": updated_at
        }

# ------------------------------------------------------------
# Генерація Telegram-постів (з ШІ)
# ------------------------------------------------------------
def get_tg_post(items, target_date, is_emergency, base_msg_id, allow_splitting=False):
    typ_str = "Аварійні" if is_emergency else "Планові"
    typ_header = "АВАРІЙНИХ" if is_emergency else "ПЛАНОВИХ"
    
    # Фільтруємо записи: виключаємо "Пісочницю" та беремо потрібний тип відключень
    filtered = [
        r for r in items 
        if r.get("settlement") != "Пісочниця" and 
        ((is_emergency and "Аварійні" in r.get("type", "")) or (not is_emergency and "Планові" in r.get("type", "")))
    ]
    
    # Використовуємо наш єдиний групувальник
    grouped = get_grouped_outages(filtered)
    
    if not grouped:
        if is_emergency:
            content = f"Шановні мешканці Старокостянтинівської громади! За оперативною інформацією АТ «Хмельницькобленерго», повідомляємо про аварійні знеструмлення.\n\nНа {target_date.strftime('%d.%m.%Y')} аварійних знеструмлень не зафіксовано."
        else:
            content = f"Шановні мешканці Старокостянтинівської громади! За офіційною інформацією АТ «Хмельницькобленерго», повідомляємо про планові знеструмлення.\n\nНа {target_date.strftime('%d.%m.%Y')} планових знеструмлень не передбачено."
        return [{"id": base_msg_id, "content": content, "hash": "no_outages"}]

    raw_text_parts = []
    line_to_records = {}
    
    # Сортування: місто Старокостянтинів першим, далі села за алфавітом
    sorted_keys = sorted(grouped.keys(), key=lambda k: (0 if k[1] == "Старокостянтинів" else 1, k[1], k[2]))
    
    for k in sorted_keys:
        typ, settlement, time_range = k
        streets_dict = grouped[k]
        
        # Знаходимо відповідні записи в filtered
        matching_recs = [
            r for r in filtered 
            if r.get("settlement") == settlement and extract_time_range(r) == time_range
        ]
        
        district_name = ""
        if settlement != "Старокостянтинів":
            district_name = districts.get(settlement, "Невідомий")
        else:
            district_name = "Місто Старокостянтинів"
            
        streets_str_list = []
        for s_name in sorted(streets_dict.keys()):
            houses_set = streets_dict[s_name]
            if houses_set:
                # Сортування будинків
                sorted_houses = sorted(list(houses_set), key=lambda x: (int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 9999, x))
                # Виводимо весь масив без жодних скорочень типу "(частково)", без круглих дужок
                streets_str_list.append(f"{s_name} буд. {', '.join(sorted_houses)}")
            else:
                streets_str_list.append(s_name)
                
        if streets_str_list:
            streets = "; ".join(streets_str_list)
            line = f"[{district_name}] {settlement} ({time_range}): {streets}"
            raw_text_parts.append(line)
            line_to_records[line] = matching_recs
            
    # 1. Групуємо рядки за округами
    district_to_lines = {}
    for line in raw_text_parts:
        match = re.match(r"^\[(.*?)\]", line)
        dist_name = match.group(1) if match else "Невідомий округ"
        if dist_name not in district_to_lines:
            district_to_lines[dist_name] = []
        district_to_lines[dist_name].append(line)
        
    district_order = sorted(list(district_to_lines.keys()), key=lambda d: (0 if "Місто" in d or "місто" in d.lower() else 1, d))
    
    # 2. Формуємо блоки (Варіант А: Округи тримаємо разом, якщо вони не надто гігантські)
    blocks = []
    for dist in district_order:
        dist_lines = district_to_lines[dist]
        combined_text = "\n".join(dist_lines)
        
        # Збираємо всі записи для цього округу
        dist_recs = []
        for line in dist_lines:
            dist_recs.extend(line_to_records[line])
            
        if len(combined_text) <= 3000:
            blocks.append((dist, combined_text, dist_recs))
        else:
            # Якщо один округ гігантський, ріжемо його на окремі рядки-записи
            for line in dist_lines:
                blocks.append((dist, line, line_to_records[line]))
                
    # 3. Допоміжна функція оцінки довжини повідомлення
    def get_estimated_len(chunk_blocks, is_first, is_last):
        if is_first and is_last:
            header_len = 150
        elif is_first:
            header_len = 170
        else:
            header_len = 80
        footer_len = 100
        content_len = sum(len(b[1]) for b in chunk_blocks) + len(chunk_blocks)
        return header_len + content_len + footer_len
        
    # 4. Пакуємо блоки у чанки з лімітом 3950 символів
    chunks = []
    if not allow_splitting:
        chunks = [blocks]
    else:
        current_chunk = []
        for dist, text, recs in blocks:
            if not current_chunk:
                current_chunk.append((dist, text, recs))
            else:
                est_len = get_estimated_len(current_chunk + [(dist, text, recs)], is_first=(len(chunks) == 0), is_last=False)
                if est_len > 3950:
                    chunks.append(current_chunk)
                    current_chunk = [(dist, text, recs)]
                else:
                    current_chunk.append((dist, text, recs))
        if current_chunk:
            chunks.append(current_chunk)
            
    # 5. Генеруємо тексти для кожного чанку
    results = []
    total_chunks = len(chunks)
    
    for idx, chunk in enumerate(chunks):
        chunk_raw_text = "\n".join(b[1] for b in chunk)
        chunk_items = []
        for b in chunk:
            chunk_items.extend(b[2])
            
        # Унікальний ID для кожної частини
        if total_chunks == 1:
            part_msg_id = base_msg_id
        else:
            part_msg_id = f"{base_msg_id}_part{idx+1}"
            
        # Визначаємо заголовки
        if total_chunks == 1:
            if is_emergency:
                intro_phrase = f"Шановні мешканці Старокостянтинівської громади! За оперативною інформацією АТ «Хмельницькобленерго», повідомляємо про аварійні знеструмлення, зафіксовані станом на {target_date.strftime('%d.%m.%Y')}:"
            else:
                intro_phrase = f"Шановні мешканці Старокостянтинівської громади! За офіційною інформацією АТ «Хмельницькобленерго», повідомляємо про планові знеструмлення, передбачені на {target_date.strftime('%d.%m.%Y')}:"
        else:
            if is_emergency:
                if idx == 0:
                    intro_phrase = f"Шановні мешканці Старокостянтинівської громади! За оперативною інформацією АТ «Хмельницькобленерго», повідомляємо про аварійні знеструмлення, зафіксовані станом на {target_date.strftime('%d.%m.%Y')} (Частина 1 з {total_chunks}):"
                else:
                    intro_phrase = f"Продовження аварійних знеструмлень на {target_date.strftime('%d.%m.%Y')} (Частина {idx+1} з {total_chunks}):"
            else:
                if idx == 0:
                    intro_phrase = f"Шановні мешканці Старокостянтинівської громади! За офіційною інформацією АТ «Хмельницькобленерго», повідомляємо про планові знеструмлення, передбачені на {target_date.strftime('%d.%m.%Y')} (Частина 1 з {total_chunks}):"
                else:
                    intro_phrase = f"Продовження планових відключень на {target_date.strftime('%d.%m.%Y')} (Частина {idx+1} з {total_chunks}):"
                    
        # Кешування (v4: скидаємо кеш для нової логіки поділу та валідації)
        chunk_hash = hashlib.md5(f"{chunk_raw_text}_v4".encode('utf-8')).hexdigest()
        if part_msg_id in messages_dict:
            old_msg = messages_dict[part_msg_id]
            if old_msg.get("hash") == chunk_hash and old_msg.get("content"):
                print(f"[{part_msg_id}] Хеш співпадає. Використано кеш (без виклику ШІ).")
                results.append({
                    "id": part_msg_id,
                    "content": old_msg.get("content"),
                    "hash": chunk_hash,
                    "is_updated": old_msg.get("is_updated", False),
                    "updated_at": old_msg.get("updated_at", None)
                })
                continue
                
        is_updated = False
        updated_at = None
        # Позначаємо оновленнями лише сьогоднішні повідомлення (де allow_splitting=True)
        # та якщо це повідомлення вже раніше існувало в нашому кеші з іншим хешем
        if allow_splitting and part_msg_id in messages_dict:
            is_updated = True
            updated_at = get_kyiv_now().isoformat()
            
        update_prefix = ""
        if is_updated:
            now_time_str = get_kyiv_now().strftime("%H:%M")
            update_prefix = f"⚠️ УВАГА! Оновлено о {now_time_str}:\n\n"
                
        prompt = f"""Створи офіційний Telegram-пост про {typ_header} ВІДКЛЮЧЕННЯ електроенергії на {target_date.strftime('%d.%m.%Y')}.
СУВОРІ ПРАВИЛА (ІГНОРУВАННЯ ПРИЗВЕДЕ ДО ПОМИЛКИ):
1. КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати БУДЬ-ЯКІ емодзі (ніяких блискавок, крапок, кружечків, трикутників). Пост має бути виключно текстовим.
2. Пост ПОВИНЕН починатися з фрази: "{intro_phrase}"
3. Час вказуй точно так, як він переданий у сирих даних (наприклад "з 09:00 до 17:00" або "з 21 травня 21:43 до 22 травня 17:43"). Не змінюй і не спотворюй хронологію.
4. Офіційний, діловий тон, але привабливе і зрозуміле структурування. Використовуй звичайні дефіси "-" для маркованих списків.
5. ЗГРУПУЙ населені пункти за округами (СО), які вказані в квадратних дужках. Спочатку має йти Місто Старокостянтинів, потім інші округи.
6. В кінці додай коротке: "Просимо завчасно зарядити пристрої та з розумінням поставитись до тимчасових незручностей."
7. КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати слово "частково" або "(частково)" для будь-яких вулиць. Також КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати круглі дужки навколо будинків. Виводь повні списки будинків відразу після слова "буд." без дужок, точно так, як вказано в сирих даних (наприклад, "буд. 1, 2, 3, 4, 5").

Сирі дані для обробки:
{chunk_raw_text}
"""
        print(f"Генерую Telegram-пост {part_msg_id} (ШІ)...")
        global ai_called
        ai_called = True
        ai_result = generate_with_validation(prompt, chunk_items)
        if ai_result:
            final_content = update_prefix + ai_result
            results.append({
                "id": part_msg_id, 
                "content": final_content, 
                "hash": chunk_hash,
                "is_updated": is_updated,
                "updated_at": updated_at
            })
        else:
            print(f"[WARN] ШІ недоступний для {part_msg_id}. Використовую резервний шаблон.")
            global warnings_list
            warnings_list.append(f"ШІ недоступний для {part_msg_id}")
            fallback_text = intro_phrase + "\n\n" + chunk_raw_text + "\n\nПросимо завчасно зарядити пристрої та з розумінням поставитись до тимчасових незручностей."
            final_content = update_prefix + fallback_text
            results.append({
                "id": part_msg_id, 
                "content": final_content, 
                "hash": chunk_hash,
                "is_updated": is_updated,
                "updated_at": updated_at
            })
            
    return results

if __name__ == "__main__":
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    today_planned_posts = get_tg_post(items_today, today, False, f"{today_str}_tg_planned", allow_splitting=True)
    today_emergency_posts = get_tg_post(items_today, today, True, f"{today_str}_tg_emergency", allow_splitting=True)
    tomorrow_planned_posts = get_tg_post(items_tomorrow, tomorrow, False, f"{tomorrow_str}_tg_planned", allow_splitting=False)
    tomorrow_emergency_posts = get_tg_post(items_tomorrow, tomorrow, True, f"{tomorrow_str}_tg_emergency", allow_splitting=False)

    # ------------------------------------------------------------
    # Збереження messages.json
    # ------------------------------------------------------------
    posts_to_add = []
    posts_to_add.append((f"{today_str}_feed", today_str, "feed_today", feed_today_content, None, False, None))
    posts_to_add.append((f"{tomorrow_str}_feed", tomorrow_str, "feed_tomorrow", feed_tomorrow_content, None, False, None))

    for post in today_planned_posts:
        posts_to_add.append((post["id"], today_str, "tg_planned", post["content"], post["hash"], post.get("is_updated", False), post.get("updated_at")))
    for post in today_emergency_posts:
        posts_to_add.append((post["id"], today_str, "tg_emergency", post["content"], post["hash"], post.get("is_updated", False), post.get("updated_at")))
    for post in tomorrow_planned_posts:
        posts_to_add.append((post["id"], tomorrow_str, "tg_planned", post["content"], post["hash"], post.get("is_updated", False), post.get("updated_at")))
    for post in tomorrow_emergency_posts:
        posts_to_add.append((post["id"], tomorrow_str, "tg_emergency", post["content"], post["hash"], post.get("is_updated", False), post.get("updated_at")))

    current_post_ids = {p[0] for p in posts_to_add}

    # Видаляємо лише застарілі частини сьогодні/завтра, яких більше немає в поточному запуску
    keys_to_delete = [
        k for k in messages_dict.keys() 
        if (k.startswith(today_str) or k.startswith(tomorrow_str)) and k not in current_post_ids
    ]
    for k in keys_to_delete:
        del messages_dict[k]

    # Зберігаємо та оновлюємо
    for p_id, p_date, p_type, p_content, p_hash, is_upd, upd_at in posts_to_add:
        add_message(p_id, p_date, p_type, p_content, p_hash, is_updated=is_upd, updated_at=upd_at)

    # Garbage Collection: Видаляємо старі повідомлення (>40 днів)
    cutoff_date = get_kyiv_now() - timedelta(days=40)
    filtered_messages = []
    for m in messages_dict.values():
        try:
            dt = datetime.strptime(m["date"], "%Y-%m-%d")
            if dt >= cutoff_date:
                filtered_messages.append(m)
        except:
            filtered_messages.append(m) # Якщо дата не розпізнана

    final_messages = sorted(filtered_messages, key=lambda x: x["date"], reverse=True)

    messages_path = os.getenv("MESSAGES_PATH", "data/messages.json")
    with open(messages_path, "w", encoding="utf-8") as f:
        json.dump(final_messages, f, ensure_ascii=False, indent=2)
    print("[SUCCESS] messages.json збережено")

    # ------------------------------------------------------------
    # Оновлення auth_config.js
    # ------------------------------------------------------------
    if ADMIN_PASSWORD:
        hash_hex = hashlib.sha256(ADMIN_PASSWORD.encode("utf-8")).hexdigest()
        with open("auth_config.js", "w", encoding="utf-8") as f:
            f.write(f'const ADMIN_HASH = "{hash_hex}";\n')
        print("[SUCCESS] auth_config.js оновлено")
    else:
        print("[WARN] ADMIN_PASSWORD не знайдено у .env")

    # ------------------------------------------------------------
    # Автоматичний запуск Щотижневої Аналітики
    # ------------------------------------------------------------
    now = get_kyiv_now()
    if now.weekday() == 0:
        try:
            with open("data/analytics.json", "r", encoding="utf-8") as f:
                last_date_str = json.load(f).get("date", "2000-01-01 00:00")
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M").date()
        except Exception:
            last_date = None
            
        if last_date != now.date():
            print("Понеділок - Запуск Щотижневої Аналітики...")
        try:
            import analytics
            analytics.generate_weekly_report()
        except Exception as e:
            print(f"Помилка при запуску аналітики: {e}")
            warnings_list.append(f"Помилка аналітики: {e}")

    # ------------------------------------------------------------
    # Запис фінального статусу в update_log.json
    # ------------------------------------------------------------
    status = "warning" if warnings_list else "ok"
    msg_parts = ["Форматування успішно завершено."]
    if not ai_called:
        msg_parts.append("Змін не виявлено, використано кеш.")
    if warnings_list:
        msg_parts.append("Попередження: " + "; ".join(warnings_list))
    update_latest_log(status=status, message_append=" ".join(msg_parts))