import random
import time

from utils.logger import logger
from utils.display import success, error


# tweak this to change how often payments fail during testing
PAYMENT_FAILURE_RATE = 0.30


class PaymentService:
    """
    Simulates payment processing with a configurable failure rate.
    In a real system this would call a payment gateway API.
    """

    def __init__(self, failure_rate: float = PAYMENT_FAILURE_RATE):
        self.failure_rate = failure_rate
        self._total_processed = 0
        self._total_failed = 0

    def process(self, order_id: str, amount: float, user_id: str) -> bool:
        print(f"  💳  Processing payment of ₹{amount:.2f} for order {order_id}...")
        time.sleep(0.4)  # simulate network latency

        self._total_processed += 1
        if random.random() < self.failure_rate:
            self._total_failed += 1
            logger.log(f"Payment FAILED: {order_id} | user={user_id} | amount=₹{amount:.2f}")
            error("Payment gateway declined the transaction.")
            return False

        logger.log(f"Payment SUCCESS: {order_id} | user={user_id} | amount=₹{amount:.2f}")
        success(f"Payment of ₹{amount:.2f} accepted.")
        return True

    def stats(self):
        print(f"  Total processed : {self._total_processed}")
        print(f"  Total failed    : {self._total_failed}")
        success_rate = (
            ((self._total_processed - self._total_failed) / self._total_processed * 100)
            if self._total_processed
            else 0
        )
        print(f"  Success rate    : {success_rate:.1f}%")
