import requests
import json
import math

def get_distance(lat1, lon1, lat2, lon2):
    # Гаверсинус формула для розрахунку відстані в метрах
    R = 6371000 # радіус Землі в метрах
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def debug():
    url = "https://z.overpass-api.de/api/interpreter"
    
    # 1. Отримуємо точку Самчиків з координатами
    query_node = """[out:json];
node["name"="Самчики"]["place"="village"];
out;"""

    # 2. Отримуємо вулицю Фурмана на OSM (шукаємо у всій громаді)
    query_street = """[out:json];
area["name"="Старокостянтинівська міська громада"]->.a;
way["highway"]["name"="вулиця Фурмана"](area.a);
out geom;"""

    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)"
    }
    
    node_lat, node_lon = None, None
    street_lat, street_lon = None, None
    
    print("Завантажуємо точку Самчиків...")
    try:
        r = requests.post(url, data={"data": query_node}, headers=headers, timeout=20)
        if r.status_code == 200:
            elements = r.json().get("elements", [])
            if elements:
                node = elements[0]
                node_lat = node["lat"]
                node_lon = node["lon"]
                print(f"Точка Самчиків: lat={node_lat}, lon={node_lon}")
        else:
            print(f"Помилка {r.status_code}")
    except Exception as e:
        print(f"Помилка: {e}")
        
    print("\nЗавантажуємо вулицю Фурмана...")
    try:
        r = requests.post(url, data={"data": query_street}, headers=headers, timeout=20)
        if r.status_code == 200:
            elements = r.json().get("elements", [])
            if elements:
                way = elements[0]
                # Беремо першу точку лінії для спрощення
                geometry = way.get("geometry", [])
                if geometry:
                    street_lat = geometry[0]["lat"]
                    street_lon = geometry[0]["lon"]
                    print(f"Вулиця Фурмана (перша точка): lat={street_lat}, lon={street_lon}")
        else:
            print(f"Помилка {r.status_code}")
    except Exception as e:
        print(f"Помилка: {e}")
        
    if node_lat and street_lat:
        dist = get_distance(node_lat, node_lon, street_lat, street_lon)
        print(f"\nВідстань між точкою села та вулицею Фурмана: {dist:.1f} метрів.")
    else:
        print("\nНе вдалося отримати координати для порівняння.")

if __name__ == "__main__":
    debug()
