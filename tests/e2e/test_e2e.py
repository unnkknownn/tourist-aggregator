import pytest
import requests
import time

BASE_URL = "http://localhost:5000"


class TestE2EFullFlow:
    """E2E тест: полный цикл от тура до оплаты"""

    def test_full_flow_create_tour_and_book(self):
        """Сценарий: создаём тур → бронируем → проверяем результат"""

        # 1. Проверяем, что оркестратор жив
        health = requests.get(f"{BASE_URL}/health")
        assert health.status_code == 200

        # 2. Получаем список туров (хотя бы один должен быть)
        tours_resp = requests.get(f"{BASE_URL}/tours")
        assert tours_resp.status_code == 200
        tours = tours_resp.json()
        
        if len(tours) == 0:
            pytest.skip("Нет туров в базе, пропускаем E2E тест")

        # 3. Бронируем первый тур
        tour = tours[0]
        payload = {
            "tour_id": tour["id"],
            "user_name": "E2E Test User",
            "seats": 1
        }
        book_resp = requests.post(f"{BASE_URL}/order/safe_book", json=payload)
        assert book_resp.status_code == 201
        data = book_resp.json()
        
        # 4. Проверяем результат
        assert data["status"] == "success"
        assert data["order_status"] == "PAID"
        assert data["booking_id"] is not None
        assert data["total_amount"] == tour["price"]
        
        print(f"\n✅ E2E тест пройден: заказ {data['order_id']} на сумму {data['total_amount']} USD")

    def test_e2e_multiple_bookings(self):
        """Тест: несколько бронирований подряд"""
        results = []
        for i in range(2):
            payload = {
                "tour_id": 1,
                "user_name": f"User_{i}",
                "seats": 1
            }
            resp = requests.post(f"{BASE_URL}/order/safe_book", json=payload)
            results.append(resp.status_code == 201)
        
        assert all(results), "Не все бронирования прошли успешно"