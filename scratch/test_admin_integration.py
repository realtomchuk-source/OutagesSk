import requests
import json
import os

def run_tests():
    api_base = "http://localhost:8000"
    
    print("=== STARTING ADMIN API INTEGRATION TESTS ===")
    
    # 1. Test GET request to static files
    print("\n1. Testing static file fetching...")
    for filename in ["data/clean_official_streets.json", "data/suspicious_base_streets.json", "data/review_recommendations.json"]:
        url = f"{api_base}/{filename}"
        resp = requests.get(url)
        print(f"   GET {filename} -> Status: {resp.status_code}")
        assert resp.status_code == 200, f"Failed to get {filename}"
        data = resp.json()
        print(f"   Successfully parsed JSON, type: {type(data)}")

    # 2. Simulate Frontend Moderation: Approve a suspicious street
    print("\n2. Simulating street approval action...")
    
    # Load current files
    with open("data/clean_official_streets.json", "r", encoding="utf-8") as f:
        clean_streets = json.load(f)
    with open("data/suspicious_base_streets.json", "r", encoding="utf-8") as f:
        susp_streets = json.load(f)
        
    print(f"   Initial state: {len(susp_streets.get('м. Старокостянтинів', {}))} suspicious streets in city.")
    
    # Check if our test street exists
    test_settlement = "м. Старокостянтинів"
    test_street = "вул. Заставня"
    
    assert test_settlement in susp_streets and test_street in susp_streets[test_settlement], "Test street not found in suspicious list"
    
    # Perform move
    street_info = susp_streets[test_settlement][test_street].copy()
    if "reason" in street_info:
        del street_info["reason"]
        
    # Add to clean
    if test_settlement not in clean_streets:
        clean_streets[test_settlement] = {}
    clean_streets[test_settlement][test_street] = street_info
    
    # Remove from suspicious
    del susp_streets[test_settlement][test_street]
    
    # Save clean streets via API
    payload_clean = {
        "filePath": "data/clean_official_streets.json",
        "content": json.dumps(clean_streets, ensure_ascii=False, indent=2)
    }
    resp_clean = requests.post(f"{api_base}/api/save", json=payload_clean)
    assert resp_clean.status_code == 200
    assert resp_clean.json().get("status") == "ok"
    print("   Posted clean_official_streets.json successfully.")
    
    # Save suspicious streets via API
    payload_susp = {
        "filePath": "data/suspicious_base_streets.json",
        "content": json.dumps(susp_streets, ensure_ascii=False, indent=2)
    }
    resp_susp = requests.post(f"{api_base}/api/save", json=payload_susp)
    assert resp_susp.status_code == 200
    assert resp_susp.json().get("status") == "ok"
    print("   Posted suspicious_base_streets.json successfully.")
    
    # Verify changes
    with open("data/clean_official_streets.json", "r", encoding="utf-8") as f:
        updated_clean = json.load(f)
    with open("data/suspicious_base_streets.json", "r", encoding="utf-8") as f:
        updated_susp = json.load(f)
        
    assert test_street in updated_clean.get(test_settlement, {}), "Street should be in clean list"
    assert test_street not in updated_susp.get(test_settlement, {}), "Street should not be in suspicious list"
    print("   Verification: SUCCESS! Street moved successfully.")
    
    # Restore original state
    clean_streets[test_settlement][test_street] = street_info
    if test_street in clean_streets[test_settlement]:
        del clean_streets[test_settlement][test_street]
    
    susp_streets[test_settlement][test_street] = street_info
    susp_streets[test_settlement][test_street]["reason"] = "Не знайдено в OpenStreetMap"
    
    with open("data/clean_official_streets.json", "w", encoding="utf-8") as f:
        json.dump(clean_streets, f, ensure_ascii=False, indent=2)
    with open("data/suspicious_base_streets.json", "w", encoding="utf-8") as f:
        json.dump(susp_streets, f, ensure_ascii=False, indent=2)
    print("   Restored original files.")
    
    print("\nALL LOCAL API TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
