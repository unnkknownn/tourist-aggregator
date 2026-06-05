import logging
import json
import time
import uuid
from datetime import datetime
from functools import wraps
from enum import Enum

from flask import Flask, request, jsonify
from flask_cors import CORS
from pythonjsonlogger import jsonlogger
import requests

# ========= НАСТРОЙКА ЛОГИРОВАНИЯ =========
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
    rename_fields={"levelname": "severity", "asctime": "timestamp"}
)
logHandler.setFormatter(formatter)
logger = logging.getLogger("tourist_aggregator")
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# Также пишем в файл
fileHandler = logging.FileHandler("logs/integration.log")
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)

# ========= СОЗДАЁМ ПРИЛОЖЕНИЕ С CORS =========
app = Flask(__name__)
CORS(app)  # РАЗРЕШАЕТ ЗАПРОСЫ ИЗ БРАУЗЕРА

# Адреса сервисов
CATALOG_URL = "http://catalog-service:5001"
BOOKING_URL = "http://booking-service:5002"
PAYMENT_URL = "http://payment-service:5003"

# ========= RETRY =========
def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Попытка {attempt+1}/{max_attempts} вызвать {func.__name__}")
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Ошибка: {e}. Попытка {attempt+1} не удалась")
                    if attempt == max_attempts - 1:
                        raise
                    wait = delay * (2 ** attempt)
                    logger.info(f"Ждём {wait} секунд...")
                    time.sleep(wait)
            return None
        return wrapper
    return decorator

# ========= CIRCUIT BREAKER =========
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout=30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout:
                logger.info("Circuit Breaker: переходим в HALF_OPEN")
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit Breaker OPEN")
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise e

payment_circuit_breaker = CircuitBreaker(failure_threshold=2, timeout=15)

# ========= STATE MACHINE =========
class OrderStatus(Enum):
    NEW = "NEW"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

orders_db = {}

# ========= API ЭНДПОИНТЫ =========
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/tours', methods=['GET'])
def get_tours():
    try:
        response = requests.get(f"{CATALOG_URL}/tours", timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route('/bookings', methods=['GET'])
def get_all_bookings():
    try:
        response = requests.get(f"{BOOKING_URL}/bookings", timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 503

@app.route('/order/safe_book', methods=['POST'])
def safe_book_with_saga():
    data = request.json
    tour_id = data.get('tour_id')
    user_name = data.get('user_name')
    seats = data.get('seats')

    if not all([tour_id, user_name, seats]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        tour_resp = requests.get(f"{CATALOG_URL}/tours/{tour_id}", timeout=5)
        if tour_resp.status_code != 200:
            return jsonify({"error": f"Tour {tour_id} not found"}), 404
        tour = tour_resp.json()
        amount = tour['price'] * seats
    except Exception as e:
        return jsonify({"error": f"Catalog error: {str(e)}"}), 503

    order_id = uuid.uuid4().int % 1000000
    orders_db[order_id] = {
        "status": OrderStatus.NEW,
        "tour_id": tour_id,
        "user_name": user_name,
        "seats": seats,
        "booking_id": None
    }

    booking_id = None
    try:
        booking_resp = requests.post(
            f"{BOOKING_URL}/bookings",
            json={"tour_id": tour_id, "user_name": user_name, "seats": seats},
            timeout=5
        )
        if booking_resp.status_code != 201:
            raise Exception("Booking service failed")
        booking = booking_resp.json()
        booking_id = booking['id']
        orders_db[order_id]["booking_id"] = booking_id

        @retry(max_attempts=3, delay=1)
        def call_payment():
            return requests.post(
                f"{PAYMENT_URL}/pay",
                json={"booking_id": booking_id, "amount": amount},
                timeout=5
            )

        payment_resp = payment_circuit_breaker.call(call_payment)
        if payment_resp.status_code != 200:
            raise Exception(f"Payment error: {payment_resp.status_code}")
        payment = payment_resp.json()

        orders_db[order_id]["status"] = OrderStatus.PAID

        return jsonify({
            "status": "success",
            "order_id": order_id,
            "order_status": OrderStatus.PAID.value,
            "booking_id": booking_id,
            "payment": payment,
            "total_amount": amount
        }), 201

    except Exception as e:
        if booking_id:
            try:
                logger.info(f"Compensation: cancelling booking {booking_id}")
            except:
                pass
            orders_db[order_id]["status"] = OrderStatus.CANCELLED
            return jsonify({
                "status": "failed",
                "error": str(e),
                "order_id": order_id,
                "order_status": OrderStatus.CANCELLED.value
            }), 402

        orders_db[order_id]["status"] = OrderStatus.CANCELLED
        return jsonify({
            "status": "failed",
            "error": str(e),
            "order_id": order_id,
            "order_status": OrderStatus.CANCELLED.value
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)