import requests
import json
import time

def test_around():
    url = "https://z.overpass-api.de/api/interpreter"
    
    # 1. Самчики - вулиця Миру
    query_samchyky = """[out:json][timeout:15];
node["name"="Самчики"]["place"~"village|town|hamlet"]->.center;
way(around.center:2000)["highway"]["name"~"миру",i];
out tags;"""

    # 2. Старокостянтинів - вулиця Рудяка
    query_city = """[out:json][timeout:15];
node["name"="Старокостянтинів"]["place"~"village|town|hamlet"]->.center;
way(around.center:5000)["highway"]["name"~"рудяка",i];
out tags;"""

    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)",
        "Accept": "application/json"
    }

    print("Тест 1: Шукаємо вулицю Миру у Самчиках через (around:2000)...")
    try:
        response = requests.post(url, data={"data": query_samchyky}, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            print(f"Знайдено вулиць: {len(elements)}")
            for elem in elements[:3]:
                print(f"  {elem.get('tags')}")
        else:
            print(f"Помилка {response.status_code}")
    except Exception as e:
        print(f"Помилка: {e}")

    time.sleep(2)

    print("\nТест 2: Шукаємо вулицю Рудяка у Старокостянтинові через (around:5000)...")
    try:
        response = requests.post(url, data={"data": query_city}, headers=headers, timeout=20)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            print(f"Знайдено вулиць: {len(elements)}")
            for elem in elements[:3]:
                print(f"  {elem.get('tags')}")
        else:
            print(f"Помилка {response.status_code}")
    except Exception as e:
        print(f"Помилка: {e}")

if __name__ == "__main__":
    test_around()
