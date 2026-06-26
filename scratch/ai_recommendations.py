import json
import os
import sys
import re
import time

# Додаємо кореневу директорію в sys.path для імпорту formatter
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from formatter import ask_ai

def generate_recommendations():
    suspicious_path = "data/suspicious_base_streets.json"
    clean_streets_path = "data/clean_official_streets.json"
    
    if not os.path.exists(suspicious_path):
        print(f"[ERROR] Файл {suspicious_path} не знайдено.")
        return
        
    with open(suspicious_path, "r", encoding="utf-8") as f:
        suspicious_data = json.load(f)
        
    with open(clean_streets_path, "r", encoding="utf-8") as f:
        clean_data = json.load(f)

    # Збираємо плоский список непідтверджених вулиць для зручності
    flat_list = []
    for settlement, streets in suspicious_data.items():
        for street_name, info in streets.items():
            flat_list.append({
                "settlement": settlement,
                "street": street_name,
                "houses": info.get("houses", []),
                "type": info.get("type", "вулиця")
            })

    print(f"Знайдено {len(flat_list)} непідтверджених вулиць. Починаємо аналіз через ШІ...")
    
    # Групуємо вулиці по 15 штук, щоб не перевантажувати Gemini
    chunk_size = 15
    chunks = [flat_list[i:i + chunk_size] for i in range(0, len(flat_list), chunk_size)]
    
    all_recommendations = []
    
    for idx, chunk in enumerate(chunks):
        print(f"Обробляємо групу {idx+1}/{len(chunks)} ({len(chunk)} вулиць)...")
        
        # Формуємо список для промпту
        chunk_text = ""
        for i, item in enumerate(chunk):
            houses_str = ", ".join(item["houses"][:10]) if item["houses"] else "немає будинків"
            chunk_text += f"ID: {idx*chunk_size + i}\n"
            chunk_text += f"Населений пункт: {item['settlement']}\n"
            chunk_text += f"Вулиця: {item['street']}\n"
            chunk_text += f"Будинки: {houses_str}\n\n"

        prompt = f"""Ти — експерт-топоніміст та адміністратор адресного реєстру Старокостянтинівської міської громади (Хмельницька область, Україна).
Тобі надано перелік вулиць, які відсутні на картах OpenStreetMap, але є в базі відключень світла.
Проаналізуй кожну вулицю та дай свою рекомендацію щодо однієї з наступних дій:
- "approve" (затвердити як є) — якщо вулиця реальна (наприклад, вул. Високогірна, вул. Заставна є відомими реальними вулицями міста, просто не нанесеними на OSM).
- "rename" (перейменувати) — якщо в назві є друкарська помилка (наприклад, "Кобеева" -> "Кобєєва") або якщо вулицю було декомунізовано (наприклад, радянська назва має бути замінена на сучасну українську). Вкажи нову назву у полі "target_street".
- "delete" (видалити повністю) — якщо це явно технічний об'єкт, який не є вулицею, або вигадана адреса.

ПЕРЕЛІК ВУЛИЦЬ ДЛЯ АНАЛІЗУ:
{chunk_text}

Поверни відповідь строго у форматі JSON (масив об'єктів) без жодного markdown розмітки. Формат відповіді:
[
  {{
    "id": число (ID з запиту),
    "settlement": "назва населеного пункту",
    "street": "оригінальна назва вулиці",
    "action": "approve" / "rename" / "delete",
    "target_street": "нова назва (тільки для rename, інакше null)",
    "reason": "коротке пояснення українською мовою, чому обрано таку дію"
  }},
  ...
]"""

        # Виклик ШІ з паузою та повторами при 429
        response_text = None
        for attempt in range(3):
            try:
                time.sleep(3.0) # обов'язкова пауза
                response_text = ask_ai(prompt)
                if response_text:
                    break
            except Exception as e:
                print(f"[WARN] Помилка запиту (спроба {attempt+1}): {e}")
                time.sleep(5.0)

        if not response_text:
            print(f"[ERROR] Не вдалося отримати відповідь від ШІ для групи {idx+1}")
            continue

        try:
            # Очищуємо від markdown ```json
            cleaned_text = re.sub(r"^```(?:json)?\s*", "", response_text, flags=re.MULTILINE)
            cleaned_text = re.sub(r"\s*```$", "", cleaned_text, flags=re.MULTILINE).strip()
            
            chunk_recs = json.loads(cleaned_text)
            all_recommendations.extend(chunk_recs)
            print(f"Отримано {len(chunk_recs)} рекомендацій.")
        except Exception as e:
            print(f"[ERROR] Помилка парсингу JSON відповіді: {e}")
            # Запишемо сирий текст помилки для відладки
            with open(f"scratch/error_raw_chunk_{idx}.txt", "w", encoding="utf-8") as f:
                f.write(response_text)

    # Зберігаємо рекомендації у JSON
    recommendations_json_path = "data/review_recommendations.json"
    with open(recommendations_json_path, "w", encoding="utf-8") as f:
        json.dump(all_recommendations, f, ensure_ascii=False, indent=2)
    print(f"\n[AI-RECOMMENDATIONS] JSON збережено у {recommendations_json_path}")

    # Генеруємо гарний markdown звіт
    markdown_path = "data/review_recommendations.md"
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write("# Рекомендації ШІ щодо затвердження та очищення бази адрес\n\n")
        f.write("Цей звіт містить пропозиції Gemini API щодо кожної з 73 непідтверджених вулиць громади.\n\n")
        
        # Групуємо рекомендації по діях
        approve_list = [r for r in all_recommendations if r.get("action") == "approve"]
        rename_list = [r for r in all_recommendations if r.get("action") == "rename"]
        delete_list = [r for r in all_recommendations if r.get("action") == "delete"]
        
        f.write(f"## Статистика пропозицій:\n")
        f.write(f"* **Затвердити як є (approve):** {len(approve_list)}\n")
        f.write(f"* **Перейменувати / Виправити помилку (rename):** {len(rename_list)}\n")
        f.write(f"* **Видалити повністю (delete):** {len(delete_list)}\n\n")
        
        f.write("---\n\n")
        
        if rename_list:
            f.write("## 1. Рекомендується перейменувати / виправити помилку (rename):\n\n")
            f.write("| Населений пункт | Оригінальна назва | Пропонована назва | Обґрунтування |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for r in rename_list:
                f.write(f"| {r.get('settlement')} | **{r.get('street')}** | `{r.get('target_street')}` | {r.get('reason')} |\n")
            f.write("\n\n")
            
        if approve_list:
            f.write("## 2. Рекомендується затвердити як є (approve):\n\n")
            f.write("| Населений пункт | Назва вулиці | Обґрунтування |\n")
            f.write("| :--- | :--- | :--- |\n")
            for r in approve_list:
                f.write(f"| {r.get('settlement')} | **{r.get('street')}** | {r.get('reason')} |\n")
            f.write("\n\n")
            
        if delete_list:
            f.write("## 3. Рекомендується видалити повністю (delete):\n\n")
            f.write("| Населений пункт | Назва | Обґрунтування |\n")
            f.write("| :--- | :--- | :--- |\n")
            for r in delete_list:
                f.write(f"| {r.get('settlement')} | **{r.get('street')}** | {r.get('reason')} |\n")
            f.write("\n")
            
    print(f"[AI-RECOMMENDATIONS] Markdown звіт збережено у {markdown_path}")
    print("Рекомендації успішно сформовані.")

if __name__ == "__main__":
    generate_recommendations()
