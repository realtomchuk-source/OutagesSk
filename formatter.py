import json
import os
import requests
from datetime import datetime, timedelta, time
from dotenv import load_dotenv
import hashlib
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
    print("❌ Жодного API-ключа не знайдено в .env (GEMINI_API_KEY або OPENROUTER_API_KEY)")
    exit(1)

GOOGLE_MODEL = "gemini-2.0-flash"
OPENROUTER_MODEL = "google/gemini-2.0-flash-001"

# ------------------------------------------------------------
# Завантаження даних
# ------------------------------------------------------------
with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
    outages = json.load(f)

with open("data/districts.json", "r", encoding="utf-8") as f:
    districts = json.load(f)

# ------------------------------------------------------------
# Допоміжні функції
# ------------------------------------------------------------
def fix_datetime(dt_string):
    if len(dt_string) >= 5:
        return f"{dt_string[:-5]} {dt_string[-5:]}"
    return dt_string

def parse_datetime(dt_string):
    fixed = fix_datetime(dt_string)
    try:
        return datetime.strptime(fixed, "%d.%m.%Y %H:%M")
    except:
        return None

def is_active_on_date(record, target_date):
    start = parse_datetime(record["start_datetime"])
    end = parse_datetime(record["end_datetime"])
    if not start or not end:
        return False
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)
    return start <= day_end and end >= day_start

def get_district(settlement):
    if settlement == "Старокостянтинів":
        return None
    for d_name, villages in districts.items():
        if settlement in villages:
            return d_name
    return None

# ------------------------------------------------------------
# Функція виклику ШІ (з fallback)
# ------------------------------------------------------------
def ask_ai(prompt):
    if HAS_GOOGLE_AI and GOOGLE_API_KEY:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel(GOOGLE_MODEL)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"⚠️ Помилка Google AI: {e}")
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
                print(f"❌ OpenRouter помилка {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"❌ OpenRouter виклик не вдався: {e}")
    else:
        print("❌ OpenRouter ключ відсутній.")
    return None

# ------------------------------------------------------------
# Підготовка дат
# ------------------------------------------------------------
today = datetime.now().date()
tomorrow = today + timedelta(days=1)

# ------------------------------------------------------------
# Генерація стрічки
# ------------------------------------------------------------
feed_items = [rec for rec in outages if is_active_on_date(rec, today) or is_active_on_date(rec, tomorrow)]

def generate_with_validation(prompt, items, max_retries=2):
    """Викликає ШІ та перевіряє, чи не загубилися вулиці"""
    for attempt in range(max_retries + 1):
        content = ask_ai(prompt)
        if not content:
            return None
        
        missing_streets = []
        for rec in items:
            for street in rec["streets"]:
                if street not in content:
                    missing_streets.append(street)
        
        if not missing_streets:
            return content
            
        print(f"⚠️ Спроба {attempt + 1}: ШІ загубив вулиці ({', '.join(missing_streets)}). Повторюю генерацію...")
    
    print("❌ ШІ не зміг згенерувати повний список без втрат після всіх спроб.")
    return content + "\n\n<p style='color:red;'>⚠️ УВАГА: Можливо, ШІ переніс не всі вулиці. Перевірте джерело.</p>"

def describe_outages(items):
    """Формує ТІЛЬКИ факти без географічних припущень, з розумним групуванням"""
    if not items:
        return "відключень немає"
        
    # Групування: ключ = (місто/село, округ, тип, початок, кінець)
    grouped = {}
    for rec in items:
        settlement = rec["settlement"]
        district = get_district(settlement)
        typ = "Аварійне" if "Аварійні" in rec['type'] else "Планове"
        start = fix_datetime(rec["start_datetime"])
        end = fix_datetime(rec["end_datetime"])
        
        key = (settlement, district, typ, start, end)
        if key not in grouped:
            grouped[key] = []
        
        if rec["streets"]:
            grouped[key].extend(rec["streets"])
            
    # Сортування: спочатку Старокостянтинів, потім округи та села за алфавітом
    def sort_key(k):
        settlement, district, typ, start, end = k
        is_city = 0 if settlement == "Старокостянтинів" else 1
        dist_str = district if district else ""
        return (is_city, dist_str, settlement, start)
        
    sorted_keys = sorted(grouped.keys(), key=sort_key)
    
    lines = []
    for k in sorted_keys:
        settlement, district, typ, start, end = k
        streets_list = grouped[k]
        
        # Прибираємо дублікати вулиць і сортуємо їх за алфавітом
        unique_streets = sorted(list(set(streets_list)))
        streets_str = ", ".join(unique_streets) if unique_streets else "невідомо"
        
        if settlement == "Старокостянтинів":
            loc = "МІСТО Старокостянтинів"
        elif district:
            loc = f"СЕЛО {settlement} (округ: {district})"
        else:
            loc = f"СЕЛО {settlement}"
            
        lines.append(f"{typ}: {loc}, з {start} до {end}, вулиці: {streets_str}")
        
    return "\n".join(lines)

feed_prompt = f"""
Згенеруй HTML-код для публікації на сайті громади. Суворо дотримуйся правил:
- ТІЛЬКИ чистий HTML (без "```html" на початку, без лапок зовні).
- Другий заголовок: "⚡ Відключення на сьогодні та завтра".
- Дві секції: "Сьогодні, {today.strftime('%d.%m.%Y')}" та "Завтра, {tomorrow.strftime('%d.%m.%Y')}".
- Всередині кожної секції спочатку йде МІСТО Старокостянтинів (з 🏙️), потім села, згруповані за округами (🔸). Ніяких інших підрозділів (районів, мікрорайонів) не створюй.
- **Категорично заборонено** вигадувати будь-які додаткові географічні об'єкти, райони чи мікрорайони, яких немає у вхідних даних.
- Для кожного запису ОБОВ'ЯЗКОВО вказуй час: "з 09:00 до 17:00". Якщо час однаковий для кількох вулиць, вкажи його на початку групи.
- Для аварійних додай "🔴", для планових – "🟡".
- Обов'язково виділяй тип відключення та ПОВНИЙ час за допомогою HTML-класів. Ніколи не видаляй час початку (слово "з"), навіть якщо відключення почалося вчора! Формат:
  <li><span class="type-emergency">🔴 Аварійне (з 10.05 21:12 до 11.05 15:30)</span> - перелік вулиць...</li>
  <li><span class="type-planned">🟡 Планове (з 09:00 до 17:00)</span> - перелік вулиць...</li>
- Якщо на день відключень немає – "✅ Відключення не зафіксовані.".
- Використовуй HTML: <h3>, <h4>, <ul>, <li>, <strong>.
- Використовуй HTML: <h3>, <h4>, <ul>, <li>, <strong>, <span>.

Ось точний перелік адрес (МІСТО або СЕЛО вказано явно):
{describe_outages(feed_items)}
"""

print("Генерую стрічку...")
feed_html = generate_with_validation(feed_prompt, feed_items)
if feed_html:
    if feed_html.startswith("```html"):
        feed_html = feed_html[7:]
    if feed_html.endswith("```"):
        feed_html = feed_html[:-3]
    feed_html = feed_html.strip()
    with open("feed.html", "w", encoding="utf-8") as f:
        f.write(feed_html)
    print("✅ feed.html збережено")
else:
    print("❌ Не вдалося згенерувати стрічку")

# ------------------------------------------------------------
# Генерація Telegram-постів
# ------------------------------------------------------------
tomorrow_items = [rec for rec in outages if is_active_on_date(rec, tomorrow)]
if tomorrow_items:
    tg_text = describe_outages(tomorrow_items)
    tg_prompt = f"""
Створи інформативний та солідний Telegram-пост про відключення електроенергії на завтра ({tomorrow.strftime('%d.%m.%Y')}).
Вимоги:
- Тільки текст посту (без вступних слів, без лапок).
- Офіційний та ввічливий тон (почни з "⚡️ До уваги мешканців Старокостянтинівської громади! Інформація щодо відключень на {tomorrow.strftime('%d.%m.%Y')}").
- Спочатку подай інформацію по місту Старокостянтинів, потім по селах (згрупуй за округами).
- **Категорично заборонено** вигадувати будь-які додаткові географічні об'єкти, райони чи мікрорайони, яких немає у вхідних даних.
- Для кожного запису **обов'язково** вказуй тип та ПОВНИЙ час (від і до) великими літерами і жирним шрифтом. Ніколи не відкидай час початку, навіть якщо він був учора! (наприклад: **🔴 АВАРІЙНЕ ВІДКЛЮЧЕННЯ (з 10.05 21:12 до 11.05 15:30)** або **🟡 ПЛАНОВІ РОБОТИ (з 09:00 до 17:00)**).
- Емодзі використовуй стримано, лише для структурування тексту (наприклад, 📍 для населених пунктів). Вони не повинні перевантажувати текст.
- Вулиці перераховуй через кому звичайним шрифтом, чітко і зрозуміло.
- Наприкінці додай коротке ввічливе завершення (наприклад, "Дякуємо за розуміння. Бережіть себе та свої прилади!").
- Якщо відключень немає – напиши коротке офіційне повідомлення, що на цей день відключень не заплановано.

Ось точний перелік адрес (МІСТО або СЕЛО вказано явно):
{tg_text}
"""
    print("Генерую Telegram-пост на завтра...")
    tg_content = generate_with_validation(tg_prompt, tomorrow_items)
    if "<p style" in tg_content:  # Видаляємо HTML попередження для Telegram
        tg_content = tg_content.split("\n\n<p style") + "\n\n⚠️ УВАГА: Можливо, ШІ переніс не всі вулиці."
else:
    tg_content = f"🔕 На {tomorrow.strftime('%d.%m.%Y')} відключення не заплановані."

# ------------------------------------------------------------
# Збереження messages.json (Upsert + Очищення > 30 днів)
# ------------------------------------------------------------
try:
    with open("data/messages.json", "r", encoding="utf-8") as f:
        existing_messages = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    existing_messages = []

# Конвертуємо у словник по ID для легкого оновлення (Upsert)
messages_dict = {m["id"]: m for m in existing_messages}

if feed_html:
    feed_id = f"{today.strftime('%Y-%m-%d')}_feed"
    messages_dict[feed_id] = {
        "id": feed_id,
        "date": today.strftime("%Y-%m-%d"),
        "type": "feed",
        "target": None,
        "content": feed_html,
        "created_at": datetime.now().isoformat()
    }

if tg_content:
    tg_id = f"{tomorrow.strftime('%Y-%m-%d')}_tg"
    messages_dict[tg_id] = {
        "id": tg_id,
        "date": tomorrow.strftime("%Y-%m-%d"),
        "type": "telegram_post",
        "target": None,
        "content": tg_content,
        "created_at": datetime.now().isoformat()
    }

# Фільтруємо старі повідомлення (Garbage Collection 7 днів)
cutoff_date = datetime.now() - timedelta(days=7)
final_messages = []

for m in messages_dict.values():
    try:
        m_date = datetime.fromisoformat(m["created_at"])
        if m_date >= cutoff_date:
            final_messages.append(m)
    except ValueError:
        final_messages.append(m)  # Якщо дата пошкоджена, залишаємо

# Зберігаємо результат
final_messages.sort(key=lambda x: x["date"], reverse=True) # Сортуємо від нових до старих

with open("data/messages.json", "w", encoding="utf-8") as f:
    json.dump(final_messages, f, ensure_ascii=False, indent=2)
print("✅ messages.json збережено")

# ------------------------------------------------------------
# Оновлення admin.html (вставка хешу пароля)
# ------------------------------------------------------------
if ADMIN_PASSWORD:
    try:
        with open("admin.html", "r", encoding="utf-8") as f:
            admin_html = f.read()
        # Обчислюємо SHA-256 хеш
        hash_hex = hashlib.sha256(ADMIN_PASSWORD.encode("utf-8")).hexdigest()
        # Замінюємо маркер, або будь-який існуючий хеш за допомогою регулярного виразу
        admin_html = admin_html.replace("__ADMIN_HASH__", hash_hex)
        admin_html = re.sub(r'const ADMIN_HASH = ".*?";', f'const ADMIN_HASH = "{hash_hex}";', admin_html)
        with open("admin.html", "w", encoding="utf-8") as f:
            f.write(admin_html)
        print("✅ admin.html оновлено (хеш пароля вставлено)")
    except FileNotFoundError:
        print("⚠️ admin.html не знайдено, хеш не вставлено")
else:
    print("⚠️ ADMIN_PASSWORD не знайдено у .env, admin.html не оновлено")