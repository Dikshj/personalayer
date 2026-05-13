# backend/main.py
import uvicorn

from interfaces.http_api import app
from scheduler import create_scheduler


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7823)
