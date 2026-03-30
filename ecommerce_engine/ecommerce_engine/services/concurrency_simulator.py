import threading
from typing import List, Tuple

from utils.logger import logger


class ConcurrencySimulator:
    """
    Simulates multiple users trying to add the same product to their carts
    at the exact same time, demonstrating that the locking mechanism
    prevents overselling.
    """

    def __init__(self, product_service, cart_service):
        self.product_svc = product_service
        self.cart_svc = cart_service

    def run(self, product_id: str, user_count: int, qty_per_user: int) -> List[Tuple[str, bool, str]]:
        product = self.product_svc.get_product(product_id)
        if product is None:
            return []

        results = []
        result_lock = threading.Lock()

        def try_add(user_id: str):
            ok = self.cart_svc.add_to_cart(user_id, product_id, qty_per_user)
            with result_lock:
                msg = "succeeded" if ok else f"failed (only {product.available_stock} available)"
                results.append((user_id, ok, msg))
                logger.log(f"Concurrency sim: {user_id} → {product_id} qty={qty_per_user} | {msg}")

        threads = [
            threading.Thread(target=try_add, args=(f"SimUser_{i+1}",))
            for i in range(user_count)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return results

    def print_results(self, results: List[Tuple[str, bool, str]], product_id: str, stock: int, qty: int):
        p = self.product_svc.get_product(product_id)
        name = p.name if p else product_id

        print(f"\n  Product : {name} ({product_id})")
        print(f"  Stock   : {stock} units  |  Each user wants : {qty}")
        print(f"\n  {'User':<15} {'Result'}")
        print("  " + "-" * 40)
        for user_id, ok, msg in results:
            icon = "✅" if ok else "❌"
            print(f"  {user_id:<15} {icon}  {msg}")

        won = sum(1 for _, ok, _ in results if ok)
        print(f"\n  {won}/{len(results)} users successfully reserved stock.")
        if p:
            print(f"  Remaining available stock: {p.available_stock}")
