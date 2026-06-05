const express = require('express');
const { Sequelize, DataTypes } = require('sequelize');

const app = express();
app.use(express.json());

const sequelize = new Sequelize(process.env.DATABASE_URL || 'postgresql://tourist:tourist123@localhost:5432/tourist_aggregator', {
    dialect: 'postgres',
    logging: false
});

const Booking = sequelize.define('Booking', {
    id: { type: DataTypes.INTEGER, autoIncrement: true, primaryKey: true },
    tour_id: { type: DataTypes.INTEGER, allowNull: false },
    user_name: { type: DataTypes.STRING(100), allowNull: false },
    seats: { type: DataTypes.INTEGER, allowNull: false },
    status: { type: DataTypes.STRING(20), defaultValue: 'pending' }
}, { tableName: 'bookings', timestamps: true, createdAt: 'created_at', updatedAt: false });

sequelize.sync();

app.post('/bookings', async (req, res) => {
    const { tour_id, user_name, seats } = req.body;
    if (!tour_id || !user_name || !seats) {
        return res.status(400).json({ error: "Missing fields" });
    }
    const booking = await Booking.create({ tour_id, user_name, seats });
    res.status(201).json(booking);
});

app.get('/bookings', async (req, res) => {
    const bookings = await Booking.findAll();
    res.json(bookings);
});

app.listen(5002, () => console.log('Booking service running on port 5002'));