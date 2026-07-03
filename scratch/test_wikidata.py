import json
import urllib.request
import urllib.parse

def test():
    # Query all properties and their values for Starokostiantyniv (Q997429)
    sparql = """
    SELECT ?property ?value WHERE {
      wd:Q997429 ?property ?value .
    }
    """
    url = "https://query.wikidata.org/sparql?query=" + urllib.parse.quote_plus(sparql) + "&format=json"
    headers = {"User-Agent": "AntigravityHromadaBot/1.0 (anti-gravity-coding-assistant)"}
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            bindings = res_data["results"]["bindings"]
            print(f"Found {len(bindings)} properties.")
            for b in bindings:
                prop = b["property"]["value"]
                val = b["value"]["value"]
                # Search for values containing UA680 or looking like KATOTTG
                if "UA680" in val or "UA68" in val or "680" in val or "11141" in val or "84208" in val:
                    print(f"Match: {prop} -> {val}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
