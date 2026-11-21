# Forex AI Signals

An AI-assisted market analyst. It scans forex pairs, gives you **BUY/SELL signals with entry, stop and
target**, explains them, and keeps an honest **track record** of how every past signal turned out.
It never places trades. You decide and trade yourself.

## Quick start
See `RUN_ON_PC.md` for step-by-step setup (Windows friendly).
```bash
cd trading-bot
pip install -r requirements.txt
cp .env.example .env     # then edit .env (keys are loaded automatically)
python run.py            # dashboard: http://127.0.0.1:8000
python -m pytest         # tests
```
Without keys it runs on **synthetic demo data** (clearly flagged).

## How it works
| Part | File | What it does |
|---|---|---|
| Data | `bot/data.py` | Candles for entry + higher timeframe: Twelve Data (free, no broker), OANDA, or synthetic demo |
| Signals | `bot/signals.py` | Confluence scoring: trend factors (EMA stack, ADX/DI, MACD, pullbacks) vs range factors (Bollinger+RSI, stochastic) picked by regime, candle patterns, higher-timeframe filter, ATR-based stop/target (1:2) |
| AI analyst | `bot/ai.py` | Pluggable provider (Claude, OpenAI, Gemini, Ollama). Gives TAKE/SKIP/WATCH, key risk and invalidation for each signal. Optional |
| Track record | `bot/tracker.py` | Logs every signal and later grades it win/loss (stop wins ties). The real test of whether to trust the bot |
| Backtest | `bot/backtest.py` | Replays the rules on history with spread, next-bar fills, no lookahead, plus walk-forward folds |
| App | `bot/api.py`, `web/index.html`, `android/` | FastAPI server, web dashboard, Android app with push notifications |

The server checks all pairs every 15 minutes, even when no app is open. New signals get AI commentary
automatically and trigger a notification on your phone.

## Using it well
1. Run **backtests with walk-forward** on each pair. Distrust an edge that shows in only one fold.
2. Let the **track record** build for a few weeks. Don't trade the signals until 30+ closed signals show a result you'd accept.
3. Always use the stop loss it gives, and risk a small fixed % per trade.

## Android app
`android/` is a native Kotlin app: live signals, AI analysis, backtests, track record, notifications.
Get the APK from the GitHub Actions run (artifact `forex-ai-bot-debug-apk`). In the app: Settings -> server
URL (https) + API token. See `RUN_ON_PC.md` for the free HTTPS tunnel.

## Honest limits
No system predicts the market. Most retail forex traders lose money. The AI gives a second opinion, not
foresight. Not financial advice.
