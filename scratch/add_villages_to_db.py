import json

def add_villages():
    # 1. Load villages
    with open("data/villages.json", "r", encoding="utf-8") as f:
        villages = json.load(f)
        
    # 2. Load clean_official_streets
    with open("data/clean_official_streets.json", "r", encoding="utf-8") as f:
        clean_streets = json.load(f)
        
    added_count = 0
    for v in villages:
        if v == "Старокостянтинів":
            continue
        key = f"с. {v}"
        if key not in clean_streets:
            clean_streets[key] = {}
            added_count += 1
            
    # Sort the dictionary keys alphabetically to keep the file clean and organized
    sorted_clean_streets = {k: clean_streets[k] for k in sorted(clean_streets.keys())}
    
    with open("data/clean_official_streets.json", "w", encoding="utf-8") as f:
        json.dump(sorted_clean_streets, f, ensure_ascii=False, indent=2)
        
    print(f"Added {added_count} villages to clean_official_streets.json")

if __name__ == "__main__":
    add_villages()
