from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Product:
    product_id: str
    name: str
    price: float
    stock: int
    reserved: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def available_stock(self):
        return self.stock - self.reserved

    def reserve(self, qty: int) -> bool:
        if qty > self.available_stock:
            return False
        self.reserved += qty
        return True

    def release(self, qty: int):
        self.reserved = max(0, self.reserved - qty)

    def deduct(self, qty: int) -> bool:
        """Actually remove from stock after order confirmed"""
        if qty > self.stock:
            return False
        self.stock -= qty
        self.reserved = max(0, self.reserved - qty)
        return True

    def restock(self, qty: int):
        self.stock += qty

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "name": self.name,
            "price": self.price,
            "stock": self.stock,
            "reserved": self.reserved,
            "available": self.available_stock,
        }
