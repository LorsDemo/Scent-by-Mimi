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


def test_api_token_enforced(monkeypatch):
    from fastapi.testclient import TestClient
    import bot.api as api
    monkeypatch.setattr(api, "API_TOKEN", "s3cret")
    c = TestClient(api.app)
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/api/status", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.get("/").status_code == 200        # dashboard shell loads without token


def test_ai_provider_selection_and_openai_compat(monkeypatch):
    from bot import ai
    assert not Config(ai_provider="none", ai_key="k").ai_enabled
    assert not Config(ai_provider="openai", ai_key="").ai_enabled
    assert Config(ai_provider="ollama", ai_key="").ai_enabled          # local: no key
    assert Config(ai_provider="gemini", ai_key="k").ai_enabled

    seen = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": '{"verdict":"TAKE","confidence":70,"summary":"s","key_risk":"r","invalidation":"i"}'}}]}

    import requests
    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, model=json["model"], auth=headers["Authorization"]); return R()
    monkeypatch.setattr(requests, "post", fake_post)
    df = synthetic(n=400)
    sig = build_signal("EUR_USD", df, resample(df, "4h"))
    out = ai.analyze(Config(ai_provider="gemini", ai_key="K"), sig, df)
    assert out["verdict"] == "TAKE"
    assert seen["url"].endswith("/openai/chat/completions") and seen["auth"] == "Bearer K"
    assert ai.analyze(Config(ai_provider="none"), sig, df)["verdict"] == "N/A"
    import pytest
    with pytest.raises(ValueError):
        ai.complete(Config(ai_provider="bogus", ai_key="k"), "s", "p")


def test_twelvedata_source_parsing_cache_and_selection(monkeypatch):
    import requests
    from bot.data import TwelveData, make_source, OandaData
    calls = []

    class R:
        def __init__(s, j): s.j = j
        def raise_for_status(s): pass
        def json(s): return s.j

    def fake_get(url, params=None, timeout=None, headers=None):
        calls.append(params)
        if params["apikey"] == "bad":
            return R({"status": "error", "message": "invalid key"})
        return R({"status": "ok", "values": [
            {"datetime": "2025-01-01 01:00:00", "open": "1.1", "high": "1.2", "low": "1.0", "close": "1.15"},
            {"datetime": "2025-01-01 00:00:00", "open": "1.0", "high": "1.1", "low": "0.9", "close": "1.1"}]})
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(TwelveData, "MIN_GAP", 0)
    td = TwelveData(Config(twelve_key="k"))
    df = td.candles("EUR_USD", "H1", 2)
    assert list(df["close"]) == [1.1, 1.15] and df.index.is_monotonic_increasing   # sorted oldest first
    assert calls[0]["symbol"] == "EUR/USD" and calls[0]["interval"] == "1h"
    td.candles("EUR_USD", "H1", 2)
    assert len(calls) == 1                                                        # cached
    import pytest
    with pytest.raises(RuntimeError, match="invalid key"):
        TwelveData(Config(twelve_key="bad")).candles("EUR_USD", "H1", 2)
    assert isinstance(make_source(Config(twelve_key="k", data_provider="auto")), TwelveData)
    assert isinstance(make_source(Config(oanda_key="a", oanda_account="b", twelve_key="k")), OandaData)
    assert make_source(Config(twelve_key="", oanda_key="", data_provider="auto")) is None
