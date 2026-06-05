const express = require('express');
const app = express();
app.use(express.json());

let bookings = []; // база бронирований в памяти
let nextId = 1;

// POST /bookings — создать бронирование
app.post('/bookings', (req, res) => {
    const { tour_id, user_name, seats } = req.body;
    if (!tour_id || !user_name || !seats) {
        return res.status(400).json({ error: "Missing fields" });
    }
    const newBooking = {
        id: nextId++,
        tour_id,
        user_name,
        seats,
        status: "pending",
        created_at: new Date()
    };
    bookings.push(newBooking);
    res.status(201).json(newBooking);
});

// GET /bookings — получить все бронирования
app.get('/bookings', (req, res) => {
    res.json(bookings);
});

app.listen(5002, () => {
    console.log('Booking service running on port 5002');
});