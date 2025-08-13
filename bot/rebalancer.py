import time, logging
from .config import Cfg
from .metrics import rebalance_count, delta_drift_pct
log = logging.getLogger(__name__)
class Rebalancer:
    def __init__(self, venues, get_delta_usd):
        self.venues=venues; self.get_delta_usd=get_delta_usd
    def run_once(self):
        drift_usd=self.get_delta_usd()
        tol_usd=Cfg.EQUITY_USD*(Cfg.DELTA_TOL_PCT/100.0)
        drift_pct=(abs(drift_usd)/max(Cfg.EQUITY_USD,1))*100.0
        delta_drift_pct.set(drift_pct)
        if abs(drift_usd) <= tol_usd:
            log.info("[REBALANCER] Drift %.2f%% < tol %.2f%% — no action.", drift_pct, Cfg.DELTA_TOL_PCT); return
        venue_name=list(self.venues.keys())[0]; v=self.venues[venue_name]
        side_spot="sell" if drift_usd>0 else "buy"; side_perp="buy" if drift_usd>0 else "sell"
        usd_size=min(abs(drift_usd), Cfg.ORDER_SIZE_USD)
        v.place_limit_hedge(side_spot, side_perp, usd_size, price_offset_bps=2, dry=Cfg.DRY_RUN)
        rebalance_count.inc()
        log.info("[REBALANCER] Drift %+0.2f%% > tol %.2f%% — adjust $%.2f POST-ONLY.", drift_pct, Cfg.DELTA_TOL_PCT, usd_size)
