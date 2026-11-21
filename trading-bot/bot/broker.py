import uuid
import requests
from .data import HOSTS


class PaperBroker:
    """Simulated account. Closes trades when price touches SL/TP."""
    name = "paper"

    def __init__(self, balance=10000.0):
        self.balance = balance
        self.open, self.closed = [], []

    def equity(self, prices=None):
        eq = self.balance
        for t in self.open:
            px = (prices or {}).get(t["pair"], t["entry"])
            eq += self._pnl(t, px)
        return eq

    @staticmethod
    def _pnl(t, px):
        d = (px - t["entry"]) * (1 if t["side"] == "BUY" else -1)
        return d * t["units"] * (1.0 / px if t["pair"].endswith("JPY") else 1.0)

    def place(self, sig, units):
        t = dict(id=uuid.uuid4().hex[:8], pair=sig.pair, side=sig.side, entry=sig.entry,
                 stop=sig.stop, target=sig.target, units=units, score=sig.score, time=sig.time)
        self.open.append(t)
        return t

    def update(self, prices):
        """prices: {pair: (high, low, last)} since last check."""
        for t in list(self.open):
            if t["pair"] not in prices:
                continue
            hi, lo, _ = prices[t["pair"]]
            hit = None
            if t["side"] == "BUY":
                hit = t["stop"] if lo <= t["stop"] else t["target"] if hi >= t["target"] else None
            else:
                hit = t["stop"] if hi >= t["stop"] else t["target"] if lo <= t["target"] else None
            if hit is not None:
                pnl = self._pnl(t, hit)
                self.balance += pnl
                self.open.remove(t)
                self.closed.append({**t, "exit": hit, "pnl": round(pnl, 2)})

    def state(self, prices=None):
        return {"broker": self.name, "balance": round(self.balance, 2),
                "equity": round(self.equity(prices), 2), "open": self.open, "closed": self.closed[-50:]}


class OandaBroker:
    """Real orders (practice or live account). Only constructed when cfg.live_enabled
    or when the user explicitly picks a practice account."""
    name = "oanda"

    def __init__(self, cfg):
        self.cfg = cfg
        self.base = HOSTS[cfg.oanda_env]
        self.h = {"Authorization": f"Bearer {cfg.oanda_key}"}
        self.acct = cfg.oanda_account

    def _get(self, path):
        r = requests.get(f"{self.base}/v3/accounts/{self.acct}{path}", headers=self.h, timeout=15)
        r.raise_for_status()
        return r.json()

    def equity(self, prices=None):
        return float(self._get("/summary")["account"]["NAV"])

    def place(self, sig, units):
        prec = 3 if sig.pair.endswith("JPY") else 2 if sig.pair.startswith("XAU") else 5
        body = {"order": {
            "type": "MARKET", "instrument": sig.pair,
            "units": str(units if sig.side == "BUY" else -units),
            "timeInForce": "FOK", "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": f"{sig.stop:.{prec}f}"},
            "takeProfitOnFill": {"price": f"{sig.target:.{prec}f}"}}}
        r = requests.post(f"{self.base}/v3/accounts/{self.acct}/orders", headers=self.h,
                          json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def update(self, prices):  # SL/TP are enforced server-side by the broker
        pass

    def state(self, prices=None):
        trades = self._get("/openTrades")["trades"]
        return {"broker": self.name, "env": self.cfg.oanda_env, "equity": self.equity(),
                "open": [{"id": t["id"], "pair": t["instrument"], "units": t["currentUnits"],
                          "entry": float(t["price"]), "pnl": float(t["unrealizedPL"])} for t in trades],
                "closed": []}
