import os
import sys
from dotenv import load_dotenv

# Set paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from formatter import ask_ai, get_grouped_outages, outages, get_kyiv_now
from datetime import timedelta

load_dotenv()

# Let's get raw text for tomorrow
now_kyiv = get_kyiv_now()
if now_kyiv.hour == 23:
    today = now_kyiv.date() + timedelta(days=1)
else:
    today = now_kyiv.date()
tomorrow = today + timedelta(days=1)

items_tomorrow = [r for r in outages if "Планові" in r.get("type", "") and (
    r.get("start_datetime", "").startswith(tomorrow.strftime("%d.%m.%Y")) or
    r.get("end_datetime", "").startswith(tomorrow.strftime("%d.%m.%Y"))
)]

grouped = get_grouped_outages(items_tomorrow)
if grouped:
    sorted_keys = sorted(grouped.keys(), key=lambda k: (0 if k[1] == "Старокостянтинів" else 1, k[1], k[2]))
    raw_text_parts = []
    for k in sorted_keys:
        typ, settlement, time_range = k
        streets_dict = grouped[k]
        streets_str_list = []
        for s_name in sorted(streets_dict.keys()):
            houses_set = streets_dict[s_name]
            if houses_set:
                sorted_houses = sorted(list(houses_set))
                streets_str_list.append(f"{s_name} (буд. {', '.join(sorted_houses)})")
            else:
                streets_str_list.append(s_name)
        streets = "; ".join(streets_str_list)
        raw_text_parts.append(f"[{settlement}] {settlement} ({time_range}): {streets}")
    raw_text = "\n".join(raw_text_parts)
    
    prompt = f"""Створи офіційний Telegram-пост про ПЛАНОВИХ ВІДКЛЮЧЕННЯ електроенергії на {tomorrow.strftime('%d.%m.%Y')}.
СУВОРІ ПРАВИЛА (ІГНОРУВАННЯ ПРИЗВЕДЕ ДО ПОМИЛКИ):
1. КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати БУДЬ-ЯКІ емодзі (ніяких блискавок, крапок, кружечків, трикутників). Пост має бути виключно текстовим.
2. Пост ПОВИНЕН починатися з фрази: "Шановні мешканці Старокостянтинівської громади! За офіційною інформацією АТ «Хмельницькобленерго», повідомляємо про планові знеструмлення, передбачені на {tomorrow.strftime('%d.%m.%Y')}:"
3. Час вказуй точно так, як він переданий у сирих даних (наприклад "з 09:00 до 17:00" або "з 21 травня 21:43 до 22 травня 17:43"). Не змінюй і не спотворюй хронологію.
4. Офіційний, діловий тон, але привабливе і зрозуміле структурування. Використовуй звичайні дефіси "-" для маркованих списків.
5. ЗГРУПУЙ населені пункти за округами (СО), які вказані в квадратних дужках. Спочатку має йти Місто Старокостянтинів, потім інші округи.
6. В кінці додай коротке: "Просимо завчасно зарядити пристрої та з розумінням поставитись до тимчасових незручностей."
7. КАТЕГОРИЧНО ЗАБОРОНЕНО використовувати слово "частково" або "(частково)" для будь-яких вулиць. Виводь повні списки будинків повністю, без жодних скорочень, точно так, як вони вказані в сирих даних (наприклад, "(буд. 1, 2, 3, 4, 5)").

Сирі дані для обробки:
{raw_text}
"""
    print("--- PROMPT ---")
    print(prompt[:500] + "...")
    print("--- CALLING AI ---")
    response = ask_ai(prompt)
    print("--- RESPONSE ---")
    print(response)
else:
    print("No outages for tomorrow to test.")
