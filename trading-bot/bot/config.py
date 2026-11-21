import os
import pathlib
from dataclasses import dataclass, field


def _load_dotenv():
    """Load trading-bot/.env without extra dependencies (works on Windows too)."""
    f = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.split(" #")[0].strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def _f(name, default):
    return float(os.getenv(name, default))


@dataclass
class Config:
    oanda_key: str = os.getenv("OANDA_API_KEY", "")
    oanda_account: str = os.getenv("OANDA_ACCOUNT_ID", "")
    oanda_env: str = os.getenv("OANDA_ENV", "practice")
    # Market data: auto | oanda | twelvedata | synthetic   (auto = first one configured)
    data_provider: str = os.getenv("DATA_PROVIDER", "auto").lower()
    twelve_key: str = os.getenv("TWELVEDATA_API_KEY", "")
    # AI provider: anthropic | openai | gemini | ollama | none
    ai_provider: str = os.getenv("AI_PROVIDER", "anthropic").lower()
    ai_key: str = os.getenv("AI_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
    ai_model: str = os.getenv("AI_MODEL") or os.getenv("CLAUDE_MODEL", "")
    ai_base_url: str = os.getenv("AI_BASE_URL", "")
    pairs: list = field(default_factory=lambda: os.getenv(
        "PAIRS", "EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,XAU_USD").split(","))
    timeframe: str = os.getenv("TIMEFRAME", "H1")
    min_score: float = _f("MIN_SCORE", 3.0)
    risk_per_trade: float = _f("RISK_PER_TRADE", 0.005)
    start_balance: float = _f("START_BALANCE", 10000)

    @property
    def ai_enabled(self) -> bool:
        if self.ai_provider in ("none", ""):
            return False
        return self.ai_provider == "ollama" or bool(self.ai_key)

    @property
    def has_oanda(self) -> bool:
        return bool(self.oanda_key and self.oanda_account)
