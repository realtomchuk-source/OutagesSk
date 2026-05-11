import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# 1. Отримуємо головну сторінку, щоб знайти CSRF-токен
print("1. Завантажуємо головну сторінку...")
main_url = "https://hoe.com.ua/shutdown/all"
main_resp = session.get(main_url)
print(f"   Статус: {main_resp.status_code}")

# Шукаємо токен у HTML
soup = BeautifulSoup(main_resp.text, "html.parser")
token_input = soup.find("input", {"name": "__RequestVerificationToken"})

if token_input:
    token = token_input.get("value")
    print(f"   Знайдено токен: {token[:30]}...")
else:
    print("   Токен не знайдено. Спробуємо без нього.")
    token = None

# 2. Формуємо запит до API
today = datetime.now()
end_date = today + timedelta(days=4)
date_range = f"{today.strftime('%d.%m.%Y')}+-+{end_date.strftime('%d.%m.%Y')}"

url = "https://hoe.com.ua/shutdown/eventlist"
payload = {
    "TypeId": "2",
    "DateRange": date_range,
    "PageNumber": "1",
    "RemId": "12",
    "X-Requested-With": "XMLHttpRequest"
}

# Якщо знайшли токен, додаємо його
if token:
    payload["__RequestVerificationToken"] = token

headers = {
    "Referer": "https://hoe.com.ua/shutdown/all",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded"
}

print("\n2. Надсилаємо API-запит...")
response = session.post(url, data=payload, headers=headers)
print(f"   Статус: {response.status_code}")

if response.status_code == 200:
    text = response.text
    if "events-wrapper" in text or "table-shutdowns" in text:
        print("✅ Успіх! Отримано таблицю. Перші 800 символів:")
        print(text[:800])
    else:
        print("❌ Відповідь без таблиці. Початок:")
        print(text[:500])
else:
    print(f"❌ HTTP помилка: {response.status_code}")