"""Claude-powered second opinion. Never executes anything: it explains and can veto."""
import json
from .indicators import add_all

SYSTEM = """You are a disciplined senior forex trader and risk manager. You get a rule-based
signal plus indicator readings. Be concise and honest: say when evidence is weak, name the
biggest risk to the trade, and never promise profit. Respond ONLY with JSON:
{"verdict":"TAKE|SKIP|WATCH","confidence":0-100,"summary":"2-3 sentences",
 "key_risk":"one sentence","invalidation":"price/condition that kills the idea"}"""


def snapshot(df):
    d = add_all(df).iloc[-1]
    keys = ["close", "ema20", "ema50", "ema200", "rsi", "macd_hist", "adx", "atr", "stoch_k"]
    return {k: round(float(d[k]), 5) for k in keys}


def analyze(cfg, sig, df, question=None):
    if not cfg.anthropic_key:
        return {"verdict": "N/A", "confidence": 0, "summary":
                "Set ANTHROPIC_API_KEY to enable AI analysis.", "key_risk": "", "invalidation": ""}
    import anthropic
    client = anthropic.Anthropic(api_key=cfg.anthropic_key)
    ctx = {"signal": sig.to_dict(), "indicators": snapshot(df),
           "recent_closes": [round(float(v), 5) for v in df["close"].tail(20)]}
    prompt = json.dumps(ctx) + (f"\nUser question: {question}" if question else "")
    msg = client.messages.create(model=cfg.claude_model, max_tokens=600, system=SYSTEM,
                                 messages=[{"role": "user", "content": prompt}])
    text = msg.content[0].text.strip()
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:
        return {"verdict": "WATCH", "confidence": 0, "summary": text, "key_risk": "", "invalidation": ""}
