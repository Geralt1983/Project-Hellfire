import time, asyncio, logging, threading
from dotenv import load_dotenv
from aiohttp import web
from .config import Cfg
from .metrics import boot_metrics, metrics_updated_ts, min_carry_threshold, errors_total, net_delta_usd
from .notify import tg
from .exchanges import Venue
from .hedger import Hedger
from .risk import Watchdog
from .state import State
from .health import build_app
from .rebalancer import Rebalancer
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
def build():
    load_dotenv(); wd=Watchdog(); st=State(); st.load()
    venues={"binance": Venue("binance","future","spot", Cfg.SYMBOL, f"{Cfg.SYMBOL}:USDT"),
            "bybit":   Venue("bybit","swap","spot",   Cfg.SYMBOL, f"{Cfg.SYMBOL}:USDT")}
    hedger=Hedger(venues, st); reb=Rebalancer(venues, get_delta_usd=lambda: 0.0)  # TODO: replace with real delta
    return hedger, wd, st, venues, reb
def daily_summary_loop(st):
    while True:
        now=time.gmtime(); secs=(24-now.tm_hour-1)*3600 + (60-now.tm_min-1)*60 + (60-now.tm_sec) + 5*60
        time.sleep(secs); ema=st.get_ema(); tg(f"[CRYPTObot] Daily summary {time.strftime('%Y-%m-%d', time.gmtime())}: EMA funding={ema if ema is not None else 0:.2f}%")
async def aiohttp_main(shared):
    app=build_app(shared); runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner, "0.0.0.0", 8000); await site.start()
    while True: await asyncio.sleep(3600)
def loop_once(hedger, wd):
    name, carry = hedger.best(); thr=hedger.active_threshold(Cfg.MIN_CARRY_APR); min_carry_threshold.set(thr)
    if not wd.ok_or_pause(): return
    try:
        if hedger.funding_flip(carry) and abs(carry) < thr:
            tg(f"[CRYPTObot] Funding flip detected. Carry {carry:.2f}% < thr {thr:.2f}%. Holding."); return
        hedger.enter_if_edge(name, dry=Cfg.DRY_RUN); net_delta_usd.set(0.0)
    except Exception as e:
        logging.exception("loop error: %s", e); errors_total.inc(); wd.record_error(e)
    finally:
        wd.mark_metrics(); metrics_updated_ts.set(time.time())
def start_rebalancer(reb):
    while True:
        time.sleep(3600)
        try: reb.run_once()
        except Exception as e: logging.warning("Rebalancer error: %s", e)
if __name__ == "__main__":
    hedger, wd, st, venues, reb = build(); boot_metrics(8000); tg("[CRYPTObot] started")
    threading.Thread(target=daily_summary_loop, args=(st,), daemon=True).start()
    threading.Thread(target=start_rebalancer, args=(reb,), daemon=True).start()
    shared={"watchdog": wd, "age_limit": int(os.getenv("POLL_SECONDS","900"))*2}
    asyncio.get_event_loop().create_task(aiohttp_main(shared))
    while True:
        loop_once(hedger, wd); time.sleep(int(os.getenv("POLL_SECONDS","900")))
