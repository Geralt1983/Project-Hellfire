import time, logging
from .config import Cfg
from .metrics import watchdog_trips_total
log = logging.getLogger(__name__)
class Watchdog:
    def __init__(self): self.err_count=0; self.paused_until=0; self.last_metrics_ts=time.time()
    def record_error(self, err): self.err_count+=1; log.warning("Error recorded (%d): %s", self.err_count, err)
    def mark_metrics(self): self.last_metrics_ts=time.time()
    def ok_or_pause(self)->bool:
        if time.time() < self.paused_until: return False
        if self.err_count >= Cfg.ERROR_TRIP_COUNT:
            watchdog_trips_total.inc(); self.paused_until=time.time()+Cfg.WATCHDOG_PAUSE_MINUTES*60
            log.error("Watchdog pause %d min", Cfg.WATCHDOG_PAUSE_MINUTES); self.err_count=0; return False
        return True
