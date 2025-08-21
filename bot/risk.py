import logging
import time
from typing import Any

from .config import Cfg
from .metrics import watchdog_trips_total

log = logging.getLogger(__name__)


class Watchdog:
    """Error counter that pauses trading after repeated failures."""

    def __init__(self) -> None:
        self.err_count = 0
        self.paused_until = 0.0
        self.last_metrics_ts = time.time()

    def record_error(self, err: Any) -> None:
        """Record an error and increase the internal counter."""
        self.err_count += 1
        log.warning("Error recorded (%d): %s", self.err_count, err)

    def mark_metrics(self) -> None:
        """Update the timestamp of the last metrics collection."""
        self.last_metrics_ts = time.time()

    def ok_or_pause(self) -> bool:
        """Return ``True`` if trading may continue, otherwise pause trading."""
        now = time.time()
        if now < self.paused_until:
            return False
        if self.err_count >= Cfg.ERROR_TRIP_COUNT:
            watchdog_trips_total.inc()
            self.paused_until = now + Cfg.WATCHDOG_PAUSE_MINUTES * 60
            log.error("Watchdog pause %d min", Cfg.WATCHDOG_PAUSE_MINUTES)
            self.err_count = 0
            return False
        return True
