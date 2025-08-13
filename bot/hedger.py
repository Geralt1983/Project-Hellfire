import logging
from .metrics import carry_apr_gauge, venue_exposure_pct, open_positions, orders_total
from .config import Cfg
from .notify import tg
log = logging.getLogger(__name__)
class Hedger:
    def __init__(self, venues, state):
        self.venues=venues; self.state=state; self.prev_carry_sign=None; self.open_count=0
    def carry(self, v): 
        spot,perp=v.prices(); basis=(perp-spot)/spot*365*100.0; f=v.funding_annualized(); return basis+f, f
    def best(self):
        scores={}; fundings={}
        for n,v in self.venues.items(): c,f=self.carry(v); scores[n]=c; fundings[n]=f
        name=max(scores, key=scores.get); carry_apr_gauge.set(scores[name])
        avg_f = sum(fundings.values())/max(len(fundings),1); self.state.update_ema(avg_f)
        for vn in scores.keys(): venue_exposure_pct.labels(vn).set(0.0)
        return name, scores[name]
    def funding_flip(self, current_carry):
        sign=1 if current_carry>=0 else -1; flipped=self.prev_carry_sign is not None and sign!=self.prev_carry_sign
        self.prev_carry_sign=sign; return flipped
    def active_threshold(self, base_min: float) -> float:
        ema=self.state.get_ema()
        if ema is None: return base_min
        if ema < 3.0: return max(base_min, Cfg.DYN_RAISE3)
        if ema < 5.0: return max(base_min, Cfg.DYN_RAISE5)
        return base_min
    def enter_if_edge(self, venue_name, dry=True):
        v=self.venues[venue_name]; c,_=self.carry(v); thr=self.active_threshold(Cfg.MIN_CARRY_APR)
        if c < thr: log.info("No entry. carry %.2f%% < threshold %.2f%%", c, thr); return None, thr
        side_spot, side_perp=("buy","sell") if c>=0 else ("sell","buy")
        res=v.place_market_hedge(side_spot, side_perp, Cfg.ORDER_SIZE_USD, dry)
        self.open_count += 1; open_positions.set(self.open_count)
        orders_total.inc(); tg(f"[CRYPTObot] Hedge {'+' if c>=0 else '-'}carry {c:.2f}% @ {venue_name} size ${Cfg.ORDER_SIZE_USD}")
        return res, thr
