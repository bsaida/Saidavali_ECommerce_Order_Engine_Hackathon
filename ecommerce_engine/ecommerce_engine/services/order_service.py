import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from models.order import Order, OrderStatus, VALID_TRANSITIONS
from utils.logger import logger
from utils.event_bus import event_bus
from utils.display import success, error, warn, info


class OrderService:
    """
    Core order management.
    Handles placement (atomic), state transitions, cancellation, returns.
    Uses idempotency keys to prevent duplicate orders.
    """

    def __init__(self, product_service, cart_service, discount_service, payment_service, fraud_service):
        self._orders: Dict[str, Order] = {}
        self._counter = 1000
        self._counter_lock = threading.Lock()
        self._idempotency_keys = set()  # (user_id, frozenset of items)

        self.product_svc = product_service
        self.cart_svc = cart_service
        self.discount_svc = discount_service
        self.payment_svc = payment_service
        self.fraud_svc = fraud_service

    def _next_order_id(self) -> str:
        with self._counter_lock:
            self._counter += 1
            return f"ORD{self._counter}"

    # ── PLACEMENT ─────────────────────────────────────────────────────────────

    def place_order(self, user_id: str, coupon_code: Optional[str] = None) -> Optional[str]:
        """
        Atomic order placement:
          1. Validate cart
          2. Idempotency check
          3. Fraud check
          4. Calculate total with discounts
          5. Deduct stock (lock)
          6. Create order record
          7. Process payment
          8. On failure -> rollback everything
        """

        # Step 1: Validate cart
        print("\n  [1/5] Validating cart...")
        cart = self.cart_svc.get_cart(user_id)
        if cart is None or cart.is_empty():
            error("Cart is empty. Add items before placing an order.")
            return None

        items = cart.all_items()

        # grab prices at this moment (price lock-in)
        prices = {}
        for pid in items:
            p = self.product_svc.get_product(pid)
            if p is None:
                error(f"Product '{pid}' no longer exists.")
                return None
            if p.available_stock < items[pid]:
                error(f"'{p.name}' only has {p.available_stock} units available.")
                return None
            prices[pid] = p.price

        # Step 2: Idempotency
        print("  [2/5] Checking for duplicate orders...")
        idem_key = (user_id, frozenset(items.items()))
        if idem_key in self._idempotency_keys:
            warn("Duplicate order detected — this order was already placed.")
            return None
        
        # Step 3: Fraud check
        print("  [3/5] Running fraud checks...")
        fraud_flags = self.fraud_svc.check(user_id, sum(prices[p] * q for p, q in items.items()))
        for flag in fraud_flags:
            warn(f"FRAUD FLAG: {flag}")
        if fraud_flags:
            logger.log(f"Fraud flags for {user_id}: {fraud_flags}")

        # Step 4: Calculate total
        print("  [4/5] Calculating totals...")
        subtotal, discount, total, breakdown = self.discount_svc.calculate(
            items, prices, coupon_code
        )
        print(f"\n  Subtotal : ₹{subtotal:.2f}")
        if breakdown != "No discounts applied":
            print(f"  Discounts:")
            print(f"    {breakdown}")
        print(f"  Total    : ₹{total:.2f}")

        confirm = input("\n  Confirm order? (y/n): ").strip().lower()
        if confirm != "y":
            info("Order cancelled by user.")
            return None

        # Step 5: Deduct stock (actual deduction, reservations already held)
        print("\n  [5/5] Locking inventory and processing payment...")
        deducted = {}
        for pid, qty in items.items():
            if not self.product_svc.deduct_stock(pid, qty):
                # rollback any deductions done so far
                for done_pid, done_qty in deducted.items():
                    self.product_svc.restore_stock(done_pid, done_qty)
                error(f"Stock deduction failed for '{pid}'. Order aborted.")
                return None
            deducted[pid] = qty

        # Create order record
        order_id = self._next_order_id()
        order = Order(
            order_id=order_id,
            user_id=user_id,
            items=dict(items),
            item_prices=prices,
            subtotal=subtotal,
            discount=discount,
            total=total,
            coupon_used=coupon_code or "",
        )
        order.transition_to(OrderStatus.PENDING_PAYMENT)
        self._orders[order_id] = order

        event_bus.publish("ORDER_CREATED", {"order_id": order_id, "user": user_id, "total": total})
        logger.log(f"Order created: {order_id} | user={user_id} | total=₹{total:.2f}")

        # Process payment
        payment_ok = self.payment_svc.process(order_id, total, user_id)

        if not payment_ok:
            # ROLLBACK
            print("  🔄  Rolling back transaction...")
            for pid, qty in deducted.items():
                self.product_svc.restore_stock(pid, qty)
            order.transition_to(OrderStatus.FAILED)
            logger.log(f"Order {order_id} rolled back — payment failure")
            event_bus.publish("PAYMENT_FAILED", {"order_id": order_id})
            error("Order failed. All changes have been reversed.")
            return None

        # All good — finalise
        order.transition_to(OrderStatus.PAID)
        self._idempotency_keys.add(idem_key)

        # Clear the cart
        self.cart_svc.clear_cart(user_id)

        event_bus.publish("PAYMENT_SUCCESS", {"order_id": order_id, "amount": total})
        event_bus.publish("INVENTORY_UPDATED", {"items": dict(items)})
        logger.log(f"Order {order_id} paid successfully | user={user_id}")

        self.fraud_svc.record_order(user_id, total)

        print(f"\n  {'─' * 40}")
        success(f"Order {order_id} placed successfully!")
        print(f"  Amount paid : ₹{total:.2f}")
        if coupon_code:
            print(f"  Coupon used : {coupon_code}")
        print(f"  {'─' * 40}")

        return order_id

    # ── CANCELLATION ──────────────────────────────────────────────────────────

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None:
            error(f"Order '{order_id}' not found.")
            return False

        if order.status == OrderStatus.CANCELLED:
            error("This order is already cancelled.")
            return False

        if not order.can_transition_to(OrderStatus.CANCELLED):
            error(
                f"Cannot cancel an order in '{order.status.value}' status. "
                "Only CREATED or PAID orders can be cancelled."
            )
            return False

        # restore stock
        for pid, qty in order.items.items():
            self.product_svc.restore_stock(pid, qty)

        order.transition_to(OrderStatus.CANCELLED)
        logger.log(f"Order {order_id} cancelled | stock restored")
        event_bus.publish("ORDER_CANCELLED", {"order_id": order_id, "user": order.user_id})
        success(f"Order {order_id} cancelled. Stock has been restored.")
        return True

    # ── RETURNS ───────────────────────────────────────────────────────────────

    def return_items(self, order_id: str, product_id: str, qty: int) -> bool:
        order = self._orders.get(order_id)
        if order is None:
            error(f"Order '{order_id}' not found.")
            return False

        if order.status != OrderStatus.DELIVERED:
            error("Only delivered orders can be returned.")
            return False

        ordered_qty = order.items.get(product_id, 0)
        if ordered_qty == 0:
            error(f"Product '{product_id}' was not part of this order.")
            return False

        if qty <= 0 or qty > ordered_qty:
            error(f"Invalid return quantity. Ordered qty was {ordered_qty}.")
            return False

        unit_price = order.item_prices.get(product_id, 0)
        refund_amount = unit_price * qty

        self.product_svc.restore_stock(product_id, qty)
        order.items[product_id] -= qty
        if order.items[product_id] == 0:
            del order.items[product_id]
        order.total -= refund_amount

        logger.log(
            f"Return processed: {order_id} | {product_id} qty={qty} | refund=₹{refund_amount:.2f}"
        )
        event_bus.publish("RETURN_PROCESSED", {"order_id": order_id, "product": product_id, "qty": qty})
        success(f"Return accepted. Refund amount: ₹{refund_amount:.2f}")
        return True

    # ── STATE MACHINE ─────────────────────────────────────────────────────────

    def advance_order_status(self, order_id: str, new_status_str: str) -> bool:
        order = self._orders.get(order_id)
        if order is None:
            error(f"Order '{order_id}' not found.")
            return False

        try:
            new_status = OrderStatus(new_status_str.upper())
        except ValueError:
            valid = [s.value for s in OrderStatus]
            error(f"Unknown status. Valid values: {valid}")
            return False

        if not order.transition_to(new_status):
            allowed = [s.value for s in VALID_TRANSITIONS.get(order.status, [])]
            error(
                f"Invalid transition: {order.status.value} → {new_status_str.upper()}. "
                f"Allowed: {allowed if allowed else 'none (terminal state)'}"
            )
            return False

        logger.log(f"Order {order_id} status → {new_status.value}")
        success(f"Order {order_id} is now {new_status.value}.")
        return True

    # ── QUERIES ───────────────────────────────────────────────────────────────

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def list_orders(self, status_filter: Optional[str] = None) -> List[Order]:
        orders = list(self._orders.values())
        if status_filter:
            try:
                f = OrderStatus(status_filter.upper())
                orders = [o for o in orders if o.status == f]
            except ValueError:
                pass
        return orders

    def print_order(self, order: Order):
        print(f"\n  Order ID  : {order.order_id}")
        print(f"  User      : {order.user_id}")
        print(f"  Status    : {order.status.value}")
        print(f"  Created   : {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Subtotal  : ₹{order.subtotal:.2f}")
        if order.discount > 0:
            print(f"  Discount  : -₹{order.discount:.2f}")
        print(f"  Total     : ₹{order.total:.2f}")
        if order.coupon_used:
            print(f"  Coupon    : {order.coupon_used}")
        print(f"  Items     :")
        for pid, qty in order.items.items():
            p = self.product_svc.get_product(pid)
            name = p.name if p else pid
            unit = order.item_prices.get(pid, 0)
            print(f"    {pid} | {name} | qty={qty} | unit=₹{unit:.2f}")
        print()
