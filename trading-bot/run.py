import sys
import uvicorn

if __name__ == "__main__":
    uvicorn.run("bot.api:app", host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
