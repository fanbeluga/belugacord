import os, json, time, secrets, hashlib, random, datetime, asyncio, re, traceback
import asyncpg, httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://belugacord_user:1VSALM1cow@127.0.0.1/belugacord_zjgh")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("pages", exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2032")
ADMIN_USERNAME = "_fan_beluga_"
OWNER_PASSWORD = "12344321"
CURRENT_VERSION = "4.5"
TURN_HOST = "189.74.125.21"
TURN_PORT = 3478
TURN_USER = "beluga"
TURN_PASS = "1VSALM1cow"
MAX_TEXT = 10000

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
def _iso(dt):
    if not dt: return None
    try: return dt.isoformat()
    except: return str(dt)
def _safe_json(v, default=None):
    if default is None: default = {}
    try:
        if isinstance(v, str): return json.loads(v)
        return v
    except: return default

pool = None
async def get_pool():
    global pool
    if pool is None: pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL, display_name VARCHAR(64),
            password_hash VARCHAR(128) NOT NULL, avatar TEXT, banner TEXT, gif_avatar TEXT,
            avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%',
            is_admin BOOLEAN DEFAULT FALSE, is_banned BOOLEAN DEFAULT FALSE, ban_reason VARCHAR(256),
            ban_role VARCHAR(16), ban_date TIMESTAMPTZ, coins INTEGER DEFAULT 0, candy INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, messages_count INTEGER DEFAULT 0,
            bio VARCHAR(256), theme VARCHAR(16) DEFAULT 'dark', profile_bg VARCHAR(32) DEFAULT 'none',
            owned_bgs TEXT DEFAULT '["none"]', created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friends(
            id SERIAL PRIMARY KEY, user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,
            user_b INTEGER REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(user_a, user_b)
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE, text TEXT, file_url TEXT,
            file_size BIGINT DEFAULT 0, msg_kind VARCHAR(16) DEFAULT 'text', created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(
            id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE, name VARCHAR(64) NOT NULL,
            bio VARCHAR(256), avatar TEXT, owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            is_private BOOLEAN DEFAULT FALSE, subscribers_count INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_admins(
            channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY(channel_id, user_id)
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_posts(
            id SERIAL PRIMARY KEY, channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, text TEXT,
            media_urls TEXT DEFAULT '[]', media_kind VARCHAR(16) DEFAULT 'text',
            views INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_positions(
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            x REAL DEFAULT 50, y REAL DEFAULT 50, location VARCHAR(32) DEFAULT 'street',
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS houses(
            id SERIAL PRIMARY KEY, owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(64) DEFAULT 'Мой дом', created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS house_items(
            id SERIAL PRIMARY KEY, house_id INTEGER REFERENCES houses(id) ON DELETE CASCADE,
            item_id VARCHAR(32), x REAL DEFAULT 50, y REAL DEFAULT 50, created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS furniture_catalog(
            id SERIAL PRIMARY KEY, item_id VARCHAR(32) UNIQUE, name VARCHAR(64),
            emoji VARCHAR(8), price INTEGER DEFAULT 0
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS music(
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(256), artist VARCHAR(128), url TEXT, created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS profile_wall(
            id SERIAL PRIMARY KEY, profile_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            author INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS promo_activations(
            id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            promo_code VARCHAR(32), reward INTEGER DEFAULT 0, activated_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        
        furniture = [("sofa","Диван","🛋️",500),("table","Стол","🪑",300),("bed","Кровать","🛏️",800),
                     ("tv","Телевизор","📺",1500),("plant","Растение","🪴",200),("lamp","Лампа","💡",250)]
        for f in furniture:
            try: await conn.execute("INSERT INTO furniture_catalog(item_id,name,emoji,price) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",*f)
            except: pass
        print("✅ БД готова")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/pages", StaticFiles(directory="pages"), name="pages")
online_users = set()
manager_ref = None

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e: print(f"❌ DB INIT: {e}")

async def get_current_user(token: str):
    parsed = parse_token(token)
    if not parsed: return None
    uid, _ = parsed
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
        return dict(row) if row else None

def user_public(row, viewer_id=None):
    if row is None: return {}
    if not isinstance(row, dict): row = dict(row)
    try:
        return {
            "id": row["id"], "username": row["username"],
            "display_name": row.get("display_name") or row["username"],
            "avatar": row.get("avatar"), "banner": row.get("banner"),
            "gif_avatar": row.get("gif_avatar"), "avatar_pos": row.get("avatar_pos") or "50% 50%",
            "banner_pos": row.get("banner_pos") or "50% 50%",
            "is_admin": bool(row.get("is_admin")), "is_banned": bool(row.get("is_banned")),
            "coins": row.get("coins", 0), "candy": row.get("candy", 0),
            "level": row.get("level", 1), "xp": row.get("xp", 0),
            "messages_count": row.get("messages_count", 0),
            "bio": row.get("bio"), "theme": row.get("theme") or "dark",
            "profile_bg": row.get("profile_bg") or "none",
            "owned_bgs": _safe_json(row.get("owned_bgs"), ["none"]),
            "created_at": _iso(row.get("created_at"))
        }
    except Exception as e:
        print(f"[user_public ERR] {e}")
        return {"id": row.get("id"), "username": row.get("username")}

# ... (ОСТАЛЬНЫЕ РОУТЫ ИЗ ПРЕДЫДУЩЕГО server.py) ...
# ВСТАВЬ СЮДА ВСЕ РОУТЫ (АВТОРИЗАЦИЯ, ДРУЗЬЯ, КАНАЛЫ, УЛИЦА, ДОМ, МУЗЫКА, СТЕНА, АДМИНКА, WEBSOCKET)

@app.get("/")
async def index(): return FileResponse("index.html")
@app.get("/login")
async def login_page(): return FileResponse("login.html")
@app.get("/reg")
async def reg_page(): return FileResponse("reg.html")
@app.get("/app")
async def app_page(): return FileResponse("app.html")
@app.get("/banned")
async def banned_page(): return FileResponse("pages/banned.html")
@app.get("/admin")
async def admin_page(): return FileResponse("admin.html")
@app.get("/app/{path:path}")
async def app_spa(path: str): return FileResponse("app.html")
@app.get("/app.js")
async def serve_app_js(): return FileResponse("app.js", media_type="application/javascript")
@app.get("/app.css")
async def serve_app_css(): return FileResponse("app.css", media_type="text/css")
@app.get("/sw.js")
async def sw(): return FileResponse("sw.js", media_type="application/javascript")
@app.get("/manifest.json")
async def manifest(): return FileResponse("manifest.json")

@app.get("/login")
async def login_page(): return FileResponse("login.html")

@app.get("/reg")
async def reg_page(): return FileResponse("reg.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 BelugaCord 4.5 запущен на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, ws="websockets", proxy_headers=True, forwarded_allow_ips="*")