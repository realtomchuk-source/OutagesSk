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

def normalize_settlement_name(settlement):
    if not settlement:
        return "Невідомо"
    s = settlement.strip()
    if s in ["Старокостянтинів", "м. Старокостянтинів"]:
        return "м. Старокостянтинів"
    if s == "Пісочниця" or s == "Невідомо":
        return s
    if s.startswith("с. "):
        return s
    return "с. " + s

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
        save_report("За минулий тиждень відключень електроенергії в громаді не зафіксовано. Дякуємо енергетикам за стабільну роботу!", {})
        return

    # 3. Вираховуємо статистику (щоб ШІ не галюцинував)
    total_outages = len(weekly_records)
    emergency_count = sum(1 for r in weekly_records if "Аварійні" in r.get("type", ""))
    planned_count = sum(1 for r in weekly_records if "Планові" in r.get("type", ""))
    
    settlement_counts = {}
    total_hours = 0.0
    emergency_hours = 0.0
    
    max_duration = 0.0
    max_duration_record = None
    
    for rec in weekly_records:
        # Нормалізуємо назву населеного пункту для групування
        s = normalize_settlement_name(rec.get("settlement", "Невідомо"))
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
                duration = (dt_end - dt_start).total_seconds() / 3600.0
                total_hours += duration
                if "Аварійні" in rec.get("type", ""):
                    emergency_hours += duration
                
                # Антирекорд
                if duration > max_duration:
                    max_duration = duration
                    max_duration_record = {
                        "settlement": s,
                        "street": rec.get("streets", ["Невідома вулиця"])[0] if rec.get("streets") else "Невідома вулиця",
                        "duration": round(duration, 1),
                        "date": dt_start.strftime("%d.%m")
                    }
        except:
            pass

    # Середні значення
    avg_duration = round(total_hours / total_outages, 1) if total_outages > 0 else 0.0
    avg_emergency_duration = round(emergency_hours / emergency_count, 1) if emergency_count > 0 else 0.0

    # Сортуємо топ-постраждалих
    top_settlements = sorted(settlement_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_str = ", ".join([f"{k} ({v} відключень)" for k, v in top_settlements])

    # 4. Динаміка порівняно з минулим тижнем (WoW)
    history_path = "data/analytics_history.json"
    history_data = {"history": []}
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except:
            pass
            
    wow_text = "Динаміка: Немає даних для порівняння з минулим тижнем."
    if history_data.get("history"):
        # Отримуємо попередній тиждень
        prev = history_data["history"][-1]
        prev_outages = prev.get("total_outages", 0)
        prev_emergency = prev.get("emergency_count", 0)
        
        if prev_outages > 0:
            diff_outages = total_outages - prev_outages
            pct_change = (diff_outages / prev_outages) * 100
            trend = "збільшилась" if diff_outages > 0 else "зменшилась"
            wow_text = f"Динаміка: Кількість відключень {trend} на {abs(round(pct_change, 1))}% порівняно з минулим тижнем (було {prev_outages}, зараз {total_outages})."
            if prev_emergency > 0:
                diff_emerg = emergency_count - prev_emergency
                wow_text += f" Кількість аварійних інцидентів: була {prev_emergency}, зараз {emergency_count}."
        
    stats_text = f"""ТОЧНА СТАТИСТИКА ЗА ТИЖДЕНЬ:
Всього відключень: {total_outages}
З них аварійних: {emergency_count}
З них планових: {planned_count}
Загальна тривалість усіх відключень: {round(total_hours, 1)} годин
Середня тривалість одного відключення: {avg_duration} годин
Середній час усунення аварії: {avg_emergency_duration} годин
Найбільше постраждали населені пункти: {top_str}
"""
    if max_duration_record:
        stats_text += f"Найдовше безперервне відключення (антирекорд): {max_duration_record['settlement']}, {max_duration_record['street']} ({max_duration_record['duration']} годин, {max_duration_record['date']})\n"
    stats_text += wow_text + "\n"

    print("Статистика для ШІ:")
    print(stats_text)

    # 5. Відправляємо до Gemini
    API_KEY = os.environ.get("GEMINI_API_KEY")
    if not API_KEY:
        print("Помилка: GEMINI_API_KEY не знайдено.")
        save_report("Помилка генерації звіту: відсутній API ключ ШІ.", {})
        return

    genai.configure(api_key=API_KEY)
    
    prompt = f"""Напиши офіційне, але емпатичне щотижневе аналітичне зведення для Telegram-каналу громади.
Використовуй ЛИШЕ ці математично точні дані, не вигадуй жодних цифр:
{stats_text}

Правила:
1. Ніяких емодзі. 
2. Зроби гарний заголовок "Аналітичне зведення за тиждень", а також обов'язково розпочни текст із фрази: "Шановні мешканці Старокостянтинівської громади!"
3. Коротко підбий підсумки (яких відключень було більше, де було найважче, який середній час усунення аварій та динаміка відключень).
4. Офіційний, діловий стиль.
5. В кінці подякуй мешканцям за терпіння.
"""

    current_stats = {
        "week_end_date": now.strftime("%Y-%m-%d"),
        "total_outages": total_outages,
        "emergency_count": emergency_count,
        "planned_count": planned_count,
        "total_hours": round(total_hours, 1)
    }

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        report_text = response.text.strip()
        print("Звіт згенеровано успішно.")
        save_report(report_text, current_stats)
    except Exception as e:
        print(f"Помилка ШІ: {e}")
        save_report("Вибачте, сталася помилка при генерації щотижневого звіту.", {})

def save_report(text, stats):
    report_data = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": text
    }
    with open("data/analytics.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print("Збережено в data/analytics.json")

    # Зберігаємо в історію, якщо статистика не порожня
    if stats:
        history_path = "data/analytics_history.json"
        history_data = {"history": []}
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
            except:
                pass
        
        # Перевіряємо, щоб не дублювати за ту саму дату
        dates = [entry.get("week_end_date") for entry in history_data["history"]]
        if stats["week_end_date"] not in dates:
            history_data["history"].append(stats)
            # Обмежуємо історію останніми 52 тижнями (1 рік)
            history_data["history"] = history_data["history"][-52:]
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            print("Статистику збережено в історію data/analytics_history.json")

if __name__ == "__main__":
    generate_weekly_report()
