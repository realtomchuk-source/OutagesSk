import json

def search():
    with open("scratch/osm_raw_streets.json", "r", encoding="utf-8") as f:
        osm_elements = json.load(f)
        
    print("Шукаємо 'Миру':")
    count = 0
    for elem in osm_elements:
        tags = elem.get("tags", {})
        name = tags.get("name", "")
        if "миру" in name.lower():
            print(f"  Знайдено: {tags}")
            count += 1
            if count >= 10:
                break
                
    print("\nШукаємо 'Південн':")
    count = 0
    for elem in osm_elements:
        tags = elem.get("tags", {})
        name = tags.get("name", "")
        if "південн" in name.lower():
            print(f"  Знайдено: {tags}")
            count += 1
            if count >= 10:
                break

if __name__ == "__main__":
    search()
