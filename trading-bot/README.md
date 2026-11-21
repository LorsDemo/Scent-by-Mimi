# Forex AI Trading Bot

Signals, AI trade analysis, backtesting, paper trading and (optional) live execution on OANDA,
with a web dashboard.

## Quick start
```bash
cd trading-bot
pip install -r requirements.txt
cp .env.example .env && set -a && source .env && set +a   # fill in keys
python run.py            # open http://127.0.0.1:8000
pytest                   # run tests
```
Without keys it runs on **synthetic demo data** (clearly flagged in the UI; auto-trading is blocked).

## How it works
| Layer | File | What it does |
|---|---|---|
| Data | `bot/data.py` | OANDA candles (entry + higher timeframe) |
| Signals | `bot/signals.py` | Confluence scoring: trend (EMA stack, ADX/DI, MACD, pullbacks) vs range (Bollinger+RSI, stochastic) chosen by ADX regime, candle patterns, higher-timeframe filter, ATR stops, 1:2 R:R |
| Risk | `bot/risk.py` | % risk position sizing, max open trades, daily loss halt |
| Backtest | `bot/backtest.py` | Next-bar-open fills, spread cost, SL-first on ambiguous bars, no lookahead, walk-forward folds |
| AI | `bot/ai.py` | Claude gives a TAKE/SKIP/WATCH opinion, key risk and invalidation; can veto auto trades, never places orders |
| Execution | `bot/broker.py` | `PaperBroker` (default) and `OandaBroker` (server-side SL/TP) |
| App | `bot/api.py`, `web/index.html` | FastAPI + dashboard |

## Going live safely
1. Backtest each pair on real OANDA data, including walk-forward. Distrust any edge that appears in only one fold.
2. Run on an OANDA **practice** account (`OANDA_ENV=practice`) for weeks.
3. Live needs all of: `BOT_MODE=live`, `LIVE_TRADING_CONFIRM=I-ACCEPT-THE-RISK`, OANDA keys.
   Start with tiny risk (`RISK_PER_TRADE=0.0025`).

## Honest limits
No bot guarantees profit; most retail forex traders lose money. This tool enforces discipline
(sizing, stops, loss limits) and gives you evidence, but the rules here are a starting point
that you must validate on real data. Not financial advice.

## Android app
`android/` is a native Kotlin/Jetpack Compose app that remote-controls this server: live signals,
AI analysis, backtests, account/trades, auto-trade switch and push notifications for new signals.
Broker and AI keys stay on the server.

1. Run the server on an always-on machine with `HOST=0.0.0.0 API_TOKEN=<long random> python run.py`
   and put it behind HTTPS (e.g. a Cloudflare Tunnel or Tailscale Funnel / reverse proxy).
2. Get the APK: GitHub Actions workflow **Build Android APK** → artifact `forex-ai-bot-debug-apk`
   (or open `android/` in Android Studio and press Run).
3. In the app: Settings → server URL + API token → Save & connect.
