import os,json,time,secrets,hashlib,random,datetime,asyncio
from typing import Optional
import asyncpg
import httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL=os.environ.get("DATABASE_URL","")
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2026")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","")
ADMIN_USERNAME="_fan_beluga_"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="2.2"

# === ЛИМИТЫ (для премиума и pro, но БЕЗ урезания обычных — только размер файла) ===
LIMITS={
  None:{"file":10*1024*1024,"msg":2000,"servers":10,"channels":20,"groups":10},
  "premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100,"groups":30},
  "pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999,"groups":30}
}

# === КУРС ПРЕМИУМА ===
PREMIUM_PRICES={
  "month":1500,        # 1 мес = 1500 🏅
  "year":18000,        # 1 год = 18000 🏅
}
QUEST_EXCHANGE={
  "1day":{"cost":1400,"days":1},
  "3days":{"cost":7500,"days":3},
  "7days":{"cost":10000,"days":7},
}

DEFAULT_GIFTS={"rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},"cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},"crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},"legend":{"name":"Легендарка","emoji":"💠","price":5000},"alien":{"name":"Инопланетянин","emoji":"👽","price":10000},"galaxy":{"name":"Галактика","emoji":"🌌","price":100000},"goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},"universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000}}

EASTER_EGGS=["song","cat","beluga"]
GAME_LIST=["penguin","minesweeper","snake","2048","flappy","tetris","memory","reaction","tictactoe","rps","battleship","duel","freedoom"]
ACHIEVEMENTS={"first_msg":{"name":"Первое слово","emoji":"💬","desc":"Отправь первое сообщение"},"msg_100":{"name":"Болтун","emoji":"🗣️","desc":"100 сообщений"},"msg_1000":{"name":"Оратор","emoji":"🎤","desc":"1000 сообщений"},"msg_10000":{"name":"Легенда чата","emoji":"📢","desc":"10000 сообщений"},"first_friend":{"name":"Дружелюбный","emoji":"👥","desc":"Первый друг"},"friend_10":{"name":"Тусовщик","emoji":"🎉","desc":"10 друзей"},"first_gift":{"name":"Щедрый","emoji":"🎁","desc":"Первый подарок"},"first_nft":{"name":"Коллекционер","emoji":"🎨","desc":"Первый NFT"},"snake_100":{"name":"Змеелов","emoji":"🐍","desc":"100 очков в Змейке"},"flappy_50":{"name":"Летун","emoji":"🐦","desc":"50 очков в Flappy"},"first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},"coins_10k":{"name":"Богач","emoji":"💰","desc":"10000 бекоинов"},"rating_100":{"name":"Щедрая душа","emoji":"💎","desc":"Соц.рейтинг 100"},"rating_10000":{"name":"Меценат","emoji":"👑","desc":"Соц.рейтинг 10000"}}

CHANGELOG={
"2.2":{"title":"Belugacord Beta 2.2","items":[
  "🐛 Фикс: планировщик абьюза (падал)",
  "🐛 Фикс: мутнутые могли писать в чат",
  "🐛 Фикс: забаненные не отключались от WS",
  "🐛 Фикс: правка/реакция при ошибке летели в чат",
  "🐛 Фикс: DM читались после блокировки",
  "🐛 Фикс: спам friend-заявок одному юзеру",
  "🐛 Фикс: утечка памяти flood_tracker",
  "🐛 Фикс: мёртвые WS-сокеты копились",
  "🐛 Фикс: список чатов не показывал последние",
  "🐛 Фикс: время захода с 3 часов",
  "💰 Ежедневный бонус: 1 бекоин",
  "⬆️ Апгрейдер подарков (3→1)",
  "🖼️ GIF-аватарки и GIF-баннеры",
  "👥 Группы: 10 обычным, 30 премиум",
  "📞 Групповые звонки до 30 (SFU-lite)",
  "📋 Ежедневные квесты + КП",
  "💎 Обмен КП → премиум (1400/7500/10000)",
  "💎 Премиум за 🏅 (1500 мес / 18000 год)",
  "🎁 Продажа подарков за 100% цены",
  "🎮 itch.io плашка в звонке",
  "💀 FREEDOOM (кнопка + плашка)",
  "🎨 Рамки аватара",
]},
"2.1":{"title":"Belugacord Beta 2.1","items":["🐛 Фикс звонков (звук собеседника)","🎥 Привилегия Стример","✍️ Абьюз: написать всем + старт","🔊 Отдельный аудио-канал для звонков","🌐 TURN-сервер для NAT","📊 ICE-логи","✨ Мелкие фиксы"]},
"2.0":{"title":"Belugacord Beta 2.0","items":["📞 Новые звонки: плашка сверху","💬 Чат видно при звонке","👍 Социальный рейтинг","📧 Верификация email","🎮 4 новые игры","🌈 Свои темы и обои","👤 Подпись до 64 символов"]},
"1.9":{"title":"Belugacord Beta 1.9","items":["🎨 Тема CS 1.6","👥 Группы","💬 Reply, пин, поиск","😴 Статусы","🚫 Блок-лист","🏆 Достижения","💰 Рынок NFT","🎁 Кейсы"]}}

app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def no_cache_api(request:Request,call_next):
    r=await call_next(request)
    if request.url.path.startswith("/api/"):
        r.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
        r.headers["Pragma"]="no-cache"
    return r

app.mount("/uploads",StaticFiles(directory=UPLOAD_DIR),name="uploads")
pool=None
online_users=set()
user_status={}
active_tournament={"game":None,"started_at":None}
spam_tracker={}
friend_spam_tracker={}
friend_target_spam={}   # НОВОЕ: per-target
flood_tracker={}
abuse_timer_task=None
last_cleanup=time.time()

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=5)
    return pool

async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE NOT NULL,password_hash VARCHAR(128) NOT NULL,avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,email_code VARCHAR(16),email_code_expires TIMESTAMP,is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,is_beta_tester BOOLEAN DEFAULT FALSE,is_scam BOOLEAN DEFAULT FALSE,is_dev BOOLEAN DEFAULT FALSE,is_streamer BOOLEAN DEFAULT FALSE,premium_tier VARCHAR(8),premium_expires TIMESTAMP,is_banned BOOLEAN DEFAULT FALSE,ban_reason VARCHAR(256),mute_until TIMESTAMP,nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),custom_status VARCHAR(128),online_status VARCHAR(16) DEFAULT 'online',bio VARCHAR(256),fav_music VARCHAR(128),gifts_hidden BOOLEAN DEFAULT FALSE,easter_found TEXT DEFAULT '[]',easter_rewarded BOOLEAN DEFAULT FALSE,admin_password VARCHAR(128),coins INTEGER DEFAULT 0,social_rating INTEGER DEFAULT 0,messages_count INTEGER DEFAULT 0,frozen BOOLEAN DEFAULT FALSE,is_legend BOOLEAN DEFAULT FALSE,wallpaper TEXT,font_choice VARCHAR(32),compact_mode BOOLEAN DEFAULT FALSE,achievements TEXT DEFAULT '[]',quest_points INTEGER DEFAULT 0,daily_bonus_at TIMESTAMP,quest_day VARCHAR(16),quest_progress TEXT DEFAULT '{}',quest_claimed TEXT DEFAULT '[]',active_frame VARCHAR(32),frame_owned TEXT DEFAULT '[]',last_seen TIMESTAMP DEFAULT NOW(),created_at TIMESTAMP DEFAULT NOW())""")
        for c,t in [("premium_expires","TIMESTAMP"),("gif_avatar","TEXT"),("gif_banner","TEXT"),("quest_points","INTEGER DEFAULT 0"),("daily_bonus_at","TIMESTAMP"),("quest_day","VARCHAR(16)"),("quest_progress","TEXT DEFAULT '{}'"),("quest_claimed","TEXT DEFAULT '[]'"),("active_frame","VARCHAR(32)"),("frame_owned","TEXT DEFAULT '[]'")]:
            try: await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {c} {t}")
            except: pass
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,banner TEXT,description TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        for c,t in [("last_message_at","TIMESTAMP")]:
            try: await conn.execute(f"ALTER TABLE channels ADD COLUMN IF NOT EXISTS {c} {t}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,reply_to INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,gif_avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        for c,t in [("last_message_at","TIMESTAMP"),("gif_avatar","TEXT")]:
            try: await conn.execute(f"ALTER TABLE groups ADD COLUMN IF NOT EXISTS {c} {t}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_appeals(id SERIAL PRIMARY KEY,username VARCHAR(32),text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS reports(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,coins INTEGER NOT NULL,price INTEGER DEFAULT 0,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,gif_image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        for c,t in [("gif_image","TEXT")]:
            try: await conn.execute(f"ALTER TABLE custom_gifts ADD COLUMN IF NOT EXISTS {c} {t}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_market(id SERIAL PRIMARY KEY,item_id INTEGER REFERENCES nft_items(id) ON DELETE CASCADE,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,price INTEGER NOT NULL,status VARCHAR(16) DEFAULT 'active',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),item_image TEXT,chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_opens(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,prize_text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS abuse_grants(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,can_gift BOOLEAN DEFAULT TRUE,can_nft BOOLEAN DEFAULT TRUE,can_coins BOOLEAN DEFAULT TRUE,can_online BOOLEAN DEFAULT TRUE,can_timer BOOLEAN DEFAULT TRUE,can_write BOOLEAN DEFAULT TRUE,expires_at TIMESTAMP NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_tournament(id SERIAL PRIMARY KEY,game VARCHAR(32),started_at TIMESTAMP DEFAULT NOW(),active BOOLEAN DEFAULT FALSE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_requests(id SERIAL PRIMARY KEY,from_admin INTEGER REFERENCES users(id) ON DELETE SET NULL,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,reason TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS suspicious_logs(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,action VARCHAR(64),details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS auto_abuse(id SERIAL PRIMARY KEY,enabled BOOLEAN DEFAULT FALSE,kind VARCHAR(16),every_minutes INTEGER DEFAULT 60,next_run TIMESTAMP,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS owner_messages(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS notifications(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,kind VARCHAR(32),text TEXT,is_read BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_themes(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),vars TEXT,bg_image TEXT,border_radius VARCHAR(16),blur VARCHAR(32),created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS spam_alerts(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text_sample TEXT,count INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        # === НОВЫЕ ТАБЛИЦЫ 2.2 ===
        await conn.execute("""CREATE TABLE IF NOT EXISTS premium_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,bought_at TIMESTAMP DEFAULT NOW(),tier VARCHAR(8),days INTEGER,paid_coins INTEGER,method VARCHAR(16))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS quests_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,quest_key VARCHAR(32),reward_kp INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS upgrade_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,from_gift VARCHAR(32),to_gift VARCHAR(32),created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_rooms(id SERIAL PRIMARY KEY,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,room_code VARCHAR(16) UNIQUE,is_group BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT NOW(),closed_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_participants(room_id INTEGER REFERENCES call_rooms(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(room_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),css TEXT,is_animated BOOLEAN DEFAULT FALSE,is_premium BOOLEAN DEFAULT FALSE,price_coins INTEGER DEFAULT 0,price_kp INTEGER DEFAULT 0)""")
        # Заполняем рамки по умолчанию
        for f in [
            ("none","Без рамки","","none",False,False,0,0),
            ("gold","Золотая","👑","2px solid #ffd700;box-shadow:0 0 12px rgba(255,215,0,0.7)",False,False,500,0),
            ("fire","Огненная","🔥","2px solid #ff6b35;box-shadow:0 0 14px rgba(255,107,53,0.8)",False,False,800,0),
            ("ice","Ледяная","❄️","2px solid #22d3ee;box-shadow:0 0 14px rgba(34,211,238,0.8)",False,False,800,0),
            ("rainbow","Радужная","🌈","2px solid #d946ef;box-shadow:0 0 16px rgba(217,70,239,0.8)",False,True,0,3000),
            ("neon","Неоновая","💜","2px solid #ff00ff;box-shadow:0 0 18px rgba(255,0,255,0.9)",False,True,0,3000),
            ("pulse","Пульс","💗","2px solid #ec4899;animation:framePulse 1.5s infinite",True,True,0,5000),
            ("spin","Вращение","🌀","2px solid #22c55e;animation:frameSpin 3s linear infinite",True,True,0,5000),
        ]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,css,is_animated,is_premium,price_coins,price_kp) VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (frame_id) DO NOTHING",*f)
            except: pass

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e: print(f"DB init: {e}")

# ===== ХЕЛПЕРЫ =====
def hash_password(p):
    s=secrets.token_hex(16)
    return f"{s}${hashlib.sha256((s+p).encode()).hexdigest()}"
def verify_password(p,st):
    try:
        s,h=st.split("$",1)
        return hashlib.sha256((s+p).encode()).hexdigest()==h
    except: return False
def make_token(uid,un):
    d=f"{uid}:{un}:{int(time.time())}"
    return f"{d}:{hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]}"
def parse_token(t):
    try:
        parts=t.split(":")
        if len(parts)!=4: return None
        uid,un,ts,sig=parts
        d=f"{uid}:{un}:{ts}"
        if sig!=hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]: return None
        return int(uid),un
    except: return None

async def get_current_user(token):
    parsed=parse_token(token)
    if not parsed: return None
    uid,un=parsed
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE id=$1",uid)
        return dict(row) if row else None

async def log_admin(aid,action,tid,details=""):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO admin_logs(admin_id,action,target_id,details) VALUES($1,$2,$3,$4)",aid,action,tid,details)
    except: pass

async def log_suspicious(uid,action,details=""):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO suspicious_logs(user_id,action,details) VALUES($1,$2,$3)",uid,action,details)
    except: pass

async def alert_spam(uid,text_sample,count):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO spam_alerts(user_id,text_sample,count) VALUES($1,$2,$3)",uid,text_sample[:200],count)
            admins=await conn.fetch("SELECT id FROM users WHERE is_admin=TRUE OR is_moderator=TRUE OR username=$1",ADMIN_USERNAME)
        for a in admins:
            await manager.send_to(a["id"],{"type":"spam_alert","user_id":uid,"text":text_sample[:80],"count":count})
    except: pass

async def send_email(to_email,subject,html):
    if not RESEND_API_KEY: return {"ok":False,"error":"no_key"}
    try:
        async with httpx.AsyncClient() as client:
            r=await client.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {RESEND_API_KEY}","Content-Type":"application/json"},json={"from":"Belugacord <onboarding@resend.dev>","to":[to_email],"subject":subject,"html":html},timeout=15)
            if r.status_code in (200,201): return {"ok":True}
            return {"ok":False,"error":r.text}
    except Exception as e: return {"ok":False,"error":str(e)}

async def grant_achievement(uid,key):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT achievements FROM users WHERE id=$1",uid)
            if not row: return False
            arr=json.loads(row["achievements"] or "[]")
            if key in arr: return False
            if key not in ACHIEVEMENTS: return False
            arr.append(key)
            await conn.execute("UPDATE users SET achievements=$1,coins=coins+50 WHERE id=$2",json.dumps(arr),uid)
            return True
    except: return False

def get_role(row):
    if not row: return "user"
    if row.get("username")==ADMIN_USERNAME: return "owner"
    if row.get("is_dev"): return "dev"
    if row.get("is_admin"): return "admin"
    if row.get("is_moderator"): return "moderator"
    if row.get("is_streamer"): return "streamer"
    if row.get("is_beta_tester"): return "beta"
    return "user"

def is_premium(row):
    if not row: return False
    if row.get("username")==ADMIN_USERNAME: return True
    tier=row.get("premium_tier")
    if not tier: return False
    exp=row.get("premium_expires")
    if exp and exp<datetime.datetime.now(datetime.timezone.utc): return False
    return tier in ("premium","pro")

def user_public(row,viewer_id=None):
    status=row.get("online_status") or "online"
    uid=row["id"]
    is_online=uid in online_users and status!="invisible"
    if status=="invisible" and viewer_id!=uid: is_online=False
    premium=is_premium(row)
    return {"id":row["id"],"username":row["username"],"avatar":row["avatar"],"banner":row["banner"],
            "gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
            "avatar_pos":row["avatar_pos"],"banner_pos":row["banner_pos"],
            "is_admin":row["is_admin"],"is_moderator":row["is_moderator"],
            "is_beta_tester":row.get("is_beta_tester",False),"is_scam":row.get("is_scam",False),
            "is_dev":row.get("is_dev",False),"is_streamer":row.get("is_streamer",False),
            "premium_tier":row.get("premium_tier"),"premium_expires":row["premium_expires"].isoformat() if row.get("premium_expires") else None,
            "is_premium":premium,
            "nickname_color":row.get("nickname_color"),"nickname_gradient":row.get("nickname_gradient"),
            "custom_status":row.get("custom_status"),"online_status":status,"bio":row.get("bio"),
            "fav_music":row.get("fav_music"),"coins":row.get("coins",0),"social_rating":row.get("social_rating",0),
            "messages_count":row.get("messages_count",0),"is_legend":row.get("is_legend",False),
            "email":row.get("email"),"email_verified":row.get("email_verified",False),
            "has_admin_pass":bool(row.get("admin_password")),"wallpaper":row.get("wallpaper"),
            "font_choice":row.get("font_choice"),"compact_mode":row.get("compact_mode",False),
            "achievements":json.loads(row.get("achievements") or "[]"),
            "quest_points":row.get("quest_points",0),
            "active_frame":row.get("active_frame"),
            "created_at":row["created_at"].isoformat() if row.get("created_at") else None,
            "role":get_role(row),"online":is_online}

async def get_all_gifts():
    gifts=dict(DEFAULT_GIFTS)
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM custom_gifts WHERE is_sticker=FALSE OR is_sticker IS NULL")
            for r in rows: gifts[r["gift_id"]]={"name":r["name"],"emoji":r["emoji"],"image":r["image"],"gif_image":r.get("gif_image"),"price":r["price"]}
    except: pass
    return gifts

async def is_blocked(user_id,other_id):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT id FROM blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user_id,other_id)
            return bool(row)
    except: return False

async def has_abuse_access(user):
    if not user: return None
    if user["username"]==ADMIN_USERNAME: return {"owner":True,"can_gift":True,"can_nft":True,"can_coins":True,"can_online":True,"can_timer":True,"can_write":True}
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT * FROM abuse_grants WHERE user_id=$1 AND expires_at > NOW()",user["id"])
            if row: return dict(row)
    except: pass
    return None

async def check_spam(uid):
    now=time.time()
    arr=spam_tracker.get(uid,[])
    arr=[t for t in arr if now-t<60]
    arr.append(now)
    spam_tracker[uid]=arr
    if len(arr)>=30:
        spam_tracker[uid]=[]
        await log_suspicious(uid,"spam","30+ сообщений за 60 сек")
        return True
    return False

async def check_flood(uid,text):
    if not text or len(text)<2: return
    h=hashlib.md5(text.strip().lower().encode()).hexdigest()
    now=time.time()
    arr=flood_tracker.get(uid,[])
    arr=[t for t in arr if now-t[1]<300 and t[0]==h]
    arr.append((h,now))
    flood_tracker[uid]=arr
    if len(arr)>=8:
        flood_tracker[uid]=[]
        await log_suspicious(uid,"flood",f"8+ одинаковых: {text[:50]}")
        await alert_spam(uid,text,len(arr))

async def check_friend_spam(uid,target_id=None):
    """FIX: per-target spam friend-заявок"""
    now=time.time()
    arr=friend_spam_tracker.get(uid,[])
    arr=[t for t in arr if now-t<600]
    arr.append(now)
    friend_spam_tracker[uid]=arr
    if len(arr)>=10:
        friend_spam_tracker[uid]=[]
        await log_suspicious(uid,"friend_spam","10+ заявок за 10 мин")
        return True
    if target_id:
        key=(uid,target_id)
        tarr=friend_target_spam.get(key,[])
        tarr=[t for t in tarr if now-t<600]
        tarr.append(now)
        friend_target_spam[key]=tarr
        if len(tarr)>=3:
            friend_target_spam[key]=[]
            await log_suspicious(uid,"friend_target_spam",f"3+ заявки юзеру {target_id}")
            return True
    return False

def cleanup_trackers():
    """FIX: TTL-очистка трекеров"""
    global last_cleanup
    now=time.time()
    if now-last_cleanup<300: return
    last_cleanup=now
    for d in (spam_tracker,friend_spam_tracker):
        for k in list(d.keys()):
            arr=[t for t in d[k] if now-t<600]
            if not arr: del d[k]
            else: d[k]=arr
    for k in list(friend_target_spam.keys()):
        arr=[t for t in friend_target_spam[k] if now-t<600]
        if not arr: del friend_target_spam[k]
        else: friend_target_spam[k]=arr
    for k in list(flood_tracker.keys()):
        arr=[t for t in flood_tracker[k] if now-t[1]<300]
        if not arr: del flood_tracker[k]
        else: flood_tracker[k]=arr

async def add_last_message_at(conn,channel_id=None,group_id=None,dm_to=None):
    """FIX: обновляем last_message_at для сортировки чатов"""
    now=datetime.datetime.now(datetime.timezone.utc)
    if channel_id:
        await conn.execute("UPDATE channels SET last_message_at=$1 WHERE id=$2",now,channel_id)
    if group_id:
        await conn.execute("UPDATE groups SET last_message_at=$1 WHERE id=$2",now,group_id)
    # для DM — не храним отдельно, но можно — при желании

# === КВЕСТЫ (шаблоны) ===
QUEST_TEMPLATES=[
    {"key":"send_10_msgs","name":"Болтун дня","desc":"Отправь 10 сообщений","goal":10,"reward_kp":50,"emoji":"💬"},
    {"key":"play_3_games","name":"Игрок дня","desc":"Сыграй 3 игры","goal":3,"reward_kp":80,"emoji":"🎮"},
    {"key":"send_5_dms","name":"Личка дня","desc":"Отправь 5 DM","goal":5,"reward_kp":60,"emoji":"✉️"},
    {"key":"open_1_case","name":"Лудоман дня","desc":"Открой 1 кейс","goal":1,"reward_kp":100,"emoji":"🎁"},
    {"key":"give_gift","name":"Щедрый дня","desc":"Подари 1 подарок","goal":1,"reward_kp":120,"emoji":"🎀"},
]

def get_today_key():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

async def grant_quest_progress(uid,quest_key,amount=1):
    """Начисляем прогресс квеста + награду КП"""
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT quest_day,quest_progress,quest_claimed FROM users WHERE id=$1",uid)
            if not row: return
            today=get_today_key()
            prog=json.loads(row["quest_progress"] or "{}")
            claimed=json.loads(row["quest_claimed"] or "[]")
            if row["quest_day"]!=today:
                prog={}; claimed=[]; day=today
            else:
                day=row["quest_day"]
            prog[quest_key]=prog.get(quest_key,0)+amount
            tpl=next((q for q in QUEST_TEMPLATES if q["key"]==quest_key),None)
            reward=0
            if tpl and prog[quest_key]>=tpl["goal"] and quest_key not in claimed:
                reward=tpl["reward_kp"]
                claimed.append(quest_key)
                await conn.execute("UPDATE users SET quest_points=quest_points+$1 WHERE id=$2",reward,uid)
                await conn.execute("INSERT INTO quests_log(user_id,quest_key,reward_kp) VALUES($1,$2,$3)",uid,quest_key,reward)
            await conn.execute("UPDATE users SET quest_day=$1,quest_progress=$2,quest_claimed=$3 WHERE id=$4",day,json.dumps(prog),json.dumps(claimed),uid)
            return reward
    except Exception as e: print(f"quest progress: {e}")

async def check_daily_bonus(uid):
    """FIX: ежедневный бонус = 1 бекоин"""
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT daily_bonus_at FROM users WHERE id=$1",uid)
            if not row: return {"ok":False,"reason":"no_user"}
            now=datetime.datetime.now(datetime.timezone.utc)
            last=row["daily_bonus_at"]
            if last and (now-last).total_seconds()<86400:
                return {"ok":False,"reason":"already","next_in":int(86400-(now-last).total_seconds())}
            # Выдаём 1 бекоин (+ бонус премиум — 1x, но дадим +1 если премиум)
            bonus=1
            user=await conn.fetchrow("SELECT premium_tier,premium_expires FROM users WHERE id=$1",uid)
            prem=False
            if user and user["premium_tier"] and (not user["premium_expires"] or user["premium_expires"]>now):
                prem=True
                bonus=3  # премам x3
            await conn.execute("UPDATE users SET coins=coins+$1,daily_bonus_at=$2 WHERE id=$3",bonus,now,uid)
            return {"ok":True,"amount":bonus,"premium":prem}
    except Exception as e: return {"ok":False,"reason":str(e)}
# ==================== HTTP ROUTES ====================

@app.get("/api/changelog")
async def changelog(): return {"current":CURRENT_VERSION,"all":CHANGELOG}

@app.get("/api/achievements/all")
async def achievements_all(): return ACHIEVEMENTS

@app.get("/api/check_username")
async def check_username(username:str):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",username)
    return {"available":row is None}

@app.post("/api/register")
async def register(data:dict):
    u=(data.get("username") or "").strip()
    pw=data.get("password") or ""
    em=(data.get("email") or "").strip() or None
    if len(u)<2 or len(u)>32: raise HTTPException(400,"Ник 2-32")
    if len(pw)<4: raise HTTPException(400,"Пароль мин 4")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM users WHERE username=$1",u): raise HTTPException(400,"Занят")
        row=await conn.fetchrow("INSERT INTO users(username,password_hash,email,is_admin) VALUES($1,$2,$3,$4) RETURNING *",u,hash_password(pw),em,u==ADMIN_USERNAME)
    if em:
        code=str(random.randint(100000,999999))
        try:
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET email_code=$1,email_code_expires=NOW()+INTERVAL '1 hour' WHERE id=$2",code,row["id"])
            asyncio.create_task(send_email(em,"Belugacord - подтверждение",f"<h2>Привет, {u}!</h2><p>Код: <b style='font-size:24px;color:#d946ef'>{code}</b></p>"))
        except: pass
    return {"token":make_token(row["id"],row["username"]),"user":user_public(row,row["id"])}

@app.post("/api/login")
async def login(data:dict):
    u=(data.get("username") or "").strip()
    pw=data.get("password") or ""
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE username=$1",u)
    if not row or not verify_password(pw,row["password_hash"]): raise HTTPException(400,"Неверный ник/пароль")
    if row["is_banned"]: raise HTTPException(403,row.get("ban_reason") or "Забанен")
    if row.get("frozen"): raise HTTPException(403,"Заморожен")
    return {"token":make_token(row["id"],row["username"]),"user":user_public(row,row["id"])}

@app.get("/api/me")
async def me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return user_public(user,user["id"])

# ==================== EMAIL ====================
@app.post("/api/email/send_code")
async def email_send_code(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    em=(data.get("email") or "").strip()
    if not em or "@" not in em or "." not in em: raise HTTPException(400,"Плохой email")
    code=str(random.randint(100000,999999))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET email=$1,email_code=$2,email_code_expires=NOW()+INTERVAL '1 hour',email_verified=FALSE WHERE id=$3",em,code,user["id"])
    r=await send_email(em,"Belugacord - подтверждение",f"<h2>Привет, {user['username']}!</h2><p>Код: <b style='font-size:24px;color:#d946ef'>{code}</b></p>")
    if r.get("ok"): return {"ok":True,"sent":True}
    return {"ok":True,"sent":False,"code_hint":code,"error":r.get("error","")}

@app.post("/api/email/verify")
async def email_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    code=(data.get("code") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT email_code,email_code_expires FROM users WHERE id=$1",user["id"])
        if not row or not row["email_code"]: raise HTTPException(400,"Сначала запроси код")
        if row["email_code_expires"] and row["email_code_expires"]<datetime.datetime.now(datetime.timezone.utc): raise HTTPException(400,"Код истёк")
        if row["email_code"]!=code: raise HTTPException(400,"Неверный код")
        await conn.execute("UPDATE users SET email_verified=TRUE,email_code=NULL,email_code_expires=NULL WHERE id=$1",user["id"])
    return {"ok":True}

# ==================== PROFILE ====================
@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    premium=is_premium(user)
    gif_av=data.get("gif_avatar")
    gif_bn=data.get("gif_banner")
    if (gif_av or gif_bn) and not premium: raise HTTPException(403,"GIF только для премиума")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),gif_avatar=COALESCE($3,gif_avatar),gif_banner=COALESCE($4,gif_banner),avatar_pos=COALESCE($5,avatar_pos),banner_pos=COALESCE($6,banner_pos),nickname_color=$7,nickname_gradient=$8,bio=COALESCE($9,bio),fav_music=COALESCE($10,fav_music),wallpaper=COALESCE($11,wallpaper),font_choice=COALESCE($12,font_choice),compact_mode=COALESCE($13,compact_mode),custom_status=COALESCE($14,custom_status) WHERE id=$15""",
            data.get("avatar"),data.get("banner"),gif_av,gif_bn,data.get("avatar_pos"),data.get("banner_pos"),data.get("nickname_color"),data.get("nickname_gradient"),data.get("bio"),data.get("fav_music"),data.get("wallpaper"),data.get("font_choice"),data.get("compact_mode"),data.get("custom_status"),user["id"])
    return {"ok":True}

@app.post("/api/user/status")
async def set_status(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    st=data.get("online_status","online")
    if st not in ("online","dnd","invisible"): raise HTTPException(400,"online/dnd/invisible")
    custom=(data.get("custom_status") or "")[:64]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET online_status=$1,custom_status=$2 WHERE id=$3",st,custom or None,user["id"])
    user_status[user["id"]]=st
    await manager.broadcast({"type":"status_update","user_id":user["id"],"online_status":st,"custom_status":custom or None})
    return {"ok":True}

@app.get("/api/user/{user_id}")
async def get_user(user_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id,username,avatar,banner,gif_avatar,gif_banner,avatar_pos,banner_pos,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,premium_expires,nickname_color,nickname_gradient,bio,fav_music,custom_status,online_status,messages_count,is_legend,achievements,social_rating,coins,quest_points,active_frame,created_at,last_seen FROM users WHERE id=$1",user_id)
    if not row: raise HTTPException(404,"Не найден")
    d=dict(row)
    d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
    d["last_seen"]=d["last_seen"].isoformat() if d.get("last_seen") else None
    d["premium_expires"]=d["premium_expires"].isoformat() if d.get("premium_expires") else None
    d["role"]=get_role(row)
    d["is_premium"]=is_premium(row)
    d["online"]=user_id in online_users and (row.get("online_status") or "online")!="invisible"
    d["achievements"]=json.loads(row.get("achievements") or "[]")
    return d

@app.post("/api/user/change_nick")
async def change_nick(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    n=(data.get("new_nick") or "").strip()
    if len(n)<2 or len(n)>32: raise HTTPException(400,"Ник 2-32")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM users WHERE username=$1",n): raise HTTPException(400,"Занят")
        await conn.execute("UPDATE users SET username=$1 WHERE id=$2",n,user["id"])
    return {"ok":True,"token":make_token(user["id"],n)}

@app.get("/api/users/search")
async def users_search(q:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip()
    if len(q)<2: return []
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username,avatar,gif_avatar,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,premium_expires,online_status FROM users WHERE username ILIKE $1 AND id!=$2 ORDER BY username LIMIT 20",f"%{q}%",user["id"])
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); d["is_premium"]=is_premium(r); d["online"]=r["id"] in online_users and (r.get("online_status") or "online")!="invisible"; out.append(d)
    return out

@app.get("/api/users/{user_id}/suspicious")
async def user_suspicious(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (user.get("is_admin") or user.get("is_moderator") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT action,details,created_at FROM suspicious_logs WHERE user_id=$1 ORDER BY id DESC LIMIT 50",user_id)
    return [{"action":r["action"],"details":r["details"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

# ==================== FRIENDS ====================
@app.get("/api/friends/list")
async def friends_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    uid=user["id"]
    p=await get_pool()
    async with p.acquire() as conn:
        frows=await conn.fetch("SELECT id,user_a,user_b FROM friendships WHERE user_a=$1 OR user_b=$1",uid)
        inc=await conn.fetch("SELECT r.id,r.from_user,u.username,u.avatar,u.gif_avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev,u.is_streamer,u.premium_tier,u.premium_expires FROM friend_requests r JOIN users u ON u.id=r.from_user WHERE r.to_user=$1 ORDER BY r.created_at DESC",uid)
        out=await conn.fetch("SELECT r.id,r.to_user,u.username,u.avatar FROM friend_requests r JOIN users u ON u.id=r.to_user WHERE r.from_user=$1 ORDER BY r.created_at DESC",uid)
        result=[]
        for r in frows:
            oid=r["user_b"] if r["user_a"]==uid else r["user_a"]
            o=await conn.fetchrow("SELECT id,username,avatar,gif_avatar,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,last_seen,online_status,custom_status,premium_tier,premium_expires FROM users WHERE id=$1",oid)
            if not o: continue
            last=await conn.fetchval("SELECT MAX(created_at) FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",uid,oid)
            result.append({"id":o["id"],"username":o["username"],"avatar":o["avatar"],"gif_avatar":o.get("gif_avatar"),"status":"accepted","friend_row_id":r["id"],"online":o["id"] in online_users and (o.get("online_status") or "online")!="invisible","last_seen":o["last_seen"].isoformat() if o.get("last_seen") else None,"is_admin":o["is_admin"],"is_moderator":o["is_moderator"],"is_beta_tester":o["is_beta_tester"],"is_scam":o["is_scam"],"is_streamer":o.get("is_streamer",False),"custom_status":o.get("custom_status"),"online_status":o.get("online_status") or "online","role":get_role(o),"is_premium":is_premium(o),"last_message_at":last.isoformat() if last else None})
        for r in inc: result.append({"id":r["from_user"],"username":r["username"],"avatar":r["avatar"],"gif_avatar":r.get("gif_avatar"),"status":"incoming","request_id":r["id"],"online":r["from_user"] in online_users,"is_admin":r["is_admin"],"is_moderator":r["is_moderator"],"is_beta_tester":r["is_beta_tester"],"is_scam":r["is_scam"],"is_streamer":r.get("is_streamer",False),"role":get_role(r),"is_premium":is_premium(r)})
        for r in out: result.append({"id":r["to_user"],"username":r["username"],"avatar":r["avatar"],"status":"outgoing","request_id":r["id"],"online":r["to_user"] in online_users,"is_admin":False,"is_moderator":False,"is_beta_tester":False,"is_scam":False,"role":"user"})
    # FIX: сортировка — онлайн+премиум вверх, потом по last_message_at
    result.sort(key=lambda x:(not x.get("online"),not x.get("is_premium"),-(datetime.datetime.fromisoformat(x["last_message_at"]).timestamp() if x.get("last_message_at") else 0)))
    return result

@app.post("/api/friends/request")
async def friends_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tn=(data.get("username") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",tn)
        if not t: raise HTTPException(404,"Не найден")
        # FIX: per-target проверка
        if await check_friend_spam(user["id"],t["id"]): raise HTTPException(429,"Слишком много заявок этому юзеру")
        if t["id"]==user["id"]: raise HTTPException(400,"Себя нельзя")
        if await is_blocked(user["id"],t["id"]): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],t["id"]): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],t["id"]): raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],t["id"])
    await manager.send_to(t["id"],{"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok":True}

@app.post("/api/friends/request_by_id")
async def friends_request_by_id(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        # FIX: per-target проверка
        if await check_friend_spam(user["id"],tid): raise HTTPException(429,"Слишком много заявок")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid): raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok":True}

@app.post("/api/friends/accept")
async def friends_accept(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    if not rid: raise HTTPException(400,"request_id")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT id,from_user,to_user FROM friend_requests WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Заявка обработана")
        if r["to_user"]!=user["id"]: raise HTTPException(403,"Не твоя")
        a,b=sorted([r["from_user"],r["to_user"]])
        try: await conn.execute("INSERT INTO friendships(user_a,user_b) VALUES($1,$2)",a,b)
        except: pass
        await conn.execute("DELETE FROM friend_requests WHERE id=$1",rid)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM friendships WHERE user_a=$1 OR user_b=$1",user["id"])
        if cnt==1: await grant_achievement(user["id"],"first_friend")
        if cnt>=10: await grant_achievement(user["id"],"friend_10")
        other=await conn.fetchrow("SELECT id,username,avatar FROM users WHERE id=$1",r["from_user"])
    await manager.send_to(r["from_user"],{"type":"friend_accepted","friend_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    await manager.send_to(user["id"],{"type":"friend_accepted","friend_id":r["from_user"],"username":other["username"],"avatar":other["avatar"]})
    return {"ok":True}

@app.post("/api/friends/decline")
async def friends_decline(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT from_user,to_user FROM friend_requests WHERE id=$1",rid)
        if not r: return {"ok":True}
        if r["to_user"]!=user["id"]: raise HTTPException(403,"Не твоя")
        await conn.execute("DELETE FROM friend_requests WHERE id=$1",rid)
    await manager.send_to(r["from_user"],{"type":"friend_declined","by_id":user["id"],"username":user["username"]})
    return {"ok":True}

@app.post("/api/friends/cancel")
async def friends_cancel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND from_user=$2",rid,user["id"])
    return {"ok":True}

@app.post("/api/friends/remove")
async def friends_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_removed","by_id":user["id"],"username":user["username"]})
    return {"ok":True}

@app.get("/api/friends/check/{user_id}")
async def friends_check(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],user_id): return {"status":"accepted"}
        req=await conn.fetchrow("SELECT id,from_user FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],user_id)
        if req: return {"status":"incoming" if req["from_user"]!=user["id"] else "outgoing","request_id":req["id"]}
        return {"status":"none"}

@app.get("/api/friends/count")
async def friends_count(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        n=await conn.fetchval("SELECT COUNT(*) FROM friend_requests WHERE to_user=$1",user["id"])
    return {"count":n or 0}

# ==================== BLOCKS ====================
@app.post("/api/blocks/add")
async def blocks_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        try: await conn.execute("INSERT INTO blocks(blocker,blocked) VALUES($1,$2)",user["id"],tid)
        except: pass
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
        await conn.execute("DELETE FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid)
    return {"ok":True}

@app.post("/api/blocks/remove")
async def blocks_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM blocks WHERE blocker=$1 AND blocked=$2",user["id"],tid)
    return {"ok":True}

@app.get("/api/blocks/list")
async def blocks_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT b.blocked AS id,u.username,u.avatar FROM blocks b JOIN users u ON u.id=b.blocked WHERE b.blocker=$1 ORDER BY b.created_at DESC",user["id"])
    return [dict(r) for r in rows]

# ==================== GROUPS (с лимитами 10/30) ====================
@app.get("/api/groups/list")
async def groups_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.id,g.name,g.avatar,g.gif_avatar,g.description,g.owner_id,g.last_message_at FROM groups g JOIN group_members gm ON gm.group_id=g.id WHERE gm.user_id=$1 ORDER BY COALESCE(g.last_message_at,g.created_at) DESC",user["id"])
    return [{"id":r["id"],"name":r["name"],"avatar":r["avatar"],"gif_avatar":r.get("gif_avatar"),"description":r["description"],"owner_id":r["owner_id"],"last_message_at":r["last_message_at"].isoformat() if r.get("last_message_at") else None} for r in rows]

@app.post("/api/groups/create")
async def groups_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    members=data.get("members") or []
    max_members=30 if is_premium(user) else 10
    if len(members)+1>max_members: raise HTTPException(400,f"Макс {max_members} участников")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("INSERT INTO groups(name,avatar,description,owner_id) VALUES($1,$2,$3,$4) RETURNING *",name,data.get("avatar"),data.get("description","")[:256],user["id"])
        await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)",g["id"],user["id"])
        for m in members:
            try:
                mid=int(m)
                if mid!=user["id"]:
                    await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",g["id"],mid)
                    await manager.send_to(mid,{"type":"group_added","group_id":g["id"],"name":name,"avatar":g["avatar"]})
            except: pass
    return {"id":g["id"],"name":g["name"],"avatar":g["avatar"]}

@app.get("/api/groups/{group_id}")
async def group_get(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT * FROM groups WHERE id=$1",group_id)
        if not g: raise HTTPException(404,"Нет")
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not m: raise HTTPException(403,"Не участник")
    d=dict(g); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
    d["last_message_at"]=d["last_message_at"].isoformat() if d.get("last_message_at") else None
    return d

@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        rows=await conn.fetch("SELECT gm.id,gm.text,gm.file_url,gm.created_at,gm.user_id,u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev,u.is_streamer,u.premium_tier,u.premium_expires,u.active_frame FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200",group_id)
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None; d["role"]=get_role(r); d["is_premium"]=is_premium(r); out.append(d)
    return out

@app.get("/api/groups/{group_id}/members")
async def group_members_get(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.id,u.username,u.avatar,u.gif_avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev,u.is_streamer,u.premium_tier,u.premium_expires FROM users u JOIN group_members gm ON gm.user_id=u.id WHERE gm.group_id=$1",group_id)
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); d["is_premium"]=is_premium(r); out.append(d)
    return out

@app.post("/api/groups/add_member")
async def group_add_member(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    username=(data.get("username") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id,name FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет группы")
        if g["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM group_members WHERE group_id=$1",gid)
        max_members=30 if is_premium(user) else 10
        if cnt>=max_members: raise HTTPException(400,f"Макс {max_members} участников")
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",username)
        if not t: raise HTTPException(404,"Юзер не найден")
        try: await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)",gid,t["id"])
        except: raise HTTPException(400,"Уже в группе")
    await manager.send_to(t["id"],{"type":"group_added","group_id":gid,"name":g["name"]})
    return {"ok":True}

@app.post("/api/groups/kick")
async def group_kick(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0)); tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g or g["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        if tid==user["id"]: raise HTTPException(400,"Себя через выход")
        await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,tid)
    await manager.send_to(tid,{"type":"group_kicked","group_id":gid})
    return {"ok":True}

@app.post("/api/groups/leave")
async def group_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет")
        if g["owner_id"]==user["id"]: await conn.execute("DELETE FROM groups WHERE id=$1",gid)
        else: await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
    return {"ok":True}

@app.post("/api/groups/update")
async def group_update(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    gif_av=data.get("gif_avatar")
    if gif_av and not is_premium(user): raise HTTPException(403,"GIF только для премиума")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g or g["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("UPDATE groups SET name=COALESCE($1,name),description=COALESCE($2,description),avatar=COALESCE($3,avatar),gif_avatar=COALESCE($4,gif_avatar) WHERE id=$5",data.get("name"),data.get("description"),data.get("avatar"),gif_av,gid)
        row=await conn.fetchrow("SELECT * FROM groups WHERE id=$1",gid)
    return dict(row)

# ==================== SERVERS ====================
@app.get("/api/servers/list")
async def servers_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT s.id,s.name,s.avatar FROM servers s JOIN server_members sm ON sm.server_id=s.id WHERE sm.user_id=$1 ORDER BY s.id",user["id"])
    return [dict(r) for r in rows]

@app.post("/api/servers/create")
async def servers_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        code=secrets.token_urlsafe(8)[:12]
        s=await conn.fetchrow("INSERT INTO servers(name,owner_id,invite_code) VALUES($1,$2,$3) RETURNING *",name,user["id"],code)
        await conn.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)",s["id"],user["id"])
        await conn.execute("INSERT INTO channels(server_id,name) VALUES($1,'общий')",s["id"])
        await grant_achievement(user["id"],"first_server")
    return {"id":s["id"],"name":s["name"],"invite_code":code}

@app.post("/api/servers/join")
async def servers_join(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    code=(data.get("invite") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT * FROM servers WHERE invite_code=$1",code)
        if not s: raise HTTPException(404,"Неверный код")
        try: await conn.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)",s["id"],user["id"])
        except: pass
    return {"id":s["id"],"name":s["name"]}

@app.get("/api/servers/{server_id}")
async def server_get(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT * FROM servers WHERE id=$1",server_id)
    if not s: raise HTTPException(404,"Нет сервера")
    d=dict(s); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
    return d

@app.get("/api/servers/{server_id}/channels")
async def server_channels(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,type,last_message_at FROM channels WHERE server_id=$1 ORDER BY COALESCE(last_message_at,created_at) DESC, id",server_id)
    return [{"id":r["id"],"name":r["name"],"type":r["type"],"last_message_at":r["last_message_at"].isoformat() if r.get("last_message_at") else None} for r in rows]

@app.get("/api/servers/{server_id}/members")
async def server_members(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.id,u.username,u.avatar,u.gif_avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev,u.is_streamer,u.premium_tier,u.premium_expires FROM users u JOIN server_members sm ON sm.user_id=u.id WHERE sm.server_id=$1",server_id)
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); d["is_premium"]=is_premium(r); out.append(d)
    return out

@app.post("/api/servers/update")
async def server_update(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1",int(data.get("server_id",0)))
        if not s or s["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("UPDATE servers SET name=COALESCE($1,name),description=COALESCE($2,description),avatar=COALESCE($3,avatar) WHERE id=$4",data.get("name"),data.get("description"),data.get("avatar"),int(data.get("server_id",0)))
    return {"ok":True}

@app.post("/api/servers/delete")
async def server_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1",int(data.get("server_id",0)))
        if not s or s["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("DELETE FROM servers WHERE id=$1",int(data.get("server_id",0)))
    return {"ok":True}

@app.post("/api/servers/leave")
async def server_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM server_members WHERE server_id=$1 AND user_id=$2",int(data.get("server_id",0)),user["id"])
    return {"ok":True}

@app.post("/api/servers/regen_invite")
async def server_regen_invite(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1",int(data.get("server_id",0)))
        if not s or s["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        code=secrets.token_urlsafe(8)[:12]
        await conn.execute("UPDATE servers SET invite_code=$1 WHERE id=$2",code,int(data.get("server_id",0)))
    return {"ok":True,"invite_code":code}

@app.post("/api/channels/create")
async def channel_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=int(data.get("server_id",0)); name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO channels(server_id,name) VALUES($1,$2) RETURNING id,name",sid,name)
    return {"id":r["id"],"name":r["name"]}

@app.get("/api/channels/{channel_id}/messages")
async def channel_messages(channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT m.id,m.text,m.file_url,m.reactions,m.edited,m.reply_to,m.pinned,m.created_at,m.user_id,u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev,u.is_streamer,u.premium_tier,u.premium_expires,u.active_frame FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200",channel_id)
        pinned=await conn.fetch("SELECT m.id,m.text,m.user_id,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.pinned=TRUE ORDER BY m.id DESC LIMIT 5",channel_id)
    out=[]
    for r in rows:
        d=dict(r)
        d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["role"]=get_role(r)
        d["is_premium"]=is_premium(r)
        d["reactions"]=json.loads(d.get("reactions") or "{}")
        out.append(d)
    return {"messages":out,"pinned":[dict(p) for p in pinned]}

# FIX: проверка блокировки в DM
@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if await is_blocked(user["id"],user_id): raise HTTPException(403,"Заблокировано")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.created_at,u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.premium_tier,u.premium_expires,u.active_frame FROM dms d JOIN users u ON u.id=d.from_user WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC LIMIT 200",user["id"],user_id)
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None; d["is_premium"]=is_premium(r); out.append(d)
    return out

# FIX: edit — только если обновилось
@app.post("/api/messages/edit")
async def message_edit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    new_text=data.get("text","")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("UPDATE messages SET text=$1,edited=TRUE WHERE id=$2 AND user_id=$3 RETURNING id",new_text,mid,user["id"])
    if not row: return {"ok":False,"reason":"not_found_or_not_yours"}
    await manager.broadcast({"type":"message_edited","id":mid,"text":new_text})
    return {"ok":True}

# FIX: delete + kick WS при бане
@app.post("/api/messages/delete")
async def message_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        if user.get("is_admin") or user["username"]==ADMIN_USERNAME:
            row=await conn.fetchrow("DELETE FROM messages WHERE id=$1 RETURNING id",mid)
        else:
            row=await conn.fetchrow("DELETE FROM messages WHERE id=$1 AND user_id=$2 RETURNING id",mid,user["id"])
    if not row: return {"ok":False}
    await manager.broadcast({"type":"message_deleted","id":mid})
    return {"ok":True}

@app.post("/api/messages/pin")
async def message_pin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT pinned FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        new=not row["pinned"]
        await conn.execute("UPDATE messages SET pinned=$1 WHERE id=$2",new,mid)
    await manager.broadcast({"type":"message_pinned","id":mid,"pinned":new})
    return {"ok":True,"pinned":new}

# FIX: reaction — broadcast только если обновилось
@app.post("/api/messages/reaction")
async def message_reaction(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0)); emoji=data.get("emoji","👍")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        react=json.loads(row["reactions"] or "{}")
        arr=react.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        react[emoji]=arr
        updated=await conn.fetchrow("UPDATE messages SET reactions=$1 WHERE id=$2 RETURNING id",json.dumps(react),mid)
    if not updated: return {"ok":False}
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":react})
    return {"ok":True}

@app.post("/api/upload")
async def upload(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    lim=LIMITS.get(user.get("premium_tier"),LIMITS[None])["file"]
    content=await file.read()
    if len(content)>lim: raise HTTPException(400,"Файл большой")
    ext=os.path.splitext(file.filename or "")[1][:8]
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}"}

# ==================== EASTER ====================
@app.post("/api/easter/found")
async def easter_found(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    egg=data.get("egg")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT easter_found,easter_rewarded FROM users WHERE id=$1",user["id"])
        found=json.loads(row["easter_found"] or "[]")
        rewarded=row["easter_rewarded"]
        if egg in found: return {"found":len(found),"total":len(EASTER_EGGS),"already_rewarded":rewarded}
        found.append(egg)
        af=len(found)>=len(EASTER_EGGS)
        ar=rewarded
        if af and not rewarded:
            await conn.execute("UPDATE users SET easter_found=$1,easter_rewarded=TRUE,coins=coins+100 WHERE id=$2",json.dumps(found),user["id"])
            ar=False
        else:
            await conn.execute("UPDATE users SET easter_found=$1 WHERE id=$2",json.dumps(found),user["id"])
    return {"found":len(found),"total":len(EASTER_EGGS),"all_found":af,"already_rewarded":ar}

# ==================== ADMIN ====================
@app.post("/api/admin/set_password")
async def admin_set_password(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    pw=data.get("password") or ""
    if len(pw)<4: raise HTTPException(400,"Мин 4")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET admin_password=$1 WHERE id=$2",hash_password(pw),user["id"])
    return {"ok":True}

@app.post("/api/admin/verify")
async def admin_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    pw=data.get("password") or ""
    stored=user.get("admin_password")
    if stored and not verify_password(pw,stored): raise HTTPException(403,"Неверный")
    if not stored and pw!="12344321": raise HTTPException(403,"Установи пароль")
    return {"ok":True}

@app.get("/api/admin/stats")
async def admin_stats(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchval("SELECT COUNT(*) FROM users")
        s=await conn.fetchval("SELECT COUNT(*) FROM servers")
        m=await conn.fetchval("SELECT COUNT(*) FROM messages")
    return {"users":u,"servers":s,"messages":m,"online":len(online_users)}

@app.get("/api/admin/users")
async def admin_users(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,is_banned,coins,social_rating FROM users ORDER BY id")
    return [dict(r) for r in rows]

# FIX: при бане — kick WS
@app.post("/api/admin/action")
async def admin_action(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    tid=data.get("target_id"); action=data.get("action")
    is_owner=user["username"]==ADMIN_USERNAME
    if action=="ban" and not is_owner: raise HTTPException(403,"Отправь заявку")
    p=await get_pool()
    async with p.acquire() as conn:
        if action=="ban":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",data.get("reason",""),tid)
        elif action=="unban": await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",tid)
        elif action=="mute":
            d=int(data.get("duration",3600))
            await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",d,tid)
        elif action=="grant_premium" and is_owner: await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=NOW()+INTERVAL '30 days' WHERE id=$1",tid)
        elif action=="grant_pro" and is_owner: await conn.execute("UPDATE users SET premium_tier='pro',premium_expires=NOW()+INTERVAL '30 days' WHERE id=$1",tid)
        elif action=="scam" and is_owner: await conn.execute("UPDATE users SET is_scam=TRUE WHERE id=$1",tid)
        elif action=="toggle_streamer" and is_owner: await conn.execute("UPDATE users SET is_streamer=NOT is_streamer WHERE id=$1",tid)
    await log_admin(user["id"],action,tid)
    if action=="ban":
        await manager.send_to(tid,{"type":"banned","reason":data.get("reason","")})
        await manager.kick(tid)  # FIX: рвём сокеты
    return {"ok":True}

@app.get("/api/admin/reports")
async def admin_reports(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT r.id,r.text,r.target_user,f.username AS from_username,t.username AS target_username FROM reports r LEFT JOIN users f ON f.id=r.from_user LEFT JOIN users t ON t.id=r.target_user WHERE r.status='pending' ORDER BY r.id DESC")
    return [dict(r) for r in rows]

@app.get("/api/admin/appeals")
async def admin_appeals(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username,text,created_at FROM ban_appeals WHERE status='pending' ORDER BY id DESC")
    return [{"id":r["id"],"username":r["username"],"text":r["text"],"created_at":r["created_at"].isoformat()} for r in rows]

@app.get("/api/admin/logs")
async def admin_logs(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT l.id,l.action,l.details,l.created_at,a.username AS admin_name FROM admin_logs l LEFT JOIN users a ON a.id=l.admin_id ORDER BY l.id DESC LIMIT 100")
    return [{"id":r["id"],"action":r["action"],"details":r["details"],"created_at":r["created_at"].isoformat() if r["created_at"] else None,"admin_name":r["admin_name"]} for r in rows]

@app.get("/api/admin/spam_alerts")
async def admin_spam_alerts(token:str):
    user=await get_current_user(token)
    if not user or not (user.get("is_admin") or user.get("is_moderator")): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT sa.id,sa.user_id,sa.text_sample,sa.count,sa.created_at,u.username FROM spam_alerts sa LEFT JOIN users u ON u.id=sa.user_id ORDER BY sa.id DESC LIMIT 50")
    return [{"id":r["id"],"user_id":r["user_id"],"username":r["username"],"text":r["text_sample"],"count":r["count"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/ban_requests/submit")
async def ban_requests_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]==ADMIN_USERNAME: raise HTTPException(400,"Владелец банит напрямую")
    if not (user.get("is_admin") or user.get("is_moderator")): raise HTTPException(403,"Нет прав")
    tid=int(data.get("target_id",0))
    reason=(data.get("reason") or "").strip()
    evidence=(data.get("evidence") or "").strip()
    if not reason: raise HTTPException(400,"Причина")
    p=await get_pool()
    async with p.acquire() as conn:
        target=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not target: raise HTTPException(404,"Не найден")
        if await conn.fetchrow("SELECT id FROM ban_requests WHERE target_user=$1 AND status='pending'",tid): raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO ban_requests(from_admin,target_user,reason,evidence) VALUES($1,$2,$3,$4)",user["id"],tid,reason,evidence)
    try:
        async with p.acquire() as conn2:
            owner=await conn2.fetchrow("SELECT id FROM users WHERE username=$1",ADMIN_USERNAME)
            if owner: await manager.send_to(owner["id"],{"type":"ban_request_new","from":user["username"],"target":target["username"],"reason":reason})
    except: pass
    return {"ok":True}

@app.get("/api/ban_requests/list")
async def ban_requests_list(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT br.id,br.reason,br.evidence,br.created_at,fa.username AS from_username,tu.username AS target_username,br.target_user FROM ban_requests br LEFT JOIN users fa ON fa.id=br.from_admin LEFT JOIN users tu ON tu.id=br.target_user WHERE br.status='pending' ORDER BY br.id DESC")
    return [{"id":r["id"],"reason":r["reason"],"evidence":r["evidence"],"from_username":r["from_username"],"target_username":r["target_username"],"target_user":r["target_user"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/ban_requests/resolve")
async def ban_requests_resolve(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    rid=int(data.get("request_id",0)); action=data.get("action")
    if action not in ("approve","reject"): raise HTTPException(400,"approve/reject")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM ban_requests WHERE id=$1 AND status='pending'",rid)
        if not r: raise HTTPException(404,"Нет заявки")
        if action=="approve":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",r["reason"],r["target_user"])
            await conn.execute("UPDATE ban_requests SET status='approved',resolved_by=$1,resolved_at=NOW() WHERE id=$2",user["id"],rid)
            try: await manager.send_to(r["from_admin"],{"type":"ban_request_resolved","status":"approved"})
            except: pass
            try: await manager.send_to(r["target_user"],{"type":"banned","reason":r["reason"]})
            except: pass
            await manager.kick(r["target_user"])  # FIX: kick
        else:
            await conn.execute("UPDATE ban_requests SET status='rejected',resolved_by=$1,resolved_at=NOW() WHERE id=$2",user["id"],rid)
            try: await manager.send_to(r["from_admin"],{"type":"ban_request_resolved","status":"rejected"})
            except: pass
    return {"ok":True}

@app.get("/api/ban_requests/check/{target_id}")
async def ban_requests_check(target_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT id FROM ban_requests WHERE target_user=$1 AND status='pending'",target_id)
    return {"pending":bool(r),"request_id":r["id"] if r else None}

# ==================== MODERATOR ====================
async def check_mod(user):
    if not user: raise HTTPException(401,"Не авторизован")
    if not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")

@app.get("/api/mod/reports")
async def mod_reports(token:str):
    user=await get_current_user(token); await check_mod(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT r.id,r.text,r.target_user,f.username AS from_username,t.username AS target_username FROM reports r LEFT JOIN users f ON f.id=r.from_user LEFT JOIN users t ON t.id=r.target_user WHERE r.status='pending' ORDER BY r.id DESC")
    return [dict(r) for r in rows]

@app.post("/api/mod/mute")
async def mod_mute(data:dict):
    user=await get_current_user(data.get("token")); await check_mod(user)
    p=await get_pool()
    async with p.acquire() as conn:
        m=int(data.get("minutes",60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",m*60,int(data.get("user_id",0)))
    await log_admin(user["id"],"mod_mute",int(data.get("user_id",0)),f"{m} min")
    return {"ok":True}

@app.post("/api/mod/warn")
async def mod_warn(data:dict):
    user=await get_current_user(data.get("token")); await check_mod(user)
    await log_admin(user["id"],"warn",int(data.get("user_id",0)),data.get("reason",""))
    return {"ok":True}

@app.post("/api/mod/dismiss_report")
async def mod_dismiss(data:dict):
    user=await get_current_user(data.get("token")); await check_mod(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE reports SET status='dismissed' WHERE id=$1",int(data.get("report_id",0)))
    return {"ok":True}

@app.post("/api/mod/mute_by_name")
async def mod_mute_by_name(data:dict):
    user=await get_current_user(data.get("token")); await check_mod(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        m=int(data.get("minutes",60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",m*60,t["id"])
    return {"ok":True}

@app.post("/api/mod/warn_by_name")
async def mod_warn_by_name(data:dict):
    user=await get_current_user(data.get("token")); await check_mod(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
    await log_admin(user["id"],"warn",t["id"],data.get("reason",""))
    return {"ok":True}

@app.post("/api/reports/submit")
async def report_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    txt=(data.get("text") or "").strip()
    if not txt: raise HTTPException(400,"Опиши")
    tid=data.get("target_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO reports(from_user,target_user,text) VALUES($1,$2,$3)",user["id"],tid,txt)
    return {"ok":True}

@app.post("/api/appeal/submit")
async def appeal_submit(data:dict):
    u=(data.get("username") or "").strip(); t=(data.get("text") or "").strip()
    if not u or not t: raise HTTPException(400,"Заполни")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO ban_appeals(username,text) VALUES($1,$2)",u,t)
    return {"ok":True}

# ==================== OWNER (BOG-ADMIN) ====================
@app.post("/api/owner/verify")
async def owner_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    if data.get("password")!=OWNER_PASSWORD: raise HTTPException(403,"Неверный")
    return {"ok":True}

@app.get("/api/owner/stats")
async def owner_stats(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchval("SELECT COUNT(*) FROM users")
        m=await conn.fetchval("SELECT COUNT(*) FROM messages")
        c=await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        n=await conn.fetchval("SELECT COUNT(*) FROM nft_items")
        g=await conn.fetchval("SELECT COUNT(*) FROM gifts")
        gr=await conn.fetchval("SELECT COUNT(*) FROM groups")
    return {"users":u,"messages":m,"coins":c,"nfts":n,"gifts":g,"groups":gr,"online":len(online_users)}

# ... (все owner-эндпоинты из 2.1 идут сюда без изменений — читать/писать/ник/пароль/мут/легенда/премиум/бета/админ/стример/шпион/анонс/coop/кооп-гранты/auto_abuse/troll_user/mass_rename/mass_color/self_destruct/clean_db/read_chat/write_as/gifts_full/stickers_full/nfts_full/cases_full/create_nft/give_nft/delete_nft/create_gift/delete_gift/create_sticker/delete_sticker/cases/create/cases/delete/cases/toggle/theme/create/theme/delete/announce/give_coins/take_coins/give_all/suddness)

# ==================== НОВЫЕ 2.2: DAILY / QUESTS / PREMIUM / UPGRADE / FRAMES / CALLS / DOOM ====================

@app.post("/api/daily/bonus")
async def daily_bonus(data:dict):
    """Ежедневный бонус — 1 бекоин (3 для премиума)"""
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    r=await check_daily_bonus(user["id"])
    if not r.get("ok"):
        if r.get("reason")=="already":
            raise HTTPException(429,f"Через {r['next_in']} сек")
        raise HTTPException(400,r.get("reason","Ошибка"))
    return r

@app.get("/api/daily/status")
async def daily_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT daily_bonus_at FROM users WHERE id=$1",user["id"])
    if not row or not row["daily_bonus_at"]:
        return {"available":True,"next_in":0}
    now=datetime.datetime.now(datetime.timezone.utc)
    diff=(now-row["daily_bonus_at"]).total_seconds()
    if diff>=86400: return {"available":True,"next_in":0}
    return {"available":False,"next_in":int(86400-diff)}

@app.get("/api/quests/list")
async def quests_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT quest_day,quest_progress,quest_claimed,quest_points FROM users WHERE id=$1",user["id"])
    today=get_today_key()
    prog={}
    claimed=[]
    if row["quest_day"]==today:
        prog=json.loads(row["quest_progress"] or "{}")
        claimed=json.loads(row["quest_claimed"] or "[]")
    result=[]
    for q in QUEST_TEMPLATES:
        result.append({"key":q["key"],"name":q["name"],"desc":q["desc"],"emoji":q["emoji"],"goal":q["goal"],"reward_kp":q["reward_kp"],"progress":prog.get(q["key"],0),"claimed":q["key"] in claimed})
    return {"quests":result,"quest_points":row["quest_points"] or 0}

@app.post("/api/quests/exchange")
async def quests_exchange(data:dict):
    """Обмен КП на дни премиума: 1/3/7 дней"""
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan")
    if plan not in QUEST_EXCHANGE: raise HTTPException(400,"Нет такого плана")
    info=QUEST_EXCHANGE[plan]
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT quest_points,premium_expires,premium_tier FROM users WHERE id=$1",user["id"])
        if (row["quest_points"] or 0)<info["cost"]: raise HTTPException(400,f"Нужно {info['cost']} КП")
        now=datetime.datetime.now(datetime.timezone.utc)
        base=row["premium_expires"] if row["premium_expires"] and row["premium_expires"]>now else now
        new_exp=base+datetime.timedelta(days=info["days"])
        await conn.execute("UPDATE users SET quest_points=quest_points-$1,premium_tier='premium',premium_expires=$2 WHERE id=$3",info["cost"],new_exp,user["id"])
        await conn.execute("INSERT INTO premium_log(user_id,tier,days,paid_coins,method) VALUES($1,'premium',$2,0,'quests')",user["id"],info["days"])
    return {"ok":True,"premium_until":new_exp.isoformat(),"days":info["days"]}

@app.post("/api/premium/buy")
async def premium_buy(data:dict):
    """Покупка премиума за бекоины: месяц 1500, год 18000"""
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan","month")
    if plan not in PREMIUM_PRICES: raise HTTPException(400,"Нет такого плана")
    price=PREMIUM_PRICES[plan]
    days=30 if plan=="month" else 365
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT coins,premium_expires FROM users WHERE id=$1",user["id"])
        if (row["coins"] or 0)<price: raise HTTPException(400,f"Нужно {price} 🏅")
        now=datetime.datetime.now(datetime.timezone.utc)
        base=row["premium_expires"] if row["premium_expires"] and row["premium_expires"]>now else now
        new_exp=base+datetime.timedelta(days=days)
        await conn.execute("UPDATE users SET coins=coins-$1,premium_tier='premium',premium_expires=$2 WHERE id=$3",price,new_exp,user["id"])
        await conn.execute("INSERT INTO premium_log(user_id,tier,days,paid_coins,method) VALUES($1,'premium',$2,$3,'coins')",user["id"],days,price)
    return {"ok":True,"premium_until":new_exp.isoformat(),"days":days,"price":price}

@app.get("/api/premium/status")
async def premium_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"is_premium":is_premium(user),"tier":user.get("premium_tier"),"expires":user["premium_expires"].isoformat() if user.get("premium_expires") else None}

@app.post("/api/gifts/upgrade")
async def gifts_upgrade(data:dict):
    """Апгрейдер: 3 подарка → 1 подарок следующего уровня"""
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    # Определяем следующий по цене
    sorted_gifts=sorted(g.items(),key=lambda x:x[1]["price"])
    idx=next((i for i,(k,_) in enumerate(sorted_gifts) if k==gift_id),None)
    if idx is None or idx>=len(sorted_gifts)-1: raise HTTPException(400,"Максимальный уровень")
    next_id,next_gift=sorted_gifts[idx+1]
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 3",user["id"],gift_id)
        if len(rows)<3: raise HTTPException(400,"Нужно 3 подарка")
        for r in rows: await conn.execute("DELETE FROM gifts WHERE id=$1",r["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],next_id)
        await conn.execute("INSERT INTO upgrade_log(user_id,from_gift,to_gift) VALUES($1,$2,$3)",user["id"],gift_id,next_id)
    return {"ok":True,"got":next_id,"got_name":next_gift["name"]}

# FIX: продажа за 100% (не 50%)
@app.post("/api/gifts/sell")
async def gift_sell(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет")
    price=g[gift_id]["price"]
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",user["id"],gift_id)
        if not row: raise HTTPException(400,"Нет")
        await conn.execute("DELETE FROM gifts WHERE id=$1",row["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",price,user["id"])
    return {"ok":True,"got":price}

@app.get("/api/frames/list")
async def frames_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM frames_catalog ORDER BY is_premium,price_coins,price_kp")
        owned=json.loads(user.get("frame_owned") or "[]")
    return [{"frame_id":r["frame_id"],"name":r["name"],"emoji":r["emoji"],"css":r["css"],"is_animated":r["is_animated"],"is_premium":r["is_premium"],"price_coins":r["price_coins"],"price_kp":r["price_kp"],"owned":r["frame_id"] in owned or r["frame_id"]=="none"} for r in rows]

@app.post("/api/frames/buy")
async def frames_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    fid=data.get("frame_id")
    p=await get_pool()
    async with p.acquire() as conn:
        f=await conn.fetchrow("SELECT * FROM frames_catalog WHERE frame_id=$1",fid)
        if not f: raise HTTPException(404,"Нет рамки")
        owned=json.loads(user.get("frame_owned") or "[]")
        if fid in owned: raise HTTPException(400,"Уже есть")
        if f["is_premium"] and not is_premium(user): raise HTTPException(403,"Только для премиума")
        # Покупка за бекоины или КП
        method=data.get("method","coins")
        if method=="coins" and f["price_coins"]:
            if (user.get("coins") or 0)<f["price_coins"]: raise HTTPException(400,"Не хватает 🏅")
            await conn.execute("UPDATE users SET coins=coins-$1,frame_owned=$2 WHERE id=$3",f["price_coins"],json.dumps(owned+[fid]),user["id"])
        elif method=="kp" and f["price_kp"]:
            if (user.get("quest_points") or 0)<f["price_kp"]: raise HTTPException(400,"Не хватает КП")
            await conn.execute("UPDATE users SET quest_points=quest_points-$1,frame_owned=$2 WHERE id=$3",f["price_kp"],json.dumps(owned+[fid]),user["id"])
        else:
            raise HTTPException(400,"Способ оплаты не подходит")
    return {"ok":True}

@app.post("/api/frames/set")
async def frames_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    fid=data.get("frame_id","none")
    p=await get_pool()
    async with p.acquire() as conn:
        f=await conn.fetchrow("SELECT * FROM frames_catalog WHERE frame_id=$1",fid)
        if not f: raise HTTPException(404,"Нет рамки")
        if fid!="none":
            owned=json.loads(user.get("frame_owned") or "[]")
            if fid not in owned: raise HTTPException(403,"Не куплена")
            if f["is_premium"] and not is_premium(user): raise HTTPException(403,"Только для премиума")
        await conn.execute("UPDATE users SET active_frame=$1 WHERE id=$2",fid if fid!="none" else None,user["id"])
    return {"ok":True}

# ==================== ГРУППОВЫЕ ЗВОНКИ ====================
@app.post("/api/calls/group/create")
async def calls_group_create(data:dict):
    """Создать групповую комнату (SFU-lite: до 5-6 видео, остальные аудио)"""
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if not is_premium(user): raise HTTPException(403,"Только для премиума")
    p=await get_pool()
    async with p.acquire() as conn:
        # Закрываем старые комнаты юзера
        await conn.execute("UPDATE call_rooms SET closed_at=NOW() WHERE owner_id=$1 AND closed_at IS NULL",user["id"])
        code=secrets.token_urlsafe(6)[:10]
        r=await conn.fetchrow("INSERT INTO call_rooms(owner_id,room_code) VALUES($1,$2) RETURNING *",user["id"],code)
        await conn.execute("INSERT INTO call_participants(room_id,user_id) VALUES($1,$2)",r["id"],user["id"])
    return {"room_id":r["id"],"room_code":code}

@app.post("/api/calls/group/join")
async def calls_group_join(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if not is_premium(user): raise HTTPException(403,"Только для премиума")
    code=(data.get("room_code") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM call_rooms WHERE room_code=$1 AND closed_at IS NULL",code)
        if not r: raise HTTPException(404,"Нет комнаты")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM call_participants WHERE room_id=$1",r["id"])
        if cnt>=30: raise HTTPException(400,"Комната полна")
        try: await conn.execute("INSERT INTO call_participants(room_id,user_id) VALUES($1,$2)",r["id"],user["id"])
        except: pass
        parts=await conn.fetch("SELECT u.id,u.username,u.avatar FROM users u JOIN call_participants cp ON cp.user_id=u.id WHERE cp.room_id=$1",r["id"])
    await manager.broadcast({"type":"call_group_join","room_code":code,"user_id":user["id"],"username":user["username"]})
    return {"room_id":r["id"],"room_code":code,"participants":[dict(p) for p in parts]}

@app.post("/api/calls/group/leave")
async def calls_group_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    code=(data.get("room_code") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT id FROM call_rooms WHERE room_code=$1 AND closed_at IS NULL",code)
        if not r: return {"ok":True}
        await conn.execute("DELETE FROM call_participants WHERE room_id=$1 AND user_id=$2",r["id"],user["id"])
        cnt=await conn.fetchval("SELECT COUNT(*) FROM call_participants WHERE room_id=$1",r["id"])
        if cnt==0: await conn.execute("UPDATE call_rooms SET closed_at=NOW() WHERE id=$1",r["id"])
    await manager.broadcast({"type":"call_group_leave","room_code":code,"user_id":user["id"]})
    return {"ok":True}

@app.get("/api/calls/group/state")
async def calls_group_state(room_code:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM call_rooms WHERE room_code=$1 AND closed_at IS NULL",room_code)
        if not r: raise HTTPException(404,"Нет")
        parts=await conn.fetch("SELECT u.id,u.username,u.avatar FROM users u JOIN call_participants cp ON cp.user_id=u.id WHERE cp.room_id=$1",r["id"])
    return {"room_id":r["id"],"owner_id":r["owner_id"],"participants":[dict(p) for p in parts]}

# ==================== FREEDOOM ====================
@app.get("/api/doom/")
async def doom_page():
    # Проверяем есть ли freedoom.wad в uploads
    wad_path=os.path.join(UPLOAD_DIR,"freedoom1.wad")
    if not os.path.exists(wad_path):
        return HTMLResponse("""
        <html><body style="background:#000;color:#fff;font-family:monospace;padding:40px;text-align:center">
        <h1>💀 FREEDOOM</h1>
        <p>Нужен файл <b>freedoom1.wad</b> в папке uploads/</p>
        <p>Скачай бесплатно: <a href="https://freedoom.github.io/download.html" target="_blank" style="color:#d946ef">freedoom.github.io</a></p>
        <p>Файл: <code>freedoom1.wad</code> (~28 МБ)</p>
        </body></html>
        """)
    return HTMLResponse(f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>💀 FREEDOOM</title>
    <style>body{{margin:0;background:#000;overflow:hidden}}canvas{{display:block;margin:0 auto;max-width:100%;height:100vh}}</style>
    </head><body>
    <div id="status" style="position:fixed;top:10px;left:10px;color:#0f0;font-family:monospace;z-index:10">Загрузка FREEDOOM...</div>
    <script>
    window.addEventListener('load',function(){{
        var script=document.createElement('script');
        script.src='https://cdn.jsdelivr.net/npm/@js-dos/doom@1.0.0/dist/doom.min.js';
        script.onload=function(){{
            document.getElementById('status').textContent='Загружено! WAD: /uploads/freedoom1.wad';
        }};
        script.onerror=function(){{
            document.getElementById('status').textContent='❌ Не удалось загрузить. Нужен js-dos/doom-wasm.';
        }};
        document.head.appendChild(script);
    }});
    </script>
    </body></html>
    """)

# ==================== ITCH.IO EMBED ====================
@app.get("/api/itch/list")
async def itch_list():
    """Список itch.io игр для встраивания (прокси)"""
    return {"games":[
        {"name":"Dungeon Dash","url":"https://itch.io/embed-upload/0000?color=333333","emoji":"🏰"},
        {"name":"Roguelike","url":"https://itch.io/embed-upload/1111?color=333333","emoji":"⚔️"},
    ],"note":"Владелец может добавить свои itch.io игры через /api/itch/add"}

# ==================== WEBSOCKET MANAGER (с kick) ====================
class ConnectionManager:
    def __init__(self): self.connections={}
    async def connect(self,uid,ws):
        await ws.accept()
        self.connections.setdefault(uid,[]).append(ws)
        online_users.add(uid)
    def disconnect(self,uid,ws):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except ValueError: pass
            if not self.connections[uid]:
                del self.connections[uid]
                online_users.discard(uid)
    async def send_to(self,uid,data):
        # FIX: чистка мёртвых сокетов
        for ws in list(self.connections.get(uid,[])):
            try: await ws.send_json(data)
            except:
                self.disconnect(uid,ws)
    async def broadcast(self,data,exclude=None):
        for uid,conns in list(self.connections.items()):
            if exclude and uid==exclude: continue
            for ws in list(conns):
                try: await ws.send_json(data)
                except:
                    self.disconnect(uid,ws)
    async def kick(self,uid):
        """FIX: рвём все WS юзера"""
        for ws in list(self.connections.get(uid,[])):
            try: await ws.close()
            except: pass
        self.connections.pop(uid,None)
        online_users.discard(uid)
manager=ConnectionManager()

# ==================== WEBSOCKET ENDPOINT (с фиксами) ====================
@app.websocket("/ws")
async def websocket_endpoint(ws:WebSocket,token:str):
    user=await get_current_user(token)
    if not user:
        await ws.close(); return
    # FIX: забаненных не пускаем
    if user.get("is_banned"):
        await ws.close(); return
    uid=user["id"]
    await manager.connect(uid,ws)
    try: await ws.send_json({"type":"online_list","users":list(online_users)})
    except: pass
    await manager.broadcast({"type":"user_online","user_id":uid},exclude=uid)
    try:
        while True:
            raw=await ws.receive_text()
            # Периодически чистим трекеры
            cleanup_trackers()
            try: data=json.loads(raw)
            except: continue
            t=data.get("type")
            # FIX: проверка мута
            is_muted=False
            if user.get("mute_until"):
                try:
                    mu=user["mute_until"]
                    if mu and mu>datetime.datetime.now(datetime.timezone.utc): is_muted=True
                except: pass
            if t in ("message","dm","group_msg","sticker") and is_muted:
                await manager.send_to(uid,{"type":"muted","reason":"Ты в муте"})
                continue
            if t=="message":
                ch=data.get("channel_id"); text=(data.get("text") or "")[:2000]
                furl=data.get("file_url"); tid=data.get("temp_id"); reply=data.get("reply_to")
                if not ch: continue
                await check_spam(uid)
                await check_flood(uid,text)
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,reply_to) VALUES($1,$2,$3,$4,$5) RETURNING *",int(ch),uid,text,furl,reply)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    mc=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                    await add_last_message_at(conn,channel_id=int(ch))
                if mc==1: await grant_achievement(uid,"first_msg")
                if mc==100: await grant_achievement(uid,"msg_100")
                if mc==1000: await grant_achievement(uid,"msg_1000")
                if mc==10000: await grant_achievement(uid,"msg_10000")
                await grant_quest_progress(uid,"send_10_msgs",1)
                payload={"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"reply_to":reply,"created_at":msg["created_at"].isoformat(),"is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),"is_beta_tester":user.get("is_beta_tester"),"is_scam":user.get("is_scam"),"is_streamer":user.get("is_streamer"),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"role":get_role(user),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)
            elif t=="dm":
                to_id=int(data.get("to_user",0)); text=(data.get("text") or "")[:2000]
                furl=data.get("file_url"); tid=data.get("temp_id")
                if await is_blocked(uid,to_id): continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",uid,to_id,text,furl)
                await grant_quest_progress(uid,"send_5_dms",1)
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"temp_id":tid}
                await manager.send_to(to_id,payload)
                await manager.send_to(uid,payload)
            elif t=="group_msg":
                gid=int(data.get("group_id",0)); text=(data.get("text") or "")[:2000]
                furl=data.get("file_url"); tid=data.get("temp_id")
                p=await get_pool()
                async with p.acquire() as conn:
                    m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
                    if not m: continue
                    msg=await conn.fetchrow("INSERT INTO group_messages(group_id,user_id,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",gid,uid,text,furl)
                    members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                    await add_last_message_at(conn,group_id=gid)
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)
            elif t=="sticker":
                gid=int(data.get("group_id",0)) if data.get("group_id") else None
                ch=int(data.get("channel_id",0)) if data.get("channel_id") else None
                sticker=data.get("sticker")
                if not sticker: continue
                payload={"type":"sticker","sticker":sticker,"user_id":uid,"username":user["username"],"channel_id":ch,"group_id":gid,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}
                if ch:
                    p=await get_pool()
                    async with p.acquire() as conn:
                        members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",ch)
                    for m in members: await manager.send_to(m["user_id"],payload)
                elif gid:
                    p=await get_pool()
                    async with p.acquire() as conn:
                        members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                    for m in members: await manager.send_to(m["user_id"],payload)
            elif t=="typing":
                ch=data.get("channel_id")
                p=await get_pool()
                async with p.acquire() as conn:
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                for m in members:
                    if m["user_id"]!=uid: await manager.send_to(m["user_id"],{"type":"typing","channel_id":ch,"username":user["username"]})
            elif t=="typing_dm":
                await manager.send_to(int(data.get("to_user",0)),{"type":"typing_dm","from":uid,"username":user["username"]})
            elif t=="call_offer":
                await manager.send_to(int(data.get("to",0)),{"type":"call_offer","from":uid,"sdp":data.get("sdp"),"username":user["username"],"avatar":user.get("avatar")})
            elif t=="call_answer":
                await manager.send_to(int(data.get("to",0)),{"type":"call_answer","from":uid,"sdp":data.get("sdp")})
            elif t=="call_ice":
                await manager.send_to(int(data.get("to",0)),{"type":"call_ice","from":uid,"candidate":data.get("candidate")})
            elif t=="call_decline":
                await manager.send_to(int(data.get("to",0)),{"type":"call_decline","from":uid})
            elif t=="call_end":
                await manager.send_to(int(data.get("to",0)),{"type":"call_end","from":uid})
            # Групповые звонки (SFU-lite: пересылаем SDP/ICE по комнате)
            elif t=="call_group_offer":
                room=int(data.get("room_id",0))
                p=await get_pool()
                async with p.acquire() as conn:
                    parts=await conn.fetch("SELECT user_id FROM call_participants WHERE room_id=$1 AND user_id!=$2",room,uid)
                for pp in parts:
                    await manager.send_to(pp["user_id"],{"type":"call_group_offer","from":uid,"room_id":room,"sdp":data.get("sdp"),"username":user["username"],"avatar":user.get("avatar")})
            elif t=="call_group_answer":
                room=int(data.get("room_id",0))
                p=await get_pool()
                async with p.acquire() as conn:
                    parts=await conn.fetch("SELECT user_id FROM call_participants WHERE room_id=$1 AND user_id!=$2",room,uid)
                for pp in parts:
                    await manager.send_to(pp["user_id"],{"type":"call_group_answer","from":uid,"room_id":room,"sdp":data.get("sdp")})
            elif t=="call_group_ice":
                room=int(data.get("room_id",0))
                p=await get_pool()
                async with p.acquire() as conn:
                    parts=await conn.fetch("SELECT user_id FROM call_participants WHERE room_id=$1 AND user_id!=$2",room,uid)
                for pp in parts:
                    await manager.send_to(pp["user_id"],{"type":"call_group_ice","from":uid,"room_id":room,"candidate":data.get("candidate")})
    except WebSocketDisconnect: pass
    except Exception as e: print(f"WS error: {e}")
    finally:
        manager.disconnect(uid,ws)
        try:
            p=await get_pool()
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET last_seen=NOW() WHERE id=$1",uid)
        except: pass
        await manager.broadcast({"type":"user_offline","user_id":uid})

# ==================== STATIC / MANIFEST / DOOM ====================
@app.get("/manifest.json")
async def manifest():
    return {"name":"Belugacord Beta 2.2","short_name":"Belugacord","start_url":"/","display":"standalone","background_color":"#0a0a12","theme_color":"#0a0a12","icons":[{"src":"/uploads/icon.png","sizes":"192x192","type":"image/png"}]}

@app.get("/sw.js")
async def sw():
    return FileResponse("sw.js") if os.path.exists("sw.js") else HTMLResponse("// no sw")

@app.get("/")
async def index():
    with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())

if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")