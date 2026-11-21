import datetime as dt
import threading
import time
from .data import make_source, get_frames
from .signals import build_signal
from .tracker import Tracker
from . import ai


class Engine:
    """Market analyst: scans pairs, logs signals, grades them later, adds AI commentary."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.src = make_source(cfg)
        self.tracker = Tracker()
        self.log = []
        self._t = None

    def note(self, msg):
        self.log.append(f"{dt.datetime.utcnow():%H:%M:%S} {msg}")
        self.log = self.log[-100:]

    @property
    def data_source(self):
        return type(self.src).__name__.replace("Data", "").lower() if self.src else "synthetic-demo"

    def analyze(self, pair, with_ai=False, question=None):
        df, htf = get_frames(self.cfg, pair, 500, self.src)
        sig = build_signal(pair, df, htf, self.cfg.min_score)
        out = {"signal": sig.to_dict(), "data_source": self.data_source}
        if with_ai:
            out["ai"] = ai.analyze(self.cfg, sig, df, question)
        return out

    def scan(self):
        out = []
        for p in self.cfg.pairs:
            try:
                out.append(self.analyze(p)["signal"])
            except Exception as e:
                self.note(f"{p} scan error: {e}")
        return out

    def watch_once(self):
        """One cycle: grade old signals, log new ones, attach AI commentary."""
        for p in self.cfg.pairs:
            try:
                df, htf = get_frames(self.cfg, p, 500, self.src)
                self.tracker.resolve(p, df)
                sig = build_signal(p, df, htf, self.cfg.min_score)
                if sig.side == "NONE":
                    continue
                item, new = self.tracker.record(sig)
                if new:
                    self.note(f"NEW {sig.side} {p} score {sig.score}")
                    if ai.enabled(self.cfg):
                        res = ai.analyze(self.cfg, sig, df)
                        if res.get("verdict") == "ERROR":
                            self.note(f"AI error: {res['summary'][:200]}")
                        else:
                            self.tracker.attach_ai(item["id"], res)
            except Exception as e:
                self.note(f"{p} error: {e}")

    def start_watch(self, every=900):
        if self._t and self._t.is_alive() or not self.src:
            return

        def loop():
            while True:
                self.watch_once()
                time.sleep(every)
        self._t = threading.Thread(target=loop, daemon=True)
        self._t.start()
        self.note(f"watching {len(self.cfg.pairs)} pairs every {every // 60} min")
