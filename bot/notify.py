import requests
from .config import Cfg
def tg(msg:str):
    if not Cfg.TELEGRAM_BOT_TOKEN or not Cfg.TELEGRAM_CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{Cfg.TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={"chat_id":Cfg.TELEGRAM_CHAT_ID,"text":msg}, timeout=5)
    except Exception: pass
