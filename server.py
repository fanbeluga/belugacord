# ============================================
# BELUGACORD SERVER.PY — Beta 0.5 Patch 1
# ============================================
# Новое в Patch 1:
# - Подарки (GIFTS + коллекция в профиле + скрытие)
# - Жалобы на юзеров
# - Посхалки (счётчик + награда 100🏅)
# - SCAM-метка
# - Админ-абьюз (рассылка)
# - Рандомайзер подарков/монет/подписок
# - Роль "owner" (владелец) + "dev" + "head_admin"
# - Плеер музыка (broadcast "что играет")
# - Заявки на бекоины
# - Звание "Бета тестер"
# - Оптимизация (temp_id для сообщений)
# ============================================

import os
import json
import time
import asyncio
import secrets
import hashlib
import random
from typing import Optional

import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# === КОНФИГ ===
DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2026")
ADMIN_USERNAME = "_fan_beluga_"
ADMIN_PASSWORD = "12344321"
OWNER_USERNAME = "_fan_beluga_"  # владелец (можно поменять)

LIMITS = {
    None:      {"file": 10 * 1024 * 1024,  "msg": 2000,  "servers": 10,  "channels": 20},
    "premium": {"file": 50 * 1024 * 1024,  "msg": 4000,  "servers": 50,  "channels": 100},
    "pro":     {"file": 200 * 1024 * 1024, "msg": 10000, "servers": 999, "channels": 999},
}

GIFTS_DB = {
    "rose":     {"name": "Роза",            "emoji": "🌹", "price": 15},
    "bear":     {"name": "Мишка",           "emoji": "🧸", "price": 25},
    "cake":     {"name": "Торт",            "emoji": "🎂", "price": 50},
    "diamond":  {"name": "Алмаз",           "emoji": "💎", "price": 100},
    "crown":    {"name": "Корона",          "emoji": "👑", "price": 500},
    "dragon":   {"name": "Дракон",          "emoji": "🐉", "price": 1000},
    "legend":   {"name": "Легендарка",      "emoji": "💠", "price": 5000},
    "alien":    {"name": "Инопланетянин",   "emoji": "👽", "price": 10000},
    "galaxy":   {"name": "Галактика",       "emoji": "🌌", "price": 100000},
    "goldcat":  {"name": "Золотой Белуга",  "emoji": "🐱", "price": 1000000},
    "universe": {"name": "Мультивселенная", "emoji": "💫", "price": 1000000000},
}

EASTER_EGGS = ["song", "walls", "cat", "beluga"]

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

pool: Optional[asyncpg.Pool] = None
online_users = set()

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return pool

# ============================================
# ИНИЦИАЛИЗАЦИЯ БД
# ============================================
async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        # === USERS ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL, avatar TEXT, banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%',
            email VARCHAR(128), reset_code VARCHAR(16),
            is_admin BOOLEAN DEFAULT FALSE, is_moderator BOOLEAN DEFAULT FALSE,
            is_beta_tester BOOLEAN DEFAULT FALSE, is_scam BOOLEAN DEFAULT FALSE,
            is_dev BOOLEAN DEFAULT FALSE, is_head_admin BOOLEAN DEFAULT FALSE,
            premium_tier VARCHAR(8), premium_until TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE, ban_reason VARCHAR(256),
            mute_until TIMESTAMP, nickname_color VARCHAR(32), nickname_gradient VARCHAR(128),
            custom_status VARCHAR(128), avatar_frame VARCHAR(32),
            msg_sound TEXT, call_sound TEXT, hidden_online BOOLEAN DEFAULT FALSE,
            gifts_hidden BOOLEAN DEFAULT FALSE,
            easter_found TEXT DEFAULT '[]',
            easter_rewarded BOOLEAN DEFAULT FALSE,
            coins INTEGER DEFAULT 0, last_daily TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW())""")
        for col, typ in [
            ("is_admin", "BOOLEAN DEFAULT FALSE"), ("is_moderator", "BOOLEAN DEFAULT FALSE"),
            ("is_beta_tester", "BOOLEAN DEFAULT FALSE"), ("is_scam", "BOOLEAN DEFAULT FALSE"),
            ("is_dev", "BOOLEAN DEFAULT FALSE"), ("is_head_admin", "BOOLEAN DEFAULT FALSE"),
            ("premium_tier", "VARCHAR(8)"), ("premium_until", "TIMESTAMP"),
            ("is_banned", "BOOLEAN DEFAULT FALSE"), ("ban_reason", "VARCHAR(256)"),
            ("mute_until", "TIMESTAMP"), ("email", "VARCHAR(128)"), ("reset_code", "VARCHAR(16)"),
            ("avatar_pos", "TEXT DEFAULT '50% 50%'"), ("banner_pos", "TEXT DEFAULT '50% 50%'"),
            ("nickname_color", "VARCHAR(32)"), ("nickname_gradient", "VARCHAR(128)"),
            ("custom_status", "VARCHAR(128)"), ("avatar_frame", "VARCHAR(32)"),
            ("msg_sound", "TEXT"), ("call_sound", "TEXT"), ("hidden_online", "BOOLEAN DEFAULT FALSE"),
            ("gifts_hidden", "BOOLEAN DEFAULT FALSE"),
            ("easter_found", "TEXT DEFAULT '[]'"), ("easter_rewarded", "BOOLEAN DEFAULT FALSE"),
            ("coins", "INTEGER DEFAULT 0"), ("last_daily", "TIMESTAMP"),
        ]:
            try: await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
            except Exception: pass
        await conn.execute("UPDATE users SET is_admin = TRUE WHERE username = $1", ADMIN_USERNAME)
        await conn.execute("UPDATE users SET is_beta_tester = TRUE WHERE username = $1", ADMIN_USERNAME)

        # === SERVERS, MEMBERS, CHANNELS, MESSAGES ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers (
            id SERIAL PRIMARY KEY, name VARCHAR(64) NOT NULL,
            owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            invite_code VARCHAR(16) UNIQUE, avatar TEXT, banner TEXT, description TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")
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
            text TEXT, file_url TEXT, reply_to INTEGER, reactions TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW())""")

        # === FRIENDSHIPS, DMS ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(16) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, file_url TEXT, reactions TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW())""")

        # === ADMIN LOGS, STORIES, APPEALS ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs (
            id SERIAL PRIMARY KEY, admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(64), target_id INTEGER, details TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS stories (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text VARCHAR(256), file TEXT, created_at TIMESTAMP DEFAULT NOW(),
            expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '24 hours'))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_appeals (
            id SERIAL PRIMARY KEY, username VARCHAR(32), text TEXT,
            status VARCHAR(16) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())""")

        # === COINS ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_transactions (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER, reason VARCHAR(64), created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            coins INTEGER NOT NULL, price INTEGER DEFAULT 0,
            status VARCHAR(16) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(), resolved_at TIMESTAMP)""")

        # === VOTES ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY, question VARCHAR(256), options TEXT,
            active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS vote_votes (
            id SERIAL PRIMARY KEY, vote_id INTEGER REFERENCES votes(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            option_index INTEGER, created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (vote_id, user_id))""")

        # === PATCH 1: GIFTS ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts (
            id SERIAL PRIMARY KEY,
            from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            gift VARCHAR(32) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW())""")

        # === PATCH 1: REPORTS (жалобы) ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT,
            status VARCHAR(16) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW())""")

# === STARTUP ===
@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e: print(f"DB init error: {e}")
    async def cleanup_loop():
        while True:
            try:
                p = await get_pool()
                async with p.acquire() as conn:
                    await conn.execute("DELETE FROM stories WHERE expires_at < NOW()")
                    await conn.execute("UPDATE users SET premium_tier = NULL WHERE premium_until IS NOT NULL AND premium_until < NOW()")
            except Exception as e: print(f"Cleanup: {e}")
            await asyncio.sleep(3600)
    asyncio.create_task(cleanup_loop())

# ============================================
# ХЕЛПЕРЫ
# ============================================
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception: return False

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
    except Exception: return None

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
        await conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES ($1,$2,$3,$4)", admin_id, action, target_id, details)

def tier_of(user): return user.get("premium_tier")

def get_role(row):
    if not row: return "user"
    if row.get("username") == OWNER_USERNAME: return "owner"
    if row.get("is_dev"): return "dev"
    if row.get("is_head_admin"): return "head_admin"
    if row.get("is_admin"): return "admin"
    if row.get("is_moderator"): return "moderator"
    if row.get("is_beta_tester"): return "beta"
    return "user"

def user_public(row):
    role = get_role(row)
    return {
        "id": row["id"], "username": row["username"], "avatar": row["avatar"],
        "banner": row["banner"], "avatar_pos": row["avatar_pos"], "banner_pos": row["banner_pos"],
        "is_admin": row["is_admin"], "is_moderator": row["is_moderator"],
        "is_beta_tester": row.get("is_beta_tester", False),
        "is_scam": row.get("is_scam", False),
        "is_dev": row.get("is_dev", False),
        "is_head_admin": row.get("is_head_admin", False),
        "premium_tier": row.get("premium_tier"),
        "nickname_color": row.get("nickname_color"), "nickname_gradient": row.get("nickname_gradient"),
        "custom_status": row.get("custom_status"), "avatar_frame": row.get("avatar_frame"),
        "msg_sound": row.get("msg_sound"), "call_sound": row.get("call_sound"),
        "hidden_online": row.get("hidden_online"),
        "gifts_hidden": row.get("gifts_hidden", False),
        "coins": row.get("coins", 0),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "role": role, "online": row["id"] in online_users
    }

# ============================================
# АВТОРИЗАЦИЯ
# ============================================
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
    if len(username) < 2 or len(username) > 32: raise HTTPException(400, "Ник от 2 до 32 символов")
    if len(password) < 4: raise HTTPException(400, "Пароль минимум 4 символа")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
        if existing: raise HTTPException(400, "Ник занят")
        is_admin = (username == ADMIN_USERNAME)
        row = await conn.fetchrow("INSERT INTO users (username, password_hash, email, is_admin) VALUES ($1,$2,$3,$4) RETURNING *", username, hash_password(password), email, is_admin)
    token = make_token(row["id"], row["username"])
    return {"token": token, "user": user_public(row)}

@app.post("/api/login")
async def login(data: dict):
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
    if not row or not verify_password(password, row["password_hash"]): raise HTTPException(400, "Неверный ник или пароль")
    if row["is_banned"]: raise HTTPException(403, row.get("ban_reason") or "Ты забанен")
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
    tier = tier_of(user); premium = tier in ("premium", "pro"); pro = tier == "pro"
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET avatar = COALESCE($1, avatar), banner = COALESCE($2, banner),
            avatar_pos = COALESCE($3, avatar_pos), banner_pos = COALESCE($4, banner_pos),
            nickname_color = COALESCE($5, nickname_color), nickname_gradient = COALESCE($6, nickname_gradient),
            custom_status = COALESCE($7, custom_status), avatar_frame = COALESCE($8, avatar_frame),
            msg_sound = COALESCE($9, msg_sound), call_sound = COALESCE($10, call_sound),
            hidden_online = COALESCE($11, hidden_online) WHERE id = $12""",
            data.get("avatar"), data.get("banner"),
            data.get("avatar_pos"), data.get("banner_pos"),
            data.get("nickname_color") if premium else None,
            data.get("nickname_gradient") if pro else None,
            data.get("custom_status") if premium else None,
            data.get("avatar_frame") if pro else None,
            data.get("msg_sound") if premium else None,
            data.get("call_sound") if premium else None,
            data.get("hidden_online") if pro else None,
            user["id"])
    return {"ok": True}

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT id, username, avatar, banner, avatar_pos, banner_pos,
            is_admin, is_moderator, is_beta_tester, is_scam, is_dev, is_head_admin,
            premium_tier, nickname_color, nickname_gradient,
            custom_status, avatar_frame, hidden_online, gifts_hidden, is_banned, created_at
            FROM users WHERE id = $1""", user_id)
    if not row: raise HTTPException(404, "Не найден")
    d = dict(row); d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["role"] = get_role(row)
    d["online"] = user_id in online_users
    return d

@app.post("/api/user/change_nick")
async def change_nick(data: dict):
    token = data.get("token"); new_nick = (data.get("new_nick") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if len(new_nick) < 2 or len(new_nick) > 32: raise HTTPException(400, "Ник от 2 до 32 символов")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE username = $1", new_nick)
        if existing: raise HTTPException(400, "Ник занят")
        await conn.execute("UPDATE users SET username = $1 WHERE id = $2", new_nick, user["id"])
    new_token = make_token(user["id"], new_nick)
    return {"ok": True, "token": new_token}

# ============================================
# ПОДАРКИ (PATCH 1)
# ============================================
@app.post("/api/gifts/send")
async def gift_send(data: dict):
    token = data.get("token"); to_user = data.get("to_user"); gift_id = data.get("gift")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if gift_id not in GIFTS_DB: raise HTTPException(400, "Такого подарка нет")
    gift = GIFTS_DB[gift_id]
    if user.get("coins", 0) < gift["price"]: raise HTTPException(400, "Не хватает Бекоинов")
    if to_user == user["id"]: raise HTTPException(400, "Нельзя подарить себе")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id, username FROM users WHERE id = $1", to_user)
        if not target: raise HTTPException(404, "Юзер не найден")
        await conn.execute("UPDATE users SET coins = coins - $1 WHERE id = $2", gift["price"], user["id"])
        await conn.execute("INSERT INTO coin_transactions (user_id, amount, reason) VALUES ($1,$2,'gift_sent')", user["id"], -gift["price"])
        await conn.execute("INSERT INTO gifts (from_user, to_user, gift) VALUES ($1,$2,$3)", user["id"], to_user, gift_id)
    await manager.send_to(to_user, {
        "type": "gift_received",
        "gift_emoji": gift["emoji"],
        "gift_name": gift["name"],
        "from_name": user["username"]
    })
    return {"ok": True}

@app.get("/api/gifts/list/{user_id}")
async def gift_list(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT gifts_hidden FROM users WHERE id = $1", user_id)
        if not target: raise HTTPException(404, "Юзер не найден")
        if target.get("gifts_hidden"):
            return {"hidden": True, "gifts": []}
        rows = await conn.fetch("SELECT gift, created_at FROM gifts WHERE to_user = $1 ORDER BY id DESC", user_id)
    return {"hidden": False, "gifts": [{"gift": r["gift"], "created_at": r["created_at"].isoformat()} for r in rows]}

@app.post("/api/gifts/toggle_hidden")
async def gift_toggle_hidden(data: dict):
    token = data.get("token")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    new_val = not user.get("gifts_hidden", False)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET gifts_hidden = $1 WHERE id = $2", new_val, user["id"])
    return {"ok": True, "hidden": new_val}

# ============================================
# ЖАЛОБЫ
# ============================================
@app.post("/api/reports/submit")
async def report_submit(data: dict):
    token = data.get("token"); target_id = data.get("target_id"); text = (data.get("text") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not text: raise HTTPException(400, "Опиши причину")
    if target_id == user["id"]: raise HTTPException(400, "Нельзя на себя")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO reports (from_user, target_user, text) VALUES ($1,$2,$3)", user["id"], target_id, text)
    return {"ok": True}

@app.get("/api/admin/reports")
async def admin_reports(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id, r.text, r.created_at,
            f.username AS from_username, t.username AS target_username, r.target_user
            FROM reports r
            LEFT JOIN users f ON f.id = r.from_user
            LEFT JOIN users t ON t.id = r.target_user
            WHERE r.status = 'pending' ORDER BY r.id DESC""")
    return [dict(r) for r in rows]

@app.post("/api/admin/report_resolve")
async def admin_report_resolve(data: dict):
    token = data.get("token"); report_id = data.get("report_id"); action = data.get("action")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rep = await conn.fetchrow("SELECT target_user FROM reports WHERE id = $1", report_id)
        if not rep: raise HTTPException(404, "Не найдено")
        if action == "ban":
            await conn.execute("UPDATE users SET is_banned = TRUE, ban_reason = 'Жалоба' WHERE id = $1", rep["target_user"])
            await manager.send_to(rep["target_user"], {"type": "banned", "reason": "Жалоба"})
        await conn.execute("UPDATE reports SET status = $1 WHERE id = $2", action, report_id)
    return {"ok": True}

# ============================================
# ПОСХАЛКИ
# ============================================
@app.post("/api/easter/found")
async def easter_found(data: dict):
    token = data.get("token"); egg = data.get("egg")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if egg not in EASTER_EGGS: raise HTTPException(400, "Нет такой посхалки")
    try: found = json.loads(user.get("easter_found") or "[]")
    except: found = []
    if egg not in found: found.append(egg)
    all_found = len(found) >= len(EASTER_EGGS)
    already_rewarded = user.get("easter_rewarded", False)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET easter_found = $1 WHERE id = $2", json.dumps(found), user["id"])
        if all_found and not already_rewarded:
            await conn.execute("UPDATE users SET easter_rewarded = TRUE, coins = coins + 100 WHERE id = $1", user["id"])
            await conn.execute("INSERT INTO coin_transactions (user_id, amount, reason) VALUES ($1,100,'easter')", user["id"])
    return {"ok": True, "found": len(found), "total": len(EASTER_EGGS), "all_found": all_found, "already_rewarded": already_rewarded}

# ============================================
# АДМИН-АБЬЮЗ
# ============================================
@app.post("/api/admin/abuse")
async def admin_abuse(data: dict):
    token = data.get("token"); text = (data.get("text") or "").strip()
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    if not text: raise HTTPException(400, "Введи текст")
    await manager.broadcast({
        "type": "abuse",
        "from_name": user["username"],
        "from_avatar": user.get("avatar"),
        "text": text
    })
    await log_admin(user["id"], "abuse", 0, text[:200])
    return {"ok": True}

# ============================================
# РАНДОМАЙЗЕР
# ============================================
@app.post("/api/admin/random_give")
async def admin_random_give(data: dict):
    token = data.get("token"); username = (data.get("username") or "").strip(); rtype = data.get("type")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id, username FROM users WHERE username = $1", username)
        if not target: raise HTTPException(404, "Юзер не найден")
        tid = target["id"]
        result = ""
        if rtype == "gift":
            gid = random.choice(list(GIFTS_DB.keys()))
            gift = GIFTS_DB[gid]
            await conn.execute("INSERT INTO gifts (from_user, to_user, gift) VALUES ($1,$2,$3)", user["id"], tid, gid)
            await manager.send_to(tid, {"type": "gift_received", "gift_emoji": gift["emoji"], "gift_name": gift["name"], "from_name": "🎲 Рандомайзер"})
            result = f"Подарок: {gift['emoji']} {gift['name']}"
        elif rtype == "coins":
            amt = random.choice([50, 100, 200, 500, 1000, 5000])
            await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", amt, tid)
            await conn.execute("INSERT INTO coin_transactions (user_id, amount, reason) VALUES ($1,$2,'random')", tid, amt)
            result = f"+{amt} 🏅"
        elif rtype == "premium":
            tier = random.choice([None, "premium", "premium", "pro"])
            if tier:
                await conn.execute("UPDATE users SET premium_tier = $1 WHERE id = $2", tier, tid)
                result = f"Подписка: {tier}"
            else:
                result = "Ничего 😢"
        await log_admin(user["id"], f"random_{rtype}", tid, result)
    return {"ok": True, "result": result}

# ============================================
# СЕРВЕРА
# ============================================
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
        if count >= limits["servers"]: raise HTTPException(400, f"Лимит: {limits['servers']}")
        invite = secrets.token_urlsafe(8)
        row = await conn.fetchrow("INSERT INTO servers (name, owner_id, invite_code) VALUES ($1,$2,$3) RETURNING id, name, invite_code", name, user["id"], invite)
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2)", row["id"], user["id"])
        await conn.execute("INSERT INTO channels (server_id, name) VALUES ($1,$2)", row["id"], "общий")
    return dict(row)

@app.get("/api/servers/list")
async def list_servers(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id, s.name, s.invite_code, s.avatar, s.banner, s.description, s.owner_id
            FROM servers s JOIN server_members sm ON sm.server_id = s.id WHERE sm.user_id = $1""", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/servers/{server_id}")
async def get_server(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT s.id, s.name, s.invite_code, s.avatar, s.banner, s.description, s.owner_id,
            u.username AS owner_name FROM servers s JOIN users u ON u.id = s.owner_id WHERE s.id = $1""", server_id)
    if not row: raise HTTPException(404, "Не найден")
    return dict(row)

@app.post("/api/servers/update")
async def update_server(data: dict):
    token = data.get("token"); user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    server_id = data.get("server_id")
    p = await get_pool()
    async with p.acquire() as conn:
        server = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", server_id)
        if not server: raise HTTPException(404, "Не найден")
        if server["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        await conn.execute("""UPDATE servers SET name = COALESCE($1, name), avatar = COALESCE($2, avatar),
            banner = COALESCE($3, banner), description = COALESCE($4, description) WHERE id = $5""",
            data.get("name"), data.get("avatar"), data.get("banner"), data.get("description"), server_id)
    return {"ok": True}

@app.post("/api/servers/delete")
async def delete_server(data: dict):
    token = data.get("token"); user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    server_id = data.get("server_id")
    p = await get_pool()
    async with p.acquire() as conn:
        server = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", server_id)
        if not server: raise HTTPException(404, "Не найден")
        if server["owner_id"] != user["id"] and not user.get("is_admin"): raise HTTPException(403, "Только владелец")
        await conn.execute("DELETE FROM servers WHERE id = $1", server_id)
    return {"ok": True}

@app.post("/api/servers/leave")
async def leave_server(data: dict):
    token = data.get("token"); user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM server_members WHERE server_id = $1 AND user_id = $2", data.get("server_id"), user["id"])
    return {"ok": True}

@app.get("/api/servers/{server_id}/members")
async def get_members(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, u.premium_tier, u.is_admin, u.is_moderator,
            u.is_beta_tester, u.is_scam, u.is_dev, u.is_head_admin, sm.joined_at
            FROM server_members sm JOIN users u ON u.id = sm.user_id
            WHERE sm.server_id = $1 ORDER BY sm.joined_at""", server_id)
    result = []
    for r in rows:
        d = dict(r); d["joined_at"] = d["joined_at"].isoformat() if d.get("joined_at") else None
        d["role"] = get_role(r)
        d["online"] = d["id"] in online_users
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

# ============================================
# КАНАЛЫ + СООБЩЕНИЯ
# ============================================
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
    token = data.get("token"); user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()
    if not name: raise HTTPException(400, "Введи название")
    limits = LIMITS.get(tier_of(user), LIMITS[None])
    p = await get_pool()
    async with p.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM channels WHERE server_id = $1", data.get("server_id"))
        if count >= limits["channels"]: raise HTTPException(400, f"Лимит: {limits['channels']}")
        row = await conn.fetchrow("INSERT INTO channels (server_id, name, type) VALUES ($1,$2,$3) RETURNING id, name, type", data.get("server_id"), name, data.get("type", "text"))
    return dict(row)

@app.get("/api/channels/{channel_id}/messages")
async def get_messages(channel_id: int, token: str, limit: int = 50):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT m.id, m.text, m.file_url, m.created_at, m.reply_to, m.reactions,
            u.id AS user_id, u.username, u.avatar, u.avatar_pos, u.premium_tier, u.nickname_color,
            u.nickname_gradient, u.avatar_frame, u.is_banned, u.is_beta_tester,
            u.is_admin, u.is_moderator, u.is_scam, u.is_dev, u.is_head_admin,
            ru.username AS reply_to_name, rm.text AS reply_to_text
            FROM messages m JOIN users u ON u.id = m.user_id
            LEFT JOIN messages rm ON rm.id = m.reply_to
            LEFT JOIN users ru ON ru.id = rm.user_id
            WHERE m.channel_id = $1 ORDER BY m.id DESC LIMIT $2""", channel_id, limit)
    result = []
    for r in reversed(rows):
        d = dict(r); d["role"] = get_role(r); result.append(d)
    return result

@app.post("/api/upload")
async def upload_file(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    contents = await file.read()
    limits = LIMITS.get(tier_of(user), LIMITS[None])
    if len(contents) > limits["file"]: raise HTTPException(400, f"Файл больше {limits['file'] // 1024 // 1024} МБ")
    ext = os.path.splitext(file.filename)[1]
    fname = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f: f.write(contents)
    return {"url": f"/uploads/{fname}"}

# ============================================
# ДРУЗЬЯ
# ============================================
@app.post("/api/friends/request")
async def friend_request(data: dict):
    token = data.get("token"); to_username = (data.get("username") or "").strip()
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", to_username)
        if not target: raise HTTPException(404, "Не найден")
        if target["id"] == user["id"]: raise HTTPException(400, "Это ты")
        existing = await conn.fetchrow("SELECT id FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], target["id"])
        if existing: raise HTTPException(400, "Уже есть запрос")
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
        if existing: raise HTTPException(400, "Уже есть")
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
            u.nickname_gradient, u.is_banned, u.is_beta_tester, u.is_scam,
            f.status, f.from_user, f.to_user
            FROM friendships f JOIN users u ON (u.id = f.from_user OR u.id = f.to_user)
            WHERE (f.from_user = $1 OR f.to_user = $1) AND u.id != $1""", user["id"])
    result = []
    for r in rows:
        d = dict(r); d["online"] = d["id"] in online_users; result.append(d)
    return result

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

# ============================================
# ЛС
# ============================================
@app.get("/api/dm/{user_id}/messages")
async def get_dm(user_id: int, token: str):
    me_user = await get_current_user(token)
    if not me_user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT d.id, d.text, d.file_url, d.created_at, d.reactions,
            u.id AS user_id, u.username, u.avatar, u.premium_tier, u.nickname_color, u.nickname_gradient,
            u.is_banned, u.is_beta_tester, u.is_admin, u.is_moderator, u.is_scam, u.is_dev, u.is_head_admin
            FROM dms d JOIN users u ON u.id = d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id ASC LIMIT 100""", me_user["id"], user_id)
    result = []
    for r in rows:
        d = dict(r); d["role"] = get_role(r); result.append(d)
    return result

@app.get("/api/dm/list")
async def dm_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT ON (other_id) other_id AS user_id,
                u.username, u.avatar, u.premium_tier, u.nickname_color, u.nickname_gradient,
                d.text AS last_text, d.file_url AS last_file, d.created_at AS last_time
            FROM (SELECT CASE WHEN from_user = $1 THEN to_user ELSE from_user END AS other_id,
                       text, file_url, created_at, id FROM dms WHERE from_user = $1 OR to_user = $1) d
            JOIN users u ON u.id = d.other_id ORDER BY other_id, d.id DESC""", user["id"])
    return [dict(r) for r in rows]

# ============================================
# ВАЛЮТА
# ============================================
@app.get("/api/coins/balance")
async def coins_balance(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"coins": user.get("coins", 0)}

@app.get("/api/coins/leaders")
async def coins_leaders():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT username, coins FROM users WHERE coins > 0 ORDER BY coins DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.post("/api/coins/request")
async def coins_request(data: dict):
    token = data.get("token"); coins = int(data.get("coins", 0)); price = int(data.get("price", 0))
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if coins < 1 or coins > 999999: raise HTTPException(400, "Некорректное количество")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM coin_requests WHERE user_id = $1 AND status = 'pending'", user["id"])
        if existing: raise HTTPException(400, "У тебя уже есть заявка")
        await conn.execute("INSERT INTO coin_requests (user_id, coins, price) VALUES ($1,$2,$3)", user["id"], coins, price)
    admins = await (await get_pool()).fetch("SELECT id FROM users WHERE is_admin = TRUE")
    for a in admins:
        await manager.send_to(a["id"], {"type": "new_coin_request", "username": user["username"], "coins": coins, "price": price})
    return {"ok": True}

@app.get("/api/admin/coin_requests")
async def admin_coin_requests(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id, r.coins, r.price, r.created_at,
            u.id AS user_id, u.username, u.avatar
            FROM coin_requests r JOIN users u ON u.id = r.user_id
            WHERE r.status = 'pending' ORDER BY r.id DESC""")
    result = []
    for r in rows:
        d = dict(r); d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None; result.append(d)
    return result

@app.post("/api/admin/coin_resolve")
async def admin_coin_resolve(data: dict):
    token = data.get("token"); request_id = data.get("request_id"); action = data.get("action")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    if action not in ("approve", "reject"): raise HTTPException(400, "Неверное действие")
    p = await get_pool()
    async with p.acquire() as conn:
        req = await conn.fetchrow("SELECT * FROM coin_requests WHERE id = $1 AND status = 'pending'", request_id)
        if not req: raise HTTPException(404, "Заявка не найдена")
        if action == "approve":
            await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", req["coins"], req["user_id"])
            await conn.execute("INSERT INTO coin_transactions (user_id, amount, reason) VALUES ($1,$2,'request')", req["user_id"], req["coins"])
        await conn.execute("UPDATE coin_requests SET status = $1, resolved_at = NOW() WHERE id = $2", action, request_id)
    if action == "approve":
        await manager.send_to(req["user_id"], {"type": "coins_approved", "amount": req["coins"]})
    else:
        await manager.send_to(req["user_id"], {"type": "coins_rejected"})
    await log_admin(user["id"], "coin_" + action, req["user_id"], f"coins={req['coins']}")
    return {"ok": True}

# ============================================
# ЗВАНИЕ БЕТА ТЕСТЕР
# ============================================
@app.post("/api/admin/toggle_beta")
async def admin_toggle_beta(data: dict):
    token = data.get("token"); target_id = data.get("target_id"); grant = bool(data.get("grant"))
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_beta_tester = $1 WHERE id = $2", grant, target_id)
    await log_admin(user["id"], "beta_" + ("grant" if grant else "revoke"), target_id)
    if grant:
        await manager.send_to(target_id, {"type": "beta_granted"})
    return {"ok": True}

# ============================================
# ГОЛОСОВАНИЕ
# ============================================
@app.get("/api/vote/current")
async def vote_current():
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, question, options FROM votes WHERE active = TRUE ORDER BY id DESC LIMIT 1")
        if not row: return {}
        options = json.loads(row["options"])
        vote_rows = await conn.fetch("SELECT option_index, COUNT(*) as c FROM vote_votes WHERE vote_id = $1 GROUP BY option_index", row["id"])
        counts = {r["option_index"]: r["c"] for r in vote_rows}
        return {"id": row["id"], "question": row["question"], "options": [{"text": o, "votes": counts.get(i, 0)} for i, o in enumerate(options)], "my_vote": None}

@app.post("/api/vote/start")
async def vote_start(data: dict):
    token = data.get("token"); user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    question = (data.get("question") or "").strip(); options = data.get("options") or []
    if not question or len(options) < 2: raise HTTPException(400, "Заполни")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE votes SET active = FALSE WHERE active = TRUE")
        row = await conn.fetchrow("INSERT INTO votes (question, options) VALUES ($1,$2) RETURNING id", question, json.dumps(options))
    await manager.broadcast({"type": "vote_started", "vote_id": row["id"]})
    return {"ok": True}

@app.post("/api/vote/cast")
async def vote_cast(data: dict):
    token = data.get("token"); vote_id = data.get("vote_id"); option = data.get("option")
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        try: await conn.execute("INSERT INTO vote_votes (vote_id, user_id, option_index) VALUES ($1,$2,$3)", vote_id, user["id"], option)
        except Exception: await conn.execute("UPDATE vote_votes SET option_index = $1 WHERE vote_id = $2 AND user_id = $3", option, vote_id, user["id"])
    return {"ok": True}

# ============================================
# ОБЖАЛОВАНИЯ
# ============================================
@app.post("/api/appeal/submit")
async def appeal_submit(data: dict):
    username = (data.get("username") or "").strip(); text = (data.get("text") or "").strip()
    if not username or not text: raise HTTPException(400, "Заполни всё")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO ban_appeals (username, text) VALUES ($1,$2)", username, text)
    return {"ok": True}

@app.get("/api/admin/appeals")
async def admin_appeals(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id, username, text, status, created_at FROM ban_appeals WHERE status = 'pending' ORDER BY id DESC")
    return [{"id": r["id"], "username": r["username"], "text": r["text"], "created_at": r["created_at"].isoformat()} for r in rows]

@app.post("/api/admin/appeal_resolve")
async def appeal_resolve(data: dict):
    token = data.get("token"); appeal_id = data.get("appeal_id"); action = data.get("action")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        appeal = await conn.fetchrow("SELECT username FROM ban_appeals WHERE id = $1", appeal_id)
        if not appeal: raise HTTPException(404, "Не найдено")
        if action == "unban":
            await conn.execute("UPDATE users SET is_banned = FALSE, ban_reason = NULL WHERE username = $1", appeal["username"])
        await conn.execute("UPDATE ban_appeals SET status = $1 WHERE id = $2", action, appeal_id)
    return {"ok": True}

# ============================================
# АДМИНКА
# ============================================
@app.post("/api/admin/verify")
async def admin_verify(data: dict):
    token = data.get("token"); password = data.get("password")
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    if password != ADMIN_PASSWORD: raise HTTPException(403, "Неверный пароль")
    return {"ok": True}

@app.get("/api/admin/stats")
async def admin_stats(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM users")
        s = await conn.fetchval("SELECT COUNT(*) FROM servers")
        m = await conn.fetchval("SELECT COUNT(*) FROM messages")
    return {"users": u, "servers": s, "messages": m, "online": len(online_users)}

@app.get("/api/admin/users")
async def admin_users(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id, username, email, is_admin, is_moderator, is_beta_tester,
            is_scam, is_dev, is_head_admin, premium_tier, is_banned, coins, created_at FROM users ORDER BY id""")
    result = []
    for r in rows:
        d = dict(r); d["online"] = d["id"] in online_users; d["role"] = get_role(r); result.append(d)
    return result

@app.get("/api/admin/logs")
async def admin_logs(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT l.id, l.action, l.details, l.created_at,
            a.username AS admin_name, u.username AS target_name
            FROM admin_logs l LEFT JOIN users a ON a.id = l.admin_id
            LEFT JOIN users u ON u.id = l.target_id ORDER BY l.id DESC LIMIT 100""")
    return [dict(r) for r in rows]

@app.post("/api/admin/give_coins")
async def admin_give_coins(data: dict):
    token = data.get("token"); target_id = data.get("target_id"); amount = int(data.get("amount", 100))
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", amount, target_id)
    await log_admin(user["id"], "give_coins", target_id, f"amount={amount}")
    return {"ok": True}

@app.post("/api/admin/action")
async def admin_action(data: dict):
    token = data.get("token"); user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    target_id = data.get("target_id"); action = data.get("action")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            reason = data.get("reason", "")
            await conn.execute("UPDATE users SET is_banned = TRUE, ban_reason = $1 WHERE id = $2", reason, target_id)
            await manager.send_to(target_id, {"type":"banned","reason":reason})
        elif action == "unban": await conn.execute("UPDATE users SET is_banned = FALSE, ban_reason = NULL WHERE id = $1", target_id)
        elif action == "grant_premium": await conn.execute("UPDATE users SET premium_tier = 'premium' WHERE id = $1", target_id)
        elif action == "grant_pro": await conn.execute("UPDATE users SET premium_tier = 'pro' WHERE id = $1", target_id)
        elif action == "revoke_premium": await conn.execute("UPDATE users SET premium_tier = NULL WHERE id = $1", target_id)
        elif action == "grant_admin": await conn.execute("UPDATE users SET is_admin = TRUE WHERE id = $1", target_id)
        elif action == "revoke_admin": await conn.execute("UPDATE users SET is_admin = FALSE WHERE id = $1", target_id)
        elif action == "grant_moderator": await conn.execute("UPDATE users SET is_moderator = TRUE WHERE id = $1", target_id)
        elif action == "revoke_moderator": await conn.execute("UPDATE users SET is_moderator = FALSE WHERE id = $1", target_id)
        elif action == "scam":
            await conn.execute("UPDATE users SET is_scam = TRUE WHERE id = $1", target_id)
            await manager.send_to(target_id, {"type": "scam_changed", "user_id": target_id, "is_scam": True})
        elif action == "unscam":
            await conn.execute("UPDATE users SET is_scam = FALSE WHERE id = $1", target_id)
            await manager.send_to(target_id, {"type": "scam_changed", "user_id": target_id, "is_scam": False})
        elif action == "delete": await conn.execute("DELETE FROM users WHERE id = $1", target_id)
    await log_admin(user["id"], action, target_id)
    return {"ok": True}

# ============================================
# WEBSOCKET
# ============================================
class Manager:
    def __init__(self): self.active = {}
    async def connect(self, uid, ws):
        await ws.accept(); self.active[uid] = ws; online_users.add(uid)
        await self.broadcast_online(uid, True)
    def disconnect(self, uid):
        self.active.pop(uid, None); online_users.discard(uid)
    async def send_to(self, uid, data):
        ws = self.active.get(uid)
        if ws:
            try: await ws.send_json(data)
            except: pass
    async def broadcast(self, data):
        for ws in list(self.active.values()):
            try: await ws.send_json(data)
            except: pass
    async def broadcast_online(self, uid, is_online):
        await self.broadcast({"type": "online", "user_id": uid, "online": is_online})

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
                channel_id = data.get("channel_id"); text = data.get("text",""); file_url = data.get("file_url"); reply_to = data.get("reply_to"); temp_id = data.get("temp_id")
                limits = LIMITS.get(tier_of(user), LIMITS[None])
                if len(text) > limits["msg"]: text = text[:limits["msg"]]
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO messages (channel_id, user_id, text, file_url, reply_to) VALUES ($1,$2,$3,$4,$5) RETURNING id, created_at", channel_id, user["id"], text, file_url, reply_to)
                    reply_name = None; reply_text = None
                    if reply_to:
                        rr = await conn.fetchrow("SELECT m.text, u.username FROM messages m JOIN users u ON u.id = m.user_id WHERE m.id = $1", reply_to)
                        if rr: reply_name = rr["username"]; reply_text = rr["text"]
                await manager.broadcast({
                    "type":"message","id":row["id"],"channel_id":channel_id,"temp_id":temp_id,
                    "user_id":user["id"],"username":user["username"],"avatar":user["avatar"],
                    "avatar_pos":user.get("avatar_pos"),"premium_tier":user.get("premium_tier"),
                    "nickname_color":user.get("nickname_color"),"nickname_gradient":user.get("nickname_gradient"),
                    "avatar_frame":user.get("avatar_frame"),"is_banned":user.get("is_banned"),
                    "is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),
                    "is_beta_tester":user.get("is_beta_tester", False),
                    "is_scam":user.get("is_scam", False),
                    "is_dev":user.get("is_dev", False),
                    "is_head_admin":user.get("is_head_admin", False),
                    "role": get_role(user),
                    "text":text,"file_url":file_url,"created_at":row["created_at"].isoformat(),
                    "reply_to_name":reply_name,"reply_to_text":reply_text,"reactions":"{}"
                })
            elif t == "dm":
                to_user = data.get("to_user"); text = data.get("text",""); file_url = data.get("file_url"); temp_id = data.get("temp_id")
                limits = LIMITS.get(tier_of(user), LIMITS[None])
                if len(text) > limits["msg"]: text = text[:limits["msg"]]
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO dms (from_user, to_user, text, file_url) VALUES ($1,$2,$3,$4) RETURNING id, created_at", user["id"], to_user, text, file_url)
                payload = {"type":"dm","id":row["id"],"from_user":user["id"],"to_user":to_user,"temp_id":temp_id,
                    "username":user["username"],"avatar":user["avatar"],"premium_tier":user.get("premium_tier"),
                    "nickname_color":user.get("nickname_color"),"nickname_gradient":user.get("nickname_gradient"),
                    "is_banned":user.get("is_banned"),
                    "is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),
                    "is_beta_tester":user.get("is_beta_tester", False),
                    "is_scam":user.get("is_scam", False),
                    "role": get_role(user),
                    "text":text,"file_url":file_url,"created_at":row["created_at"].isoformat(),"reactions":"{}"}
                await manager.send_to(to_user, payload); await manager.send_to(user["id"], payload)
            elif t == "typing":
                await manager.broadcast({"type":"typing","channel_id":data.get("channel_id"),"username":user["username"]})
            elif t == "typing_dm":
                await manager.send_to(data.get("to_user"), {"type":"typing_dm","from":user["id"],"username":user["username"]})
            elif t == "music":
                await manager.broadcast({"type": "music", "track": data.get("track", ""), "from": user["username"]})
            elif t in ("call","offer","answer","ice","call_decline","call_end"):
                target = data.get("target")
                if target: await manager.send_to(target, {**data, "from":user["id"], "from_name":user["username"], "from_avatar":user["avatar"]})
    except WebSocketDisconnect:
        manager.disconnect(user["id"])
        await manager.broadcast_online(user["id"], False)

@app.get("/")
async def index():
    return HTMLResponse(open("index.html", encoding="utf-8").read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))