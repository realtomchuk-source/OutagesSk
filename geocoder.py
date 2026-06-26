import os
import json
import re
import time
import requests

class OSMGeocoder:
    def __init__(self, cache_path="data/geocoding_cache.json"):
        self.cache_path = cache_path
        self.cache = {}
        self.load_cache()
        # z.overpass-api.de - єдине дзеркало, яке стабільно працює для України
        self.overpass_url = "https://z.overpass-api.de/api/interpreter"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
        
    def load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"[GEOCODER] Завантажено {len(self.cache)} записів із кешу.")
            except Exception as e:
                print(f"[GEOCODER] Помилка завантаження кешу: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def save_cache(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[GEOCODER] Помилка збереження кешу: {e}")

    def clean_street_name_for_query(self, name):
        """Очищує назву вулиці від типів для гнучкого пошуку регулярним виразом."""
        if not name:
            return ""
        name = name.lower().strip()
        types = ["вулиця", "вул.", "вул", "провулок", "пров.", "пров", "проспект", "площа", "проїзд", "тупик"]
        for t in types:
            if name.startswith(t):
                name = name[len(t):].strip()
            elif name.endswith(t):
                name = name[:-len(t)].strip()
        name = name.replace(".", "").strip()
        name = re.sub(r"[’'`\u2019\u2018\u02bc]", "", name)
        name = re.sub(r"(\d+)-(й|ша|а|е|я|го|ти)\b", r"\1", name)
        return name.strip()

    def format_settlement_name(self, settlement):
        """Приводить назву села/міста до чистого імені для пошуку node["name"="..."] в OSM."""
        if not settlement:
            return "Старокостянтинів"
        settlement = settlement.strip()
        settlement = re.sub(r"^(с\.|м\.|c\.|m\.)\s*", "", settlement).strip()
        return settlement

    def verify_street_in_settlement(self, settlement, street_name):
        """
        Перевіряє через Overpass API, чи існує вулиця в радіусі довкола точки населеного пункту.
        """
        sett_formatted = self.format_settlement_name(settlement)
        street_clean = self.clean_street_name_for_query(street_name)
        
        if not street_clean:
            return False
            
        cache_key = f"{sett_formatted}||{street_clean}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        is_city = (sett_formatted == "Старокостянтинів")
        radius = 5000 if is_city else 2000

        query = f"""[out:json][timeout:15];
node["name"="{sett_formatted}"]["place"~"city|town|village|hamlet"]->.center;
way(around.center:{radius})["highway"]["name"~"{street_clean}",i];
out tags;"""

        attempts = 3
        result = False
        success = False

        for attempt in range(attempts):
            print(f"[GEOCODER] Запит (Спроба {attempt+1}/{attempts}) до {self.overpass_url}: '{street_name}' у радіусі {radius}м від '{sett_formatted}'...")
            
            try:
                # Пауза перед запитом
                time.sleep(2.0)
                response = requests.get(self.overpass_url, params={"data": query}, headers=self.headers, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    elements = data.get("elements", [])
                    if elements:
                        result = True
                        print(f"[GEOCODER] ЗНАЙДЕНО в OSM: '{street_name}' у '{sett_formatted}'")
                    else:
                        result = False
                        print(f"[GEOCODER] НЕ знайдено в OSM: '{street_name}' у '{sett_formatted}'")
                    success = True
                    break
                elif response.status_code == 429:
                    print(f"[GEOCODER] [ПОПЕРЕДЖЕННЯ] Сервер повернув 429 (ліміт запитів). Очікуємо 5 секунд перед повтором...")
                    time.sleep(5.0)
                else:
                    print(f"[GEOCODER] [ПОПЕРЕДЖЕННЯ] Сервер повернув статус {response.status_code}. Очікуємо 3 секунди...")
                    time.sleep(3.0)
            except Exception as e:
                print(f"[GEOCODER] [ERROR] Помилка запиту: {e}. Очікуємо 3 секунди...")
                time.sleep(3.0)

        if not success:
            print(f"[GEOCODER] [ERROR] Усі спроби геокодування для '{street_name}' у '{sett_formatted}' завершилися невдачею.")
            return False

        # Зберігаємо тільки успішні відповіді в кеш
        self.cache[cache_key] = result
        self.save_cache()
        return result
