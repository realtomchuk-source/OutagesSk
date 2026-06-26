import os
import sys
import json
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from formatter import outages, is_active_on_date, get_kyiv_now
from datetime import timedelta

load_dotenv()
now_kyiv = get_kyiv_now()
today = now_kyiv.date()
tomorrow = today + timedelta(days=1)

print(f"Today is {today}")
print(f"Tomorrow is {tomorrow}")

items_today = [r for r in outages if is_active_on_date(r, today)]

print(f"Total outages in snapshot: {len(outages)}")

# Count by date in outages
date_counts = {}
for r in outages:
    sd = r.get("start_datetime", "")
    if len(sd) >= 10:
        d = sd[:10]
        date_counts[d] = date_counts.get(d, 0) + 1

print("\nOutages by date in snapshot:")
for d, count in sorted(date_counts.items()):
    print(f"  {d}: {count}")

print(f"\nItems today ({len(items_today)}):")
for r in items_today:
    settlement = r.get("settlement", "")
    t = r.get("type", "")
    start = r.get("start_datetime", "")
    # Print safe string (repr)
    print(f"  Settlement: {settlement!r}, Type: {t!r}, Start: {start!r}")
