from datetime import datetime
from typing import List


class AuditLogger:
    """
    Immutable append-only audit log.
    Once a log entry is written, it cannot be modified or deleted.
    """

    def __init__(self):
        self._logs: List[str] = []

    def log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self._logs.append(entry)

    def get_all(self) -> List[str]:
        # return a copy so no one can mutate the internal list
        return list(self._logs)

    def get_recent(self, n: int = 20) -> List[str]:
        return list(self._logs[-n:])

    def __len__(self):
        return len(self._logs)


# single shared instance
logger = AuditLogger()
