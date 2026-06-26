import json

with open("data/official_streets.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    
print("с. Великий Чернятин:")
print(list(data.get("с. Великий Чернятин", {}).keys()))
print("\nс. Малий Чернятин:")
print(list(data.get("с. Малий Чернятин", {}).keys()))
