import requests
import json

def check_samchyky():
    url = "https://z.overpass-api.de/api/interpreter"
    query = """[out:json][timeout:30];
(
  node["name"="Самчики"];
  way["name"="Самчики"];
  relation["name"="Самчики"];
);
out tags;"""
    
    headers = {
        "User-Agent": "StarokostiantynivOutagesVerifier/1.0 (contact: local-testing-only@example.com)"
    }
    
    try:
        response = requests.post(url, data={"data": query}, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            print(f"Found {len(elements)} objects.")
            
            with open("scratch/samchyky_osm.json", "w", encoding="utf-8") as f:
                json.dump(elements, f, ensure_ascii=False, indent=2)
            print("Saved details to scratch/samchyky_osm.json")
            
            for i, elem in enumerate(elements):
                print(f"Obj {i+1}: type={elem['type']}, id={elem['id']}")
        else:
            print(f"Error {response.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_samchyky()
