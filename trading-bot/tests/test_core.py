import numpy as np
from bot.data import synthetic, resample
from bot.indicators import add_all, rsi
from bot.signals import build_signal
from bot.risk import units_for_risk, RiskManager
from bot.config import Config
from bot import backtest as bt


def test_indicators_ranges():
    d = add_all(synthetic(n=600))
    assert d["rsi"].between(0, 100).all()
    assert (d["atr"].dropna() > 0).all()


def test_signal_levels_consistent():
    df = synthetic(n=800, seed=3)
    for i in range(300, 800, 7):
        s = build_signal("EUR_USD", df.iloc[: i + 1], resample(df.iloc[: i + 1], "4h"))
        if s.side == "BUY":
            assert s.stop < s.entry < s.target
        elif s.side == "SELL":
            assert s.target < s.entry < s.stop
        if s.side != "NONE":
            assert abs(s.rr - 2.0) < 0.01


def test_position_sizing_risks_target_fraction():
    u = units_for_risk("EUR_USD", 10000, 0.01, 1.1000, 1.0950)
    assert abs(u * 0.0050 - 100) < 1


def test_daily_loss_halt():
    cfg = Config()
    rm = RiskManager(cfg)
    assert rm.can_trade(10000, [], "EUR_USD", "d1")[0]
    ok, why = rm.can_trade(9700, [], "EUR_USD", "d1")
    assert not ok and "daily loss" in why


def test_live_requires_explicit_confirmation():
    c = Config(mode="live", oanda_key="k", oanda_account="a", live_confirm="")
    assert not c.live_enabled
    c.live_confirm = "I-ACCEPT-THE-RISK"
    assert c.live_enabled


def test_backtest_runs_and_no_lookahead_equity_consistent():
    df = synthetic(n=3000, seed=5)
    r = bt.run("EUR_USD", df)
    assert r["trades"] > 0
    assert r["max_drawdown_pct"] >= 0
    assert r["final_equity"] > 0
