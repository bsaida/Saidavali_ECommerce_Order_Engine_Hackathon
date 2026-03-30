from typing import Dict, Tuple, Optional

COUPONS: Dict[str, Tuple[str, float]] = {
    "SAVE10": ("percent", 10.0),
    "FLAT200": ("flat", 200.0),
}


class DiscountEngine:
    """
    Calculates applicable discounts.

    Rules:
    - Order total > ₹1000  -> 10% discount
    - Any single product qty > 3 -> extra 5%
    - Coupon SAVE10  -> 10% off
    - Coupon FLAT200 -> ₹200 flat off

    Combinations are allowed but a coupon stacks on top of rule discounts.
    Invalid combinations (e.g. two coupons) are blocked at CLI level.
    """

    def calculate(
        self,
        items: Dict[str, int],          # product_id -> qty
        prices: Dict[str, float],        # product_id -> unit price
        coupon_code: Optional[str] = None,
    ) -> Tuple[float, float, float, str]:
        """
        Returns: (subtotal, discount_amount, final_total, breakdown_string)
        """
        subtotal = sum(prices[pid] * qty for pid, qty in items.items())
        discount = 0.0
        breakdown_parts = []

        # Rule 1
        if subtotal > 1000:
            rule1_disc = subtotal * 0.10
            discount += rule1_disc
            breakdown_parts.append(f"Order > ₹1000 → -₹{rule1_disc:.2f} (10%)")

        # Rule 2
        for pid, qty in items.items():
            if qty > 3:
                rule2_disc = subtotal * 0.05
                discount += rule2_disc
                breakdown_parts.append(
                    f"Qty > 3 for {pid} → -₹{rule2_disc:.2f} (extra 5%)"
                )
                break  # only apply once even if multiple products qualify

        # Coupon
        coupon_note = ""
        if coupon_code:
            code = coupon_code.upper().strip()
            if code in COUPONS:
                ctype, cval = COUPONS[code]
                if ctype == "percent":
                    coupon_disc = subtotal * (cval / 100)
                    coupon_note = f"Coupon {code} → -₹{coupon_disc:.2f} ({cval:.0f}%)"
                else:
                    coupon_disc = min(cval, subtotal)
                    coupon_note = f"Coupon {code} → -₹{coupon_disc:.2f} (flat)"
                discount += coupon_disc
                breakdown_parts.append(coupon_note)
            else:
                breakdown_parts.append(f"Coupon '{code}' is invalid — ignored")

        discount = min(discount, subtotal)
        final = subtotal - discount
        breakdown = "\n    ".join(breakdown_parts) if breakdown_parts else "No discounts applied"

        return subtotal, discount, final, breakdown

    def is_valid_coupon(self, code: str) -> bool:
        return code.upper().strip() in COUPONS
