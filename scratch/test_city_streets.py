import requests
import json

def test_city():
    url = "https://z.overpass-api.de/api/interpreter"
    query = """[out:json][timeout:120];
area["name"="Старокостянтинів"]->.searchArea;
way["highway"]["name"](area.searchArea);
out tags;"""
    
    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)",
        "Accept": "application/json"
    }
    
    print("Завантажуємо вулиці безпосередньо для міста Старокостянтинів...")
    try:
        response = requests.post(url, data={"data": query}, headers=headers, timeout=120)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            print(f"Знайдено вулиць у місті: {len(elements)}")
            
            # Пошукаємо Манькевича та Рудяка
            man_found = []
            rud_found = []
            for elem in elements:
                tags = elem.get("tags", {})
                name = tags.get("name", "")
                if "маньк" in name.lower():
                    man_found.append(tags)
                if "рудяк" in name.lower():
                    rud_found.append(tags)
                    
            print(f"Знайдено Манькевича: {man_found}")
            print(f"Знайдено Рудяка: {rud_found}")
            
            # Збережемо результат у тимчасовий файл
            with open("scratch/osm_city_streets.json", "w", encoding="utf-8") as f:
                json.dump(elements, f, ensure_ascii=False, indent=2)
                
        else:
            print(f"Помилка {response.status_code}: {response.text[:500]}")
    except Exception as e:
        print(f"Помилка: {e}")

if __name__ == "__main__":
    test_city()
