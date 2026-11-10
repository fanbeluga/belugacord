import os, secrets, time, hashlib, json
from pathlib import Path
from typing import Optional
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

DB_URL = os.getenv("DATABASE_URL", "postgresql://belugacord_user:1VSALM1cow@localhost/belugacord_zjgh")
UP = Path("uploads"); UP.mkdir(exist_ok=True)

app = FastAPI()
pool: asyncpg.Pool = None
live: dict[int, set[WebSocket]] = {}
online_users: set[int] = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, pw_hash TEXT NOT NULL, token TEXT UNIQUE, becoins INT DEFAULT 0, role TEXT DEFAULT 'user', bio TEXT DEFAULT '', avatar TEXT, banner TEXT, online_status TEXT DEFAULT 'online', custom_status TEXT, banned BOOLEAN DEFAULT false, created_at BIGINT, public_key TEXT, font_choice TEXT, compact_mode BOOLEAN DEFAULT false, wallpaper TEXT);
CREATE TABLE IF NOT EXISTS friends(id SERIAL PRIMARY KEY, from_user INT REFERENCES users(id), to_user INT REFERENCES users(id), status TEXT DEFAULT 'pending', created_at BIGINT);
CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY, name TEXT, owner_id INT, invite_code TEXT UNIQUE, created_at BIGINT);
CREATE TABLE IF NOT EXISTS server_members(server_id INT, user_id INT, PRIMARY KEY(server_id, user_id));
CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY, server_id INT, name TEXT, type TEXT DEFAULT 'text');
CREATE TABLE IF NOT EXISTS channel_messages(id SERIAL PRIMARY KEY, channel_id INT, user_id INT, text TEXT, file_url TEXT, created_at BIGINT);
CREATE TABLE IF NOT EXISTS dm_messages(id SERIAL PRIMARY KEY, from_user INT, to_user INT, text TEXT, file_url TEXT, created_at BIGINT);
CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY, name TEXT, owner_id INT, created_at BIGINT);
CREATE TABLE IF NOT EXISTS group_members(group_id INT, user_id INT, PRIMARY KEY(group_id, user_id));
CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY, group_id INT, user_id INT, text TEXT, created_at BIGINT);
"""

def now(): return int(time.time())
def tok(): return secrets.token_hex(24)
def hsh(p): return hashlib.sha256(p.encode()).hexdigest()

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DB_URL)
    async with pool.acquire() as con:
        for s in SCHEMA.split(";"):
            if s.strip(): await con.execute(s)

@app.on_event("startup")
async def startup(): await init_db()

async def auth(authorization: str = Header(None), x_token: str = Header(None), token: str = None):
    t = x_token or token or (authorization.split(" ")[-1] if authorization else None)
    if not t: raise HTTPException(401, "Нужен вход")
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", t)
    if not u: raise HTTPException(401, "Сессия истекла")
    if u["banned"]: raise HTTPException(403, "Забанен")
    return u

def user_dict(u):
    return dict(id=u["id"], username=u["username"], name=u["name"], role=u["role"], becoins=u["becoins"], bio=u["bio"], avatar=u["avatar"], banner=u["banner"], online_status=u["online_status"], custom_status=u["custom_status"], public_key=u["public_key"], font_choice=u["font_choice"], compact_mode=u["compact_mode"], wallpaper=u["wallpaper"], messages_count=0)

# --- МОДЕЛИ ---
class AuthIn(BaseModel): username: str; password: str; email: Optional[str] = None
class MsgIn(BaseModel): channel_id: Optional[int] = None; text: str = ""; file_url: Optional[str] = None
class DMIn(BaseModel): to_user: int; text: str = ""; file_url: Optional[str] = None
class FriendIn(BaseModel): user_id: Optional[int] = None; username: Optional[str] = None
class FriendAccept(BaseModel): request_id: int
class ProfileIn(BaseModel): avatar: Optional[str] = None; banner: Optional[str] = None; bio: Optional[str] = None; nickname_color: Optional[str] = None; nickname_gradient: Optional[str] = None; font_choice: Optional[str] = None; compact_mode: Optional[bool] = None; wallpaper: Optional[str] = None; avatar_pos: Optional[str] = None; banner_pos: Optional[str] = None; fav_music: Optional[str] = None

# --- АВТОРИЗАЦИЯ ---
@app.post("/api/register")
async def register(b: AuthIn):
    u = b.username.strip().lower()
    if not (5 <= len(u) <= 32): raise HTTPException(400, "Юз от 5 символов")
    async with pool.acquire() as con:
        if await con.fetchval("SELECT 1 FROM users WHERE username=$1", u): raise HTTPException(400, "Ник занят")
        t = tok()
        uid = await con.fetchval("INSERT INTO users(username,name,pw_hash,token,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", u, u, hsh(b.password), t, now())
    return {"token": t, "user": user_dict(await pool.fetchrow("SELECT * FROM users WHERE id=$1", uid))}

@app.post("/api/login")
async def login(b: AuthIn):
    u = b.username.strip().lower()
    async with pool.acquire() as con:
        acc = await con.fetchrow("SELECT * FROM users WHERE username=$1", u)
        if not acc: raise HTTPException(403, "Аккаунт не найден")
        if acc["banned"]: raise HTTPException(403, "Забанен")
        if hsh(b.password) != acc["pw_hash"]: raise HTTPException(403, "Неверный пароль")
        t = tok()
        await con.execute("UPDATE users SET token=$1 WHERE id=$2", t, acc["id"])
    return {"token": t, "user": user_dict(await pool.fetchrow("SELECT * FROM users WHERE id=$1", acc["id"]))}

@app.get("/api/me")
async def me(u=Depends(auth)): return user_dict(u)

@app.get("/api/check_username")
async def check_username(username: str):
    async with pool.acquire() as con:
        taken = await con.fetchval("SELECT 1 FROM users WHERE username=$1", username.strip().lower())
    return {"available": not taken}

@app.post("/api/update_profile")
async def update_profile(b: ProfileIn, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("""UPDATE users SET avatar=COALESCE($1,avatar), banner=COALESCE($2,banner), bio=COALESCE($3,bio), font_choice=COALESCE($4,font_choice), compact_mode=COALESCE($5,compact_mode), wallpaper=COALESCE($6,wallpaper) WHERE id=$7""",
            b.avatar, b.banner, b.bio, b.font_choice, b.compact_mode, b.wallpaper, u["id"])
    return {"ok": True}

@app.post("/api/user/status")
async def set_status(online_status: str = Form("online"), custom_status: str = Form(""), u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET online_status=$1, custom_status=$2 WHERE id=$3", online_status, custom_status, u["id"])
    return {"ok": True}

# --- ПОИСК И ЮЗЕРЫ ---
@app.get("/api/users/search")
async def search_users(q: str, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, username, avatar, online_status FROM users WHERE username ILIKE $1 OR name ILIKE $1 LIMIT 20", f"%{q}%")
    return [dict(r, online=True) for r in rows]

@app.get("/api/user/{uid}")
async def get_user(uid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM users WHERE id=$1", uid)
    if not row: raise HTTPException(404)
    return user_dict(row)

# --- ДРУЗЬЯ ---
@app.get("/api/friends/list")
async def friends_list(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT f.id as request_id, f.status, u.id, u.username, u.avatar, u.online_status, u.custom_status, f.from_user, f.to_user
            FROM friends f JOIN users u ON u.id = CASE WHEN f.from_user=$1 THEN f.to_user ELSE f.from_user END
            WHERE (f.from_user=$1 OR f.to_user=$1) AND f.status != 'removed'
        """, u["id"])
    res = []
    for r in rows:
        d = dict(r)
        if d["status"] == "pending":
            d["status"] = "incoming" if d["to_user"] == u["id"] else "outgoing"
        d["online"] = True
        res.append(d)
    return res

@app.post("/api/friends/request_by_id")
async def friend_req(b: FriendIn, u=Depends(auth)):
    if b.user_id == u["id"]: raise HTTPException(400, "Себя нельзя")
    async with pool.acquire() as con:
        if await con.fetchval("SELECT 1 FROM friends WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", u["id"], b.user_id):
            raise HTTPException(400, "Уже есть заявка")
        await con.execute("INSERT INTO friends(from_user,to_user,created_at) VALUES($1,$2,$3)", u["id"], b.user_id, now())
    return {"ok": True}

@app.post("/api/friends/request")
async def friend_req_name(b: FriendIn, u=Depends(auth)):
    async with pool.acquire() as con:
        target = await con.fetchrow("SELECT id FROM users WHERE username=$1", b.username.strip().lower())
    if not target: raise HTTPException(404, "Юзер не найден")
    return await friend_req(FriendIn(user_id=target["id"]), u)

@app.post("/api/friends/accept")
async def friend_accept(b: FriendAccept, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE friends SET status='accepted' WHERE id=$1 AND to_user=$2", b.request_id, u["id"])
    return {"ok": True}

@app.post("/api/friends/decline")
async def friend_decline(b: FriendAccept, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM friends WHERE id=$1 AND to_user=$2", b.request_id, u["id"])
    return {"ok": True}

@app.post("/api/friends/remove")
async def friend_remove(b: FriendIn, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM friends WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", u["id"], b.user_id)
    return {"ok": True}

@app.get("/api/friends/count")
async def friends_count(u=Depends(auth)):
    async with pool.acquire() as con:
        n = await con.fetchval("SELECT count(*) FROM friends WHERE to_user=$1 AND status='pending'", u["id"])
    return {"count": n}

@app.get("/api/friends/check/{uid}")
async def friend_check(uid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT id, status, from_user, to_user FROM friends WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", u["id"], uid)
    if not row: return {"status": "none"}
    if row["status"] == "accepted": return {"status": "accepted"}
    return {"status": "incoming" if row["to_user"] == u["id"] else "outgoing", "request_id": row["id"]}

# --- ЛИЧНЫЕ СООБЩЕНИЯ (DM) ---
@app.get("/api/dm/{peer_id}/messages")
async def dm_messages(peer_id: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT m.*, u.username, u.avatar FROM dm_messages m JOIN users u ON u.id=m.from_user
            WHERE (m.from_user=$1 AND m.to_user=$2) OR (m.from_user=$2 AND m.to_user=$1) ORDER BY m.id
        """, u["id"], peer_id)
    return [dict(r) for r in rows]

@app.post("/api/dm/send")
async def dm_send(b: DMIn, u=Depends(auth)):
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO dm_messages(from_user,to_user,text,file_url,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", u["id"], b.to_user, b.text, b.file_url, now())
        msg = dict(await con.fetchrow("SELECT m.*, u.username, u.avatar FROM dm_messages m JOIN users u ON u.id=m.from_user WHERE m.id=$1", mid))
    await push([u["id"], b.to_user], {"type": "dm", **msg})
    return msg

# --- СЕРВЕРЫ И КАНАЛЫ ---
@app.get("/api/servers/list")
async def servers_list(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT s.* FROM servers s JOIN server_members m ON m.server_id=s.id WHERE m.user_id=$1", u["id"])
    return [dict(r) for r in rows]

@app.post("/api/servers/create")
async def server_create(name: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        invite = secrets.token_urlsafe(8)
        sid = await con.fetchval("INSERT INTO servers(name,owner_id,invite_code,created_at) VALUES($1,$2,$3,$4) RETURNING id", name, u["id"], invite, now())
        await con.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)", sid, u["id"])
        await con.execute("INSERT INTO channels(server_id,name) VALUES($1,'общий')", sid)
    return {"id": sid, "name": name}

@app.get("/api/servers/{sid}")
async def get_server(sid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM servers WHERE id=$1", sid)
    if not row: raise HTTPException(404)
    return dict(row)

@app.get("/api/servers/{sid}/channels")
async def server_channels(sid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM channels WHERE server_id=$1 ORDER BY id", sid)
    return [dict(r) for r in rows]

@app.get("/api/servers/{sid}/members")
async def server_members(sid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT u.id, u.username, u.avatar, u.role FROM users u JOIN server_members m ON m.user_id=u.id WHERE m.server_id=$1", sid)
    return [dict(r) for r in rows]

@app.get("/api/channels/{cid}/messages")
async def channel_msgs(cid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT m.*, u.username, u.avatar, u.role FROM channel_messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id", cid)
    return {"messages": [dict(r) for r in rows], "pinned": []}

@app.post("/api/messages/send")
async def msg_send(b: MsgIn, u=Depends(auth)):
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO channel_messages(channel_id,user_id,text,file_url,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", b.channel_id, u["id"], b.text, b.file_url, now())
    await push_channel(b.channel_id, {"type": "message", "id": mid, "channel_id": b.channel_id, "user_id": u["id"], "username": u["username"], "avatar": u["avatar"], "text": b.text, "file_url": b.file_url, "created_at": now()})
    return {"id": mid}

# --- ГРУППЫ ---
@app.get("/api/groups/list")
async def groups_list(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT g.* FROM groups g JOIN group_members m ON m.group_id=g.id WHERE m.user_id=$1", u["id"])
    return [dict(r) for r in rows]

@app.post("/api/groups/create")
async def group_create(name: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        gid = await con.fetchval("INSERT INTO groups(name,owner_id,created_at) VALUES($1,$2,$3) RETURNING id", name, u["id"], now())
        await con.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)", gid, u["id"])
    return {"id": gid, "name": name}

@app.get("/api/groups/{gid}")
async def get_group(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM groups WHERE id=$1", gid)
    if not row: raise HTTPException(404)
    return dict(row)

@app.get("/api/groups/{gid}/messages")
async def group_msgs(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT m.*, u.username, u.avatar FROM group_messages m JOIN users u ON u.id=m.user_id WHERE m.group_id=$1 ORDER BY m.id", gid)
    return [dict(r) for r in rows]

@app.post("/api/groups/{gid}/send")
async def group_send(gid: int, text: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO group_messages(group_id,user_id,text,created_at) VALUES($1,$2,$3,$4) RETURNING id", gid, u["id"], text, now())
    return {"id": mid}

# --- ЗАГЛУШКИ ДЛЯ ВСЕГО ОСТАЛЬНОГО (чтобы фронт не падал) ---
@app.get("/api/coins/balance") -> dict:
@app.get("/api/coins/leaders") -> list:
async def dummy_get(): return []
@app.post("/api/coins/transfer") -> dict:
async def dummy_post(): return {"ok": True}

@app.get("/api/nft/list") -> list:
@app.get("/api/nft/my") -> list:
@app.get("/api/nft_market/list") -> list:
async def dummy_list(): return []

@app.get("/api/cases/list") -> list:
async def dummy_cases(): return []

@app.get("/api/gifts/all") -> list:
@app.get("/api/gifts/list/{uid}") -> list:
async def dummy_gifts(): return []

@app.get("/api/stickers/list") -> list:
@app.get("/api/themes/list") -> list:
@app.get("/api/achievements/all") -> dict:
async def dummy_ach(): return {}

@app.get("/api/abuse/access") -> dict:
async def abuse_access(): return {"access": False}

@app.get("/api/games/tournament") -> dict:
async def games_tour(): return {"game": None}

@app.get("/api/games/top3") -> dict:
async def games_top3(): return {}

@app.get("/api/admin/stats") -> dict:
async def admin_stats(): return {"users": 0, "servers": 0, "messages": 0, "online": 0}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...), u=Depends(auth)):
    dest = UP / f"{int(time.time())}_{file.filename}"
    with open(dest, "wb") as f: f.write(await file.read())
    return {"url": f"/uploads/{dest.name}"}

@app.get("/uploads/{name}")
def get_upload(name: str):
    p = UP / name
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

# --- WEBSOCKET ---
async def push(uids, payload):
    for uid in set(uids):
        for ws in list(live.get(uid, [])):
            try: await ws.send_json(payload)
            except: live[uid].discard(ws)

async def push_channel(cid, payload):
    async with pool.acquire() as con:
        uids = [r["user_id"] for r in await con.fetch("SELECT user_id FROM server_members WHERE server_id=(SELECT server_id FROM channels WHERE id=$1)", cid)]
    await push(uids, payload)

@app.websocket("/ws")
async def ws(sock: WebSocket, token: str):
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", token)
    if not u: return await sock.close()
    await sock.accept()
    live.setdefault(u["id"], set()).add(sock)
    online_users.add(u["id"])
    try:
        while True:
            data = await sock.receive_json()
            t = data.get("type")
            if t == "message":
                cid = data["channel_id"]
                mid = await pool.fetchval("INSERT INTO channel_messages(channel_id,user_id,text,created_at) VALUES($1,$2,$3,$4) RETURNING id", cid, u["id"], data.get("text",""), now())
                await push_channel(cid, {"type": "message", "id": mid, "channel_id": cid, "user_id": u["id"], "username": u["username"], "avatar": u["avatar"], "text": data.get("text",""), "temp_id": data.get("temp_id"), "created_at": now()})
            elif t == "dm":
                to = data["to_user"]
                mid = await pool.fetchval("INSERT INTO dm_messages(from_user,to_user,text,created_at) VALUES($1,$2,$3,$4) RETURNING id", u["id"], to, data.get("text",""), now())
                await push([u["id"], to], {"type": "dm", "id": mid, "from_user": u["id"], "to_user": to, "username": u["username"], "avatar": u["avatar"], "text": data.get("text",""), "temp_id": data.get("temp_id"), "created_at": now()})
    except WebSocketDisconnect:
        live[u["id"]].discard(sock)
        online_users.discard(u["id"])

@app.get("/", response_class=HTMLResponse)
def index():
    return open("index.html", encoding="utf-8").read()