# backend/main.py
import uvicorn
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from routers import file_router

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"

os.makedirs(DATA_DIR, exist_ok=True)

LISTEN_PORT = 9986

app.include_router(file_router.router, prefix="/api/file", tags=["file"])

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=LISTEN_PORT)
