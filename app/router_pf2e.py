"""
app/router_pf2e.py — PF2E reference pages and API.
"""
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from pydantic import BaseModel
from app import database as db
from engine.encounter import generate_encounter, DIFFICULTY_BUDGET, ENVIRONMENT_TAGS, get_options as encounter_options
from engine.loot import generate_loot, PROFILE_NAMES
from engine.dice import roll as dice_roll
from engine.hook import generate_hook, ARC_OPTIONS

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


@router.get("/encounter", response_class=HTMLResponse)
def encounter(request: Request):
    return templates.TemplateResponse("encounter.html", {"request": request})


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


# ── Encounter Generator ────────────────────────────────────────────────────────

class EncounterRequest(BaseModel):
    party_level: int = 1
    difficulty: str = "moderate"
    environment: str = "dungeon"
    terrain: Optional[str] = None
    encounter_type: str = "combat"
    preferred_types: Optional[list[str]] = None
    session_id: Optional[int] = None
    arc: str = "custom"
    locked_slots: Optional[dict] = None   # e.g. {"who": "a lich"}


@router.post("/api/encounter/generate")
def api_encounter_generate(req: EncounterRequest):
    # ── Recent types from session history ─────────────────────────────────────
    recent_types: list[str] = []
    if req.session_id:
        recent_types = db.get_recent_types(req.session_id, limit=5)

    # ── Generate hook (drives preferred_types + strategy if not overridden) ───
    hook_data = generate_hook(
        environment=req.environment,
        arc=req.arc or "custom",
        recent_types=recent_types,
        locked=req.locked_slots,
    )

    # Caller-specified preferred_types override the hook
    preferred_types = req.preferred_types or hook_data["preferred_types"] or None

    # Hook's strategy only applies when encounter_type is generic ("combat")
    # For boss/patrol/etc., encounter_type wins — hook just flavors the types
    hook_strategy = hook_data.get("strategy_hint") if req.encounter_type == "combat" else None

    con = db.get_conn()
    result = generate_encounter(
        db_con=con,
        party_level=max(1, min(20, req.party_level)),
        difficulty=req.difficulty,
        environment=req.environment,
        terrain=req.terrain,
        encounter_type=req.encounter_type,
        preferred_types=preferred_types,
        strategy_override=hook_strategy,
    )
    con.close()

    # ── Persist to session ─────────────────────────────────────────────────────
    if req.session_id:
        used_types = list({c.creature_type for c in result.creatures if c.creature_type})
        db.record_session_encounter(
            session_id=req.session_id,
            hook=hook_data["hook"],
            who=hook_data["who"],
            action=hook_data["action"],
            modifier=hook_data["modifier"],
            obj=hook_data["object"],
            creature_types=used_types,
            environment=req.environment,
            arc=req.arc or "custom",
            party_level=req.party_level,
        )

    return {
        "party_level":        result.party_level,
        "difficulty":         result.difficulty,
        "encounter_type":     result.encounter_type,
        "environment":        result.environment,
        "terrain":            result.terrain,
        "xp_budget":          result.xp_budget,
        "xp_used":            result.xp_used,
        "loot_profile_hint":  result.loot_profile_hint,
        "tactics":            result.tactics,
        "hook":               hook_data,
        "creatures": [
            {
                "name":     c.name,
                "level":    c.level,
                "type":     c.creature_type,
                "quantity": c.quantity,
                "xp_each":  c.xp_each,
                "xp_total": c.xp_total,
            }
            for c in result.creatures
        ],
        "roll_log": result.roll_log,
        "warnings": result.warnings,
    }


@router.get("/api/encounter/options")
def api_encounter_options():
    opts = encounter_options()
    opts["arcs"] = ARC_OPTIONS
    return opts


# ── Hook generator (standalone) ────────────────────────────────────────────────

class HookRequest(BaseModel):
    environment: str = "dungeon"
    arc: str = "custom"
    session_id: Optional[int] = None
    locked_slots: Optional[dict] = None


@router.post("/api/encounter/hook")
def api_hook_generate(req: HookRequest):
    recent_types = []
    if req.session_id:
        recent_types = db.get_recent_types(req.session_id, limit=5)
    return generate_hook(
        environment=req.environment,
        arc=req.arc,
        recent_types=recent_types,
        locked=req.locked_slots,
    )


# ── Encounter / Adventure browser ─────────────────────────────────────────────

@router.get("/api/encounters")
def api_encounters(
    q: str = "",
    adventure_id: Optional[str] = None,
    difficulty: Optional[str] = None,
    level: Optional[str] = None,
):
    return db.search_encounters(
        q=q,
        adventure_id=adventure_id or None,
        difficulty=difficulty or None,
        level=level,
    )


@router.get("/api/encounters/{enc_id}")
def api_encounter_detail(enc_id: int):
    result = db.get_encounter_by_id(enc_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Encounter not found")
    return result


@router.get("/api/adventures")
def api_adventures():
    return db.get_all_adventures()


# ── Loot Generator ─────────────────────────────────────────────────────────────

class LootRequest(BaseModel):
    party_level: int = 1
    profile: str = "standard"
    creature_types: Optional[list[str]] = None
    randomize: bool = True


@router.post("/api/loot/generate")
def api_loot_generate(req: LootRequest):
    result = generate_loot(
        party_level=max(1, min(20, req.party_level)),
        profile_key=req.profile,
        creature_types=req.creature_types,
        randomize=req.randomize,
    )
    return {
        "party_level":     result.party_level,
        "profile":         result.profile,
        "creature_types":  result.creature_types,
        "gold":            result.gold,
        "gold_note":       result.gold_note,
        "items": [
            {
                "name":        i.name,
                "type":        i.item_type,
                "rarity":      i.rarity,
                "level_range": i.level_range,
                "quantity":    i.quantity,
                "value_note":  i.value_note,
            }
            for i in result.items
        ],
        "roll_log": result.roll_log,
    }


@router.get("/api/loot/profiles")
def api_loot_profiles():
    return {"profiles": list(PROFILE_NAMES.keys())}


# ── Campaign sessions ──────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    name: str
    arc: str = "custom"


@router.get("/api/campaign-sessions")
def api_list_sessions():
    return db.get_campaign_sessions()


@router.post("/api/campaign-sessions")
def api_create_session(req: SessionCreate):
    return db.create_campaign_session(req.name, req.arc)


@router.delete("/api/campaign-sessions/{session_id}")
def api_delete_session(session_id: int):
    db.delete_campaign_session(session_id)
    return {"ok": True}


@router.get("/api/campaign-sessions/{session_id}/history")
def api_session_history(session_id: int, limit: int = 20):
    return db.get_session_history(session_id, limit)


# ── Dice roller (utility) ──────────────────────────────────────────────────────

@router.get("/api/roll")
def api_roll(notation: str = "1d20"):
    try:
        result = dice_roll(notation)
        return {
            "notation":    result.notation,
            "rolls":       result.rolls,
            "modifier":    result.modifier,
            "total":       result.total,
            "description": result.description,
        }
    except ValueError as e:
        return {"error": str(e)}
