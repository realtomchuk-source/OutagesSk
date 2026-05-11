from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import time

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

print("Запускаємо браузер...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    print("Відкриваємо сайт...")
    driver.get("https://hoe.com.ua/shutdown/all")
    wait = WebDriverWait(driver, 10)

    # --- Вкладка АВАРІЙНІ ---
    print("Вибираємо Старокостянтинівський РЕМ у вкладці 'Аварійні'...")
    # Знаходимо select у першій формі (аварійні)
    emergency_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panel_emergancy select.select-rem")))
    Select(emergency_select).select_by_value("12")

    # Чекаємо, поки з'явиться таблиця або повідомлення про відсутність даних
    time.sleep(3)  # даємо час на AJAX
    # Розгортаємо всі "Показати вулиці"
    show_buttons = driver.find_elements(By.CSS_SELECTOR, "#panel_emergancy a.show-street")
    for btn in show_buttons:
        try:
            btn.click()
            time.sleep(0.2)
        except:
            pass

    emergency_html = driver.find_element(By.ID, "panel_emergancy").get_attribute("outerHTML")
    with open("test_emergency.html", "w", encoding="utf-8") as f:
        f.write(emergency_html)
    print("✅ Аварійні збережено в test_emergency.html")

    # --- Вкладка ПЛАНОВІ ---
    print("Переходимо на вкладку 'Планові'...")
    planned_tab = driver.find_element(By.CSS_SELECTOR, "a[href='#panel_planned']")
    planned_tab.click()
    time.sleep(1)

    print("Вибираємо Старокостянтинівський РЕМ у вкладці 'Планові'...")
    planned_select = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#panel_planned select.select-rem")))
    Select(planned_select).select_by_value("12")
    time.sleep(3)

    show_buttons = driver.find_elements(By.CSS_SELECTOR, "#panel_planned a.show-street")
    for btn in show_buttons:
        try:
            btn.click()
            time.sleep(0.2)
        except:
            pass

    planned_html = driver.find_element(By.ID, "panel_planned").get_attribute("outerHTML")
    with open("test_planned.html", "w", encoding="utf-8") as f:
        f.write(planned_html)
    print("✅ Планові збережено в test_planned.html")

finally:
    driver.quit()