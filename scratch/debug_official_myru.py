import json

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    data = json.load(f)

city = data.get("м. Старокостянтинів", {})
print("Вулиці міста Старокостянтинів, які містять 'Миру':")
for street in city.keys():
    if "миру" in street.lower():
        print(f"  '{street}' (тип: {type(street)})")
        # Роздрукуємо коди символів, щоб перевірити наявність прихованих символів або латиниці
        print(f"  Коди: {[ord(c) for c in street]}")
