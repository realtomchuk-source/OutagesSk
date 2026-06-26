import json
import subprocess

def get_head_messages():
    result = subprocess.run(["git", "show", "HEAD:data/messages.json"], capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0:
        return json.loads(result.stdout)
    return []

def get_local_messages():
    with open("data/messages.json", "r", encoding="utf-8") as f:
        return json.load(f)

head_msgs = get_head_messages()
local_msgs = get_local_messages()

target = "2026-06-21_tg_planned"

head_msg = next((m for m in head_msgs if m.get("id") == target), None)
local_msg = next((m for m in local_msgs if m.get("id") == target), None)

print("HEAD version:")
if head_msg:
    print(f"Created At: {head_msg.get('created_at')}")
    print(head_msg.get("content")[:500])
else:
    print("None")

print("\nLOCAL version:")
if local_msg:
    print(f"Created At: {local_msg.get('created_at')}")
    print(local_msg.get("content")[:500])
else:
    print("None")
