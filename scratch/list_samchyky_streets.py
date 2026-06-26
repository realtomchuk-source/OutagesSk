import requests
import json

def list_streets():
    url = "https://overpass.osm.ch/api/interpreter"
    query = """[out:json][timeout:30];
node["name"="Самчики"]["place"="village"]->.center;
way(around.center:3000)["highway"]["name"];
out tags;"""
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = requests.post(url, data={"data": query}, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            print(f"Found {len(elements)} streets.")
            
            with open("scratch/samchyky_streets_all.json", "w", encoding="utf-8") as f:
                json.dump(elements, f, ensure_ascii=False, indent=2)
            print("Saved to scratch/samchyky_streets_all.json")
            
            names = set()
            for elem in elements:
                name = elem.get("tags", {}).get("name")
                if name:
                    names.add(name)
            
            with open("scratch/samchyky_street_names.txt", "w", encoding="utf-8") as f:
                f.write(f"Names count: {len(names)}\n")
                for n in sorted(names):
                    f.write(f"  - {n}\n")
            print("Saved names list to scratch/samchyky_street_names.txt")
            
        else:
            print(f"Error status: {response.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    list_streets()
