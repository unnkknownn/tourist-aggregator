from flask import Flask, request, jsonify
import time
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://tourist:tourist123@localhost:5432/tourist_aggregator')
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_id = Column(String(100))
    status = Column(String(20), default='success')
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


@app.route('/pay', methods=['POST'])
def process_payment():
    data = request.json
    booking_id = data.get('booking_id')
    amount = data.get('amount')

    if not booking_id or not amount:
        return jsonify({"error": "Missing booking_id or amount"}), 400

    transaction_id = f"TXN_{booking_id}_{int(time.time())}"
    
    session = SessionLocal()
    payment = Payment(booking_id=booking_id, amount=amount, transaction_id=transaction_id)
    session.add(payment)
    session.commit()
    session.close()

    return jsonify({
        "status": "success",
        "message": f"Payment for booking {booking_id} of ${amount} processed",
        "transaction_id": transaction_id
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)