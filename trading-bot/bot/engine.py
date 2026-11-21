import datetime as dt
import threading
import time
from .data import make_source, get_frames, OandaData
from .signals import build_signal
from .risk import RiskManager, units_for_risk
from .broker import PaperBroker, OandaBroker
from . import ai


class Engine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.src = make_source(cfg)
        self.broker = OandaBroker(cfg) if cfg.live_enabled else PaperBroker(cfg.start_balance)
        self.risk = RiskManager(cfg)
        self.signals, self.log = {}, []
        self.auto = False
        self._t = None

    def note(self, msg):
        self.log.append(f"{dt.datetime.utcnow():%H:%M:%S} {msg}")
        self.log = self.log[-200:]

    @property
    def data_source(self):
        return type(self.src).__name__.replace("Data", "").lower() if self.src else "synthetic-demo"

    def analyze(self, pair, with_ai=False, question=None):
        df, htf = get_frames(self.cfg, pair, 500, self.src)
        sig = build_signal(pair, df, htf, self.cfg.min_score)
        self.signals[pair] = sig
        out = {"signal": sig.to_dict(), "data_source": self.data_source}
        if with_ai:
            out["ai"] = ai.analyze(self.cfg, sig, df, question)
        return out

    def scan(self):
        return [self.analyze(p)["signal"] for p in self.cfg.pairs]

    def step(self):
        """One full cycle: update open trades, scan, execute qualifying signals."""
        prices = {}
        for p in self.cfg.pairs:
            df, htf = get_frames(self.cfg, p, 500, self.src)
            last = df.iloc[-1]
            prices[p] = (float(last.high), float(last.low), float(last.close))
            sig = build_signal(p, df, htf, self.cfg.min_score)
            self.signals[p] = sig
            self.broker.update({p: prices[p]})
            if sig.side == "NONE":
                continue
            eq = self.broker.equity({k: v[2] for k, v in prices.items()})
            st = self.broker.state()
            ok, why = self.risk.can_trade(eq, st["open"], p, dt.date.today())
            if not ok:
                self.note(f"{p} {sig.side} skipped: {why}")
                continue
            if ai.enabled(self.cfg):
                v = ai.analyze(self.cfg, sig, df)
                if v.get("verdict") == "SKIP":
                    self.note(f"{p} {sig.side} vetoed by AI: {v.get('summary','')[:90]}")
                    continue
            units = units_for_risk(p, eq, self.cfg.risk_per_trade, sig.entry, sig.stop)
            if units <= 0:
                continue
            self.broker.place(sig, units)
            self.note(f"{self.broker.name.upper()} {sig.side} {p} x{units} @ {sig.entry:.5f} "
                      f"SL {sig.stop:.5f} TP {sig.target:.5f} score {sig.score}")

    def start(self, every=300):
        if self._t and self._t.is_alive():
            return
        self.auto = True

        def loop():
            while self.auto:
                try:
                    self.step()
                except Exception as e:  # keep the bot alive, surface the error
                    self.note(f"ERROR {e}")
                time.sleep(every)
        self._t = threading.Thread(target=loop, daemon=True)
        self._t.start()
        self.note(f"auto-trading started ({self.broker.name})")

    def stop(self):
        self.auto = False
        self.note("auto-trading stopped")
