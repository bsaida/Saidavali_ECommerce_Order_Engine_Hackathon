import random
import time
from utils.logger import logger


class FailureInjectionService:
    """
    Simulates random system-level failures for testing resilience.
    Each subsystem can independently succeed or fail.
    """

    FAILURE_RATE = 0.40  # 40% chance of failure per subsystem

    def run_simulation(self):
        subsystems = [
            ("Payment Gateway", "payment"),
            ("Order Creation", "order_creation"),
            ("Inventory Update", "inventory"),
        ]

        print("\n  Running failure injection across all subsystems...\n")
        all_ok = True

        for name, key in subsystems:
            time.sleep(0.2)
            failed = random.random() < self.FAILURE_RATE
            if failed:
                all_ok = False
                logger.log(f"Failure injection: {name} FAILED")
                print(f"  ❌  {name:<25} → FAILED")
            else:
                print(f"  ✅  {name:<25} → OK")

        print()
        if not all_ok:
            print("  ⚠️   Some subsystems failed. System attempting recovery...")
            time.sleep(0.3)
            print("  ✅  Recovery complete. Services back online.")
            logger.log("Failure injection: recovery completed")
        else:
            print("  ✅  All subsystems healthy.")
