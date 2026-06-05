const API_BASE = 'http://localhost:5000'; // Integration Service

// Показывать уведомления
function showMessage(message, isError = false) {
    const toastEl = document.getElementById('liveToast');
    const toastBody = document.getElementById('toastMessage');
    toastBody.innerText = message;
    toastEl.classList.remove('bg-success', 'bg-danger');
    toastEl.classList.add(isError ? 'bg-danger' : 'bg-success');
    const bsToast = new bootstrap.Toast(toastEl, { delay: 2000 });
    bsToast.show();
}

// Загрузка каталога
async function loadCatalog() {
    try {
        const res = await fetch(`${API_BASE}/tours`);
        const tours = await res.json();
        const container = document.getElementById('catalog');
        if (!tours.length) {
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">Туры временно отсутствуют</div></div>';
            return;
        }
        container.innerHTML = tours.map(tour => `
            <div class="col-md-4 mb-3">
                <div class="card tour-card" data-id="${tour.id}" data-name="${tour.name}" data-price="${tour.price}">
                    <div class="card-body">
                        <h5 class="card-title">${tour.name}</h5>
                        <p class="card-text">💰 ${tour.price} USD</p>
                        <p class="card-text">📅 ${tour.days} дней</p>
                        <button class="btn btn-primary book-btn" data-id="${tour.id}" data-name="${tour.name}" data-price="${tour.price}">Забронировать</button>
                    </div>
                </div>
            </div>
        `).join('');
        
        // Навесить обработчики на кнопки
        document.querySelectorAll('.book-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.dataset.id;
                const name = btn.dataset.name;
                const price = btn.dataset.price;
                bookTour(id, name, price);
            });
        });
    } catch (err) {
        console.error(err);
        showMessage('Ошибка загрузки каталога', true);
    }
}

// Бронирование (через оркестратор)
async function bookTour(tourId, tourName, price) {
    const seats = prompt(`Сколько мест бронируем для тура "${tourName}"?`, '1');
    if (!seats || isNaN(seats) || seats < 1) {
        showMessage('Некорректное количество мест', true);
        return;
    }
    
    const payload = {
        tour_id: parseInt(tourId),
        user_name: "Клиент сайта",
        seats: parseInt(seats)
    };
    
    try {
        showMessage(`Оформляем бронирование на тур "${tourName}"...`);
        const res = await fetch(`${API_BASE}/order/safe_book`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
            showMessage(`✅ Заказ №${data.order_id} оформлен! Статус: ${data.order_status}. Сумма: ${data.total_amount} USD`);
            loadMyBookings(); // обновить список броней
        } else {
            showMessage(`❌ Ошибка: ${data.error || 'неизвестная ошибка'}`, true);
        }
    } catch (err) {
        console.error(err);
        showMessage('Ошибка сети при бронировании', true);
    }
}

// Загрузить мои бронирования (через оркестратор)
async function loadMyBookings() {
    try {
        const res = await fetch(`${API_BASE}/bookings`);
        const bookings = await res.json();
        const container = document.getElementById('bookings');
        if (!bookings.length) {
            container.innerHTML = '<div class="alert alert-secondary">У вас пока нет бронирований</div>';
            return;
        }
        container.innerHTML = bookings.map(b => `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>Тур #${b.tour_id}</strong> для <strong>${b.user_name}</strong><br>
                        Мест: ${b.seats}, статус: <span class="badge bg-info">${b.status}</span>
                    </div>
                    <small>${new Date(b.created_at).toLocaleString()}</small>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error(err);
        document.getElementById('bookings').innerHTML = '<div class="alert alert-danger">Не удалось загрузить бронирования</div>';
    }
}

// При загрузке страницы
loadCatalog();
loadMyBookings();
setInterval(loadMyBookings, 5000); // обновление каждые 5 секунд