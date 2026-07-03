import json
import urllib.request
import urllib.parse
import traceback

def query_wikidata():
    # SPARQL query to get all Wikidata entities with KATOTTG codes starting with UA6804039
    sparql = """
    SELECT ?item ?name ?katottg WHERE {
      ?item wdt:P9435 ?katottg .
      FILTER (STRSTARTS(?katottg, "UA6804039"))
      ?item rdfs:label ?name .
      FILTER (LANG(?name) = "uk")
    }
    """
    url = "https://query.wikidata.org/sparql?query=" + urllib.parse.quote_plus(sparql) + "&format=json"
    headers = {"User-Agent": "AntigravityHromadaBot/1.0 (anti-gravity-coding-assistant)"}
    
    print("Querying Wikidata SPARQL endpoint with prefix UA6804039...")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["results"]["bindings"]
    except Exception as e:
        print(f"Error querying Wikidata: {e}")
        traceback.print_exc()
        return []

def main():
    bindings = query_wikidata()
    if not bindings:
        print("Failed to fetch Wikidata entries.")
        return
        
    print(f"Received {len(bindings)} bindings from Wikidata.")
    
    # Load districts
    with open("data/districts.json", "r", encoding="utf-8") as f:
        districts = json.load(f)
        
    # Map village name (normalized) -> district name
    village_to_district = {}
    for district, villages in districts.items():
        for v in villages:
            village_to_district[v.strip().lower()] = district
            
    # Process bindings
    settlements = []
    seen_katottg = set()
    
    for b in bindings:
        name = b["name"]["value"]
        katottg = b["katottg"]["value"]
        
        if katottg in seen_katottg:
            continue
        seen_katottg.add(katottg)
        
        # Determine type & prefix
        prefix = "с."
        sett_type = "село"
        if name == "Старокостянтинів":
            prefix = "м."
            sett_type = "місто"
            
        # Determine district
        clean_name = name.strip()
        district = "Місто Старокостянтинів"
        if sett_type == "село":
            district = village_to_district.get(clean_name.lower(), "Невідомий старостинський округ")
            
        # Create aliases
        aliases = [clean_name.lower()]
        aliases.append(f"{prefix} {clean_name}".lower())
        aliases.append(f"{prefix}{clean_name}".lower())
        
        # Special case for Першотравневе / Березівка
        if clean_name == "Березівка":
            aliases.extend(["першотравневе", "с. першотравневе", "с.першотравневе"])
            
        sett_obj = {
            "katottg": katottg,
            "name": clean_name,
            "type": sett_type,
            "prefix": prefix,
            "district": district,
            "aliases": aliases
        }
        settlements.append(sett_obj)
        
    # Sort settlements: city first, then villages alphabetically
    settlements.sort(key=lambda x: (0 if x["type"] == "місто" else 1, x["name"]))
    
    # Save settlements.json
    with open("data/settlements.json", "w", encoding="utf-8") as out_f:
        json.dump(settlements, out_f, ensure_ascii=False, indent=2)
        
    print(f"Successfully generated data/settlements.json with {len(settlements)} entries.")

if __name__ == "__main__":
    main()
