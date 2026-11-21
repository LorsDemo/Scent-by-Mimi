"""Event-driven backtester with realistic frictions.

- Signal computed on bar close, filled at NEXT bar open (no lookahead).
- Spread/slippage charged on entry. If SL and TP are both inside one bar, SL wins (pessimistic).
- Position size from risk-per-trade; compounding equity.
- HTF bias uses only completed higher-timeframe bars.
"""
import numpy as np
import pandas as pd
from .indicators import add_all, ema
from .signals import score_row
from .risk import pip_size, units_for_risk


def htf_bias_series(df, rule="4h"):
    h = df.resample(rule).agg({"close": "last"}).dropna()
    e50, e200 = ema(h["close"], 50), ema(h["close"], 200)
    b = pd.Series(0, index=h.index)
    b[(h["close"] > e50) & (e50 > e200)] = 1
    b[(h["close"] < e50) & (e50 < e200)] = -1
    # shift by one HTF bar: only completed bars are known
    return b.shift(1).reindex(df.index, method="ffill").fillna(0)


def run(pair, df, cfg_min_score=3.0, risk=0.005, balance=10000.0, spread_pips=1.0,
        sl_atr=1.5, rr=2.0, htf_rule="4h"):
    d = add_all(df)
    bias = htf_bias_series(df, htf_rule)
    pip, spread = pip_size(pair), spread_pips * pip_size(pair)
    eq, curve, trades, pos = balance, [], [], None

    for i in range(210, len(d) - 1):
        bar = d.iloc[i]
        if pos:  # manage open trade on this bar
            hit = None
            if pos["side"] == "BUY":
                if bar.low <= pos["stop"]: hit = pos["stop"]
                elif bar.high >= pos["target"]: hit = pos["target"]
            else:
                if bar.high >= pos["stop"]: hit = pos["stop"]
                elif bar.low <= pos["target"]: hit = pos["target"]
            if hit is not None:
                pnl_px = (hit - pos["entry"]) * (1 if pos["side"] == "BUY" else -1)
                qa = 1.0 / hit if pair.endswith("JPY") else 1.0
                pnl = pnl_px * pos["units"] * qa
                eq += pnl
                trades.append({**pos, "exit": hit, "pnl": pnl, "r": pnl / pos["risk_amt"],
                               "exit_time": d.index[i]})
                pos = None
        if not pos:
            s, regime, _ = score_row(d, i, int(bias.iloc[i]))
            side = "BUY" if s >= cfg_min_score else "SELL" if s <= -cfg_min_score else None
            if side:
                nxt = d.iloc[i + 1]
                a = bar.atr
                entry = nxt.open + (spread if side == "BUY" else -spread)
                stop = entry - sl_atr * a if side == "BUY" else entry + sl_atr * a
                tgt = entry + sl_atr * rr * a if side == "BUY" else entry - sl_atr * rr * a
                u = units_for_risk(pair, eq, risk, entry, stop)
                if u > 0:
                    pos = dict(pair=pair, side=side, entry=entry, stop=stop, target=tgt, units=u,
                               risk_amt=eq * risk, score=round(s, 2), regime=regime,
                               time=d.index[i + 1])
        curve.append(eq)
    return stats(trades, balance, curve)


def stats(trades, balance, curve):
    n = len(trades)
    if n == 0:
        return {"trades": 0, "note": "no trades", "equity_curve": curve}
    pnl = np.array([t["pnl"] for t in trades])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    c = np.array(curve)
    dd = ((np.maximum.accumulate(c) - c) / np.maximum.accumulate(c)).max()
    return {
        "trades": n,
        "win_rate": round(len(wins) / n * 100, 1),
        "profit_factor": round(wins.sum() / abs(losses.sum()), 2) if losses.sum() else float("inf"),
        "expectancy_R": round(float(np.mean([t["r"] for t in trades])), 3),
        "net_return_pct": round((c[-1] / balance - 1) * 100, 2),
        "max_drawdown_pct": round(dd * 100, 2),
        "final_equity": round(float(c[-1]), 2),
        "equity_curve": [round(float(v), 2) for v in c[:: max(1, len(c) // 300)]],
        "trade_list": [{k: (str(v) if k.endswith("time") else v) for k, v in t.items()}
                       for t in trades[-50:]],
    }


def walk_forward(pair, df, folds=4, **kw):
    """Out-of-sample sanity check: run on consecutive slices; a real edge should not
    exist in only one of them."""
    out, size = [], len(df) // folds
    for k in range(folds):
        part = df.iloc[k * size:(k + 1) * size]
        r = run(pair, part, **kw)
        r.pop("equity_curve", None); r.pop("trade_list", None)
        out.append(r)
    return out
