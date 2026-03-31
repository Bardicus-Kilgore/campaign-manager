"""
server.py — Campaign Manager entry point
"""
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.router_pf2e import router as pf2e_router
from app.router_chat import router as chat_router, ws_router

app = FastAPI(title="Campaign Manager")

init_db()

app.include_router(pf2e_router)
app.include_router(chat_router)
app.include_router(ws_router)

import os as _os
_upload_dir = "/data/uploads" if _os.path.exists("/data") else "data/uploads"
app.mount("/uploads", StaticFiles(directory=_upload_dir), name="uploads")
app.mount("/static",  StaticFiles(directory="static"),       name="static")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=5000, reload=True)
