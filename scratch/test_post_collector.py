import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def fetch_html(type_id, date_range=None):
    url = "https://hoe.com.ua/shutdown/eventlist"
    payload = {
        "TypeId": str(type_id),
        "PageNumber": "1",
        "RemId": "12"
    }
    if date_range:
        payload["DateRange"] = date_range

    data = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://hoe.com.ua/shutdown/all",
        "Origin": "https://hoe.com.ua"
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")

def test():
    today = datetime.now().strftime("%d.%m.%Y")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    date_range = f"{today} - {tomorrow}"
    print(f"Тестуємо діапазон: {date_range}")

    print("Завантажуємо аварійні...")
    em_html = fetch_html(1)
    print(f"Аварійні отримано, розмір: {len(em_html)} симв.")

    print("Завантажуємо планові з діапазоном дат...")
    pl_html = fetch_html(2, date_range=date_range)
    print(f"Планові отримано, розмір: {len(pl_html)} симв.")

    soup = BeautifulSoup(pl_html, "html.parser")
    table = soup.find("table", class_="table-shutdowns")
    if not table:
        print("Таблицю планових не знайдено!")
        return

    rows = table.find_all("tr")
    print(f"Усього рядків у таблиці планових: {len(rows)}")

    dates = set()
    staro_entries = 0
    for r in rows:
        city_tag = r.find("p", class_="city")
        if city_tag and "Старокостянтинів" in city_tag.get_text():
            staro_entries += 1
            stimes = [s.get_text(strip=True) for s in r.find_all("div", class_="stime")]
            if len(stimes) > 1:
                dates.add(stimes[1][:10])

    print(f"Знайдено записів для Старокостянтинова: {staro_entries}")
    print(f"Знайдені дати початку відключень: {sorted(list(dates))}")

if __name__ == "__main__":
    test()
