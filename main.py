import os
from fastapi import FastAPI

app = FastAPI()
STAND = os.getenv("STAND", "unknown")

@app.get("/")
def root():
    return {"stand": STAND, "status": "ok"}