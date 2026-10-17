# BELUGACORD 3.7 «ФЕНИКС» — server.py — ЧАСТЬ 1/4
# Чистая база: Конфиг, Утилиты, База Данных (Таблицы)

import os, json, time, secrets, hashlib, random, datetime, asyncio, re, traceback, base64
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ============ КОНФИГ ============
DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2032")
ADMIN_USERNAME = "_fan_beluga_"
ADMIN_DISPLAY = "👑 Владелец"
OWNER_PASSWORD = "12344321"
CURRENT_VERSION = "3.7"
MAX_TEXT = 10000

# ============ УТИЛИТЫ БЕЗОПАСНОСТИ ============
# Функция хеширования пароля
def hash_password(p):
    s = secrets.token_hex(16)
    return f"{s}${hashlib.sha256((s+p).encode()).hexdigest()}"

# Функция проверки пароля
def verify_password(p, st):
    try:
        s, h = st.split("$", 1)
        return hashlib.sha256((s+p).encode()).hexdigest() == h
    except: return False

# Генерация токена авторизации
def make_token(uid, un):
    d = f"{uid}:{un}:{int(time.time())}"
    return f"{d}:{hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]}"

# Парсинг токена
def parse_token(t):
    try:
        parts = t.split(":")
        if len(parts) != 4: return None
        uid, un, ts, sig = parts
        d = f"{uid}:{un}:{ts}"
        if sig != hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]: return None
        return int(uid), un
    except: return None

# Очистка юзернейма от мусора
def sanitize_username(u):
    u = re.sub(r'[^a-zA-Z0-9_]', '_', str(u).lower())
    if not u: u = "user"
    if len(u) > 24: u = u[:24]
    if u[0].isdigit(): u = "_" + u
    return u

# Валидация юзернейма
def validate_username(u):
    if not u: return False, "Пусто"
    if len(u) < 4 or len(u) > 32: return False, "4-32 символа"
    if not re.match(r'^[a-z][a-z0-9_]*$', u): return False, "Только a-z, 0-9, _"
    return True, None

# Конвертация времени в ISO
def _iso(dt):
    if not dt: return None
    try: return dt.isoformat()
    except: return str(dt)

# Безопасный JSON
def _safe_json(v, default=None):
    if default is None: default = {}
    try:
        if isinstance(v, str): return json.loads(v)
        return v
    except: return default

# ============ БАЗА ДАННЫХ ============
pool = None
online_users = set() # Кто сейчас онлайн
active_calls = {}    # Кто сейчас в звонках

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        # --- ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ ---
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
        
        # --- ТАБЛИЦА ДРУЗЕЙ ---
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY, user_a INTEGER REFERENCES users(id) ON DELETE CASCADE, user_b INTEGER REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(user_a, user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE, to_user INTEGER REFERENCES users(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_blocks(id SERIAL PRIMARY KEY, blocker INTEGER REFERENCES users(id) ON DELETE CASCADE, blocked INTEGER REFERENCES users(id) ON DELETE CASCADE, chat_cleared BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(blocker, blocked))""")
        
        # --- ТАБЛИЦА ГРУПП ---
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE, name VARCHAR(64) NOT NULL, avatar TEXT, banner TEXT, avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%', description VARCHAR(256), owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE, invite_code VARCHAR(16) UNIQUE, last_message_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, is_admin BOOLEAN DEFAULT FALSE, joined_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(group_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY, group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, text TEXT, file_url TEXT, file_size BIGINT DEFAULT 0, msg_kind VARCHAR(16) DEFAULT 'text', voice_duration INTEGER DEFAULT 0, reply_to_id INTEGER, edited_at TIMESTAMPTZ, reactions TEXT DEFAULT '{}', pinned BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW())""")
        
        # --- ТАБЛИЦА ЛИЧНЫХ СООБЩЕНИЙ ---
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(
            id SERIAL PRIMARY KEY, from_user INTEGER REFERENCES users(id) ON DELETE CASCADE, to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT, file_url TEXT, file_size BIGINT DEFAULT 0, msg_kind VARCHAR(16) DEFAULT 'text', voice_duration INTEGER DEFAULT 0,
            read_at TIMESTAMPTZ, forwarded_from VARCHAR(64), pinned BOOLEAN DEFAULT FALSE, starred TEXT DEFAULT '[]',
            reply_to_id INTEGER, edited_at TIMESTAMPTZ, reactions TEXT DEFAULT '{}', deleted_for_all BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        
        # --- ТАБЛИЦА КАНАЛОВ ---
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY, username VARCHAR(32) UNIQUE, name VARCHAR(64) NOT NULL, bio VARCHAR(256), avatar TEXT, banner TEXT, avatar_pos TEXT DEFAULT '50% 50%', banner_pos TEXT DEFAULT '50% 50%', owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE, is_private BOOLEAN DEFAULT FALSE, category VARCHAR(32), subscribers_count INTEGER DEFAULT 0, username_changed_at TIMESTAMPTZ, linked_group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_admins(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, perms TEXT DEFAULT '{"post":true}', added_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(channel_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_subscribers(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, muted_until TIMESTAMPTZ, subscribed_at TIMESTAMPTZ DEFAULT NOW(), PRIMARY KEY(channel_id, user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_posts(id SERIAL PRIMARY KEY, channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE, author_id INTEGER REFERENCES users(id) ON DELETE SET NULL, text TEXT, media_urls TEXT DEFAULT '[]', media_kind VARCHAR(16) DEFAULT 'text', reactions TEXT DEFAULT '{}', pinned BOOLEAN DEFAULT FALSE, views INTEGER DEFAULT 0, edited BOOLEAN DEFAULT FALSE, comments_count INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""")
        
        # --- ТАБЛИЦА РАНГОВ ---
        await conn.execute("""CREATE TABLE IF NOT EXISTS ranks(id SERIAL PRIMARY KEY, name VARCHAR(64) NOT NULL, emoji VARCHAR(8) DEFAULT '🏆', color VARCHAR(32) DEFAULT '#d946ef', priority INTEGER DEFAULT 10, perms TEXT DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT NOW())""")
        
        # --- ТАБЛИЦА РЕФЕРАЛКИ ---
        await conn.execute("""CREATE TABLE IF NOT EXISTS referrals(id SERIAL PRIMARY KEY, code VARCHAR(16) UNIQUE NOT NULL, owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE, clicks INTEGER DEFAULT 0, registrations INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS referral_uses(id SERIAL PRIMARY KEY, code VARCHAR(16), referrer_id INTEGER REFERENCES users(id) ON DELETE SET NULL, new_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, reward_ref INTEGER DEFAULT 0, reward_new INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""")

        # --- СИД БАЗОВЫХ ДАННЫХ ---
        await conn.execute("UPDATE users SET display_name=username WHERE display_name IS NULL")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1", ADMIN_USERNAME)
        await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2", ADMIN_DISPLAY, ADMIN_USERNAME)
        
        # Создание дефолтных рангов
        ranks_cnt = await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if ranks_cnt == 0:
            try:
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","👑 Владелец","👑","#ffd700",1000,json.dumps({"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🛡️ Администратор","🛡️","#d946ef",500,json.dumps({"admin_panel":True,"manage_users":True,"give_coins":True,"ban":True,"mute":True,"delete_msgs":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🔨 Модератор","🔨","#22c55e",100,json.dumps({"mute":True,"delete_msgs":True}))
            except Exception as e:
                print(f"Ошибка при создании дефолтных рангов: {e}")

        print("✅ БД 3.7 ФЕНИКС готова (Чистая база)")
# BELUGACORD 3.7 «ФЕНИКС» — server.py — ЧАСТЬ 2/4
# Пользователи, Авторизация, Профили, Друзья, Каналы

# ============ ПОЛЬЗОВАТЕЛИ И АВТОРИЗАЦИЯ ============
# Функция получения юзера по токену
async def get_current_user(token):
    parsed = parse_token(token)
    if not parsed: return None
    uid, _ = parsed
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
        return dict(row) if row else None

# Функция получения прав и ранга
async def get_user_perms_full(conn, uid):
    row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
    if not row: return {}, None
    u = dict(row)
    perms = {}
    # Высшие права для Бога
    if u.get("username") == ADMIN_USERNAME:
        perms = {"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"manage_shop":True,"manage_cosmetics":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True}
    # Права админов и модеров
    if u.get("is_admin"): perms["admin_panel"] = True
    if u.get("is_moderator"): perms["mute"] = True; perms["delete_msgs"] = True
    # Права из ранга
    if u.get("rank_id"):
        r = await conn.fetchrow("SELECT perms,name,emoji,color,priority FROM ranks WHERE id=$1", u["rank_id"])
        if r:
            rp = _safe_json(r["perms"], {})
            perms = {**perms, **rp}
            return perms, {"id":u["rank_id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"priority":r["priority"]}
    return perms, None

# Функция публичного профиля (для фронта)
def user_public(row, viewer_id=None):
    if row is None: return {}
    return {
        "id": row["id"], "username": row["username"], "display_name": row.get("display_name") or row["username"],
        "avatar": row.get("avatar"), "banner": row.get("banner"), "gif_avatar": row.get("gif_avatar"),
        "is_admin": bool(row.get("is_admin")), "is_moderator": bool(row.get("is_moderator")),
        "is_scam": bool(row.get("is_scam")), "premium_tier": row.get("premium_tier"),
        "coins": row.get("coins", 0), "level": row.get("level", 1), "xp": row.get("xp", 0),
        "online_status": row.get("online_status", "online"),
        "role": "owner" if row.get("username") == ADMIN_USERNAME else ("admin" if row.get("is_admin") else "user"),
        "online": row["id"] in online_users
    }

# РЕГИСТРАЦИЯ (с заглушкой под рефералку)
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
        
        # === ЗАМЕНИ НА: Логика выдачи бонусов за реф-ссылку (Рефералка) ===
        if ref_code:
            try:
                ref = await conn.fetchrow("SELECT owner_id FROM referrals WHERE code=$1", ref_code)
                if ref:
                    await conn.execute("UPDATE users SET coins=coins+20000 WHERE id=$1", ref["owner_id"])
                    await conn.execute("UPDATE users SET coins=coins+500 WHERE id=$1", row["id"])
                    await conn.execute("UPDATE referrals SET registrations=registrations+1 WHERE code=$1", ref_code)
            except Exception as e:
                print(f"[referral] {e}")

    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

# ВХОД
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

# ПОЛУЧЕНИЕ СВОЕГО ПРОФИЛЯ (с правами)
@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    pub = user_public(user, user["id"])
    p = await get_pool()
    async with p.acquire() as conn:
        perms, rank = await get_user_perms_full(conn, user["id"])
    pub["perms"] = perms
    pub["rank"] = rank
    return pub

# ============ ПРОФИЛИ И МЕДИА ============
# === ЗАМЕНИ НА: Функция загрузки Base64 (Аватарки/Баннеры не слетают) ===
@app.post("/api/upload_avatar")
async def upload_avatar(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    # Заглушка: Base64 будет позже
    return {"ok": True, "url": "/uploads/default_avatar.png"}

# === ЗАМЕНИ НА: Функция загрузки Base64 (Баннеры) ===
@app.post("/api/upload_banner")
async def upload_banner(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"ok": True, "url": "/uploads/default_banner.png"}

# === ЗАМЕНИ НА: Обновление профиля (bio, ник, драг позиции) ===
@app.post("/api/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    return {"ok": True}

# === ЗАМЕНИ НА: Логика Друзей (Заявки, принятие, список) ===
@app.get("/api/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return [] # Заглушка

# === ЗАМЕНИ НА: Отправка заявки в друзья с пуш-уведомлением ===
@app.post("/api/friends/request")
async def friends_request(data: dict):
    return {"ok": True}

# ============ КАНАЛЫ ============
# === ЗАМЕНИ НА: Получение моих каналов (фикс ошибки 500) ===
@app.get("/api/channels/my")
async def channels_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    try:
        async with p.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM channels WHERE owner_id=$1", user["id"])
        return [{"id": r["id"], "name": r["name"], "username": r["username"], "subscribers_count": r["subscribers_count"], "is_owner": True} for r in rows]
    except Exception as e:
        print(f"[channels_my] ОШИБКА: {e}")
        return []

# === ЗАМЕНИ НА: Создание канала с проверкой юзернейма ===
@app.post("/api/channels/create")
async def channels_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    return {"ok": True, "id": 1}

# === ЗАМЕНИ НА: Инфо о канале ===
@app.get("/api/channels/{cid}")
async def channel_get(cid: int, token: str):
    return {"id": cid, "name": "Тестовый канал"}

# === ЗАМЕНИ НА: Посты канала (с медиа и реакциями) ===
@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int, token: str):
    return []

# === ЗАМЕНИ НА: Создание поста в канале ===
@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, data: dict):
    return {"ok": True}
# BELUGACORD 3.7 «ФЕНИКС» — server.py — ЧАСТЬ 3/4
# Сообщения, Группы, WebSocket (Сердце), Медиа

# ============ ЛИЧНЫЕ СООБЩЕНИЯ (DM) ============
# === ЗАМЕНИ НА: Получение истории переписки (с реакциями и ответами) ===
@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    # Заглушка: возвращает пустой массив, чтобы фронт не падал
    return []

# ============ ГРУППЫ ============
# === ЗАМЕНИ НА: Список групп пользователя ===
@app.get("/api/groups/list")
async def groups_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return []

# === ЗАМЕНИ НА: Создание новой группы ===
@app.post("/api/groups/create")
async def groups_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    return {"ok": True, "id": 1}

# === ЗАМЕНИ НА: История сообщений группы ===
@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return []

# ============ МЕДИА И ФАЙЛЫ ============
# === ЗАМЕНИ НА: Загрузка обычных файлов и фото ===
@app.post("/api/upload")
async def upload(token: str = Form(...), file: UploadFile = File(...)):
    return {"url": "/uploads/test.png", "size": 0}

# === ЗАМЕНИ НА: Загрузка голосовых сообщений ===
@app.post("/api/upload_voice")
async def upload_voice(token: str = Form(...), file: UploadFile = File(...), duration: int = Form(0)):
    return {"url": "/uploads/test_voice.ogg", "duration": duration}

# === ЗАМЕНИ НА: Загрузка видео-кружков (до 60 сек) ===
@app.post("/api/upload_video_note")
async def upload_video_note(token: str = Form(...), file: UploadFile = File(...), duration: int = Form(0)):
    return {"url": "/uploads/test_vnote.webm", "duration": duration}

# ============ WEBSOCKET (СЕРДЦЕ) ============
class ConnectionManager:
    def __init__(self): self.connections = {}
    
    # Подключение нового сокета
    async def connect(self, uid, ws):
        await ws.accept()
        self.connections.setdefault(uid, []).append(ws)
        online_users.add(uid)
        
    # Отключение сокета
    def disconnect(self, uid, ws):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except: pass
            if not self.connections[uid]:
                del self.connections[uid]
                online_users.discard(uid)
                
    # Отправка пакета конкретному юзеру
    async def send_to(self, uid, data):
        for ws in list(self.connections.get(uid, [])):
            try: await ws.send_json(data)
            except: self.disconnect(uid, ws)
            
    # Рассылка всем
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
    
    uid = user["id"]
    await manager.connect(uid, ws)
    
    # Отправляем список онлайна при входе
    try: await ws.send_json({"type": "online_list", "users": list(online_users)})
    except: pass
    
    # Оповещаем всех, что юзер зашел
    await manager.broadcast({"type": "user_online", "user_id": uid}, exclude=uid)
    
    try:
        while True:
            raw = await ws.receive_text()
            try: data = json.loads(raw)
            except: continue
            
            t = data.get("type")
            
            # --- ПИНГ / ПОНГ (проверка связи) ---
            if t == "ping":
                try: await ws.send_json({"type": "pong"})
                except: pass
                continue
                
            # --- СТАТУС "ПЕЧАТАЕТ" ---
            elif t == "typing":
                # === ЗАМЕНИ НА: Логика статуса "Печатает..." ===
                pass
                
            # --- ЗВОНКИ ---
            elif t == "call_invite":
                # === ЗАМЕНИ НА: Приглашение на звонок (создание комнаты) ===
                pass
            elif t == "call_accept":
                # === ЗАМЕНИ НА: Принятие звонка (запуск WebRTC) ===
                pass
            elif t == "call_end":
                # === ЗАМЕНИ НА: Завершение звонка (запись в историю) ===
                pass
            elif t in ("webrtc_offer", "webrtc_answer", "webrtc_ice"):
                # === ЗАМЕНИ НА: Пересылка WebRTC пакетов (Звук/Видео) ===
                pass
                
            # --- УЛИЦА (SPATIAL AUDIO) ---
            elif t == "street_move":
                # === ЗАМЕНИ НА: Логика движения по 2D/3D Улице (координаты и звук) ===
                pass
                
            # --- ОТПРАВКА СООБЩЕНИЙ ---
            elif t == "dm":
                # === ЗАМЕНИ НА: Сохранение личного сообщения в БД и отправка получателю ===
                pass
            elif t == "group_msg":
                # === ЗАМЕНИ НА: Сохранение сообщения в группу и рассылка участникам ===
                pass
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] {type(e).__name__}: {e}")
    finally:
        manager.disconnect(uid, ws)
        # Оповещаем всех, что юзер ушел
        await manager.broadcast({"type": "user_offline", "user_id": uid})
# BELUGACORD 3.7 «ФЕНИКС» — server.py — ЧАСТЬ 4/4
# БОГ-Панель, Админка, Статика, Запуск

# ============ БОГ-ПАНЕЛЬ И АДМИНКА ============
# Функция проверки на Владельца (Бога)
async def check_owner(user):
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")

# Вход в БОГ-панель
@app.post("/api/owner/verify")
async def owner_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    if (data.get("password") or "") != OWNER_PASSWORD: raise HTTPException(403, "Неверный пароль")
    return {"ok": True}

# === ЗАМЕНИ НА: Статистика для БОГа (юзеры, онлайн, монеты) ===
@app.get("/api/owner/stats")
async def owner_stats(token: str):
    user = await get_current_user(token); await check_owner(user)
    # Заглушка, чтобы панель не падала
    return {"users": 0, "online": len(online_users), "messages": 0, "coins": 0, "channels": 0, "groups": 0, "premium": 0, "ranks": 0}

# === ЗАМЕНИ НА: Список всех юзеров для Админки ===
@app.get("/api/admin/users")
async def admin_users(token: str, limit: int = 500):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    # Заглушка
    return {"users": []}

# === ЗАМЕНИ НА: Генерация Промокодов (DonationAlerts/Подарки) ===
@app.post("/api/owner/promo/create")
async def promo_create(data: dict):
    user = await get_current_user(data.get("token")); await check_owner(user)
    return {"ok": True, "code": "BELUGA-TEST"}

# === ЗАМЕНИ НА: Активация Промокода юзером ===
@app.post("/api/promo/activate")
async def promo_activate(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    return {"ok": True, "amount": 0}

# === ЗАМЕНИ НА: Массовая выдача монет/беков ===
@app.post("/api/owner/mass/give")
async def owner_mass_give(data: dict):
    user = await get_current_user(data.get("token")); await check_owner(user)
    return {"ok": True}

# === ЗАМЕНИ НА: Массовая смена темы для всех ===
@app.post("/api/owner/mass/theme")
async def owner_mass_theme(data: dict):
    user = await get_current_user(data.get("token")); await check_owner(user)
    return {"ok": True}

# === ЗАМЕНИ НА: Создание, редактирование и удаление рангов ===
@app.get("/api/owner/ranks/list")
async def ranks_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"ranks": []} # Заглушка

# ============ СИСТЕМНЫЕ НАСТРОЙКИ ============
# Получение чейнджлога версии
@app.get("/api/changelog")
async def changelog():
    return {"current": CURRENT_VERSION, "all": {"3.7": {"title": "BelugaCord 3.7 — Феникс", "items": ["🚀 Улица со звуком", "💰 Экономика и Донаты", "📱 Мобильный UI 2.0"]}}}

# ============ СТАТИКА И ЗАПУСК ============
# Отдача иконки
@app.get("/icon.png")
async def serve_icon():
    for p in ["icon-192x192.png", "icon.png"]:
        if os.path.exists(p):
            with open(p, "rb") as f: return HTMLResponse(content=f.read(), media_type="image/png")
    return HTMLResponse("", status_code=404)

# Отдача манифеста для PWA
@app.get("/manifest.json")
async def manifest():
    return {"name":"BelugaCord 3.7","short_name":"BelugaCord","start_url":"/","display":"standalone","background_color":"#0f0f13","theme_color":"#0f0f13","icons":[{"src":"/icon-192x192.png","sizes":"192x192","type":"image/png"}]}

# Отдача index.html (и реф-ссылки)
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

# Раздача загруженных файлов (пока для тестов)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ИНИЦИАЛИЗАЦИЯ БАЗЫ ПРИ СТАРТЕ
@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e:
            print(f"❌ DB INIT: {e}")
            traceback.print_exc()

# ТОЧКА ВХОДА
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, ws="websockets", proxy_headers=True, forwarded_allow_ips="*")