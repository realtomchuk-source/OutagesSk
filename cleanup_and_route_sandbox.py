import json
import os
import re

def normalize_street_name(name):
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r"^(вул\.|пров\.|просп\.|площа|бул\.)\s*", "", name)
    name = name.replace(".", "").strip()
    name = re.sub(r"\s+", " ", name)
    return name

def route_sandbox():
    archive_path = "data/archive.json"
    snapshot_path = "data/outages_snapshot.json"
    villages_path = "data/villages.json"
    clean_streets_path = "data/clean_official_streets.json"
    corrections_path = "data/street_corrections.json"
    
    # 1. Load files
    if not os.path.exists(archive_path) or not os.path.exists(villages_path) or not os.path.exists(clean_streets_path):
        print("Required files not found.")
        return
        
    with open(archive_path, "r", encoding="utf-8") as f:
        archive = json.load(f)
        
    with open(villages_path, "r", encoding="utf-8") as f:
        villages = json.load(f)
        
    with open(clean_streets_path, "r", encoding="utf-8") as f:
        clean_streets = json.load(f)
        
    corrections = {}
    if os.path.exists(corrections_path):
        try:
            with open(corrections_path, "r", encoding="utf-8") as f:
                corrections = json.load(f)
        except Exception as e:
            print(f"Error loading corrections: {e}")
            
    snapshot = []
    if os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
            
    print(f"[ROUTER] Loaded {len(archive)} archive records and {len(snapshot)} snapshot records.")
    
    # Helper to resolve candidates to our hromada with exclusion check
    def get_hromada_candidates(original_settlement, street_name):
        if not original_settlement:
            return []
        candidates = [c.strip() for c in original_settlement.split(",")]
        hromada_candidates = []
        for c in candidates:
            c_clean = re.sub(r"^(с\.|м\.|c\.|m\.)\s*", "", c.strip()).strip()
            if not c_clean:
                continue
            # Match case-insensitive
            match = None
            for v in villages:
                if v.lower().replace(" ", "") == c_clean.lower().replace(" ", ""):
                    match = v
                    break
            if match:
                cand_key = "м. Старокостянтинів" if match == "Старокостянтинів" else f"с. {match}"
                
                # Check if there is a rule for this street under this candidate settlement to move it to Sandbox
                rule = corrections.get(cand_key, {}).get(street_name, {})
                if rule.get("action") == "move_to_settlement" and "Пісочниця" in rule.get("target_settlements", []):
                    # User explicitly moved this street from this village to Sandbox, so exclude it!
                    continue
                hromada_candidates.append(cand_key)
                
        hromada_candidates = list(dict.fromkeys(hromada_candidates)) # remove duplicates
        
        # Fallback: if candidates are empty (or excluded), search all other settlements globally in whitelist
        if not hromada_candidates and street_name:
            global_candidates = []
            for cc, cc_streets in clean_streets.items():
                if cc == "Пісочниця":
                    continue
                # Check if this street is in this settlement's whitelist
                for ws in cc_streets.keys():
                    if ws.strip().lower() == street_name.strip().lower() or normalize_street_name(ws) == normalize_street_name(street_name):
                        # Verify we don't have a rule moving this street to Sandbox here
                        rule = corrections.get(cc, {}).get(street_name, {})
                        if not (rule.get("action") == "move_to_settlement" and "Пісочниця" in rule.get("target_settlements", [])):
                            global_candidates.append(cc)
                        break
            hromada_candidates = global_candidates
            
        return hromada_candidates

    # Routing logic
    def process_records(records_list, list_name):
        routed_direct = 0
        routed_intel = 0
        
        for rec in records_list:
            if rec.get("settlement") != "Пісочниця":
                continue
                
            orig = rec.get("original_settlement", "")
            
            # Find representative street name for candidates lookup
            rep_street = ""
            if rec.get("streets"):
                rep_street = rec["streets"][0]
            elif rec.get("streets_detailed") and rec["streets_detailed"][0].get("name"):
                rep_street = rec["streets_detailed"][0]["name"]
                
            hromada_candidates = get_hromada_candidates(orig, rep_street)
            
            if not hromada_candidates:
                continue
                
            # Case 1: Direct single village match
            if len(hromada_candidates) == 1:
                rec["settlement"] = hromada_candidates[0]
                routed_direct += 1
                continue
                
            # Case 2: Multi-village match (Intel routing)
            scores = {}
            for cand in hromada_candidates:
                cand_streets = clean_streets.get(cand, {})
                score = 0
                for s in rec.get("streets", []):
                    # Check direct or normalized street match in whitelist
                    matched_whitelist_street = None
                    for ws in cand_streets.keys():
                        if ws.strip().lower() == s.strip().lower() or normalize_street_name(ws) == normalize_street_name(s):
                            matched_whitelist_street = ws
                            break
                            
                    if matched_whitelist_street:
                        score += 10 # Found street in this village's whitelist
                        
                        # Compare house overlaps
                        rec_houses = []
                        if rec.get("streets_detailed"):
                            for sd in rec["streets_detailed"]:
                                if sd.get("name") == s and sd.get("houses"):
                                    rec_houses = [h.strip() for h in sd["houses"].split(",") if h.strip()]
                        
                        off_houses = cand_streets[matched_whitelist_street].get("houses", [])
                        if rec_houses and off_houses:
                            overlap = len(set(rec_houses) & set(off_houses))
                            score += overlap * 2
                            
                scores[cand] = score
                
            # Find the best candidate
            if scores:
                best_cand = max(scores, key=scores.get)
                best_score = scores[best_cand]
                
                # Check if it is a unique winner and has a positive score
                if best_score > 0:
                    ties = [cand for cand, sc in scores.items() if sc == best_score]
                    if len(ties) == 1:
                        rec["settlement"] = best_cand
                        routed_intel += 1
                        
        print(f"[ROUTER] [{list_name}] Routed {routed_direct} directly and {routed_intel} using intel matching.")

    # 2. Run routing on archive and snapshot
    process_records(archive, "Archive")
    process_records(snapshot, "Snapshot")
    
    # 3. Save files
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
        
    if snapshot:
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
    print("[ROUTER] Files successfully updated and saved.")

if __name__ == "__main__":
    route_sandbox()
