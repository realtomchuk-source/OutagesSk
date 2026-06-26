import subprocess

def run_cmd(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding="utf-8")
    return result.stdout

with open("data/git_history_result.txt", "w", encoding="utf-8") as f:
    f.write("=== Git Log for 'Кривоноса' ===\n")
    f.write(run_cmd("git log -S Кривоноса --oneline") + "\n")
    
    f.write("=== Git Log for 'інтернаціоналістів' ===\n")
    f.write(run_cmd("git log -S інтернаціоналістів --oneline") + "\n")
    
    f.write("=== Git Log for 'інтернаціональний' ===\n")
    f.write(run_cmd("git log -S інтернаціональний --oneline") + "\n")

print("Done writing git history search results.")
