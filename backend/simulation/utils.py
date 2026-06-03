import hashlib


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_pin(pin: str, hashed_pin: str) -> bool:
    return hash_pin(pin) == hashed_pin


def calculate_profit_rate(avg_price: float, current_price: float) -> float:
    if avg_price == 0:
        return 0.0
    return ((current_price - avg_price) / avg_price) * 100


def calculate_evaluation_amount(quantity: int, current_price: float) -> float:
    return quantity * current_price