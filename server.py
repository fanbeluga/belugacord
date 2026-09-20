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
ADMIN_PASSWORD = "12344321"

LIMITS = {
    None:     {"file": 10 * 1024 * 1024,  "msg": 2000,  "servers": 10,  "channels": 20},
    "premium":{"file": 50 * 1024 * 1024,  "msg": 4000,  "servers": 50,  "channels": 100},
    "pro":    {"file": 200 * 1024 * 1024, "msg": 10000, "servers": 999, "channels": 999},
}

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
            avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%',
            email VARCHAR(128), reset_code VARCHAR(16),
            is_admin BOOLEAN DEFAULT FALSE, is_moderator BOOLEAN DEFAULT FALSE,
            premium_tier VARCHAR(8), is_banned BOOLEAN DEFAULT FALSE,
            mute_until TIMESTAMP, nickname_color VARCHAR(32), nickname_gradient VARCHAR(128),
            custom_status VARCHAR(128), avatar_frame VARCHAR(32),
            msg_sound TEXT, call_sound TEXT, hidden_online BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW())""")
        for col, typ in [
            ("is_admin", "BOOLEAN DEFAULT FALSE"),
            ("is_moderator", "BOOLEAN DEFAULT FALSE"),
            ("premium_tier", "VARCHAR(8)"),
            ("is_banned", "BOOLEAN DEFAULT FALSE"),
            ("mute_until", "TIMESTAMP"),
            ("email", "VARCHAR(128)"),
            ("reset_code", "VARCHAR(16)"),
            ("avatar_pos", "TEXT DEFAULT '50% 50%'"),
            ("banner_pos", "TEXT DEFAULT '50% 50%'"),
            ("nickname_color", "VARCHAR(32)"),
            ("nickname_gradient", "VARCHAR(128)"),
            ("custom_status", "VARCHAR(128)"),
            ("avatar_frame", "VARCHAR(32)"),
            ("msg_sound", "TEXT"),
            ("call_sound", "TEXT"),
            ("hidden_online", "BOOLEAN DEFAULT FALSE"),
        ]:
            try:
                await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
            except Exception:
                pass
        try:
            await conn.execute("UPDATE users SET premium_tier = 'premium' WHERE is_premium = TRUE AND premium_tier IS NULL")
        except Exception:
            pass
        await conn.execute("UPDATE users SET is_admin = TRUE WHERE username = $1", ADMIN_USERNAME)
        # Сервера — добавляем аватарку, баннер, описание
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers (
            id SERIAL PRIMARY KEY, name VARCHAR(64) NOT NULL,
            owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            invite_code VARCHAR(16) UNIQUE, avatar TEXT, banner TEXT, description TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")
        for col, typ in [("avatar","TEXT"),("banner","TEXT"),("description","TEXT")]:
            try:
                await conn.execute(f"ALTER TABLE servers ADD COLUMN IF NOT EXISTS {col} {typ}")
            except Exception:
                pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members (
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            joined_at TIMESTAMP DEFAULT NOW(),
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
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
            id SERIAL PRIMARY KEY, admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(32), target_id INTEGER, details TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try:
            await init_db()
        except Exception as e:
            print(f"DB init error: {e}")

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
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None

async def log_admin(admin_id, action, target_id, details=""):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES ($1,$2,$3,$4)",
                           admin_id, action, target_id, details)

def tier_of(user):
    return user.get("premium_tier")

def user_public(row):
    # определяем роль
    role = "user"
    if row.get("is_admin"): role = "admin"
    elif row.get("is_moderator"): role = "moderator"
    return {
        "id": row["id"], "username": row["username"], "avatar": row["avatar"],
        "banner": row["banner"], "avatar_pos": row["avatar_pos"], "banner_pos": row["banner_pos"],
        "is_admin": row["is_admin"], "is_moderator": row["is_moderator"],
        "premium_tier": row.get("premium_tier"),
        "nickname_color": row.get("nickname_color"),
        "nickname_gradient": row.get("nickname_gradient"),
        "custom_status": row.get("custom_status"),
        "avatar_frame": row.get("avatar_frame"),
        "msg_sound": row.get("msg_sound"),
        "call_sound": row.get("call_sound"),
        "hidden_online": row.get("hidden_online"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "role": role
    }

# ===== API =====
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
    email = (data.get("email") or "").strip() or None
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
            "INSERT INTO users (username, password_hash, email, is_admin) VALUES ($1,$2,$3,$4) RETURNING *",
            username, hash_password(password), email, is_admin)
    token = make_token(row["id"], row["username"])
    return {"token": token, "user": user_public(row)}

@app.post("/api/login")
async def login(data: dict):
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(400, "Неверный ник или пароль")
    if row["is_banned"]:
        raise HTTPException(403, "Ты забанен")
    token = make_token(row["id"], row["username"])
    return {"token": token, "user": user_public(row)}

@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return user_public(user)

@app.post("/api/update_profile")
async def update_profile(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    tier = tier_of(user)
    premium = tier in ("premium", "pro")
    pro = tier == "pro"
    avatar = data.get("avatar"); banner = data.get("banner")
    avatar_pos = data.get("avatar_pos"); banner_pos = data.get("banner_pos")
    nickname_color = data.get("nickname_color") if premium else None
    nickname_gradient = data.get("nickname_gradient") if pro else None
    custom_status = data.get("custom_status") if premium else None
    avatar_frame = data.get("avatar_frame") if pro else None
    msg_sound = data.get("msg_sound") if premium else None
    call_sound = data.get("call_sound") if premium else None
    hidden_online = data.get("hidden_online") if pro else None
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET
            avatar = COALESCE($1, avatar), banner = COALESCE($2, banner),
            avatar_pos = COALESCE($3, avatar_pos), banner_pos = COALESCE($4, banner_pos),
            nickname_color = COALESCE($5, nickname_color),
            nickname_gradient = COALESCE($6, nickname_gradient),
            custom_status = COALESCE($7, custom_status),
            avatar_frame = COALESCE($8, avatar_frame),
            msg_sound = COALESCE($9, msg_sound),
            call_sound = COALESCE($10, call_sound),
            hidden_online = COALESCE($11, hidden_online)
            WHERE id = $12""", avatar, banner, avatar_pos, banner_pos,
            nickname_color, nickname_gradient, custom_status, avatar_frame,
            msg_sound, call_sound, hidden_online, user["id"])
    return {"ok": True}

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT id, username, avatar, banner, avatar_pos, banner_pos,
            is_admin, is_moderator, premium_tier, nickname_color, nickname_gradient,
            custom_status, avatar_frame, hidden_online, created_at
            FROM users WHERE id = $1""", user_id)
    if not row: raise HTTPException(404, "Не найден")
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    if d.get("is_admin"): d["role"] = "admin"
    elif d.get("is_moderator"): d["role"] = "moderator"
    else: d["role"] = "user"
    return d

# ===== СЕРВЕРА =====
@app.post("/api/servers/create")
async def create_server(data: dict):
    token = data.get("token"); name = (data.get("name") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not name: raise HTTPException(400, "Введи название")
    limits = LIMITS.get(tier_of(user), LIMITS[None])
    p = await get_pool()
    async with p.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM servers WHERE owner_id = $1", user["id"])
        if count >= limits["servers"]:
            raise HTTPException(400, f"Лимит серверов: {limits['servers']}")
        invite = secrets.token_urlsafe(8)
        row = await conn.fetchrow("INSERT INTO servers (name, owner_id, invite_code) VALUES ($1,$2,$3) RETURNING id, name, invite_code",
                                  name, user["id"], invite)
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2)", row["id"], user["id"])
        await conn.execute("INSERT INTO channels (server_id, name) VALUES ($1,$2)", row["id"], "общий")
    return dict(row)

@app.get("/api/servers/list")
async def list_servers(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id, s.name, s.invite_code, s.avatar, s.banner, s.description,
            s.owner_id FROM servers s
            JOIN server_members sm ON sm.server_id = s.id WHERE sm.user_id = $1""", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/servers/{server_id}")
async def get_server(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT s.id, s.name, s.invite_code, s.avatar, s.banner, s.description,
            s.owner_id, u.username AS owner_name FROM servers s
            JOIN users u ON u.id = s.owner_id WHERE s.id = $1""", server_id)
    if not row: raise HTTPException(404, "Не найден")
    return dict(row)

@app.post("/api/servers/update")
async def update_server(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    server_id = data.get("server_id")
    p = await get_pool()
    async with p.acquire() as conn:
        server = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", server_id)
        if not server: raise HTTPException(404, "Сервер не найден")
        if server["owner_id"] != user["id"]:
            raise HTTPException(403, "Только владелец")
        name = data.get("name"); avatar = data.get("avatar")
        banner = data.get("banner"); description = data.get("description")
        await conn.execute("""UPDATE servers SET
            name = COALESCE($1, name), avatar = COALESCE($2, avatar),
            banner = COALESCE($3, banner), description = COALESCE($4, description)
            WHERE id = $5""", name, avatar, banner, description, server_id)
    return {"ok": True}

@app.post("/api/servers/delete")
async def delete_server(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    server_id = data.get("server_id")
    p = await get_pool()
    async with p.acquire() as conn:
        server = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", server_id)
        if not server: raise HTTPException(404, "Сервер не найден")
        if server["owner_id"] != user["id"] and not user.get("is_admin"):
            raise HTTPException(403, "Только владелец")
        await conn.execute("DELETE FROM servers WHERE id = $1", server_id)
    return {"ok": True}

@app.post("/api/servers/leave")
async def leave_server(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    server_id = data.get("server_id")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM server_members WHERE server_id = $1 AND user_id = $2", server_id, user["id"])
    return {"ok": True}

@app.get("/api/servers/{server_id}/members")
async def get_members(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, u.premium_tier, u.is_admin, u.is_moderator,
            sm.joined_at FROM server_members sm
            JOIN users u ON u.id = sm.user_id WHERE sm.server_id = $1
            ORDER BY sm.joined_at""", server_id)
    result = []
    for r in rows:
        d = dict(r)
        d["joined_at"] = d["joined_at"].isoformat() if d.get("joined_at") else None
        if d.get("is_admin"): d["role"] = "admin"
        elif d.get("is_moderator"): d["role"] = "moderator"
        else: d["role"] = "user"
        result.append(d)
    return result

@app.post("/api/servers/join")
async def join_server(data: dict):
    token = data.get("token"); invite = (data.get("invite") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name FROM servers WHERE invite_code = $1", invite)
        if not row: raise HTTPException(404, "Приглашение не найдено")
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", row["id"], user["id"])
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
    limits = LIMITS.get(tier_of(user), LIMITS[None])
    p = await get_pool()
    async with p.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM channels WHERE server_id = $1", server_id)
        if count >= limits["channels"]:
            raise HTTPException(400, f"Лимит каналов: {limits['channels']}")
        row = await conn.fetchrow("INSERT INTO channels (server_id, name, type) VALUES ($1,$2,$3) RETURNING id, name, type",
                                  server_id, name, ctype)
    return dict(row)

@app.post("/api/channels/delete")
async def delete_channel(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    channel_id = data.get("channel_id")
    p = await get_pool()
    async with p.acquire() as conn:
        ch = await conn.fetchrow("SELECT s.owner_id FROM channels c JOIN servers s ON s.id = c.server_id WHERE c.id = $1", channel_id)
        if not ch: raise HTTPException(404, "Канал не найден")
        if ch["owner_id"] != user["id"] and not user.get("is_admin"):
            raise HTTPException(403, "Только владелец")
        await conn.execute("DELETE FROM channels WHERE id = $1", channel_id)
    return {"ok": True}

@app.get("/api/channels/{channel_id}/messages")
async def get_messages(channel_id: int, token: str, limit: int = 50):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT m.id, m.text, m.file_url, m.created_at, u.id AS user_id,
            u.username, u.avatar, u.avatar_pos, u.premium_tier, u.nickname_color,
            u.nickname_gradient, u.avatar_frame
            FROM messages m JOIN users u ON u.id = m.user_id WHERE m.channel_id = $1
            ORDER BY m.id DESC LIMIT $2""", channel_id, limit)
    return [dict(r) for r in reversed(rows)]

@app.post("/api/upload")
async def upload_file(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    contents = await file.read()
    limits = LIMITS.get(tier_of(user), LIMITS[None])
    if len(contents) > limits["file"]:
        raise HTTPException(400, f"Файл больше {limits['file'] // 1024 // 1024} МБ")
    ext = os.path.splitext(file.filename)[1]
    fname = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(contents)
    return {"url": f"/uploads/{fname}"}

# ===== ДРУЗЬЯ =====
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
        await conn.execute("INSERT INTO friendships (from_user, to_user, status) VALUES ($1,$2,'pending')", user["id"], target["id"])
    await manager.send_to(target["id"], {"type":"friend_request","from_id":user["id"],"from_name":user["username"],"from_avatar":user["avatar"]})
    return {"ok": True}

@app.post("/api/friends/request_by_id")
async def friend_request_by_id(data: dict):
    token = data.get("token"); target_id = data.get("user_id")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if target_id == user["id"]: raise HTTPException(400, "Это ты")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], target_id)
        if existing: raise HTTPException(400, "Запрос уже есть")
        await conn.execute("INSERT INTO friendships (from_user, to_user, status) VALUES ($1,$2,'pending')", user["id"], target_id)
    await manager.send_to(target_id, {"type":"friend_request","from_id":user["id"],"from_name":user["username"],"from_avatar":user["avatar"]})
    return {"ok": True}

@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, u.premium_tier, u.nickname_color,
            u.nickname_gradient, f.status, f.from_user, f.to_user
            FROM friendships f JOIN users u ON (u.id = f.from_user OR u.id = f.to_user)
            WHERE (f.from_user = $1 OR f.to_user = $1) AND u.id != $1""", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/friends/check/{user_id}")
async def friend_check(user_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], user_id)
    return {"status": row["status"] if row else None}

@app.post("/api/friends/accept")
async def friend_accept(data: dict):
    token = data.get("token"); friend_id = data.get("friend_id")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE friendships SET status = 'accepted' WHERE from_user = $1 AND to_user = $2", friend_id, user["id"])
    await manager.send_to(friend_id, {"type":"friend_accepted","by":user["username"]})
    return {"ok": True}

@app.get("/api/dm/{user_id}/messages")
async def get_dm(user_id: int, token: str):
    me_user = await get_current_user(token)
    if not me_user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT d.id, d.text, d.file_url, d.created_at,
            u.id AS user_id, u.username, u.avatar, u.premium_tier, u.nickname_color, u.nickname_gradient
            FROM dms d JOIN users u ON u.id = d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id ASC LIMIT 100""", me_user["id"], user_id)
    return [dict(r) for r in rows]

@app.get("/api/dm/list")
async def dm_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (other_id)
                other_id AS user_id,
                u.username, u.avatar, u.premium_tier, u.nickname_color, u.nickname_gradient,
                d.text AS last_text, d.file_url AS last_file, d.created_at AS last_time
            FROM (
                SELECT CASE WHEN from_user = $1 THEN to_user ELSE from_user END AS other_id,
                       text, file_url, created_at, id
                FROM dms WHERE from_user = $1 OR to_user = $1
            ) d
            JOIN users u ON u.id = d.other_id
            ORDER BY other_id, d.id DESC
        """, user["id"])
    return [dict(r) for r in rows]

# ===== АДМИНКА =====
@app.post("/api/admin/verify")
async def admin_verify(data: dict):
    token = data.get("token"); password = data.get("password")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Не админ")
    if password != ADMIN_PASSWORD:
        raise HTTPException(403, "Неверный пароль")
    return {"ok": True}

@app.get("/api/admin/users")
async def admin_users(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id, username, email, is_admin, is_moderator, premium_tier,
            is_banned, mute_until, created_at FROM users ORDER BY id""")
    return [dict(r) for r in rows]

@app.get("/api/admin/logs")
async def admin_logs(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT l.id, l.action, l.details, l.created_at,
            a.username AS admin_name, u.username AS target_name
            FROM admin_logs l
            LEFT JOIN users a ON a.id = l.admin_id
            LEFT JOIN users u ON u.id = l.target_id
            ORDER BY l.id DESC LIMIT 100""")
    return [dict(r) for r in rows]

@app.post("/api/admin/action")
async def admin_action(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Не админ")
    target_id = data.get("target_id"); action = data.get("action")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            await conn.execute("UPDATE users SET is_banned = TRUE WHERE id = $1", target_id)
            await manager.send_to(target_id, {"type":"banned"})
        elif action == "unban":
            await conn.execute("UPDATE users SET is_banned = FALSE WHERE id = $1", target_id)
        elif action == "grant_premium":
            await conn.execute("UPDATE users SET premium_tier = 'premium' WHERE id = $1", target_id)
        elif action == "grant_pro":
            await conn.execute("UPDATE users SET premium_tier = 'pro' WHERE id = $1", target_id)
        elif action == "revoke_premium":
            await conn.execute("UPDATE users SET premium_tier = NULL WHERE id = $1", target_id)
        elif action == "grant_admin":
            await conn.execute("UPDATE users SET is_admin = TRUE WHERE id = $1", target_id)
        elif action == "revoke_admin":
            await conn.execute("UPDATE users SET is_admin = FALSE WHERE id = $1", target_id)
        elif action == "grant_moderator":
            await conn.execute("UPDATE users SET is_moderator = TRUE WHERE id = $1", target_id)
        elif action == "revoke_moderator":
            await conn.execute("UPDATE users SET is_moderator = FALSE WHERE id = $1", target_id)
        elif action == "mute":
            await conn.execute("UPDATE users SET mute_until = NOW() + INTERVAL '1 hour' WHERE id = $1", target_id)
        elif action == "unmute":
            await conn.execute("UPDATE users SET mute_until = NULL WHERE id = $1", target_id)
        elif action == "delete":
            await conn.execute("DELETE FROM users WHERE id = $1", target_id)
        elif action == "reset_password":
            new_pass = secrets.token_hex(4)
            await conn.execute("UPDATE users SET password_hash = $1 WHERE id = $2", hash_password(new_pass), target_id)
            await log_admin(user["id"], action, target_id, f"new_pass={new_pass}")
            return {"ok": True, "new_password": new_pass}
    await log_admin(user["id"], action, target_id)
    return {"ok": True}

# ===== WEBSOCKET =====
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
                if user.get("mute_until"): continue
                channel_id = data.get("channel_id"); text = data.get("text",""); file_url = data.get("file_url")
                limits = LIMITS.get(tier_of(user), LIMITS[None])
                if len(text) > limits["msg"]: text = text[:limits["msg"]]
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO messages (channel_id, user_id, text, file_url) VALUES ($1,$2,$3,$4) RETURNING id, created_at",
                                              channel_id, user["id"], text, file_url)
                await manager.broadcast({"type":"message","id":row["id"],"channel_id":channel_id,
                    "user_id":user["id"],"username":user["username"],"avatar":user["avatar"],
                    "avatar_pos":user.get("avatar_pos"),"premium_tier":user.get("premium_tier"),
                    "nickname_color":user.get("nickname_color"),
                    "nickname_gradient":user.get("nickname_gradient"),
                    "avatar_frame":user.get("avatar_frame"),
                    "text":text,"file_url":file_url,"created_at":row["created_at"].isoformat()})
            elif t == "dm":
                to_user = data.get("to_user"); text = data.get("text",""); file_url = data.get("file_url")
                limits = LIMITS.get(tier_of(user), LIMITS[None])
                if len(text) > limits["msg"]: text = text[:limits["msg"]]
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO dms (from_user, to_user, text, file_url) VALUES ($1,$2,$3,$4) RETURNING id, created_at",
                                              user["id"], to_user, text, file_url)
                payload = {"type":"dm","id":row["id"],"from_user":user["id"],"to_user":to_user,
                    "username":user["username"],"avatar":user["avatar"],
                    "premium_tier":user.get("premium_tier"),
                    "nickname_color":user.get("nickname_color"),
                    "nickname_gradient":user.get("nickname_gradient"),
                    "text":text,"file_url":file_url,"created_at":row["created_at"].isoformat()}
                await manager.send_to(to_user, payload)
                await manager.send_to(user["id"], payload)
            elif t in ("call","offer","answer","ice","call_decline","call_end"):
                target = data.get("target")
                if target:
                    await manager.send_to(target, {**data, "from":user["id"], "from_name":user["username"], "from_avatar":user["avatar"]})
    except WebSocketDisconnect:
        manager.disconnect(user["id"])

@app.get("/")
async def index():
    return HTMLResponse(open("index.html", encoding="utf-8").read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))