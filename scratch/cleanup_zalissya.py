import json

def cleanup():
    archive_path = "data/archive.json"
    with open(archive_path, "r", encoding="utf-8") as f:
        archive = json.load(f)
        
    initial_len = len(archive)
    
    # Filter out records where settlement is "Пісочниця" and original_settlement is "Залісся"
    filtered_archive = [
        rec for rec in archive
        if not (rec.get("settlement") == "Пісочниця" and rec.get("original_settlement") == "Залісся")
    ]
    
    removed = initial_len - len(filtered_archive)
    print(f"Removed {removed} records from archive.")
    
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(filtered_archive, f, ensure_ascii=False, indent=2)
        
if __name__ == "__main__":
    cleanup()
