#!/usr/bin/env python3
"""
Distributed E-Commerce Order Engine
Hackathon Technical Assessment

Run: python main.py
"""

import sys
import os

# make sure local imports work regardless of where you run from
sys.path.insert(0, os.path.dirname(__file__))

from models.order import OrderStatus
from services.product_service import ProductService
from services.cart_service import CartService
from services.discount_service import DiscountEngine
from services.payment_service import PaymentService
from services.fraud_service import FraudDetectionService
from services.order_service import OrderService
from services.concurrency_simulator import ConcurrencySimulator
from services.failure_injection import FailureInjectionService
from utils.logger import logger
from utils.event_bus import event_bus
from utils.display import (
    header, divider, success, error, warn, info,
    pause, ask, ask_int, ask_float
)


# ── WIRE UP SERVICES ──────────────────────────────────────────────────────────

product_svc = ProductService()
cart_svc = CartService(product_svc)
discount_svc = DiscountEngine()
payment_svc = PaymentService()
fraud_svc = FraudDetectionService()
order_svc = OrderService(product_svc, cart_svc, discount_svc, payment_svc, fraud_svc)
concurrency_sim = ConcurrencySimulator(product_svc, cart_svc)
failure_svc = FailureInjectionService()


# ── SEED DATA ─────────────────────────────────────────────────────────────────

def seed_demo_data():
    """Load some starter products so you can start testing right away."""
    demo = [
        ("P001", "Laptop",        45999.0, 10),
        ("P002", "Wireless Mouse",  599.0, 50),
        ("P003", "Mechanical Keyboard", 1299.0, 3),
        ("P004", "27\" Monitor",  12999.0, 8),
        ("P005", "USB-C Hub",       899.0, 4),
        ("P006", "Webcam",         2499.0, 0),  # intentionally out of stock
    ]
    for pid, name, price, stock in demo:
        product_svc.add_product(pid, name, price, stock)
    print()


# ── MENU HANDLERS ─────────────────────────────────────────────────────────────

def handle_add_product():
    header("Add New Product")
    pid   = ask("Product ID")
    name  = ask("Product name")
    price = ask_float("Price (₹)")
    stock = ask_int("Stock quantity")
    product_svc.add_product(pid, name, price, stock)


def handle_view_products():
    header("Product Catalogue")
    product_svc.print_all_products()


def handle_update_stock():
    header("Update Stock")
    pid   = ask("Product ID")
    stock = ask_int("New stock quantity")
    product_svc.update_stock(pid, stock)


def handle_add_to_cart():
    header("Add to Cart")
    uid = ask("Your user ID")
    product_svc.print_all_products()
    pid = ask("Product ID to add")
    qty = ask_int("Quantity")
    cart_svc.add_to_cart(uid, pid, qty)


def handle_remove_from_cart():
    header("Remove from Cart")
    uid = ask("Your user ID")
    cart_svc.print_cart(uid)
    pid = ask("Product ID to remove")
    cart_svc.remove_from_cart(uid, pid)


def handle_view_cart():
    header("View Cart")
    uid = ask("Your user ID")
    cart_svc.print_cart(uid)


def handle_apply_coupon():
    header("Apply Coupon")
    uid    = ask("Your user ID")
    cart   = cart_svc.get_cart(uid)
    if cart is None or cart.is_empty():
        error("Cart is empty.")
        return

    items  = cart.all_items()
    prices = {}
    for pid in items:
        p = product_svc.get_product(pid)
        if p:
            prices[pid] = p.price

    code = ask("Coupon code (SAVE10 / FLAT200)")
    subtotal, discount, final, breakdown = discount_svc.calculate(items, prices, code)

    print(f"\n  Subtotal  : ₹{subtotal:.2f}")
    print(f"  Breakdown :")
    print(f"    {breakdown}")
    print(f"  Discount  : -₹{discount:.2f}")
    print(f"  Final     : ₹{final:.2f}")


def handle_place_order():
    header("Place Order")
    uid    = ask("Your user ID")
    coupon = ask("Coupon code (or press Enter to skip)").upper() or None
    order_svc.place_order(uid, coupon_code=coupon)


def handle_cancel_order():
    header("Cancel Order")
    oid = ask("Order ID to cancel")
    order_svc.cancel_order(oid)


def handle_view_orders():
    header("Order Management")
    print("  Filter:  1) All   2) Paid   3) Delivered   4) Cancelled   5) Search by ID")
    choice = ask("Choice")

    filter_map = {
        "2": "PAID",
        "3": "DELIVERED",
        "4": "CANCELLED",
    }

    if choice == "5":
        oid = ask("Order ID")
        o = order_svc.get_order(oid)
        if o:
            order_svc.print_order(o)
        else:
            error(f"Order '{oid}' not found.")
        return

    status_filter = filter_map.get(choice)
    orders = order_svc.list_orders(status_filter)

    if not orders:
        print("  No orders found.")
        return

    for o in orders:
        order_svc.print_order(o)
        divider()


def handle_update_order_status():
    header("Update Order Status")

    # show valid statuses
    print("  Valid statuses: CREATED, PENDING_PAYMENT, PAID, SHIPPED, DELIVERED, CANCELLED, FAILED\n")
    oid        = ask("Order ID")
    new_status = ask("New status")
    order_svc.advance_order_status(oid, new_status)


def handle_low_stock_alert():
    header("Low Stock Alert")
    product_svc.print_low_stock()


def handle_return_product():
    header("Return & Refund")
    oid = ask("Order ID")
    o   = order_svc.get_order(oid)
    if o:
        order_svc.print_order(o)
        pid = ask("Product ID to return")
        qty = ask_int("Quantity to return")
        order_svc.return_items(oid, pid, qty)
    else:
        error(f"Order '{oid}' not found.")


def handle_concurrency_simulation():
    header("Concurrency Simulation")
    product_svc.print_all_products()

    pid   = ask("Product ID to test")
    p     = product_svc.get_product(pid)
    if p is None:
        error("Product not found.")
        return

    stock = ask_int(f"Set test stock (current: {p.stock})")
    users = ask_int("Number of concurrent users")
    qty   = ask_int("Quantity each user tries to add")

    # reset stock for a clean test
    product_svc.update_stock(pid, stock)
    p.reserved = 0

    print(f"\n  Launching {users} concurrent threads...\n")
    results = concurrency_sim.run(pid, users, qty)
    concurrency_sim.print_results(results, pid, stock, qty)


def handle_view_logs():
    header("Audit Logs")
    logs = logger.get_recent(30)
    if not logs:
        print("  No log entries yet.")
        return
    for entry in logs:
        print(f"  {entry}")
    print(f"\n  Total entries: {len(logger)}")


def handle_failure_mode():
    header("Failure Injection")
    failure_svc.run_simulation()


def handle_view_events():
    header("Event Queue")
    events = event_bus.get_recent(25)
    if not events:
        print("  No events recorded yet.")
        return
    for e in events:
        print(f"  {e}")
    print(f"\n  Total events: {len(event_bus.get_all())}")


# ── MAIN MENU ─────────────────────────────────────────────────────────────────

MENU = [
    ("Product Management", None),
    ("Add Product",           handle_add_product),
    ("View Products",         handle_view_products),
    ("Update Stock",          handle_update_stock),
    ("", None),
    ("Cart", None),
    ("Add to Cart",           handle_add_to_cart),
    ("Remove from Cart",      handle_remove_from_cart),
    ("View Cart",             handle_view_cart),
    ("Apply Coupon",          handle_apply_coupon),
    ("", None),
    ("Orders", None),
    ("Place Order",           handle_place_order),
    ("Cancel Order",          handle_cancel_order),
    ("Return Product",        handle_return_product),
    ("View Orders",           handle_view_orders),
    ("Update Order Status",   handle_update_order_status),
    ("", None),
    ("System", None),
    ("Low Stock Alert",       handle_low_stock_alert),
    ("Simulate Concurrent Users", handle_concurrency_simulation),
    ("Trigger Failure Mode",  handle_failure_mode),
    ("View Event Queue",      handle_view_events),
    ("View Audit Logs",       handle_view_logs),
]


def print_menu():
    header("Distributed E-Commerce Order Engine")
    idx = 1
    for label, handler in MENU:
        if handler is None and label == "":
            print()
        elif handler is None:
            # section heading
            print(f"\n  ── {label} {'─' * (35 - len(label))}")
        else:
            print(f"  {idx:>2}. {label}")
            idx += 1
    print(f"\n   0. Exit")
    print()


def get_handler(choice: int):
    idx = 1
    for _, handler in MENU:
        if handler is not None:
            if idx == choice:
                return handler
            idx += 1
    return None


def main():
    print("\n" + "=" * 56)
    print("  🛒  Distributed E-Commerce Order Engine")
    print("  🏆  Hackathon Technical Assessment")
    print("=" * 56)

    load = input("\n  Load demo products for testing? (y/n): ").strip().lower()
    if load == "y":
        seed_demo_data()
        success("Demo data loaded: P001–P006")

    while True:
        cart_svc.check_and_expire_reservations()  # background cleanup

        print_menu()
        raw = input("  Enter choice: ").strip()

        if raw == "0":
            print("\n  Goodbye! 👋\n")
            break

        try:
            choice = int(raw)
        except ValueError:
            error("Please enter a number.")
            pause()
            continue

        handler = get_handler(choice)
        if handler is None:
            error("Invalid option. Please choose from the menu.")
        else:
            try:
                handler()
            except KeyboardInterrupt:
                print("\n  (cancelled)")

        pause()


if __name__ == "__main__":
    main()
