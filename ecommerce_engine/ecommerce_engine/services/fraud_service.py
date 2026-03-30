from collections import defaultdict
from datetime import datetime
from typing import List


HIGH_VALUE_THRESHOLD = 10000.0
ORDER_RATE_LIMIT = 3         # orders
ORDER_RATE_WINDOW_SEC = 60   # within this many seconds


class FraudDetectionService:
    """
    Flags suspicious activity based on:
    - 3+ orders placed within 1 minute
    - High-value orders (> ₹10,000)
    """

    def __init__(self):
        self._order_timestamps = defaultdict(list)  # user_id -> [datetime]
        self._flagged_users = set()

    def check(self, user_id: str, order_total: float) -> List[str]:
        """Returns a list of fraud flags (empty = clean)."""
        flags = []

        # Rate-based check
        now = datetime.now()
        recent = [
            t for t in self._order_timestamps[user_id]
            if (now - t).total_seconds() < ORDER_RATE_WINDOW_SEC
        ]
        if len(recent) >= ORDER_RATE_LIMIT:
            flags.append(
                f"{user_id} placed {len(recent)} orders in the last minute — rate limit exceeded"
            )
            self._flagged_users.add(user_id)

        # High-value check
        if order_total > HIGH_VALUE_THRESHOLD:
            flags.append(
                f"High-value order ₹{order_total:.2f} flagged as suspicious"
            )

        return flags

    def record_order(self, user_id: str, total: float):
        """Call this after a successful order to update tracking data."""
        self._order_timestamps[user_id].append(datetime.now())

    def is_flagged(self, user_id: str) -> bool:
        return user_id in self._flagged_users

    def flagged_users(self) -> set:
        return set(self._flagged_users)
