import os, ccxt, logging
from .config import Cfg
log = logging.getLogger(__name__)
class Venue:
    def __init__(self, name:str, fut_type:str, spot_type:str, spot_symbol:str, perp_symbol:str):
        self.name=name
        cls=getattr(ccxt, name)
        self.fut=cls({"apiKey":os.getenv(f"API_KEY_{name.upper()}",""),"secret":os.getenv(f"API_SECRET_{name.upper()}",""),
                      "enableRateLimit":True,"options":{"defaultType":fut_type}})
        self.spot=cls({"apiKey":os.getenv(f"API_KEY_{name.upper()}",""),"secret":os.getenv(f"API_SECRET_{name.upper()}",""),
                       "enableRateLimit":True,"options":{"defaultType":spot_type}})
        self.spot_symbol=spot_symbol; self.perp_symbol=perp_symbol
        if Cfg.BROKER_MODE=="paper":
            for ex in (self.fut,self.spot):
                try: ex.set_sandbox_mode(True)
                except Exception: pass
    def prices(self):
        st=self.spot.fetch_ticker(self.spot_symbol); ft=self.fut.fetch_ticker(self.perp_symbol)
        return float(st["last"]), float(ft["last"])
    def funding_annualized(self):
        try:
            fr=self.fut.fetch_funding_rate(self.perp_symbol); rate=float(fr.get("fundingRate",0.0))
            return rate*3*365*100.0
        except Exception as e:
            log.warning("%s funding fetch fail: %s", self.name, e); return 0.0
    def place_market_hedge(self, side_spot, side_perp, usd_size, dry=True):
        spot_p,perp_p=self.prices(); qty_spot=usd_size/spot_p; qty_perp=usd_size/perp_p
        if dry: return {"spot_id":"dry","perp_id":"dry","spot_px":spot_p,"perp_px":perp_p,"qty_spot":qty_spot,"qty_perp":qty_perp}
        so=self.spot.create_order(self.spot_symbol,"market",side_spot,qty_spot)
        po=self.fut.create_order(self.perp_symbol,"market",side_perp,qty_perp, params={"reduceOnly":False})
        return {"spot_id":so.get("id"),"perp_id":po.get("id"),"spot_px":spot_p,"perp_px":perp_p,"qty_spot":qty_spot,"qty_perp":qty_perp}
    def place_limit_hedge(self, side_spot, side_perp, usd_size, price_offset_bps=2, dry=True):
        spot_p,perp_p=self.prices()
        m=1 - price_offset_bps/10000 if side_spot=="buy" else 1 + price_offset_bps/10000
        m2=1 + price_offset_bps/10000 if side_perp=="sell" else 1 - price_offset_bps/10000
        spot_price=spot_p*m; perp_price=perp_p*m2; qty_spot=usd_size/spot_p; qty_perp=usd_size/perp_p
        if dry: return {"spot_id":"dryL","perp_id":"dryL","spot_px":spot_price,"perp_px":perp_price,"qty_spot":qty_spot,"qty_perp":qty_perp}
        so=self.spot.create_order(self.spot_symbol,"limit",side_spot,qty_spot,spot_price, params={"postOnly":True})
        po=self.fut.create_order(self.perp_symbol,"limit",side_perp,qty_perp,perp_price, params={"postOnly":True})
        return {"spot_id":so.get("id"),"perp_id":po.get("id"),"spot_px":spot_price,"perp_px":perp_price,"qty_spot":qty_spot,"qty_perp":qty_perp}
