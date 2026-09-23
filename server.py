# ============================================
# BELUGACORD SERVER.PY — 2.0
# ============================================
import os, json, time, asyncio, secrets, hashlib, random
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
OWNER_PASSWORD = "12344321"

LIMITS = {
    None: {"file":10*1024*1024,"msg":2000,"servers":10,"channels":20},
    "premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100},
    "pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999},
}
GIFTS_DB = {
    "rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},
    "cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},
    "crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},
    "legend":{"name":"Легендарка","emoji":"💠","price":5000},"alien":{"name":"Инопланетянин","emoji":"👽","price":10000},
    "galaxy":{"name":"Галактика","emoji":"🌌","price":100000},"goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},
    "universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000},
}
EASTER_EGGS = ["song","cat","beluga"]

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
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_transactions (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER, reason VARCHAR(64), created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests (
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            coins INTEGER NOT NULL, price INTEGER DEFAULT 0,
            status VARCHAR(16) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(), resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts (
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            gift VARCHAR(32) NOT NULL, created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series (
            id SERIAL PRIMARY KEY, name VARCHAR(64), emoji VARCHAR(8), image TEXT,
            total INTEGER NOT NULL, sold INTEGER DEFAULT 0, price INTEGER NOT NULL,
            rarity VARCHAR(16) DEFAULT 'common',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW())""")
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
        "gifts_hidden": row.get("gifts_hidden", False),
        "coins": row.get("coins", 0), "messages_count": row.get("messages_count", 0),
        "is_legend": row.get("is_legend", False),
        "has_admin_pass": bool(row.get("admin_password")),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "role": get_role(row), "online": row["id"] in online_users
    }

# АВТОРИЗАЦИЯ
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

# АДМИН
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
    owner_only = ["grant_premium","grant_pro","revoke_premium","grant_admin","revoke_admin",
                  "grant_moderator","revoke_moderator","scam","unscam"]
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

# ЖАЛОБЫ / ОБЖАЛОВАНИЯ
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

# ВЛАДЕЛЕЦ
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
        target = await conn.fetchrow("SELECT id, is_beta_tester FROM users WHERE username = $1", data.get("username"))
        if not target: raise HTTPException(404, "Не найден")
        new_val = not target.get("is_beta_tester", False)
        await conn.execute("UPDATE users SET is_beta_tester = $1 WHERE id = $2", new_val, target["id"])
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

@app.post("/api/owner/create_nft")
async def create_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    name = data.get("name"); emoji = data.get("emoji","🎨")
    total = int(data.get("total",0)); price = int(data.get("price",0)); rarity = data.get("rarity","common")
    if not name or total < 1 or price < 1: raise HTTPException(400, "Заполни всё")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("INSERT INTO nft_series (name, emoji, total, price, rarity, created_by) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
            name, emoji, total, price, rarity, user["id"])
    return {"ok": True, "id": row["id"]}

@app.post("/api/owner/delete_nft")
async def owner_delete_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM nft_series WHERE id = $1", data.get("nft_id"))
    return {"ok": True}

@app.post("/api/owner/clean_db")
async def owner_clean_db(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE created_at < NOW() - INTERVAL '1 year'")
    return {"ok": True}

@app.post("/api/owner/self_destruct")
async def owner_self_destruct(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    ch = data.get("channel_id")
    if not ch: raise HTTPException(400, "Нет канала")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE channel_id = $1", ch)
    return {"ok": True}

@app.get("/api/owner/read_chat")
async def owner_read_chat(token: str, username: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
        if not target: raise HTTPException(404, "Не найден")
        rows = await conn.fetch("""SELECT d.text, d.created_at, u.username AS from_name
            FROM dms d JOIN users u ON u.id = d.from_user
            WHERE d.from_user = $1 OR d.to_user = $1 ORDER BY d.id DESC LIMIT 50""", target["id"])
    return {"messages": [{"from": r["from_name"], "text": r["text"], "time": r["created_at"].isoformat()} for r in rows]}

@app.post("/api/owner/write_as")
async def owner_write_as(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    return {"ok": True}

# ПОСХАЛКИ
@app.post("/api/easter/found")
async def easter_found(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    egg = data.get("egg")
    if egg not in EASTER_EGGS: raise HTTPException(400, "Нет такой")
    try: found = json.loads(user.get("easter_found") or "[]")
    except: found = []
    if egg not in found: found.append(egg)
    all_found = len(found) >= len(EASTER_EGGS)
    already = user.get("easter_rewarded", False)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET easter_found = $1 WHERE id = $2", json.dumps(found), user["id"])
        if all_found and not already:
            await conn.execute("UPDATE users SET easter_rewarded = TRUE, coins = coins + 100 WHERE id = $1", user["id"])
    return {"ok": True, "found": len(found), "total": len(EASTER_EGGS), "all_found": all_found, "already_rewarded": already}

# БЕКОИНЫ
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
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    c = int(data.get("coins",0)); pr = int(data.get("price",0))
    if c < 1 or c > 999999999: raise HTTPException(400, "Неверно")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM coin_requests WHERE user_id = $1 AND status = 'pending'", user["id"])
        if existing: raise HTTPException(400, "Уже есть заявка")
        await conn.execute("INSERT INTO coin_requests (user_id, coins, price) VALUES ($1,$2,$3)", user["id"], c, pr)
    return {"ok": True}

@app.get("/api/admin/coin_requests")
async def admin_coin_requests(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id, r.coins, r.price, u.username
            FROM coin_requests r JOIN users u ON u.id = r.user_id
            WHERE r.status = 'pending' ORDER BY r.id DESC""")
    return [dict(r) for r in rows]

@app.post("/api/admin/coin_resolve")
async def admin_coin_resolve(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    rid = data.get("request_id"); action = data.get("action")
    p = await get_pool()
    async with p.acquire() as conn:
        req = await conn.fetchrow("SELECT * FROM coin_requests WHERE id = $1 AND status = 'pending'", rid)
        if not req: raise HTTPException(404, "Не найдена")
        if action == "approve":
            await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", req["coins"], req["user_id"])
        await conn.execute("UPDATE coin_requests SET status = $1, resolved_at = NOW() WHERE id = $2", action, rid)
    if action == "approve":
        await manager.send_to(req["user_id"], {"type":"coins_approved","amount":req["coins"]})
    else:
        await manager.send_to(req["user_id"], {"type":"coins_rejected"})
    return {"ok": True}

# ПОДАРКИ
@app.post("/api/gifts/send")
async def gift_send(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    to_user = data.get("to_user"); gid = data.get("gift")
    if gid not in GIFTS_DB: raise HTTPException(400, "Нет такого")
    gift = GIFTS_DB[gid]
    if user.get("coins", 0) < gift["price"]: raise HTTPException(400, "Не хватает")
    if to_user == user["id"]: raise HTTPException(400, "Себе нельзя")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins = coins - $1 WHERE id = $2", gift["price"], user["id"])
        await conn.execute("INSERT INTO gifts (from_user, to_user, gift) VALUES ($1,$2,$3)", user["id"], to_user, gid)
    await manager.send_to(to_user, {"type":"gift_received","gift_emoji":gift["emoji"],"gift_name":gift["name"],"from_name":user["username"]})
    return {"ok": True}

@app.get("/api/gifts/list/{user_id}")
async def gift_list(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT gifts_hidden FROM users WHERE id = $1", user_id)
        if not target: raise HTTPException(404, "Не найден")
        if target.get("gifts_hidden"): return {"hidden": True, "gifts": []}
        rows = await conn.fetch("SELECT gift FROM gifts WHERE to_user = $1", user_id)
    return {"hidden": False, "gifts": [{"gift": r["gift"]} for r in rows]}

@app.post("/api/gifts/sell")
async def gift_sell(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gid = data.get("gift")
    if gid not in GIFTS_DB: raise HTTPException(400, "Нет такого")
    gift = GIFTS_DB[gid]
    price = int(gift["price"] * 0.5)
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM gifts WHERE to_user = $1 AND gift = $2 LIMIT 1", user["id"], gid)
        if not row: raise HTTPException(400, "У тебя нет такого")
        await conn.execute("DELETE FROM gifts WHERE id = $1", row["id"])
        await conn.execute("UPDATE users SET coins = coins + $1 WHERE id = $2", price, user["id"])
    return {"ok": True, "price": price}

@app.post("/api/gifts/toggle_hidden")
async def gift_toggle(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    new_val = not user.get("gifts_hidden", False)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET gifts_hidden = $1 WHERE id = $2", new_val, user["id"])
    return {"ok": True, "hidden": new_val}

# NFT
@app.get("/api/nft/list")
async def nft_list():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id, name, emoji, total, sold, price, rarity,
            (sold + 1) AS number FROM nft_series WHERE sold < total ORDER BY id DESC""")
    return [dict(r) for r in rows]

@app.get("/api/nft/my")
async def nft_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT i.id, i.number, s.name, s.emoji, s.rarity, s.price, s.total
            FROM nft_items i JOIN nft_series s ON s.id = i.series_id WHERE i.owner_id = $1""", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/nft/{nft_id}")
async def nft_get(nft_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name, emoji, total, sold, price, rarity FROM nft_series WHERE id = $1", nft_id)
    if not row: raise HTTPException(404, "Не найден")
    d = dict(row); d["number"] = d["sold"] + 1
    return d

@app.post("/api/nft/buy")
async def nft_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    sid = data.get("nft_id")
    p = await get_pool()
    async with p.acquire() as conn:
        series = await conn.fetchrow("SELECT * FROM nft_series WHERE id = $1", sid)
        if not series: raise HTTPException(404, "Не найден")
        if series["sold"] >= series["total"]: raise HTTPException(400, "Распродано")
        if user.get("coins", 0) < series["price"]: raise HTTPException(400, "Не хватает")
        number = series["sold"] + 1
        await conn.execute("INSERT INTO nft_items (series_id, number, owner_id) VALUES ($1,$2,$3)", series["id"], number, user["id"])
        await conn.execute("UPDATE nft_series SET sold = sold + 1 WHERE id = $1", series["id"])
        await conn.execute("UPDATE users SET coins = coins - $1 WHERE id = $2", series["price"], user["id"])
    return {"ok": True}

# СООБЩЕНИЯ
@app.post("/api/messages/edit")
async def msg_edit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = data.get("message_id"); text = (data.get("text") or "").strip()
    if not text: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM messages WHERE id = $1", mid)
        if not row or row["user_id"] != user["id"]: raise HTTPException(403, "Не твоё")
        await conn.execute("UPDATE messages SET text = $1, edited = TRUE WHERE id = $2", text, mid)
    await manager.broadcast({"type":"message_edited","message_id":mid,"text":text})
    return {"ok": True}

@app.post("/api/messages/delete")
async def msg_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = data.get("message_id")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT user_id FROM messages WHERE id = $1", mid)
        if not row: raise HTTPException(404, "Не найден")
        if row["user_id"] != user["id"] and not user.get("is_admin"): raise HTTPException(403, "Не твоё")
        await conn.execute("DELETE FROM messages WHERE id = $1", mid)
    await manager.broadcast({"type":"message_deleted","message_id":mid})
    return {"ok": True}

@app.post("/api/messages/reaction")
async def msg_reaction(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = data.get("message_id"); emoji = data.get("emoji")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT reactions FROM messages WHERE id = $1", mid)
        if not row: raise HTTPException(404, "Не найден")
        try: reactions = json.loads(row["reactions"] or "{}")
        except: reactions = {}
        if emoji not in reactions: reactions[emoji] = []
        if user["username"] in reactions[emoji]: reactions[emoji].remove(user["username"])
        else: reactions[emoji].append(user["username"])
        if not reactions[emoji]: del reactions[emoji]
        await conn.execute("UPDATE messages SET reactions = $1 WHERE id = $2", json.dumps(reactions), mid)
    await manager.broadcast({"type":"message_reaction","message_id":mid,"reactions":reactions})
    return {"ok": True, "reactions": reactions}

# СЕРВЕРА
@app.post("/api/servers/create")
async def create_server(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()
    if not name: raise HTTPException(400, "Введи название")
    p = await get_pool()
    async with p.acquire() as conn:
        invite = secrets.token_urlsafe(8)
        row = await conn.fetchrow("INSERT INTO servers (name, owner_id, invite_code) VALUES ($1,$2,$3) RETURNING id, name", name, user["id"], invite)
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2)", row["id"], user["id"])
        await conn.execute("INSERT INTO channels (server_id, name) VALUES ($1,$2)", row["id"], "общий")
    return dict(row)

@app.get("/api/servers/list")
async def list_servers(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id, s.name, s.invite_code, s.avatar
            FROM servers s JOIN server_members sm ON sm.server_id = s.id WHERE sm.user_id = $1""", user["id"])
    return [dict(r) for r in rows]

@app.get("/api/servers/{sid}")
async def get_server(sid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name, invite_code, owner_id FROM servers WHERE id = $1", sid)
    if not row: raise HTTPException(404, "Не найден")
    return dict(row)

@app.post("/api/servers/join")
async def join_server(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    invite = data.get("invite","").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name FROM servers WHERE invite_code = $1", invite)
        if not row: raise HTTPException(404, "Не найдено")
        await conn.execute("INSERT INTO server_members (server_id, user_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", row["id"], user["id"])
    return dict(row)

@app.get("/api/servers/{sid}/members")
async def get_members(sid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, u.is_admin, u.is_moderator,
            u.is_beta_tester, u.is_scam FROM server_members sm JOIN users u ON u.id = sm.user_id
            WHERE sm.server_id = $1""", sid)
    result = []
    for r in rows:
        d = dict(r); d["role"] = get_role(r); d["online"] = d["id"] in online_users; result.append(d)
    return result

@app.get("/api/servers/{sid}/channels")
async def get_channels(sid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id, name, type FROM channels WHERE server_id = $1 ORDER BY id", sid)
    return [dict(r) for r in rows]

@app.post("/api/channels/create")
async def create_channel(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()
    if not name: raise HTTPException(400, "Введи название")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("INSERT INTO channels (server_id, name, type) VALUES ($1,$2,$3) RETURNING id, name, type",
            data.get("server_id"), name, data.get("type","text"))
    return dict(row)

@app.get("/api/channels/{cid}/messages")
async def get_messages(cid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT m.id, m.text, m.file_url, m.created_at, m.reactions,
            u.id AS user_id, u.username, u.avatar, u.is_banned, u.is_beta_tester,
            u.is_admin, u.is_moderator, u.is_scam, u.nickname_color, u.nickname_gradient
            FROM messages m JOIN users u ON u.id = m.user_id
            WHERE m.channel_id = $1 ORDER BY m.id ASC LIMIT 100""", cid)
    result = []
    for r in rows:
        d = dict(r); d["role"] = get_role(r); result.append(d)
    return result

@app.post("/api/upload")
async def upload_file(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    contents = await file.read()
    ext = os.path.splitext(file.filename)[1]
    fname = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f: f.write(contents)
    return {"url": f"/uploads/{fname}"}

# ДРУЗЬЯ
@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id, u.username, u.avatar, u.is_banned, u.is_beta_tester, u.is_scam,
            f.status, f.from_user, f.to_user
            FROM friendships f JOIN users u ON (u.id = f.from_user OR u.id = f.to_user)
            WHERE (f.from_user = $1 OR f.to_user = $1) AND u.id != $1""", user["id"])
    result = []
    for r in rows:
        d = dict(r); d["online"] = d["id"] in online_users; result.append(d)
    return result

@app.post("/api/friends/accept")
async def friend_accept(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE friendships SET status = 'accepted' WHERE from_user = $1 AND to_user = $2", data.get("friend_id"), user["id"])
    return {"ok": True}

@app.post("/api/friends/request_by_id")
async def friend_request_by_id(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = data.get("user_id")
    if tid == user["id"]: raise HTTPException(400, "Это ты")
    p = await get_pool()
    async with p.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM friendships WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], tid)
        if existing: raise HTTPException(400, "Уже есть")
        await conn.execute("INSERT INTO friendships (from_user, to_user) VALUES ($1,$2)", user["id"], tid)
    return {"ok": True}

# ЛС
@app.get("/api/dm/{uid}/messages")
async def get_dm(uid: int, token: str):
    me_u = await get_current_user(token)
    if not me_u: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT d.id, d.text, d.created_at,
            u.id AS user_id, u.username, u.avatar FROM dms d
            JOIN users u ON u.id = d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id ASC LIMIT 100""", me_u["id"], uid)
    return [dict(r) for r in rows]

# ВЕБСОКЕТ
class Manager:
    def __init__(self): self.active = {}
    async def connect(self, uid, ws):
        await ws.accept(); self.active[uid] = ws; online_users.add(uid)
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

manager = Manager()

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token","")
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
                ch = data.get("channel_id"); text = data.get("text",""); temp_id = data.get("temp_id")
                if not text.strip(): continue
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO messages (channel_id, user_id, text) VALUES ($1,$2,$3) RETURNING id, created_at", ch, user["id"], text)
                    await conn.execute("UPDATE users SET messages_count = messages_count + 1 WHERE id = $1", user["id"])
                await manager.broadcast({
                    "type":"message","id":row["id"],"channel_id":ch,"temp_id":temp_id,
                    "user_id":user["id"],"username":user["username"],"avatar":user["avatar"],
                    "is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),
                    "is_beta_tester":user.get("is_beta_tester"),"is_scam":user.get("is_scam"),
                    "role":get_role(user),"nickname_color":user.get("nickname_color"),
                    "nickname_gradient":user.get("nickname_gradient"),
                    "text":text,"created_at":row["created_at"].isoformat()
                })
            elif t == "dm":
                to_user = data.get("to_user"); text = data.get("text",""); temp_id = data.get("temp_id")
                p = await get_pool()
                async with p.acquire() as conn:
                    row = await conn.fetchrow("INSERT INTO dms (from_user, to_user, text) VALUES ($1,$2,$3) RETURNING id, created_at", user["id"], to_user, text)
                payload = {"type":"dm","id":row["id"],"from_user":user["id"],"to_user":to_user,"temp_id":temp_id,
                    "username":user["username"],"avatar":user["avatar"],"role":get_role(user),
                    "text":text,"created_at":row["created_at"].isoformat()}
                await manager.send_to(to_user, payload); await manager.send_to(user["id"], payload)
            elif t == "typing":
                await manager.broadcast({"type":"typing","channel_id":data.get("channel_id"),"username":user["username"]})
            elif t == "typing_dm":
                await manager.send_to(data.get("to_user"), {"type":"typing_dm","from":user["id"],"username":user["username"]})
    except WebSocketDisconnect:
        manager.disconnect(user["id"])

@app.get("/")
async def index():
    return HTMLResponse(open("index.html", encoding="utf-8").read())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))