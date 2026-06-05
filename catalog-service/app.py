from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # чтобы другие сервисы могли обращаться

# Пример данных — туристические туры
tours = [
    {"id": 1, "name": "Париж", "price": 500, "days": 7},
    {"id": 2, "name": "Рим", "price": 450, "days": 6},
    {"id": 3, "name": "Лондон", "price": 550, "days": 5}
]

@app.route('/tours', methods=['GET'])
def get_tours():
    return jsonify(tours)

@app.route('/tours/<int:tour_id>', methods=['GET'])
def get_tour(tour_id):
    tour = next((t for t in tours if t["id"] == tour_id), None)
    return jsonify(tour) if tour else ("Not found", 404)

if __name__ == '__main__':
    app.run(port=5001, debug=True)