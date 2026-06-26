import requests
import json

def test():
    url = "https://z.overpass-api.de/api/interpreter"
    query = """[out:json][timeout:15];
node["name"="Самчики"]["place"="village"]->.center;
way(around.center:2000)["highway"]["name"~"Фурмана",i];
out tags;"""
    
    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)"
    }
    
    try:
        r = requests.post(url, data={"data": query}, headers=headers, timeout=20)
        if r.status_code == 200:
            elements = r.json().get("elements", [])
            print(f"Знайдено вулиць: {len(elements)}")
            for elem in elements:
                print(f"  {elem.get('tags')}")
        else:
            print(f"Помилка {r.status_code}")
    except Exception as e:
        print(f"Помилка: {e}")

if __name__ == "__main__":
    test()
