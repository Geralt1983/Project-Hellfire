"""Hedging logic for the carry trading bot."""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from .config import Cfg
from .metrics import carry_apr_gauge, open_positions, orders_total, venue_exposure_pct
from .notify import tg


log = logging.getLogger(__name__)


class Hedger:
    """Determine the best venue and place hedges when edge exists."""

    def __init__(self, venues: Dict[str, object], state: object) -> None:
        self.venues = venues
        self.state = state
        self.prev_carry_sign: int | None = None
        self.open_count = 0

    def carry(self, venue: object) -> Tuple[float, float]:
        """Return total carry APR and funding APR for a given venue."""

        spot, perp = venue.prices()
        basis = (perp - spot) / spot * 365 * 100.0
        funding = venue.funding_annualized()
        return basis + funding, funding

    def best(self) -> Tuple[str, float]:
        """Find the venue with the highest carry and update metrics."""

        scores: Dict[str, float] = {}
        fundings: Dict[str, float] = {}
        for name, venue in self.venues.items():
            score, funding = self.carry(venue)
            scores[name] = score
            fundings[name] = funding

        best_name = max(scores, key=scores.get)
        carry_apr_gauge.set(scores[best_name])

        avg_funding = sum(fundings.values()) / max(len(fundings), 1)
        self.state.update_ema(avg_funding)

        for venue_name in scores:
            venue_exposure_pct.labels(venue_name).set(0.0)

        return best_name, scores[best_name]

    def funding_flip(self, current_carry: float) -> bool:
        """Detect if funding sign flips relative to previous check."""

        sign = 1 if current_carry >= 0 else -1
        flipped = self.prev_carry_sign is not None and sign != self.prev_carry_sign
        self.prev_carry_sign = sign
        return flipped

    def active_threshold(self, base_min: float) -> float:
        """Return the dynamic carry threshold based on EMA of funding."""

        ema = self.state.get_ema()
        if ema is None:
            return base_min
        if ema < 3.0:
            return max(base_min, Cfg.DYN_RAISE3)
        if ema < 5.0:
            return max(base_min, Cfg.DYN_RAISE5)
        return base_min

    def enter_if_edge(self, venue_name: str, dry: bool = True):
        """Execute a market hedge if carry exceeds threshold."""

        venue = self.venues[venue_name]
        carry, _ = self.carry(venue)
        threshold = self.active_threshold(Cfg.MIN_CARRY_APR)
        if carry < threshold:
            log.info("No entry. carry %.2f%% < threshold %.2f%%", carry, threshold)
            return None, threshold

        side_spot, side_perp = ("buy", "sell") if carry >= 0 else ("sell", "buy")
        result = venue.place_market_hedge(side_spot, side_perp, Cfg.ORDER_SIZE_USD, dry)
        self.open_count += 1
        open_positions.set(self.open_count)
        orders_total.inc()
        tg(
            f"[CRYPTObot] Hedge {'+' if carry >= 0 else '-'}carry {carry:.2f}% @ {venue_name} size ${Cfg.ORDER_SIZE_USD}"
        )
        return result, threshold
