"""Confluence signal engine.

Each factor votes +/- a weight. The bot is regime-aware: in a trend (ADX high) it
favours trend-following factors, in a range it favours mean reversion. A higher-
timeframe trend filter vetoes counter-trend trades. SL/TP are ATR-based.
"""
from dataclasses import dataclass, asdict, field
import pandas as pd
from .indicators import add_all


@dataclass
class Signal:
    pair: str
    side: str            # BUY | SELL | NONE
    score: float
    entry: float
    stop: float
    target: float
    atr: float
    regime: str
    reasons: list = field(default_factory=list)
    time: str = ""

    @property
    def rr(self):
        r = abs(self.entry - self.stop)
        return round(abs(self.target - self.entry) / r, 2) if r else 0.0

    def to_dict(self):
        d = asdict(self)
        d["rr"] = self.rr
        return d


def htf_bias(df_htf) -> int:
    """+1 / -1 / 0 trend direction from a higher-timeframe frame."""
    if df_htf is None or len(df_htf) < 60:
        return 0
    x = add_all(df_htf).iloc[-1]
    if x.close > x.ema50 > x.ema200 or (x.close > x.ema50 and x.ema20 > x.ema50 and pd.isna(x.ema200)):
        return 1
    if x.close < x.ema50 < x.ema200 or (x.close < x.ema50 and x.ema20 < x.ema50 and pd.isna(x.ema200)):
        return -1
    return 0


def score_row(df, i, bias=0):
    """Score bar i of an indicator-enriched frame. Returns (score, regime, reasons)."""
    x, p = df.iloc[i], df.iloc[i - 1]
    trending = x.adx >= 22
    regime = "trend" if trending else "range"
    s, why = 0.0, []

    def add(v, msg):
        nonlocal s
        s += v
        why.append(f"{'+' if v > 0 else ''}{v:g} {msg}")

    if trending:
        if x.ema20 > x.ema50 > x.ema200:
            add(1.5, "EMA stack bullish (20>50>200)")
        elif x.ema20 < x.ema50 < x.ema200:
            add(-1.5, "EMA stack bearish (20<50<200)")
        if x.pdi > x.mdi:
            add(0.5, f"+DI over -DI, ADX {x.adx:.0f}")
        else:
            add(-0.5, f"-DI over +DI, ADX {x.adx:.0f}")
        if p.macd_hist <= 0 < x.macd_hist:
            add(1.0, "MACD histogram turned positive")
        elif p.macd_hist >= 0 > x.macd_hist:
            add(-1.0, "MACD histogram turned negative")
        # pullback entries inside a trend
        if x.ema20 > x.ema50 and x.low <= x.ema20 and x.close > x.ema20:
            add(1.0, "bullish pullback bounce off EMA20")
        if x.ema20 < x.ema50 and x.high >= x.ema20 and x.close < x.ema20:
            add(-1.0, "bearish pullback rejection at EMA20")
    else:
        if x.close <= x.bb_lo and x.rsi < 35:
            add(1.5, f"oversold at lower Bollinger (RSI {x.rsi:.0f})")
        elif x.close >= x.bb_hi and x.rsi > 65:
            add(-1.5, f"overbought at upper Bollinger (RSI {x.rsi:.0f})")
        if p.stoch_k <= p.stoch_d and x.stoch_k > x.stoch_d and x.stoch_k < 30:
            add(1.0, "stochastic bullish cross in oversold zone")
        elif p.stoch_k >= p.stoch_d and x.stoch_k < x.stoch_d and x.stoch_k > 70:
            add(-1.0, "stochastic bearish cross in overbought zone")

    # candle confirmation (engulfing)
    if x.close > x.open and p.close < p.open and x.close >= p.open and x.open <= p.close:
        add(0.5, "bullish engulfing candle")
    elif x.close < x.open and p.close > p.open and x.close <= p.open and x.open >= p.close:
        add(-0.5, "bearish engulfing candle")

    # higher timeframe filter
    if bias:
        if (bias > 0) == (s > 0):
            add(1.0 * bias, "aligned with higher-timeframe trend")
        elif s != 0:
            s *= 0.4
            why.append("x0.4 counter higher-timeframe trend")
    return s, regime, why


def build_signal(pair, df, df_htf=None, min_score=3.0, sl_atr=1.5, rr=2.0, i=None) -> Signal:
    d = add_all(df)
    i = len(d) - 1 if i is None else i
    bias = htf_bias(df_htf)
    s, regime, why = score_row(d, i, bias)
    x = d.iloc[i]
    side = "BUY" if s >= min_score else "SELL" if s <= -min_score else "NONE"
    entry, a = float(x.close), float(x.atr)
    if side == "BUY":
        stop, target = entry - sl_atr * a, entry + sl_atr * rr * a
    elif side == "SELL":
        stop, target = entry + sl_atr * a, entry - sl_atr * rr * a
    else:
        stop = target = entry
    return Signal(pair, side, round(s, 2), entry, stop, target, a, regime, why,
                  str(d.index[i]))
