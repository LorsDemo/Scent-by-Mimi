import os
import sys
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    if host != "127.0.0.1" and not os.getenv("API_TOKEN"):
        sys.exit("Refusing to listen on a network interface without API_TOKEN set.")
    uvicorn.run("bot.api:app", host=host, port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
