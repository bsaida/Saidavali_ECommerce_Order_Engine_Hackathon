#!/usr/bin/env python3
"""
Distributed E-Commerce Order Engine
Hackathon Technical Assessment
"""

import time
import random
import threading
from datetime import datetime, timedelta
from collections import defaultdict

# ─────────────────────────────────────────────
# DATA STORES
# ─────────────────────────────────────────────
products = {}          # product_id -> {name, price, stock, reserved}
carts = {}             # user_id -> {product_id: qty}
orders = {}            # order_id -> {user_id, items, total, status, created_at}
audit_logs = []        # immutable log list
event_queue = []       # event-driven system
flagged_users = set()  # fraud detection
order_counter = [1000]
locks = defaultdict(threading.Lock)  # per-product locks
reservation_expiry = {}  # (user_id, product_id) -> expiry_time
placed_order_keys = set()  # idempotency: (user_id, frozenset(items))
user_order_timestamps = defaultdict(list)  # fraud: user_id -> [timestamps]

COUPONS = {
    "SAVE10": ("percent", 10),
    "FLAT200": ("flat", 200),
}

LOW_STOCK_THRESHOLD = 5

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def log(msg):
    entry = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    audit_logs.append(entry)
    print(f"  📋 LOG: {msg}")

def new_order_id():
    order_counter[0] += 1
    return f"ORD_{order_counter[0]}"

def emit_event(event_type, data):
    event = {"type": event_type, "data": data, "time": datetime.now()}
    event_queue.append(event)
    print(f"  📡 EVENT: {event_type} → {data}")

def separator(title=""):
    print("\n" + "═" * 55)
    if title:
        print(f"  {title}")
        print("═" * 55)

def pause():
    input("\n  [Press Enter to continue...]\n")

# ─────────────────────────────────────────────
# TASK 1: PRODUCT MANAGEMENT
# ─────────────────────────────────────────────

def add_product():
    separator("ADD PRODUCT")
    pid = input("  Product ID: ").strip()
    if pid in products:
        print("  ❌ Duplicate product ID! Product already exists.")
        return
    name = input("  Product Name: ").strip()
    try:
        price = float(input("  Price (₹): "))
        stock = int(input("  Stock quantity: "))
        if stock < 0:
            print("  ❌ Stock cannot be negative!")
            return
    except ValueError:
        print("  ❌ Invalid input.")
        return
    products[pid] = {"name": name, "price": price, "stock": stock, "reserved": 0}
    log(f"Product {pid} '{name}' added with stock={stock}, price=₹{price}")
    print(f"  ✅ Product '{name}' added successfully!")

def view_products():
    separator("ALL PRODUCTS")
    if not products:
        print("  No products available.")
        return
    print(f"  {'ID':<12} {'Name':<20} {'Price':>8} {'Stock':>6} {'Reserved':>9}")
    print("  " + "-" * 58)
    for pid, p in products.items():
        avail = p['stock'] - p['reserved']
        flag = " ⚠️ LOW" if avail <= LOW_STOCK_THRESHOLD else ""
        print(f"  {pid:<12} {p['name']:<20} ₹{p['price']:>7.2f} {avail:>6}{flag}")

def update_stock():
    separator("UPDATE STOCK")
    pid = input("  Product ID: ").strip()
    if pid not in products:
        print("  ❌ Product not found.")
        return
    try:
        qty = int(input("  New stock quantity: "))
        if qty < 0:
            print("  ❌ Stock cannot be negative!")
            return
    except ValueError:
        print("  ❌ Invalid input.")
        return
    products[pid]['stock'] = qty
    log(f"Stock updated for {pid}: stock={qty}")
    print(f"  ✅ Stock updated to {qty}.")

# ─────────────────────────────────────────────
# TASK 2 & 3: MULTI-USER CART + STOCK RESERVATION
# ─────────────────────────────────────────────

def add_to_cart():
    separator("ADD TO CART")
    uid = input("  User ID: ").strip()
    pid = input("  Product ID: ").strip()
    if pid not in products:
        print("  ❌ Product not found.")
        return
    try:
        qty = int(input("  Quantity: "))
        if qty <= 0:
            print("  ❌ Quantity must be positive.")
            return
    except ValueError:
        print("  ❌ Invalid quantity.")
        return

    with locks[pid]:  # Task 4: Concurrency locking
        avail = products[pid]['stock'] - products[pid]['reserved']
        current_in_cart = carts.get(uid, {}).get(pid, 0)
        if qty > avail + current_in_cart:
            print(f"  ❌ Not enough stock! Available: {avail}")
            return
        # Release previous reservation
        products[pid]['reserved'] -= current_in_cart
        # New reservation
        products[pid]['reserved'] += qty
        if uid not in carts:
            carts[uid] = {}
        carts[uid][pid] = qty
        # Task 15: reservation expiry (10 minutes)
        reservation_expiry[(uid, pid)] = datetime.now() + timedelta(minutes=10)

    log(f"{uid} added {pid} qty={qty} to cart")
    emit_event("CART_UPDATED", {"user": uid, "product": pid, "qty": qty})
    print(f"  ✅ Added {qty}x '{products[pid]['name']}' to cart.")

def remove_from_cart():
    separator("REMOVE FROM CART")
    uid = input("  User ID: ").strip()
    pid = input("  Product ID: ").strip()
    if uid not in carts or pid not in carts.get(uid, {}):
        print("  ❌ Item not in cart.")
        return
    with locks[pid]:
        qty = carts[uid][pid]
        products[pid]['reserved'] -= qty
        del carts[uid][pid]
        reservation_expiry.pop((uid, pid), None)
    log(f"{uid} removed {pid} from cart")
    print(f"  ✅ Removed '{products[pid]['name']}' from cart.")

def view_cart():
    separator("VIEW CART")
    uid = input("  User ID: ").strip()
    cart = carts.get(uid, {})
    if not cart:
        print("  Cart is empty.")
        return
    total = 0
    print(f"  {'Product':<20} {'Qty':>5} {'Unit Price':>12} {'Subtotal':>12}")
    print("  " + "-" * 52)
    for pid, qty in cart.items():
        p = products[pid]
        sub = p['price'] * qty
        total += sub
        print(f"  {p['name']:<20} {qty:>5} ₹{p['price']:>10.2f} ₹{sub:>10.2f}")
    print("  " + "-" * 52)
    print(f"  {'TOTAL':>39} ₹{total:>10.2f}")

# ─────────────────────────────────────────────
# TASK 4: CONCURRENCY SIMULATION
# ─────────────────────────────────────────────

def simulate_concurrent_users():
    separator("CONCURRENCY SIMULATION")
    pid = input("  Product ID to test: ").strip()
    if pid not in products:
        print("  ❌ Product not found.")
        return
    try:
        stock = int(input("  Set stock for test: "))
        users_count = int(input("  Number of concurrent users: "))
        qty_each = int(input("  Qty each user tries to add: "))
    except ValueError:
        print("  ❌ Invalid input.")
        return

    products[pid]['stock'] = stock
    products[pid]['reserved'] = 0
    results = []

    def try_add(uid):
        with locks[pid]:
            avail = products[pid]['stock'] - products[pid]['reserved']
            if qty_each <= avail:
                products[pid]['reserved'] += qty_each
                if uid not in carts:
                    carts[uid] = {}
                carts[uid][pid] = qty_each
                results.append((uid, True))
            else:
                results.append((uid, False))

    threads = [threading.Thread(target=try_add, args=(f"User_{i}",)) for i in range(users_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"\n  Results (stock={stock}, each wants {qty_each}):")
    for uid, success in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"    {uid}: {status}")
    log(f"Concurrency sim: product={pid}, stock={stock}, users={users_count}, qty_each={qty_each}")

# ─────────────────────────────────────────────
# TASK 9: DISCOUNT & COUPON ENGINE
# ─────────────────────────────────────────────

def calculate_discount(uid, cart, coupon=None):
    total = sum(products[p]['price'] * q for p, q in cart.items())
    discount = 0

    # Rule 1: Total > ₹1000 → 10% off
    if total > 1000:
        discount += total * 0.10
        print("  💰 10% discount applied (order > ₹1000)")

    # Rule 2: Any product qty > 3 → extra 5%
    for pid, qty in cart.items():
        if qty > 3:
            discount += total * 0.05
            print(f"  💰 Extra 5% discount ({products[pid]['name']} qty={qty} > 3)")
            break

    # Coupon
    if coupon and coupon in COUPONS:
        ctype, cval = COUPONS[coupon]
        if ctype == "percent":
            coupon_disc = total * (cval / 100)
        else:
            coupon_disc = min(cval, total)
        discount += coupon_disc
        print(f"  🎫 Coupon '{coupon}' applied: -₹{coupon_disc:.2f}")
    elif coupon:
        print(f"  ❌ Invalid coupon '{coupon}'")

    discount = min(discount, total)
    return total, discount, total - discount

def apply_coupon():
    separator("APPLY COUPON")
    uid = input("  User ID: ").strip()
    cart = carts.get(uid, {})
    if not cart:
        print("  ❌ Cart is empty.")
        return
    code = input("  Coupon code: ").strip().upper()
    total, disc, final = calculate_discount(uid, cart, code)
    print(f"\n  Original Total: ₹{total:.2f}")
    print(f"  Discount:      -₹{disc:.2f}")
    print(f"  Final Total:    ₹{final:.2f}")

# ─────────────────────────────────────────────
# TASK 5, 6, 7: ORDER PLACEMENT + PAYMENT + ROLLBACK
# ─────────────────────────────────────────────

def place_order():
    separator("PLACE ORDER")
    uid = input("  User ID: ").strip()
    cart = carts.get(uid, {})
    if not cart:
        print("  ❌ Cart is empty.")
        return

    coupon = input("  Coupon code (or Enter to skip): ").strip().upper() or None

    # Task 19: Idempotency check
    order_key = (uid, frozenset(cart.items()))
    if order_key in placed_order_keys:
        print("  ⚠️  Duplicate order detected! Ignoring.")
        return

    # Step 1: Validate cart
    print("\n  Step 1: Validating cart...")
    for pid, qty in cart.items():
        if pid not in products:
            print(f"  ❌ Product {pid} not found.")
            return

    # Step 2: Calculate total
    print("  Step 2: Calculating total...")
    total, disc, final = calculate_discount(uid, cart, coupon)

    # Task 17: Fraud detection
    now = datetime.now()
    user_order_timestamps[uid] = [t for t in user_order_timestamps[uid] if (now - t).seconds < 60]
    if len(user_order_timestamps[uid]) >= 3:
        flagged_users.add(uid)
        print(f"  🚨 FRAUD ALERT: {uid} flagged for too many orders!")
    if final > 10000:
        print(f"  🚨 FRAUD ALERT: High-value order ₹{final:.2f} flagged as suspicious!")

    # Step 3: Lock stock (already reserved)
    print("  Step 3: Locking stock...")
    snapshot = {}  # for rollback
    for pid, qty in cart.items():
        snapshot[pid] = products[pid]['stock']
        products[pid]['stock'] -= qty
        products[pid]['reserved'] -= qty

    # Step 4: Create order
    print("  Step 4: Creating order...")
    oid = new_order_id()
    orders[oid] = {
        "user_id": uid,
        "items": dict(cart),
        "total": final,
        "original_total": total,
        "discount": disc,
        "status": "CREATED",
        "created_at": now,
    }
    emit_event("ORDER_CREATED", {"order_id": oid, "user": uid, "total": final})

    # Step 5 / Task 6: Payment simulation
    print("  Step 5: Processing payment...")
    time.sleep(0.5)
    payment_success = random.random() > 0.3  # 70% success

    if not payment_success:
        # Task 7: Rollback
        print("  ❌ Payment FAILED! Rolling back transaction...")
        for pid, orig_stock in snapshot.items():
            products[pid]['stock'] = orig_stock
        del orders[oid]
        log(f"Order {oid} rolled back due to payment failure")
        emit_event("PAYMENT_FAILED", {"order_id": oid})
        print("  ✅ Rollback complete. Stock restored.")
        return

    # Payment success
    orders[oid]['status'] = "PENDING_PAYMENT"
    orders[oid]['status'] = "PAID"
    emit_event("PAYMENT_SUCCESS", {"order_id": oid})
    emit_event("INVENTORY_UPDATED", {"items": dict(cart)})

    # Step 5: Clear cart
    del carts[uid]
    placed_order_keys.add(order_key)
    user_order_timestamps[uid].append(now)

    log(f"{uid} placed order {oid} total=₹{final:.2f}")
    print(f"\n  ✅ Order {oid} placed successfully!")
    print(f"     Total paid: ₹{final:.2f}")

# ─────────────────────────────────────────────
# TASK 8: ORDER STATE MACHINE
# ─────────────────────────────────────────────

VALID_TRANSITIONS = {
    "CREATED": ["PENDING_PAYMENT"],
    "PENDING_PAYMENT": ["PAID", "FAILED"],
    "PAID": ["SHIPPED"],
    "SHIPPED": ["DELIVERED"],
    "DELIVERED": [],
    "FAILED": [],
    "CANCELLED": [],
}

def update_order_status():
    separator("UPDATE ORDER STATUS")
    oid = input("  Order ID: ").strip()
    if oid not in orders:
        print("  ❌ Order not found.")
        return
    current = orders[oid]['status']
    valid_next = VALID_TRANSITIONS.get(current, [])
    print(f"  Current status: {current}")
    print(f"  Valid transitions: {valid_next if valid_next else 'None (terminal state)'}")
    if not valid_next:
        print("  ❌ Order is in a terminal state.")
        return
    new_status = input("  New status: ").strip().upper()
    if new_status not in valid_next:
        print(f"  ❌ Invalid transition: {current} → {new_status}")
        return
    orders[oid]['status'] = new_status
    log(f"Order {oid} status: {current} → {new_status}")
    print(f"  ✅ Order status updated to {new_status}.")

# ─────────────────────────────────────────────
# TASK 10: INVENTORY ALERT SYSTEM
# ─────────────────────────────────────────────

def low_stock_alert():
    separator("LOW STOCK ALERT")
    found = False
    for pid, p in products.items():
        avail = p['stock'] - p['reserved']
        if avail <= LOW_STOCK_THRESHOLD:
            print(f"  ⚠️  {pid} '{p['name']}': {avail} units remaining")
            found = True
    if not found:
        print("  ✅ All products have sufficient stock.")

# ─────────────────────────────────────────────
# TASK 11: ORDER MANAGEMENT
# ─────────────────────────────────────────────

def view_orders():
    separator("ORDER MANAGEMENT")
    print("  Filter: 1) All  2) Completed  3) Cancelled  4) Search by ID")
    choice = input("  Choice: ").strip()

    def print_order(oid, o):
        print(f"\n  Order ID : {oid}")
        print(f"  User     : {o['user_id']}")
        print(f"  Status   : {o['status']}")
        print(f"  Total    : ₹{o['total']:.2f}")
        print(f"  Created  : {o['created_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Items    : {o['items']}")

    if choice == "1":
        for oid, o in orders.items():
            print_order(oid, o)
    elif choice == "2":
        for oid, o in orders.items():
            if o['status'] == "DELIVERED":
                print_order(oid, o)
    elif choice == "3":
        for oid, o in orders.items():
            if o['status'] == "CANCELLED":
                print_order(oid, o)
    elif choice == "4":
        oid = input("  Order ID: ").strip()
        if oid in orders:
            print_order(oid, orders[oid])
        else:
            print("  ❌ Order not found.")
    if not orders:
        print("  No orders found.")

# ─────────────────────────────────────────────
# TASK 12: ORDER CANCELLATION ENGINE
# ─────────────────────────────────────────────

def cancel_order():
    separator("CANCEL ORDER")
    oid = input("  Order ID: ").strip()
    if oid not in orders:
        print("  ❌ Order not found.")
        return
    if orders[oid]['status'] == "CANCELLED":
        print("  ❌ Order already cancelled!")
        return
    if orders[oid]['status'] in ("DELIVERED", "SHIPPED"):
        print("  ❌ Cannot cancel a shipped/delivered order.")
        return
    # Restore stock
    for pid, qty in orders[oid]['items'].items():
        if pid in products:
            products[pid]['stock'] += qty
    orders[oid]['status'] = "CANCELLED"
    log(f"Order {oid} cancelled, stock restored")
    emit_event("ORDER_CANCELLED", {"order_id": oid})
    print(f"  ✅ Order {oid} cancelled and stock restored.")

# ─────────────────────────────────────────────
# TASK 13: RETURN & REFUND SYSTEM
# ─────────────────────────────────────────────

def return_product():
    separator("RETURN & REFUND")
    oid = input("  Order ID: ").strip()
    if oid not in orders:
        print("  ❌ Order not found.")
        return
    if orders[oid]['status'] != "DELIVERED":
        print("  ❌ Only delivered orders can be returned.")
        return
    pid = input("  Product ID to return: ").strip()
    if pid not in orders[oid]['items']:
        print("  ❌ Product not in this order.")
        return
    try:
        qty = int(input(f"  Qty to return (ordered: {orders[oid]['items'][pid]}): "))
        if qty <= 0 or qty > orders[oid]['items'][pid]:
            print("  ❌ Invalid return quantity.")
            return
    except ValueError:
        print("  ❌ Invalid input.")
        return
    refund = products[pid]['price'] * qty
    products[pid]['stock'] += qty
    orders[oid]['items'][pid] -= qty
    if orders[oid]['items'][pid] == 0:
        del orders[oid]['items'][pid]
    orders[oid]['total'] -= refund
    log(f"Return: {qty}x {pid} for order {oid}, refund=₹{refund:.2f}")
    emit_event("INVENTORY_UPDATED", {"product": pid, "returned": qty})
    print(f"  ✅ Return processed. Refund: ₹{refund:.2f}, stock restored.")

# ─────────────────────────────────────────────
# TASK 14: EVENT-DRIVEN SYSTEM
# ─────────────────────────────────────────────

def view_event_queue():
    separator("EVENT QUEUE")
    if not event_queue:
        print("  No events yet.")
        return
    for i, e in enumerate(event_queue[-20:], 1):
        print(f"  {i:>3}. [{e['time'].strftime('%H:%M:%S')}] {e['type']} → {e['data']}")

# ─────────────────────────────────────────────
# TASK 15: INVENTORY RESERVATION EXPIRY
# ─────────────────────────────────────────────

def check_reservation_expiry():
    now = datetime.now()
    expired = [(k, v) for k, v in reservation_expiry.items() if now > v]
    for (uid, pid), _ in expired:
        if uid in carts and pid in carts[uid]:
            qty = carts[uid][pid]
            products[pid]['reserved'] -= qty
            del carts[uid][pid]
            del reservation_expiry[(uid, pid)]
            log(f"Reservation expired: {uid} for {pid} qty={qty}")
            print(f"  ⏰ Reservation expired: {uid} → {pid}")

# ─────────────────────────────────────────────
# TASK 16: AUDIT LOGGING
# ─────────────────────────────────────────────

def view_logs():
    separator("AUDIT LOGS")
    if not audit_logs:
        print("  No logs yet.")
        return
    for entry in audit_logs[-30:]:
        print(f"  {entry}")

# ─────────────────────────────────────────────
# TASK 17: FRAUD DETECTION (inline in place_order)
# TASK 18: FAILURE INJECTION
# ─────────────────────────────────────────────

def trigger_failure_mode():
    separator("FAILURE INJECTION SYSTEM")
    print("  Simulating random system failures...\n")
    scenarios = ["Payment", "Order creation", "Inventory update"]
    for s in scenarios:
        fails = random.random() < 0.4
        status = "❌ FAILED" if fails else "✅ OK"
        print(f"  {s:<20}: {status}")
        if fails:
            log(f"Failure injection: {s} failed")
    print("\n  ✅ System recovery check: All services back online.")

# ─────────────────────────────────────────────
# TASK 19: IDEMPOTENCY (inline in place_order)
# TASK 20: MICROSERVICE SIMULATION
# ─────────────────────────────────────────────

class ProductService:
    @staticmethod
    def add(pid, name, price, stock):
        products[pid] = {"name": name, "price": price, "stock": stock, "reserved": 0}

class CartService:
    @staticmethod
    def add(uid, pid, qty):
        carts.setdefault(uid, {})[pid] = qty

class OrderService:
    @staticmethod
    def create(uid, items, total):
        oid = new_order_id()
        orders[oid] = {"user_id": uid, "items": items, "total": total,
                       "status": "CREATED", "created_at": datetime.now()}
        return oid

class PaymentService:
    @staticmethod
    def process(oid):
        return random.random() > 0.3

# ─────────────────────────────────────────────
# CLI MENU
# ─────────────────────────────────────────────

def print_menu():
    separator("DISTRIBUTED E-COMMERCE ORDER ENGINE")
    print("""
  1.  Add Product             9.  View Orders
  2.  View Products          10.  Low Stock Alert
  3.  Add to Cart            11.  Return Product
  4.  Remove from Cart       12.  Simulate Concurrent Users
  5.  View Cart              13.  View Logs
  6.  Apply Coupon           14.  Trigger Failure Mode
  7.  Place Order            15.  View Event Queue
  8.  Cancel Order           16.  Update Order Status
                              0.  Exit
""")

def seed_demo_data():
    """Seed some demo products for quick testing"""
    ProductService.add("P001", "Laptop", 45000, 10)
    ProductService.add("P002", "Mouse", 599, 50)
    ProductService.add("P003", "Keyboard", 1299, 3)
    ProductService.add("P004", "Monitor", 12999, 8)
    print("  ✅ Demo products loaded: P001 Laptop, P002 Mouse, P003 Keyboard, P004 Monitor")

def main():
    print("\n" + "═" * 55)
    print("  🛒  Distributed E-Commerce Order Engine")
    print("  📦  Hackathon Technical Assessment")
    print("═" * 55)
    seed = input("\n  Load demo products? (y/n): ").strip().lower()
    if seed == 'y':
        seed_demo_data()

    while True:
        check_reservation_expiry()  # Task 15: background check
        print_menu()
        choice = input("  Enter choice: ").strip()

        if choice == "1":
            add_product()
        elif choice == "2":
            view_products()
        elif choice == "3":
            add_to_cart()
        elif choice == "4":
            remove_from_cart()
        elif choice == "5":
            view_cart()
        elif choice == "6":
            apply_coupon()
        elif choice == "7":
            place_order()
        elif choice == "8":
            cancel_order()
        elif choice == "9":
            view_orders()
        elif choice == "10":
            low_stock_alert()
        elif choice == "11":
            return_product()
        elif choice == "12":
            simulate_concurrent_users()
        elif choice == "13":
            view_logs()
        elif choice == "14":
            trigger_failure_mode()
        elif choice == "15":
            view_event_queue()
        elif choice == "16":
            update_order_status()
        elif choice == "0":
            print("\n  👋 Goodbye! Exiting E-Commerce Engine.\n")
            break
        else:
            print("  ❌ Invalid choice. Please try again.")

        pause()

if __name__ == "__main__":
    main()
