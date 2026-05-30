import json
import time
import re
import sys
import traceback
import os
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Фікс для Windows консолі (щоб коректно відображалися українські літери та емодзі)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# ------------------------------------------------------------
# 1. Завантаження довідника населених пунктів
# ------------------------------------------------------------
with open("data/villages.json", "r", encoding="utf-8") as f:
    villages = json.load(f)

# ------------------------------------------------------------
# 2. Налаштування Selenium (безголовий режим)
# ------------------------------------------------------------
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

print("Запуск браузера...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 10)

all_records = []  # сюди зберемо всі знайдені записи

os.makedirs("html_dumps", exist_ok=True)

try:
    # ------------------------------------------------------------
    # 3. Відкриваємо сайт
    # ------------------------------------------------------------
    driver.get("https://hoe.com.ua/shutdown/all")
    time.sleep(2)

    # ------------------------------------------------------------
    # 4. Обробка вкладки "Аварійні" (TypeId=1)
    # ------------------------------------------------------------
    print("Обробляю аварійні відключення...")
    emergency_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panel_emergancy select.select-rem")))
    Select(emergency_select).select_by_value("12")
    time.sleep(1)  # чекаємо поки почнеться AJAX (з'явиться loader)
    WebDriverWait(driver, 30).until(lambda d: "loader" not in d.find_element(By.ID, "panel_emergancy").get_attribute("class"))
    time.sleep(1)  # пауза для повної відмальовки ДОМ

    # Розгортаємо всі "Показати вулиці"
    for btn in driver.find_elements(By.CSS_SELECTOR, "#panel_emergancy a.show-street"):
        try:
            btn.click()
            time.sleep(0.2)
        except:
            pass

    # Парсимо HTML
    emergency_html = driver.find_element(By.ID, "panel_emergancy").get_attribute("outerHTML")
    
    # Зберігаємо сирий HTML-зліпок для глибокого аналізу
    dump_filename = f"html_dumps/emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(dump_filename, "w", encoding="utf-8") as f:
        f.write(emergency_html)
        
    soup = BeautifulSoup(emergency_html, "html.parser")
    table = soup.find("table", class_="table-shutdowns")
    if table:
        rows = table.find_all("tr")
        i = 0
        while i < len(rows):
            row = rows[i]
            city_tag = row.find("p", class_="city")
            if not city_tag:
                i += 1
                continue

            city_text = city_tag.get_text(strip=True)
            # Визначаємо населений пункт за довідником
            settlement = None
            for v in villages:
                if v in city_text:
                    settlement = v
                    break
            if not settlement:
                i += 1
                continue

            # Тип (з наступної комірки)
            tds = row.find_all("td")
            work_type = "Аварійні"
            if len(tds) >= 2:
                work_type = tds[1].get_text(strip=True)

            # Дати та час
            stimes = row.find_all("div", class_="stime")
            created_date = stimes[0].get_text(strip=True) if len(stimes) > 0 else ""
            start_str = stimes[1].get_text(strip=True) if len(stimes) > 1 else ""
            end_str = stimes[2].get_text(strip=True) if len(stimes) > 2 else ""

            # Збираємо вулиці (наступний рядок з класом street)
            streets = []
            streets_detailed = []
            if i + 1 < len(rows) and "street" in rows[i + 1].get("class", []):
                street_row = rows[i + 1]
                for p in street_row.find_all("p"):
                    house_span = p.find("span", class_="house")
                    if house_span:
                        houses = house_span.get_text(strip=True)
                        house_span.decompose()  # Видаляємо тег з номерами, щоб залишилась лише вулиця
                        
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True).strip(" ,")
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            
                        streets.append(street_name)
                        streets_detailed.append({"name": street_name, "houses": houses})
                    else:
                        # Fallback (якщо структура зміниться)
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True)
                            streets.append(street_name)
                            full_text = p.get_text(separator=" ", strip=True)
                            houses = full_text.replace(street_name, "").strip(" ,")
                            streets_detailed.append({"name": street_name, "houses": houses})
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            if street_name:
                                streets.append(street_name)
                                streets_detailed.append({"name": street_name, "houses": ""})
                i += 2  # перестрибуємо рядок з вулицями
            else:
                i += 1

            # Формуємо запис
            all_records.append({
                "settlement": settlement,
                "type": work_type,
                "created_date": created_date,
                "start_datetime": start_str,
                "end_datetime": end_str,
                "streets": streets,
                "streets_detailed": streets_detailed
            })

    # ------------------------------------------------------------
    # 5. Обробка вкладки "Планові" (TypeId=2)
    # ------------------------------------------------------------
    print("Обробляю планові відключення...")
    planned_tab = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='#panel_planned']")))
    driver.execute_script("arguments[0].click();", planned_tab)
    time.sleep(1)

    planned_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panel_planned select.select-rem")))
    Select(planned_select).select_by_value("12")
    time.sleep(1)
    WebDriverWait(driver, 30).until(lambda d: "loader" not in d.find_element(By.ID, "panel_planned").get_attribute("class"))
    time.sleep(1)

    for btn in driver.find_elements(By.CSS_SELECTOR, "#panel_planned a.show-street"):
        try:
            btn.click()
            time.sleep(0.2)
        except:
            pass

    planned_html = driver.find_element(By.ID, "panel_planned").get_attribute("outerHTML")
    
    # Зберігаємо сирий HTML-зліпок для глибокого аналізу
    dump_filename = f"html_dumps/planned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(dump_filename, "w", encoding="utf-8") as f:
        f.write(planned_html)
        
    soup = BeautifulSoup(planned_html, "html.parser")
    table = soup.find("table", class_="table-shutdowns")
    if table:
        rows = table.find_all("tr")
        i = 0
        while i < len(rows):
            row = rows[i]
            city_tag = row.find("p", class_="city")
            if not city_tag:
                i += 1
                continue

            city_text = city_tag.get_text(strip=True)
            settlement = None
            for v in villages:
                if v in city_text:
                    settlement = v
                    break
            if not settlement:
                i += 1
                continue

            tds = row.find_all("td")
            work_type = "Планові"
            if len(tds) >= 2:
                work_type = tds[1].get_text(strip=True)

            stimes = row.find_all("div", class_="stime")
            created_date = stimes[0].get_text(strip=True) if len(stimes) > 0 else ""
            start_str = stimes[1].get_text(strip=True) if len(stimes) > 1 else ""
            end_str = stimes[2].get_text(strip=True) if len(stimes) > 2 else ""

            streets = []
            streets_detailed = []
            if i + 1 < len(rows) and "street" in rows[i + 1].get("class", []):
                street_row = rows[i + 1]
                for p in street_row.find_all("p"):
                    house_span = p.find("span", class_="house")
                    if house_span:
                        houses = house_span.get_text(strip=True)
                        house_span.decompose()  # Видаляємо тег з номерами, щоб залишилась лише вулиця
                        
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True).strip(" ,")
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            
                        streets.append(street_name)
                        streets_detailed.append({"name": street_name, "houses": houses})
                    else:
                        # Fallback (якщо структура зміниться)
                        strong = p.find("strong")
                        if strong:
                            street_name = strong.get_text(strip=True)
                            streets.append(street_name)
                            full_text = p.get_text(separator=" ", strip=True)
                            houses = full_text.replace(street_name, "").strip(" ,")
                            streets_detailed.append({"name": street_name, "houses": houses})
                        else:
                            street_name = p.get_text(strip=True).strip(" ,")
                            if street_name:
                                streets.append(street_name)
                                streets_detailed.append({"name": street_name, "houses": ""})
                i += 2
            else:
                i += 1

            all_records.append({
                "settlement": settlement,
                "type": work_type,
                "created_date": created_date,
                "start_datetime": start_str,
                "end_datetime": end_str,
                "streets": streets,
                "streets_detailed": streets_detailed
            })

    # ------------------------------------------------------------
    # 6. Зберігаємо результат
    # ------------------------------------------------------------
    with open("data/outages_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"✅ Готово! Зібрано {len(all_records)} записів. Дані збережено в data/outages_snapshot.json")

    # ------------------------------------------------------------
    # 7. Оновлення Архіву (archive.json)
    # ------------------------------------------------------------
    archive_path = "data/archive.json"
    archive_records = []
    try:
        with open(archive_path, "r", encoding="utf-8") as f:
            archive_records = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Створюємо унікальний підпис (ключ) для кожного запису без вулиць
    def get_rec_signature(rec):
        return f"{rec.get('settlement')}-{rec.get('type')}-{rec.get('start_datetime')}-{rec.get('end_datetime')}"

    # Створюємо словник для швидкого пошуку існуючих записів
    archive_dict = {get_rec_signature(r): r for r in archive_records}
    
    for rec in all_records:
        sig = get_rec_signature(rec)
        if sig in archive_dict:
            # Оновлюємо масив вулиць (можливо Обленерго додали нові будинки)
            archive_dict[sig]["streets"] = rec.get("streets", [])
            archive_dict[sig]["streets_detailed"] = rec.get("streets_detailed", [])
            # Оновлюємо last_seen_at, щоб бачити, коли запис ще був актуальним
            archive_dict[sig]["last_seen_at"] = datetime.now().isoformat()
        else:
            # Додаємо новий запис із фіксацією точного часу виявлення
            rec["first_seen_at"] = datetime.now().isoformat()
            rec["last_seen_at"] = datetime.now().isoformat()
            archive_records.append(rec)
            archive_dict[sig] = rec

    # Очищення старих записів (>40 днів)
    cutoff_date = datetime.now() - timedelta(days=40)
    filtered_archive = []
    for rec in archive_records:
        start_str = rec.get("start_datetime", "")
        # Фікс формату дати якщо немає пробілу
        if len(start_str) >= 5 and not " " in start_str[-6:]:
            start_str = f"{start_str[:-5]} {start_str[-5:]}"
            
        try:
            dt = datetime.strptime(start_str, "%d.%m.%Y %H:%M")
            if dt >= cutoff_date:
                filtered_archive.append(rec)
        except ValueError:
            filtered_archive.append(rec)

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(filtered_archive, f, ensure_ascii=False, indent=2)
    print(f"✅ Архів оновлено (всього {len(filtered_archive)} записів у archive.json)")


except Exception as e:
    print(f"\n❌ СТАЛАСЯ ПОМИЛКА під час збору даних: {e}")
    traceback.print_exc()
    driver.quit()
    sys.exit(1)
finally:
    try:
        driver.quit()
    except:
        pass