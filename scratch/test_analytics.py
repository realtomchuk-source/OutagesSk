import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import json
from analytics import normalize_settlement_name, generate_weekly_report

class TestAnalytics(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize_settlement_name("Старокостянтинів"), "м. Старокостянтинів")
        self.assertEqual(normalize_settlement_name("м. Старокостянтинів"), "м. Старокостянтинів")
        self.assertEqual(normalize_settlement_name("  Старокостянтинів  "), "м. Старокостянтинів")
        self.assertEqual(normalize_settlement_name("Самчики"), "с. Самчики")
        self.assertEqual(normalize_settlement_name("с. Самчики"), "с. Самчики")
        self.assertEqual(normalize_settlement_name("Пісочниця"), "Пісочниця")
        self.assertEqual(normalize_settlement_name("Невідомо"), "Невідомо")
        self.assertEqual(normalize_settlement_name(""), "Невідомо")

    def test_weekly_run(self):
        print("Тестування генерації звіту...")
        # Run report generation (this will print stats and might call Gemini if key is present)
        # We ensure it doesn't crash
        generate_weekly_report()
        
        # Verify that data/analytics.json was created/updated
        self.assertTrue(os.path.exists("data/analytics.json"))
        with open("data/analytics.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("date", data)
            self.assertIn("content", data)
            print("Analytics content preview:")
            print(data["content"][:300])

if __name__ == "__main__":
    unittest.main()
