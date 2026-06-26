import json

with open("data/sandbox_origins_report_v2.json", "r", encoding="utf-8") as f:
    report = json.load(f)

no_match_streets = [
    "вул. Дзержинського",
    "вул. Леніна",
    "вул. Ліцейна",
    "вул. Нагірна",
    "вул. Немиринецька",
    "вул. Озерна",
    "вул. Островського",
    "вул. автодорога (Городище-Рівне-Старокостянтинів) - Попівці",
    "пров. 1 Кривоноса",
    "пров. Воїнів інтернаціоналістів"
]

with open("data/inspect_no_matches_result.txt", "w", encoding="utf-8") as out_f:
    for s in no_match_streets:
        if s in report:
            out_f.write(f"Street: {s}\n")
            out_f.write(f"  Possible settlements: {report[s]['possible_original_settlements']}\n")
            out_f.write(f"  Sample houses: {report[s]['sample_houses']}\n")
            out_f.write(f"  Occurrences: {report[s]['occurrences']}\n")
            out_f.write("-" * 40 + "\n")
        else:
            out_f.write(f"Street: {s} not found in trace report.\n")
            
print("Done writing inspect_no_matches_result.txt")
