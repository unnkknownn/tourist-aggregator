import pytest
import requests
import time

BASE_URL = "http://localhost:5000"  # Integration Service


class TestIntegrationAPI:
    """Интеграционные тесты: реальные запросы к API"""

    def test_health_endpoint(self):
        """Тест: проверка здоровья оркестратора"""
        resp = requests.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"

    def test_tours_endpoint(self):
        """Тест: получение списка туров"""
        resp = requests.get(f"{BASE_URL}/tours")
        assert resp.status_code == 200
        tours = resp.json()
        assert isinstance(tours, list)
        if len(tours) > 0:
            assert "id" in tours[0]
            assert "name" in tours[0]
            assert "price" in tours[0]

    def test_safe_book_success(self):
        """Тест: успешное бронирование через оркестратор"""
        payload = {
            "tour_id": 1,
            "user_name": "Integration Test",
            "seats": 1
        }
        resp = requests.post(f"{BASE_URL}/order/safe_book", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("status") == "success"
        assert data.get("order_status") == "PAID"
        assert data.get("booking_id") is not None
        assert data.get("total_amount") is not None

    def test_safe_book_invalid_tour(self):
        """Тест: бронирование несуществующего тура"""
        payload = {
            "tour_id": 999,
            "user_name": "Test User",
            "seats": 1
        }
        resp = requests.post(f"{BASE_URL}/order/safe_book", json=payload)
        assert resp.status_code == 404