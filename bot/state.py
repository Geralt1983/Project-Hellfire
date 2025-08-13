import time, json, os
class State:
    def __init__(self): self.path="state.json"; self.ema=None; self.samples=[]
    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path,"r") as f: d=json.load(f); self.ema=d.get("ema"); self.samples=d.get("samples",[])
        except Exception: pass
    def save(self):
        try:
            with open(self.path,"w") as f: import json; json.dump({"ema":self.ema,"samples":self.samples[-1000:]}, f)
        except Exception: pass
    def update_ema(self, value: float, span_hours: int = 24*7):
        a=2/(span_hours+1); self.ema = value if self.ema is None else a*value + (1-a)*self.ema
        self.samples.append({"ts": int(time.time()), "funding_ann": value}); self.save()
    def get_ema(self): return self.ema
