import json
import os
import sys
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv

# Завантажуємо змінні оточення з .env
load_dotenv()

# Фікс для Windows консолі
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def generate_weekly_report():
    print("Збір даних для щотижневої аналітики...")
    
    # 1. Читаємо архів
    archive_path = "data/archive.json"
    try:
        with open(archive_path, "r", encoding="utf-8") as f:
            archive = json.load(f)
    except FileNotFoundError:
        print("Архів порожній або не знайдено.")
        return
        
    # 2. Фільтруємо за останні 7 днів
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    
    weekly_records = []
    for rec in archive:
        # Виключаємо "Пісочницю" з щотижневої аналітики
        if rec.get("settlement") == "Пісочниця":
            continue
        start_str = rec.get("start_datetime", "")
        if len(start_str) >= 5 and not " " in start_str[-6:]:
            start_str = f"{start_str[:-5]} {start_str[-5:]}"
            
        try:
            dt = datetime.strptime(start_str, "%d.%m.%Y %H:%M")
            if dt >= seven_days_ago and dt <= now:
                weekly_records.append(rec)
        except ValueError:
            pass

    if not weekly_records:
        print("За останні 7 днів відключень не зафіксовано.")
        save_report("За минулий тиждень відключень електроенергії в громаді не зафіксовано. Дякуємо енергетикам за стабільну роботу!")
        return

    # 3. Вираховуємо статистику (щоб ШІ не галюцинував)
    total_outages = len(weekly_records)
    emergency_count = sum(1 for r in weekly_records if "Аварійні" in r.get("type", ""))
    planned_count = sum(1 for r in weekly_records if "Планові" in r.get("type", ""))
    
    settlement_counts = {}
    total_hours = 0.0
    
    for rec in weekly_records:
        s = rec.get("settlement", "Невідомо")
        settlement_counts[s] = settlement_counts.get(s, 0) + 1
        
        # Рахуємо тривалість
        st = rec.get("start_datetime", "")
        en = rec.get("end_datetime", "")
        if len(st) >= 5 and not " " in st[-6:]: st = f"{st[:-5]} {st[-5:]}"
        if len(en) >= 5 and not " " in en[-6:]: en = f"{en[:-5]} {en[-5:]}"
        try:
            dt_start = datetime.strptime(st, "%d.%m.%Y %H:%M")
            dt_end = datetime.strptime(en, "%d.%m.%Y %H:%M")
            if dt_end > dt_start:
                total_hours += (dt_end - dt_start).total_seconds() / 3600.0
        except:
            pass

    # Сортуємо топ-постраждалих
    top_settlements = sorted(settlement_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_str = ", ".join([f"{k} ({v} відключень)" for k, v in top_settlements])

    stats_text = f"""ТОЧНА СТАТИСТИКА ЗА ТИЖДЕНЬ:
Всього відключень: {total_outages}
З них аварійних: {emergency_count}
З них планових: {planned_count}
Загальна тривалість усіх відключень: {round(total_hours, 1)} годин
Найбільше постраждали населені пункти: {top_str}
"""

    print("Статистика для ШІ:")
    print(stats_text)

    # 4. Відправляємо до Gemini
    API_KEY = os.environ.get("GEMINI_API_KEY")
    if not API_KEY:
        print("Помилка: GEMINI_API_KEY не знайдено.")
        save_report("Помилка генерації звіту: відсутній API ключ ШІ.")
        return

    genai.configure(api_key=API_KEY)
    
    prompt = f"""Напиши офіційне, але емпатичне щотижневе аналітичне зведення для Telegram-каналу громади.
Використовуй ЛИШЕ ці математично точні дані, не вигадуй жодних цифр:
{stats_text}

Правила:
1. Ніяких емодзі. 
2. Зроби гарний заголовок "Аналітичне зведення за тиждень", а також обов'язково розпочни текст із фрази: "Шановні мешканці Старокостянтинівської громади!"
3. Коротко підбий підсумки (яких відключень було більше, де було найважче).
4. Офіційний, діловий стиль.
5. В кінці подякуй мешканцям за терпіння.
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        report_text = response.text.strip()
        print("Звіт згенеровано успішно.")
        save_report(report_text)
    except Exception as e:
        print(f"Помилка ШІ: {e}")
        save_report("Вибачте, сталася помилка при генерації щотижневого звіту.")

def save_report(text):
    report_data = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": text
    }
    with open("data/analytics.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print("Збережено в data/analytics.json")

if __name__ == "__main__":
    generate_weekly_report()
