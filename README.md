# Distributed-E-Commerce-Order-Engine
A menu-driven CLI application simulating a real-world distributed e-commerce backend engine, covering inventory management, multi-user carts, order processing, payment simulation, fraud detection, and more.

## Features Implemented

| # | Task | Status |
|---|------|--------|
| 1 | Product Management (add, view, update stock) | ✅ |
| 2 | Multi-User Cart System | ✅ |
| 3 | Real-Time Stock Reservation | ✅ |
| 4 | Concurrency Simulation with thread locking | ✅ |
| 5 | Order Placement Engine (atomic, 5-step) | ✅ |
| 6 | Payment Simulation (success / failure) | ✅ |
| 7 | Transaction Rollback on failure | ✅ |
| 8 | Order State Machine | ✅ |
| 9 | Discount & Coupon Engine | ✅ |
| 10 | Inventory Alert System | ✅ |
| 11 | Order Management (view / filter / search) | ✅ |
| 12 | Order Cancellation Engine | ✅ |
| 13 | Return & Refund System (partial) | ✅ |
| 14 | Event-Driven System (pub/sub queue) | ✅ |
| 15 | Inventory Reservation Expiry | ✅ |
| 16 | Audit Logging System (immutable) | ✅ |
| 17 | Fraud Detection System | ✅ |
| 18 | Failure Injection System | ✅ |
| 19 | Idempotency Handling | ✅ |
| 20 | Microservice Simulation (loose coupling) | ✅ |

---

## Design Approach

### Architecture

The project is split into distinct layers rather than one giant script:

```
ecommerce_engine/
├── main.py                        # CLI entry point and menu
├── models/
│   ├── product.py                 # Product dataclass
│   ├── cart.py                    # Cart + CartItem dataclasses
│   └── order.py                   # Order dataclass + state machine
├── services/
│   ├── product_service.py         # Inventory management + per-product locks
│   ├── cart_service.py            # Cart ops + reservation TTL
│   ├── discount_service.py        # Coupon + discount rules
│   ├── payment_service.py         # Payment simulation
│   ├── order_service.py           # Atomic order placement + rollback
│   ├── fraud_service.py           # Fraud detection rules
│   ├── concurrency_simulator.py   # Multi-threaded race condition demo
│   └── failure_injection.py       # Random subsystem failure simulation
└── utils/
    ├── logger.py                  # Immutable append-only audit log
    ├── event_bus.py               # Pub/sub event queue
    └── display.py                 # CLI formatting helpers
```

### Key Design Decisions

**Thread-safe stock reservation** — Each product has its own `threading.Lock`. When a user adds an item to cart, the stock is reserved immediately. If two users race for the last unit, only one can acquire the lock and succeed.

**Atomic order placement** — Order placement follows a strict 5-step sequence. If payment fails at step 7, every prior action (stock deduction, order creation) is rolled back before returning. The user's cart is only cleared on success.

**Order State Machine** — Valid status transitions are defined in a dictionary on the `Order` model. Any attempt to jump to an invalid state (e.g. SHIPPED → CREATED) is rejected at the model level, not just the service level.

**Idempotency** — Before placing an order, a key is computed from `(user_id, frozenset of cart items)`. If that exact combination was already ordered, the request is silently rejected, preventing duplicate orders from double-clicks or retries.

**Immutable audit log** — The `AuditLogger` class exposes only an `append` method. It returns a copy of the log list on reads so callers cannot mutate history.

**Event Bus** — A lightweight pub/sub system fires events like `ORDER_CREATED`, `PAYMENT_SUCCESS`, `INVENTORY_UPDATED` after each operation. Handlers execute in registration order; a failing handler stops the chain.

**Microservice boundaries** — Each service class owns its domain and communicates only through well-defined method calls. `OrderService` depends on `ProductService`, `CartService`, `DiscountEngine`, `PaymentService`, and `FraudDetectionService` — all injected at startup, making them easy to swap or mock.

---

## Assumptions

- Payment fails ~30% of the time (configurable via `PaymentService(failure_rate=...)`)
- Cart reservations expire after 10 minutes of inactivity
- Fraud is flagged when a user places 3+ orders within 60 seconds, or a single order exceeds ₹10,000
- Low stock threshold is 5 units
- Coupons available: `SAVE10` (10% off), `FLAT200` (₹200 flat off)
- Discounts stack: bulk discount + coupon can apply together
- Prices are locked at time of order (not recalculated if price changes later)

---

## How to Run

**Requirements:** Python 3.7+, no external dependencies.

```bash
cd ecommerce_engine
python main.py
```

On startup you'll be asked if you want to load demo products (P001–P006). Choose `y` to get started immediately.

### CLI Menu

```
── Product Management ─────────────────
 1. Add Product
 2. View Products
 3. Update Stock

── Cart ───────────────────────────────
 4. Add to Cart
 5. Remove from Cart
 6. View Cart
 7. Apply Coupon

── Orders ─────────────────────────────
 8. Place Order
 9. Cancel Order
10. Return Product
11. View Orders
12. Update Order Status

── System ─────────────────────────────
13. Low Stock Alert
14. Simulate Concurrent Users
15. Trigger Failure Mode
16. View Event Queue
17. View Audit Logs
```

### Quick Demo Flow

```
1. Start → load demo data (y)
2. Option 2  → view products
3. Option 4  → add to cart (user: alice, product: P001, qty: 1)
4. Option 4  → add to cart (user: alice, product: P002, qty: 4)
5. Option 6  → view cart (alice)
6. Option 8  → place order (alice, coupon: SAVE10)
7. Option 12 → update order status → SHIPPED
8. Option 14 → simulate 5 concurrent users racing for P003 (stock=3)
9. Option 17 → view audit logs
```

---

## Coupon Codes

| Code | Effect |
|------|--------|
| `SAVE10` | 10% off the order subtotal |
| `FLAT200` | ₹200 flat discount |

Automatic discounts (no code needed):
- Order total > ₹1000 → 10% off
- Any product ordered in qty > 3 → extra 5% off
