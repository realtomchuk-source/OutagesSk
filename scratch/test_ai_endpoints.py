import requests
import json
import os

def run_tests():
    api_base = "http://localhost:8000"
    
    print("=== STARTING AI ENDPOINTS INTEGRATION TESTS ===")
    
    # Reset limit state first so test is clean
    limit_file = "data/ai_limit_state.json"
    with open(limit_file, "w", encoding="utf-8") as f:
        json.dump({"last_ai_request_time": "1970-01-01T00:00:00Z"}, f, indent=2)
    print("   Reset ai_limit_state.json to 1970.")
    
    # 1. Test status allowed
    resp = requests.get(f"{api_base}/api/ai_status")
    print(f"   GET /api/ai_status -> Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json().get("allowed") is True
    
    # 2. Test clean houses (should succeed and trigger limit)
    payload = {
        "street": "вул. Центральна",
        "houses": ["1", "2", "3", "опора 12", "ктп-43", "4б"]
    }
    resp = requests.post(f"{api_base}/api/clean_houses_ai", json=payload)
    print(f"   POST /api/clean_houses_ai -> Status: {resp.status_code}")
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data.get("status") == "ok"
    print(f"   Cleaned houses returned: {res_data.get('cleaned_houses')}")
    # Verify that garbage is filtered out by AI
    assert "ктп-43" not in res_data.get("cleaned_houses")
    
    # 3. Test status blocked
    resp = requests.get(f"{api_base}/api/ai_status")
    print(f"   GET /api/ai_status -> Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json().get("allowed") is False
    assert resp.json().get("seconds_left") > 3000
    
    # 4. Test calling again (should fail with 429)
    resp = requests.post(f"{api_base}/api/clean_houses_ai", json=payload)
    print(f"   POST /api/clean_houses_ai (during cooldown) -> Status: {resp.status_code}, Body: {resp.json()}")
    assert resp.status_code == 429
    assert "Зачекайте ще" in resp.json().get("message")
    
    # 5. Restore original state (cooldown off)
    with open(limit_file, "w", encoding="utf-8") as f:
        json.dump({"last_ai_request_time": "1970-01-01T00:00:00Z"}, f, indent=2)
    print("   Reset ai_limit_state.json to 1970 (cooldown cleared).")
    
    print("\nALL AI ENDPOINT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
