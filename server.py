import os
import json
import time
import secrets
import hashlib
from typing import Optional

import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2026")
ADMIN_USERNAME = "_fan_beluga_"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

pool: Optional[asyncpg.Pool] = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL, avatar TEXT, banner TEXT,
            is_admin BOOLEAN DEFAULT FALSE, is_banned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers (
            id SERIAL PRIMARY KEY, name VARCHAR(64) NOT NULL,
            owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            invite_code VARCHAR(16) UNIQUE, created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members (
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (server_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY, server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            name VARCHAR(64) NOT NULL, type VARCHAR(16) DEFAULT 'text',
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY, channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, file_url TEXT, created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(16) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, file_url TEXT, created_at TIMESTAMP DEFAULT NOW())""")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        await init_db()
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute("UPDATE users SET is_admin = TRUE WHERE username = $1", ADMIN_USERNAME)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False

def make_token(user_id: int, username: str) -> str:
    data = f"{user_id}:{username}:{int(time.time())}"
    sig = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()[:32]
    return f"{data}:{sig}"

def parse_token(token: str):
    try:
        parts = token.split(":")
        if len(parts) != 4: return None
        user_id, username, ts, sig = parts
        data = f"{user_id}:{username}:{ts}"
        expected = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()[:32]
        if sig != expected: return None
        return int(user_id), username
    except Exception:
        return None

async def get_current_user(token: str):
    parsed = parse_token(token)
    if not parsed: return None
    user_id, username = parsed
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, username, avatar, banner, is_admin, is_banned FROM users WHERE id = $1", user_id)
        return dict(row) if row else None

@app.get("/api/check_username")
async def check_username(username: str):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
    return {"available": row is None}

@app.post("/api/register")
async def register(data: dict):
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if len(username) < 2 or len(username) > 32:
        raise HTTPException(400, "Ник от 2 до 32 символов")
    if len(password) < 4:
        raise HTTPException(400, "Пароль минимум 4 символа")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
        if existing: raise HTTPException(400, "Ник занят")
        is_admin = (username == ADMIN_USERNAME)
        row = await conn.fetchrow(
            "INSERT INTO users (username, password_hash, is_admin) VALUES ($1, $2, $3) RETURNING id, username, avatar, banner, is_admin",
            username, hash_password(password), is_admin)
    token = make_token(row["id"], row["username"])
    return {"token": token, "user": dict(row)}

@app.post("/api/login")
async def login(data: dict):
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, username, password_hash, avatar, banner, is_admin, is_banned FROM users WHERE username = $1", username)
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(400, "Неверный ник или пароль")
    if row["is_banned"]:
        raise HTTPException(403, "Ты забанен")
    token = make_token(row["id"], row["username"])
    return {"token": token, "user": {"id": row["id"], "username": row["username"], "avatar": row["avatar"], "banner": row["banner"], "is_admin": row["is_admin"]}}

@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return user

@app.post("/api/update_profile")
async def update_profile(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    avatar = data.get("avatar"); banner = data.get("banner")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET avatar = COALESCE($1, avatar), banner = COALESCE($2, banner) WHERE id = $3", avatar, banner, user["id"])
    return {"ok": True}

@app.post("/api/servers/create")
async def create_server(data: dict):
    token = data.get("token"); name = (data.get("name") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not name: raise HTTPException(400, "Введи название")
    invite = secrets.token_urlsafe(8)
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("INSERT INTO servers (name, owner_id, invite_code) VALUES ($1, $2, $3) RETURNING id, name, invite_code", name, user["id"], invite)
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1, $2)", row["id"], user["id"])
        await conn.execute("INSERT INTO channels (server_id, name) VALUES ($1, $2)", row["id"], "общий")
    return dict(row)

@app.get("/api/servers/list")
async def list_servers(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id, s.name, s.invite_code FROM servers s
            JOIN server_members sm ON sm.server_id = s.id WHERE sm.user_id = $1""", user["id"])
    return [dict(r) for r in rows]

@app.post("/api/servers/join")
async def join_server(data: dict):
    token = data.get("token"); invite = (data.get("invite") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name FROM servers WHERE invite_code = $1", invite)
        if not row: raise HTTPException(404, "Приглашение не найдено")
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", row["id"], user["id"])
    return dict(row)

@app.get("/api/servers/{server_id}/channels")
async def get_channels(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, type FROM channels WHERE server_id = $1 ORDER BY id", server_id)
    return [dict(r) for r in rows]

@app.post("/api/channels/create")
async def create_channel(data: dict):
    token = data.get("token"); server_id = data.get("server_id")
    name = (data.get("name") or "").strip(); ctype = data.get("type", "text")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not name: raise HTTPException(400, "Введи название")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("INSERT INTO channels (server_id, name, type) VALUES ($1, $2, $3) RETURNING id, name, type", server_id, name, ctype)
    return dict(row)

@app.get("/api/channels/{channel_id}/messages")
async def get_messages(channel_id: int, token: str, limit: int = 50):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT m.id, m.text, m.file_url, m.created_at, u.username, u.avatar
            FROM messages m JOIN users u ON u.id = m.user_id WHERE m.channel_id = $1
            ORDER BY m.id DESC LIMIT $2""", channel_id, limit)
    return [dict(r) for r in reversed(rows)]

@app.post("/api/upload")
async def upload_file(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    ext = os.path.splitext(file.filename)[1]
    fname = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(await file.read())
    return {"url": f"/uploads/{fname}"}

@app.post("/api/friends/request")
async def friend_request(data: dict):
    token = data.get("token"); to_username = (data.get("username") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", to_username)
        if not target: raise HTTPException(404, "Пользователь не найден")
        if target["id"] == user["id"]: raise HTTPException(400, "Это ты")
        existing = await conn.fetchrow("SELECT id FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], target["id"])
        if existing: raise HTTPException(400, "Запрос уже есть")
        await conn.execute("INSERT INTO friendships (from_user, to_user, status) VALUES ($1, $2, 'pending')", user["id"], target["id"])
    # Пуш другу
    await manager.send_to(target["id"], {"type": "friend_request", "from_id": user["id"], "from_name": user["username"], "from_avatar": user["avatar"]})
    return {"ok": True}

@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, f.status, f.from_user, f.to_user
            FROM friendships f JOIN users u ON (u.id = f.from_user OR u.id = f.to_user)
            WHERE (f.from_user = $1 OR f.to_user = $1) AND u.id != $1""", user["id"])
    return [dict(r) for r in rows]

@app.post("/api/friends/accept")
async def friend_accept(data: dict):
    token = data.get("token"); friend_id = data.get("friend_id")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE friendships SET status = 'accepted' WHERE from_user = $1 AND to_user = $2", friend_id, user["id"])
    await manager.send_to(friend_id, {"type": "friend_accepted", "by": user["username"]})
    return {"ok": True}

@app.get("/api/dm/{user_id}/messages")
async def get_dm(user_id: int, token: str):
    me_user = await get_current_user(token)
    if not me_user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT d.id, d.text, d.file_url, d.created_at, u.username, u.avatar
            FROM dms d JOIN users u ON u.id = d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id ASC LIMIT 100""", me_user["id"], user_id)
    return [dict(r) for r in rows]

class Manager:
    def __init__(self): self.active = {}
    async def connect(self, uid, ws):
        await ws.accept(); self.active[uid] = ws
    def disconnect(self, uid): self.active.pop(uid, None)
    async def send_to(self, uid, data):
        ws = self.active.get(uid)
        if ws:
            try: await ws.send_json(data)
            except: pass
    async def broadcast(self, data):
        for ws in list(self.active.values()):
            try: await ws.send_json(data)
            except: pass

manager = Manager()

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    user = await get_current_user(token)
    if not user or user.get("is_banned"):
        await websocket.close(); return
    await manager.connect(user["id"], websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try: data = json.loads(raw)
            except: continue
            t = data.get("type")
            if t == "message":
                channel_id = data.get("channel_id"); text = data.get("text", ""); file_url = data.get("file_url")
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO messages (channel_id, user_id, text, file_url) VALUES ($1,$2,$3,$4) RETURNING id, created_at", channel_id, user["id"], text, file_url)
                await manager.broadcast({"type":"message","id":row["id"],"channel_id":channel_id,"user_id":user["id"],
                    "username":user["username"],"avatar":user["avatar"],"text":text,"file_url":file_url,
                    "created_at":row["created_at"].isoformat()})
            elif t == "dm":
                to_user = data.get("to_user"); text = data.get("text",""); file_url = data.get("file_url")
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO dms (from_user, to_user, text, file_url) VALUES ($1,$2,$3,$4) RETURNING id, created_at", user["id"], to_user, text, file_url)
                payload = {"type":"dm","id":row["id"],"from_user":user["id"],"to_user":to_user,
                    "username":user["username"],"avatar":user["avatar"],"text":text,"file_url":file_url,
                    "created_at":row["created_at"].isoformat()}
                await manager.send_to(to_user, payload)
                await manager.send_to(user["id"], payload)
            elif t in ("call","offer","answer","ice","call_decline","call_end"):
                target = data.get("target")
                if target:
                    await manager.send_to(target, {**data, "from": user["id"], "from_name": user["username"], "from_avatar": user["avatar"]})
            elif t == "admin_ban":
                if user.get("is_admin"):
                    target = data.get("target")
                    p = await get_pool()
                    async with p.acquire() as conn:
                        await conn.execute("UPDATE users SET is_banned = TRUE WHERE id = $1", target)
                    await manager.send_to(target, {"type": "banned"})
    except WebSocketDisconnect:
        manager.disconnect(user["id"])

@app.get("/")
async def index():
    return HTMLResponse(open("index.html", encoding="utf-8").read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))