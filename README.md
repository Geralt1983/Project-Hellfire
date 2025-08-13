# Cryptobot Production v1.1 (All-in-One)

Delta-neutral BTC/USDT carry (basis + funding) bot for Binance & Bybit.

**Included features**
- Prometheus metrics **/metrics**
- Health endpoint **/health** (200 OK when metrics fresh & watchdog green)
- Docker **HEALTHCHECK** + `restart: always` (self-healing)
- Venue outage watchdog + pause
- Funding flip detector
- Hourly **post-only** rebalancer to keep delta-neutral within ±`DELTA_TOL_PCT` of equity
- Dynamic carry threshold (EMA of 7-day funding): auto-raises to 10–12% in compressed regimes
- Daily Telegram summary (00:05 UTC): orders / errors / flips / avg & max carry
- Telegram alerts on start, orders, watchdog pauses
- Optional JSON persistence for EMA & daily stats

## Quick start (VPS)
1. Install Docker (or run with Python)
2. Upload/unzip this folder
3. `cp .env.example .env` and fill keys
4. `docker compose up -d`

## Ports
- API (metrics + health): `:8000`

## Notes
- Start with `DRY_RUN=true` and `ORDER_SIZE_USD=50`. Flip to live after 24–48h of clean run.
- For equity drift tolerance, set `EQUITY_USD` to your effective account equity (used for rebalancer logic).
