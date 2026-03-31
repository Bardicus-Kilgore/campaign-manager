"""
app/router_pf2e.py — PF2E reference pages and API.
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from app import database as db

router    = APIRouter()
templates = Jinja2Templates(directory="templates")


# ── Pages ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    stats = db.get_stats()
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})


@router.get("/grimoire", response_class=HTMLResponse)
def grimoire(request: Request, tab: str = "spells"):
    conditions = db.get_all_conditions() if tab == "conditions" else []
    return templates.TemplateResponse("grimoire.html", {
        "request": request, "tab": tab, "conditions": conditions
    })


@router.get("/bestiary", response_class=HTMLResponse)
def bestiary(request: Request):
    return templates.TemplateResponse("bestiary.html", {"request": request})


@router.get("/chat", response_class=HTMLResponse)
def chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


# ── API ────────────────────────────────────────────────────────────────────────

@router.get("/api/spells")
def api_spells(
    q: str = "",
    level: Optional[str] = None,
    tradition: Optional[str] = None,
    type: Optional[str] = None,
):
    return db.search_spells(q=q, level=level, tradition=tradition, spell_type=type)


@router.get("/api/creatures")
def api_creatures(
    q: str = "",
    level: Optional[str] = None,
    type: Optional[str] = None,
):
    return db.search_creatures(q=q, level=level, creature_type=type)


@router.get("/api/feats")
def api_feats(
    q: str = "",
    level: Optional[str] = None,
    feat_class: Optional[str] = Query(default=None, alias="class"),
):
    return db.search_feats(q=q, level=level, feat_class=feat_class)


@router.get("/api/items")
def api_items(
    q: str = "",
    level: Optional[str] = None,
):
    return db.search_items(q=q, level=level)
