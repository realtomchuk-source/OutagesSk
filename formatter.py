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
OPENROUTER_MODEL = "google/gemini-2.0-flash-001"

# ------------------------------------------------------------
# Завантаження даних
# ------------------------------------------------------------
try:
    with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
        outages = json.load(f)
except FileNotFoundError:
    outages = []

# ------------------------------------------------------------
# Телеметрія змін (Smart Monitor)
# ------------------------------------------------------------
has_cardinal_changes = True
try:
    with open("data/previous_snapshot.json", "r", encoding="utf-8") as f:
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
        log_entry = {"time": datetime.now().isoformat(), "msg": "Detected changes in outages_snapshot"}
        try:
            with open("data/changelog.json", "r", encoding="utf-8") as clog:
                changelog = json.load(clog)
        except (FileNotFoundError, json.JSONDecodeError):
            changelog = []
        changelog.append(log_entry)
        with open("data/changelog.json", "w", encoding="utf-8") as clog:
            json.dump(changelog, clog, ensure_ascii=False, indent=2)

except FileNotFoundError:
    print("[TELEMETRY] Немає previous_snapshot.json, створюємо.")

# Зберігаємо поточний снепшот як попередній для наступного запуску
with open("data/previous_snapshot.json", "w", encoding="utf-8") as f:
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

# ------------------------------------------------------------
# Функція виклику ШІ
# ------------------------------------------------------------
def ask_ai(prompt):
    if HAS_GOOGLE_AI and GOOGLE_API_KEY:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(GOOGLE_MODEL)
            response = model.generate_content(prompt)
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
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"[ERROR] OpenRouter помилка {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[ERROR] OpenRouter виклик не вдався: {e}")
    return None

def generate_with_validation(prompt, items, max_retries=2):
    for attempt in range(max_retries + 1):
        content = ask_ai(prompt)
        if not content:
            return None
        
        missing_streets = []
        for rec in items:
            for street in rec.get("streets", []):
                if street not in content:
                    missing_streets.append(street)
        
        if not missing_streets:
            return content
            
        print(f"[WARN] Спроба {attempt + 1}: ШІ загубив вулиці ({', '.join(missing_streets)}). Повторюю генерацію...")
    
    print("[ERROR] ШІ не зміг згенерувати повний список без втрат після всіх спроб.")
    return content + "\n\n[УВАГА] Можливо, ШІ переніс не всі вулиці. Перевірте джерело."

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
def generate_feed_text(items, label):
    if not items:
        return f"[{label}] Відключення не зафіксовані."
        
    # Групування: ключ = (Тип, Місто, Час)
    # Значення = список очищених назв вулиць з будинками
    grouped = {}
    for rec in items:
        settlement = rec.get("settlement", "Невідомо")
        typ = "Аварійні" if "Аварійні" in rec.get("type", "") else "Планові"
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
                if name not in grouped[key]:
                    grouped[key][name] = set()
            
    # Сортування
    sorted_keys = sorted(grouped.keys(), key=lambda k: (0 if k[0] == "Аварійні" else 1, 0 if k[1] == "Старокостянтинів" else 1, k[1], k[2]))
    
    parts = []
    for k in sorted_keys:
        typ, settlement, time_range = k
        streets_dict = grouped[k]
        
        street_parts = []
        for s_name in sorted(streets_dict.keys()):
            houses_set = streets_dict[s_name]
            if houses_set:
                sorted_houses = sorted(list(houses_set), key=lambda x: (int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 9999, x))
                if len(sorted_houses) <= 5:
                    street_parts.append(f"{s_name} ({', '.join(sorted_houses)})")
                else:
                    street_parts.append(f"{s_name} (частково)")
            else:
                street_parts.append(s_name)
                
        if street_parts:
            streets_str = "; ".join(street_parts)
            parts.append(f"{typ}: {settlement} ({time_range}): {streets_str}")
            
    return f"[{label}] " + " | ".join(parts) if parts else f"[{label}] Відключення не зафіксовані."

# ------------------------------------------------------------
# Підготовка дат
# ------------------------------------------------------------
today = datetime.now().date()
tomorrow = today + timedelta(days=1)

# Фільтруємо дані для Telegram-постів
items_today = [r for r in outages if is_active_on_date(r, today)]
items_tomorrow = [r for r in outages if is_active_on_date(r, tomorrow)]

# ------------------------------------------------------------
# Робота з data/feed.json (Динамічна стрічка та тижнева сітка)
# ------------------------------------------------------------
FEED_PATH = "data/feed.json"

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
current_time_str = datetime.now().strftime("%H:%M")

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
    
    if existing_day:
        history = existing_day.get("history", [])
        last_version = history[-1]["content"] if history else ""
        
        # Порівнюємо контент без мітки оновлення (Оновлено о ...)
        clean_last = re.sub(r"\s*\(Оновлено о \d{2}:\d{2}\)", "", last_version)
        clean_new = re.sub(r"\s*\(Оновлено о \d{2}:\d{2}\)", "", new_text)
        
        if clean_last != clean_new:
            # Зміна контенту протягом доби є аномалією
            marked_text = f"{new_text} (Оновлено о {current_time_str})"
            history.append({
                "timestamp": datetime.now().isoformat(),
                "content": marked_text,
                "is_anomaly": True
            })
            feed_data["anomalies_log"].append({
                "date": date_str,
                "timestamp": datetime.now().isoformat(),
                "old_text": last_version,
                "new_text": marked_text
            })
            planned_content = existing_day.get("planned_content", clean_new)
            actual_content = marked_text
        else:
            planned_content = existing_day.get("planned_content", clean_new)
            actual_content = last_version
            
        new_days.append({
            "date": date_str,
            "planned_content": planned_content,
            "actual_content": actual_content,
            "history": history
        })
    else:
        new_days.append({
            "date": date_str,
            "planned_content": new_text,
            "actual_content": new_text,
            "history": [{
                "timestamp": datetime.now().isoformat(),
                "content": new_text,
                "is_anomaly": False
            }]
        })

feed_data["days"] = new_days

# Формуємо поточну стрічку (актуальну на тепер, очищену від [СЬОГОДНІ])
today_day = next((d for d in new_days if d["date"] == today.strftime("%Y-%m-%d")), None)
tomorrow_day = next((d for d in new_days if d["date"] == tomorrow.strftime("%Y-%m-%d")), None)

current_parts = []
if today_day and today_day["actual_content"]:
    clean_today = re.sub(r"^\[СЬОГОДНІ\]\s*", "", today_day["actual_content"])
    current_parts.append(clean_today)
if tomorrow_day and tomorrow_day["actual_content"]:
    current_parts.append(tomorrow_day["actual_content"])

feed_data["current_feed"] = " | ".join(current_parts) if current_parts else "Відключення не зафіксовані."
feed_data["last_updated"] = datetime.now().isoformat()

# Очищення історії (зберігаємо за останні 60 днів)
cutoff_dt = datetime.now() - timedelta(days=60)
feed_data["days"] = [d for d in feed_data["days"] if datetime.strptime(d["date"], "%Y-%m-%d") >= cutoff_dt.replace(hour=0, minute=0, second=0, microsecond=0)]
feed_data["anomalies_log"] = [a for a in feed_data["anomalies_log"] if datetime.fromisoformat(a["timestamp"]) >= cutoff_dt]

# Зберігаємо структурований JSON
with open(FEED_PATH, "w", encoding="utf-8") as f:
    json.dump(feed_data, f, ensure_ascii=False, indent=2)
print("[SUCCESS] feed.json збережено")

# Зберігаємо чистий плоский текст у feed.txt для іншого додатка
with open("data/feed.txt", "w", encoding="utf-8") as txt_f:
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
feed_tomorrow_content = " | ".join(feed_tomorrow_parts) if feed_tomorrow_parts else "[ЗАВТРА] Відключення не зафіксовані."

# ------------------------------------------------------------
# Завантаження messages.json для Кешування
# ------------------------------------------------------------
try:
    with open("data/messages.json", "r", encoding="utf-8") as f:
        existing_messages = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    existing_messages = []

messages_dict = {m["id"]: m for m in existing_messages}

def add_message(m_id, m_date, m_type, m_content, m_hash=None):
    if m_content:
        messages_dict[m_id] = {
            "id": m_id,
            "date": m_date,
            "type": m_type,
            "content": m_content,
            "hash": m_hash,
            "created_at": datetime.now().isoformat()
        }

# ------------------------------------------------------------
# Генерація Telegram-постів (з ШІ)
# ------------------------------------------------------------
def get_tg_post(items, target_date, is_emergency, msg_id):
    typ_str = "Аварійні" if is_emergency else "Планові"
    typ_header = "АВАРІЙНИХ" if is_emergency else "ПЛАНОВИХ"
    
    filtered = [r for r in items if (is_emergency and "Аварійні" in r.get("type", "")) or (not is_emergency and "Планові" in r.get("type", ""))]
    
    if not filtered:
        if is_emergency:
            return f"Шановні мешканці Старокостянтинівської громади! За оперативною інформацією АТ «Хмельницькобленерго», повідомляємо про аварійні знеструмлення.\n\nНа {target_date.strftime('%d.%m.%Y')} аварійних знеструмлень не зафіксовано.", "no_outages"
        else:
            return f"Шановні мешканці Старокостянтинівської громади! За офіційною інформацією АТ «Хмельницькобленерго», повідомляємо про планові знеструмлення.\n\nНа {target_date.strftime('%d.%m.%Y')} планових знеструмлень не передбачено.", "no_outages"

    raw_text_parts = []
    for rec in filtered:
        time_range = extract_time_range(rec)
        settlement = rec.get("settlement", "")
        
        district_name = ""
        if settlement != "Старокостянтинів":
            district_name = districts.get(settlement, "Невідомий")
        else:
            district_name = "Місто Старокостянтинів"
            
        streets_str_list = []
        for s_det in rec.get("streets_detailed", []):
            name = s_det.get("name", "")
            houses = s_det.get("houses", "").strip()
            if not houses:
                streets_str_list.append(name)
            else:
                house_list = [h.strip() for h in houses.split(",") if h.strip()]
                if len(house_list) <= 5:
                    streets_str_list.append(f"{name} (буд. {', '.join(house_list)})")
                else:
                    streets_str_list.append(f"{name} (частково)")
                    
        if not streets_str_list:
            streets_str_list = rec.get("streets", [])
            
        streets = "; ".join(streets_str_list)
        raw_text_parts.append(f"[{district_name}] {settlement} ({time_range}): {streets}")
        
    raw_text = "\n".join(raw_text_parts)
    
    
    # Кешування
    text_hash = hashlib.md5(raw_text.encode('utf-8')).hexdigest()
    if msg_id in messages_dict:
        old_msg = messages_dict[msg_id]
        if old_msg.get("hash") == text_hash and old_msg.get("content"):
            print(f"[{msg_id}] Хеш співпадає. Використано кеш (без виклику ШІ).")
            return old_msg.get("content"), text_hash

    if is_emergency:
        intro_phrase = f"Шановні мешканці Старокостянтинівської громади! За оперативною інформацією АТ «Хмельницькобленерго», повідомляємо про аварійні знеструмлення, зафіксовані станом на {target_date.strftime('%d.%m.%Y')}:"
    else:
        intro_phrase = f"Шановні мешканці Старокостянтинівської громади! За офіційною інформацією АТ «Хмельницькобленерго», повідомляємо про планові знеструмлення, передбачені на {target_date.strftime('%d.%m.%Y')}:"

    prompt = f"""Створи офіційний Telegram-пост про {typ_header} ВІДКЛЮЧЕННЯ електроенергії на {target_date.strftime('%d.%m.%Y')}.
СУВОРІ ПРАВИЛА (ІГНОРУВАННЯ ПРИЗВЕДЕ ДО ПОМИЛКИ):
1. КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати БУДЬ-ЯКІ емодзі (ніяких блискавок, крапок, кружечків, трикутників). Пост має бути виключно текстовим.
2. Пост ПОВИНЕН починатися з фрази: "{intro_phrase}"
3. Час вказуй точно так, як він переданий у сирих даних (наприклад "з 09:00 до 17:00" або "з 21 травня 21:43 до 22 травня 17:43"). Не змінюй і не спотворюй хронологію.
4. Офіційний, діловий тон, але привабливе і зрозуміле структурування. Використовуй звичайні дефіси "-" для маркованих списків.
5. ЗГРУПУЙ населені пункти за округами (СО), які вказані в квадратних дужках. Спочатку має йти Місто Старокостянтинів, потім інші округи.
6. В кінці додай коротке: "Просимо завчасно зарядити пристрої та з розумінням поставитись до тимчасових незручностей."

Сирі дані для обробки:
{raw_text}
"""
    print(f"Генерую Telegram-пост (ШІ): {typ_str} на {target_date.strftime('%d.%m.%Y')}...")
    ai_result = generate_with_validation(prompt, filtered)
    if ai_result:
        return ai_result, text_hash
    else:
        print(f"[WARN] ШІ недоступний (ліміти або помилка). Використовую резервний шаблон для {typ_str}.")
        fallback_text = intro_phrase + "\n\n" + raw_text + "\n\nПросимо завчасно зарядити пристрої та з розумінням поставитись до тимчасових незручностей."
        return fallback_text, text_hash

today_str = today.strftime("%Y-%m-%d")
tomorrow_str = tomorrow.strftime("%Y-%m-%d")

tg_today_planned, hash_tp = get_tg_post(items_today, today, False, f"{today_str}_tg_planned")
tg_today_emergency, hash_te = get_tg_post(items_today, today, True, f"{today_str}_tg_emergency")
tg_tomorrow_planned, hash_tmp = get_tg_post(items_tomorrow, tomorrow, False, f"{tomorrow_str}_tg_planned")
tg_tomorrow_emergency, hash_tme = get_tg_post(items_tomorrow, tomorrow, True, f"{tomorrow_str}_tg_emergency")

# ------------------------------------------------------------
# Збереження messages.json
# ------------------------------------------------------------
add_message(f"{today_str}_feed", today_str, "feed_today", feed_today_content)
add_message(f"{tomorrow_str}_feed", tomorrow_str, "feed_tomorrow", feed_tomorrow_content)

add_message(f"{today_str}_tg_planned", today_str, "tg_planned", tg_today_planned, hash_tp)
add_message(f"{today_str}_tg_emergency", today_str, "tg_emergency", tg_today_emergency, hash_te)
add_message(f"{tomorrow_str}_tg_planned", tomorrow_str, "tg_planned", tg_tomorrow_planned, hash_tmp)
add_message(f"{tomorrow_str}_tg_emergency", tomorrow_str, "tg_emergency", tg_tomorrow_emergency, hash_tme)

# Garbage Collection: Видаляємо старі повідомлення (>40 днів)
cutoff_date = datetime.now() - timedelta(days=40)
filtered_messages = []
for m in messages_dict.values():
    try:
        dt = datetime.strptime(m["date"], "%Y-%m-%d")
        if dt >= cutoff_date:
            filtered_messages.append(m)
    except:
        filtered_messages.append(m) # Якщо дата не розпізнана

final_messages = sorted(filtered_messages, key=lambda x: x["date"], reverse=True)

with open("data/messages.json", "w", encoding="utf-8") as f:
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
now = datetime.now()
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