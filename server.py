# BELUGACORD BETA 2.5 — server.py
import os,json,time,secrets,hashlib,random,datetime,asyncio
from typing import Optional
import asyncpg
import httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL=os.environ.get("DATABASE_URL","")
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2026")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","")
ADMIN_USERNAME="_fan_beluga_"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="2.5"

# ============ 2.5 FIX: whitelist расширений + MIME ============
ALLOWED_EXT={'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mov','.mp3','.wav','.ogg','.m4a','.pdf','.txt','.zip','.json'}
ALLOWED_MIME={'image/png','image/jpeg','image/gif','image/webp','image/svg+xml','video/mp4','video/webm','video/quicktime','audio/mpeg','audio/wav','audio/ogg','audio/mp4','audio/webm','application/pdf','text/plain','application/zip','application/json','application/octet-stream'}

LIMITS={None:{"file":10*1024*1024,"msg":2000,"servers":10,"channels":20,"groups":10},"premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100,"groups":30},"pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999,"groups":30}}
PREMIUM_PRICES={"month":1500,"year":18000}
QUEST_EXCHANGE={"1day":{"cost":1400,"days":1},"3days":{"cost":7500,"days":3},"7days":{"cost":10000,"days":7}}

DEFAULT_GIFTS={"rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},"cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},"crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},"legend":{"name":"Легендарка","emoji":"💠","price":5000},"alien":{"name":"Инопланетянин","emoji":"👽","price":10000},"galaxy":{"name":"Галактика","emoji":"🌌","price":100000},"goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},"universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000}}
GAME_LIST=["penguin","minesweeper","snake","2048","flappy","tetris","memory","reaction","tictactoe","rps","battleship","duel","freedoom"]

ACHIEVEMENTS={"first_msg":{"name":"Первое слово","emoji":"💬","desc":"Отправь первое сообщение"},"msg_100":{"name":"Болтун","emoji":"🗣️","desc":"100 сообщений"},"msg_1000":{"name":"Оратор","emoji":"🎤","desc":"1000 сообщений"},"msg_10000":{"name":"Легенда чата","emoji":"📢","desc":"10000 сообщений"},"first_friend":{"name":"Дружелюбный","emoji":"👥","desc":"Первый друг"},"friend_10":{"name":"Тусовщик","emoji":"🎉","desc":"10 друзей"},"first_gift":{"name":"Щедрый","emoji":"🎁","desc":"Первый подарок"},"first_nft":{"name":"Коллекционер","emoji":"🎨","desc":"Первый NFT"},"snake_100":{"name":"Змеелов","emoji":"🐍","desc":"100 очков в Змейке"},"flappy_50":{"name":"Летун","emoji":"🐦","desc":"50 очков в Flappy"},"first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},"coins_10k":{"name":"Богач","emoji":"💰","desc":"10000 бекоинов"},"rating_100":{"name":"Щедрая душа","emoji":"💎","desc":"Соц.рейтинг 100"},"rating_10000":{"name":"Меценат","emoji":"👑","desc":"Соц.рейтинг 10000"}}

CHANGELOG={
"2.5":{"title":"Belugacord Beta 2.5","items":["🛠️ Фикс всех багов 2.4","🏆 Полный БП-конструктор (награды, квесты, длительность)","📢 Сообщение от лица владельца (ава+ник+текст)","🧹 Чистка мёртвого кода","🔒 Валидация загрузок по MIME+расширению","💓 WS ping/pong","🎨 Эффекты сообщений реально работают","⚡ Хот-свап контента","📊 Улучшенный БОГ-ГУИ","🐛 Фиксы slowmode / кэша / prompt-модалок"]},
"2.4":{"title":"Belugacord Beta 2.4","items":["🎮 13 игр","⚡ Медленный режим","📝 Форматирование","📎 Drag-drop файлов","👁️ Шпион","💀 Самоуничтожение"]},
"2.3":{"title":"Belugacord Beta 2.3","items":["⬆️ Апгрейдер-колесо","🎤 Голосовые","📸 Сторис","🧵 Треды","💎 Премиум","🏦 Банк","🔨 Аукцион","🎰 Рулетка"]}}

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
friend_target_spam={}
flood_tracker={}
abuse_timer_task=None
last_cleanup=time.time()
active_events=[]
upgrade_chance_bonus={}
custom_commands={}

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=5)
    return pool

# ============ DB INIT ============
async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE NOT NULL,password_hash VARCHAR(128) NOT NULL,avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,email_code VARCHAR(16),email_code_expires TIMESTAMP,is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,is_beta_tester BOOLEAN DEFAULT FALSE,is_scam BOOLEAN DEFAULT FALSE,is_dev BOOLEAN DEFAULT FALSE,is_streamer BOOLEAN DEFAULT FALSE,premium_tier VARCHAR(8),premium_expires TIMESTAMP,is_banned BOOLEAN DEFAULT FALSE,shadow_banned BOOLEAN DEFAULT FALSE,ban_reason VARCHAR(256),mute_until TIMESTAMP,nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),custom_status VARCHAR(128),online_status VARCHAR(16) DEFAULT 'online',bio VARCHAR(256),fav_music VARCHAR(128),gifts_hidden BOOLEAN DEFAULT FALSE,easter_found TEXT DEFAULT '[]',easter_rewarded BOOLEAN DEFAULT FALSE,admin_password VARCHAR(128),coins INTEGER DEFAULT 0,social_rating INTEGER DEFAULT 0,messages_count INTEGER DEFAULT 0,frozen BOOLEAN DEFAULT FALSE,is_legend BOOLEAN DEFAULT FALSE,wallpaper TEXT,font_choice VARCHAR(32),compact_mode BOOLEAN DEFAULT FALSE,achievements TEXT DEFAULT '[]',quest_points INTEGER DEFAULT 0,daily_bonus_at TIMESTAMP,quest_day VARCHAR(16),quest_progress TEXT DEFAULT '{}',quest_claimed TEXT DEFAULT '[]',active_frame VARCHAR(32),frame_owned TEXT DEFAULT '[]',title VARCHAR(32),reputation INTEGER DEFAULT 0,level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,chest_streak INTEGER DEFAULT 0,chest_at TIMESTAMP,bank_deposit INTEGER DEFAULT 0,bank_at TIMESTAMP,last_seen TIMESTAMP DEFAULT NOW(),created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,banner TEXT,description TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',mode VARCHAR(16) DEFAULT 'public',paid_reaction_cost INTEGER DEFAULT 10,last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,reply_to INTEGER,thread_root INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,effect VARCHAR(16) DEFAULT 'none',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,gif_avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_appeals(id SERIAL PRIMARY KEY,username VARCHAR(32),text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS reports(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,coins INTEGER NOT NULL,price INTEGER DEFAULT 0,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,gif_image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_market(id SERIAL PRIMARY KEY,item_id INTEGER REFERENCES nft_items(id) ON DELETE CASCADE,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,price INTEGER NOT NULL,status VARCHAR(16) DEFAULT 'active',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),item_image TEXT,chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_opens(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,prize_text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS abuse_grants(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,can_gift BOOLEAN DEFAULT TRUE,can_nft BOOLEAN DEFAULT TRUE,can_coins BOOLEAN DEFAULT TRUE,can_online BOOLEAN DEFAULT TRUE,can_timer BOOLEAN DEFAULT TRUE,can_write BOOLEAN DEFAULT TRUE,expires_at TIMESTAMP NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_requests(id SERIAL PRIMARY KEY,from_admin INTEGER REFERENCES users(id) ON DELETE SET NULL,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,reason TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS suspicious_logs(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,action VARCHAR(64),details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS auto_abuse(id SERIAL PRIMARY KEY,enabled BOOLEAN DEFAULT FALSE,kind VARCHAR(16),every_minutes INTEGER DEFAULT 60,next_run TIMESTAMP,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS owner_messages(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_themes(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),vars TEXT,bg_image TEXT,border_radius VARCHAR(16),blur VARCHAR(32),created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS spam_alerts(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text_sample TEXT,count INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS premium_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,bought_at TIMESTAMP DEFAULT NOW(),tier VARCHAR(8),days INTEGER,paid_coins INTEGER,method VARCHAR(16))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS quests_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,quest_key VARCHAR(32),reward_kp INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS upgrade_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,from_gift VARCHAR(32),to_gift VARCHAR(32),success BOOLEAN,chance REAL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_rooms(id SERIAL PRIMARY KEY,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,room_code VARCHAR(16) UNIQUE,is_group BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT NOW(),closed_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_participants(room_id INTEGER REFERENCES call_rooms(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(room_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),css TEXT,is_animated BOOLEAN DEFAULT FALSE,is_premium BOOLEAN DEFAULT FALSE,price_coins INTEGER DEFAULT 0,price_kp INTEGER DEFAULT 0)""")
        for f in [("none","Без рамки","","none",False,False,0,0),("gold","Золотая","👑","2px solid #ffd700;box-shadow:0 0 12px rgba(255,215,0,0.7)",False,False,500,0),("fire","Огненная","🔥","2px solid #ff6b35;box-shadow:0 0 14px rgba(255,107,53,0.8)",False,False,800,0),("ice","Ледяная","❄️","2px solid #22d3ee;box-shadow:0 0 14px rgba(34,211,238,0.8)",False,False,800,0),("rainbow","Радужная","🌈","2px solid #d946ef;box-shadow:0 0 16px rgba(217,70,239,0.8)",False,True,0,3000),("neon","Неоновая","💜","2px solid #ff00ff;box-shadow:0 0 18px rgba(255,0,255,0.9)",False,True,0,3000),("pulse","Пульс","💗","2px solid #ec4899;animation:framePulse 1.5s infinite",True,True,0,5000),("spin","Вращение","🌀","2px solid #22c55e;animation:frameSpin 3s linear infinite",True,True,0,5000)]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,css,is_animated,is_premium,price_coins,price_kp) VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (frame_id) DO NOTHING",*f)
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS stories(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,image TEXT,text TEXT,bg_color VARCHAR(16) DEFAULT '#000',views TEXT DEFAULT '[]',reactions TEXT DEFAULT '{}',created_at TIMESTAMP DEFAULT NOW(),expires_at TIMESTAMP DEFAULT NOW()+INTERVAL '24 hours')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS story_replies(id SERIAL PRIMARY KEY,story_id INTEGER REFERENCES stories(id) ON DELETE CASCADE,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,message_id INTEGER,text TEXT,from_user INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_reactions(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,url TEXT NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS rep_given(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_quests(id SERIAL PRIMARY KEY,name VARCHAR(128),description TEXT,goal INTEGER,xp_reward INTEGER DEFAULT 100,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_rewards(id SERIAL PRIMARY KEY,level INTEGER,reward TEXT,active BOOLEAN DEFAULT TRUE)""")
        # 2.5 NEW: ends_at + days_total для БП
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_season(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🏆',started_at TIMESTAMP DEFAULT NOW(),ended_at TIMESTAMP,ends_at TIMESTAMP,days_total INTEGER DEFAULT 30,active BOOLEAN DEFAULT TRUE)""")
        try: await conn.execute("ALTER TABLE bp_season ADD COLUMN IF NOT EXISTS ends_at TIMESTAMP")
        except: pass
        try: await conn.execute("ALTER TABLE bp_season ADD COLUMN IF NOT EXISTS days_total INTEGER DEFAULT 30")
        except: pass
        try: await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS shadow_banned BOOLEAN DEFAULT FALSE")
        except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_progress(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_id INTEGER,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,claimed TEXT DEFAULT '[]',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS events(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🎉',event_type VARCHAR(16),multiplier INTEGER DEFAULT 1,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,started_at TIMESTAMP DEFAULT NOW(),end_at TIMESTAMP,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS commands(id SERIAL PRIMARY KEY,name VARCHAR(32) UNIQUE,description TEXT,response TEXT,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS lottery(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,tickets INTEGER DEFAULT 0,updated_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS lottery_history(id SERIAL PRIMARY KEY,winner_id INTEGER,winner_name VARCHAR(32),amount INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS auction(id SERIAL PRIMARY KEY,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,item_type VARCHAR(16),item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),start_price INTEGER,current_price INTEGER,current_bidder INTEGER,started_at TIMESTAMP DEFAULT NOW(),ends_at TIMESTAMP,status VARCHAR(16) DEFAULT 'active')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS threads(id SERIAL PRIMARY KEY,root_msg INTEGER REFERENCES messages(id) ON DELETE CASCADE,author_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS rate_limits(user_id INTEGER,action VARCHAR(32),ts TIMESTAMP DEFAULT NOW())""")

# ============ HELPERS ============
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
    return {"id":row["id"],"username":row["username"],"avatar":row["avatar"],"banner":row["banner"],"gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),"avatar_pos":row["avatar_pos"],"banner_pos":row["banner_pos"],"is_admin":row["is_admin"],"is_moderator":row["is_moderator"],"is_beta_tester":row.get("is_beta_tester",False),"is_scam":row.get("is_scam",False),"is_dev":row.get("is_dev",False),"is_streamer":row.get("is_streamer",False),"premium_tier":row.get("premium_tier"),"premium_expires":row["premium_expires"].isoformat() if row.get("premium_expires") else None,"is_premium":is_premium(row),"nickname_color":row.get("nickname_color"),"nickname_gradient":row.get("nickname_gradient"),"custom_status":row.get("custom_status"),"online_status":status,"bio":row.get("bio"),"fav_music":row.get("fav_music"),"coins":row.get("coins",0),"social_rating":row.get("social_rating",0),"messages_count":row.get("messages_count",0),"is_legend":row.get("is_legend",False),"email":row.get("email"),"email_verified":row.get("email_verified",False),"has_admin_pass":bool(row.get("admin_password")),"wallpaper":row.get("wallpaper"),"font_choice":row.get("font_choice"),"compact_mode":row.get("compact_mode",False),"achievements":json.loads(row.get("achievements") or "[]"),"quest_points":row.get("quest_points",0),"active_frame":row.get("active_frame"),"title":row.get("title"),"reputation":row.get("reputation",0),"level":row.get("level",1),"xp":row.get("xp",0),"created_at":row["created_at"].isoformat() if row.get("created_at") else None,"role":get_role(row),"online":is_online}

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

# ============ 2.5 FIX: cleanup_trackers теперь чистит friend_target_spam ============
def cleanup_trackers():
    global last_cleanup
    now=time.time()
    if now-last_cleanup<300: return
    last_cleanup=now
    for d in (spam_tracker,friend_spam_tracker):
        for k in list(d.keys()):
            arr=[t for t in d[k] if now-t<600]
            if not arr: del d[k]
            else: d[k]=arr
    for k in list(flood_tracker.keys()):
        arr=[t for t in flood_tracker[k] if now-t[1]<300]
        if not arr: del flood_tracker[k]
        else: flood_tracker[k]=arr
    # 2.5 NEW: чистим friend_target_spam
    for k in list(friend_target_spam.keys()):
        arr=[t for t in friend_target_spam[k] if now-t<600]
        if not arr: del friend_target_spam[k]
        else: friend_target_spam[k]=arr

async def add_last_message_at(conn,channel_id=None,group_id=None):
    now=datetime.datetime.now(datetime.timezone.utc)
    if channel_id:
        await conn.execute("UPDATE channels SET last_message_at=$1 WHERE id=$2",now,channel_id)
    if group_id:
        await conn.execute("UPDATE groups SET last_message_at=$1 WHERE id=$2",now,group_id)

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
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT daily_bonus_at FROM users WHERE id=$1",uid)
            if not row: return {"ok":False,"reason":"no_user"}
            now=datetime.datetime.now(datetime.timezone.utc)
            last=row["daily_bonus_at"]
            if last and (now-last).total_seconds()<86400:
                return {"ok":False,"reason":"already","next_in":int(86400-(now-last).total_seconds())}
            bonus=1
            user=await conn.fetchrow("SELECT premium_tier,premium_expires FROM users WHERE id=$1",uid)
            prem=False
            if user and user["premium_tier"] and (not user["premium_expires"] or user["premium_expires"]>now):
                prem=True
                bonus=3
            await conn.execute("UPDATE users SET coins=coins+$1,daily_bonus_at=$2 WHERE id=$3",bonus,now,uid)
            return {"ok":True,"amount":bonus,"premium":prem}
    except Exception as e: return {"ok":False,"reason":str(e)}

def get_upgrade_chance_bonus(uid):
    return upgrade_chance_bonus.get(uid,0)

def apply_event_multiplier(base,event_type):
    mult=base
    now=datetime.datetime.now(datetime.timezone.utc)
    for e in active_events:
        if e.get("active") and e.get("event_type")==event_type:
            if e.get("end_at") and e["end_at"]>now:
                mult=base*e.get("multiplier",1)
    return mult

async def grant_xp(uid,amount):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT xp,level FROM users WHERE id=$1",uid)
            if not row: return
            amount=apply_event_multiplier(amount,"xp_x")
            new_xp=row["xp"]+amount
            new_level=row["level"]
            while new_xp>=(new_level*100):
                new_xp-=new_level*100
                new_level+=1
                await manager.send_to(uid,{"type":"level_up","level":new_level})
            await conn.execute("UPDATE users SET xp=$1,level=$2 WHERE id=$3",new_xp,new_level,uid)
    except: pass

# ============ BACKGROUND LOOPS ============
async def lottery_draw_loop():
    while True:
        try:
            await asyncio.sleep(3600)
            p=await get_pool()
            async with p.acquire() as conn:
                rows=await conn.fetch("SELECT user_id,tickets FROM lottery WHERE tickets>0")
                if not rows: continue
                pool_tickets=[]
                for r in rows: pool_tickets.extend([r["user_id"]]*r["tickets"])
                if not pool_tickets: continue
                winner=random.choice(pool_tickets)
                total=sum(r["tickets"] for r in rows)*100
                jackpot=int(total*0.7)
                w=await conn.fetchrow("SELECT username FROM users WHERE id=$1",winner)
                if w:
                    await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",jackpot,winner)
                    await conn.execute("INSERT INTO lottery_history(winner_id,winner_name,amount) VALUES($1,$2,$3)",winner,w["username"],jackpot)
                    await conn.execute("DELETE FROM lottery")
                    await manager.send_to(winner,{"type":"coins_approved","amount":jackpot})
                    await manager.broadcast({"type":"event","event":"confetti"})
        except Exception as e:
            print(f"Lottery loop: {e}")
            await asyncio.sleep(60)

# 2.5 FIX: auto_abuse_loop с корректным SQL для next_run
async def auto_abuse_loop():
    while True:
        try:
            await asyncio.sleep(60)
            p=await get_pool()
            async with p.acquire() as conn:
                row=await conn.fetchrow("SELECT * FROM auto_abuse WHERE enabled=TRUE AND next_run<=NOW() LIMIT 1")
                if not row: continue
                kind=row["kind"]; every=row["every_minutes"]
                next_run=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=every)
                await conn.execute("UPDATE auto_abuse SET next_run=$1 WHERE id=$2",next_run,row["id"])
            if not online_users: continue
            tid=random.choice(list(online_users))
            if kind=="gift":
                g=await get_all_gifts()
                if g:
                    gid=random.choice(list(g.keys())); gift=g[gid]
                    p=await get_pool()
                    async with p.acquire() as conn:
                        t=await conn.fetchrow("SELECT username,avatar FROM users WHERE id=$1",tid)
                        if t:
                            await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",1,tid,gid)
                            await manager.broadcast({"type":"abuse_win","kind":"gift","username":t["username"],"avatar":t.get("avatar"),"item_name":gift["name"],"item_emoji":gift.get("emoji"),"price":gift["price"]})
            elif kind=="coins":
                amt=random.randint(100,10000)
                p=await get_pool()
                async with p.acquire() as conn:
                    t=await conn.fetchrow("SELECT username,avatar FROM users WHERE id=$1",tid)
                    if t:
                        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,tid)
                        await manager.broadcast({"type":"abuse_win","kind":"coins","username":t["username"],"avatar":t.get("avatar"),"item_name":f"{amt} 🏅","item_emoji":"🏅","price":amt})
        except Exception as e:
            print(f"Auto-abuse loop: {e}")
            await asyncio.sleep(60)

async def events_cleanup_loop():
    while True:
        try:
            await asyncio.sleep(30)
            p=await get_pool()
            async with p.acquire() as conn:
                # 2.5 NEW: авто-завершение БП по ends_at
                bp_ended=await conn.fetch("SELECT id FROM bp_season WHERE active=TRUE AND ends_at IS NOT NULL AND ends_at<=NOW()")
                for r in bp_ended:
                    await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE id=$1",r["id"])
                    await manager.broadcast({"type":"bp_update","ended":True})
                rows=await conn.fetch("SELECT id FROM events WHERE active=TRUE AND end_at<=NOW()")
                for r in rows:
                    await conn.execute("UPDATE events SET active=FALSE WHERE id=$1",r["id"])
                    for e in active_events:
                        if e["id"]==r["id"]: e["active"]=False
                    await manager.broadcast({"type":"event_end","id":r["id"]})
        except Exception as e:
            print(f"Events loop: {e}")
            await asyncio.sleep(60)

async def auction_cleanup_loop():
    while True:
        try:
            await asyncio.sleep(30)
            p=await get_pool()
            async with p.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM auction WHERE status='active' AND ends_at<=NOW()")
                for r in rows:
                    if r["current_bidder"]:
                        await conn.execute("UPDATE auction SET status='sold' WHERE id=$1",r["id"])
                        await manager.send_to(r["current_bidder"],{"type":"dm","from_user":0,"to_user":r["current_bidder"],"username":"🔨 Аукцион","text":f"Ты выиграл лот: {r['item_name']} за {r['current_price']} 🏅","created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})
                        if r["item_id"]:
                            await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",1,r["current_bidder"],r["item_id"])
                    else:
                        await conn.execute("UPDATE auction SET status='ended' WHERE id=$1",r["id"])
        except Exception as e:
            print(f"Auction loop: {e}")
            await asyncio.sleep(60)

async def startup_tasks():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM events WHERE active=TRUE AND end_at>NOW()")
            for r in rows:
                active_events.append({"id":r["id"],"name":r["name"],"description":r["description"],"emoji":r["emoji"],"event_type":r["event_type"],"multiplier":r["multiplier"],"end_at":r["end_at"],"active":True})
            cmds=await conn.fetch("SELECT name,response FROM commands")
            for c in cmds:
                custom_commands[c["name"]]=c["response"]
    except Exception as e:
        print(f"Startup tasks: {e}")
    asyncio.create_task(lottery_draw_loop())
    asyncio.create_task(auto_abuse_loop())
    asyncio.create_task(events_cleanup_loop())
    asyncio.create_task(auction_cleanup_loop())
    print("🐱 Background loops started (2.5)")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try:
            await init_db()
            await startup_tasks()
        except Exception as e:
            print(f"DB init: {e}")

# ============ HTTP ============
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

@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    premium=is_premium(user)
    gif_av=data.get("gif_avatar"); gif_bn=data.get("gif_banner")
    if (gif_av or gif_bn) and not premium: raise HTTPException(403,"GIF только для премиума")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),gif_avatar=COALESCE($3,gif_avatar),gif_banner=COALESCE($4,gif_banner),avatar_pos=COALESCE($5,avatar_pos),banner_pos=COALESCE($6,banner_pos),nickname_color=$7,nickname_gradient=$8,bio=COALESCE($9,bio),fav_music=COALESCE($10,fav_music),wallpaper=COALESCE($11,wallpaper),font_choice=$12,compact_mode=COALESCE($13,compact_mode),custom_status=COALESCE($14,custom_status) WHERE id=$15""",
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
    await manager.broadcast({"type":"status_update","user_id":user["id"],"online_status":st,"custom_status":custom or None})
    return {"ok":True}

@app.get("/api/user/{user_id}")
async def get_user(user_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id,username,avatar,banner,gif_avatar,gif_banner,avatar_pos,banner_pos,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,premium_expires,nickname_color,nickname_gradient,bio,fav_music,custom_status,online_status,messages_count,is_legend,achievements,social_rating,coins,quest_points,active_frame,title,reputation,level,xp,created_at,last_seen FROM users WHERE id=$1",user_id)
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

@app.get("/api/users/search")
async def users_search(q:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip()
    if len(q)<2: return []
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username,avatar,gif_avatar,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,premium_expires,online_status,title FROM users WHERE username ILIKE $1 AND id!=$2 ORDER BY username LIMIT 20",f"%{q}%",user["id"])
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); d["is_premium"]=is_premium(r); d["online"]=r["id"] in online_users; out.append(d)
    return out

# ============ FRIENDS ============
@app.get("/api/friends/list")
async def friends_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    uid=user["id"]
    p=await get_pool()
    async with p.acquire() as conn:
        frows=await conn.fetch("SELECT id,user_a,user_b FROM friendships WHERE user_a=$1 OR user_b=$1",uid)
        inc=await conn.fetch("SELECT r.id,r.from_user,u.username,u.avatar,u.gif_avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires FROM friend_requests r JOIN users u ON u.id=r.from_user WHERE r.to_user=$1 ORDER BY r.created_at DESC",uid)
        out=await conn.fetch("SELECT r.id,r.to_user,u.username,u.avatar FROM friend_requests r JOIN users u ON u.id=r.to_user WHERE r.from_user=$1 ORDER BY r.created_at DESC",uid)
        result=[]
        for r in frows:
            oid=r["user_b"] if r["user_a"]==uid else r["user_a"]
            o=await conn.fetchrow("SELECT id,username,avatar,gif_avatar,is_admin,is_moderator,is_beta_tester,is_scam,is_streamer,last_seen,online_status,custom_status,premium_tier,premium_expires,title FROM users WHERE id=$1",oid)
            if not o: continue
            last=await conn.fetchval("SELECT MAX(created_at) FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",uid,oid)
            has_story=await conn.fetchval("SELECT id FROM stories WHERE user_id=$1 AND expires_at>NOW() LIMIT 1",oid)
            result.append({"id":o["id"],"username":o["username"],"avatar":o["avatar"],"gif_avatar":o.get("gif_avatar"),"status":"accepted","friend_row_id":r["id"],"online":o["id"] in online_users and (o.get("online_status") or "online")!="invisible","last_seen":o["last_seen"].isoformat() if o.get("last_seen") else None,"is_admin":o["is_admin"],"is_moderator":o["is_moderator"],"is_beta_tester":o["is_beta_tester"],"is_scam":o["is_scam"],"is_streamer":o.get("is_streamer",False),"custom_status":o.get("custom_status"),"online_status":o.get("online_status") or "online","role":get_role(o),"is_premium":is_premium(o),"last_message_at":last.isoformat() if last else None,"has_story":bool(has_story),"title":o.get("title")})
        for r in inc: result.append({"id":r["from_user"],"username":r["username"],"avatar":r["avatar"],"gif_avatar":r.get("gif_avatar"),"status":"incoming","request_id":r["id"],"online":r["from_user"] in online_users,"is_admin":r["is_admin"],"is_moderator":r["is_moderator"],"is_beta_tester":r["is_beta_tester"],"is_scam":r["is_scam"],"is_streamer":r.get("is_streamer",False),"role":get_role(r),"is_premium":is_premium(r)})
        for r in out: result.append({"id":r["to_user"],"username":r["username"],"avatar":r["avatar"],"status":"outgoing","request_id":r["id"],"online":r["to_user"] in online_users,"is_admin":False,"is_moderator":False,"is_beta_tester":False,"is_scam":False,"role":"user"})
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
        if await check_friend_spam(user["id"],t["id"]): raise HTTPException(429,"Слишком много заявок")
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

# ============ BLOCKS ============
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

# ============ GROUPS ============
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
        rows=await conn.fetch("SELECT gm.id,gm.text,gm.file_url,gm.created_at,gm.user_id,u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires,u.active_frame,u.title FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200",group_id)
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
        rows=await conn.fetch("SELECT u.id,u.username,u.avatar,u.gif_avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires,u.title FROM users u JOIN group_members gm ON gm.user_id=u.id WHERE gm.group_id=$1",group_id)
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
        if cnt>=max_members: raise HTTPException(400,f"Макс {max_members}")
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
    return {"ok":True}

# ============ SERVERS ============
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
    if not s: raise HTTPException(404,"Нет")
    d=dict(s); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
    return d

@app.get("/api/servers/{server_id}/channels")
async def server_channels(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,type,mode,last_message_at FROM channels WHERE server_id=$1 ORDER BY COALESCE(last_message_at,created_at) DESC, id",server_id)
    return [{"id":r["id"],"name":r["name"],"type":r["type"],"mode":r.get("mode") or "public","last_message_at":r["last_message_at"].isoformat() if r.get("last_message_at") else None} for r in rows]

@app.get("/api/servers/{server_id}/members")
async def server_members(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.id,u.username,u.avatar,u.gif_avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires,u.title FROM users u JOIN server_members sm ON sm.user_id=u.id WHERE sm.server_id=$1",server_id)
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

@app.post("/api/channels/set_mode")
async def channel_set_mode(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    cid=int(data.get("channel_id",0))
    mode=data.get("mode","public")
    if mode not in ("public","readonly","paid_reactions","forum"): raise HTTPException(400,"Плохой режим")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT s.owner_id FROM channels c JOIN servers s ON s.id=c.server_id WHERE c.id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец сервера")
        await conn.execute("UPDATE channels SET mode=$1 WHERE id=$2",mode,cid)
    return {"ok":True,"mode":mode}

@app.get("/api/channels/{channel_id}/messages")
async def channel_messages(channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT m.id,m.text,m.file_url,m.reactions,m.edited,m.reply_to,m.thread_root,m.pinned,m.effect,m.created_at,m.user_id,u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires,u.active_frame,u.title FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200",channel_id)
        pinned=await conn.fetch("SELECT m.id,m.text,m.user_id,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.pinned=TRUE ORDER BY m.id DESC LIMIT 5",channel_id)
        chan=await conn.fetchrow("SELECT mode,paid_reaction_cost FROM channels WHERE id=$1",channel_id)
    out=[]
    for r in rows:
        d=dict(r)
        d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["role"]=get_role(r)
        d["is_premium"]=is_premium(r)
        d["reactions"]=json.loads(d.get("reactions") or "{}")
        out.append(d)
    return {"messages":out,"pinned":[dict(p) for p in pinned],"mode":chan["mode"] if chan else "public","paid_cost":chan["paid_reaction_cost"] if chan else 10}

@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if await is_blocked(user["id"],user_id): raise HTTPException(403,"Заблокировано")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.created_at,u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.premium_tier,u.premium_expires,u.active_frame,u.title FROM dms d JOIN users u ON u.id=d.from_user WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC LIMIT 200",user["id"],user_id)
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None; d["is_premium"]=is_premium(r); out.append(d)
    return out

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

@app.post("/api/messages/reaction")
async def message_reaction(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0)); emoji=data.get("emoji","👍")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions,channel_id FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        chan=await conn.fetchrow("SELECT mode,paid_reaction_cost FROM channels WHERE id=$1",row["channel_id"]) if row["channel_id"] else None
        if chan and chan["mode"]=="paid_reactions":
            cost=chan["paid_reaction_cost"] or 10
            if (user.get("coins") or 0)<cost: raise HTTPException(400,f"Нужно {cost} 🏅")
            await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",cost,user["id"])
        react=json.loads(row["reactions"] or "{}")
        arr=react.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        react[emoji]=arr
        await conn.execute("UPDATE messages SET reactions=$1 WHERE id=$2",json.dumps(react),mid)
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":react})
    return {"ok":True}

@app.post("/api/messages/save")
async def message_save(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        msg=await conn.fetchrow("SELECT text,user_id FROM messages WHERE id=$1",mid)
        if not msg: raise HTTPException(404,"Нет")
        await conn.execute("INSERT INTO saved_messages(user_id,message_id,text,from_user) VALUES($1,$2,$3,$4)",user["id"],mid,msg["text"],msg["user_id"])
    return {"ok":True}

@app.get("/api/messages/saved")
async def messages_saved(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT sm.id,sm.text,sm.created_at,u.username FROM saved_messages sm LEFT JOIN users u ON u.id=sm.from_user WHERE sm.user_id=$1 ORDER BY sm.id DESC",user["id"])
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.get("/api/messages/search")
async def messages_search(q:str,channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip()
    if len(q)<2: return []
    p=await get_pool()
    async with p.acquire() as conn:
        if channel_id:
            rows=await conn.fetch("SELECT m.id,m.text,m.created_at,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.text ILIKE $2 ORDER BY m.id DESC LIMIT 50",channel_id,f"%{q}%")
        else:
            rows=await conn.fetch("SELECT m.id,m.text,m.created_at,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.text ILIKE $1 ORDER BY m.id DESC LIMIT 50",f"%{q}%")
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

# ============ 2.5 FIX: /api/upload с MIME + whitelist ============
@app.post("/api/upload")
async def upload(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    lim=LIMITS.get(user.get("premium_tier"),LIMITS[None])["file"]
    # MIME whitelist
    mime=(file.content_type or "application/octet-stream").lower()
    if mime not in ALLOWED_MIME: raise HTTPException(400,f"Тип файла запрещён: {mime}")
    ext=os.path.splitext(file.filename or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT: raise HTTPException(400,f"Расширение запрещено: {ext}")
    content=await file.read()
    if len(content)>lim: raise HTTPException(400,"Файл большой")
    if len(content)==0: raise HTTPException(400,"Пустой файл")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}"}

# ============ THREADS ============
@app.get("/api/threads/{msg_id}")
async def threads_get(msg_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT t.id,t.text,t.created_at,u.username,u.avatar FROM threads t JOIN users u ON u.id=t.author_id WHERE t.root_msg=$1 ORDER BY t.id ASC",msg_id)
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"avatar":r["avatar"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/threads/{msg_id}/reply")
async def threads_reply(msg_id:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO threads(root_msg,author_id,text) VALUES($1,$2,$3)",msg_id,user["id"],text)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM threads WHERE root_msg=$1",msg_id)
    await manager.broadcast({"type":"thread_update","root":msg_id,"count":cnt})
    return {"ok":True,"count":cnt}

# ============ STORIES ============
@app.get("/api/stories/list")
async def stories_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT s.id,s.image,s.text,s.bg_color,s.created_at,s.user_id,u.username,u.avatar FROM stories s JOIN users u ON u.id=s.user_id WHERE s.expires_at>NOW() ORDER BY s.created_at DESC LIMIT 100")
    return [{"id":r["id"],"image":r["image"],"text":r["text"],"bg_color":r["bg_color"],"username":r["username"],"avatar":r["avatar"],"user_id":r["user_id"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/stories/create")
async def stories_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    image=(data.get("image") or "").strip() or None
    text=(data.get("text") or "").strip() or None
    bg=data.get("bg_color","#000")
    if not image and not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO stories(user_id,image,text,bg_color) VALUES($1,$2,$3,$4)",user["id"],image,text,bg)
    await manager.broadcast({"type":"story_new","user_id":user["id"],"username":user["username"]})
    return {"ok":True}

@app.post("/api/stories/react")
async def stories_react(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=int(data.get("story_id",0)); emoji=data.get("emoji","❤️")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions,user_id FROM stories WHERE id=$1",sid)
        if not row: raise HTTPException(404,"Нет")
        react=json.loads(row["reactions"] or "{}")
        arr=react.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        react[emoji]=arr
        await conn.execute("UPDATE stories SET reactions=$1 WHERE id=$2",json.dumps(react),sid)
    await manager.send_to(row["user_id"],{"type":"story_reaction","emoji":emoji,"from":user["username"]})
    return {"ok":True}

@app.post("/api/stories/reply")
async def stories_reply(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=int(data.get("story_id",0)); text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        st=await conn.fetchrow("SELECT user_id FROM stories WHERE id=$1",sid)
        if not st: raise HTTPException(404,"Нет")
        await conn.execute("INSERT INTO story_replies(story_id,from_user,text) VALUES($1,$2,$3)",sid,user["id"],text)
    await manager.send_to(st["user_id"],{"type":"story_reply","username":user["username"],"text":text})
    return {"ok":True}

# ============ CHEST / LOTTERY / BANK / AUCTION / ROULETTE ============
@app.get("/api/chest/status")
async def chest_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    now=datetime.datetime.now(datetime.timezone.utc)
    last=user.get("chest_at")
    available=not last or (now-last).total_seconds()>=86400
    next_in=0 if available else int(86400-(now-last).total_seconds())
    return {"available":available,"next_in":next_in,"streak":user.get("chest_streak",0)}

@app.post("/api/chest/open")
async def chest_open(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT chest_at,chest_streak FROM users WHERE id=$1",user["id"])
        now=datetime.datetime.now(datetime.timezone.utc)
        last=row["chest_at"]
        if last and (now-last).total_seconds()<86400: raise HTTPException(400,"Рано")
        streak=row["chest_streak"]+1 if last and (now-last).total_seconds()<172800 else 1
        roll=random.random()*100
        if roll<0.1:
            await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '7 days',chest_at=$1,chest_streak=$2 WHERE id=$3",now,streak,user["id"])
            return {"ok":True,"type":"premium","days":7}
        elif roll<3.1:
            await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '2 days',chest_at=$1,chest_streak=$2 WHERE id=$3",now,streak,user["id"])
            return {"ok":True,"type":"premium","days":2}
        elif roll<6.1:
            await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day',chest_at=$1,chest_streak=$2 WHERE id=$3",now,streak,user["id"])
            return {"ok":True,"type":"premium","days":1}
        else:
            amount=random.randint(1,10)+streak
            await conn.execute("UPDATE users SET coins=coins+$1,chest_at=$2,chest_streak=$3 WHERE id=$4",amount,now,streak,user["id"])
            return {"ok":True,"type":"coins","amount":amount,"streak":streak}

@app.get("/api/lottery/status")
async def lottery_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        total=await conn.fetchval("SELECT COALESCE(SUM(tickets),0) FROM lottery")
        players=await conn.fetchval("SELECT COUNT(*) FROM lottery WHERE tickets>0")
        my=await conn.fetchval("SELECT tickets FROM lottery WHERE user_id=$1",user["id"]) or 0
        hist=await conn.fetch("SELECT winner_name,amount,created_at FROM lottery_history ORDER BY id DESC LIMIT 10")
        next_draw=3600-(int(time.time())%3600)
    return {"jackpot":total*100,"tickets":my,"players":players,"next_in":next_draw,"history":[{"winner":r["winner_name"],"amount":r["amount"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in hist]}

@app.post("/api/lottery/buy")
async def lottery_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if (user.get("coins") or 0)<100: raise HTTPException(400,"Нужно 100 🏅")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-100 WHERE id=$1",user["id"])
        await conn.execute("INSERT INTO lottery(user_id,tickets,updated_at) VALUES($1,1,NOW()) ON CONFLICT (user_id) DO UPDATE SET tickets=lottery.tickets+1,updated_at=NOW()",user["id"])
    return {"ok":True}

@app.get("/api/bank/status")
async def bank_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    dep=user.get("bank_deposit",0) or 0
    last=user.get("bank_at")
    interest=0
    if last and dep>0:
        days=(datetime.datetime.now(datetime.timezone.utc)-last).total_seconds()/86400
        interest=int(dep*0.015*days)
    return {"deposit":dep,"interest":interest}

@app.post("/api/bank/deposit")
async def bank_deposit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    amt=int(data.get("amount",0))
    if amt<=0: raise HTTPException(400,"Сумма>0")
    if (user.get("coins") or 0)<amt: raise HTTPException(400,"Не хватает")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1,bank_deposit=bank_deposit+$1,bank_at=NOW() WHERE id=$2",amt,user["id"])
    return {"ok":True}

@app.post("/api/bank/withdraw")
async def bank_withdraw(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT bank_deposit,bank_at FROM users WHERE id=$1",user["id"])
        if not row or not row["bank_deposit"]: raise HTTPException(400,"Пусто")
        days=(datetime.datetime.now(datetime.timezone.utc)-row["bank_at"]).total_seconds()/86400 if row["bank_at"] else 0
        interest=int(row["bank_deposit"]*0.015*days)
        total=row["bank_deposit"]+interest
        await conn.execute("UPDATE users SET coins=coins+$1,bank_deposit=0,bank_at=NULL WHERE id=$2",total,user["id"])
    return {"ok":True,"got":total,"interest":interest}

@app.get("/api/auction/list")
async def auction_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE auction SET status='ended' WHERE ends_at<NOW() AND status='active'")
        cur=await conn.fetchrow("SELECT a.*,u.username AS leader FROM auction a LEFT JOIN users u ON u.id=a.current_bidder WHERE a.status='active' ORDER BY a.id DESC LIMIT 1")
        if cur:
            timer=int((cur["ends_at"]-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
            return {"current":{"id":cur["id"],"name":cur["item_name"],"emoji":cur["item_emoji"],"price":cur["current_price"] or cur["start_price"],"leader":cur["leader"],"timer":max(0,timer)}}
    return {"current":None}

@app.post("/api/auction/bid")
async def auction_bid(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    amt=int(data.get("amount",0))
    p=await get_pool()
    async with p.acquire() as conn:
        cur=await conn.fetchrow("SELECT id,current_price,start_price,current_bidder FROM auction WHERE status='active' ORDER BY id DESC LIMIT 1")
        if not cur: raise HTTPException(404,"Нет лота")
        min_price=max(cur["current_price"] or cur["start_price"],cur["start_price"])+1
        if amt<min_price: raise HTTPException(400,f"Мин {min_price}")
        if (user.get("coins") or 0)<amt: raise HTTPException(400,"Не хватает")
        if cur["current_bidder"]:
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",cur["current_price"],cur["current_bidder"])
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amt,user["id"])
        await conn.execute("UPDATE auction SET current_price=$1,current_bidder=$2 WHERE id=$3",amt,user["id"],cur["id"])
    return {"ok":True}

@app.post("/api/roulette/spin")
async def roulette_spin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bet=int(data.get("bet",0)); color=data.get("color","red")
    if bet<50: raise HTTPException(400,"Мин 50")
    if (user.get("coins") or 0)<bet: raise HTTPException(400,"Не хватает")
    outcomes=["red"]*17+["black"]*17+["green"]*2
    result=random.choice(outcomes)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",bet,user["id"])
        if result==color:
            mult=14 if color=="green" else 2
            got=bet*mult
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",got,user["id"])
            return {"ok":True,"win":True,"result":result,"got":got}
    return {"ok":True,"win":False,"result":result}

# ============ UPGRADE ============
@app.post("/api/gifts/upgrade_wheel")
async def gifts_upgrade_wheel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    from_id=data.get("from_gift"); to_id=data.get("to_gift")
    g=await get_all_gifts()
    if from_id not in g or to_id not in g: raise HTTPException(400,"Нет подарка")
    if g[to_id]["price"]<=g[from_id]["price"]: raise HTTPException(400,"Цель должна быть дороже")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",user["id"],from_id)
        if not row: raise HTTPException(400,"Нет у тебя такого")
        chance=min(75,(g[from_id]["price"]/g[to_id]["price"])*100)
        bonus=get_upgrade_chance_bonus(user["id"])
        chance=max(1,min(75,chance+bonus))
        roll=random.random()*100
        success=roll<=chance
        await conn.execute("DELETE FROM gifts WHERE id=$1",row["id"])
        if success:
            await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],to_id)
        await conn.execute("INSERT INTO upgrade_log(user_id,from_gift,to_gift,success,chance) VALUES($1,$2,$3,$4,$5)",user["id"],from_id,to_id,success,chance)
    if success:
        return {"ok":True,"success":True,"got_name":g[to_id]["name"],"chance":chance}
    return {"ok":True,"success":False,"chance":chance}

# ============ LEVELS / REP / BP ============
@app.get("/api/levels/me")
async def levels_me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"level":user.get("level",1),"xp":user.get("xp",0),"next_xp":(user.get("level",1))*100}

@app.get("/api/levels/leaders")
async def levels_leaders():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT username,level,xp FROM users ORDER BY level DESC, xp DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.post("/api/rep/give")
async def rep_give(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM rep_given WHERE from_user=$1 AND to_user=$2 AND created_at>NOW()-INTERVAL '24 hours'",user["id"],tid)
        if exists: raise HTTPException(400,"Уже давал сегодня")
        await conn.execute("INSERT INTO rep_given(from_user,to_user) VALUES($1,$2)",user["id"],tid)
        await conn.execute("UPDATE users SET reputation=reputation+1 WHERE id=$1",tid)
    await manager.send_to(tid,{"type":"rep_update","from":user["username"]})
    return {"ok":True}

@app.get("/api/bp/current")
async def bp_current(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT * FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: return {"active":False}
        prog=await conn.fetchrow("SELECT xp,level,claimed FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        quests=await conn.fetch("SELECT id,name,description,goal,xp_reward FROM bp_quests WHERE active=TRUE")
        rewards=await conn.fetch("SELECT id,level,reward FROM bp_rewards WHERE active=TRUE ORDER BY level")
    my_xp=prog["xp"] if prog else 0
    my_level=prog["level"] if prog else 1
    claimed=json.loads(prog["claimed"] or "[]") if prog else []
    ends_in_days=None
    if season.get("ends_at"):
        ends_in_days=max(0,int((season["ends_at"]-datetime.datetime.now(datetime.timezone.utc)).total_seconds()//86400))
    return {"active":True,"name":season["name"],"description":season["description"],"emoji":season["emoji"],"my_xp":my_xp,"my_level":my_level,"next_xp":my_level*1000,"ends_in_days":ends_in_days,"quests":[{"id":q["id"],"name":q["name"],"desc":q["description"],"goal":q["goal"],"progress":0,"xp_reward":q["xp_reward"],"done":False} for q in quests],"rewards":[{"id":r["id"],"level":r["level"],"reward":r["reward"],"unlocked":my_level>=r["level"] and str(r["id"]) not in claimed} for r in rewards]}

@app.post("/api/bp/claim")
async def bp_claim(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    level=int(data.get("level",0))
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: raise HTTPException(404,"Нет сезона")
        r=await conn.fetchrow("SELECT id,reward FROM bp_rewards WHERE level=$1 AND active=TRUE LIMIT 1",level)
        if not r: raise HTTPException(404,"Нет награды")
        prog=await conn.fetchrow("SELECT id,level,claimed FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        if prog and prog["level"]<level: raise HTTPException(400,"Уровень мал")
        claimed=json.loads(prog["claimed"] or "[]") if prog else []
        rid=str(r["id"])
        if rid in claimed: raise HTTPException(400,"Уже забрано")
        claimed.append(rid)
        if prog:
            await conn.execute("UPDATE bp_progress SET claimed=$1 WHERE id=$2",json.dumps(claimed),prog["id"])
        else:
            await conn.execute("INSERT INTO bp_progress(user_id,season_id,claimed) VALUES($1,$2,$3)",user["id"],season["id"],json.dumps(claimed))
    return {"ok":True}

# ============ 2.5 NEW: BP ADMIN API ============
@app.get("/api/bp/admin/info")
async def bp_admin_info(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
    if not row: return {"name":"","description":"","emoji":"🏆","ends_at":None,"days_total":30}
    return {"name":row["name"],"description":row["description"],"emoji":row["emoji"],"ends_at":row["ends_at"].isoformat() if row.get("ends_at") else None,"days_total":row.get("days_total") or 30}

@app.post("/api/bp/admin/save")
async def bp_admin_save(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    name=(data.get("name") or "")[:64]
    desc=(data.get("description") or "")[:256]
    emoji=(data.get("emoji") or "🏆")[:4]
    days=int(data.get("days") or 30)
    days=max(1,min(365,days))
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id,started_at FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if row:
            # пересчёт ends_at от started_at (или от now если ещё не стартовал)
            base=row["started_at"] or datetime.datetime.now(datetime.timezone.utc)
            ends=base+datetime.timedelta(days=days)
            await conn.execute("UPDATE bp_season SET name=$1,description=$2,emoji=$3,days_total=$4,ends_at=$5 WHERE id=$6",name,desc,emoji,days,ends,row["id"])
        else:
            ends=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=days)
            await conn.execute("INSERT INTO bp_season(name,description,emoji,days_total,ends_at) VALUES($1,$2,$3,$4,$5)",name,desc,emoji,days,ends)
    return {"ok":True}

@app.post("/api/bp/admin/start")
async def bp_admin_start(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE active=TRUE")
        days=30
        ends=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=days)
        await conn.execute("INSERT INTO bp_season(name,description,emoji,days_total,ends_at,active) VALUES('Новый сезон','','🏆',$1,$2,TRUE)",days,ends)
    await manager.broadcast({"type":"bp_update"})
    return {"ok":True}

@app.post("/api/bp/admin/end")
async def bp_admin_end(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE active=TRUE")
    await manager.broadcast({"type":"bp_update"})
    return {"ok":True}

@app.get("/api/bp/admin/quests")
async def bp_admin_quests(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,description,goal,xp_reward FROM bp_quests WHERE active=TRUE ORDER BY id")
    return [dict(r) for r in rows]

@app.post("/api/bp/admin/quests/add")
async def bp_admin_quests_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    name=(data.get("name") or "")[:128]
    desc=(data.get("description") or "")[:256]
    goal=int(data.get("goal",10))
    xp=int(data.get("xp_reward",100))
    if not name: raise HTTPException(400,"Название нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO bp_quests(name,description,goal,xp_reward) VALUES($1,$2,$3,$4)",name,desc,goal,xp)
    return {"ok":True}

@app.post("/api/bp/admin/quests/delete")
async def bp_admin_quests_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_quests WHERE id=$1",int(data.get("quest_id",0)))
    return {"ok":True}

@app.get("/api/bp/admin/rewards")
async def bp_admin_rewards(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,level,reward FROM bp_rewards WHERE active=TRUE ORDER BY level")
    return [dict(r) for r in rows]

@app.post("/api/bp/admin/rewards/add")
async def bp_admin_rewards_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    level=int(data.get("level",1))
    reward=(data.get("reward") or "")[:128]
    if not reward: raise HTTPException(400,"Награда нужна")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO bp_rewards(level,reward) VALUES($1,$2)",level,reward)
    return {"ok":True}

@app.post("/api/bp/admin/rewards/delete")
async def bp_admin_rewards_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_rewards WHERE id=$1",int(data.get("reward_id",0)))
    return {"ok":True}

@app.post("/api/bp/admin/reset_progress")
async def bp_admin_reset_progress(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_progress")
    await manager.broadcast({"type":"bp_update"})
    return {"ok":True}

# ============ 2.5 NEW: OWNER ANNOUNCE FULL ============
@app.post("/api/owner/announce_full")
async def owner_announce_full(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    username=(data.get("username") or user["username"])[:32]
    avatar=(data.get("avatar") or user.get("avatar") or "")
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    if len(text)>1000: text=text[:1000]
    send_dm=bool(data.get("send_dm"))
    payload={"type":"abuse_announce","username":username,"avatar":avatar,"text":text,"from_id":user["id"],"ts":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    sent=0
    # broadcast всем онлайн
    for uid in list(manager.connections.keys()):
        try:
            await manager.send_to(uid,payload)
            sent+=1
        except: pass
    # DM всем онлайн (опционально)
    if send_dm:
        p=await get_pool()
        for uid in list(manager.connections.keys()):
            if uid==user["id"]: continue
            try:
                async with p.acquire() as conn:
                    await conn.execute("INSERT INTO dms(from_user,to_user,text) VALUES($1,$2,$3)",user["id"],uid,text)
                await manager.send_to(uid,{"type":"dm","from_user":user["id"],"to_user":uid,"username":username,"avatar":avatar,"text":text,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})
            except: pass
    await log_admin(user["id"],"announce_full",None,f"to {sent} users")
    return {"ok":True,"sent":sent}

# ============ EVENTS ============
@app.get("/api/events/active")
async def events_active():
    now=datetime.datetime.now(datetime.timezone.utc)
    for e in active_events[:]:
        if e.get("end_at") and e["end_at"]<=now: e["active"]=False
    cur=[e for e in active_events if e.get("active")]
    if cur:
        e=cur[0]
        return {"active":True,"id":e["id"],"name":e["name"],"description":e.get("description"),"emoji":e.get("emoji","🎉"),"event_type":e.get("event_type"),"multiplier":e.get("multiplier"),"end_at":e["end_at"].isoformat() if e.get("end_at") else None}
    return {"active":False}

# ============ TITLES / REACTIONS / COMMANDS ============
TITLES_DEFAULT=[{"name":"Легенда","emoji":"🏅"},{"name":"Стример","emoji":"🎥"},{"name":"Олдфаг","emoji":"👴"},{"name":"Бета","emoji":"🧪"},{"name":"Админ","emoji":"🛡️"},{"name":"Меценат","emoji":"💰"}]

@app.get("/api/titles/list")
async def titles_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT DISTINCT title FROM users WHERE title IS NOT NULL")
    all_titles=TITLES_DEFAULT[:]
    for r in rows:
        if r["title"] and not any(t["name"]==r["title"] for t in all_titles):
            all_titles.append({"name":r["title"],"emoji":"⭐"})
    return all_titles

@app.post("/api/titles/set")
async def titles_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    title=(data.get("title") or "").strip()[:32]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",title or None,user["id"])
    return {"ok":True}

@app.get("/api/reactions/custom/list")
async def custom_reactions_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,url FROM custom_reactions WHERE user_id=$1 ORDER BY id DESC",user["id"])
    return [dict(r) for r in rows]

@app.post("/api/reactions/custom/add")
async def custom_reactions_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    url=(data.get("url") or "").strip()
    if not url: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        cnt=await conn.fetchval("SELECT COUNT(*) FROM custom_reactions WHERE user_id=$1",user["id"])
        if cnt>=5: raise HTTPException(400,"Макс 5")
        await conn.execute("INSERT INTO custom_reactions(user_id,url) VALUES($1,$2)",user["id"],url)
    return {"ok":True}

@app.get("/api/commands/list")
async def commands_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,description FROM commands ORDER BY name")
    return [dict(r) for r in rows]

# ============ COINS / GIFTS / NFT / CASES ============
@app.get("/api/coins/balance")
async def coins_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"coins":user.get("coins",0),"social_rating":user.get("social_rating",0)}

@app.post("/api/coins/request")
async def coins_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO coin_requests(user_id,coins,price) VALUES($1,$2,$3)",user["id"],int(data.get("coins",0)),int(data.get("price",0)))
    return {"ok":True}

@app.post("/api/coins/transfer")
async def coins_transfer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("to_user",0)); amt=int(data.get("amount",0))
    if amt<=0: raise HTTPException(400,"Сумма >0")
    if user.get("coins",0)<amt: raise HTTPException(400,"Не хватает")
    p=await get_pool()
    async with p.acquire() as conn:
        fr=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
        if not fr: raise HTTPException(400,"Только друзьям")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amt,user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,tid)
    await manager.send_to(tid,{"type":"coins_received","amount":amt,"from_name":user["username"]})
    return {"ok":True,"to":t["username"]}

@app.get("/api/coins/leaders")
async def coins_leaders():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT username,coins FROM users ORDER BY coins DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.get("/api/gifts/all")
async def gifts_all():
    g=await get_all_gifts()
    return [{"gift_id":k,"name":v["name"],"emoji":v.get("emoji"),"image":v.get("image"),"price":v["price"]} for k,v in g.items()]

@app.get("/api/gifts/list/{user_id}")
async def gifts_list(user_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT gift FROM gifts WHERE to_user=$1 ORDER BY id DESC",user_id)
    return {"gifts":[dict(r) for r in rows]}

@app.post("/api/gifts/send")
async def gift_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    gift=g[gift_id]; price=gift["price"]
    if user.get("coins",0)<price: raise HTTPException(400,"Не хватает")
    to_id=int(data.get("to_user",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",price,user["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],to_id,gift_id)
        await conn.execute("UPDATE users SET social_rating=social_rating+$1 WHERE id=$2",price,user["id"])
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1",user["id"])
        newrating=await conn.fetchval("SELECT social_rating FROM users WHERE id=$1",user["id"])
    if cnt==1: await grant_achievement(user["id"],"first_gift")
    if newrating>=100: await grant_achievement(user["id"],"rating_100")
    if newrating>=10000: await grant_achievement(user["id"],"rating_10000")
    await manager.send_to(to_id,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"gift_image":gift.get("image"),"from_name":user["username"]})
    await grant_quest_progress(user["id"],"give_gift",1)
    return {"ok":True}

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

@app.get("/api/stickers/list")
async def stickers_list():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT gift_id,name,emoji,image FROM custom_gifts WHERE is_sticker=TRUE ORDER BY created_at DESC")
        return [{"id":r["gift_id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"]} for r in rows]
    except: return []

@app.get("/api/nft/list")
async def nft_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM nft_series WHERE sold<total ORDER BY id DESC")
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"image":r.get("image"),"price":r["price"],"total":r["total"],"sold":r["sold"],"rarity":r["rarity"],"number":(r["sold"] or 0)+1} for r in rows]

@app.get("/api/nft/my")
async def nft_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT ni.id,ni.number,ns.name,ns.emoji,ns.image,ns.price,ns.total,ns.rarity FROM nft_items ni JOIN nft_series ns ON ns.id=ni.series_id WHERE ni.owner_id=$1 ORDER BY ni.id DESC",user["id"])
    return [dict(r) for r in rows]

@app.post("/api/nft/buy")
async def nft_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    nid=int(data.get("nft_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",nid)
        if not s: raise HTTPException(404,"Нет")
        if s["sold"]>=s["total"]: raise HTTPException(400,"Распродано")
        if user.get("coins",0)<s["price"]: raise HTTPException(400,"Не хватает")
        num=s["sold"]+1
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",s["price"],user["id"])
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",nid,num,user["id"])
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",nid)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM nft_items WHERE owner_id=$1",user["id"])
    if cnt==1: await grant_achievement(user["id"],"first_nft")
    return {"ok":True,"number":num}

@app.post("/api/nft/sell")
async def nft_sell(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    item_id=int(data.get("item_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        item=await conn.fetchrow("SELECT ni.id,ni.owner_id,ns.price FROM nft_items ni JOIN nft_series ns ON ns.id=ni.series_id WHERE ni.id=$1",item_id)
        if not item: raise HTTPException(404,"Не найден")
        if item["owner_id"]!=user["id"]: raise HTTPException(403,"Не твой")
        sp=item["price"]//2
        await conn.execute("DELETE FROM nft_items WHERE id=$1",item_id)
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",sp,user["id"])
    return {"ok":True,"got":sp}

@app.get("/api/nft_market/list")
async def nft_market_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT nm.id,nm.price,nm.seller_id,ni.id AS item_id,ni.number,ns.name,ns.emoji,ns.image,ns.rarity,u.username AS seller_name FROM nft_market nm JOIN nft_items ni ON ni.id=nm.item_id JOIN nft_series ns ON ns.id=ni.series_id JOIN users u ON u.id=nm.seller_id WHERE nm.status='active' ORDER BY nm.id DESC")
    return [{"id":r["id"],"item_id":r["item_id"],"price":r["price"],"number":r["number"],"name":r["name"],"emoji":r["emoji"],"image":r["image"],"rarity":r["rarity"],"seller_id":r["seller_id"],"seller_name":r["seller_name"]} for r in rows]

@app.post("/api/nft_market/sell")
async def nft_market_sell(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    item_id=int(data.get("item_id",0)); price=int(data.get("price",0))
    if price<=0: raise HTTPException(400,"Цена >0")
    p=await get_pool()
    async with p.acquire() as conn:
        item=await conn.fetchrow("SELECT owner_id FROM nft_items WHERE id=$1",item_id)
        if not item: raise HTTPException(404,"Не найден")
        if item["owner_id"]!=user["id"]: raise HTTPException(403,"Не твой")
        if await conn.fetchrow("SELECT id FROM nft_market WHERE item_id=$1 AND status='active'",item_id): raise HTTPException(400,"Уже на рынке")
        await conn.execute("INSERT INTO nft_market(item_id,seller_id,price) VALUES($1,$2,$3)",item_id,user["id"],price)
    return {"ok":True}

@app.post("/api/nft_market/buy")
async def nft_market_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("market_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT * FROM nft_market WHERE id=$1 AND status='active'",mid)
        if not m: raise HTTPException(404,"Нет лота")
        if m["seller_id"]==user["id"]: raise HTTPException(400,"Свой лот")
        if user.get("coins",0)<m["price"]: raise HTTPException(400,"Не хватает")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",m["price"],user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",m["price"],m["seller_id"])
        await conn.execute("UPDATE nft_items SET owner_id=$1 WHERE id=$2",user["id"],m["item_id"])
        await conn.execute("UPDATE nft_market SET status='sold' WHERE id=$1",mid)
    await manager.send_to(m["seller_id"],{"type":"nft_sold","price":m["price"]})
    return {"ok":True}

@app.get("/api/cases/list")
async def cases_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,emoji,image,price FROM cases WHERE is_active=TRUE ORDER BY id DESC")
    return [dict(r) for r in rows]

@app.get("/api/cases/{case_id}/prizes")
async def case_prizes(case_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT kind,item_id,item_name,item_emoji,item_image,chance,coins_min,coins_max FROM case_prizes WHERE case_id=$1 ORDER BY chance DESC",case_id)
    return [dict(r) for r in rows]

@app.post("/api/cases/open")
async def cases_open(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    cid=int(data.get("case_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT * FROM cases WHERE id=$1 AND is_active=TRUE",cid)
        if not c: raise HTTPException(404,"Нет кейса")
        if user.get("coins",0)<c["price"]: raise HTTPException(400,"Не хватает")
        prizes=await conn.fetch("SELECT * FROM case_prizes WHERE case_id=$1",cid)
        if not prizes: raise HTTPException(400,"Нет призов")
        total=sum(p["chance"] for p in prizes)
        roll=random.randint(1,total)
        acc=0; chosen=None
        for p in prizes:
            acc+=p["chance"]
            if roll<=acc: chosen=p; break
        if not chosen: chosen=prizes[-1]
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",c["price"],user["id"])
        if chosen["kind"]=="coins":
            amt=random.randint(chosen["coins_min"] or 1,chosen["coins_max"] or chosen["coins_min"] or 1)
            amt=apply_event_multiplier(amt,"coins_x")
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,user["id"])
            prize_text=f"🏅 {amt} бекоинов"
        elif chosen["kind"]=="gift":
            gid=chosen["item_id"]
            if gid: await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],gid)
            prize_text=f"🎀 {chosen['item_name'] or gid}"
        elif chosen["kind"]=="nft":
            try:
                nid=int(chosen["item_id"])
                s=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",nid)
                if s and s["sold"]<s["total"]:
                    num=s["sold"]+1
                    await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",nid,num,user["id"])
                    await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",nid)
                    prize_text=f"🎨 {s['name']} #{num}"
                else: prize_text="😢 пусто"
            except: prize_text="😢 пусто"
        else: prize_text=f"❓ {chosen['item_name'] or '???'}"
        await conn.execute("INSERT INTO case_opens(user_id,case_id,prize_text) VALUES($1,$2,$3)",user["id"],cid,prize_text)
    await grant_quest_progress(user["id"],"open_1_case",1)
    return {"ok":True,"prize":prize_text}

# ============ ADMIN ============
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
        rows=await conn.fetch("SELECT id,username,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,is_banned,coins,social_rating,title FROM users ORDER BY id")
    return [dict(r) for r in rows]

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
    await log_admin(user["id"],action,tid)
    if action=="ban":
        await manager.send_to(tid,{"type":"banned","reason":data.get("reason","")})
        await manager.kick(tid)
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

@app.get("/api/admin/coin_requests")
async def admin_coin_requests(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT cr.id,cr.coins,cr.price,u.username FROM coin_requests cr JOIN users u ON u.id=cr.user_id WHERE cr.status='pending' ORDER BY cr.id DESC")
    return [dict(r) for r in rows]

@app.post("/api/admin/coin_resolve")
async def admin_coin_resolve(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        req=await conn.fetchrow("SELECT * FROM coin_requests WHERE id=$1",int(data.get("request_id",0)))
        if not req: raise HTTPException(404,"Не найдено")
        if data.get("action")=="approve":
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",req["coins"],req["user_id"])
            await conn.execute("UPDATE coin_requests SET status='approved',resolved_at=NOW() WHERE id=$1",req["id"])
            await manager.send_to(req["user_id"],{"type":"coins_approved","amount":req["coins"]})
        else:
            await conn.execute("UPDATE coin_requests SET status='rejected',resolved_at=NOW() WHERE id=$1",req["id"])
            await manager.send_to(req["user_id"],{"type":"coins_rejected"})
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
            await manager.kick(r["target_user"])
        else:
            await conn.execute("UPDATE ban_requests SET status='rejected',resolved_by=$1,resolved_at=NOW() WHERE id=$2",user["id"],rid)
            try: await manager.send_to(r["from_admin"],{"type":"ban_request_resolved","status":"rejected"})
            except: pass
    return {"ok":True}

# ============ MOD ============
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

# ============ OWNER ============
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

@app.post("/api/owner/troll")
async def owner_troll(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    await manager.broadcast({"type":"event","event":data.get("troll")})
    return {"ok":True}

@app.post("/api/owner/troll_user")
async def owner_troll_user(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    tid=int(data.get("user_id",0)); kind=data.get("kind"); dur=int(data.get("duration",10))
    await manager.send_to(tid,{"type":"troll_user","kind":kind,"duration":dur})
    return {"ok":True}

@app.post("/api/owner/storm")
async def owner_storm(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    dur=int(data.get("duration",30))
    await manager.broadcast({"type":"storm","duration":dur})
    return {"ok":True}

@app.post("/api/owner/mass_rename")
async def owner_mass_rename(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    prefix=(data.get("prefix") or "")[:16]; suffix=(data.get("suffix") or "")[:16]
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username FROM users WHERE username!=$1",ADMIN_USERNAME)
        for r in rows:
            new=(prefix+r["username"]+suffix)[:32]
            try: await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,r["id"])
            except: pass
    await manager.broadcast({"type":"mass_renamed"})
    return {"ok":True,"count":len(rows)}

@app.post("/api/owner/force_logout")
async def owner_force_logout(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    tid=int(data.get("user_id",0))
    await manager.send_to(tid,{"type":"force_logout"})
    return {"ok":True}

@app.post("/api/owner/mass_color")
async def owner_mass_color(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    color=data.get("color")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET nickname_color=$1 WHERE username!=$2",color,ADMIN_USERNAME)
    return {"ok":True}

@app.get("/api/owner/spy/{user_id}")
async def owner_spy(user_id:int,token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT m.text,m.created_at,c.name AS channel_name FROM messages m LEFT JOIN channels c ON c.id=m.channel_id WHERE m.user_id=$1 ORDER BY m.id DESC LIMIT 100",user_id)
        dms=await conn.fetch("SELECT d.text,d.created_at,u.username AS to_name FROM dms d LEFT JOIN users u ON u.id=d.to_user WHERE d.from_user=$1 ORDER BY d.id DESC LIMIT 100",user_id)
    return {"messages":[{"text":r["text"],"channel":r["channel_name"],"at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows],"dms":[{"text":r["text"],"to":r["to_name"],"at":r["created_at"].isoformat() if r["created_at"] else None} for r in dms]}

@app.post("/api/owner/auto_abuse")
async def owner_auto_abuse(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    enabled=bool(data.get("enabled",False)); kind=data.get("kind","gift"); every=int(data.get("every_minutes",60))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM auto_abuse")
        if enabled:
            next_run=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=every)
            await conn.execute("INSERT INTO auto_abuse(enabled,kind,every_minutes,next_run,created_by) VALUES(TRUE,$1,$2,$3,$4)",kind,every,next_run,user["id"])
    return {"ok":True,"enabled":enabled}

@app.post("/api/owner/suddness")
async def owner_suddness(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    evt=random.choice(["confetti","balloons","cat_mode"])
    await manager.broadcast({"type":"event","event":evt})
    return {"ok":True,"event":evt}

@app.post("/api/owner/give_coins")
async def owner_give_coins(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,coins FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,t["id"])
    return {"ok":True}

@app.post("/api/owner/take_coins")
async def owner_take_coins(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET coins=GREATEST(coins-$1,0) WHERE id=$2",int(data.get("amount",100)),t["id"])
    return {"ok":True}

@app.post("/api/owner/give_all")
async def owner_give_all(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins+$1",int(data.get("amount",10)))
    return {"ok":True}

@app.post("/api/owner/toggle_streamer")
async def owner_toggle_streamer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,is_streamer FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET is_streamer=NOT is_streamer WHERE id=$1",t["id"])
        new_status=not t["is_streamer"]
    await manager.broadcast({"type":"streamer_update","user_id":t["id"],"is_streamer":new_status})
    return {"ok":True,"is_streamer":new_status}

@app.post("/api/owner/announce")
async def owner_announce(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    await manager.broadcast({"type":"abuse_announce","username":user["username"],"avatar":user.get("avatar") or "","text":data.get("text",""),"from_id":user["id"],"ts":datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return {"ok":True}

@app.post("/api/owner/change_nick")
async def owner_change_nick(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET username=$1 WHERE username=$2",data.get("new_nick"),data.get("username"))
    return {"ok":True}

@app.post("/api/owner/reset_pass")
async def owner_reset_pass(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    np=secrets.token_hex(4)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET password_hash=$1 WHERE username=$2",hash_password(np),data.get("username"))
    return {"ok":True,"new_password":np}

@app.post("/api/owner/mute")
async def owner_mute(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        m=int(data.get("minutes",60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",m*60,t["id"])
    return {"ok":True}

@app.post("/api/owner/delete_all_msgs")
async def owner_del_msgs(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("DELETE FROM messages WHERE user_id=$1",t["id"])
    return {"ok":True}

@app.post("/api/owner/legend")
async def owner_legend(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_legend=TRUE WHERE username=$1",data.get("username"))
    return {"ok":True}

@app.post("/api/owner/give_premium")
async def owner_give_premium(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET premium_tier=$1,premium_expires=NOW()+INTERVAL '30 days' WHERE username=$2",data.get("tier","premium"),data.get("username"))
    return {"ok":True}

@app.post("/api/owner/toggle_beta")
async def owner_toggle_beta(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_beta_tester=NOT is_beta_tester WHERE username=$1",data.get("username"))
    return {"ok":True}

@app.post("/api/owner/grant_admin")
async def owner_grant_admin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",data.get("username"))
    return {"ok":True}

@app.post("/api/owner/revoke_admin")
async def owner_revoke_admin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=FALSE WHERE username=$1",data.get("username"))
    return {"ok":True}

@app.post("/api/owner/read_chat")
async def owner_read_chat(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    username=data.get("username")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",username)
        if not t: raise HTTPException(404,"Не найден")
        rows=await conn.fetch("SELECT m.text,u.username AS from_user FROM messages m JOIN users u ON u.id=m.user_id WHERE m.user_id=$1 ORDER BY m.id DESC LIMIT 50",t["id"])
    return {"messages":[{"from":r["from_user"],"text":r["text"]} for r in rows]}

@app.post("/api/owner/write_as")
async def owner_write_as(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username,avatar FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        ch=await conn.fetchrow("SELECT c.id FROM channels c JOIN server_members sm ON sm.server_id=c.server_id WHERE sm.user_id=$1 ORDER BY c.id LIMIT 1",t["id"])
        if ch:
            msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text) VALUES($1,$2,$3) RETURNING *",ch["id"],t["id"],data.get("text",""))
            await manager.broadcast({"type":"message","id":msg["id"],"channel_id":ch["id"],"user_id":t["id"],"username":t["username"],"avatar":t["avatar"],"text":data.get("text",""),"created_at":msg["created_at"].isoformat()})
    return {"ok":True}

@app.post("/api/owner/self_destruct")
async def owner_self_destruct(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        ch=int(data.get("channel_id",0))
        await conn.execute("DELETE FROM messages WHERE channel_id=$1",ch)
    await manager.broadcast({"type":"event","event":"self_destruct","channel_id":ch})
    return {"ok":True}

@app.post("/api/owner/clean_db")
async def owner_clean_db(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE created_at<NOW()-INTERVAL '30 days'")
        await conn.execute("DELETE FROM dms WHERE created_at<NOW()-INTERVAL '30 days'")
    return {"ok":True}

@app.get("/api/owner/backup")
async def owner_backup(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    data={"users":[],"servers":[],"channels":[],"messages":[],"dms":[],"gifts":[],"nft_items":[]}
    async with p.acquire() as conn:
        data["users"]=[dict(r) for r in await conn.fetch("SELECT id,username,coins,social_rating,level,xp,reputation,title,created_at FROM users")]
        data["servers"]=[dict(r) for r in await conn.fetch("SELECT id,name,owner_id,invite_code FROM servers")]
        data["channels"]=[dict(r) for r in await conn.fetch("SELECT id,server_id,name,mode FROM channels")]
        data["messages"]=[dict(r) for r in await conn.fetch("SELECT id,channel_id,user_id,text,created_at FROM messages LIMIT 5000")]
        data["dms"]=[dict(r) for r in await conn.fetch("SELECT id,from_user,to_user,text,created_at FROM dms LIMIT 5000")]
        data["gifts"]=[dict(r) for r in await conn.fetch("SELECT id,from_user,to_user,gift FROM gifts")]
        data["nft_items"]=[dict(r) for r in await conn.fetch("SELECT id,series_id,number,owner_id FROM nft_items")]
    def convert(o):
        if isinstance(o,datetime.datetime): return o.isoformat()
        return str(o)
    return JSONResponse(data,default=convert)

@app.get("/api/owner/gifts_full")
async def owner_gifts_full(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    result=[]
    for gid,g in DEFAULT_GIFTS.items():
        result.append({"db_id":None,"slug":gid,"name":g["name"],"emoji":g["emoji"],"image":g.get("image"),"price":g["price"],"is_default":True})
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,gift_id,name,emoji,image,price FROM custom_gifts WHERE is_sticker=FALSE OR is_sticker IS NULL ORDER BY id DESC")
        for r in rows:
            result.append({"db_id":r["id"],"slug":r["gift_id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"],"is_default":False})
    except: pass
    return result

@app.get("/api/owner/stickers_full")
async def owner_stickers_full(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,gift_id,name,emoji,image FROM custom_gifts WHERE is_sticker=TRUE ORDER BY id DESC")
        return [{"db_id":r["id"],"slug":r["gift_id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"]} for r in rows]
    except: return []

@app.get("/api/owner/nfts_full")
async def owner_nfts_full(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,name,emoji,image,price,total,sold,rarity FROM nft_series ORDER BY id DESC")
        return [{"db_id":r["id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"],"total":r["total"],"sold":r["sold"],"rarity":r["rarity"]} for r in rows]
    except: return []

@app.post("/api/owner/create_nft")
async def owner_create_nft(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("INSERT INTO nft_series(name,emoji,image,total,price,rarity,created_by) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",data.get("name"),data.get("emoji","🎨"),data.get("image"),int(data.get("total",1)),int(data.get("price",0)),data.get("rarity","common"),user["id"])
    return {"ok":True,"id":row["id"]}

@app.post("/api/owner/delete_nft")
async def owner_delete_nft(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM nft_series WHERE id=$1",int(data.get("nft_id",0)))
    return {"ok":True}

@app.post("/api/owner/create_gift")
async def owner_create_gift(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    gid=(data.get("gift_id") or "").strip().lower()
    if not gid or len(gid)>32: raise HTTPException(400,"ID 1-32")
    name=(data.get("name") or "").strip()
    if not name: raise HTTPException(400,"Название")
    price=int(data.get("price",0))
    if price<=0: raise HTTPException(400,"Цена>0")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT gift_id FROM custom_gifts WHERE gift_id=$1",gid): raise HTTPException(400,"ID занят")
        if gid in DEFAULT_GIFTS: raise HTTPException(400,"ID занят")
        await conn.execute("INSERT INTO custom_gifts(gift_id,name,emoji,image,price,is_sticker) VALUES($1,$2,$3,$4,$5,FALSE)",gid,name,data.get("emoji","🎁"),data.get("image"),price)
    return {"ok":True}

@app.post("/api/owner/delete_gift")
async def owner_delete_gift(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_gifts WHERE gift_id=$1 AND (is_sticker=FALSE OR is_sticker IS NULL)",data.get("gift_id"))
    return {"ok":True}

@app.post("/api/owner/create_sticker")
async def owner_create_sticker(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    sid=(data.get("sticker_id") or "").strip().lower()
    if not sid or len(sid)>32: raise HTTPException(400,"ID 1-32")
    name=(data.get("name") or "").strip()
    if not name: raise HTTPException(400,"Название")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT gift_id FROM custom_gifts WHERE gift_id=$1",sid): raise HTTPException(400,"ID занят")
        await conn.execute("INSERT INTO custom_gifts(gift_id,name,emoji,image,price,is_sticker) VALUES($1,$2,$3,$4,0,TRUE)",sid,name,data.get("emoji","🎨"),data.get("image"))
    await manager.broadcast({"type":"sticker_added","id":sid})
    return {"ok":True}

@app.post("/api/owner/delete_sticker")
async def owner_delete_sticker(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_gifts WHERE gift_id=$1 AND is_sticker=TRUE",data.get("sticker_id"))
    return {"ok":True}

@app.get("/api/owner/cases_full")
async def owner_cases_full(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,name,emoji,image,price,is_active FROM cases ORDER BY id DESC")
        result=[]
        for r in rows:
            prizes=await conn.fetch("SELECT kind,item_id,item_name,item_emoji,item_image,chance,coins_min,coins_max FROM case_prizes WHERE case_id=$1",r["id"])
            result.append({"db_id":r["id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"],"is_active":r["is_active"],"prizes":[dict(p) for p in prizes]})
        return result
    except: return []

@app.post("/api/owner/cases/create")
async def owner_cases_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название")
    price=int(data.get("price",0))
    if price<=0: raise HTTPException(400,"Цена >0")
    prizes=data.get("prizes") or []
    if not prizes: raise HTTPException(400,"Хотя бы 1 приз")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("INSERT INTO cases(name,emoji,image,price,created_by) VALUES($1,$2,$3,$4,$5) RETURNING id",name,data.get("emoji","🎁"),data.get("image"),price,user["id"])
        for pr in prizes:
            await conn.execute("INSERT INTO case_prizes(case_id,kind,item_id,item_name,item_emoji,item_image,chance,coins_min,coins_max) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)",c["id"],pr.get("kind","coins"),str(pr.get("item_id") or ""),pr.get("item_name",""),pr.get("item_emoji",""),pr.get("item_image"),int(pr.get("chance",0)),int(pr.get("coins_min",0)),int(pr.get("coins_max",0)))
    await manager.broadcast({"type":"case_added","id":c["id"],"name":name})
    return {"ok":True,"id":c["id"]}

@app.post("/api/owner/cases/delete")
async def owner_cases_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM cases WHERE id=$1",int(data.get("case_id",0)))
    return {"ok":True}

@app.post("/api/owner/cases/toggle")
async def owner_cases_toggle(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE cases SET is_active=NOT is_active WHERE id=$1",int(data.get("case_id",0)))
    return {"ok":True}

@app.get("/api/themes/list")
async def themes_list():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,name,emoji,vars,bg_image,border_radius,blur FROM custom_themes ORDER BY id DESC")
        return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"vars":json.loads(r["vars"] or "{}"),"bg_image":r["bg_image"],"border_radius":r["border_radius"],"blur":r["blur"]} for r in rows]
    except: return []

@app.post("/api/owner/theme/create")
async def owner_theme_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO custom_themes(name,emoji,vars,bg_image,border_radius,blur,created_by) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,data.get("emoji","🎨"),json.dumps(data.get("vars") or {}),data.get("bg_image"),data.get("border_radius","12px"),data.get("blur","blur(30px)"),user["id"])
    await manager.broadcast({"type":"theme_added","id":r["id"],"name":name})
    return {"ok":True,"id":r["id"]}

@app.get("/api/abuse/access")
async def abuse_access(token:str):
    user=await get_current_user(token)
    acc=await has_abuse_access(user)
    if not acc: return {"access":False}
    return {"access":True,"owner":acc.get("owner",False),"can_gift":acc.get("can_gift",False),"can_nft":acc.get("can_nft",False),"can_coins":acc.get("can_coins",False),"can_online":acc.get("can_online",False),"can_timer":acc.get("can_timer",False),"can_write":acc.get("can_write",True)}

@app.get("/api/abuse/online")
async def abuse_online(token:str):
    user=await get_current_user(token)
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_online"): raise HTTPException(403,"Нет доступа")
    p=await get_pool()
    async with p.acquire() as conn:
        if not online_users: return {"users":[]}
        rows=await conn.fetch("SELECT id,username,avatar FROM users WHERE id=ANY($1::int[]) ORDER BY username",list(online_users))
    return {"users":[dict(r) for r in rows]}

@app.post("/api/abuse/random_gift")
async def abuse_random_gift(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_gift"): raise HTTPException(403,"Нет доступа")
    if not online_users: raise HTTPException(400,"Никого онлайн")
    g=await get_all_gifts()
    if not g: raise HTTPException(400,"Нет подарков")
    tid=random.choice(list(online_users)); gid=random.choice(list(g.keys()))
    gift=g[gid]
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT username,avatar FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],tid,gid)
    await manager.send_to(tid,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"gift_image":gift.get("image"),"from_name":"🎁 ADMIN ABUSE"})
    return {"ok":True,"target":t["username"],"gift":gift["name"]}

@app.post("/api/abuse/random_nft")
async def abuse_random_nft(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_nft"): raise HTTPException(403,"Нет доступа")
    if not online_users: raise HTTPException(400,"Никого онлайн")
    p=await get_pool()
    async with p.acquire() as conn:
        sr=await conn.fetch("SELECT * FROM nft_series WHERE sold<total")
        if not sr: raise HTTPException(400,"Нет NFT")
        tid=random.choice(list(online_users))
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        s=random.choice(sr); num=(s["sold"] or 0)+1
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",s["id"],num,tid)
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",s["id"])
    return {"ok":True,"target":t["username"],"nft":s["name"],"number":num}

@app.post("/api/abuse/random_coins")
async def abuse_random_coins(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_coins"): raise HTTPException(403,"Нет доступа")
    if not online_users: raise HTTPException(400,"Никого онлайн")
    tid=random.choice(list(online_users)); amt=random.randint(100,10000)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,tid)
    return {"ok":True,"target":t["username"],"amount":amt}

@app.post("/api/abuse/schedule")
async def abuse_schedule(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    delay=int(data.get("delay",60)); kind=data.get("kind","gift")
    if delay<5 or delay>86400: raise HTTPException(400,"5-86400 сек")
    await manager.broadcast({"type":"abuse_timer_start","delay":delay,"kind":kind})
    asyncio.create_task(run_abuse_timer(delay,kind))
    return {"ok":True,"delay":delay,"kind":kind}

@app.post("/api/abuse/schedule_cancel")
async def abuse_schedule_cancel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    global abuse_timer_task
    if abuse_timer_task and not abuse_timer_task.done(): abuse_timer_task.cancel()
    await manager.broadcast({"type":"abuse_timer_cancel"})
    return {"ok":True}

# ============ 2.5 FIX: корректный таск ============
async def run_abuse_timer(delay,kind):
    try:
        await asyncio.sleep(delay)
        await manager.broadcast({"type":"abuse_timer_cancel"})
        if kind=="gift":
            g=await get_all_gifts()
            if g and online_users:
                tid=random.choice(list(online_users)); gid=random.choice(list(g.keys()))
                gift=g[gid]
                p=await get_pool()
                async with p.acquire() as conn:
                    t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
                    if t:
                        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",1,tid,gid)
                        await manager.send_to(tid,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"from_name":"🎁 ADMIN ABUSE"})
    except asyncio.CancelledError: pass
    except Exception as e: print(f"Timer: {e}")

@app.post("/api/abuse/coop_start")
async def abuse_coop_start(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    target_name=(data.get("username") or "").strip()
    minutes=int(data.get("minutes",60))
    cg=bool(data.get("can_gift",True)); cn=bool(data.get("can_nft",True)); cc=bool(data.get("can_coins",True)); co=bool(data.get("can_online",True)); ct=bool(data.get("can_timer",True)); cw=bool(data.get("can_write",True))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",target_name)
        if not t: raise HTTPException(404,"Не найден")
        expires=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=minutes)
        await conn.execute("""INSERT INTO abuse_grants(user_id,granted_by,can_gift,can_nft,can_coins,can_online,can_timer,can_write,expires_at) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (user_id) DO UPDATE SET can_gift=$3,can_nft=$4,can_coins=$5,can_online=$6,can_timer=$7,can_write=$8,expires_at=$9""",t["id"],user["id"],cg,cn,cc,co,ct,cw,expires)
    await manager.send_to(t["id"],{"type":"coop_started","minutes":minutes,"username":user["username"]})
    return {"ok":True,"target":t["username"],"minutes":minutes}

@app.get("/api/abuse/coop_grants")
async def abuse_coop_grants(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.user_id,g.can_gift,g.can_nft,g.can_coins,g.can_online,g.can_timer,g.can_write,g.expires_at,u.username FROM abuse_grants g JOIN users u ON u.id=g.user_id WHERE g.expires_at>NOW() ORDER BY g.expires_at DESC")
    return [{"user_id":r["user_id"],"username":r["username"],"can_gift":r["can_gift"],"can_nft":r["can_nft"],"can_coins":r["can_coins"],"can_online":r["can_online"],"can_timer":r["can_timer"],"can_write":r["can_write"],"expires_at":r["expires_at"].isoformat()} for r in rows]

@app.post("/api/abuse/coop_revoke")
async def abuse_coop_revoke(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM abuse_grants WHERE user_id=$1",int(data.get("user_id",0)))
    return {"ok":True}

# ============ EVENTS OWNER ============
@app.post("/api/owner/events/create")
async def owner_events_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    name=data.get("name","");desc=data.get("description","");emoji=data.get("emoji","🎉")
    etype=data.get("event_type","coins_x");mult=int(data.get("multiplier",1));dur=int(data.get("duration_minutes",10))
    end_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=dur)
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO events(name,description,emoji,event_type,multiplier,created_by,end_at) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,desc,emoji,etype,mult,user["id"],end_at)
    active_events.append({"id":r["id"],"name":name,"description":desc,"emoji":emoji,"event_type":etype,"multiplier":mult,"end_at":end_at,"active":True})
    await manager.broadcast({"type":"event_active","id":r["id"],"name":name,"description":desc,"emoji":emoji,"event_type":etype,"multiplier":mult,"end_at":end_at.isoformat()})
    return {"ok":True,"id":r["id"]}

@app.get("/api/owner/events/list")
async def owner_events_list(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,event_type,multiplier,end_at FROM events WHERE active=TRUE AND end_at>NOW() ORDER BY id DESC")
    return [{"id":r["id"],"name":r["name"],"event_type":r["event_type"],"multiplier":r["multiplier"],"end_at":r["end_at"].isoformat() if r["end_at"] else None} for r in rows]

@app.post("/api/owner/events/stop")
async def owner_events_stop(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    eid=int(data.get("event_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE events SET active=FALSE WHERE id=$1",eid)
    for e in active_events:
        if e["id"]==eid: e["active"]=False
    await manager.broadcast({"type":"event_end","id":eid})
    return {"ok":True}

@app.post("/api/owner/upgrade_chance")
async def owner_upgrade_chance(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    un=data.get("username","");bonus=int(data.get("bonus",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",un)
        if not t: raise HTTPException(404,"Не найден")
        upgrade_chance_bonus[t["id"]]=bonus
    return {"ok":True}

@app.post("/api/owner/commands/create")
async def owner_commands_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    name=(data.get("name") or "").strip().lower()
    if not name: raise HTTPException(400,"Пусто")
    desc=data.get("description","");resp=data.get("response","")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM commands WHERE name=$1",name): raise HTTPException(400,"Занято")
        await conn.execute("INSERT INTO commands(name,description,response,created_by) VALUES($1,$2,$3,$4)",name,desc,resp,user["id"])
    custom_commands[name]=resp
    return {"ok":True}

@app.post("/api/owner/commands/delete")
async def owner_commands_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM commands WHERE id=$1",int(data.get("command_id",0)))
    return {"ok":True}

@app.get("/api/owner/chat")
async def owner_chat_get(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT om.id,om.text,om.created_at,u.username FROM owner_messages om LEFT JOIN users u ON u.id=om.from_user ORDER BY om.id DESC LIMIT 100")
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in reversed(rows)]

@app.post("/api/owner/chat/send")
async def owner_chat_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO owner_messages(from_user,text) VALUES($1,$2)",user["id"],text)
    return {"ok":True}

# ============ FRAMES / PREMIUM / QUESTS / DAILY ============
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
        method=data.get("method","coins")
        if method=="coins" and f["price_coins"]:
            if (user.get("coins") or 0)<f["price_coins"]: raise HTTPException(400,"Не хватает 🏅")
            await conn.execute("UPDATE users SET coins=coins-$1,frame_owned=$2 WHERE id=$3",f["price_coins"],json.dumps(owned+[fid]),user["id"])
        elif method=="kp" and f["price_kp"]:
            if (user.get("quest_points") or 0)<f["price_kp"]: raise HTTPException(400,"Не хватает КП")
            await conn.execute("UPDATE users SET quest_points=quest_points-$1,frame_owned=$2 WHERE id=$3",f["price_kp"],json.dumps(owned+[fid]),user["id"])
        else: raise HTTPException(400,"Способ оплаты не подходит")
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

@app.get("/api/premium/status")
async def premium_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"is_premium":is_premium(user),"tier":user.get("premium_tier"),"expires":user["premium_expires"].isoformat() if user.get("premium_expires") else None}

@app.post("/api/premium/buy")
async def premium_buy(data:dict):
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

@app.get("/api/quests/list")
async def quests_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT quest_day,quest_progress,quest_claimed,quest_points FROM users WHERE id=$1",user["id"])
    today=get_today_key()
    prog={};claimed=[]
    if row["quest_day"]==today:
        prog=json.loads(row["quest_progress"] or "{}")
        claimed=json.loads(row["quest_claimed"] or "[]")
    result=[]
    for q in QUEST_TEMPLATES:
        result.append({"key":q["key"],"name":q["name"],"desc":q["desc"],"emoji":q["emoji"],"goal":q["goal"],"reward_kp":q["reward_kp"],"progress":prog.get(q["key"],0),"claimed":q["key"] in claimed})
    return {"quests":result,"quest_points":row["quest_points"] or 0}

@app.post("/api/quests/exchange")
async def quests_exchange(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan")
    if plan not in QUEST_EXCHANGE: raise HTTPException(400,"Нет такого плана")
    info=QUEST_EXCHANGE[plan]
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT quest_points,premium_expires FROM users WHERE id=$1",user["id"])
        if (row["quest_points"] or 0)<info["cost"]: raise HTTPException(400,f"Нужно {info['cost']} КП")
        now=datetime.datetime.now(datetime.timezone.utc)
        base=row["premium_expires"] if row["premium_expires"] and row["premium_expires"]>now else now
        new_exp=base+datetime.timedelta(days=info["days"])
        await conn.execute("UPDATE users SET quest_points=quest_points-$1,premium_tier='premium',premium_expires=$2 WHERE id=$3",info["cost"],new_exp,user["id"])
    return {"ok":True,"premium_until":new_exp.isoformat(),"days":info["days"]}

@app.post("/api/daily/bonus")
async def daily_bonus(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    r=await check_daily_bonus(user["id"])
    if not r.get("ok"):
        if r.get("reason")=="already": raise HTTPException(429,f"Через {r['next_in']} сек")
        raise HTTPException(400,r.get("reason","Ошибка"))
    return r

# ============ GAMES ============
@app.post("/api/games/submit")
async def games_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    game=data.get("game"); score=int(data.get("score",0))
    if game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    if score<0 or score>1000000: raise HTTPException(400,"Плохой счёт")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO game_scores(user_id,game,score) VALUES($1,$2,$3)",user["id"],game,score)
    if game=="snake" and score>=100: await grant_achievement(user["id"],"snake_100")
    if game=="flappy" and score>=50: await grant_achievement(user["id"],"flappy_50")
    await grant_xp(user["id"],5)
    await grant_quest_progress(user["id"],"play_3_games",1)
    return {"ok":True}

@app.get("/api/games/leaders")
async def games_leaders(game:str):
    if game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.username,MAX(gs.score) AS best FROM game_scores gs JOIN users u ON u.id=gs.user_id WHERE gs.game=$1 GROUP BY u.id,u.username ORDER BY best DESC LIMIT 20",game)
    return [{"username":r["username"],"score":r["best"]} for r in rows]

@app.get("/api/games/tournament")
async def games_tournament_get():
    return {"game":active_tournament.get("game"),"started_at":active_tournament.get("started_at").isoformat() if active_tournament.get("started_at") else None}

@app.post("/api/games/tournament_set")
async def games_tournament_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    game=data.get("game")
    if game and game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    if game is None:
        active_tournament["game"]=None; active_tournament["started_at"]=None
    else:
        active_tournament["game"]=game; active_tournament["started_at"]=datetime.datetime.now(datetime.timezone.utc)
    await manager.broadcast({"type":"tournament_update","game":active_tournament.get("game")})
    return {"ok":True,"game":active_tournament.get("game")}

@app.post("/api/games/tournament_reset")
async def games_tournament_reset(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    game=data.get("game")
    if game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM game_scores WHERE game=$1",game)
    if active_tournament.get("game")==game: active_tournament["started_at"]=datetime.datetime.now(datetime.timezone.utc)
    await manager.broadcast({"type":"tournament_update","game":active_tournament.get("game")})
    return {"ok":True}

@app.get("/api/games/top3")
async def games_top3():
    p=await get_pool()
    result={}
    async with p.acquire() as conn:
        for g in GAME_LIST:
            rows=await conn.fetch("SELECT u.username,MAX(gs.score) AS best FROM game_scores gs JOIN users u ON u.id=gs.user_id WHERE gs.game=$1 GROUP BY u.id,u.username ORDER BY best DESC LIMIT 3",g)
            result[g]=[{"username":r["username"],"score":r["best"]} for r in rows]
    return result

# ============ ITCH ============
@app.get("/api/itch/list")
async def itch_list():
    return {"games":[{"name":"Dungeon Dash","url":"https://itch.io/embed-upload/0000?color=333333","emoji":"🏰"},{"name":"Roguelike","url":"https://itch.io/embed-upload/1111?color=333333","emoji":"⚔️"}]}

# ============ CALLS ============
@app.post("/api/calls/group/create")
async def calls_group_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if not is_premium(user): raise HTTPException(403,"Только для премиума")
    p=await get_pool()
    async with p.acquire() as conn:
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

# ============ STATIC ============
@app.get("/manifest.json")
async def manifest():
    return {"name":"Belugacord Beta 2.5","short_name":"Belugacord","start_url":"/","display":"standalone","background_color":"#0a0a12","theme_color":"#0a0a12","icons":[{"src":"/uploads/icon.png","sizes":"192x192","type":"image/png"}]}

@app.get("/")
async def index():
    with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())

# ============ WS ============
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
        for ws in list(self.connections.get(uid,[])):
            try: await ws.send_json(data)
            except: self.disconnect(uid,ws)
    async def broadcast(self,data,exclude=None):
        for uid,conns in list(self.connections.items()):
            if exclude and uid==exclude: continue
            for ws in list(conns):
                try: await ws.send_json(data)
                except: self.disconnect(uid,ws)
    async def kick(self,uid):
        for ws in list(self.connections.get(uid,[])):
            try: await ws.close()
            except: pass
        self.connections.pop(uid,None)
        online_users.discard(uid)

manager=ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws:WebSocket,token:str):
    user=await get_current_user(token)
    if not user:
        await ws.close(); return
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
            cleanup_trackers()
            try: data=json.loads(raw)
            except: continue
            t=data.get("type")
            # 2.5 FIX: ping/pong
            if t=="ping":
                try: await ws.send_json({"type":"pong"})
                except: pass
                continue
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
                effect=data.get("effect","none")
                if not ch: continue
                if text.startswith("/"):
                    cmd_name=text[1:].split()[0].lower()
                    p=await get_pool()
                    async with p.acquire() as conn:
                        cr=await conn.fetchrow("SELECT response FROM commands WHERE name=$1",cmd_name)
                    if cr:
                        await manager.send_to(uid,{"type":"dm","from_user":0,"to_user":uid,"username":"🤖 Belugacord","text":cr["response"],"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"is_bot":True})
                        continue
                await check_spam(uid)
                await check_flood(uid,text)
                p=await get_pool()
                async with p.acquire() as conn:
                    chan=await conn.fetchrow("SELECT mode,server_id FROM channels WHERE id=$1",int(ch))
                    if chan and chan["mode"]=="readonly":
                        srv=await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1",chan["server_id"])
                        if srv and srv["owner_id"]!=uid and user["username"]!=ADMIN_USERNAME:
                            await manager.send_to(uid,{"type":"muted","reason":"Канал только для чтения"})
                            continue
                    msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,reply_to,effect) VALUES($1,$2,$3,$4,$5,$6) RETURNING *",int(ch),uid,text,furl,reply,effect)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    mc=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                    await add_last_message_at(conn,channel_id=int(ch))
                if mc==1: await grant_achievement(uid,"first_msg")
                if mc==100: await grant_achievement(uid,"msg_100")
                if mc==1000: await grant_achievement(uid,"msg_1000")
                if mc==10000: await grant_achievement(uid,"msg_10000")
                await grant_quest_progress(uid,"send_10_msgs",1)
                await grant_xp(uid,1)
                payload={"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"reply_to":reply,"effect":effect,"created_at":msg["created_at"].isoformat(),"is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),"is_beta_tester":user.get("is_beta_tester"),"is_scam":user.get("is_scam"),"is_streamer":user.get("is_streamer"),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"title":user.get("title"),"role":get_role(user),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)
            elif t=="dm":
                to_id=int(data.get("to_user",0)); text=(data.get("text") or "")[:2000]
                furl=data.get("file_url"); tid=data.get("temp_id")
                if await is_blocked(uid,to_id): continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",uid,to_id,text,furl)
                await grant_quest_progress(uid,"send_5_dms",1)
                await grant_xp(uid,1)
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"title":user.get("title"),"temp_id":tid}
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
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"title":user.get("title"),"temp_id":tid}
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

if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")