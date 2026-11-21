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
