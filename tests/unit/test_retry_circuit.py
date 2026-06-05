"""Unit-тесты для Retry и Circuit Breaker (без импорта app.py)"""
import pytest
import time
from functools import wraps

# ========= Копируем код из app.py (без проблемных импортов) =========
def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = delay * (2 ** attempt)
                    time.sleep(wait)
            return None
        return wrapper
    return decorator


class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout=30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit Breaker OPEN — сервис временно недоступен")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise e


# ========= ТЕСТЫ =========
class TestRetry:
    def test_retry_success_on_first_try(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "OK"

        result = success_func()
        assert result == "OK"
        assert call_count == 1

    def test_retry_after_failures(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "OK"

        result = flaky_func()
        assert result == "OK"
        assert call_count == 3

    def test_retry_all_failures(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.1)
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        with pytest.raises(Exception, match="Always fails"):
            failing_func()
        assert call_count == 3


class TestCircuitBreaker:
    def test_circuit_closed_success(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=5)

        def ok_func():
            return "OK"

        result = cb.call(ok_func)
        assert result == "OK"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_circuit_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=2, timeout=5)

        def failing_func():
            raise Exception("Service error")

        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "CLOSED"
        assert cb.failure_count == 1

        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "OPEN"
        assert cb.failure_count == 2

    def test_circuit_rejects_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=1)

        def failing_func():
            raise Exception("Error")

        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "OPEN"

        with pytest.raises(Exception, match="Circuit Breaker OPEN"):
            cb.call(failing_func)

    def test_circuit_half_open_recovers(self):
        cb = CircuitBreaker(failure_threshold=1, timeout=1)

        def failing_func():
            raise Exception("Error")

        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state == "OPEN"

        time.sleep(1.1)

        def ok_func():
            return "OK"

        result = cb.call(ok_func)
        assert result == "OK"
        assert cb.state == "CLOSED"