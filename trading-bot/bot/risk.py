"""Helpers used by the backtester to express results in realistic position sizes."""


def pip_size(pair: str) -> float:
    if pair.startswith("XAU"):
        return 0.1
    return 0.01 if pair.endswith("JPY") else 0.0001


def units_for_risk(pair, equity, risk_frac, entry, stop, quote_to_account=1.0) -> int:
    """Units such that hitting the stop loses ~risk_frac of equity."""
    dist = abs(entry - stop)
    if dist <= 0:
        return 0
    if pair.endswith("JPY"):
        quote_to_account = 1.0 / entry          # JPY -> USD
    return int((equity * risk_frac) / (dist * quote_to_account))
