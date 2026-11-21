import hmac
import os
import pathlib
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import Config
from .engine import Engine
from .data import synthetic
from . import backtest as bt

cfg = Config()
API_TOKEN = os.getenv("API_TOKEN", "")


def require_token(x_api_key: str = Header(default="")):
    """Shared-secret auth. If API_TOKEN is unset the API is open: only OK on localhost."""
    if API_TOKEN and not hmac.compare_digest(x_api_key, API_TOKEN):
        raise HTTPException(401, "invalid or missing X-API-Key")


app = FastAPI(title="Forex AI Trading Bot")
AUTH = [Depends(require_token)]
eng = Engine(cfg)
WEB = pathlib.Path(__file__).resolve().parent.parent / "web"


class Ask(BaseModel):
    pair: str
    question: str | None = None


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.on_event("startup")
def _startup():
    eng.start_watch()


@app.get("/api/status", dependencies=AUTH)
def status():
    return {"data_source": eng.data_source, "ai_enabled": cfg.ai_enabled, "pairs": cfg.pairs,
            "timeframe": cfg.timeframe, "min_score": cfg.min_score, "log": eng.log[-30:]}


@app.get("/api/signals", dependencies=AUTH)
def signals():
    return {"data_source": eng.data_source, "signals": eng.scan()}


@app.get("/api/record", dependencies=AUTH)
def record():
    """Track record: every signal given so far and how it turned out."""
    return {"summary": eng.tracker.summary(), "signals": eng.tracker.recent(50),
            "data_source": eng.data_source}


@app.post("/api/analyze", dependencies=AUTH)
def analyze(a: Ask):
    if a.pair not in cfg.pairs:
        raise HTTPException(400, "unknown pair")
    return eng.analyze(a.pair, with_ai=True, question=a.question)


@app.get("/api/backtest/{pair}", dependencies=AUTH)
def backtest(pair: str, walk: bool = False):
    if pair not in cfg.pairs:
        raise HTTPException(400, "unknown pair")
    df = eng.src.candles(pair, cfg.timeframe, 5000) if eng.src else synthetic(pair, 4000)
    kw = dict(cfg_min_score=cfg.min_score, risk=cfg.risk_per_trade, balance=cfg.start_balance)
    out = {"data_source": eng.data_source, "result": bt.run(pair, df, **kw)}
    if walk:
        out["walk_forward"] = bt.walk_forward(pair, df, **kw)
    return out
