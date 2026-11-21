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


# provider -> (default base URL, default model) for OpenAI-compatible chat APIs.
# Model names change often: override with AI_MODEL if a default is retired.
OPENAI_COMPAT = {
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash"),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
}


def enabled(cfg) -> bool:
    return cfg.ai_enabled


def complete(cfg, system, prompt) -> str:
    """Send one prompt to the configured provider and return the text reply."""
    if cfg.ai_provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=cfg.ai_key)
        msg = client.messages.create(model=cfg.ai_model or "claude-sonnet-5-5", max_tokens=600,
                                     system=system, messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    if cfg.ai_provider in OPENAI_COMPAT:
        import requests
        base, model = OPENAI_COMPAT[cfg.ai_provider]
        r = requests.post((cfg.ai_base_url or base).rstrip("/") + "/chat/completions",
                          headers={"Authorization": f"Bearer {cfg.ai_key or 'none'}"}, timeout=60,
                          json={"model": cfg.ai_model or model, "max_tokens": 600, "temperature": 0.2,
                                "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": prompt}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise ValueError(f"Unknown AI_PROVIDER '{cfg.ai_provider}' (use anthropic, openai, gemini, ollama, none)")


def analyze(cfg, sig, df, question=None):
    if not enabled(cfg):
        return {"verdict": "N/A", "confidence": 0, "summary":
                "AI is off. Set AI_PROVIDER and AI_API_KEY (see .env.example) to enable it.",
                "key_risk": "", "invalidation": ""}
    ctx = {"signal": sig.to_dict(), "indicators": snapshot(df),
           "recent_closes": [round(float(v), 5) for v in df["close"].tail(20)]}
    prompt = json.dumps(ctx) + (f"\nUser question: {question}" if question else "")
    text = complete(cfg, SYSTEM, prompt).strip()
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:
        return {"verdict": "WATCH", "confidence": 0, "summary": text, "key_risk": "", "invalidation": ""}
