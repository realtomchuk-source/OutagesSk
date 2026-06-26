import json

with open("data/outages_snapshot.json", "r", encoding="utf-8") as f:
    data = json.load(f)

if data:
    s = data[0]['settlement']
    print(f"Length: {len(s)}")
    print("Codepoints:")
    for char in s:
        print(f"  char: {char!r}, codepoint: U+{ord(char):04X}, name: {char.encode('utf-8')}")
else:
    print("No data")
