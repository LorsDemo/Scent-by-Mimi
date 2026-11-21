import threading
import time
import numpy as np
import pandas as pd
import requests

HOSTS = {"practice": "https://api-fxpractice.oanda.com", "live": "https://api-fxtrade.oanda.com"}
HTF = {"M15": "H1", "H1": "H4", "H4": "D"}


class OandaData:
    def __init__(self, cfg):
        self.cfg = cfg
        self.base = HOSTS.get(cfg.oanda_env, HOSTS["practice"])
        self.h = {"Authorization": f"Bearer {cfg.oanda_key}"}

    def candles(self, pair, tf="H1", count=500) -> pd.DataFrame:
        r = requests.get(f"{self.base}/v3/instruments/{pair}/candles", headers=self.h, timeout=15,
                         params={"granularity": tf, "count": count, "price": "M"})
        r.raise_for_status()
        rows = [{"time": c["time"], "open": float(c["mid"]["o"]), "high": float(c["mid"]["h"]),
                 "low": float(c["mid"]["l"]), "close": float(c["mid"]["c"]), "volume": c["volume"]}
                for c in r.json()["candles"] if c["complete"]]
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"])
        return df.set_index("time")


class TwelveData:
    """Free-tier friendly forex candles (https://twelvedata.com). No broker account needed.

    Free plan allows ~8 requests/minute, so calls are throttled and cached.
    """
    URL = "https://api.twelvedata.com/time_series"
    TF = {"M15": "15min", "H1": "1h", "H4": "4h", "D": "1day"}
    TTL = {"M15": 240, "H1": 600, "H4": 1800, "D": 3600}   # seconds
    MIN_GAP = 7.6                                          # => <= 8 calls/min

    def __init__(self, cfg):
        self.key = cfg.twelve_key
        self._cache, self._last, self._lock = {}, 0.0, threading.Lock()

    def candles(self, pair, tf="H1", count=500) -> pd.DataFrame:
        k = (pair, tf, count)
        hit = self._cache.get(k)
        if hit and time.time() - hit[0] < self.TTL.get(tf, 600):
            return hit[1]
        with self._lock:
            wait = self.MIN_GAP - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            r = requests.get(self.URL, timeout=20, params={
                "symbol": pair.replace("_", "/"), "interval": self.TF[tf], "outputsize": count,
                "order": "ASC", "timezone": "UTC", "apikey": self.key})
        r.raise_for_status()
        j = r.json()
        if j.get("status") == "error" or "values" not in j:
            raise RuntimeError(f"Twelve Data: {j.get('message', 'unknown error')}")
        df = pd.DataFrame(j["values"])
        for c in ("open", "high", "low", "close"):
            df[c] = df[c].astype(float)
        df["volume"] = 0
        df["time"] = pd.to_datetime(df["datetime"], utc=True)
        df = df.set_index("time")[["open", "high", "low", "close", "volume"]].sort_index()
        self._cache[k] = (time.time(), df)
        return df


def make_source(cfg):
    """Pick the market-data source. Returns None => synthetic demo data."""
    p = cfg.data_provider
    if p == "oanda" or (p == "auto" and cfg.has_oanda):
        return OandaData(cfg)
    if p == "twelvedata" or (p == "auto" and cfg.twelve_key):
        return TwelveData(cfg)
    return None


def synthetic(pair="EUR_USD", n=3000, seed=1, tf_minutes=60) -> pd.DataFrame:
    """Regime-switching random walk. FOR TESTING/DEMO ONLY - not real market data."""
    rng = np.random.default_rng(seed)
    base = {"USD_JPY": 150.0, "XAU_USD": 2000.0}.get(pair, 1.1)
    vol = base * 0.0004
    drift, ret = 0.0, []
    for i in range(n):
        if i % 250 == 0:
            drift = rng.choice([-1, 0, 1]) * vol * 0.12
        ret.append(drift + rng.normal(0, vol))
    close = base + np.cumsum(ret)
    open_ = np.r_[base, close[:-1]]
    hi = np.maximum(open_, close) + np.abs(rng.normal(0, vol * 0.5, n))
    lo = np.minimum(open_, close) - np.abs(rng.normal(0, vol * 0.5, n))
    idx = pd.date_range("2025-01-01", periods=n, freq=f"{tf_minutes}min")
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close, "volume": 100}, index=idx)


def resample(df, rule="4h"):
    return df.resample(rule).agg({"open": "first", "high": "max", "low": "min",
                                  "close": "last", "volume": "sum"}).dropna()


def get_frames(cfg, pair, count=500, source=None):
    """Return (entry-timeframe frame, higher-timeframe frame)."""
    if source is not None:
        return source.candles(pair, cfg.timeframe, count), source.candles(pair, HTF[cfg.timeframe], count)
    df = synthetic(pair, count)
    return df, resample(df, "4h")
