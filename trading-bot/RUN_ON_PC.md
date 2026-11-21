# Run the signals bot on your PC + connect the Android app

Needs Python 3.10+ (https://www.python.org/downloads/). Keep the PC awake while the bot runs.

## 1. Install and configure (once)
```
cd trading-bot
pip install -r requirements.txt
copy .env.example .env        (Mac/Linux: cp .env.example .env)
```
Open `.env` in a text editor and set:
- `API_TOKEN=` a long random string (e.g. 30+ random characters). The app needs the same value.
- `TWELVEDATA_API_KEY` from a free account at https://twelvedata.com (market data, no broker needed).
  OANDA is optional and only needed for real order execution.
- AI is optional. To enable it set `AI_PROVIDER` (`anthropic`, `openai`, `gemini`, `ollama` = free local, or `none`) and `AI_API_KEY`.

## 2. Start the server
```
python run.py
```
Open http://127.0.0.1:8000 in your browser to check the dashboard works.

## 3. Give your phone an HTTPS address (free tunnel)
Install `cloudflared` (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/), then in a second terminal:
```
cloudflared tunnel --url http://localhost:8000
```
It prints an address like `https://something-random.trycloudflare.com`. It changes each time you restart the tunnel.
The tunnel is reachable by anyone who has the address, so `API_TOKEN` must be set.

## 4. Connect the app
Settings tab -> Server URL = the https address, API token = your `API_TOKEN` -> Save & connect.
