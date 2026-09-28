# BELUGACORD 2.5 — api/calls.py
# Групповые звонки (WebRTC сигналинг через WS)
import secrets
from fastapi import APIRouter, HTTPException

from api._shared import get_pool, get_current_user, is_premium, manager

router = APIRouter()

# ============================================================
# CREATE ROOM
# ============================================================
@router.post("/calls/group/create")
async def calls_group_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if not is_premium(user): raise HTTPException(403, "Только для премиума")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE call_rooms SET closed_at=NOW()
            WHERE owner_id=$1 AND closed_at IS NULL""", user["id"])
        code = secrets.token_urlsafe(6)[:10]
        r = await conn.fetchrow("""INSERT INTO call_rooms(owner_id,room_code)
            VALUES($1,$2) RETURNING *""", user["id"], code)
        await conn.execute("INSERT INTO call_participants(room_id,user_id) VALUES($1,$2)",
            r["id"], user["id"])
    return {"room_id": r["id"], "room_code": code}

# ============================================================
# JOIN ROOM
# ============================================================
@router.post("/calls/group/join")
async def calls_group_join(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if not is_premium(user): raise HTTPException(403, "Только для премиума")
    code = (data.get("room_code") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM call_rooms WHERE room_code=$1 AND closed_at IS NULL", code)
        if not r: raise HTTPException(404, "Нет комнаты")
        cnt = await conn.fetchval("SELECT COUNT(*) FROM call_participants WHERE room_id=$1", r["id"])
        if cnt >= 30: raise HTTPException(400, "Комната полна")
        try:
            await conn.execute("INSERT INTO call_participants(room_id,user_id) VALUES($1,$2)",
                r["id"], user["id"])
        except: pass
        parts = await conn.fetch("""SELECT u.id,u.username,u.avatar FROM users u
            JOIN call_participants cp ON cp.user_id=u.id WHERE cp.room_id=$1""", r["id"])
    return {"room_id": r["id"], "room_code": code, "participants": [dict(p) for p in parts]}

# ============================================================
# LEAVE ROOM
# ============================================================
@router.post("/calls/group/leave")
async def calls_group_leave(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    code = (data.get("room_code") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT id FROM call_rooms WHERE room_code=$1 AND closed_at IS NULL", code)
        if not r: return {"ok": True}
        await conn.execute("DELETE FROM call_participants WHERE room_id=$1 AND user_id=$2",
            r["id"], user["id"])
        cnt = await conn.fetchval("SELECT COUNT(*) FROM call_participants WHERE room_id=$1", r["id"])
        if cnt == 0:
            await conn.execute("UPDATE call_rooms SET closed_at=NOW() WHERE id=$1", r["id"])
    return {"ok": True}

# ============================================================
# STATE (список участников)
# ============================================================
@router.get("/calls/group/state")
async def calls_group_state(room_code: str, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM call_rooms WHERE room_code=$1 AND closed_at IS NULL", room_code)
        if not r: raise HTTPException(404, "Нет")
        parts = await conn.fetch("""SELECT u.id,u.username,u.avatar FROM users u
            JOIN call_participants cp ON cp.user_id=u.id WHERE cp.room_id=$1""", r["id"])
    return {"room_id": r["id"], "owner_id": r["owner_id"],
            "participants": [dict(p) for p in parts]}