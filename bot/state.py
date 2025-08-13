import json
import os
import time


class State:
    """Persist minimal running state for the bot.

    The state keeps an exponential moving average (EMA) of the funding rate
    and a history of recent samples.  Data is stored in a small JSON file so
    the bot can resume with context after restarts.
    """

    def __init__(self, path: str = "state.json") -> None:
        self.path = path
        self.ema: float | None = None
        self.samples: list[dict] = []

    def load(self) -> None:
        """Load EMA and sample history from disk if the file exists."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        self.ema = data.get("ema")
        self.samples = data.get("samples", [])

    def save(self) -> None:
        """Persist current EMA and truncated sample history to disk."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"ema": self.ema, "samples": self.samples[-1000:]}, f)
        except Exception:
            pass

    def update_ema(self, value: float, span_hours: int = 24 * 7) -> None:
        """Update the EMA with a new value and record the sample."""
        alpha = 2 / (span_hours + 1)
        self.ema = value if self.ema is None else alpha * value + (1 - alpha) * self.ema
        self.samples.append({"ts": int(time.time()), "funding_ann": value})
        self.save()

    def get_ema(self) -> float | None:
        """Return the current EMA value."""
        return self.ema
