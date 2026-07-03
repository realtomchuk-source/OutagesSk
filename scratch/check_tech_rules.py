import json

def check_sandbox():
    with open("data/street_corrections.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    sandbox_rules = data.get("Пісочниця", {})
    
    lines = []
    lines.append(f"Total rules in Sandbox: {len(sandbox_rules)}\n")
    for street, rule in sandbox_rules.items():
        lines.append(f"Street: '{street}'")
        lines.append(f"  Rule: {rule}")
        lines.append("-" * 40)
        
    with open("scratch/sandbox_rules.txt", "w", encoding="utf-8") as out_f:
        out_f.write("\n".join(lines))
        
    print("Report saved to scratch/sandbox_rules.txt")

if __name__ == "__main__":
    check_sandbox()
