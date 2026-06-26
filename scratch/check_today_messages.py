import json

with open("data/messages.json", "r", encoding="utf-8") as f:
    messages = json.load(f)

targets = ["2026-06-21_tg_planned", "2026-06-22_tg_planned"]
for m in messages:
    if m.get("id") in targets:
        print(f"ID: {m.get('id')}")
        print(f"  Date: {m.get('date')}")
        print(f"  Hash: {m.get('hash')}")
        print(f"  Created At: {m.get('created_at')}")
        content = m.get('content', '')
        print(f"  Has 'частково': {'частково' in content.lower()}")
        print(f"  Content:\n{content}\n")
