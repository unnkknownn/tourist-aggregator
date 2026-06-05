from flask import Flask, request, jsonify
import time


app = Flask(__name__)


@app.route('/pay', methods=['POST'])
def process_payment():
    data = request.json
    booking_id = data.get('booking_id')
    amount = data.get('amount')

    if not booking_id or not amount:
        return jsonify({"error": "Missing booking_id or amount"}), 400

    return jsonify({
        "status": "success",
        "message": f"Payment for booking {booking_id} of ${amount} processed",
        "transaction_id": f"TXN_{booking_id}_{int(time.time())}"
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
