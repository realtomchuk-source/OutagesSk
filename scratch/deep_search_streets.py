import json

print("--- Searching official_streets.json ---")
with open("data/official_streets.json", "r", encoding="utf-8") as f:
    official = json.load(f)
for sett, streets in official.items():
    for street in streets.keys():
        if "Крив" in street or "інтер" in street.lower():
            print(f"[{sett}] {street}")

print("\n--- Searching street_corrections.json ---")
with open("data/street_corrections.json", "r", encoding="utf-8") as f:
    corrections = json.load(f)
for sett, rules in corrections.items():
    for source, rule in rules.items():
        if "Крив" in source or "Крив" in str(rule) or "інтер" in source.lower() or "інтер" in str(rule).lower():
            print(f"[{sett}] {source} -> {rule}")

print("\n--- Searching address_changelog.json ---")
with open("data/address_changelog.json", "r", encoding="utf-8") as f:
    changelog = json.load(f)
for entry in changelog:
    desc = str(entry)
    if "Крив" in desc or "інтер" in desc.lower():
        print(f"Entry: {entry}")
