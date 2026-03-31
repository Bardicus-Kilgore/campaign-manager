"""
app/router_chat.py — Real-time chat, polls, notes, references, calendar.
"""
import io
import csv
import json
import os
import random
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Header
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.database import get_conn

ADMIN_PASS  = os.environ.get("ADMIN_PASSWORD", "bard1cus")
_data_root  = "/data" if os.path.exists("/data") else "data"
UPLOAD_DIR  = f"{_data_root}/uploads"
REFS_DIR    = f"{_data_root}/references"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REFS_DIR,   exist_ok=True)

router    = APIRouter()
ws_router = APIRouter()

# username -> list of WebSockets (supports multiple devices)
connections: dict[str, list[WebSocket]] = {}


def _is_admin(token: str) -> bool:
    return token == ADMIN_PASS


def _rand_filename(original: str) -> str:
    ext  = os.path.splitext(original)[1].lower()
    rand = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=14))
    return f"{rand}{ext}"


def _poll_state(poll_id: int, viewer: str) -> dict:
    conn    = get_conn()
    row     = conn.execute("SELECT question, options FROM polls WHERE id = ?", (poll_id,)).fetchone()
    if not row:
        conn.close(); return {}
    options   = json.loads(row["options"])
    vote_rows = conn.execute(
        "SELECT option_idx, COUNT(*) as cnt FROM poll_votes WHERE poll_id = ? GROUP BY option_idx",
        (poll_id,)
    ).fetchall()
    votes  = [0] * len(options)
    for vr in vote_rows:
        votes[vr["option_idx"]] = vr["cnt"]
    my_row = conn.execute(
        "SELECT option_idx FROM poll_votes WHERE poll_id = ? AND voter = ?",
        (poll_id, viewer)
    ).fetchone()
    conn.close()
    return {
        "poll_id":  poll_id,
        "question": row["question"],
        "options":  options,
        "votes":    votes,
        "total":    sum(votes),
        "my_vote":  my_row["option_idx"] if my_row else None,
    }


# ── WebSocket ──────────────────────────────────────────────────────────────────

@ws_router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    username = None

    try:
        raw  = await websocket.receive_text()
        data = json.loads(raw)

        if data.get("type") != "auth" or not data.get("username", "").strip():
            await websocket.close()
            return

        username = data["username"].strip()[:30]
        is_new   = username not in connections
        connections.setdefault(username, []).append(websocket)

        if is_new:
            for u, wss in list(connections.items()):
                if u != username:
                    for ws in wss:
                        await ws.send_json({"type": "user_joined", "username": username})

        await websocket.send_json({"type": "ready", "online": list(connections.keys())})

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            # ── Room message ──
            if msg["type"] == "room_message":
                room_id  = msg.get("room_id", "pf2e")
                msg_type = msg.get("msgType", "text")
                content  = msg["content"]

                conn = get_conn()
                cur  = conn.execute(
                    "INSERT INTO room_messages (room_id, username, type, content) VALUES (?, ?, ?, ?)",
                    (room_id, username, msg_type, content)
                )
                conn.commit()
                ts = conn.execute("SELECT timestamp FROM room_messages WHERE id = ?", (cur.lastrowid,)).fetchone()["timestamp"]
                conn.close()

                payload = {
                    "type": "room_message", "room_id": room_id,
                    "from": username, "msgType": msg_type,
                    "content": content, "timestamp": ts,
                }
                for wss in list(connections.values()):
                    for ws in wss:
                        await ws.send_json(payload)

            # ── Create poll ──
            elif msg["type"] == "create_poll":
                question = msg.get("question", "").strip()
                options  = msg.get("options", [])
                room_id  = msg.get("room_id", "pf2e")
                if not question or len(options) < 2:
                    continue

                conn  = get_conn()
                cur   = conn.execute("INSERT INTO polls (question, options) VALUES (?, ?)", (question, json.dumps(options)))
                conn.commit()
                poll_id = cur.lastrowid

                poll_content = json.dumps({"poll_id": poll_id, "question": question, "options": options})
                cur2 = conn.execute(
                    "INSERT INTO room_messages (room_id, username, type, content) VALUES (?, ?, 'poll', ?)",
                    (room_id, username, poll_content)
                )
                conn.commit()
                ts = conn.execute("SELECT timestamp FROM room_messages WHERE id = ?", (cur2.lastrowid,)).fetchone()["timestamp"]
                conn.close()

                payload = {
                    "type": "room_message", "room_id": room_id,
                    "from": username, "msgType": "poll",
                    "content": poll_content, "timestamp": ts,
                }
                for wss in list(connections.values()):
                    for ws in wss:
                        await ws.send_json(payload)

            # ── Vote ──
            elif msg["type"] == "vote":
                poll_id    = msg.get("poll_id")
                option_idx = msg.get("option")
                conn = get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO poll_votes (poll_id, voter, option_idx) VALUES (?, ?, ?)",
                    (poll_id, username, option_idx)
                )
                conn.commit()
                conn.close()

                for u, wss in list(connections.items()):
                    state = _poll_state(poll_id, u)
                    for ws in wss:
                        await ws.send_json({"type": "poll_update", **state})

    except WebSocketDisconnect:
        pass
    finally:
        if username and username in connections:
            connections[username] = [ws for ws in connections[username] if ws is not websocket]
            if not connections[username]:
                del connections[username]
                for wss in list(connections.values()):
                    for ws in wss:
                        await ws.send_json({"type": "user_left", "username": username})


# ── Rooms ──────────────────────────────────────────────────────────────────────

@router.get("/api/rooms")
def api_rooms():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM rooms").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/rooms/{room_id}/history")
def api_room_history(room_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM room_messages WHERE room_id = ? ORDER BY timestamp ASC LIMIT 300",
        (room_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Image upload ───────────────────────────────────────────────────────────────

@router.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="File type not allowed")
    filename = _rand_filename(file.filename)
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(await file.read())
    return {"url": f"/uploads/{filename}"}


# ── Admin ──────────────────────────────────────────────────────────────────────

class AdminLogin(BaseModel):
    password: str


@router.post("/api/admin/login")
def api_admin_login(body: AdminLogin):
    if body.password != ADMIN_PASS:
        raise HTTPException(status_code=403, detail="Wrong password")
    return {"token": ADMIN_PASS}


# ── Notes ──────────────────────────────────────────────────────────────────────

class NoteIn(BaseModel):
    date:    str
    title:   str
    content: str
    author:  str


class NoteUpdate(BaseModel):
    date:    str
    title:   str
    content: str


@router.get("/api/notes")
def api_notes_list():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM session_notes ORDER BY date DESC, id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/notes")
def api_notes_save(note: NoteIn):
    conn = get_conn()
    conn.execute(
        "INSERT INTO session_notes (date, title, content, author) VALUES (?, ?, ?, ?)",
        (note.date, note.title, note.content, note.author)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.put("/api/notes/{note_id}")
def api_notes_update(note_id: int, note: NoteUpdate, x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_conn()
    conn.execute(
        "UPDATE session_notes SET date=?, title=?, content=? WHERE id=?",
        (note.date, note.title, note.content, note_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/api/notes/{note_id}")
def api_notes_delete(note_id: int, x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_conn()
    conn.execute("DELETE FROM session_notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/notes/export/csv")
def api_notes_export():
    conn = get_conn()
    rows = conn.execute(
        "SELECT date, title, content, author, created FROM session_notes ORDER BY date ASC"
    ).fetchall()
    conn.close()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Title", "Notes", "Author", "Saved At"])
    for r in rows:
        writer.writerow([r["date"], r["title"], r["content"], r["author"], r["created"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=session_notes.csv"}
    )


# ── References ─────────────────────────────────────────────────────────────────

@router.get("/api/references")
def api_refs_list():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ref_files ORDER BY created DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/references")
async def api_refs_upload(file: UploadFile = File(...), x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Admin only")
    allowed = {".xlsx", ".md", ".pdf", ".txt"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="File type not allowed")
    filename = _rand_filename(file.filename)
    with open(os.path.join(REFS_DIR, filename), "wb") as f:
        f.write(await file.read())
    conn = get_conn()
    conn.execute("INSERT INTO ref_files (filename, original_name) VALUES (?, ?)", (filename, file.filename))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/api/references/{ref_id}")
def api_refs_delete(ref_id: int, x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_conn()
    row  = conn.execute("SELECT filename FROM ref_files WHERE id = ?", (ref_id,)).fetchone()
    if row:
        try: os.remove(os.path.join(REFS_DIR, row["filename"]))
        except FileNotFoundError: pass
        conn.execute("DELETE FROM ref_files WHERE id = ?", (ref_id,))
        conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/references/{ref_id}/download")
def api_refs_download(ref_id: int):
    conn = get_conn()
    row  = conn.execute("SELECT filename, original_name FROM ref_files WHERE id = ?", (ref_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404)
    return FileResponse(os.path.join(REFS_DIR, row["filename"]), filename=row["original_name"])


@router.get("/api/references/{ref_id}/content")
def api_refs_content(ref_id: int):
    conn = get_conn()
    row  = conn.execute("SELECT filename, original_name FROM ref_files WHERE id = ?", (ref_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404)
    with open(os.path.join(REFS_DIR, row["filename"]), "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return {"content": content, "name": row["original_name"]}


# ── Events / Calendar ──────────────────────────────────────────────────────────

class EventIn(BaseModel):
    date:        str
    time:        str = ""
    title:       str
    description: str = ""
    author:      str


@router.get("/api/events")
def api_events_list(month: str = ""):
    conn = get_conn()
    if month:
        rows = conn.execute(
            "SELECT * FROM events WHERE date LIKE ? ORDER BY date ASC, time ASC",
            (f"{month}%",)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM events ORDER BY date ASC, time ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/events/upcoming")
def api_events_upcoming():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM events WHERE date >= date('now') ORDER BY date ASC, time ASC LIMIT 5"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/events")
async def api_events_create(event: EventIn):
    conn = get_conn()
    conn.execute(
        "INSERT INTO events (date, time, title, description, author) VALUES (?, ?, ?, ?, ?)",
        (event.date, event.time, event.title, event.description, event.author)
    )
    conn.commit()
    conn.close()

    payload = {
        "type": "event_created", "title": event.title,
        "date": event.date, "time": event.time, "author": event.author,
    }
    for wss in list(connections.values()):
        for ws in wss:
            await ws.send_json(payload)

    return {"ok": True}


@router.post("/api/events/{event_id}/attend")
def api_events_attend(event_id: int, username: str):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO event_attendees (event_id, username) VALUES (?, ?)", (event_id, username))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/api/events/{event_id}/attend")
def api_events_unattend(event_id: int, username: str):
    conn = get_conn()
    conn.execute("DELETE FROM event_attendees WHERE event_id = ? AND username = ?", (event_id, username))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/events/{event_id}/attendees")
def api_events_attendees(event_id: int):
    conn = get_conn()
    rows = conn.execute("SELECT username FROM event_attendees WHERE event_id = ?", (event_id,)).fetchall()
    conn.close()
    return [r["username"] for r in rows]


@router.delete("/api/events/{event_id}")
def api_events_delete(event_id: int, x_admin_token: Optional[str] = Header(None)):
    if not _is_admin(x_admin_token or ""):
        raise HTTPException(status_code=403, detail="Admin only")
    conn = get_conn()
    conn.execute("DELETE FROM event_attendees WHERE event_id = ?", (event_id,))
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Polls ──────────────────────────────────────────────────────────────────────

@router.get("/api/polls/{poll_id}")
def api_poll(poll_id: int, viewer: str = ""):
    return _poll_state(poll_id, viewer)
