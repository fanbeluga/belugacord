# ============================================
# BELUGACORD SERVER.PY — BETA 1.7
# ============================================
import os, json, time, secrets, hashlib, random
from typing import Optional
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2026")
ADMIN_USERNAME = "_fan_beluga_"
OWNER_PASSWORD = "12344321"
CURRENT_VERSION = "1.7"

LIMITS = {
    None: {"file":10*1024*1024,"msg":2000,"servers":10,"channels":20},
    "premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100},
    "pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999},
}

DEFAULT_GIFTS = {
    "rose":{"name":"Роза","emoji":"🌹","price":15},
    "bear":{"name":"Мишка","emoji":"🧸","price":25},
    "cake":{"name":"Торт","emoji":"🎂","price":50},
    "diamond":{"name":"Алмаз","emoji":"💎","price":100},
    "crown":{"name":"Корона","emoji":"👑","price":500},
    "dragon":{"name":"Дракон","emoji":"🐉","price":1000},
    "legend":{"name":"Легендарка","emoji":"💠","price":5000},
    "alien":{"name":"Инопланетянин","emoji":"👽","price":10000},
    "galaxy":{"name":"Галактика","emoji":"🌌","price":100000},
    "goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},
    "universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000},
}

EASTER_EGGS = ["song","cat","beluga"]

CHANGELOG = {
    "1.7": {
        "title": "Belugacord Beta 1.7",
        "items": [
            "📞 Полноценные голосовые звонки (WebRTC)",
            "📑 Табы серверов/каналов сверху чата",
            "🟢 Кружок онлайна теперь на рамке аватара (пульсирует)",
            "🎁 Кастомные подарки с картинками (БОГ-ГУИ)",
            "🎨 NFT теперь можно загружать картинку вместо эмодзи",
            "🔔 Уведомления в реальном времени через WebSocket",
            "👥 Оптимистичное принятие заявок в друзья",
            "🎯 Тема CS2",
            "🐛 Множество багфиксов"
        ]
    },
    "1.6": {
        "title": "Belugacord Beta 1.6",
        "items": ["🔍 Поиск юзеров","👥 Друзья","⚙️ Настройки сервера","📱 Мобильный интерфейс","🔧 Модер-панель"]
    },
    "0.6": {
        "title": "Belugacord 0.6",
        "items": ["Первый публичный бета-релиз","Темы, магазин, NFT, подарки","Мини-игры"]
    }
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def no_cache_api(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
pool: Optional[asyncpg.Pool] = None
online_users = set()

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
            email VARCHAR(128), is_admin BOOLEAN DEFAULT FALSE, is_moderator BOOLEAN DEFAULT FALSE,
            is_beta_tester BOOLEAN DEFAULT FALSE, is_scam BOOLEAN DEFAULT FALSE,
            is_dev BOOLEAN DEFAULT FALSE, premium_tier VARCHAR(8),
            is_banned BOOLEAN DEFAULT FALSE, ban_reason VARCHAR(256),
            mute_until TIMESTAMP, nickname_color VARCHAR(32), nickname_gradient VARCHAR(128),
            custom_status VARCHAR(128), bio VARCHAR(256), fav_music VARCHAR(128),
            gifts_hidden BOOLEAN DEFAULT FALSE, easter_found TEXT DEFAULT '[]',
            easter_rewarded BOOLEAN DEFAULT FALSE, admin_password VARCHAR(128),
            coins INTEGER DEFAULT 0, messages_count INTEGER DEFAULT 0,
            frozen BOOLEAN DEFAULT FALSE, is_legend BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW())""")
        for col, typ in [
            ("is_admin","BOOLEAN DEFAULT FALSE"),("is_moderator","BOOLEAN DEFAULT FALSE"),
            ("is_beta_tester","BOOLEAN DEFAULT FALSE"),("is_scam","BOOLEAN DEFAULT FALSE"),
            ("is_dev","BOOLEAN DEFAULT FALSE"),("premium_tier","VARCHAR(8)"),
            ("is_banned","BOOLEAN DEFAULT FALSE"),("ban_reason","VARCHAR(256)"),
            ("email","VARCHAR(128)"),("mute_until","TIMESTAMP"),
            ("nickname_color","VARCHAR(32)"),("nickname_gradient","VARCHAR(128)"),
            ("custom_status","VARCHAR(128)"),("bio","VARCHAR(256)"),("fav_music","VARCHAR(128)"),
            ("gifts_hidden","BOOLEAN DEFAULT FALSE"),("easter_found","TEXT DEFAULT '[]'"),
            ("easter_rewarded","BOOLEAN DEFAULT FALSE"),("admin_password","VARCHAR(128)"),
            ("coins","INTEGER DEFAULT 0"),("messages_count","INTEGER DEFAULT 0"),
            ("frozen","BOOLEAN DEFAULT FALSE"),("is_legend","BOOLEAN DEFAULT FALSE"),
        ]:
            try: await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass
        await conn.execute("UPDATE users SET is_admin = TRUE WHERE username = $1", ADMIN_USERNAME)

        await conn.execute("""CREATE TABLE IF NOT EXISTS servers (
            id SERIAL PRIMARY KEY, name VARCHAR(64), owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            invite_code VARCHAR(16) UNIQUE, avatar TEXT, banner TEXT, description TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")
        for col, typ in [("avatar","TEXT"),("banner","TEXT"),("description","TEXT")]:
            try: await conn.execute(f"ALTER TABLE servers ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass

        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members (
            server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            joined_at TIMESTAMP DEFAULT NOW(), PRIMARY KEY (server_id, user_id))""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS channels (
            id SERIAL PRIMARY KEY, server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,
            name VARCHAR(64), type VARCHAR(16) DEFAULT 'text', created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY, channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, file_url TEXT, reply_to INTEGER, reactions TEXT DEFAULT '{}',
            edited BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW())""")
        for col, typ in [("reply_to","INTEGER"),("reactions","TEXT DEFAULT '{}'"),("edited","BOOLEAN DEFAULT FALSE")]:
            try: await conn.execute(f"ALTER TABLE messages ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass

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
            action VARCHAR(64), target_id INTEGER, details TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_appeals (
            id SERIAL PRIMARY KEY, username VARCHAR(32), text TEXT,
            status VARCHAR(16) DEFAULT 'pending', created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, status VARCHAR(16) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            coins INTEGER NOT NULL, price INTEGER DEFAULT 0,
            status VARCHAR(16) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(), resolved_at TIMESTAMP)""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            gift VARCHAR(32) NOT NULL, created_at TIMESTAMP DEFAULT NOW())""")

        # Кастомные подарки (созданные владельцем)
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts (
            gift_id VARCHAR(32) PRIMARY KEY, name VARCHAR(64) NOT NULL,
            emoji VARCHAR(8), image TEXT, price INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series (
            id SERIAL PRIMARY KEY, name VARCHAR(64), emoji VARCHAR(8), image TEXT,
            total INTEGER NOT NULL, sold INTEGER DEFAULT 0, price INTEGER NOT NULL,
            rarity VARCHAR(16) DEFAULT 'common',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW())""")
        try: await conn.execute("ALTER TABLE nft_series ADD COLUMN IF NOT EXISTS image TEXT")
        except: pass

        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items (
            id SERIAL PRIMARY KEY, series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,
            number INTEGER NOT NULL, owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT NOW())""")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e: print(f"DB init: {e}")

def hash_password(p):
    s = secrets.token_hex(16)
    return f"{s}${hashlib.sha256((s+p).encode()).hexdigest()}"

def verify_password(p, st):
    try:
        s, h = st.split("$", 1)
        return hashlib.sha256((s+p).encode()).hexdigest() == h
    except: return False

def make_token(uid, un):
    d = f"{uid}:{un}:{int(time.time())}"
    return f"{d}:{hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]}"

def parse_token(t):
    try:
        parts = t.split(":")
        if len(parts) != 4: return None
        uid, un, ts, sig = parts
        d = f"{uid}:{un}:{ts}"
        if sig != hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]: return None
        return int(uid), un
    except: return None

async def get_current_user(token):
    parsed = parse_token(token)
    if not parsed: return None
    uid, un = parsed
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", uid)
        return dict(row) if row else None

async def log_admin(aid, action, tid, details=""):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES ($1,$2,$3,$4)", aid, action, tid, details)
    except: pass

def get_role(row):
    if not row: return "user"
    if row.get("username") == ADMIN_USERNAME: return "owner"
    if row.get("is_dev"): return "dev"
    if row.get("is_admin"): return "admin"
    if row.get("is_moderator"): return "moderator"
    if row.get("is_beta_tester"): return "beta"
    return "user"

def user_public(row):
    return {
        "id": row["id"], "username": row["username"], "avatar": row["avatar"],
        "banner": row["banner"], "avatar_pos": row["avatar_pos"], "banner_pos": row["banner_pos"],
        "is_admin": row["is_admin"], "is_moderator": row["is_moderator"],
        "is_beta_tester": row.get("is_beta_tester", False),
        "is_scam": row.get("is_scam", False), "is_dev": row.get("is_dev", False),
        "premium_tier": row.get("premium_tier"),
        "nickname_color": row.get("nickname_color"), "nickname_gradient": row.get("nickname_gradient"),
        "custom_status": row.get("custom_status"), "bio": row.get("bio"), "fav_music": row.get("fav_music"),
        "coins": row.get("coins", 0), "messages_count": row.get("messages_count", 0),
        "is_legend": row.get("is_legend", False),
        "has_admin_pass": bool(row.get("admin_password")),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "role": get_role(row), "online": row["id"] in online_users
    }

async def get_all_gifts():
    """Сливаем DEFAULT_GIFTS с кастомными из БД"""
    gifts = dict(DEFAULT_GIFTS)
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM custom_gifts")
            for r in rows:
                gifts[r["gift_id"]] = {
                    "name": r["name"], "emoji": r["emoji"],
                    "image": r["image"], "price": r["price"]
                }
    except: pass
    return gifts

# ============================================
# CHANGELOG
# ============================================
@app.get("/api/changelog")
async def changelog():
    return {"current": CURRENT_VERSION, "all": CHANGELOG}

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
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    em = (data.get("email") or "").strip() or None
    if len(u) < 2 or len(u) > 32: raise HTTPException(400, "Ник 2-32")
    if len(pw) < 4: raise HTTPException(400, "Пароль минимум 4")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM users WHERE username = $1", u): raise HTTPException(400, "Занят")
        is_admin = (u == ADMIN_USERNAME)
        row = await conn.fetchrow("INSERT INTO users (username, password_hash, email, is_admin) VALUES ($1,$2,$3,$4) RETURNING *", u, hash_password(pw), em, is_admin)
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row)}

@app.post("/api/login")
async def login(data: dict):
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", u)
    if not row or not verify_password(pw, row["password_hash"]): raise HTTPException(400, "Неверный ник/пароль")
    if row["is_banned"]: raise HTTPException(403, row.get("ban_reason") or "Забанен")
    if row.get("frozen"): raise HTTPException(403, "Аккаунт заморожен")
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row)}

@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return user_public(user)

@app.post("/api/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET avatar = COALESCE($1, avatar), banner = COALESCE($2, banner),
            avatar_pos = COALESCE($3, avatar_pos), banner_pos = COALESCE($4, banner_pos),
            nickname_color = COALESCE($5, nickname_color), nickname_gradient = COALESCE($6, nickname_gradient),
            bio = COALESCE($7, bio), fav_music = COALESCE($8, fav_music) WHERE id = $9""",
            data.get("avatar"), data.get("banner"), data.get("avatar_pos"), data.get("banner_pos"),
            data.get("nickname_color"), data.get("nickname_gradient"),
            data.get("bio"), data.get("fav_music"), user["id"])
    return {"ok": True}

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT id, username, avatar, banner, avatar_pos, banner_pos,
            is_admin, is_moderator, is_beta_tester, is_scam, is_dev,
            premium_tier, nickname_color, nickname_gradient, bio, fav_music,
            messages_count, is_legend, created_at FROM users WHERE id = $1""", user_id)
    if not row: raise HTTPException(404, "Не найден")
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["role"] = get_role(row)
    d["online"] = user_id in online_users
    return d

@app.post("/api/user/change_nick")
async def change_nick(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    new_nick = (data.get("new_nick") or "").strip()
    if len(new_nick) < 2 or len(new_nick) > 32: raise HTTPException(400, "Ник 2-32")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM users WHERE username = $1", new_nick): raise HTTPException(400, "Занят")
        await conn.execute("UPDATE users SET username = $1 WHERE id = $2", new_nick, user["id"])
    return {"ok": True, "token": make_token(user["id"], new_nick)}

# ============================================
# ПОИСК ЮЗЕРОВ
# ============================================
@app.get("/api/users/search")
async def users_search(q: str, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    q = (q or "").strip()
    if len(q) < 2: return []
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id, username, avatar, is_admin, is_moderator,
            is_beta_tester, is_scam, is_dev FROM users
            WHERE username ILIKE $1 AND id != $2 ORDER BY username LIMIT 20""",
            f"%{q}%", user["id"])
    result = []
    for r in rows:
        d = dict(r); d["role"] = get_role(r); result.append(d)
    return result

# ============================================
# АДМИН
# ============================================
@app.post("/api/admin/set_password")
async def admin_set_password(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    pw = data.get("password") or ""
    if len(pw) < 4: raise HTTPException(400, "Минимум 4")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET admin_password = $1 WHERE id = $2", hash_password(pw), user["id"])
    return {"ok": True}

@app.post("/api/admin/verify")
async def admin_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    pw = data.get("password") or ""
    stored = user.get("admin_password")
    if stored and not verify_password(pw, stored): raise HTTPException(403, "Неверный пароль")
    if not stored and pw != "12344321": raise HTTPException(403, "Установи пароль")
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
    return {"users":u,"servers":s,"messages":m,"online":len(online_users)}

@app.get("/api/admin/users")
async def admin_users(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id, username, is_admin, is_moderator, is_beta_tester, is_scam, is_dev, premium_tier, is_banned FROM users ORDER BY id")
    return [dict(r) for r in rows]

@app.post("/api/admin/action")
async def admin_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    tid = data.get("target_id"); action = data.get("action")
    is_owner = user["username"] == ADMIN_USERNAME
    owner_only = ["grant_premium","grant_pro","revoke_premium","grant_admin","revoke_admin","scam","unscam"]
    if action in owner_only and not is_owner: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            reason = data.get("reason","")
            await conn.execute("UPDATE users SET is_banned = TRUE, ban_reason = $1 WHERE id = $2", reason, tid)
        elif action == "unban": await conn.execute("UPDATE users SET is_banned = FALSE WHERE id = $1", tid)
        elif action == "mute":
            dur = int(data.get("duration", 3600))
            await conn.execute(f"UPDATE users SET mute_until = NOW() + INTERVAL '{dur} seconds' WHERE id = $1", tid)
        elif action == "grant_premium": await conn.execute("UPDATE users SET premium_tier = 'premium' WHERE id = $1", tid)
        elif action == "grant_pro": await conn.execute("UPDATE users SET premium_tier = 'pro' WHERE id = $1", tid)
        elif action == "scam": await conn.execute("UPDATE users SET is_scam = TRUE WHERE id = $1", tid)
    await log_admin(user["id"], action, tid)
    return {"ok": True}

@app.get("/api/admin/reports")
async def admin_reports(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id, r.text, r.target_user,
            f.username AS from_username, t.username AS target_username
            FROM reports r LEFT JOIN users f ON f.id = r.from_user
            LEFT JOIN users t ON t.id = r.target_user
            WHERE r.status = 'pending' ORDER BY r.id DESC""")
    return [dict(r) for r in rows]

@app.get("/api/admin/appeals")
async def admin_appeals(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id, username, text, created_at FROM ban_appeals WHERE status = 'pending' ORDER BY id DESC")
    result = []
    for r in rows:
        d = dict(r); d["created_at"] = d["created_at"].isoformat(); result.append(d)
    return result

@app.get("/api/admin/logs")
async def admin_logs(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT l.id, l.action, l.created_at, a.username AS admin_name
            FROM admin_logs l LEFT JOIN users a ON a.id = l.admin_id ORDER BY l.id DESC LIMIT 100""")
    result = []
    for r in rows:
        d = dict(r); d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        result.append(d)
    return result

# ============================================
# МОДЕР-ПАНЕЛЬ
# ============================================
async def check_mod(user):
    if not user: raise HTTPException(401, "Не авторизован")
    if not (user.get("is_moderator") or user.get("is_admin") or user["username"] == ADMIN_USERNAME):
        raise HTTPException(403, "Нет прав модератора")

@app.get("/api/mod/reports")
async def mod_reports(token: str):
    user = await get_current_user(token)
    await check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id, r.text, r.target_user,
            f.username AS from_username, t.username AS target_username
            FROM reports r LEFT JOIN users f ON f.id = r.from_user
            LEFT JOIN users t ON t.id = r.target_user
            WHERE r.status = 'pending' ORDER BY r.id DESC""")
    return [dict(r) for r in rows]

@app.post("/api/mod/mute")
async def mod_mute(data: dict):
    user = await get_current_user(data.get("token"))
    await check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        mins = int(data.get("minutes", 60))
        await conn.execute(f"UPDATE users SET mute_until = NOW() + INTERVAL '{mins*60} seconds' WHERE id = $1",
            int(data.get("user_id",0)))
    await log_admin(user["id"], "mod_mute", int(data.get("user_id",0)), f"{mins} min")
    return {"ok": True}

@app.post("/api/mod/warn")
async def mod_warn(data: dict):
    user = await get_current_user(data.get("token"))
    await check_mod(user)
    await log_admin(user["id"], "warn", int(data.get("user_id",0)), data.get("reason",""))
    return {"ok": True}

@app.post("/api/mod/dismiss_report")
async def mod_dismiss_report(data: dict):
    user = await get_current_user(data.get("token"))
    await check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE reports SET status = 'dismissed' WHERE id = $1", int(data.get("report_id",0)))
    return {"ok": True}

@app.post("/api/mod/mute_by_name")
async def mod_mute_by_name(data: dict):
    user = await get_current_user(data.get("token"))
    await check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        mins = int(data.get("minutes", 60))
        await conn.execute(f"UPDATE users SET mute_until = NOW() + INTERVAL '{mins*60} seconds' WHERE id = $1", target["id"])
    await log_admin(user["id"], "mod_mute", target["id"], f"{mins} min")
    return {"ok": True}

@app.post("/api/mod/warn_by_name")
async def mod_warn_by_name(data: dict):
    user = await get_current_user(data.get("token"))
    await check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
    await log_admin(user["id"], "warn", target["id"], data.get("reason",""))
    return {"ok": True}

# ============================================
# ЖАЛОБЫ / ОБЖАЛОВАНИЯ
# ============================================
@app.post("/api/reports/submit")
async def report_submit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = data.get("target_id"); text = (data.get("text") or "").strip()
    if not text: raise HTTPException(400, "Опиши")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO reports (from_user, target_user, text) VALUES ($1,$2,$3)", user["id"], tid, text)
    return {"ok": True}

@app.post("/api/appeal/submit")
async def appeal_submit(data: dict):
    u = (data.get("username") or "").strip(); t = (data.get("text") or "").strip()
    if not u or not t: raise HTTPException(400, "Заполни")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO ban_appeals (username, text) VALUES ($1,$2)", u, t)
    return {"ok": True}

# ============================================
# ВЛАДЕЛЕЦ
# ============================================
@app.post("/api/owner/verify")
async def owner_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    if data.get("password") != OWNER_PASSWORD: raise HTTPException(403, "Неверный пароль")
    return {"ok": True}

@app.get("/api/owner/stats")
async def owner_stats(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM users")
        m = await conn.fetchval("SELECT COUNT(*) FROM messages")
        c = await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        n = await conn.fetchval("SELECT COUNT(*) FROM nft_items")
        g = await conn.fetchval("SELECT COUNT(*) FROM gifts")
    return {"users":u,"messages":m,"coins":c,"nfts":n,"gifts":g,"online":len(online_users)}

@app.post("/api/owner/troll")
async def owner_troll(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    troll = data.get("troll")
    await manager.broadcast({"type":"event","event":troll})
    return {"ok": True}

@app.post("/api/owner/suddness")
async def owner_suddness(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    events = ["confetti","balloons","cat_mode"]
    evt = random.choice(events)
    await manager.broadcast({"type":"event","event":evt})
    return {"ok": True, "event": evt}

@app.post("/api/owner/give_coins")
async def owner_give_coins(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        amt = int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", amt, target["id"])
    return {"ok": True}

@app.post("/api/owner/take_coins")
async def owner_take_coins(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        amt = int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins = GREATEST(coins - $1, 0) WHERE id = $2", amt, target["id"])
    return {"ok": True}

@app.post("/api/owner/give_all")
async def owner_give_all(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    amt = int(data.get("amount",10))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins = coins + $1", amt)
    return {"ok": True}

@app.post("/api/owner/announce")
async def owner_announce(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    text = data.get("text","")
    await manager.broadcast({"type":"abuse","from_name":user["username"],"from_avatar":user.get("avatar"),"text":text})
    return {"ok": True}

@app.post("/api/owner/mass_dm")
async def owner_mass_dm(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    text = data.get("text","")
    for uid in list(online_users):
        await manager.send_to(uid, {"type":"abuse","from_name":user["username"],"from_avatar":user.get("avatar"),"text":text})
    return {"ok": True}

@app.post("/api/owner/change_nick")
async def owner_change_nick(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET username = $1 WHERE username = $2", data.get("new_nick"), data.get("username"))
    return {"ok": True}

@app.post("/api/owner/reset_pass")
async def owner_reset_pass(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    new_pass = secrets.token_hex(4)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET password_hash = $1 WHERE username = $2", hash_password(new_pass), data.get("username"))
    return {"ok": True, "new_password": new_pass}

@app.post("/api/owner/kick")
async def owner_kick(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    return {"ok": True}

@app.post("/api/owner/mute")
async def owner_mute(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        mins = int(data.get("minutes",60))
        await conn.execute(f"UPDATE users SET mute_until = NOW() + INTERVAL '{mins*60} seconds' WHERE id = $1", target["id"])
    return {"ok": True}

@app.post("/api/owner/shadow_ban")
async def owner_shadow(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    return {"ok": True}

@app.post("/api/owner/delete_all_msgs")
async def owner_del_msgs(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        await conn.execute("DELETE FROM messages WHERE user_id = $1", target["id"])
    return {"ok": True}

@app.post("/api/owner/legend")
async def owner_legend(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_legend = TRUE WHERE username = $1", data.get("username"))
    return {"ok": True}

@app.post("/api/owner/give_premium")
async def owner_give_premium(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET premium_tier = $1 WHERE username = $2", data.get("tier","premium"), data.get("username"))
    return {"ok": True}

@app.post("/api/owner/toggle_beta")
async def owner_toggle_beta(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_beta_tester = NOT is_beta_tester WHERE username = $1", data.get("username"))
    return {"ok": True}

@app.post("/api/owner/grant_admin")
async def owner_grant_admin(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin = TRUE WHERE username = $1", data.get("username"))
    return {"ok": True}

@app.post("/api/owner/revoke_admin")
async def owner_revoke_admin(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin = FALSE WHERE username = $1", data.get("username"))
    return {"ok": True}

@app.post("/api/owner/read_chat")
async def owner_read_chat(token: str, username: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
        if not target: raise HTTPException(404, "Не найден")
        rows = await conn.fetch("""SELECT m.text, u.username AS from_user, m.created_at
            FROM messages m JOIN users u ON u.id = m.user_id
            WHERE m.user_id = $1 ORDER BY m.id DESC LIMIT 50""", target["id"])
    return {"messages": [{"from": r["from_user"], "text": r["text"]} for r in rows]}

@app.post("/api/owner/write_as")
async def owner_write_as(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id, username, avatar FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        ch = await conn.fetchrow("""SELECT c.id FROM channels c
            JOIN server_members sm ON sm.server_id = c.server_id
            WHERE sm.user_id = $1 ORDER BY c.id LIMIT 1""", target["id"])
        if ch:
            msg = await conn.fetchrow("INSERT INTO messages (channel_id, user_id, text) VALUES ($1,$2,$3) RETURNING *",
                ch["id"], target["id"], data.get("text",""))
            await manager.broadcast({"type":"message","id":msg["id"],"channel_id":ch["id"],
                "user_id":target["id"],"username":target["username"],"avatar":target["avatar"],
                "text":data.get("text",""),"created_at":msg["created_at"].isoformat()})
    return {"ok": True}

@app.post("/api/owner/create_nft")
async def owner_create_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""INSERT INTO nft_series (name, emoji, image, total, price, rarity, created_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
            data.get("name"), data.get("emoji","🎨"), data.get("image"),
            int(data.get("total",1)), int(data.get("price",0)), data.get("rarity","common"), user["id"])
    return {"ok": True, "id": row["id"]}

@app.post("/api/owner/give_nft")
async def owner_give_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        series = await conn.fetchrow("SELECT * FROM nft_series WHERE id = $1", int(data.get("nft_id",0)))
        if not series: raise HTTPException(404, "NFT не найден")
        number = (series["sold"] or 0) + 1
        await conn.execute("INSERT INTO nft_items (series_id, number, owner_id) VALUES ($1,$2,$3)",
            series["id"], number, target["id"])
        await conn.execute("UPDATE nft_series SET sold = sold + 1 WHERE id = $1", series["id"])
    return {"ok": True}

@app.post("/api/owner/delete_nft")
async def owner_delete_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM nft_series WHERE id = $1", int(data.get("nft_id",0)))
    return {"ok": True}

@app.post("/api/owner/create_gift")
async def owner_create_gift(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    gid = (data.get("gift_id") or "").strip().lower()
    if not gid or len(gid) > 32: raise HTTPException(400, "ID 1-32")
    name = (data.get("name") or "").strip()
    if not name: raise HTTPException(400, "Название нужно")
    price = int(data.get("price", 0))
    if price <= 0: raise HTTPException(400, "Цена > 0")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT gift_id FROM custom_gifts WHERE gift_id = $1", gid):
            raise HTTPException(400, "Такой ID уже есть")
        if gid in DEFAULT_GIFTS:
            raise HTTPException(400, "ID занят дефолтным подарком")
        await conn.execute("""INSERT INTO custom_gifts (gift_id, name, emoji, image, price)
            VALUES ($1,$2,$3,$4,$5)""", gid, name, data.get("emoji","🎁"), data.get("image"), price)
    return {"ok": True}

@app.post("/api/owner/delete_gift")
async def owner_delete_gift(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_gifts WHERE gift_id = $1", data.get("gift_id"))
    return {"ok": True}

@app.get("/api/gifts/all")
async def gifts_all():
    gifts = await get_all_gifts()
    return [{"gift_id": k, "name": v["name"], "emoji": v.get("emoji"),
             "image": v.get("image"), "price": v["price"]} for k, v in gifts.items()]

@app.post("/api/owner/self_destruct")
async def owner_self_destruct(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        ch = int(data.get("channel_id",0))
        await conn.execute("DELETE FROM messages WHERE channel_id = $1", ch)
    await manager.broadcast({"type":"event","event":"self_destruct","channel_id":ch})
    return {"ok": True}

@app.post("/api/owner/clean_db")
async def owner_clean_db(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE created_at < NOW() - INTERVAL '30 days'")
        await conn.execute("DELETE FROM dms WHERE created_at < NOW() - INTERVAL '30 days'")
    return {"ok": True}

# ============================================
# ЭКОНОМИКА
# ============================================
@app.get("/api/coins/balance")
async def coins_balance(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"coins": user.get("coins",0)}

@app.post("/api/coins/request")
async def coins_request(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO coin_requests (user_id, coins, price) VALUES ($1,$2,$3)",
            user["id"], int(data.get("coins",0)), int(data.get("price",0)))
    return {"ok": True}

@app.get("/api/coins/leaders")
async def coins_leaders():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.get("/api/admin/coin_requests")
async def admin_coin_requests(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT cr.id, cr.coins, cr.price, u.username
            FROM coin_requests cr JOIN users u ON u.id = cr.user_id
            WHERE cr.status = 'pending' ORDER BY cr.id DESC""")
    return [dict(r) for r in rows]

@app.post("/api/admin/coin_resolve")
async def admin_coin_resolve(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        req = await conn.fetchrow("SELECT * FROM coin_requests WHERE id = $1", int(data.get("request_id",0)))
        if not req: raise HTTPException(404, "Не найдено")
        action = data.get("action")
        if action == "approve":
            await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", req["coins"], req["user_id"])
            await conn.execute("UPDATE coin_requests SET status = 'approved', resolved_at = NOW() WHERE id = $1", req["id"])
            await manager.send_to(req["user_id"], {"type":"coins_approved","amount":req["coins"]})
        else:
            await conn.execute("UPDATE coin_requests SET status = 'rejected', resolved_at = NOW() WHERE id = $1", req["id"])
            await manager.send_to(req["user_id"], {"type":"coins_rejected"})
    return {"ok": True}

# ============================================
# ПОДАРКИ
# ============================================
@app.post("/api/gifts/send")
async def gift_send(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gift_id = data.get("gift")
    all_gifts = await get_all_gifts()
    if gift_id not in all_gifts: raise HTTPException(400, "Нет такого подарка")
    gift = all_gifts[gift_id]
    price = gift["price"]
    if user.get("coins",0) < price: raise HTTPException(400, "Не хватает 🏅")
    to_id = int(data.get("to_user",0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins = coins - $1 WHERE id = $2", price, user["id"])
        await conn.execute("INSERT INTO gifts (from_user, to_user, gift) VALUES ($1,$2,$3)", user["id"], to_id, gift_id)
    await manager.send_to(to_id, {
        "type":"gift_received",
        "gift_emoji": gift.get("emoji"),
        "gift_name": gift["name"],
        "gift_image": gift.get("image"),
        "from_name": user["username"]
    })
    return {"ok": True}

@app.get("/api/gifts/list/{user_id}")
async def gifts_list(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT gift FROM gifts WHERE to_user = $1 ORDER BY id DESC", user_id)
    return {"gifts": [dict(r) for r in rows]}

@app.post("/api/gifts/sell")
async def gift_sell(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gift_id = data.get("gift")
    all_gifts = await get_all_gifts()
    if gift_id not in all_gifts: raise HTTPException(400, "Нет подарка")
    price = all_gifts[gift_id]["price"] // 2
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM gifts WHERE to_user = $1 AND gift = $2 ORDER BY id LIMIT 1", user["id"], gift_id)
        if not row: raise HTTPException(400, "Нет такого подарка")
        await conn.execute("DELETE FROM gifts WHERE id = $1", row["id"])
        await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", price, user["id"])
    return {"ok": True, "got": price}

# ============================================
# NFT
# ============================================
@app.get("/api/nft/list")
async def nft_list():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM nft_series WHERE sold < total ORDER BY id DESC")
    return [{"id": r["id"], "name": r["name"], "emoji": r["emoji"], "image": r.get("image"),
             "price": r["price"], "total": r["total"], "sold": r["sold"],
             "rarity": r["rarity"], "number": (r["sold"] or 0)+1} for r in rows]

@app.get("/api/nft/my")
async def nft_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT ni.id, ni.number, ns.name, ns.emoji, ns.image, ns.price, ns.total, ns.rarity
            FROM nft_items ni JOIN nft_series ns ON ns.id = ni.series_id
            WHERE ni.owner_id = $1 ORDER BY ni.id DESC""", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/nft/{nft_id}")
async def nft_get(nft_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM nft_series WHERE id = $1", nft_id)
    if not r: raise HTTPException(404, "Не найден")
    return {"id": r["id"], "name": r["name"], "emoji": r["emoji"], "image": r.get("image"),
            "price": r["price"], "total": r["total"], "sold": r["sold"], "rarity": r["rarity"]}

@app.post("/api/nft/buy")
async def nft_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    nid = int(data.get("nft_id",0))
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM nft_series WHERE id = $1", nid)
        if not s: raise HTTPException(404, "Нет")
        if s["sold"] >= s["total"]: raise HTTPException(400, "Распродано")
        if user.get("coins",0) < s["price"]: raise HTTPException(400, "Не хватает 🏅")
        number = s["sold"] + 1
        await conn.execute("UPDATE users SET coins = coins - $1 WHERE id = $2", s["price"], user["id"])
        await conn.execute("INSERT INTO nft_items (series_id, number, owner_id) VALUES ($1,$2,$3)", nid, number, user["id"])
        await conn.execute("UPDATE nft_series SET sold = sold + 1 WHERE id = $1", nid)
    return {"ok": True, "number": number}

# ============================================
# ДРУЗЬЯ
# ============================================
@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT f.id, f.from_user, f.to_user, f.status,
            CASE WHEN f.from_user = $1 THEN f.to_user ELSE f.from_user END AS other_id
            FROM friendships f WHERE f.from_user = $1 OR f.to_user = $1""", user["id"])
        result = []
        for r in rows:
            o = await conn.fetchrow("""SELECT id, username, avatar, is_admin, is_moderator,
                is_beta_tester, is_scam, is_dev FROM users WHERE id = $1""", r["other_id"])
            if not o: continue
            result.append({
                "id": o["id"], "username": o["username"], "avatar": o["avatar"],
                "status": r["status"], "from_user": r["from_user"], "to_user": r["to_user"],
                "online": o["id"] in online_users,
                "is_admin": o["is_admin"], "is_moderator": o["is_moderator"],
                "is_beta_tester": o["is_beta_tester"], "is_scam": o["is_scam"],
                "role": get_role(o)
            })
    return result

@app.post("/api/friends/request")
async def friends_request(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    target_name = (data.get("username") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", target_name)
        if not target: raise HTTPException(404, "Не найден")
        if target["id"] == user["id"]: raise HTTPException(400, "Себя нельзя")
        ex = await conn.fetchrow("""SELECT id FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)""",
            user["id"], target["id"])
        if ex: raise HTTPException(400, "Уже есть заявка")
        await conn.execute("INSERT INTO friendships (from_user, to_user) VALUES ($1,$2)", user["id"], target["id"])
    await manager.send_to(target["id"], {"type":"friend_request","from_id":user["id"],"username":user["username"]})
    return {"ok": True}

@app.post("/api/friends/request_by_id")
async def friends_request_by_id(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id",0))
    if tid == user["id"]: raise HTTPException(400, "Себя нельзя")
    p = await get_pool()
    async with p.acquire() as conn:
        ex = await conn.fetchrow("SELECT id FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], tid)
        if ex: raise HTTPException(400, "Уже есть")
        await conn.execute("INSERT INTO friendships (from_user, to_user) VALUES ($1,$2)", user["id"], tid)
    await manager.send_to(tid, {"type":"friend_request","from_id":user["id"],"username":user["username"]})
    return {"ok": True}

@app.post("/api/friends/accept")
async def friends_accept(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    fid = int(data.get("friend_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, from_user, to_user, status FROM friendships WHERE id = $1", fid)
        if not row: raise HTTPException(404, "Заявка не найдена")
        if row["to_user"] != user["id"]: raise HTTPException(403, "Не твоя заявка")
        if row["status"] == "accepted": return {"ok": True, "status": "accepted", "already": True}
        await conn.execute("UPDATE friendships SET status = 'accepted' WHERE id = $1", fid)
    await manager.send_to(row["from_user"], {"type":"friend_accepted","friend_id":user["id"],"username":user["username"]})
    await manager.send_to(user["id"], {"type":"friend_accepted","friend_id":row["from_user"]})
    return {"ok": True, "status": "accepted"}

@app.post("/api/friends/decline")
async def friends_decline(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE id = $1 AND to_user = $2",
            int(data.get("friend_id",0)), user["id"])
    return {"ok": True}

@app.post("/api/friends/remove")
async def friends_remove(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""DELETE FROM friendships
            WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)""",
            user["id"], int(data.get("user_id",0)))
    return {"ok": True}

@app.get("/api/friends/check/{user_id}")
async def friends_check(user_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("""SELECT status FROM friendships
            WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)""", user["id"], user_id)
    return {"status": r["status"] if r else "none"}

# ============================================
# СЕРВЕРЫ / КАНАЛЫ
# ============================================
@app.get("/api/servers/list")
async def servers_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id, s.name, s.avatar FROM servers s
            JOIN server_members sm ON sm.server_id = s.id WHERE sm.user_id = $1 ORDER BY s.id""", user["id"])
    return [dict(r) for r in rows]

@app.post("/api/servers/create")
async def servers_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя нужно")
    p = await get_pool()
    async with p.acquire() as conn:
        code = secrets.token_urlsafe(8)[:12]
        s = await conn.fetchrow("INSERT INTO servers (name, owner_id, invite_code) VALUES ($1,$2,$3) RETURNING *",
            name, user["id"], code)
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2)", s["id"], user["id"])
        await conn.execute("INSERT INTO channels (server_id, name) VALUES ($1,'общий')", s["id"])
    return {"id": s["id"], "name": s["name"], "invite_code": code}

@app.post("/api/servers/join")
async def servers_join(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    code = (data.get("invite") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM servers WHERE invite_code = $1", code)
        if not s: raise HTTPException(404, "Неверный код")
        try:
            await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2)", s["id"], user["id"])
        except: pass
    return {"id": s["id"], "name": s["name"]}

@app.get("/api/servers/{server_id}")
async def server_get(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM servers WHERE id = $1", server_id)
    if not s: raise HTTPException(404, "Нет сервера")
    d = dict(s)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return d

@app.get("/api/servers/{server_id}/channels")
async def server_channels(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, type FROM channels WHERE server_id = $1 ORDER BY id", server_id)
    return [dict(r) for r in rows]

@app.get("/api/servers/{server_id}/members")
async def server_members(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, u.is_admin, u.is_moderator,
            u.is_beta_tester, u.is_scam, u.is_dev FROM users u
            JOIN server_members sm ON sm.user_id = u.id WHERE sm.server_id = $1""", server_id)
    result = []
    for r in rows:
        d = dict(r); d["role"] = get_role(r); result.append(d)
    return result

@app.post("/api/servers/update")
async def server_update(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", int(data.get("server_id",0)))
        if not s or s["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец сервера")
        await conn.execute("UPDATE servers SET name = COALESCE($1,name), description = COALESCE($2,description) WHERE id = $3",
            data.get("name"), data.get("description"), int(data.get("server_id",0)))
    return {"ok": True}

@app.post("/api/servers/delete")
async def server_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", int(data.get("server_id",0)))
        if not s or s["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        await conn.execute("DELETE FROM servers WHERE id = $1", int(data.get("server_id",0)))
    return {"ok": True}

@app.post("/api/servers/leave")
async def server_leave(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM server_members WHERE server_id = $1 AND user_id = $2",
            int(data.get("server_id",0)), user["id"])
    return {"ok": True}

@app.post("/api/servers/regen_invite")
async def server_regen_invite(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT owner_id FROM servers WHERE id = $1", int(data.get("server_id",0)))
        if not s or s["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        code = secrets.token_urlsafe(8)[:12]
        await conn.execute("UPDATE servers SET invite_code = $1 WHERE id = $2", code, int(data.get("server_id",0)))
    return {"ok": True, "invite_code": code}

@app.post("/api/channels/create")
async def channel_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    sid = int(data.get("server_id",0)); name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя нужно")
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("INSERT INTO channels (server_id, name) VALUES ($1,$2) RETURNING id, name",
            sid, name)
    return {"id": r["id"], "name": r["name"]}

# ============================================
# СООБЩЕНИЯ
# ============================================
@app.get("/api/channels/{channel_id}/messages")
async def channel_messages(channel_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT m.id, m.text, m.file_url, m.reactions, m.created_at,
            m.user_id, u.username, u.avatar, u.avatar_pos, u.is_admin, u.is_moderator,
            u.is_beta_tester, u.is_scam, u.is_dev
            FROM messages m JOIN users u ON u.id = m.user_id
            WHERE m.channel_id = $1 ORDER BY m.id ASC LIMIT 200""", channel_id)
    result = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        d["role"] = get_role(r)
        d["reactions"] = json.loads(d.get("reactions") or "{}")
        result.append(d)
    return result

@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT d.id, d.from_user, d.to_user, d.text, d.file_url, d.created_at,
            u.username, u.avatar, u.avatar_pos
            FROM dms d JOIN users u ON u.id = d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id ASC LIMIT 200""", user["id"], user_id)
    result = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        result.append(d)
    return result

@app.post("/api/messages/edit")
async def message_edit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE messages SET text = $1, edited = TRUE WHERE id = $2 AND user_id = $3",
            data.get("text",""), int(data.get("message_id",0)), user["id"])
    return {"ok": True}

@app.post("/api/messages/delete")
async def message_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        if user.get("is_admin") or user["username"] == ADMIN_USERNAME:
            await conn.execute("DELETE FROM messages WHERE id = $1", int(data.get("message_id",0)))
        else:
            await conn.execute("DELETE FROM messages WHERE id = $1 AND user_id = $2",
                int(data.get("message_id",0)), user["id"])
    await manager.broadcast({"type":"message_deleted","id":int(data.get("message_id",0))})
    return {"ok": True}

@app.post("/api/messages/reaction")
async def message_reaction(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("message_id",0)); emoji = data.get("emoji","👍")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT reactions FROM messages WHERE id = $1", mid)
        if not row: raise HTTPException(404, "Нет")
        react = json.loads(row["reactions"] or "{}")
        arr = react.get(emoji, [])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        react[emoji] = arr
        await conn.execute("UPDATE messages SET reactions = $1 WHERE id = $2", json.dumps(react), mid)
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":react})
    return {"ok": True}

@app.post("/api/upload")
async def upload(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    lim = LIMITS.get(user.get("premium_tier"), LIMITS[None])["file"]
    content = await file.read()
    if len(content) > lim: raise HTTPException(400, "Файл большой")
    ext = os.path.splitext(file.filename or "")[1][:8]
    name = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(content)
    return {"url": f"/uploads/{name}"}

# ============================================
# ПАСХАЛКИ
# ============================================
@app.post("/api/easter/found")
async def easter_found(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    egg = data.get("egg")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT easter_found, easter_rewarded FROM users WHERE id = $1", user["id"])
        found = json.loads(row["easter_found"] or "[]")
        rewarded = row["easter_rewarded"]
        if egg in found: return {"found": len(found), "total": len(EASTER_EGGS), "already_rewarded": rewarded}
        found.append(egg)
        all_found = len(found) >= len(EASTER_EGGS)
        already_rewarded = rewarded
        if all_found and not rewarded:
            await conn.execute("UPDATE users SET easter_found=$1, easter_rewarded=TRUE, coins=coins+100 WHERE id=$2",
                json.dumps(found), user["id"])
            already_rewarded = False
        else:
            await conn.execute("UPDATE users SET easter_found=$1 WHERE id=$2", json.dumps(found), user["id"])
    return {"found": len(found), "total": len(EASTER_EGGS), "all_found": all_found, "already_rewarded": already_rewarded}

# ============================================
# WEBSOCKET
# ============================================
class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}

    async def connect(self, uid: int, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(uid, []).append(ws)
        online_users.add(uid)

    def disconnect(self, uid: int, ws: WebSocket):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except ValueError: pass
            if not self.connections[uid]:
                del self.connections[uid]
                online_users.discard(uid)

    async def send_to(self, uid: int, data: dict):
        for ws in list(self.connections.get(uid, [])):
            try: await ws.send_json(data)
            except: pass

    async def broadcast(self, data: dict, exclude: int = None):
        for uid, conns in list(self.connections.items()):
            if exclude and uid == exclude: continue
            for ws in list(conns):
                try: await ws.send_json(data)
                except: pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str):
    user = await get_current_user(token)
    if not user:
        await ws.close()
        return
    uid = user["id"]
    await manager.connect(uid, ws)
    # Отправляем список онлайна
    try: await ws.send_json({"type":"online_list","users":list(online_users)})
    except: pass
    # Уведомляем всех что я онлайн
    await manager.broadcast({"type":"user_online","user_id":uid}, exclude=uid)
    try:
        while True:
            raw = await ws.receive_text()
            try: data = json.loads(raw)
            except: continue
            t = data.get("type")

            if t == "message":
                ch = data.get("channel_id"); text = (data.get("text") or "")[:2000]
                file_url = data.get("file_url"); temp_id = data.get("temp_id")
                if not ch: continue
                p = await get_pool()
                async with p.acquire() as conn:
                    msg = await conn.fetchrow("""INSERT INTO messages (channel_id, user_id, text, file_url)
                        VALUES ($1,$2,$3,$4) RETURNING *""", int(ch), uid, text, file_url)
                    await conn.execute("UPDATE users SET messages_count = messages_count + 1 WHERE id = $1", uid)
                    members = await conn.fetch("""SELECT sm.user_id FROM server_members sm
                        JOIN channels c ON c.server_id = sm.server_id WHERE c.id = $1""", int(ch))
                payload = {"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,
                    "username":user["username"],"avatar":user.get("avatar"),"avatar_pos":user.get("avatar_pos"),
                    "text":text,"file_url":file_url,"created_at":msg["created_at"].isoformat(),
                    "is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),
                    "is_beta_tester":user.get("is_beta_tester"),"is_scam":user.get("is_scam"),
                    "role":get_role(user),"temp_id":temp_id}
                for m in members:
                    await manager.send_to(m["user_id"], payload)

            elif t == "dm":
                to_id = int(data.get("to_user",0)); text = (data.get("text") or "")[:2000]
                file_url = data.get("file_url"); temp_id = data.get("temp_id")
                p = await get_pool()
                async with p.acquire() as conn:
                    msg = await conn.fetchrow("""INSERT INTO dms (from_user, to_user, text, file_url)
                        VALUES ($1,$2,$3,$4) RETURNING *""", uid, to_id, text, file_url)
                payload = {"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,
                    "username":user["username"],"avatar":user.get("avatar"),"avatar_pos":user.get("avatar_pos"),
                    "text":text,"file_url":file_url,"created_at":msg["created_at"].isoformat(),
                    "temp_id":temp_id}
                await manager.send_to(to_id, payload)
                await manager.send_to(uid, payload)

            elif t == "typing":
                ch = data.get("channel_id")
                p = await get_pool()
                async with p.acquire() as conn:
                    members = await conn.fetch("""SELECT sm.user_id FROM server_members sm
                        JOIN channels c ON c.server_id = sm.server_id WHERE c.id = $1""", int(ch))
                for m in members:
                    if m["user_id"] != uid:
                        await manager.send_to(m["user_id"], {"type":"typing","channel_id":ch,"username":user["username"]})

            elif t == "typing_dm":
                to_id = int(data.get("to_user",0))
                await manager.send_to(to_id, {"type":"typing_dm","from":uid,"username":user["username"]})

            elif t == "call_offer":
                to_id = int(data.get("to",0))
                await manager.send_to(to_id, {
                    "type":"call_offer","from":uid,"sdp":data.get("sdp"),
                    "username":user["username"],"avatar":user.get("avatar")
                })

            elif t == "call_answer":
                to_id = int(data.get("to",0))
                await manager.send_to(to_id, {"type":"call_answer","from":uid,"sdp":data.get("sdp")})

            elif t == "call_ice":
                to_id = int(data.get("to",0))
                await manager.send_to(to_id, {"type":"call_ice","from":uid,"candidate":data.get("candidate")})

            elif t == "call_decline":
                to_id = int(data.get("to",0))
                await manager.send_to(to_id, {"type":"call_decline","from":uid})

            elif t == "call_end":
                to_id = int(data.get("to",0))
                await manager.send_to(to_id, {"type":"call_end","from":uid})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS error: {e}")
    finally:
        manager.disconnect(uid, ws)
        await manager.broadcast({"type":"user_offline","user_id":uid})

# ============================================
# СТАТИКА И СТАРТ
# ============================================
@app.get("/manifest.json")
async def manifest():
    return {
        "name": "Belugacord Beta 1.7", "short_name": "Belugacord",
        "start_url": "/", "display": "standalone",
        "background_color": "#0a0a12", "theme_color": "#0a0a12",
        "icons": [{"src": "/uploads/icon.png", "sizes": "192x192", "type": "image/png"}]
    }

@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, ws="websockets",
                proxy_headers=True, forwarded_allow_ips="*")