import json

with open("data/messages.json", "r", encoding="utf-8") as f:
    messages = json.load(f)

print(f"Total messages in file: {len(messages)}")
for i, m in enumerate(messages):
    print(f"[{i+1}] ID: {m.get('id')!r}, Date: {m.get('date')!r}, Type: {m.get('type')!r}")
    print(f"    Hash: {m.get('hash')!r}")
    print(f"    Created At: {m.get('created_at')!r}")
    content = m.get('content', '')
    has_part = "частково" in content.lower()
    print(f"    Has 'частково': {has_part}")
    print(f"    Content preview: {content[:100]}...")
