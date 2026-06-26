import json

with open("data/suspicious_base_streets.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("=== СПИСОК НЕПІДТВЕРДЖЕНИХ ВУЛИЦЬ ЗА НАСЕЛЕНИМИ ПУНКТАМИ ===")
total = 0
for settlement, streets in sorted(data.items()):
    if streets:
        print(f"\n{settlement} ({len(streets)}):")
        for street_name in sorted(streets.keys()):
            info = streets[street_name]
            houses_str = ", ".join(info.get("houses", []))
            houses_preview = f" (будинки: {houses_str})" if houses_str else " (немає будинків)"
            print(f"  - '{street_name}'{houses_preview}")
            total += 1

print(f"\nВсього непідтверджених вулиць: {total}")
