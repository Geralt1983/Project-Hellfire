"""Primary entry point for the carry-trading bot.

The original implementation bundled much of the logic onto single lines and
loaded environment variables only when ``build`` was called.  This module has
been refactored for readability and to ensure configuration is loaded exactly
once on import.
"""

import asyncio
import logging
import threading
import time

from aiohttp import web

from .config import Cfg
from .exchanges import Venue
from .health import build_app
from .hedger import Hedger
from .metrics import (
    boot_metrics,
    errors_total,
    metrics_updated_ts,
    min_carry_threshold,
    net_delta_usd,
)
from .notify import tg
from .rebalancer import Rebalancer
from .risk import Watchdog
from .state import State


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def build() -> tuple[Hedger, Watchdog, State, dict, Rebalancer]:
    """Initialise core components for the bot."""

    watchdog = Watchdog()
    state = State()
    state.load()

    venues = {
        "binance": Venue("binance", "future", "spot", Cfg.SYMBOL, f"{Cfg.SYMBOL}:USDT"),
        "bybit": Venue("bybit", "swap", "spot", Cfg.SYMBOL, f"{Cfg.SYMBOL}:USDT"),
    }

    hedger = Hedger(venues, state)
    rebalancer = Rebalancer(venues, get_delta_usd=lambda: 0.0)  # TODO: real delta

    return hedger, watchdog, state, venues, rebalancer


def daily_summary_loop(state: State) -> None:
    """Send a daily EMA summary via Telegram."""

    while True:
        now = time.gmtime()
        secs = (
            (24 - now.tm_hour - 1) * 3600
            + (60 - now.tm_min - 1) * 60
            + (60 - now.tm_sec)
            + 5 * 60
        )
        time.sleep(secs)
        ema = state.get_ema() or 0.0
        tg(
            f"[CRYPTObot] Daily summary {time.strftime('%Y-%m-%d', time.gmtime())}: "
            f"EMA funding={ema:.2f}%"
        )


async def aiohttp_main(shared: dict) -> None:
    """Run the HTTP server exposing metrics and health endpoints."""

    app = build_app(shared)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    while True:  # pragma: no cover - background server loop
        await asyncio.sleep(3600)


def loop_once(hedger: Hedger, watchdog: Watchdog) -> None:
    """Execute a single hedging iteration."""

    name, carry = hedger.best()
    thr = hedger.active_threshold(Cfg.MIN_CARRY_APR)
    min_carry_threshold.set(thr)

    if not watchdog.ok_or_pause():
        return

    try:
        if hedger.funding_flip(carry) and abs(carry) < thr:
            tg(
                f"[CRYPTObot] Funding flip detected. Carry {carry:.2f}% < thr {thr:.2f}%. "
                "Holding."
            )
            return

        hedger.enter_if_edge(name, dry=Cfg.DRY_RUN)
        net_delta_usd.set(0.0)
    except Exception as exc:  # broad: log and forward to watchdog
        logging.exception("loop error: %s", exc)
        errors_total.inc()
        watchdog.record_error(exc)
    finally:
        watchdog.mark_metrics()
        metrics_updated_ts.set(time.time())


def start_rebalancer(reb: Rebalancer) -> None:
    """Background thread that triggers a rebalance once per hour."""

    while True:
        time.sleep(3600)
        try:
            reb.run_once()
        except Exception as exc:  # pragma: no cover - log warning
            logging.warning("Rebalancer error: %s", exc)


def main() -> None:
    """Start the bot and its background tasks."""

    hedger, watchdog, state, venues, rebalancer = build()
    boot_metrics(8000)
    tg("[CRYPTObot] started")

    threading.Thread(target=daily_summary_loop, args=(state,), daemon=True).start()
    threading.Thread(target=start_rebalancer, args=(rebalancer,), daemon=True).start()

    shared = {"watchdog": watchdog, "age_limit": Cfg.POLL_SECONDS * 2}
    asyncio.get_event_loop().create_task(aiohttp_main(shared))

    while True:
        loop_once(hedger, watchdog)
        time.sleep(Cfg.POLL_SECONDS)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()

