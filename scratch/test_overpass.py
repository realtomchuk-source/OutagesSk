import requests
import json
import time

def test_mirrors():
    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
        "https://overpass.osm.ch/api/interpreter"
    ]
    
    query = """[out:json][timeout:60];
area["name"="Старокостянтинівська міська громада"]->.searchArea;
way["highway"]["name"](area.searchArea);
out tags;"""
    
    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)",
        "Accept": "application/json"
    }
    
    print("=== ТЕСТУВАННЯ ДЗЕРКАЛ OVERPASS API ===")
    for mirror in mirrors:
        print(f"\nТестуємо: {mirror}")
        try:
            # Спробуємо POST
            response = requests.post(mirror, data={"data": query}, headers=headers, timeout=15)
            print(f"POST Статус: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Успішно! Знайдено елементів: {len(data.get('elements', []))}")
                break
            
            # Спробуємо GET
            response = requests.get(mirror, params={"data": query}, headers=headers, timeout=15)
            print(f"GET Статус: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Успішно! Знайдено елементів: {len(data.get('elements', []))}")
                break
        except Exception as e:
            print(f"Помилка з'єднання: {e}")

def test_nominatim():
    print("\n=== ТЕСТУВАННЯ NOMINATIM API ===")
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": "вулиця Миру, с. Самчики, Хмельницька область",
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"Статус Nominatim: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Успішна відповідь Nominatim:")
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(response.text)
    except Exception as e:
        print(f"Помилка: {e}")

if __name__ == "__main__":
    test_mirrors()
    test_nominatim()
