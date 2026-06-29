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
        
    snapshot = []
    if os.path.exists(snapshot_path):
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
            
    print(f"Loaded {len(archive)} archive records and {len(snapshot)} snapshot records.")
    
    # Helper to resolve candidates to our hromada
    def get_hromada_candidates(original_settlement):
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
                if match == "Старокостянтинів":
                    hromada_candidates.append("м. Старокостянтинів")
                else:
                    hromada_candidates.append(f"с. {match}")
        return list(dict.fromkeys(hromada_candidates)) # remove duplicates

    # Routing logic
    def process_records(records_list, list_name):
        routed_direct = 0
        routed_intel = 0
        
        for rec in records_list:
            if rec.get("settlement") != "Пісочниця":
                continue
                
            orig = rec.get("original_settlement", "")
            hromada_candidates = get_hromada_candidates(orig)
            
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
                        
        print(f"[{list_name}] Routed {routed_direct} directly and {routed_intel} using intel matching.")

    # 2. Run routing on archive and snapshot
    process_records(archive, "Archive")
    process_records(snapshot, "Snapshot")
    
    # 3. Save files
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
        
    if snapshot:
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
    print("Files successfully updated and saved.")

if __name__ == "__main__":
    route_sandbox()
