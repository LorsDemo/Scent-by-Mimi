"""Position sizing and portfolio guards. Capital preservation comes before signals."""


def pip_size(pair: str) -> float:
    if pair.startswith("XAU"):
        return 0.1
    return 0.01 if pair.endswith("JPY") else 0.0001


def units_for_risk(pair, equity, risk_frac, entry, stop, quote_to_account=1.0) -> int:
    """Units such that hitting the stop loses ~risk_frac of equity.

    quote_to_account: price of 1 quote-currency unit in account currency (1.0 for
    USD-quoted pairs on a USD account; approximate for USD/JPY etc.).
    """
    dist = abs(entry - stop)
    if dist <= 0:
        return 0
    if pair.endswith("JPY"):
        quote_to_account = 1.0 / entry          # JPY -> USD
    return int((equity * risk_frac) / (dist * quote_to_account))


class RiskManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.day = None
        self.day_start_equity = None

    def can_trade(self, equity, open_trades, pair, now_day):
        if self.day != now_day:
            self.day, self.day_start_equity = now_day, equity
        if len(open_trades) >= self.cfg.max_open:
            return False, "max open trades reached"
        if any(t["pair"] == pair for t in open_trades):
            return False, "already in this pair"
        if equity <= self.day_start_equity * (1 - self.cfg.max_daily_loss):
            return False, "daily loss limit hit - trading halted until tomorrow"
        return True, "ok"
