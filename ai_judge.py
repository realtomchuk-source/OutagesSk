import json
import os
import re
import difflib
from formatter import ask_ai

class AIJudge:
    def __init__(self, 
                 clean_streets_path="data/clean_official_streets.json", 
                 corrections_path="data/street_corrections.json"):
        self.clean_streets_path = clean_streets_path
        self.corrections_path = corrections_path
        self.official_data = {}
        self.corrections = {}
        self.load_data()
        
    def load_data(self):
        if os.path.exists(self.clean_streets_path):
            with open(self.clean_streets_path, "r", encoding="utf-8") as f:
                self.official_data = json.load(f)
        if os.path.exists(self.corrections_path):
            with open(self.corrections_path, "r", encoding="utf-8") as f:
                self.corrections = json.load(f)

    def save_corrections(self):
        try:
            with open(self.corrections_path, "w", encoding="utf-8") as f:
                json.dump(self.corrections, f, ensure_ascii=False, indent=2)
            print("[AI-JUDGE] Файл street_corrections.json оновлено.")
        except Exception as e:
            print(f"[AI-JUDGE] [ERROR] Не вдалося зберегти street_corrections.json: {e}")

    def advanced_normalize(self, name):
        if not name:
            return ""
        name = name.lower().strip()
        name = re.sub(r"[’'`\u2019\u2018\u02bc]", "'", name)
        name = name.replace("i", "і").replace("e", "е")
        types = ["вулиця", "вул", "провулок", "пров", "проспект", "просп", "площа", "пл", "проїзд", "тупик"]
        for t in types:
            name = re.sub(r"^\b" + t + r"\.?", "", name).strip()
            name = re.sub(r"\b" + t + r"\.?$", "", name).strip()
        name = re.sub(r"(\d+)-(й|ша|а|е|я|го|ти)\b", r"\1", name)
        name = re.sub(r"[^\w\s\-\']", "", name)
        words = [w.strip() for w in name.split() if w.strip()]
        words.sort()
        return " ".join(words)

    def get_candidates(self, original_settlement, street_name):
        """Підбирає потенційних кандидатів на вулицю по всій громаді."""
        candidates = []
        norm_search = self.advanced_normalize(street_name)
        
        # 1. Завжди додаємо всі вулиці з оригінально вказаного села (це найімовірніше місце)
        orig_key = None
        for k in self.official_data.keys():
            if original_settlement.lower() in k.lower():
                orig_key = k
                break
                
        if orig_key:
            for s_name, s_info in self.official_data[orig_key].items():
                candidates.append({
                    "settlement": orig_key,
                    "street": s_name,
                    "houses": s_info.get("houses", []),
                    "score": 0.5  # Базовий пріоритет для свого села
                })
                
        # 2. Шукаємо схожі назви по всій громаді
        for sett, streets in self.official_data.items():
            if sett == orig_key:
                continue # вже додали
            for s_name, s_info in streets.items():
                norm_official = self.advanced_normalize(s_name)
                # Розрахунок коефіцієнта схожості
                score = difflib.SequenceMatcher(None, norm_search, norm_official).ratio()
                
                # Також перевіряємо чи є наше прізвище частиною назви в базі (subname match)
                if norm_search in norm_official.split() or norm_official in norm_search.split():
                    score = max(score, 0.85)
                    
                if score >= 0.45:  # Тільки кандидати з мінімальним збігом
                    candidates.append({
                        "settlement": sett,
                        "street": s_name,
                        "houses": s_info.get("houses", []),
                        "score": score
                    })
                    
        # Сортуємо кандидатів за спаданням схожості і беремо максимум 7
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:7]

    def ask_gemini_judge(self, original_settlement, street_name, houses_list, candidates):
        if not candidates:
            return None
            
        candidates_str = ""
        for i, cand in enumerate(candidates):
            houses_preview = ", ".join(cand["houses"][:15])
            if len(cand["houses"]) > 15:
                houses_preview += "..."
            candidates_str += f"{i+1}. Село/Місто: {cand['settlement']}, Вулиця: {cand['street']}, Будинки в базі: [{houses_preview}]\n"
            
        houses_str = ", ".join(houses_list) if houses_list else "немає номерів"

        prompt = f"""Ти — інтелектуальний суддя-верифікатор адрес Старокостянтинівської громади (Україна).
Тобі надано нерозпізнану адресу з відключення світла, яку парсер не зміг верифікувати автоматично.
Визнач правильну адресу серед наданих кандидатів.

ОРИГІНАЛЬНІ ДАНІ ВІД ОБЛЕНЕРГО:
- Оригінально вказане село: {original_settlement}
- Нерозпізнана вулиця: {street_name}
- Номери будинків у відключенні: {houses_str}

СПИСОК ОФІЦІЙНИХ КАНДИДАТІВ У ГРОМАДІ:
{candidates_str}

ПРАВИЛА ВЕРИФІКАЦІЇ:
1. Пріоритет №1 — це збіг будинків! Якщо оригінальні номери будинків ({houses_str}) є в базі якогось кандидата, це майже 100% доказ приналежності саме до цього кандидата.
2. Звертай увагу на очевидні скорочення або друкарські помилки (наприклад, "Хм-го" -> "Хмельницького", "Украінки" -> "Українки").
3. Якщо жоден кандидат не підходить, або рівень сумніву занадто великий, вкажи "matched": false.
4. Поверни відповідь СТРОГО у форматі JSON без будь-яких розміток markdown чи додаткового тексту.

Формат відповіді JSON:
{{
  "matched": true/false,
  "confidence": число від 0.0 до 1.0 (рівень впевненості),
  "target_settlement": "назва офіційного населеного пункту (наприклад, с. Самчики)",
  "target_street": "офіційна назва вулиці (наприклад, вул. Миру)",
  "explanation": "коротке пояснення рішення"
}}"""

        try:
            response_text = ask_ai(prompt)
            if not response_text:
                return None
                
            # Очищуємо текст від можливої markdown розмітки ```json ... ```
            cleaned_text = re.sub(r"^```(?:json)?\s*", "", response_text, flags=re.MULTILINE)
            cleaned_text = re.sub(r"\s*```$", "", cleaned_text, flags=re.MULTILINE).strip()
            
            result = json.loads(cleaned_text)
            return result
        except Exception as e:
            print(f"[AI-JUDGE] [ERROR] Помилка виклику Gemini API або парсингу JSON: {e}")
            return None

    def judge_sandbox_records(self, records):
        """Проходить по записах відключень і виправляє ті, що потрапили в Пісочницю."""
        sandbox_count = 0
        corrected_count = 0
        
        for rec in records:
            settlement = rec.get("settlement")
            if settlement != "Пісочниця":
                continue
                
            sandbox_count += 1
            original_settlement = rec.get("original_settlement", "")
            
            # Беремо детальну інформацію про нерозпізнані вулиці
            streets_detailed = rec.get("streets_detailed", [])
            if not streets_detailed:
                continue
                
            new_streets_detailed = []
            
            for s_det in streets_detailed:
                s_name = s_det.get("name", "")
                s_houses_str = s_det.get("houses", "")
                s_houses = [h.strip() for h in s_houses_str.split(",") if h.strip()]
                
                # 1. Перевіряємо чи є готове правило в corrections
                # Ключ правила: "Пісочниця" -> "назва вулиці"
                rule = self.corrections.get("Пісочниця", {}).get(s_name)
                if rule and rule.get("action") == "move_to_settlement":
                    target_sett = rule.get("target_settlement") or rule.get("target_settlements")[0]
                    target_street = rule.get("target_street")
                    print(f"[AI-JUDGE] [КЕШ-ПРАВИЛО] Виправлено '{s_name}' -> '{target_street}' у '{target_sett}'")
                    
                    # Змінюємо запис відключення
                    rec["settlement"] = target_sett
                    s_det["name"] = target_street
                    corrected_count += 1
                    new_streets_detailed.append(s_det)
                    continue
                    
                # 2. Якщо правила немає — підбираємо кандидатів по всій громаді
                candidates = self.get_candidates(original_settlement, s_name)
                
                # 3. Викликаємо Gemini
                decision = self.ask_gemini_judge(original_settlement, s_name, s_houses, candidates)
                
                if decision and decision.get("matched") and decision.get("confidence", 0.0) >= 0.90:
                    target_sett = decision.get("target_settlement")
                    target_street = decision.get("target_street")
                    explanation = decision.get("explanation")
                    
                    print(f"[AI-JUDGE] [AI-ВЕРДИКТ] Успішно! Вулицю '{s_name}' з '{original_settlement}' перенаправлено до '{target_sett}' -> '{target_street}' (Впевненість: {decision.get('confidence')*100}%). Пояснення: {explanation}")
                    
                    # Записуємо нове автоматичне правило
                    if "Пісочниця" not in self.corrections:
                        self.corrections["Пісочниця"] = {}
                    
                    self.corrections["Пісочниця"][s_name] = {
                        "action": "move_to_settlement",
                        "target_settlements": [target_sett],
                        "target_settlement": target_sett,
                        "target_street": target_street,
                        "auto": True,
                        "timestamp": datetime.now().isoformat() if 'datetime' in globals() else "2026-06-26T20:12:00Z"
                    }
                    self.save_corrections()
                    
                    # Змінюємо запис відключення
                    rec["settlement"] = target_sett
                    s_det["name"] = target_street
                    corrected_count += 1
                    new_streets_detailed.append(s_det)
                else:
                    print(f"[AI-JUDGE] Не вдалося впевнено розпізнати '{s_name}' з '{original_settlement}'. Залишається в Пісочниці.")
                    new_streets_detailed.append(s_det)
                    
            rec["streets_detailed"] = new_streets_detailed
            # Оновлюємо також простий список вулиць
            rec["streets"] = [s.get("name") for s in new_streets_detailed]
            
        print(f"\n[AI-JUDGE] Завершено обробку Пісочниці. Перевірено сумнівних записів: {sandbox_count}. Автовиправлено ШІ: {corrected_count}")
        return records
