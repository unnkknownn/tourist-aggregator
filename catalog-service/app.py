from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://tourist:tourist123@localhost:5432/tourist_aggregator')
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class Tour(Base):
    __tablename__ = 'tours'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    days = Column(Integer, nullable=False)


Base.metadata.create_all(engine)


@app.route('/tours', methods=['GET'])
def get_tours():
    session = SessionLocal()
    tours = session.query(Tour).all()
    session.close()
    return jsonify([{'id': t.id, 'name': t.name, 'price': t.price, 'days': t.days} for t in tours])


@app.route('/tours/<int:tour_id>', methods=['GET'])
def get_tour(tour_id):
    session = SessionLocal()
    tour = session.query(Tour).filter(Tour.id == tour_id).first()
    session.close()
    if tour:
        return jsonify({'id': tour.id, 'name': tour.name, 'price': tour.price, 'days': tour.days})
    return jsonify({'error': 'Tour not found'}), 404

@app.route('/tours', methods=['POST'])
def create_tour():
    data = request.json
    session = SessionLocal()
    new_tour = Tour(
        name=data['name'],
        price=data['price'],
        days=data['days']
    )
    session.add(new_tour)
    session.commit()
    tour_id = new_tour.id
    session.close()
    return jsonify({'id': tour_id, 'message': 'Tour created'}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)