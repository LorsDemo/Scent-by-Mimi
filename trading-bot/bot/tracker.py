"""Signal track record: logs every signal and later checks whether it hit target or stop.

This is the honest scoreboard. If the bot's signals don't win here over weeks, don't trade them.
"""
import json
import pathlib
import threading
import uuid
import pandas as pd

EXPIRE_BARS = 120   # a signal that hits neither level within this many bars is closed as "expired"


def _utc(x):
    t = pd.Timestamp(x)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo else t


def _naive_index(df):
    return df.index.tz_convert("UTC").tz_localize(None) if df.index.tz is not None else df.index


class Tracker:
    def __init__(self, path=None):
        self.path = pathlib.Path(path or pathlib.Path(__file__).resolve().parent.parent / "signals_log.json")
        self.lock = threading.Lock()
        self.items = []
        if self.path.exists():
            try:
                self.items = json.loads(self.path.read_text())
            except Exception:
                self.items = []

    def _save(self):
        self.path.write_text(json.dumps(self.items[-1000:], indent=1))

    def record(self, sig):
        """Store a BUY/SELL signal once. Returns (item, is_new)."""
        with self.lock:
            for it in self.items:
                if it["pair"] == sig.pair and it["time"] == sig.time and it["side"] == sig.side:
                    return it, False
            # don't stack the same direction while one is still open on this pair
            for it in self.items:
                if it["pair"] == sig.pair and it["side"] == sig.side and it["status"] == "open":
                    return it, False
            it = {"id": uuid.uuid4().hex[:8], **sig.to_dict(), "status": "open", "ai": None}
            self.items.append(it)
            self._save()
            return it, True

    def attach_ai(self, item_id, ai_result):
        with self.lock:
            for it in self.items:
                if it["id"] == item_id:
                    it["ai"] = ai_result
            self._save()

    def resolve(self, pair, df):
        """Check open signals of this pair against candles that formed after the signal."""
        idx = _naive_index(df)
        with self.lock:
            changed = False
            for it in self.items:
                if it["pair"] != pair or it["status"] != "open":
                    continue
                after = df[idx > _utc(it["time"])]
                for n, (t, bar) in enumerate(after.iterrows(), 1):
                    buy = it["side"] == "BUY"
                    hit_sl = bar.low <= it["stop"] if buy else bar.high >= it["stop"]
                    hit_tp = bar.high >= it["target"] if buy else bar.low <= it["target"]
                    if hit_sl:                       # pessimistic: stop wins if both in one bar
                        it.update(status="loss", r=-1.0, closed=str(t)); changed = True; break
                    if hit_tp:
                        it.update(status="win", r=it["rr"], closed=str(t)); changed = True; break
                    if n >= EXPIRE_BARS:
                        it.update(status="expired", r=0.0, closed=str(t)); changed = True; break
            if changed:
                self._save()

    def summary(self):
        done = [i for i in self.items if i["status"] in ("win", "loss")]
        wins = [i for i in done if i["status"] == "win"]
        return {"total": len(self.items), "open": sum(i["status"] == "open" for i in self.items),
                "closed": len(done), "wins": len(wins), "losses": len(done) - len(wins),
                "win_rate": round(len(wins) / len(done) * 100, 1) if done else None,
                "total_R": round(sum(i.get("r", 0) for i in done), 2)}

    def recent(self, n=50):
        return list(reversed(self.items[-n:]))
