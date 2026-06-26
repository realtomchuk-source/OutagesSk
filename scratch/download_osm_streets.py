import requests
import json
import time

def download_osm():
    url = "https://z.overpass-api.de/api/interpreter"
    
    query_community = """[out:json][timeout:60];
area["name"="Старокостянтинівська міська громада"]->.searchArea;
way["highway"]["name"](area.searchArea);
out tags;"""

    query_city = """[out:json][timeout:60];
area["name"="Старокостянтинів"]->.searchArea;
way["highway"]["name"](area.searchArea);
out tags;"""
    
    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)",
        "Accept": "application/json"
    }
    
    all_elements = {}
    
    # 1. Запит для всієї громади
    print("Крок 1: Завантажуємо вулиці для Старокостянтинівської громади...")
    try:
        response = requests.post(url, data={"data": query_community}, headers=headers, timeout=90)
        if response.status_code == 200:
            community_data = response.json()
            elements = community_data.get("elements", [])
            print(f"Знайдено в громаді: {len(elements)} елементів.")
            for elem in elements:
                all_elements[elem["id"]] = elem
        else:
            print(f"Помилка громади {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"Помилка запиту громади: {e}")
        
    time.sleep(2)  # Пауза перед наступним запитом
    
    # 2. Запит для самого міста
    print("\nКрок 2: Завантажуємо вулиці для міста Старокостянтинів...")
    try:
        response = requests.post(url, data={"data": query_city}, headers=headers, timeout=90)
        if response.status_code == 200:
            city_data = response.json()
            elements = city_data.get("elements", [])
            print(f"Знайдено в місті: {len(elements)} елементів.")
            for elem in elements:
                all_elements[elem["id"]] = elem
        else:
            print(f"Помилка міста {response.status_code}: {response.text[:300]}")
    except Exception as e:
        print(f"Помилка запиту міста: {e}")
        
    # 3. Об'єднання та збереження
    unique_elements = list(all_elements.values())
    print(f"\nОб'єднано унікальних елементів: {len(unique_elements)}")
    
    try:
        with open("scratch/osm_raw_streets.json", "w", encoding="utf-8") as f:
            json.dump(unique_elements, f, ensure_ascii=False, indent=2)
        print("Результати успішно об'єднано та збережено у scratch/osm_raw_streets.json")
    except Exception as e:
        print(f"Помилка збереження файлу: {e}")

if __name__ == "__main__":
    download_osm()
