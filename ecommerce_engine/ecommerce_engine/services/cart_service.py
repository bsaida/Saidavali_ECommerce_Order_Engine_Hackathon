from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from models.cart import Cart
from utils.logger import logger
from utils.display import success, error, warn

RESERVATION_TTL_MINUTES = 10


class CartService:
    """
    Manages per-user shopping carts.
    Coordinates with ProductService for stock reservations.
    Reservations auto-expire after RESERVATION_TTL_MINUTES.
    """

    def __init__(self, product_service):
        self._carts: Dict[str, Cart] = {}
        self._expiry: Dict[Tuple[str, str], datetime] = {}  # (user_id, product_id) -> expiry
        self.product_svc = product_service

    def _get_or_create_cart(self, user_id: str) -> Cart:
        if user_id not in self._carts:
            self._carts[user_id] = Cart(user_id=user_id)
        return self._carts[user_id]

    def add_to_cart(self, user_id: str, product_id: str, qty: int) -> bool:
        if qty <= 0:
            error("Quantity must be at least 1.")
            return False

        product = self.product_svc.get_product(product_id)
        if product is None:
            error(f"Product '{product_id}' not found.")
            return False

        if product.available_stock == 0:
            error(f"'{product.name}' is out of stock.")
            return False

        cart = self._get_or_create_cart(user_id)
        existing_qty = cart.get_qty(product_id)

        # reserve stock (release previous qty for this user first)
        reserved = self.product_svc.reserve_stock(
            product_id, qty, release_existing=existing_qty
        )
        if not reserved:
            error(
                f"Not enough stock. Available: {product.available_stock + existing_qty}"
            )
            return False

        cart.add_item(product_id, qty)
        self._expiry[(user_id, product_id)] = datetime.now() + timedelta(
            minutes=RESERVATION_TTL_MINUTES
        )

        logger.log(f"{user_id} added {product_id} qty={qty} to cart")
        success(f"Added {qty}x '{product.name}' to cart.")
        return True

    def remove_from_cart(self, user_id: str, product_id: str) -> bool:
        cart = self._carts.get(user_id)
        if cart is None or cart.is_empty():
            error("Your cart is empty.")
            return False

        qty = cart.remove_item(product_id)
        if qty == 0:
            error(f"'{product_id}' is not in your cart.")
            return False

        self.product_svc.release_stock(product_id, qty)
        self._expiry.pop((user_id, product_id), None)

        product = self.product_svc.get_product(product_id)
        name = product.name if product else product_id
        logger.log(f"{user_id} removed {product_id} qty={qty} from cart")
        success(f"Removed '{name}' from cart.")
        return True

    def get_cart(self, user_id: str) -> Optional[Cart]:
        return self._carts.get(user_id)

    def clear_cart(self, user_id: str):
        cart = self._carts.get(user_id)
        if cart:
            # release all reservations
            for pid, qty in cart.all_items().items():
                self.product_svc.release_stock(pid, qty)
                self._expiry.pop((user_id, pid), None)
            cart.clear()

    def print_cart(self, user_id: str):
        cart = self._carts.get(user_id)
        if cart is None or cart.is_empty():
            print("  Cart is empty.")
            return

        print(f"\n  Cart for user: {user_id}")
        print(f"  {'Product':<22} {'Name':<20} {'Qty':>5} {'Unit Price':>12} {'Subtotal':>12}")
        print("  " + "-" * 75)

        total = 0.0
        for pid, qty in cart.all_items().items():
            p = self.product_svc.get_product(pid)
            if p:
                sub = p.price * qty
                total += sub
                exp = self._expiry.get((user_id, pid))
                exp_str = f"  (expires {exp.strftime('%H:%M')})" if exp else ""
                print(
                    f"  {pid:<22} {p.name:<20} {qty:>5}"
                    f" ₹{p.price:>10.2f} ₹{sub:>10.2f}{exp_str}"
                )

        print("  " + "-" * 75)
        print(f"  {'':>60} ₹{total:>10.2f}")

    def check_and_expire_reservations(self):
        """Call this periodically to release expired reservations."""
        now = datetime.now()
        expired = [(k, v) for k, v in self._expiry.items() if now > v]
        for (user_id, product_id), _ in expired:
            cart = self._carts.get(user_id)
            if cart:
                qty = cart.remove_item(product_id)
                if qty:
                    self.product_svc.release_stock(product_id, qty)
                    logger.log(
                        f"Reservation expired: {user_id} | {product_id} qty={qty}"
                    )
                    warn(f"Reservation expired for {user_id} → {product_id} (released {qty} units)")
            del self._expiry[(user_id, product_id)]
