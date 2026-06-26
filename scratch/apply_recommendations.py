import json
import os
from datetime import datetime

def apply_recommendations():
    recommendations_path = "data/review_recommendations.json"
    clean_streets_path = "data/clean_official_streets.json"
    suspicious_path = "data/suspicious_base_streets.json"
    corrections_path = "data/street_corrections.json"
    
    if not os.path.exists(recommendations_path):
        print(f"[ERROR] Файл {recommendations_path} не знайдено. Спочатку запустіть скрипт ai_recommendations.py")
        return
        
    with open(recommendations_path, "r", encoding="utf-8") as f:
        recommendations = json.load(f)
        
    with open(clean_streets_path, "r", encoding="utf-8") as f:
        clean_data = json.load(f)
        
    with open(suspicious_path, "r", encoding="utf-8") as f:
        suspicious_data = json.load(f)
        
    if os.path.exists(corrections_path):
        with open(corrections_path, "r", encoding="utf-8") as f:
            corrections_data = json.load(f)
    else:
        corrections_data = {}

    print(f"Зчитано {len(recommendations)} рекомендацій ШІ. Починаємо застосування...")
    
    approved_count = 0
    renamed_count = 0
    deleted_count = 0
    
    for rec in recommendations:
        settlement = rec.get("settlement")
        street = rec.get("street")
        action = rec.get("action")
        target_street = rec.get("target_street")
        
        # Перевіряємо чи є ця вулиця взагалі у сумнівних
        if settlement not in suspicious_data or street not in suspicious_data[settlement]:
            # Вже оброблена або немає
            continue
            
        street_info = suspicious_data[settlement][street]
        # Видаляємо причину незбігу для переносу в чисту базу
        if "reason" in street_info:
            del street_info["reason"]
            
        if action == "approve":
            # Переносимо в чисту базу як є
            if settlement not in clean_data:
                clean_data[settlement] = {}
            clean_data[settlement][street] = street_info
            
            # Видаляємо з сумнівних
            del suspicious_data[settlement][street]
            approved_count += 1
            
        elif action == "rename" and target_street:
            # Перейменовуємо та переносимо в чисту базу під новою назвою
            if settlement not in clean_data:
                clean_data[settlement] = {}
                
            clean_data[settlement][target_street] = street_info
            
            # Видаляємо стару назву з сумнівних
            del suspicious_data[settlement][street]
            
            # Додатково створюємо правило автоматичного перейменування для майбутніх зборів!
            # Ключ словника правил: с. Назва або м. Старокостянтинів
            sett_key = settlement.strip()
            if not sett_key.startswith("с. ") and not sett_key.startswith("м. "):
                if sett_key == "Старокостянтинів":
                    sett_key = "м. Старокостянтинів"
                else:
                    sett_key = "с. " + sett_key
                    
            if sett_key not in corrections_data:
                corrections_data[sett_key] = {}
                
            corrections_data[sett_key][street] = {
                "action": "rename",
                "target": target_street,
                "auto": True,
                "timestamp": datetime.now().isoformat()
            }
            renamed_count += 1
            
        elif action == "delete":
            # Просто видаляємо з сумнівних (не переносимо в чисту базу)
            del suspicious_data[settlement][street]
            deleted_count += 1

    # Очищуємо порожні населені пункти в suspicious_data
    empty_settlements = [s for s, str_dict in suspicious_data.items() if not str_dict]
    for s in empty_settlements:
        del suspicious_data[s]

    # Зберігаємо оновлені файли на диск
    with open(clean_streets_path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False, indent=2)
        
    with open(suspicious_path, "w", encoding="utf-8") as f:
        json.dump(suspicious_data, f, ensure_ascii=False, indent=2)
        
    with open(corrections_path, "w", encoding="utf-8") as f:
        json.dump(corrections_data, f, ensure_ascii=False, indent=2)

    print("\n=== РЕЗУЛЬТАТИ ЗАСТОСУВАННЯ ===")
    print(f"Затверджено (approve): {approved_count}")
    print(f"Перейменовано (rename): {renamed_count} (авто-правила додані у street_corrections.json)")
    print(f"Видалено (delete): {deleted_count}")
    print("Усі бази даних успішно оновлено!")

if __name__ == "__main__":
    apply_recommendations()
