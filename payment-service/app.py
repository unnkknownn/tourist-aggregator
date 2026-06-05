from flask import Flask, request, jsonify

app = Flask(__name__)

# Симуляция обработки платежа
@app.route('/pay', methods=['POST'])
def process_payment():
    data = request.json
    booking_id = data.get('booking_id')
    amount = data.get('amount')
    
    # Простая валидация
    if not booking_id or not amount:
        return jsonify({"error": "Missing booking_id or amount"}), 400
    
    # Имитируем успешную оплату
    return jsonify({
        "status": "success",
        "message": f"Payment for booking {booking_id} of ${amount} processed",
        "transaction_id": f"TXN_{booking_id}_{int(time.time())}"
    }), 200

if __name__ == '__main__':
    import time
    app.run(port=5003, debug=True)