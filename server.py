import os, json, time, secrets, hashlib, random, datetime, asyncio, re, traceback, base64
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2032")
ADMIN_USERNAME = "_fan_beluga_"
ADMIN_DISPLAY = "👑 Владелец"
OWNER_PASSWORD = "12344321"
CURRENT_VERSION = "3.7"
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

def sanitize_username(u):
    u = re.sub(r'[^a-zA-Z0-9_]', '_', str(u).lower())
    if not u: u = "user"
    if len(u) > 24: u = u[:24]
    if u[0].isdigit(): u = "_" + u
    return u

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
online_users = set()
active_calls = {}

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY, username VARCHAR(64) UNIQUE NOT NULL, display_name VARCHAR(64),
            password_hash VARCHAR(128) NOT NULL, avatar TEXT, banner TEXT, gif_avatar TEXT, gif_banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%',
            is_admin BOOLEAN DEFAULT FALSE, is_moderator BOOLEAN DEFAULT FALSE,
            is_scam BOOLEAN DEFAULT FALSE, is_banned BOOLEAN DEFAULT FALSE, ban_reason VARCHAR(256), mute_until TIMESTAMPTZ,
            premium_tier VARCHAR(8), premium_expires TIMESTAMPTZ,
            online_status VARCHAR(16) DEFAULT 'online', custom_status VARCHAR(128), bio VARCHAR(256),
            coins INTEGER DEFAULT 0, messages_count INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]', active_frame VARCHAR(32), frame_owned TEXT DEFAULT '[]',
            title VARCHAR(64), title_owned TEXT DEFAULT '[]', level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0,
            candy INTEGER DEFAULT 0, scam_perms TEXT DEFAULT '{}',
            airplane_mode BOOLEAN DEFAULT FALSE, notif_enabled BOOLEAN DEFAULT TRUE, sound_enabled BOOLEAN DEFAULT TRUE,
            theme VARCHAR(16) DEFAULT 'dark', font_size VARCHAR(8) DEFAULT 'md', rank_id INTEGER,
            double_xp_until TIMESTAMPTZ, nick_gradient VARCHAR(64), status_emoji VARCHAR(8), bio_bg TEXT,
            hide_typing BOOLEAN DEFAULT FALSE,
            last_seen TIMESTAMPTZ DEFAULT NOW(), created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY, user_a INTEGER REFERENCES users(id) ON DELETE CASCADE, user_b INTEGER REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(user_a, user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE, to_user INTEGER REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_blocks(id SERIAL PRIMARY KEY, blocker INTEGER REFERENCES users(id) ON DELETE CASCADE, blocked INTEGER REFERENCES users(id) ON DELETE CASCADE, chat_cleared BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(blocker, blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE, name VARCHAR(64) NOT NULL, avatar TEXT, banner TEXT, avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%', description VARCHAR(256), owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE, invite_code VARCHAR(16) UNIQUE, last_message_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, is_admin BOOLEAN DEFAULT FALSE, joined_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(group_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, text TEXT, file_url TEXT, file_size BIGINT DEFAULT 0, msg_kind VARCHAR(16) DEFAULT 'text', voice_duration INTEGER DEFAULT 0, reply_to_id INTEGER, edited_at TIMESTAMPTZ, reactions TEXT DEFAULT '{}', pinned BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE, to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, file_url TEXT, file_size BIGINT DEFAULT 0, msg_kind VARCHAR(16) DEFAULT 'text', voice_duration INTEGER DEFAULT 0,
            read_at TIMESTAMPTZ, forwarded_from VARCHAR(64), pinned BOOLEAN DEFAULT FALSE, starred TEXT DEFAULT '[]',
            reply_to_id INTEGER, edited_at TIMESTAMPTZ, reactions TEXT DEFAULT '{}', deleted_for_all BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE, name VARCHAR(64) NOT NULL, bio VARCHAR(256), avatar TEXT, banner TEXT, avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%', owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE, is_private BOOLEAN DEFAULT FALSE, category VARCHAR(32), subscribers_count INTEGER DEFAULT 0, username_changed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_admins(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, perms TEXT DEFAULT '{"post":true}', added_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(channel_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_subscribers(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, muted_until TIMESTAMPTZ, subscribed_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(channel_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_posts(id SERIAL PRIMARY KEY, channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE, author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, text TEXT, media_urls TEXT DEFAULT '[]', media_kind VARCHAR(16) DEFAULT 'text', reactions TEXT DEFAULT '{}', pinned BOOLEAN DEFAULT FALSE, views INTEGER DEFAULT 0, edited BOOLEAN DEFAULT FALSE, comments_count INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ranks(id SERIAL PRIMARY KEY, name VARCHAR(64) NOT NULL, emoji VARCHAR(8) DEFAULT '🏆', color VARCHAR(32) DEFAULT '#d946ef', priority INTEGER DEFAULT 10, perms TEXT DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS referrals(id SERIAL PRIMARY KEY, code VARCHAR(16) UNIQUE NOT NULL, owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE, clicks INTEGER DEFAULT 0, registrations INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""")
        
        await conn.execute("UPDATE users SET display_name=username WHERE display_name IS NULL")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1", ADMIN_USERNAME)
        await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2", ADMIN_DISPLAY, ADMIN_USERNAME)
        
        cnt = await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if cnt == 0:
            try:
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","👑 Владелец","👑","#ffd700",1000,json.dumps({"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🛡️ Администратор","🛡️","#d946ef",500,json.dumps({"admin_panel":True,"manage_users":True,"give_coins":True,"ban":True,"mute":True,"delete_msgs":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🔨 Модератор","🔨","#22c55e",100,json.dumps({"mute":True,"delete_msgs":True}))
            except: pass
        print("✅ БД 3.7 готова")
# ============ ПОЛЬЗОВАТЕЛИ ============
async def get_current_user(token):
    parsed = parse_token(token)
    if not parsed: return None
    uid, _ = parsed
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
        return dict(row) if row else None

def user_public(row, viewer_id=None):
    if row is None: return {}
    return {
        "id": row["id"], "username": row["username"], "display_name": row.get("display_name") or row["username"],
        "avatar": row.get("avatar"), "banner": row.get("banner"), "gif_avatar": row.get("gif_avatar"),
        "avatar_pos": row.get("avatar_pos"), "banner_pos": row.get("banner_pos"),
        "is_admin": bool(row.get("is_admin")), "is_moderator": bool(row.get("is_moderator")),
        "is_scam": bool(row.get("is_scam")), "premium_tier": row.get("premium_tier"),
        "coins": row.get("coins", 0), "candy": row.get("candy", 0), "level": row.get("level", 1), "xp": row.get("xp", 0),
        "online_status": row.get("online_status", "online"), "custom_status": row.get("custom_status"),
        "bio": row.get("bio"), "title": row.get("title"), "active_frame": row.get("active_frame"),
        "role": "owner" if row.get("username") == ADMIN_USERNAME else ("admin" if row.get("is_admin") else "user"),
        "online": row["id"] in online_users
    }

@app.post("/api/register")
async def register(data: dict):
    raw_u = (data.get("username") or "").strip().lower()
    raw_d = (data.get("display_name") or raw_u).strip()
    pw = data.get("password") or ""
    ref_code = (data.get("ref_code") or "").strip()
    
    if not raw_u: raise HTTPException(400, "Логин обязателен")
    raw_u = sanitize_username(raw_u)
    if len(pw) < 4: raise HTTPException(400, "Пароль мин 4")
    
    p = await get_pool()
    async with p.acquire() as conn:
        exists = await conn.fetchrow("SELECT id FROM users WHERE username=$1", raw_u)
        if exists: raise HTTPException(400, "Занято")
        
        row = await conn.fetchrow("INSERT INTO users(username,display_name,password_hash,is_admin) VALUES($1,$2,$3,$4) RETURNING *", raw_u, raw_d, hash_password(pw), raw_u == ADMIN_USERNAME)
        
        if ref_code:
            try:
                ref = await conn.fetchrow("SELECT owner_id FROM referrals WHERE code=$1", ref_code)
                if ref:
                    await conn.execute("UPDATE users SET coins=coins+20000 WHERE id=$1", ref["owner_id"])
                    await conn.execute("UPDATE users SET coins=coins+500 WHERE id=$1", row["id"])
                    await conn.execute("UPDATE referrals SET registrations=registrations+1 WHERE code=$1", ref_code)
                    await manager.send_to(ref["owner_id"], {"type": "referral_bonus", "amount": 20000, "new_username": raw_u})
            except Exception as e: print(f"[referral] {e}")

    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

@app.post("/api/login")
async def login(data: dict):
    u = (data.get("username") or "").strip().lstrip("@").lower()
    pw = data.get("password") or ""
    if not u or not pw: raise HTTPException(400, "Заполни поля")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username=$1 OR LOWER(display_name)=$2", u, u)
    if not row or not verify_password(pw, row["password_hash"]): raise HTTPException(400, "Неверный логин/пароль")
    if row["is_banned"]: raise HTTPException(403, "Забанен")
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return user_public(user, user["id"])

# ============ BASE64 ЗАГРУЗКА ============
@app.post("/api/upload_avatar")
async def upload_avatar(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Только картинка")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024: raise HTTPException(400, "Макс 5 МБ")
    
    mime = (file.content_type or "image/png").lower()
    b64 = base64.b64encode(content).decode('utf-8')
    url = f"data:{mime};base64,{b64}"
    
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET avatar=$1 WHERE id=$2", url, user["id"])
    return {"ok": True, "url": url}

@app.post("/api/upload_banner")
async def upload_banner(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400, "Только картинка")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024: raise HTTPException(400, "Макс 5 МБ")
    
    mime = (file.content_type or "image/png").lower()
    b64 = base64.b64encode(content).decode('utf-8')
    url = f"data:{mime};base64,{b64}"
    
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET banner=$1 WHERE id=$2", url, user["id"])
    return {"ok": True, "url": url}

@app.post("/api/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    
    p = await get_pool()
    async with p.acquire() as conn:
        if data.get("display_name"): await conn.execute("UPDATE users SET display_name=$1 WHERE id=$2", data["display_name"][:64], user["id"])
        if data.get("bio") is not None: await conn.execute("UPDATE users SET bio=$1 WHERE id=$2", data["bio"][:128], user["id"])
        if data.get("avatar_pos"): await conn.execute("UPDATE users SET avatar_pos=$1 WHERE id=$2", data["avatar_pos"], user["id"])
        if data.get("banner_pos"): await conn.execute("UPDATE users SET banner_pos=$1 WHERE id=$2", data["banner_pos"], user["id"])
    return {"ok": True}

# ============ ДРУЗЬЯ ============
@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    uid = user["id"]
    p = await get_pool()
    async with p.acquire() as conn:
        result = []
        # Друзья
        frows = await conn.fetch("SELECT CASE WHEN user_a=$1 THEN user_b ELSE user_a END AS oid FROM friendships WHERE user_a=$1 OR user_b=$1", uid)
        for r in frows:
            o = await conn.fetchrow("SELECT * FROM users WHERE id=$1", r["oid"])
            if o:
                item = user_public(o, uid)
                item["status"] = "accepted"
                result.append(item)
        # Входящие
        inc = await conn.fetch("SELECT id AS rid, from_user AS oid FROM friend_requests WHERE to_user=$1", uid)
        for r in inc:
            o = await conn.fetchrow("SELECT * FROM users WHERE id=$1", r["oid"])
            if o:
                item = user_public(o, uid)
                item["status"] = "incoming"
                item["request_id"] = r["rid"]
                result.append(item)
        # Исходящие
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
    if not tid or tid == user["id"]: raise HTTPException(400, "Неверный ID")
    p = await get_pool()
    async with p.acquire() as conn:
        # Проверка на блокировку
        blk = await conn.fetchrow("SELECT id FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)", user["id"], tid)
        if blk: raise HTTPException(403, "Заблокирован")
        # Проверка на дружбу
        fr = await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], tid)
        if fr: raise HTTPException(400, "Уже друзья")
        # Проверка на заявку
        req = await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], tid)
        if req: raise HTTPException(400, "Заявка уже есть")
        
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)", user["id"], tid)
    await manager.send_to(tid, {"type": "friend_request", "from_id": user["id"], "username": user["username"], "display_name": user.get("display_name")})
    return {"ok": True}

@app.post("/api/friends/accept")
async def friends_accept(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT from_user, to_user FROM friend_requests WHERE id=$1", rid)
        if not r or r["to_user"] != user["id"]: raise HTTPException(403, "Ошибка")
        
        a, b = sorted([r["from_user"], r["to_user"]])
        await conn.execute("INSERT INTO friendships(user_a,user_b) VALUES($1,$2) ON CONFLICT DO NOTHING", a, b)
        await conn.execute("DELETE FROM friend_requests WHERE id=$1", rid)
        
        other = await conn.fetchrow("SELECT id, username, display_name FROM users WHERE id=$1", r["from_user"])
        if other:
            await manager.send_to(other["id"], {"type": "friend_accepted", "friend_id": user["id"], "username": user["username"]})
    return {"ok": True}
# ============ КАНАЛЫ ============
@app.get("/api/channels/my")
async def channels_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    try:
        async with p.acquire() as conn:
            # Подписки
            subs = await conn.fetch("""SELECT c.* FROM channels c JOIN channel_subscribers cs ON cs.channel_id=c.id WHERE cs.user_id=$1""", user["id"])
            # Свои каналы
            owned = await conn.fetch("SELECT * FROM channels WHERE owner_id=$1", user["id"])
            
            result = []
            seen = set()
            for r in subs:
                if r["id"] in seen: continue
                seen.add(r["id"])
                result.append({"id": r["id"], "username": r["username"], "name": r["name"], "bio": r["bio"], "avatar": r["avatar"], "subscribers_count": r["subscribers_count"], "is_owner": r["owner_id"] == user["id"]})
            
            for r in owned:
                if r["id"] in seen: continue
                result.append({"id": r["id"], "username": r["username"], "name": r["name"], "bio": r["bio"], "avatar": r["avatar"], "subscribers_count": r["subscribers_count"], "is_owner": True})
            
            return result
    except Exception as e:
        print(f"[channels_my] ОШИБКА: {e}")
        return []

@app.post("/api/channels/create")
async def channels_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя обязательно")
    
    uname = (data.get("username") or "").strip().lower()
    p = await get_pool()
    async with p.acquire() as conn:
        if uname:
            u1 = await conn.fetchval("SELECT 1 FROM users WHERE username=$1", uname)
            u2 = await conn.fetchval("SELECT 1 FROM channels WHERE username=$1", uname)
            if u1 or u2: raise HTTPException(409, "Username занят")
        
        c = await conn.fetchrow("""INSERT INTO channels(username, name, bio, avatar, owner_id, is_private, category) 
            VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *""", 
            uname or None, name, (data.get("bio") or "")[:256], data.get("avatar"), user["id"], bool(data.get("is_private", False)), (data.get("category") or "")[:32])
        
        # Добавляем создателя в админы
        await conn.execute("INSERT INTO channel_admins(channel_id, user_id, perms) VALUES($1,$2,$3)", c["id"], user["id"], json.dumps({"post": True, "edit": True, "delete": True}))
        
    return {"ok": True, "id": c["id"], "username": c["username"], "name": c["name"]}

@app.get("/api/channels/{cid}")
async def channel_get(cid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not c: raise HTTPException(404, "Канал не найден")
        
        is_sub = await conn.fetchval("SELECT 1 FROM channel_subscribers WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
        is_adm = await conn.fetchval("SELECT 1 FROM channel_admins WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
        is_owner = c["owner_id"] == user["id"]
        
    return {
        "id": c["id"], "username": c["username"], "name": c["name"], "bio": c["bio"], 
        "avatar": c["avatar"], "banner": c["banner"], "avatar_pos": c["avatar_pos"], "banner_pos": c["banner_pos"],
        "is_private": c["is_private"], "category": c["category"], "subscribers_count": c["subscribers_count"],
        "is_owner": is_owner, "is_admin": bool(is_adm) or is_owner, "is_subscribed": bool(is_sub)
    }

@app.post("/api/channels/{cid}/subscribe")
async def channel_subscribe(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO channel_subscribers(channel_id, user_id) VALUES($1,$2) ON CONFLICT DO NOTHING", cid, user["id"])
        await conn.execute("UPDATE channels SET subscribers_count=(SELECT COUNT(*) FROM channel_subscribers WHERE channel_id=$1) WHERE id=$1", cid)
    return {"ok": True}

@app.post("/api/channels/{cid}/unsubscribe")
async def channel_unsubscribe(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM channel_subscribers WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
        await conn.execute("UPDATE channels SET subscribers_count=(SELECT COUNT(*) FROM channel_subscribers WHERE channel_id=$1) WHERE id=$1", cid)
    return {"ok": True}

@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT p.*, u.username AS author_name FROM channel_posts p LEFT JOIN users u ON u.id=p.author_id WHERE p.channel_id=$1 ORDER BY p.pinned DESC, p.id DESC LIMIT 50", cid)
    return [{"id": r["id"], "text": r["text"], "media_urls": _safe_json(r["media_urls"], []), "media_kind": r["media_kind"], "reactions": _safe_json(r["reactions"], {}), "pinned": r["pinned"], "views": r["views"], "comments_count": r["comments_count"], "created_at": _iso(r["created_at"])} for r in rows]

@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        adm = await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
        if not adm: raise HTTPException(403, "Вы не админ канала")
        
        text = (data.get("text") or "")[:MAX_TEXT]
        if not text: raise HTTPException(400, "Пусто")
        
        r = await conn.fetchrow("INSERT INTO channel_posts(channel_id, author_id, text, media_urls, media_kind) VALUES($1,$2,$3,$4,$5) RETURNING *", cid, user["id"], text, json.dumps(data.get("media_urls") or []), (data.get("media_kind") or "text")[:16])
    return {"ok": True, "post_id": r["id"]}

@app.post("/api/channels/{cid}/posts/{pid}/delete")
async def channel_post_delete(cid: int, pid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        adm = await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2", cid, user["id"])
        if not adm: raise HTTPException(403, "Нет прав")
        await conn.execute("DELETE FROM channel_posts WHERE id=$1 AND channel_id=$2", pid, cid)
    return {"ok": True}

# ============ ОБСУЖДЕНИЯ ============
@app.get("/api/channels/{cid}/posts/{pid}/comments")
async def post_comments(cid: int, pid: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT linked_group_id FROM channels WHERE id=$1", cid)
        if not c or not c["linked_group_id"]: return {"comments": [], "group_id": None}
        
        rows = await conn.fetch("""SELECT gm.*, u.username, u.display_name, u.avatar FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 AND gm.post_id=$2 ORDER BY gm.id ASC""", c["linked_group_id"], pid)
    return {"comments": [{"id": r["id"], "text": r["text"], "username": r["username"], "display_name": r["display_name"], "avatar": r["avatar"], "created_at": _iso(r["created_at"])} for r in rows], "group_id": c["linked_group_id"]}

@app.post("/api/channels/{cid}/posts/{pid}/comment")
async def post_comment(cid: int, pid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    text = (data.get("text") or "")[:MAX_TEXT]
    if not text: raise HTTPException(400, "Текст обязателен")
    
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT linked_group_id FROM channels WHERE id=$1", cid)
        if not c or not c["linked_group_id"]: raise HTTPException(400, "Обсуждение не включено")
        
        msg = await conn.fetchrow("INSERT INTO group_messages(group_id, user_id, text, post_id) VALUES($1,$2,$3,$4) RETURNING *", c["linked_group_id"], user["id"], text, pid)
        await conn.execute("UPDATE channel_posts SET comments_count=(SELECT COUNT(*) FROM group_messages WHERE post_id=$1) WHERE id=$1", pid)
        
        members = await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1", c["linked_group_id"])
    
    payload = {"type": "group_msg", "id": msg["id"], "group_id": c["linked_group_id"], "user_id": user["id"], "username": user["username"], "text": text, "post_id": pid, "created_at": _iso(msg["created_at"])}
    for m in members:
        if m["user_id"] != user["id"]:
            await manager.send_to(m["user_id"], payload)
    return {"ok": True, "comment_id": msg["id"]}
# ============ WEBSOCKET (СЕРДЦЕ) ============
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
                
            # --- ОТПРАВКА СООБЩЕНИЙ (DM) ---
            elif t == "dm":
                to_id = int(data.get("to_user", 0))
                text = (data.get("text") or "")[:MAX_TEXT]
                tid = data.get("temp_id")
                if not to_id: continue
                
                p = await get_pool()
                async with p.acquire() as conn:
                    msg = await conn.fetchrow("INSERT INTO dms(from_user, to_user, text) VALUES($1,$2,$3) RETURNING *", uid, to_id, text)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1", uid)
                
                payload = {"type": "dm", "id": msg["id"], "from_user": uid, "to_user": to_id, "username": user["username"], "display_name": user.get("display_name"), "avatar": user.get("avatar"), "text": text, "created_at": _iso(msg["created_at"]), "temp_id": tid}
                await manager.send_to(to_id, payload)
                await manager.send_to(uid, payload)

            # --- ОТПРАВКА СООБЩЕНИЙ (ГРУППА) ---
            elif t == "group_msg":
                gid = int(data.get("group_id", 0))
                text = (data.get("text") or "")[:MAX_TEXT]
                tid = data.get("temp_id")
                if not gid: continue
                
                p = await get_pool()
                async with p.acquire() as conn:
                    msg = await conn.fetchrow("INSERT INTO group_messages(group_id, user_id, text) VALUES($1,$2,$3) RETURNING *", gid, uid, text)
                    members = await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1", gid)
                
                payload = {"type": "group_msg", "id": msg["id"], "group_id": gid, "user_id": uid, "username": user["username"], "display_name": user.get("display_name"), "avatar": user.get("avatar"), "text": text, "created_at": _iso(msg["created_at"]), "temp_id": tid}
                for m in members: await manager.send_to(m["user_id"], payload)
                
            # --- СТАТУС "ПЕЧАТАЕТ" ---
            elif t == "typing":
                to_id = int(data.get("to_user", 0))
                if to_id: await manager.send_to(to_id, {"type": "typing", "from_user": uid})

    except WebSocketDisconnect: pass
    except Exception as e: print(f"[WS] {e}")
    finally:
        manager.disconnect(uid, ws)
        await manager.broadcast({"type": "user_offline", "user_id": uid})

# ============ БОГ-ПАНЕЛЬ И АДМИНКА ============
async def check_owner(user):
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")

@app.post("/api/owner/verify")
async def owner_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    if (data.get("password") or "") != OWNER_PASSWORD: raise HTTPException(403, "Неверный пароль")
    return {"ok": True}

@app.get("/api/owner/stats")
async def owner_stats(token: str):
    user = await get_current_user(token); await check_owner(user)
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        c = await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
    return {"users": u, "online": len(online_users), "coins": c}

@app.post("/api/owner/give_coins")
async def owner_give_coins(data: dict):
    user = await get_current_user(data.get("token")); await check_owner(user)
    uid = int(data.get("user_id", 0))
    amount = int(data.get("amount", 100))
    if not uid: raise HTTPException(400, "user_id")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", amount, uid)
    return {"ok": True}

# ============ КАНАЛЫ (ДОПОЛНЕНИЕ) ============
@app.post("/api/channels/{cid}/edit")
async def channel_edit(cid: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not c or c["owner_id"] != user["id"]: raise HTTPException(403, "Нет прав")
        if data.get("name"): await conn.execute("UPDATE channels SET name=$1 WHERE id=$2", data["name"][:64], cid)
        if data.get("bio"): await conn.execute("UPDATE channels SET bio=$1 WHERE id=$2", data["bio"][:256], cid)
    return {"ok": True}

# ============ СТАТИКА И ЗАПУСК ============
@app.get("/icon.png")
async def serve_icon():
    for p in ["icon-192x192.png", "icon.png"]:
        if os.path.exists(p):
            with open(p, "rb") as f: return HTMLResponse(content=f.read(), media_type="image/png")
    return HTMLResponse("", status_code=404)

@app.get("/manifest.json")
async def manifest():
    return {"name": "BelugaCord 3.7", "short_name": "BelugaCord", "start_url": "/", "display": "standalone", "background_color": "#0f0f13", "theme_color": "#0f0f13", "icons": [{"src": "/icon-192x192.png", "sizes": "192x192", "type": "image/png"}]}

@app.get("/")
async def index():
    try:
        with open("index.html", "r", encoding="utf-8") as f: return HTMLResponse(f.read())
    except Exception as e: return HTMLResponse(f"<h1>index.html нет</h1><p>{e}</p>", status_code=500)

@app.get("/ref/{code}")
async def ref_redirect(code: str):
    try:
        with open("index.html", "r", encoding="utf-8") as f: return HTMLResponse(f.read())
    except Exception:
        return HTMLResponse("<h1>index.html нет</h1>", status_code=500)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e:
            print(f"❌ DB INIT: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, ws="websockets", proxy_headers=True, forwarded_allow_ips="*")