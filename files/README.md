# Distributed E-Commerce Order Engine

## Project Overview
A menu-driven CLI application simulating a real-world distributed e-commerce backend engine, covering inventory management, multi-user carts, order processing, payment simulation, fraud detection, and more.

## Features Implemented (All 20 Tasks)

| Task | Feature |
|------|---------|
| 1 | Product Management (add, view, update stock) |
| 2 | Multi-User Cart System |
| 3 | Real-Time Stock Reservation |
| 4 | Concurrency Simulation with thread locking |
| 5 | Order Placement Engine (atomic) |
| 6 | Payment Simulation (success/failure) |
| 7 | Transaction Rollback System |
| 8 | Order State Machine |
| 9 | Discount & Coupon Engine |
| 10 | Inventory Alert System |
| 11 | Order Management (view/filter/search) |
| 12 | Order Cancellation Engine |
| 13 | Return & Refund System |
| 14 | Event-Driven System |
| 15 | Inventory Reservation Expiry |
| 16 | Audit Logging System (immutable) |
| 17 | Fraud Detection System |
| 18 | Failure Injection System |
| 19 | Idempotency Handling |
| 20 | Microservice Simulation (loose coupling) |

## Design Approach
- **Threading Locks** per product to prevent overselling (Task 4)
- **Atomic order placement** — all-or-nothing with rollback (Tasks 5, 7)
- **State machine** for order lifecycle validation (Task 8)
- **Immutable audit log** list appended only (Task 16)
- **Event queue** simulating pub/sub pattern (Task 14)
- **Microservice classes**: ProductService, CartService, OrderService, PaymentService (Task 20)

## Assumptions
- Payments fail ~30% of the time (random simulation)
- Reservations expire after 10 minutes
- Fraud flagged if user places 3+ orders in 1 minute, or order > ₹10,000
- Coupons: SAVE10 (10% off), FLAT200 (₹200 flat off)
- Low stock threshold: 5 units

## How to Run

```bash
python ecommerce_engine.py
```

Python 3.7+ required. No external dependencies.

### Quick Start
1. Run the script
2. Choose `y` to load demo products (P001–P004)
3. Navigate the CLI menu (options 1–16)
