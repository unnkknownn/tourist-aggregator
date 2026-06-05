from flask import Flask, request, jsonify
import requests
import json

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)