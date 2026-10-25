import os, json, time, secrets, hashlib, random, datetime, asyncio, re, traceback
import asyncpg, httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ====== НАСТРОЙКИ ======
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://belugacord_user:1VSALM1cow@127.0.0.1/belugacord_zjgh")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs("pages", exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2032")
ADMIN_USERNAME = "_fan_beluga_"
OWNER_PASSWORD = "12344321"
CURRENT_VERSION = "4.3"

TURN_HOST = "189.74.125.21"
TURN_PORT = 3478
TURN_USER = "beluga"
TURN_PASS = "1VSALM1cow"

MAX_TEXT = 10000
ALLOWED_EXT = {'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mp3','.wav','.ogg','.zip','.rar','.7z','.pdf','.txt'}
ALLOWED_MIME = {'image/png','image/jpeg','image/gif','image/webp','video/mp4','video/webm','audio/mpeg','audio/wav','audio/ogg','application/zip','application/pdf','text/plain','application/octet-stream'}

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

# ====== БД ======
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
            bio VARCHAR(256), theme VARCHAR(16) DEFAULT 'dark', created_at TIMESTAMPTZ DEFAULT NOW()
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
        furniture = [("sofa","Диван","🛋️",500),("table","Стол","🪑",300),("bed","Кровать","🛏️",800),
                     ("tv","Телевизор","📺",1500),("plant","Растение","🪴",200),("lamp","Лампа","💡",250)]
        for f in furniture:
            try: await conn.execute("INSERT INTO furniture_catalog(item_id,name,emoji,price) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",*f)
            except: pass
        print("✅ БД 4.3 готова")

# ====== APP ======
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

# ====== ХЕЛПЕРЫ ======
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
            "created_at": _iso(row.get("created_at"))
        }
    except Exception as e:
        print(f"[user_public ERR] {e}")
        return {"id": row.get("id"), "username": row.get("username")}
# ====== АВТОРИЗАЦИЯ ======
@app.post("/api/register")
async def register(data: dict):
    raw_u = (data.get("username") or "").strip().lower()
    raw_d = (data.get("display_name") or raw_u).strip()
    pw = data.get("password") or ""
    
    if len(pw) < 4: raise HTTPException(400, "Пароль мин 4")
    if len(raw_d) < 2 or len(raw_d) > 64: raise HTTPException(400, "Ник 2-64")
    if not re.match(r'^[a-z][a-z0-9_]*$', raw_u): raise HTTPException(400, "Только a-z, 0-9, _")
    
    p = await get_pool()
    async with p.acquire() as conn:
        exists = await conn.fetchrow("SELECT id FROM users WHERE LOWER(username)=LOWER($1)", raw_u)
        if exists: raise HTTPException(400, "Этот username уже занят. Выбери другой.")
        
        row = await conn.fetchrow("""INSERT INTO users(username,display_name,password_hash,is_admin) 
            VALUES($1,$2,$3,$4) RETURNING *""", raw_u, raw_d, hash_password(pw), raw_u == ADMIN_USERNAME)
        
        try: await conn.execute("INSERT INTO user_positions(user_id) VALUES($1)", row["id"])
        except: pass
        
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

@app.post("/api/login")
async def login(data: dict):
    u = (data.get("username") or "").strip().lstrip("@").lower()
    pw = data.get("password") or ""
    if not u or not pw: raise HTTPException(400, "Заполни поля")
    
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username=$1 OR LOWER(display_name)=$2", u, u)
    
    if not row or not verify_password(pw, row["password_hash"]): 
        raise HTTPException(400, "Неверный логин/пароль")
    
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return user_public(user, user["id"])

@app.get("/api/ban_info")
async def ban_info(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {
        "is_banned": bool(user.get("is_banned")),
        "role": user.get("ban_role") or "system",
        "reason": user.get("ban_reason") or "Нарушение правил",
        "date": _iso(user.get("ban_date"))
    }

@app.post("/api/delete_my_account")
async def delete_my_account(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE id=$1", user["id"])
    return {"ok": True}

@app.post("/api/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET 
            display_name=COALESCE($1,display_name), bio=COALESCE($2,bio),
            avatar_pos=COALESCE($3,avatar_pos), banner_pos=COALESCE($4,banner_pos)
            WHERE id=$5""", 
            data.get("display_name"), data.get("bio"), 
            data.get("avatar_pos"), data.get("banner_pos"), user["id"])
    return {"ok": True}

@app.post("/api/upload_avatar")
async def upload_avatar(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Только фото")
    content = await file.read()
    if len(content) > 5*1024*1024: raise HTTPException(400, "Макс 5 МБ")
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    name = f"av_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f: f.write(content)
    url = f"/uploads/{name}"
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET avatar=$1 WHERE id=$2", url, user["id"])
    return {"ok": True, "url": url}

@app.post("/api/upload_banner")
async def upload_banner(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Только фото")
    content = await file.read()
    if len(content) > 10*1024*1024: raise HTTPException(400, "Макс 10 МБ")
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    name = f"bn_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f: f.write(content)
    url = f"/uploads/{name}"
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET banner=$1 WHERE id=$2", url, user["id"])
    return {"ok": True, "url": url}

@app.post("/api/upload")
async def upload_file(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    lim = 30 * 1024 * 1024
    mime = (file.content_type or "application/octet-stream").lower()
    content = await file.read()
    if len(content) > lim: raise HTTPException(400, "Макс 30 МБ")
    ext = os.path.splitext(file.filename or "")[1].lower()[:8]
    name = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f: f.write(content)
    return {"url": f"/uploads/{name}", "size": len(content), "mime": mime, "name": file.filename or name}

# ====== ПОЛЬЗОВАТЕЛИ ======
@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
    if not row: raise HTTPException(404, "Не найден")
    return user_public(row, user_id)

@app.get("/api/users/search")
async def users_search(q: str, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    q = (q or "").strip().lstrip("@")
    if len(q) < 1: return []
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE (username ILIKE $1 OR display_name ILIKE $1) AND id!=$2 ORDER BY username LIMIT 25", f"%{q}%", user["id"])
    return [user_public(r, user["id"]) for r in rows]

# ====== ДРУЗЬЯ ======
@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    uid = user["id"]
    p = await get_pool()
    async with p.acquire() as conn:
        result = []
        frows = await conn.fetch("SELECT CASE WHEN user_a=$1 THEN user_b ELSE user_a END AS oid FROM friends WHERE user_a=$1 OR user_b=$1", uid)
        for r in frows:
            o = await conn.fetchrow("SELECT * FROM users WHERE id=$1", r["oid"])
            if o:
                item = user_public(o, uid)
                item["status"] = "accepted"
                result.append(item)
        inc = await conn.fetch("SELECT id AS rid, from_user AS oid FROM friend_requests WHERE to_user=$1", uid)
        for r in inc:
            o = await conn.fetchrow("SELECT * FROM users WHERE id=$1", r["oid"])
            if o:
                item = user_public(o, uid)
                item["status"] = "incoming"
                item["request_id"] = r["rid"]
                result.append(item)
        out = await conn.fetch("SELECT id AS rid, to_user AS oid FROM friend_requests WHERE from_user=$1", uid)
        for r in out:
            o = await conn.fetchrow("SELECT * FROM users WHERE id=$1", r["oid"])
            if o:
                item = user_public(o, uid)
                item["status"] = "outgoing"
                item["request_id"] = r["rid"]
                result.append(item)
    return result

@app.post("/api/friends/request")
async def friends_request(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id", 0))
    if not tid or tid == user["id"]: raise HTTPException(400, "Неверный user_id")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM friends WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], tid): 
            raise HTTPException(400, "Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], tid): 
            raise HTTPException(400, "Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)", user["id"], tid)
    return {"ok": True}

@app.post("/api/friends/accept")
async def friends_accept(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT from_user,to_user FROM friend_requests WHERE id=$1", rid)
        if not r: raise HTTPException(404, "Не найдено")
        if r["to_user"] != user["id"]: raise HTTPException(403, "Не твоя заявка")
        a, b = sorted([r["from_user"], r["to_user"]])
        await conn.execute("INSERT INTO friends(user_a,user_b) VALUES($1,$2) ON CONFLICT DO NOTHING", a, b)
        await conn.execute("DELETE FROM friend_requests WHERE id=$1", rid)
    return {"ok": True}

@app.post("/api/friends/decline")
async def friends_decline(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND to_user=$2", rid, user["id"])
    return {"ok": True}

@app.post("/api/friends/cancel")
async def friends_cancel(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND from_user=$2", rid, user["id"])
    return {"ok": True}

# ====== КАНАЛЫ ======
@app.get("/api/check_channel_username")
async def check_channel_username(u: str, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    u = (u or "").lower().strip()
    if len(u) < 4: return {"available": False, "reason": "Минимум 4 символа"}
    if len(u) > 32: return {"available": False, "reason": "Максимум 32 символа"}
    if not re.match(r'^[a-z][a-z0-9_]*$', u): return {"available": False, "reason": "Только a-z, 0-9, _"}
    p = await get_pool()
    async with p.acquire() as conn:
        u1 = await conn.fetchval("SELECT 1 FROM users WHERE LOWER(username)=$1", u)
        if u1: return {"available": False, "reason": "Занято пользователем"}
        u2 = await conn.fetchval("SELECT 1 FROM channels WHERE LOWER(username)=$1", u)
        if u2: return {"available": False, "reason": "Занято каналом"}
    return {"available": True, "reason": "Свободен"}

@app.get("/api/channels/my")
async def channels_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM channels WHERE owner_id=$1 ORDER BY id DESC", user["id"])
    return [{"id": r["id"], "username": r["username"], "name": r["name"], "bio": r["bio"], "avatar": r["avatar"], "subscribers_count": r["subscribers_count"], "is_owner": True} for r in rows]

@app.post("/api/channels/create")
async def channels_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя")
    uname = (data.get("username") or "").strip().lower()
    p = await get_pool()
    async with p.acquire() as conn:
        if uname:
            if len(uname) < 4: raise HTTPException(400, "Username мин 4")
            if not re.match(r'^[a-z][a-z0-9_]*$', uname): raise HTTPException(400, "Только a-z, 0-9, _")
            if await conn.fetchval("SELECT 1 FROM users WHERE LOWER(username)=$1", uname):
                raise HTTPException(400, "Username занят пользователем")
            if await conn.fetchval("SELECT 1 FROM channels WHERE LOWER(username)=$1", uname):
                raise HTTPException(400, "Username занят каналом")
        c = await conn.fetchrow("""INSERT INTO channels(username,name,bio,avatar,owner_id,is_private) 
            VALUES($1,$2,$3,$4,$5,$6) RETURNING *""",
            uname or None, name, (data.get("bio") or "")[:256], data.get("avatar"), user["id"], bool(data.get("is_private", False)))
        await conn.execute("INSERT INTO channel_admins(channel_id,user_id) VALUES($1,$2)", c["id"], user["id"])
    return {"id": c["id"], "username": c["username"], "name": c["name"]}

@app.get("/api/channels/{cid}")
async def channel_get(cid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not c: raise HTTPException(404, "Нет канала")
        is_adm = await conn.fetchval("SELECT 1 FROM channel_admins WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
    return {"id": c["id"], "username": c["username"], "name": c["name"], "bio": c["bio"], "avatar": c["avatar"], "subscribers_count": c["subscribers_count"], "is_owner": c["owner_id"] == user["id"], "is_admin": bool(is_adm)}

@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int, token: str, limit: int = 50):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM channel_posts WHERE channel_id=$1 ORDER BY id DESC LIMIT $2", cid, limit)
    return [{"id": r["id"], "text": r["text"], "media_urls": _safe_json(r["media_urls"], []), "media_kind": r["media_kind"], "views": r["views"], "created_at": _iso(r["created_at"])} for r in rows]

@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        adm = await conn.fetchrow("SELECT 1 FROM channel_admins WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
        if not adm: raise HTTPException(403, "Не админ канала")
        text = (data.get("text") or "")[:MAX_TEXT]
        media = data.get("media_urls") or []
        kind = (data.get("media_kind") or "text")[:16]
        if not text and not media: raise HTTPException(400, "Пусто")
        r = await conn.fetchrow("""INSERT INTO channel_posts(channel_id,author_id,text,media_urls,media_kind)
            VALUES($1,$2,$3,$4,$5) RETURNING *""", cid, user["id"], text, json.dumps(media), kind)
    return {"ok": True, "post_id": r["id"]}
# ====== УЛИЦА ======
@app.get("/api/street/users")
async def street_users(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT up.user_id, up.x, up.y, u.username, u.display_name, u.avatar 
            FROM user_positions up JOIN users u ON u.id=up.user_id WHERE up.location='street'""")
    return [{"user_id": r["user_id"], "x": r["x"], "y": r["y"], "username": r["username"], "display_name": r["display_name"], "avatar": r["avatar"]} for r in rows]

@app.post("/api/street/move")
async def street_move(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    x = max(0, min(100, float(data.get("x", 50))))
    y = max(0, min(100, float(data.get("y", 50))))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO user_positions(user_id,x,y,location,updated_at) VALUES($1,$2,$3,'street',NOW())
            ON CONFLICT(user_id) DO UPDATE SET x=$2,y=$3,location='street',updated_at=NOW()""", user["id"], x, y)
    await manager.broadcast({"type": "street_move", "user_id": user["id"], "x": x, "y": y}, exclude=user["id"])
    return {"ok": True}

# ====== ДОМ ======
@app.get("/api/house/my")
async def house_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        h = await conn.fetchrow("SELECT * FROM houses WHERE owner_id=$1", user["id"])
        if not h:
            h = await conn.fetchrow("INSERT INTO houses(owner_id,name) VALUES($1,'Мой дом') RETURNING *", user["id"])
        items = await conn.fetch("SELECT * FROM house_items WHERE house_id=$1", h["id"])
    return {"id": h["id"], "name": h["name"], "items": [{"id": i["id"], "item_id": i["item_id"], "x": i["x"], "y": i["y"]} for i in items]}

@app.get("/api/house/catalog")
async def house_catalog():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM furniture_catalog")
    return [{"item_id": r["item_id"], "name": r["name"], "emoji": r["emoji"], "price": r["price"]} for r in rows]

@app.post("/api/house/place")
async def house_place(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    iid = int(data.get("item_row_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        h = await conn.fetchrow("SELECT id FROM houses WHERE owner_id=$1", user["id"])
        if not h: raise HTTPException(404, "Нет дома")
        await conn.execute("UPDATE house_items SET x=$1,y=$2 WHERE id=$3 AND house_id=$4", 
            float(data.get("x", 50)), float(data.get("y", 50)), iid, h["id"])
    return {"ok": True}

# ====== АДМИНКА ======
@app.post("/api/owner/verify")
async def owner_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    if (data.get("password") or "") != OWNER_PASSWORD: raise HTTPException(403, "Неверный пароль")
    return {"ok": True}

@app.get("/api/owner/stats")
async def owner_stats(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM users")
        c = await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        m = await conn.fetchval("SELECT COUNT(*) FROM dms")
        ch = await conn.fetchval("SELECT COUNT(*) FROM channels")
    return {"users": u, "online": len(online_users), "coins": c, "messages": m, "channels": ch, "groups": 0}

@app.get("/api/admin/users")
async def admin_users(token: str, limit: int = 500):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id,username,display_name,is_admin,is_banned,coins,level FROM users ORDER BY id LIMIT $1", limit)
    return {"users": [dict(r) for r in rows]}

@app.post("/api/admin/action")
async def admin_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    tid = int(data.get("target_id", 0))
    action = data.get("action")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            await conn.execute("UPDATE users SET is_banned=TRUE, ban_reason=$1, ban_role='owner', ban_date=NOW() WHERE id=$2", (data.get("reason") or "")[:256], tid)
        elif action == "unban":
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1", tid)
    return {"ok": True}

@app.post("/api/owner/give_coins")
async def give_coins(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    tid = int(data.get("user_id", 0))
    amt = int(data.get("amount", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", amt, tid)
    return {"ok": True}

# ====== TURN CONFIG ======
@app.get("/api/webrtc/config")
async def webrtc_config():
    return {
        "iceServers": [
            {"urls": "stun:stun.l.google.com:19302"},
            {"urls": f"turn:{TURN_HOST}:{TURN_PORT}", "username": TURN_USER, "credential": TURN_PASS}
        ]
    }

# ====== WEBSOCKET ======
class ConnectionManager:
    def __init__(self): self.connections = {}
    async def connect(self, uid, ws):
        await ws.accept()
        self.connections.setdefault(uid, []).append(ws)
        online_users.add(uid)
    def disconnect(self, uid, ws):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except: pass
            if not self.connections[uid]:
                del self.connections[uid]
                online_users.discard(uid)
    async def send_to(self, uid, data):
        for ws in list(self.connections.get(uid, [])):
            try: await ws.send_json(data)
            except: self.disconnect(uid, ws)
    async def broadcast(self, data, exclude=None):
        for uid, conns in list(self.connections.items()):
            if exclude and uid == exclude: continue
            for ws in list(conns):
                try: await ws.send_json(data)
                except: self.disconnect(uid, ws)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str):
    user = await get_current_user(token)
    if not user: await ws.close(); return
    if user.get("is_banned"): await ws.close(); return
    
    uid = user["id"]
    await manager.connect(uid, ws)
    active_calls = {}
    
    try: await ws.send_json({"type": "online_list", "users": list(online_users)})
    except: pass
    await manager.broadcast({"type": "user_online", "user_id": uid}, exclude=uid)

    try:
        while True:
            raw = await ws.receive_text()
            try: data = json.loads(raw)
            except: continue
            t = data.get("type")
            if t == "ping":
                try: await ws.send_json({"type": "pong"})
                except: pass
                continue

            if t == "dm":
                to_id = int(data.get("to_user", 0))
                text = (data.get("text") or "")[:MAX_TEXT]
                furl = data.get("file_url")
                kind = data.get("msg_kind", "text")
                fsize = int(data.get("file_size", 0))
                tid = data.get("temp_id")
                if not to_id: continue
                p = await get_pool()
                async with p.acquire() as conn:
                    msg = await conn.fetchrow("""INSERT INTO dms(from_user,to_user,text,file_url,file_size,msg_kind) 
                        VALUES($1,$2,$3,$4,$5,$6) RETURNING *""", uid, to_id, text, furl, fsize, kind)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1", uid)
                dn = user.get("display_name") or user["username"]
                payload = {"type": "dm", "id": msg["id"], "from_user": uid, "to_user": to_id, "username": user["username"], "display_name": dn, "avatar": user.get("avatar"), "text": text, "file_url": furl, "file_size": fsize, "msg_kind": kind, "created_at": _iso(msg["created_at"]), "temp_id": tid}
                await manager.send_to(to_id, payload)
                await manager.send_to(uid, payload)

            elif t == "street_move":
                x = max(0, min(100, float(data.get("x", 50))))
                y = max(0, min(100, float(data.get("y", 50))))
                await manager.broadcast({"type": "street_move", "user_id": uid, "x": x, "y": y}, exclude=uid)

            elif t == "call_invite":
                to_id = int(data.get("to_user", 0))
                ctype = data.get("call_type", "audio")
                if not to_id: continue
                call_id = secrets.token_hex(8)
                active_calls[call_id] = {"caller": uid, "callee": to_id, "type": ctype}
                dn = user.get("display_name") or user["username"]
                await manager.send_to(to_id, {"type": "call_incoming", "call_id": call_id, "from_user": uid, "from_name": dn, "from_avatar": user.get("avatar"), "call_type": ctype})
                await manager.send_to(uid, {"type": "call_ringing", "call_id": call_id})

            elif t == "call_accept":
                cid = data.get("call_id")
                if cid in active_calls:
                    await manager.send_to(active_calls[cid]["caller"], {"type": "call_accepted", "call_id": cid})

            elif t == "call_reject":
                cid = data.get("call_id")
                if cid in active_calls:
                    await manager.send_to(active_calls[cid]["caller"], {"type": "call_rejected", "call_id": cid})
                    del active_calls[cid]

            elif t == "call_end":
                cid = data.get("call_id")
                if cid in active_calls:
                    c = active_calls[cid]
                    other = c["callee"] if c["caller"] == uid else c["caller"]
                    await manager.send_to(other, {"type": "call_ended", "call_id": cid})
                    del active_calls[cid]

            elif t in ("webrtc_offer", "webrtc_answer", "webrtc_ice"):
                to_id = int(data.get("to_user", 0))
                if not to_id: continue
                payload = {"type": t, "from_user": uid, "call_id": data.get("call_id")}
                if t == "webrtc_offer": payload["sdp"] = data.get("sdp")
                elif t == "webrtc_answer": payload["sdp"] = data.get("sdp")
                else: payload["candidate"] = data.get("candidate")
                await manager.send_to(to_id, payload)

    except WebSocketDisconnect: pass
    except Exception as e: print(f"[WS ERR] {e}")
    finally:
        manager.disconnect(uid, ws)
        await manager.broadcast({"type": "user_offline", "user_id": uid})

# ====== РАЗДАЧА СТРАНИЦ ======
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

@app.get("/sw.js")
async def sw(): return FileResponse("sw.js", media_type="application/javascript")

@app.get("/manifest.json")
async def manifest(): return FileResponse("manifest.json")

@app.post("/api/channels/{cid}/edit")
async def channel_edit(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not c: raise HTTPException(404, "Нет канала")
        if c["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        
        new_username = data.get("username")
        if new_username:
            new_username = new_username.lower().strip()
            if len(new_username) < 4: raise HTTPException(400, "Username мин 4")
            if not re.match(r'^[a-z][a-z0-9_]*$', new_username): raise HTTPException(400, "Только a-z, 0-9, _")
            if await conn.fetchval("SELECT 1 FROM users WHERE LOWER(username)=$1", new_username):
                raise HTTPException(400, "Username занят пользователем")
            if await conn.fetchval("SELECT 1 FROM channels WHERE LOWER(username)=$1 AND id!=$2", new_username, cid):
                raise HTTPException(400, "Username занят каналом")
        
        await conn.execute("""UPDATE channels SET 
            name=COALESCE($1,name), bio=COALESCE($2,bio), username=COALESCE($3,username)
            WHERE id=$4""", 
            data.get("name"), data.get("bio"), new_username, cid)
    return {"ok": True}

@app.post("/api/channels/{cid}/upload_avatar")
async def channel_upload_avatar(cid: int, token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not c or c["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Только фото")
    content = await file.read()
    if len(content) > 5*1024*1024: raise HTTPException(400, "Макс 5 МБ")
    ext = os.path.splitext(file.filename or "")[1].lower() or ".png"
    name = f"ch_av_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f: f.write(content)
    url = f"/uploads/{name}"
    async with p.acquire() as conn:
        await conn.execute("UPDATE channels SET avatar=$1 WHERE id=$2", url, cid)
    return {"ok": True, "url": url}

@app.post("/api/channels/{cid}/delete")
async def channel_delete(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not c or c["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        await conn.execute("DELETE FROM channels WHERE id=$1", cid)
    return {"ok": True}

# ====== МУЗЫКА ======
@app.get("/api/music/list")
async def music_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM music WHERE user_id=$1 ORDER BY id DESC LIMIT 20", user["id"])
    return [{"id": r["id"], "title": r["title"], "artist": r["artist"], "url": r["url"]} for r in rows]

@app.post("/api/music/upload")
async def music_upload(token: str = Form(...), file: UploadFile = File(...), title: str = Form(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(400, "Только аудио")
    content = await file.read()
    if len(content) > 20*1024*1024: raise HTTPException(400, "Макс 20 МБ")
    ext = os.path.splitext(file.filename or "")[1].lower() or ".mp3"
    name = f"music_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f: f.write(content)
    url = f"/uploads/{name}"
    
    p = await get_pool()
    async with p.acquire() as conn:
        # Проверяем лимит треков
        cnt = await conn.fetchval("SELECT COUNT(*) FROM music WHERE user_id=$1", user["id"])
        if cnt >= 20: raise HTTPException(400, "Макс 20 треков")
        await conn.execute("INSERT INTO music(user_id, title, url) VALUES($1,$2,$3)", user["id"], title, url)
    return {"url": url, "title": title}

# ====== СТЕНА ======
@app.get("/api/wall/{uid}")
async def wall_list(uid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    target = uid if uid > 0 else user["id"]
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT pw.*, u.username, u.display_name 
            FROM profile_wall pw JOIN users u ON u.id=pw.author 
            WHERE pw.profile_user=$1 ORDER BY pw.id DESC LIMIT 100""", target)
    return [{"id": r["id"], "text": r["text"], "username": r["username"], "display_name": r["display_name"], "created_at": _iso(r["created_at"])} for r in rows]

@app.post("/api/wall/{uid}/post")
async def wall_post(uid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    target = uid if uid > 0 else user["id"]
    text = (data.get("text") or "").strip()[:1000]
    if not text: raise HTTPException(400, "Текст")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO profile_wall(profile_user,author,text) VALUES($1,$2,$3)", target, user["id"], text)
    return {"ok": True}

# ====== ЗАПУСК ======
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 BelugaCord 4.3 запущен на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, ws="websockets", proxy_headers=True, forwarded_allow_ips="*")
