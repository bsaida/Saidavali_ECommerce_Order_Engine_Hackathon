import threading
from typing import Dict, Optional

from models.product import Product
from utils.logger import logger
from utils.display import success, error, warn


LOW_STOCK_THRESHOLD = 5


class ProductService:
    """
    Handles all product-related operations.
    Maintains per-product threading locks to handle concurrent access safely.
    """

    def __init__(self):
        self._products: Dict[str, Product] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_lock(self, product_id: str) -> threading.Lock:
        with self._global_lock:
            if product_id not in self._locks:
                self._locks[product_id] = threading.Lock()
            return self._locks[product_id]

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_product(self, product_id: str, name: str, price: float, stock: int) -> bool:
        if product_id in self._products:
            error(f"Product ID '{product_id}' already exists.")
            return False
        if stock < 0:
            error("Stock cannot be negative.")
            return False
        if price <= 0:
            error("Price must be greater than 0.")
            return False

        self._products[product_id] = Product(
            product_id=product_id,
            name=name,
            price=price,
            stock=stock,
        )
        logger.log(f"Product added: {product_id} | name={name} | price={price} | stock={stock}")
        success(f"Product '{name}' ({product_id}) added successfully.")
        return True

    def get_product(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)

    def product_exists(self, product_id: str) -> bool:
        return product_id in self._products

    def update_stock(self, product_id: str, new_stock: int) -> bool:
        if product_id not in self._products:
            error(f"Product '{product_id}' not found.")
            return False
        if new_stock < 0:
            error("Stock cannot be negative.")
            return False

        with self._get_lock(product_id):
            old = self._products[product_id].stock
            self._products[product_id].stock = new_stock

        logger.log(f"Stock updated: {product_id} | {old} -> {new_stock}")
        success(f"Stock updated to {new_stock}.")
        return True

    def list_products(self) -> Dict[str, Product]:
        return dict(self._products)

    # ── RESERVATION (for cart / concurrency) ──────────────────────────────────

    def reserve_stock(self, product_id: str, qty: int, release_existing: int = 0) -> bool:
        """
        Thread-safe stock reservation.
        release_existing: qty already reserved by this user (e.g. updating cart qty)
        """
        with self._get_lock(product_id):
            p = self._products.get(product_id)
            if p is None:
                return False
            # release old reservation first, then try new
            p.reserved = max(0, p.reserved - release_existing)
            if not p.reserve(qty):
                # put old reservation back
                p.reserved += release_existing
                return False
            return True

    def release_stock(self, product_id: str, qty: int):
        with self._get_lock(product_id):
            p = self._products.get(product_id)
            if p:
                p.release(qty)

    def deduct_stock(self, product_id: str, qty: int) -> bool:
        """Called when an order is confirmed (payment success)."""
        with self._get_lock(product_id):
            p = self._products.get(product_id)
            if p is None:
                return False
            return p.deduct(qty)

    def restore_stock(self, product_id: str, qty: int):
        """Called on rollback or cancellation."""
        with self._get_lock(product_id):
            p = self._products.get(product_id)
            if p:
                p.restock(qty)

    # ── DISPLAY ───────────────────────────────────────────────────────────────

    def print_all_products(self):
        if not self._products:
            print("  No products in inventory.")
            return

        print(f"\n  {'ID':<10} {'Name':<22} {'Price':>9} {'Stock':>7} {'Reserved':>9} {'Available':>10}")
        print("  " + "-" * 72)
        for p in self._products.values():
            avail = p.available_stock
            flag = "  ⚠️ LOW" if avail <= LOW_STOCK_THRESHOLD else ""
            print(
                f"  {p.product_id:<10} {p.name:<22} ₹{p.price:>8.2f}"
                f" {p.stock:>7} {p.reserved:>9} {avail:>10}{flag}"
            )

    def print_low_stock(self):
        low = [p for p in self._products.values() if p.available_stock <= LOW_STOCK_THRESHOLD]
        if not low:
            success("All products have sufficient stock.")
            return
        print(f"\n  {'ID':<10} {'Name':<22} {'Available':>10}")
        print("  " + "-" * 45)
        for p in low:
            avail = p.available_stock
            status = "OUT OF STOCK" if avail == 0 else f"{avail} units"
            print(f"  {p.product_id:<10} {p.name:<22} {status:>10}")
