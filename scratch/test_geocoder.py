from geocoder import OSMGeocoder
import os
import time

def test_geocoder():
    test_cache = "data/geocoding_test_cache.json"
    if os.path.exists(test_cache):
        os.remove(test_cache)
        
    geocoder = OSMGeocoder(cache_path=test_cache)
    
    # 1. Перевірка реальної вулиці в місті
    print("\nТест 1: Реальна вулиця Михайла Рудяка у Старокостянтинові...")
    res1 = geocoder.verify_street_in_settlement("м. Старокостянтинів", "Рудяка")
    print(f"Результат (очікується True): {res1}")
    
    time.sleep(3.0) # Запобігаємо 429 лімітам
    
    # 2. Перевірка реальної вулиці в селі
    print("\nТест 2: Реальна вулиця Фурмана у с. Самчики...")
    res2 = geocoder.verify_street_in_settlement("с. Самчики", "вулиця Фурмана")
    print(f"Результат (очікується True): {res2}")
    
    time.sleep(3.0) # Запобігаємо 429 лімітам
    
    # 3. Перевірка неіснуючої вулиці
    print("\nТест 3: Неіснуюча вулиця у с. Самчики...")
    res3 = geocoder.verify_street_in_settlement("с. Самчики", "Неіснуюча вулиця")
    print(f"Результат (очікується False): {res3}")
    
    time.sleep(3.0) # Запобігаємо 429 лімітам
    
    # 4. Перевірка кешування (має виконатися миттєво без виклику мережі)
    print("\nТест 4: Повторний виклик для вулиці Фурмана у с. Самчики (перевірка кешу)...")
    start_time = os.times()[4]
    res4 = geocoder.verify_street_in_settlement("с. Самчики", "вулиця Фурмана")
    end_time = os.times()[4]
    elapsed = end_time - start_time
    print(f"Результат (очікується True): {res4}")
    print(f"Час виконання повторного запиту: {elapsed:.6f} секунд")
    
    if os.path.exists(test_cache):
        os.remove(test_cache)

if __name__ == "__main__":
    test_geocoder()
