# BELUGACORD 2.5 — api/_shared.py
# Общие утилиты, состояние, WS, фоновые задачи
import os, json, time, secrets, hashlib, random, datetime, asyncio, re
import asyncpg
import httpx
from fastapi import HTTPException, WebSocket

DATABASE_URL = os.environ.get("DATABASE_URL", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "belugacord_secret_2026")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ADMIN_USERNAME = "_fan_beluga_"
OWNER_PASSWORD = "12344321"
CURRENT_VERSION = "2.5"

EMAIL_CODE_TTL_MINUTES = 10
EMAIL_CODE_MAX_ATTEMPTS = 3
EMAIL_RESEND_COOLDOWN = 60

LIMITS = {
    None: {"file": 10*1024*1024, "msg": 2000, "servers": 10, "channels": 20, "groups": 10},
    "premium": {"file": 50*1024*1024, "msg": 4000, "servers": 50, "channels": 100, "groups": 30},
    "pro": {"file": 200*1024*1024, "msg": 10000, "servers": 999, "channels": 999, "groups": 30}
}
PREMIUM_PRICES = {"month": 1500, "year": 18000}
QUEST_EXCHANGE = {"1day": {"cost":1400,"days":1}, "3days":{"cost":7500,"days":3}, "7days":{"cost":10000,"days":7}}

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
    "universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000}
}

GAME_LIST = ["penguin","minesweeper","snake","2048","flappy","tetris","memory","reaction","tictactoe","rps","battleship","duel","freedoom"]

ACHIEVEMENTS = {
    "first_msg":{"name":"Первое слово","emoji":"💬","desc":"Отправь первое сообщение"},
    "msg_100":{"name":"Болтун","emoji":"🗣️","desc":"100 сообщений"},
    "msg_1000":{"name":"Оратор","emoji":"🎤","desc":"1000 сообщений"},
    "msg_10000":{"name":"Легенда чата","emoji":"📢","desc":"10000 сообщений"},
    "first_friend":{"name":"Дружелюбный","emoji":"👥","desc":"Первый друг"},
    "friend_10":{"name":"Тусовщик","emoji":"🎉","desc":"10 друзей"},
    "first_gift":{"name":"Щедрый","emoji":"🎁","desc":"Первый подарок"},
    "first_nft":{"name":"Коллекционер","emoji":"🎨","desc":"Первый NFT"},
    "snake_100":{"name":"Змеелов","emoji":"🐍","desc":"100 очков в Змейке"},
    "flappy_50":{"name":"Летун","emoji":"🐦","desc":"50 очков в Flappy"},
    "first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},
    "coins_10k":{"name":"Богач","emoji":"💰","desc":"10000 бекоинов"},
    "rating_100":{"name":"Щедрая душа","emoji":"💎","desc":"Соц.рейтинг 100"},
    "rating_10000":{"name":"Меценат","emoji":"👑","desc":"Соц.рейтинг 10000"}
}

CHANGELOG = {
    "2.5":{"title":"Belugacord Beta 2.5","items":[
        "🚀 Hot-swap обновлений (владелец включает в БОГ-меню)",
        "🎁 Промо-панель (рефералы /fanchipromo)",
        "👑 Починено БОГ-меню — все кнопки работают",
        "📋 Список юзеров с фильтрами и массовыми действиями",
        "🏆 Редактор БП (сезон, задания, награды)",
        "🎰 Апгрейдер 2.0 — дропдауны, множители ×2/×4/×6/×8, круг-мишень",
        "🎭 SCAM-плашка для юзеров",
        "📧 Email-верификация (10 мин код, 3 попытки)",
        "🧩 Модульная архитектура (features/*)",
        "🎮 13 игр"
    ]},
    "2.4":{"title":"Belugacord Beta 2.4","items":[
        "🛠️ Полная пересборка","🐛 Фиксы кнопок подарков","🎰 Апгрейдер-колесо",
        "🎤 Голосовые","📸 Сторис","🧵 Треды","📊 Биржа NFT","🏦 Банк","🔨 Аукцион",
        "🎨 Титулы","😀 Кастомные реакции","✨ Эффекты","📊 Уровни/XP","🏆 БП"
    ]}
}

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ============================================================
pool = None
online_users = set()
active_events = []
active_tournament = {"game": None, "started_at": None}
upgrade_chance_bonus = {}
custom_commands = {}
email_last_sent = {}

spam_tracker = {}
friend_spam_tracker = {}
friend_target_spam = {}
flood_tracker = {}
last_cleanup = time.time()

# ============================================================
# POOL
# ============================================================
async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return pool

# ============================================================
# ХЕШ ПАРОЛЯ / ТОКЕНЫ
# ============================================================
def hash_password(p):
    s = secrets.token_hex(16)
    return f"{s}${hashlib.sha256((s + p).encode()).hexdigest()}"

def verify_password(p, st):
    try:
        s, h = st.split("$", 1)
        return hashlib.sha256((s + p).encode()).hexdigest() == h
    except: return False

def make_token(uid, un):
    d = f"{uid}:{un}:{int(time.time())}"
    return f"{d}:{hashlib.sha256((d + SECRET_KEY).encode()).hexdigest()[:32]}"

def parse_token(t):
    try:
        parts = t.split(":")
        if len(parts) != 4: return None
        uid, un, ts, sig = parts
        d = f"{uid}:{un}:{ts}"
        if sig != hashlib.sha256((d + SECRET_KEY).encode()).hexdigest()[:32]: return None
        return int(uid), un
    except: return None

def is_valid_email(e):
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", e or ""))

# ============================================================
# ЮЗЕР
# ============================================================
async def get_current_user(token):
    parsed = parse_token(token)
    if not parsed: return None
    uid, un = parsed
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
        return dict(row) if row else None

def get_role(row):
    if not row: return "user"
    if row.get("username") == ADMIN_USERNAME: return "owner"
    if row.get("is_dev"): return "dev"
    if row.get("is_admin"): return "admin"
    if row.get("is_moderator"): return "moderator"
    if row.get("is_streamer"): return "streamer"
    if row.get("is_beta_tester"): return "beta"
    return "user"

def is_premium(row):
    if not row: return False
    if row.get("username") == ADMIN_USERNAME: return True
    tier = row.get("premium_tier")
    if not tier: return False
    exp = row.get("premium_expires")
    if exp and exp < datetime.datetime.now(datetime.timezone.utc): return False
    return tier in ("premium", "pro")

def user_public(row, viewer_id=None):
    status = row.get("online_status") or "online"
    uid = row["id"]
    is_online = uid in online_users and status != "invisible"
    if status == "invisible" and viewer_id != uid: is_online = False
    return {
        "id":row["id"],"username":row["username"],"avatar":row["avatar"],"banner":row["banner"],
        "gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
        "avatar_pos":row["avatar_pos"],"banner_pos":row["banner_pos"],
        "is_admin":row["is_admin"],"is_moderator":row["is_moderator"],
        "is_beta_tester":row.get("is_beta_tester",False),"is_scam":row.get("is_scam",False),
        "is_dev":row.get("is_dev",False),"is_streamer":row.get("is_streamer",False),
        "premium_tier":row.get("premium_tier"),
        "premium_expires":row["premium_expires"].isoformat() if row.get("premium_expires") else None,
        "is_premium":is_premium(row),
        "nickname_color":row.get("nickname_color"),"nickname_gradient":row.get("nickname_gradient"),
        "custom_status":row.get("custom_status"),"online_status":status,
        "bio":row.get("bio"),"fav_music":row.get("fav_music"),
        "coins":row.get("coins",0),"social_rating":row.get("social_rating",0),
        "messages_count":row.get("messages_count",0),"is_legend":row.get("is_legend",False),
        "email":row.get("email"),"email_verified":row.get("email_verified",False),
        "has_admin_pass":bool(row.get("admin_password")),
        "wallpaper":row.get("wallpaper"),"font_choice":row.get("font_choice"),
        "compact_mode":row.get("compact_mode",False),
        "achievements":json.loads(row.get("achievements") or "[]"),
        "quest_points":row.get("quest_points",0),
        "active_frame":row.get("active_frame"),"title":row.get("title"),
        "reputation":row.get("reputation",0),
        "level":row.get("level",1),"xp":row.get("xp",0),
        "created_at":row["created_at"].isoformat() if row.get("created_at") else None,
        "role":get_role(row),"online":is_online
    }

# ============================================================
# ПОДАРКИ / БЛОКИ
# ============================================================
async def get_all_gifts():
    gifts = dict(DEFAULT_GIFTS)
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM custom_gifts WHERE is_sticker=FALSE OR is_sticker IS NULL")
            for r in rows:
                gifts[r["gift_id"]] = {"name":r["name"],"emoji":r["emoji"],"image":r["image"],"gif_image":r.get("gif_image"),"price":r["price"]}
    except: pass
    return gifts

async def is_blocked(user_id, other_id):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)", user_id, other_id)
            return bool(row)
    except: return False

async def has_abuse_access(user):
    if not user: return None
    if user["username"] == ADMIN_USERNAME:
        return {"owner":True,"can_gift":True,"can_nft":True,"can_coins":True,"can_online":True,"can_timer":True,"can_write":True}
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM abuse_grants WHERE user_id=$1 AND expires_at > NOW()", user["id"])
            if row: return dict(row)
    except: pass
    return None

# ============================================================
# АНТИСПАМ / ФЛУД
# ============================================================
async def check_spam(uid):
    now = time.time()
    arr = spam_tracker.get(uid, [])
    arr = [t for t in arr if now - t < 60]
    arr.append(now)
    spam_tracker[uid] = arr
    if len(arr) >= 30:
        spam_tracker[uid] = []
        await log_suspicious(uid, "spam", "30+ сообщений за 60 сек")
        return True
    return False

async def check_flood(uid, text):
    if not text or len(text) < 2: return
    h = hashlib.md5(text.strip().lower().encode()).hexdigest()
    now = time.time()
    arr = flood_tracker.get(uid, [])
    arr = [t for t in arr if now - t[1] < 300 and t[0] == h]
    arr.append((h, now))
    flood_tracker[uid] = arr
    if len(arr) >= 8:
        flood_tracker[uid] = []
        await log_suspicious(uid, "flood", f"8+ одинаковых: {text[:50]}")

async def check_friend_spam(uid, target_id=None):
    now = time.time()
    arr = friend_spam_tracker.get(uid, [])
    arr = [t for t in arr if now - t < 600]
    arr.append(now)
    friend_spam_tracker[uid] = arr
    if len(arr) >= 10:
        friend_spam_tracker[uid] = []
        return True
    if target_id:
        key = (uid, target_id)
        tarr = friend_target_spam.get(key, [])
        tarr = [t for t in tarr if now - t < 600]
        tarr.append(now)
        friend_target_spam[key] = tarr
        if len(tarr) >= 3:
            friend_target_spam[key] = []
            return True
    return False

def cleanup_trackers():
    global last_cleanup
    now = time.time()
    if now - last_cleanup < 300: return
    last_cleanup = now
    for d in (spam_tracker, friend_spam_tracker):
        for k in list(d.keys()):
            arr = [t for t in d[k] if now - t < 600]
            if not arr: del d[k]
            else: d[k] = arr

# ============================================================
# ЛОГИ
# ============================================================
async def log_admin(aid, action, tid, details=""):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO admin_logs(admin_id,action,target_id,details) VALUES($1,$2,$3,$4)", aid, action, tid, details)
    except: pass

async def log_suspicious(uid, action, details=""):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO suspicious_logs(user_id,action,details) VALUES($1,$2,$3)", uid, action, details)
    except: pass

# ============================================================
# EMAIL
# ============================================================
async def send_email(to_email, subject, html):
    if not RESEND_API_KEY: return {"ok":False, "error":"no_key"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post("https://api.resend.com/emails",
                headers={"Authorization":f"Bearer {RESEND_API_KEY}","Content-Type":"application/json"},
                json={"from":"Belugacord <onboarding@resend.dev>","to":[to_email],"subject":subject,"html":html},
                timeout=15)
            if r.status_code in (200, 201): return {"ok":True}
            return {"ok":False, "error":r.text}
    except Exception as e: return {"ok":False, "error":str(e)}

# ============================================================
# ДОСТИЖЕНИЯ / XP / КВЕСТЫ
# ============================================================
async def grant_achievement(uid, key):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            row = await conn.fetchrow("SELECT achievements FROM users WHERE id=$1", uid)
            if not row: return False
            arr = json.loads(row["achievements"] or "[]")
            if key in arr or key not in ACHIEVEMENTS: return False
            arr.append(key)
            await conn.execute("UPDATE users SET achievements=$1, coins=coins+50 WHERE id=$2", json.dumps(arr), uid)
            return True
    except: return False

def apply_event_multiplier(base, event_type):
    mult = base
    now = datetime.datetime.now(datetime.timezone.utc)
    for e in active_events:
        if e.get("active") and e.get("event_type") == event_type:
            if e.get("end_at") and e["end_at"] > now:
                mult = base * e.get("multiplier", 1)
    return mult

async def grant_xp(uid, amount):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            row = await conn.fetchrow("SELECT xp,level FROM users WHERE id=$1", uid)
            if not row: return
            amount = apply_event_multiplier(amount, "xp_x")
            new_xp = row["xp"] + amount
            new_level = row["level"]
            while new_xp >= (new_level * 100):
                new_xp -= new_level * 100
                new_level += 1
                await manager.send_to(uid, {"type":"level_up","level":new_level})
            await conn.execute("UPDATE users SET xp=$1,level=$2 WHERE id=$3", new_xp, new_level, uid)
    except: pass

def get_today_key():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

QUEST_TEMPLATES = [
    {"key":"send_10_msgs","name":"Болтун дня","desc":"Отправь 10 сообщений","goal":10,"reward_kp":50,"emoji":"💬"},
    {"key":"play_3_games","name":"Игрок дня","desc":"Сыграй 3 игры","goal":3,"reward_kp":80,"emoji":"🎮"},
    {"key":"send_5_dms","name":"Личка дня","desc":"Отправь 5 DM","goal":5,"reward_kp":60,"emoji":"✉️"},
    {"key":"open_1_case","name":"Лудоман дня","desc":"Открой 1 кейс","goal":1,"reward_kp":100,"emoji":"🎁"},
    {"key":"give_gift","name":"Щедрый дня","desc":"Подари 1 подарок","goal":1,"reward_kp":120,"emoji":"🎀"},
]

async def grant_quest_progress(uid, quest_key, amount=1):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            row = await conn.fetchrow("SELECT quest_day,quest_progress,quest_claimed FROM users WHERE id=$1", uid)
            if not row: return
            today = get_today_key()
            prog = json.loads(row["quest_progress"] or "{}")
            claimed = json.loads(row["quest_claimed"] or "[]")
            if row["quest_day"] != today:
                prog = {}; claimed = []; day = today
            else:
                day = row["quest_day"]
            prog[quest_key] = prog.get(quest_key, 0) + amount
            tpl = next((q for q in QUEST_TEMPLATES if q["key"] == quest_key), None)
            reward = 0
            if tpl and prog[quest_key] >= tpl["goal"] and quest_key not in claimed:
                reward = tpl["reward_kp"]
                claimed.append(quest_key)
                await conn.execute("UPDATE users SET quest_points=quest_points+$1 WHERE id=$2", reward, uid)
            await conn.execute("UPDATE users SET quest_day=$1,quest_progress=$2,quest_claimed=$3 WHERE id=$4",
                day, json.dumps(prog), json.dumps(claimed), uid)
            return reward
    except Exception as e: print(f"quest: {e}")

async def check_daily_bonus(uid):
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            row = await conn.fetchrow("SELECT daily_bonus_at FROM users WHERE id=$1", uid)
            if not row: return {"ok":False, "reason":"no_user"}
            now = datetime.datetime.now(datetime.timezone.utc)
            last = row["daily_bonus_at"]
            if last and (now - last).total_seconds() < 86400:
                return {"ok":False, "reason":"already", "next_in":int(86400-(now-last).total_seconds())}
            bonus = 1
            u = await conn.fetchrow("SELECT premium_tier,premium_expires FROM users WHERE id=$1", uid)
            prem = False
            if u and u["premium_tier"] and (not u["premium_expires"] or u["premium_expires"] > now):
                prem = True; bonus = 3
            await conn.execute("UPDATE users SET coins=coins+$1,daily_bonus_at=$2 WHERE id=$3", bonus, now, uid)
            return {"ok":True, "amount":bonus, "premium":prem}
    except Exception as e: return {"ok":False, "reason":str(e)}

# ============================================================
# WS MANAGER
# ============================================================
class ConnectionManager:
    def __init__(self): self.connections = {}
    async def connect(self, uid, ws):
        await ws.accept()
        self.connections.setdefault(uid, []).append(ws)
        online_users.add(uid)
    def disconnect(self, uid, ws):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except ValueError: pass
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
    async def kick(self, uid):
        for ws in list(self.connections.get(uid, [])):
            try: await ws.close()
            except: pass
        self.connections.pop(uid, None)
        online_users.discard(uid)

manager = ConnectionManager()

# ============================================================
# WS ОБРАБОТКА СООБЩЕНИЙ
# ============================================================
async def handle_ws_message(uid, user, raw):
    cleanup_trackers()
    try: data = json.loads(raw)
    except: return
    t = data.get("type")
    is_muted = False
    if user.get("mute_until"):
        try:
            mu = user["mute_until"]
            if mu and mu > datetime.datetime.now(datetime.timezone.utc): is_muted = True
        except: pass
    if t in ("message","dm","group_msg","sticker") and is_muted:
        await manager.send_to(uid, {"type":"muted","reason":"Ты в муте"})
        return

    if t == "message":
        ch = data.get("channel_id"); text = (data.get("text") or "")[:2000]
        furl = data.get("file_url"); tid = data.get("temp_id"); reply = data.get("reply_to")
        effect = data.get("effect", "none")
        if not ch: return
        if text.startswith("/"):
            cmd_name = text[1:].split()[0].lower()
            p = await get_pool()
            async with p.acquire() as conn:
                cr = await conn.fetchrow("SELECT response FROM commands WHERE name=$1", cmd_name)
            if cr:
                await manager.send_to(uid, {"type":"dm","from_user":0,"to_user":uid,"username":"🤖 Belugacord","text":cr["response"],"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"is_bot":True})
                return
        await check_spam(uid)
        await check_flood(uid, text)
        p = await get_pool()
        async with p.acquire() as conn:
            chan = await conn.fetchrow("SELECT mode,server_id FROM channels WHERE id=$1", int(ch))
            if chan and chan["mode"] == "readonly":
                srv = await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1", chan["server_id"])
                if srv and srv["owner_id"] != uid and user["username"] != ADMIN_USERNAME:
                    await manager.send_to(uid, {"type":"muted","reason":"Канал только для чтения"})
                    return
            msg = await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,reply_to,effect) VALUES($1,$2,$3,$4,$5,$6) RETURNING *",
                int(ch), uid, text, furl, reply, effect)
            await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1", uid)
            mc = await conn.fetchval("SELECT messages_count FROM users WHERE id=$1", uid)
            members = await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1", int(ch))
            await conn.execute("UPDATE channels SET last_message_at=NOW() WHERE id=$1", int(ch))
        if mc == 1: await grant_achievement(uid, "first_msg")
        if mc == 100: await grant_achievement(uid, "msg_100")
        if mc == 1000: await grant_achievement(uid, "msg_1000")
        if mc == 10000: await grant_achievement(uid, "msg_10000")
        await grant_quest_progress(uid, "send_10_msgs", 1)
        await grant_xp(uid, 1)
        payload = {"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,
            "username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),
            "avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"reply_to":reply,"effect":effect,
            "created_at":msg["created_at"].isoformat(),"is_admin":user.get("is_admin"),
            "is_moderator":user.get("is_moderator"),"is_beta_tester":user.get("is_beta_tester"),
            "is_scam":user.get("is_scam"),"is_streamer":user.get("is_streamer"),
            "is_premium":is_premium(user),"active_frame":user.get("active_frame"),
            "title":user.get("title"),"role":get_role(user),"temp_id":tid}
        for m in members: await manager.send_to(m["user_id"], payload)

    elif t == "dm":
        to_id = int(data.get("to_user", 0)); text = (data.get("text") or "")[:2000]
        furl = data.get("file_url"); tid = data.get("temp_id")
        if await is_blocked(uid, to_id): return
        p = await get_pool()
        async with p.acquire() as conn:
            msg = await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url) VALUES($1,$2,$3,$4) RETURNING *", uid, to_id, text, furl)
        await grant_quest_progress(uid, "send_5_dms", 1)
        await grant_xp(uid, 1)
        payload = {"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,
            "username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),
            "avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,
            "created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),
            "active_frame":user.get("active_frame"),"title":user.get("title"),"temp_id":tid}
        await manager.send_to(to_id, payload)
        await manager.send_to(uid, payload)

    elif t == "group_msg":
        gid = int(data.get("group_id", 0)); text = (data.get("text") or "")[:2000]
        furl = data.get("file_url"); tid = data.get("temp_id")
        p = await get_pool()
        async with p.acquire() as conn:
            m = await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2", gid, uid)
            if not m: return
            msg = await conn.fetchrow("INSERT INTO group_messages(group_id,user_id,text,file_url) VALUES($1,$2,$3,$4) RETURNING *", gid, uid, text, furl)
            members = await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1", gid)
            await conn.execute("UPDATE groups SET last_message_at=NOW() WHERE id=$1", gid)
        payload = {"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,
            "username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),
            "avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,
            "created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),
            "active_frame":user.get("active_frame"),"title":user.get("title"),"temp_id":tid}
        for m in members: await manager.send_to(m["user_id"], payload)

    elif t == "sticker":
        gid = int(data.get("group_id", 0)) if data.get("group_id") else None
        ch = int(data.get("channel_id", 0)) if data.get("channel_id") else None
        sticker = data.get("sticker")
        if not sticker: return
        payload = {"type":"sticker","sticker":sticker,"user_id":uid,"username":user["username"],
            "channel_id":ch,"group_id":gid,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
        if ch:
            p = await get_pool()
            async with p.acquire() as conn:
                members = await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1", ch)
            for m in members: await manager.send_to(m["user_id"], payload)
        elif gid:
            p = await get_pool()
            async with p.acquire() as conn:
                members = await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1", gid)
            for m in members: await manager.send_to(m["user_id"], payload)

    elif t == "typing":
        ch = data.get("channel_id")
        p = await get_pool()
        async with p.acquire() as conn:
            members = await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1", int(ch))
        for m in members:
            if m["user_id"] != uid:
                await manager.send_to(m["user_id"], {"type":"typing","channel_id":ch,"username":user["username"]})

    elif t == "typing_dm":
        await manager.send_to(int(data.get("to_user", 0)), {"type":"typing_dm","from":uid,"username":user["username"]})

    elif t == "call_offer":
        await manager.send_to(int(data.get("to", 0)), {"type":"call_offer","from":uid,"sdp":data.get("sdp"),"username":user["username"],"avatar":user.get("avatar")})
    elif t == "call_answer":
        await manager.send_to(int(data.get("to", 0)), {"type":"call_answer","from":uid,"sdp":data.get("sdp")})
    elif t == "call_ice":
        await manager.send_to(int(data.get("to", 0)), {"type":"call_ice","from":uid,"candidate":data.get("candidate")})
    elif t == "call_decline":
        await manager.send_to(int(data.get("to", 0)), {"type":"call_decline","from":uid})
    elif t == "call_end":
        await manager.send_to(int(data.get("to", 0)), {"type":"call_end","from":uid})

# ============================================================
# ФОНОВЫЕ LOOP'Ы
# ============================================================
async def lottery_draw_loop():
    while True:
        try:
            await asyncio.sleep(3600)
            p = await get_pool()
            async with p.acquire() as conn:
                rows = await conn.fetch("SELECT user_id,tickets FROM lottery WHERE tickets>0")
                if not rows: continue
                pool_tickets = []
                for r in rows: pool_tickets.extend([r["user_id"]] * r["tickets"])
                if not pool_tickets: continue
                winner = random.choice(pool_tickets)
                total = sum(r["tickets"] for r in rows) * 100
                jackpot = int(total * 0.7)
                w = await conn.fetchrow("SELECT username FROM users WHERE id=$1", winner)
                if w:
                    await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", jackpot, winner)
                    await conn.execute("INSERT INTO lottery_history(winner_id,winner_name,amount) VALUES($1,$2,$3)", winner, w["username"], jackpot)
                    await conn.execute("DELETE FROM lottery")
                    await manager.send_to(winner, {"type":"coins_approved","amount":jackpot})
                    await manager.broadcast({"type":"event","event":"confetti"})
        except Exception as e:
            print(f"Lottery: {e}")
            await asyncio.sleep(60)

async def events_cleanup_loop():
    while True:
        try:
            await asyncio.sleep(30)
            p = await get_pool()
            async with p.acquire() as conn:
                rows = await conn.fetch("SELECT id FROM events WHERE active=TRUE AND end_at<=NOW()")
                for r in rows:
                    await conn.execute("UPDATE events SET active=FALSE WHERE id=$1", r["id"])
                    for e in active_events:
                        if e["id"] == r["id"]: e["active"] = False
                    await manager.broadcast({"type":"event_end","id":r["id"]})
        except Exception as e:
            print(f"Events: {e}")
            await asyncio.sleep(60)

async def startup_tasks():
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM events WHERE active=TRUE AND end_at>NOW()")
            for r in rows:
                active_events.append({"id":r["id"],"name":r["name"],"description":r["description"],
                    "emoji":r["emoji"],"event_type":r["event_type"],"multiplier":r["multiplier"],
                    "end_at":r["end_at"],"active":True})
    except Exception as e:
        print(f"Startup: {e}")
    asyncio.create_task(lottery_draw_loop())
    asyncio.create_task(events_cleanup_loop())
    print("🐱 Background loops started")

# ============================================================
# INIT DB
# ============================================================
async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE NOT NULL,password_hash VARCHAR(128) NOT NULL,avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,email_code VARCHAR(16),email_code_expires TIMESTAMP,email_code_attempts INTEGER DEFAULT 0,is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,is_beta_tester BOOLEAN DEFAULT FALSE,is_scam BOOLEAN DEFAULT FALSE,is_dev BOOLEAN DEFAULT FALSE,is_streamer BOOLEAN DEFAULT FALSE,premium_tier VARCHAR(8),premium_expires TIMESTAMP,is_banned BOOLEAN DEFAULT FALSE,ban_reason VARCHAR(256),mute_until TIMESTAMP,nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),custom_status VARCHAR(128),online_status VARCHAR(16) DEFAULT 'online',bio VARCHAR(256),fav_music VARCHAR(128),coins INTEGER DEFAULT 0,social_rating INTEGER DEFAULT 0,messages_count INTEGER DEFAULT 0,wallpaper TEXT,font_choice VARCHAR(32),compact_mode BOOLEAN DEFAULT FALSE,achievements TEXT DEFAULT '[]',quest_points INTEGER DEFAULT 0,daily_bonus_at TIMESTAMP,quest_day VARCHAR(16),quest_progress TEXT DEFAULT '{}',quest_claimed TEXT DEFAULT '[]',active_frame VARCHAR(32),frame_owned TEXT DEFAULT '[]',title VARCHAR(32),reputation INTEGER DEFAULT 0,level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,chest_streak INTEGER DEFAULT 0,chest_at TIMESTAMP,bank_deposit INTEGER DEFAULT 0,bank_at TIMESTAMP,admin_password VARCHAR(128),referred_by VARCHAR(32),last_seen TIMESTAMP DEFAULT NOW(),created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1", ADMIN_USERNAME)
        # ... и дальше все таблицы как в 2.4 (сократил для краткости)
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER,user_id INTEGER,text TEXT,file_url TEXT,reply_to INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,effect VARCHAR(16) DEFAULT 'none',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER,to_user INTEGER,gift VARCHAR(32),created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        # ... остальные таблицы — как в 2.4 server.py
        print("🐱 DB initialized")