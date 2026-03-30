from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class CartItem:
    product_id: str
    qty: int
    reserved_at: datetime = field(default_factory=datetime.now)


@dataclass
class Cart:
    user_id: str
    items: Dict[str, CartItem] = field(default_factory=dict)

    def add_item(self, product_id: str, qty: int):
        if product_id in self.items:
            self.items[product_id].qty = qty
            self.items[product_id].reserved_at = datetime.now()
        else:
            self.items[product_id] = CartItem(product_id=product_id, qty=qty)

    def remove_item(self, product_id: str) -> int:
        """Returns qty that was in cart, 0 if not found"""
        if product_id in self.items:
            qty = self.items[product_id].qty
            del self.items[product_id]
            return qty
        return 0

    def get_qty(self, product_id: str) -> int:
        item = self.items.get(product_id)
        return item.qty if item else 0

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def clear(self):
        self.items.clear()

    def all_items(self) -> Dict[str, int]:
        return {pid: item.qty for pid, item in self.items.items()}
