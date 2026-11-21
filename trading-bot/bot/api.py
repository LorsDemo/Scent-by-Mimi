import pathlib
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import Config
from .engine import Engine
from .data import get_frames, synthetic
from . import backtest as bt

app = FastAPI(title="Forex AI Trading Bot")
cfg = Config()
eng = Engine(cfg)
WEB = pathlib.Path(__file__).resolve().parent.parent / "web"


class Ask(BaseModel):
    pair: str
    question: str | None = None


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/status")
def status():
    return {"mode": "LIVE" if cfg.live_enabled else "PAPER", "data_source": eng.data_source,
            "ai_enabled": bool(cfg.anthropic_key), "auto": eng.auto, "pairs": cfg.pairs,
            "timeframe": cfg.timeframe, "min_score": cfg.min_score,
            "account": eng.broker.state(), "log": eng.log[-30:]}


@app.get("/api/signals")
def signals():
    return {"data_source": eng.data_source, "signals": eng.scan()}


@app.post("/api/analyze")
def analyze(a: Ask):
    if a.pair not in cfg.pairs:
        raise HTTPException(400, "unknown pair")
    return eng.analyze(a.pair, with_ai=True, question=a.question)


@app.get("/api/backtest/{pair}")
def backtest(pair: str, walk: bool = False):
    if pair not in cfg.pairs:
        raise HTTPException(400, "unknown pair")
    df = eng.src.candles(pair, cfg.timeframe, 5000) if eng.src else synthetic(pair, 4000)
    kw = dict(cfg_min_score=cfg.min_score, risk=cfg.risk_per_trade, balance=cfg.start_balance)
    out = {"data_source": eng.data_source, "result": bt.run(pair, df, **kw)}
    if walk:
        out["walk_forward"] = bt.walk_forward(pair, df, **kw)
    return out


@app.post("/api/auto/{action}")
def auto(action: str):
    if action == "start":
        if not eng.src:
            raise HTTPException(400, "Auto-trading needs real market data: set OANDA_API_KEY/OANDA_ACCOUNT_ID.")
        eng.start()
    elif action == "stop":
        eng.stop()
    else:
        raise HTTPException(404)
    return {"auto": eng.auto}
