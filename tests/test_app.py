import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest
from datetime import date, timedelta
from app import create_app
from app.db import get_db_connection

class NourishTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.app.config["TESTING"] = True

    def test_index_page(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ward Elders", resp.data)
        self.assertIn(b"Sister Missionaries", resp.data)

    def test_calendar_page(self):
        resp = self.client.get("/set/elders")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Ward Elders", resp.data)

    def test_calendar_api(self):
        resp = self.client.get("/api/calendar/elders?year=2026&month=11")
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertIn("days", json_data)
        self.assertEqual(json_data["set"]["slug"], "elders")
        self.assertGreater(len(json_data["days"]), 25)

    def test_booking_flow(self):
        # Pick a date 5 days from today
        future_date = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        
        post_data = {
            "meal_date": future_date,
            "meal_time": "5:30 PM",
            "host_name": "Brother & Sister Miller",
            "host_phone": "801-555-9876",
            "location_type": "home",
            "address": "456 Birch Lane",
            "notes": "Pot roast and potatoes",
            "host_email": "miller@example.com"
        }

        # 1. Sign up
        resp = self.client.post("/set/elders/book", data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Brother &amp; Sister Miller", resp.data)
        self.assertIn(b"Pot roast and potatoes", resp.data)
        self.assertIn(b"Add to Calendar", resp.data)

        # 2. Verify that date is now marked as 'booked' in the API
        resp_api = self.client.get(f"/api/calendar/elders?year={future_date[:4]}&month={int(future_date[5:7])}")
        days = resp_api.get_json()["days"]
        target_day = next((d for d in days if d["date"] == future_date), None)
        self.assertIsNotNone(target_day)
        self.assertEqual(target_day["status"], "booked")
        self.assertEqual(target_day["booking"]["host_name"], "Brother & Sister Miller")

        # 3. Test duplicate booking rejection
        resp_dup = self.client.post("/set/elders/book", data=post_data, follow_redirects=True)
        self.assertIn(b"Someone has already signed up", resp_dup.data)

    def test_admin_flow(self):
        # Admin login
        resp = self.client.post("/admin/login", data={"password": "nourish-admin"}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Admin Dashboard", resp.data)

        # View calendar admin page
        resp_cal = self.client.get("/admin/sets/1/calendar")
        self.assertEqual(resp_cal.status_code, 200)
        self.assertIn(b"Dinner Bookings", resp_cal.data)

        # Add a blackout date
        block_date = (date.today() + timedelta(days=12)).strftime("%Y-%m-%d")
        resp_block = self.client.post("/admin/sets/1/blackout/add", data={
            "blocked_date": block_date,
            "reason": "Zone Conference"
        }, follow_redirects=True)
        self.assertEqual(resp_block.status_code, 200)
        self.assertIn(b"Zone Conference", resp_block.data)

if __name__ == "__main__":
    unittest.main()
