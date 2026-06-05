import logging
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger
import time
from functools import wraps
from flask import Flask, request, jsonify
import requests
import json
# ========= ЭТАП 9.3: RETRY + CIRCUIT BREAKER =========
import time
import logging
from functools import wraps

# Настройка простого лога (чтобы видеть, что происходит)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- 1. RETRY (повторяем запрос, если упал) ----------
def retry(max_attempts=3, delay=1):
    """
    Декоратор: повторяет функцию до 3 раз, если она выкинула ошибку.
    delay=1 → ждём 1 секунду, потом 2 секунды, потом 4 (экспоненциальная задержка)
    """
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
                        raise  # последняя попытка не удалась — кидаем ошибку дальше
                    wait = delay * (2 ** attempt)  # 1, 2, 4 секунды
                    logger.info(f"Ждём {wait} секунд перед повторной попыткой...")
                    time.sleep(wait)
            return None
        return wrapper
    return decorator

# ---------- 2. CIRCUIT BREAKER (защита от мёртвого сервиса) ----------
class CircuitBreaker:
    """
    Простой Circuit Breaker:
    - CLOSED: всё работает, запросы идут
    - OPEN: сервис сломался, быстро возвращаем ошибку (не тратим время)
    - HALF_OPEN: пробуем один запрос, если ок — закрываем
    """
    def __init__(self, failure_threshold=3, timeout=30):
        self.failure_threshold = failure_threshold   # сколько ошибок нужно, чтобы открыть цепь
        self.timeout = timeout                       # через сколько секунд попробовать снова
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        # Если цепь открыта
        if self.state == "OPEN":
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout:
                logger.info("Circuit Breaker: переходим в HALF_OPEN (пробуем один запрос)")
                self.state = "HALF_OPEN"
            else:
                logger.warning(f"Circuit Breaker OPEN, отклоняем запрос (осталось ждать {self.timeout - elapsed:.0f} сек)")
                raise Exception("Circuit Breaker OPEN — сервис временно недоступен")

        try:
            result = func(*args, **kwargs)
            # Если HALF_OPEN и запрос прошёл — закрываем цепь
            if self.state == "HALF_OPEN":
                logger.info("Circuit Breaker: запрос в HALF_OPEN успешен, закрываем цепь")
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            logger.error(f"Ошибка: {e}. Счётчик ошибок: {self.failure_count}/{self.failure_threshold}")
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error("Circuit Breaker: переходим в OPEN (сервис отключён на время)")
            raise e

# Создаём экземпляр Circuit Breaker для Payment API
payment_circuit_breaker = CircuitBreaker(failure_threshold=2, timeout=15)
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
app = Flask(__name__)

# Адреса сервисов (имена контейнеров из docker-compose)
CATALOG_URL = "http://catalog-service:5001"
BOOKING_URL = "http://booking-service:5002"
PAYMENT_URL = "http://payment-service:5003"

@app.route('/health', methods=['GET'])
def health():
    """Проверка, что оркестратор жив"""
    return jsonify({"status": "ok"})

@app.route('/tours', methods=['GET'])
def get_tours():
    """Получить список туров (прокси в catalog-service)"""
    try:
        response = requests.get(f"{CATALOG_URL}/tours", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Catalog service error: {str(e)}"}), 503

@app.route('/book', methods=['POST'])
def book_tour():
    """
    Полный процесс бронирования:
    1. Проверяем, что тур существует
    2. Создаём бронирование
    3. Оплачиваем
    """
    data = request.json
    
    # Входные данные от пользователя
    tour_id = data.get('tour_id')
    user_name = data.get('user_name')
    seats = data.get('seats')
    
    # Валидация
    if not all([tour_id, user_name, seats]):
        return jsonify({"error": "Missing required fields: tour_id, user_name, seats"}), 400
    
    try:
        # ШАГ 1: Проверяем, что тур существует
        tour_response = requests.get(f"{CATALOG_URL}/tours/{tour_id}", timeout=5)
        if tour_response.status_code != 200:
            return jsonify({"error": f"Tour with id {tour_id} not found"}), 404
        
        tour = tour_response.json()
        
        # ШАГ 2: Создаём бронирование
        booking_data = {
            "tour_id": tour_id,
            "user_name": user_name,
            "seats": seats
        }
        booking_response = requests.post(
            f"{BOOKING_URL}/bookings",
            json=booking_data,
            timeout=5
        )
        
        if booking_response.status_code != 201:
            return jsonify({"error": "Failed to create booking"}), 500
        
        booking = booking_response.json()
        booking_id = booking.get('id')
        
        # ШАГ 3: Оплачиваем бронирование
        # Рассчитываем сумму (цена тура * количество мест)
        price = tour.get('price', 0)
        amount = price * seats
        
        payment_data = {
            "booking_id": booking_id,
            "amount": amount
        }
        payment_response = requests.post(
            f"{PAYMENT_URL}/pay",
            json=payment_data,
            timeout=5
        )
        
        if payment_response.status_code != 200:
            # Оплата не прошла, но бронь уже создана
            # В реальном проекте нужно бы откатить бронь
            return jsonify({
                "warning": "Booking created but payment failed",
                "booking": booking,
                "payment_error": payment_response.json()
            }), 402
        
        payment = payment_response.json()
        
        # ВСЁ УСПЕШНО!
        return jsonify({
            "status": "success",
            "booking": booking,
            "payment": payment,
            "total_amount": amount
        }), 201
        
    except requests.exceptions.Timeout:
        return jsonify({"error": "Service timeout"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Service unavailable"}), 503
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route('/bookings', methods=['GET'])
def get_all_bookings():
    """Получить все бронирования (прокси в booking-service)"""
    try:
        response = requests.get(f"{BOOKING_URL}/bookings", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Booking service error: {str(e)}"}), 503

# ========= ЭТАП 7: State Machine + Saga =========
from enum import Enum
import uuid

# Статусы заказа (State Machine)
class OrderStatus(Enum):
    NEW = "NEW"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

# Хранилище заказов (временно в памяти)
orders_db = {}

@app.route('/order/<int:order_id>', methods=['GET'])
def get_order_status(order_id):
    """Проверить статус заказа"""
    order = orders_db.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify({
        "order_id": order_id,
        "status": order["status"].value,
        "tour_id": order["tour_id"],
        "user_name": order["user_name"],
        "seats": order["seats"]
    })

@app.route('/order/safe_book', methods=['POST'])
def safe_book_with_saga():
    """
    Сквозной сценарий с транзакционностью (Saga pattern):
    1. Создаём заказ со статусом NEW
    2. Пытаемся создать бронирование
    3. Пытаемся провести оплату
    4. Если оплата не прошла → отменяем бронирование (компенсация)
    """
    data = request.json
    tour_id = data.get('tour_id')
    user_name = data.get('user_name')
    seats = data.get('seats')

    if not all([tour_id, user_name, seats]):
        return jsonify({"error": "Missing fields"}), 400

    # 1. Проверяем тур
    try:
        tour_resp = requests.get(f"{CATALOG_URL}/tours/{tour_id}", timeout=5)
        if tour_resp.status_code != 200:
            return jsonify({"error": f"Tour {tour_id} not found"}), 404
        tour = tour_resp.json()
        amount = tour['price'] * seats
    except Exception as e:
        return jsonify({"error": f"Catalog error: {str(e)}"}), 503

    # 2. Создаём заказ со статусом NEW
    order_id = uuid.uuid4().int % 1000000
    orders_db[order_id] = {
        "status": OrderStatus.NEW,
        "tour_id": tour_id,
        "user_name": user_name,
        "seats": seats,
        "booking_id": None
    }

    # 3. Saga: пытаемся выполнить операции, с возможностью отката
    booking_id = None
    try:
        # --- Шаг A: Создаём бронирование ---
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

                # --- Шаг B: Проводим оплату (с Retry + Circuit Breaker) ---
        @retry(max_attempts=3, delay=1)  # повторяем 3 раза, если упало
        def call_payment():
            return requests.post(
                f"{PAYMENT_URL}/pay",
                json={"booking_id": booking_id, "amount": amount},
                timeout=5
            )

        try:
            payment_resp = payment_circuit_breaker.call(call_payment)
            if payment_resp.status_code != 200:
                raise Exception(f"Payment вернул ошибку {payment_resp.status_code}")
            payment = payment_resp.json()
        except Exception as e:
            logger.error(f"Оплата не удалась после повторов: {e}")
            raise Exception("Payment failed")

        # --- Всё успешно: обновляем статус заказа ---
        orders_db[order_id]["status"] = OrderStatus.PAID

        return jsonify({
            "status": "success",
            "order_id": order_id,
            "order_status": OrderStatus.PAID.value,
            "booking_id": booking_id,
            "payment": payment_resp.json(),
            "total_amount": amount
        }), 201

    except Exception as e:
        # --- КОМПЕНСАЦИЯ (Saga Rollback) ---
        # Если бронирование было создано, но оплата не прошла — отменяем бронь
        if booking_id:
            try:
                # В реальном API нужен DELETE /bookings/<id>, у нас симуляция
                # Отмечаем бронь как cancelled (можно добавить эндпоинт, но для демо просто лог)
                print(f"Compensation: cancelling booking {booking_id}")
                # Здесь мог бы быть вызов booking_service.cancel(booking_id)
            except:
                pass
            orders_db[order_id]["status"] = OrderStatus.CANCELLED
            return jsonify({
                "status": "failed",
                "error": str(e),
                "order_id": order_id,
                "order_status": OrderStatus.CANCELLED.value,
                "message": "Booking created but payment failed → booking cancelled (Saga compensation)"
            }), 402

        # Если бронирование даже не создалось
        orders_db[order_id]["status"] = OrderStatus.CANCELLED
        return jsonify({
            "status": "failed",
            "error": str(e),
            "order_id": order_id,
            "order_status": OrderStatus.CANCELLED.value
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)