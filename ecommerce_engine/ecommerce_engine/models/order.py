from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict


class OrderStatus(Enum):
    CREATED = "CREATED"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


# defines which statuses can move to which next statuses
VALID_TRANSITIONS = {
    OrderStatus.CREATED: [OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED],
    OrderStatus.PENDING_PAYMENT: [OrderStatus.PAID, OrderStatus.FAILED],
    OrderStatus.PAID: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
    OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [],
    OrderStatus.CANCELLED: [],
    OrderStatus.FAILED: [],
}


@dataclass
class Order:
    order_id: str
    user_id: str
    items: Dict[str, int]          # product_id -> qty
    item_prices: Dict[str, float]  # product_id -> price at time of order
    subtotal: float
    discount: float
    total: float
    coupon_used: str
    status: OrderStatus = OrderStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        return new_status in VALID_TRANSITIONS.get(self.status, [])

    def transition_to(self, new_status: OrderStatus) -> bool:
        if not self.can_transition_to(new_status):
            return False
        self.status = new_status
        self.updated_at = datetime.now()
        return True

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "items": self.items,
            "subtotal": self.subtotal,
            "discount": self.discount,
            "total": self.total,
            "coupon": self.coupon_used or "None",
            "status": self.status.value,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
