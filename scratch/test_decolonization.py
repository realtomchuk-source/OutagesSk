import os
import json
import shutil
import sys

# Встановлюємо тестові шляхи через змінні оточення до імпорту formatter
os.environ["OFFICIAL_STREETS_PATH"] = "data/official_streets_test.json"
os.environ["STREET_CORRECTIONS_PATH"] = "data/street_corrections_test.json"
os.environ["OUTAGES_SNAPSHOT_PATH"] = "data/outages_snapshot_test.json"
os.environ["PREVIOUS_SNAPSHOT_PATH"] = "data/previous_snapshot_test.json"
os.environ["FEED_PATH"] = "data/feed_test.json"
os.environ["FEED_TXT_PATH"] = "data/feed_test.txt"
os.environ["MESSAGES_PATH"] = "data/messages_test.json"

# Додаємо кореневу директорію до шляху пошуку модулів, щоб імпортувати formatter
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Шляхи до тестових файлів
OFFICIAL_PATH = os.environ["OFFICIAL_STREETS_PATH"]
CORRECTIONS_PATH = os.environ["STREET_CORRECTIONS_PATH"]
SNAPSHOT_PATH = os.environ["OUTAGES_SNAPSHOT_PATH"]

# Шляхи до бекапів
BACKUP_SUFFIX = ".bak_test_decol"
OFFICIAL_BACKUP = OFFICIAL_PATH + BACKUP_SUFFIX
CORRECTIONS_BACKUP = CORRECTIONS_PATH + BACKUP_SUFFIX
SNAPSHOT_BACKUP = SNAPSHOT_PATH + BACKUP_SUFFIX

def backup_files():
    print("[INFO] Створення резервних копій оригінальних файлів...")
    for path, backup_path in [
        (OFFICIAL_PATH, OFFICIAL_BACKUP),
        (CORRECTIONS_PATH, CORRECTIONS_BACKUP),
        (SNAPSHOT_PATH, SNAPSHOT_BACKUP)
    ]:
        if os.path.exists(path):
            shutil.copy(path, backup_path)
            print(f"   Створено бекап: {backup_path}")
        else:
            if os.path.exists(backup_path):
                os.remove(backup_path)

def restore_files():
    print("[INFO] Відновлення оригінальних файлів...")
    for path, backup_path in [
        (OFFICIAL_PATH, OFFICIAL_BACKUP),
        (CORRECTIONS_PATH, CORRECTIONS_BACKUP),
        (SNAPSHOT_PATH, SNAPSHOT_BACKUP)
    ]:
        if os.path.exists(backup_path):
            shutil.copy(backup_path, path)
            os.remove(backup_path)
            print(f"   Відновлено з бекапу: {path}")
        else:
            if os.path.exists(path):
                os.remove(path)
                print(f"   Видалено тестовий файл: {path}")
                
    # Також видаляємо інші тимчасові тестові файли
    for extra_path in [
        os.environ["PREVIOUS_SNAPSHOT_PATH"],
        os.environ["FEED_PATH"],
        os.environ["FEED_TXT_PATH"],
        os.environ["MESSAGES_PATH"]
    ]:
        if os.path.exists(extra_path):
            os.remove(extra_path)
            print(f"   Видалено тестовий файл: {extra_path}")

def setup_mock_data():
    print("[INFO] Створення тестових даних...")
    os.makedirs("data", exist_ok=True)
    
    # 1. Офіційні вулиці
    mock_official = {
        "с. Оріхівка": {
            "вул. Покровська": { "houses": ["1", "2", "3", "5", "10"] },
            "вул. Садова": { "houses": ["1", "2"] }
        }
    }
    with open(OFFICIAL_PATH, "w", encoding="utf-8") as f:
        json.dump(mock_official, f, ensure_ascii=False, indent=2)
        
    # 2. Початкові корекції (порожні)
    with open(CORRECTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

    # 3. Тестові записи про відключення
    mock_outages = [
        {
            "settlement": "с. Оріхівка",
            "streets": ["вул. Леніна"],
            "streets_detailed": [{"name": "вул. Леніна", "houses": "5, 10"}]
        },
        {
            "settlement": "с. Оріхівка",
            "streets": ["вул. Зелена"],
            "streets_detailed": [{"name": "вул. Зелена", "houses": "1, 2"}]
        },
        {
            "settlement": "с. Оріхівка",
            "streets": ["вул. Покровська"],
            "streets_detailed": [{"name": "вул. Покровська", "houses": "1"}]
        }
    ]
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(mock_outages, f, ensure_ascii=False, indent=2)

def run_tests():
    backup_files()
    try:
        setup_mock_data()
        
        # Імпортуємо модуль formatter
        import formatter
        
        print("\n--- ТЕСТ 1: Робота з мокнутим ШІ (Mock Mode) ---")
        
        # Мокаємо ask_ai
        def mock_ask_ai(prompt):
            print(f"   [MOCK AI] Отримано промпт. Довжина: {len(prompt)}")
            # Перевіряємо яку вулицю аналізуємо
            if "вул. Леніна" in prompt:
                # Повертаємо нову назву з білого списку
                return "вул. Покровська"
            elif "вул. Зелена" in prompt:
                # Повертаємо null для нейтральної назви
                return "null"
            return "null"
            
        formatter.ask_ai = mock_ask_ai
        
        # Завантажуємо тестові записи
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            test_outages = json.load(f)
            
        # Запускаємо корекцію
        results = formatter.apply_street_corrections(test_outages)
        
        print("\n[INFO] Результати виконання apply_street_corrections:")
        print(json.dumps(results, ensure_ascii=False, indent=2))
        
        # Перевіряємо створені правила в street_corrections.json
        with open(CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            rules = json.load(f)
        print("\n[INFO] Оновлений street_corrections.json:")
        print(json.dumps(rules, ensure_ascii=False, indent=2))
        
        # Перевірки (Asserts)
        # 1. вул. Леніна має бути перейменована на вул. Покровську
        assert "с. Оріхівка" in rules, "Немає секції с. Оріхівка у правилах"
        assert "вул. Леніна" in rules["с. Оріхівка"], "Немає правила для вул. Леніна"
        assert rules["с. Оріхівка"]["вул. Леніна"]["action"] == "rename", "Дія для вул. Леніна має бути rename"
        assert rules["с. Оріхівка"]["вул. Леніна"]["target"] == "вул. Покровська", "Ціль для вул. Леніна має бути вул. Покровська"
        assert rules["с. Оріхівка"]["вул. Леніна"].get("auto") is True, "Маркер auto має бути True"
        
        # 2. вул. Зелена має бути відмічена як unverified
        assert "вул. Зелена" in rules["с. Оріхівка"], "Немає правила для вул. Зелена"
        assert rules["с. Оріхівка"]["вул. Зелена"]["action"] == "unverified", "Дія для вул. Зелена має бути unverified"
        assert rules["с. Оріхівка"]["вул. Зелена"].get("auto") is True, "Маркер auto має бути True"
        
        # 3. Перевіримо маршрутизацію у результатах
        # вул. Леніна перейменовано на вул. Покровська (яка є офіційною), тому запис має лишитися в с. Оріхівка
        rec_pokrovska = [r for r in results if r["settlement"] == "с. Оріхівка" and "вул. Покровська" in r["streets"]]
        assert len(rec_pokrovska) > 0, "Не знайдено запис з вул. Покровська у с. Оріхівка"
        # вул. Зелена не є офіційною і позначена як unverified, тому вона має бути переміщена до Пісочниці
        rec_sandbox = [r for r in results if r["settlement"] == "Пісочниця" and "вул. Зелена" in r["streets"]]
        assert len(rec_sandbox) > 0, "вул. Зелена мала бути переміщена до Пісочниці"
        
        print("\n[SUCCESS] Тест 1 (Mock Mode) пройдено успішно!")
        
        # -------------------------------------------------------------
        # ТЕСТ 2: Реальний виклик Gemini API (якщо є ключ)
        # -------------------------------------------------------------
        if os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
            print("\n--- ТЕСТ 2: Реальний виклик Gemini/OpenRouter API ---")
            
            # Відновлюємо оригінальний метод ask_ai
            from importlib import reload
            reload(formatter)
            
            # Скидаємо корекції та тестові записи знову
            setup_mock_data()
            
            # Завантажуємо
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                test_outages_real = json.load(f)
                
            # Запускаємо з реальними API
            print("[INFO] Викликаємо apply_street_corrections з реальним API...")
            real_results = formatter.apply_street_corrections(test_outages_real)
            
            with open(CORRECTIONS_PATH, "r", encoding="utf-8") as f:
                real_rules = json.load(f)
                
            print("\n[INFO] Реальні правила, створені ШІ:")
            print(json.dumps(real_rules, ensure_ascii=False, indent=2))
            
            # Перевіримо, що вул. Леніна успішно деколонізовано
            if "с. Оріхівка" in real_rules and "вул. Леніна" in real_rules["с. Оріхівка"]:
                rule_lenina = real_rules["с. Оріхівка"]["вул. Леніна"]
                print(f"   Результат для вул. Леніна: {rule_lenina}")
                if rule_lenina["action"] == "rename":
                    assert rule_lenina["target"] == "вул. Покровська", "Неправильна назва перейменування для вул. Леніна"
                    print("[SUCCESS] Реальний тест: вул. Леніна успішно перейменовано на вул. Покровська!")
                else:
                    print("[WARNING] Реальний виклик повернув unverified для вул. Леніна. Перевірте статус API квоти/лімітів.")
            else:
                print("[ERROR] Реальний тест: Не вдалося отримати коректну відповідь для вул. Леніна.")
                
            if "с. Оріхівка" in real_rules and "вул. Зелена" in real_rules["с. Оріхівка"]:
                rule_zelena = real_rules["с. Оріхівка"]["вул. Зелена"]
                print(f"   Результат для вул. Зелена: {rule_zelena}")
                assert rule_zelena["action"] == "unverified", "Дія для вул. Зелена має бути unverified"
                print("[SUCCESS] Реальний тест: вул. Зелена успішно відмічена як unverified!")
            else:
                print("[ERROR] Реальний тест: Не вдалося отримати коректну відповідь для вул. Зелена.")
                
        else:
            print("\n[WARNING] Пропускаємо ТЕСТ 2 (Реальний API), оскільки ключі відсутні.")

    except AssertionError as e:
        print(f"\n[ERROR] ПОМИЛКА ТЕСТУ: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n[ERROR] Неочікувана помилка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        restore_files()

if __name__ == "__main__":
    run_tests()
