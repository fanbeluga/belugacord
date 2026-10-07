# BELUGACORD 3.1 BETA — server.py
# ZIP/RAR, лимиты 25/50 МБ для премиума, звонки, автомиграции
import os,json,time,secrets,hashlib,random,datetime,asyncio,re,traceback
from typing import Optional
import asyncpg
import httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ==== КОНФИГ ====
DATABASE_URL=os.environ.get("DATABASE_URL","")
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2031")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","")
ADMIN_USERNAME="_fan_beluga_"
ADMIN_DISPLAY="👑 Владелец"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="3.1"
SUPPORT_BOT_ID=0
SUPPORT_BOT_NAME="support_bot"
SUPPORT_BOT_DISPLAY="🤖 Support Bot"

ALLOWED_EXT={
    '.png','.jpg','.jpeg','.gif','.webp','.svg','.bmp','.avif',
    '.mp4','.webm','.mov','.mkv','.avi',
    '.mp3','.wav','.ogg','.m4a','.opus','.aac','.flac',
    '.pdf','.txt','.json','.csv','.xml',
    '.zip','.rar','.7z','.tar','.gz',
    '.doc','.docx','.xls','.xlsx','.ppt','.pptx',
    '.py','.js','.html','.css','.md'
}
ALLOWED_MIME={
    'image/png','image/jpeg','image/jpg','image/gif','image/webp','image/svg+xml','image/bmp','image/avif',
    'video/mp4','video/webm','video/quicktime','video/x-matroska','video/x-msvideo','video/avi',
    'audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/ogg','audio/mp4','audio/webm',
    'audio/opus','audio/aac','audio/x-m4a','audio/flac','audio/x-flac',
    'application/zip','application/x-zip-compressed','application/x-zip',
    'application/x-rar-compressed','application/vnd.rar','application/x-rar',
    'application/x-7z-compressed','application/x-7z',
    'application/x-tar','application/gzip','application/x-gzip',
    'application/pdf','text/plain','application/json','text/csv','application/xml','text/xml',
    'application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint','application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/javascript','application/javascript','text/html','text/css','text/markdown',
    'application/octet-stream'
}
LIMITS={
    None:     {"file":10*1024*1024,  "msg":2000},
    "premium":{"file":25*1024*1024,  "msg":4000},
    "pro":    {"file":50*1024*1024,  "msg":10000},
}
PREMIUM_PRICES={"month":1500,"year":18000}

DEFAULT_GIFTS={
    "rose":{"name":"Роза","emoji":"🌹","price":15},
    "bear":{"name":"Мишка","emoji":"🧸","price":25},
    "cake":{"name":"Торт","emoji":"🎂","price":50},
    "diamond":{"name":"Алмаз","emoji":"💎","price":100},
    "crown":{"name":"Корона","emoji":"👑","price":500},
    "dragon":{"name":"Дракон","emoji":"🐉","price":1000},
    "legend":{"name":"Легендарка","emoji":"💠","price":5000},
    "pumpkin":{"name":"Тыква","emoji":"🎃","price":150},
    "ghost":{"name":"Призрак","emoji":"👻","price":250},
    "skull":{"name":"Череп","emoji":"💀","price":400},
    "bat":{"name":"Летучая мышь","emoji":"🦇","price":300},
    "heart":{"name":"Сердце","emoji":"❤️","price":50},
    "bouquet":{"name":"Букет","emoji":"💐","price":200},
    "book":{"name":"Книга","emoji":"📚","price":150},
    "graduation":{"name":"Диплом","emoji":"🎓","price":500},
    "alien":{"name":"Инопланетянин","emoji":"👽","price":10000},
    "galaxy":{"name":"Галактика","emoji":"🌌","price":100000},
    "tree":{"name":"Ёлка","emoji":"🎄","price":200},
    "santa":{"name":"Дед Мороз","emoji":"🎅","price":400},
    "snowman":{"name":"Снеговик","emoji":"⛄","price":150},
}

GAME_LIST=["snake","2048","tetris","memory","tictactoe","rps","duel","freedoom"]

ACHIEVEMENTS={
    "first_msg":{"name":"Первое слово","emoji":"💬","desc":"Отправь первое сообщение"},
    "msg_100":{"name":"Болтун","emoji":"🗣️","desc":"100 сообщений"},
    "msg_1000":{"name":"Оратор","emoji":"🎤","desc":"1000 сообщений"},
    "first_friend":{"name":"Дружелюбный","emoji":"👥","desc":"Первый друг"},
    "friend_10":{"name":"Тусовщик","emoji":"🎉","desc":"10 друзей"},
    "first_gift":{"name":"Щедрый","emoji":"🎁","desc":"Первый подарок"},
    "first_call":{"name":"Звонкий","emoji":"📞","desc":"Первый звонок"},
    "first_voice":{"name":"Голос","emoji":"🎙️","desc":"Первое голосовое"},
    "first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},
    "first_file":{"name":"Загрузчик","emoji":"📎","desc":"Первый файл"},
}

HOLIDAYS=[
    ("01-01","newyear","Новый год","🎄","#dc2626","world"),
    ("01-07","christmas_orthodox","Православное Рождество","✝️","#fbbf24","ru"),
    ("02-14","valentine","День Валентина","💕","#ec4899","world"),
    ("02-23","defender_day","День защитника","🎖️","#22c55e","ru"),
    ("03-08","womens_day","8 марта","🌷","#f472b6","world"),
    ("04-01","fools_day","День смеха","🤡","#facc15","world"),
    ("04-12","cosmonautics","День космонавтики","🚀","#3b82f6","ru"),
    ("05-01","labour_day","День труда","⚒️","#dc2626","world"),
    ("05-09","victory_day","День Победы","🎖️","#f97316","ru"),
    ("06-01","children_day","День детей","🧒","#22d3ee","world"),
    ("06-12","russia_day","День России","🇷🇺","#ffffff","ru"),
    ("07-04","usa_independence","4 июля США","🇺🇸","#3b82f6","us"),
    ("09-01","knowledge_day","День знаний","📚","#8b5cf6","ru"),
    ("10-01","teachers_day","День учителя","🍎","#f59e0b","world"),
    ("10-31","halloween","Хэллоуин","🎃","#ff6b1a","world"),
    ("11-04","unity_day","День единства","🤝","#dc2626","ru"),
    ("11-24","thanksgiving","День благодарения","🦃","#92400e","us"),
    ("12-25","christmas_catholic","Католическое Рождество","🎅","#dc2626","world"),
]

SCAM_DEFAULT_PERMS={
    "dm_send":False,"dm_reply":True,"gift_send":False,"gift_receive":True,
    "chat_send":True,"chat_create":False,"set_avatar":False,"set_banner":False,
    "open_cases":False,"buy_nft":False,"transfer_coins":False,"join_bp":False,
    "play_games":True,"call":False,"add_friends":False,"post_story":False,
}

BP_PRESETS={
"halloween":{
  "name":"Жуткий месяц","description":"Хэллоуин","emoji":"🎃","days_total":30,"max_level":50,
  "quests":[
    {"name":"Напиши 10 сообщений","action_type":"send_message","target_count":10,"xp_reward":100},
    {"name":"Сыграй 1 игру","action_type":"play_game","target_count":1,"xp_reward":100},
    {"name":"Отправь 1 DM","action_type":"send_dm","target_count":1,"xp_reward":100},
    {"name":"Позвони другу","action_type":"call","target_count":1,"xp_reward":500},
    {"name":"Отправь голосовое","action_type":"voice","target_count":1,"xp_reward":300},
    {"name":"Добавь 1 друга","action_type":"add_friend","target_count":1,"xp_reward":300},
  ],
  "rewards":[
    {"level":1,"reward":"💰 100 бекоинов","reward_type":"coins","reward_value":100,"track":"free"},
    {"level":1,"reward":"💎 Premium 1д","reward_type":"premium","reward_value":1,"track":"premium"},
    {"level":5,"reward":"🎟️ 100 КП","reward_type":"kp","reward_value":100,"track":"free"},
    {"level":10,"reward":"💰 50000 бекоинов","reward_type":"coins","reward_value":50000,"track":"free"},
  ]
},
}

# ============ UTILS ============
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

def sanitize_username(u):
    u=re.sub(r'[^a-zA-Z0-9_]','_',str(u).lower())
    if not u:u="user"
    if len(u)>24:u=u[:24]
    if u[0].isdigit():u="_"+u
    return u

TRANSLIT={
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i',
    'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t',
    'у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y',
    'ь':'','э':'e','ю':'yu','я':'ya','А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E',
    'Ё':'E','Ж':'Zh','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M','Н':'N','О':'O',
    'П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H','Ц':'Ts','Ч':'Ch','Ш':'Sh',
    'Щ':'Sch','Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Yu','Я':'Ya',
}

def translit_to_username(s):
    out=''
    for ch in str(s):
        if ch in TRANSLIT: out+=TRANSLIT[ch]
        elif ch.isalnum(): out+=ch
        elif ch in '_-. ': out+='_'
    if not out: out='user'
    return sanitize_username(out)

async def get_unique_username(conn,base,exclude_id=None):
    base=sanitize_username(base)
    u=base;n=0
    while True:
        if exclude_id:
            row=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",u,exclude_id)
        else:
            row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",u)
        if not row: return u
        n+=1
        u=f"{base}_{n}"
        if len(u)>32:u=base[:28]+f"_{n}"

def _iso(dt):
    if not dt: return None
    try: return dt.isoformat()
    except: return str(dt)

def _aware(dt):
    if dt is None: return None
    if isinstance(dt,str): return dt
    if dt.tzinfo is None: return dt.replace(tzinfo=datetime.timezone.utc)
    return dt

def _safe_int(v,default=0):
    try: return int(v)
    except: return default

def _safe_json(v,default=None):
    if default is None: default={}
    try:
        if isinstance(v,str): return json.loads(v)
        return v
    except: return default

def get_today_holiday():
    today=datetime.datetime.now(datetime.timezone.utc)
    today_str=today.strftime("%m-%d")
    for h in HOLIDAYS:
        if h[0]==today_str:
            return {"active":True,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"exact":True}
    return {"active":False}

# ============ APP ============
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
forced_holiday=None
active_calls={}

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=10)
    return pool

# ============ БД INIT + АВТОМИГРАЦИИ ============
async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        # ===== USERS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            display_name VARCHAR(64),
            password_hash VARCHAR(128) NOT NULL,
            avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%',
            banner_pos TEXT DEFAULT '50% 50%',
            email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,
            email_code VARCHAR(16),email_code_expires TIMESTAMPTZ,
            is_admin BOOLEAN DEFAULT FALSE,
            is_moderator BOOLEAN DEFAULT FALSE,
            is_beta_tester BOOLEAN DEFAULT FALSE,
            is_scam BOOLEAN DEFAULT FALSE,
            is_dev BOOLEAN DEFAULT FALSE,
            is_streamer BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            is_legend BOOLEAN DEFAULT FALSE,
            premium_tier VARCHAR(8),premium_expires TIMESTAMPTZ,
            is_banned BOOLEAN DEFAULT FALSE,
            ban_reason VARCHAR(256),
            mute_until TIMESTAMPTZ,
            nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),
            custom_status VARCHAR(128),
            online_status VARCHAR(16) DEFAULT 'online',
            bio VARCHAR(256),fav_music VARCHAR(128),
            admin_password VARCHAR(128),
            coins INTEGER DEFAULT 0,
            social_rating INTEGER DEFAULT 0,
            messages_count INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]',
            quest_points INTEGER DEFAULT 0,
            active_frame VARCHAR(32),
            frame_owned TEXT DEFAULT '[]',
            title VARCHAR(64),
            title_owned TEXT DEFAULT '[]',
            reputation INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            chest_streak INTEGER DEFAULT 0,
            chest_at TIMESTAMPTZ,
            candy INTEGER DEFAULT 0,
            scam_perms TEXT DEFAULT '{}',
            last_seen TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        # ===== SERVERS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,description TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',last_message_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())""")
        # ===== MESSAGES =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(
            id SERIAL PRIMARY KEY,
            channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,
            reply_to INTEGER,
            reactions TEXT DEFAULT '{}',
            pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,
            effect VARCHAR(16) DEFAULT 'none',
            msg_kind VARCHAR(16) DEFAULT 'text',
            voice_duration INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        # ===== FRIENDS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        # ===== GROUPS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,last_message_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(
            id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,
            msg_kind VARCHAR(16) DEFAULT 'text',
            voice_duration INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        # ===== DMS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(
            id SERIAL PRIMARY KEY,
            from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,
            msg_kind VARCHAR(16) DEFAULT 'text',
            voice_duration INTEGER DEFAULT 0,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        # ===== SUPPORT / ADMIN =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS support_tickets(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,ticket_type VARCHAR(32),target_user INTEGER REFERENCES users(id) ON DELETE SET NULL,title VARCHAR(128),description TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',admin_reply TEXT,resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW(),resolved_at TIMESTAMPTZ)""")
        # ===== GIFTS / NFT / CASES =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        # ===== FRAMES / TITLES =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),is_premium BOOLEAN DEFAULT FALSE,price_coins INTEGER DEFAULT 0,price_kp INTEGER DEFAULT 0)""")
        for f in [("none","Без рамки","",0,0),("gold","Золотая","👑",500,0),("fire","Огненная","🔥",800,0),("ice","Ледяная","❄️",800,0),("rainbow","Радужная","🌈",0,3000),("pumpkin","Тыква","🎃",0,2000),("ghost","Призрак","👻",0,2500),("teacher","Учитель года","🎓",0,1500)]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,price_coins,price_kp) VALUES($1,$2,$3,$4,$5) ON CONFLICT (frame_id) DO NOTHING",*f)
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS titles_catalog(
            id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),color VARCHAR(32),
            is_public BOOLEAN DEFAULT TRUE,condition_type VARCHAR(32),condition_value INTEGER,
            creator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM titles_catalog")
        if cnt==0:
            for t in [("Призрак","👻","#a855f7",True,"free",0),("Вампир","🧛","#dc2626",True,"level",10),("Ведьма","🧙","#ec4899",True,"level",20),("Владыка тьмы","💀","#8b5cf6",True,"level",50),("Учитель года","🎓","#f59e0b",True,"custom",0),("Легенда","🏅","#ffd700",True,"messages",1000)]:
                await conn.execute("INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value) VALUES($1,$2,$3,$4,$5,$6)",*t)
        # ===== BP =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_quests(id SERIAL PRIMARY KEY,name VARCHAR(128),description TEXT,goal INTEGER,xp_reward INTEGER DEFAULT 100,action_type VARCHAR(32),target_count INTEGER DEFAULT 1,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_rewards(id SERIAL PRIMARY KEY,level INTEGER,reward TEXT,reward_type VARCHAR(32),reward_value INTEGER DEFAULT 0,reward_item_id VARCHAR(64),track VARCHAR(16) DEFAULT 'free',active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_season(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🏆',started_at TIMESTAMPTZ DEFAULT NOW(),ended_at TIMESTAMPTZ,ends_at TIMESTAMPTZ,days_total INTEGER DEFAULT 30,max_level INTEGER DEFAULT 50,xp_per_level INTEGER DEFAULT 1000,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_progress(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_id INTEGER,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,claimed TEXT DEFAULT '[]',has_premium_pass BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        # ===== SYSTEM =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS system_settings(key VARCHAR(64) PRIMARY KEY,value TEXT,updated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        # ===== CALLS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_history(
            id SERIAL PRIMARY KEY,
            call_id VARCHAR(32),
            caller INTEGER REFERENCES users(id) ON DELETE CASCADE,
            callee INTEGER REFERENCES users(id) ON DELETE CASCADE,
            call_type VARCHAR(16) DEFAULT 'audio',
            status VARCHAR(16) DEFAULT 'ended',
            duration INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")

        # ============ АВТОМИГРАЦИИ (для старых БД) ============
        migrations=[
            # users
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_legend BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS title VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS title_owned TEXT DEFAULT '[]'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS candy INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS scam_perms TEXT DEFAULT '{}'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_frame VARCHAR(32)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS frame_owned TEXT DEFAULT '[]'",
            "ALTER TABLE users ALTER COLUMN premium_expires TYPE TIMESTAMPTZ USING premium_expires AT TIME ZONE 'UTC'",
            "ALTER TABLE users ALTER COLUMN mute_until TYPE TIMESTAMPTZ USING mute_until AT TIME ZONE 'UTC'",
            "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE users ALTER COLUMN last_seen TYPE TIMESTAMPTZ USING last_seen AT TIME ZONE 'UTC'",
            # messages
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS effect VARCHAR(16) DEFAULT 'none'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited BOOLEAN DEFAULT FALSE",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reactions TEXT DEFAULT '{}'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply_to INTEGER",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS msg_kind VARCHAR(16) DEFAULT 'text'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS voice_duration INTEGER DEFAULT 0",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT 0",
            "ALTER TABLE messages ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            # dms
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS msg_kind VARCHAR(16) DEFAULT 'text'",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS voice_duration INTEGER DEFAULT 0",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT 0",
            "ALTER TABLE dms ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            # group_messages
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS msg_kind VARCHAR(16) DEFAULT 'text'",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS voice_duration INTEGER DEFAULT 0",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT 0",
            "ALTER TABLE group_messages ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            # groups
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ",
            # bp
            "ALTER TABLE bp_progress ADD COLUMN IF NOT EXISTS has_premium_pass BOOLEAN DEFAULT FALSE",
            "ALTER TABLE bp_progress ADD COLUMN IF NOT EXISTS claimed TEXT DEFAULT '[]'",
            "ALTER TABLE bp_season ALTER COLUMN ends_at TYPE TIMESTAMPTZ USING ends_at AT TIME ZONE 'UTC'",
            "ALTER TABLE bp_season ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at AT TIME ZONE 'UTC'",
            # friendships
            "ALTER TABLE friendships ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE friend_requests ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            # calls
            "ALTER TABLE call_history ADD COLUMN IF NOT EXISTS duration INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try: await conn.execute(sql)
            except Exception as e: print(f"[migr] {str(e)[:100]}")
        # Заполняем display_name
        await conn.execute("UPDATE users SET display_name=username WHERE display_name IS NULL")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2",ADMIN_DISPLAY,ADMIN_USERNAME)

        # Support bot
        bot_exists=await conn.fetchval("SELECT 1 FROM users WHERE id=$1",SUPPORT_BOT_ID)
        if not bot_exists:
            try:
                await conn.execute("""INSERT INTO users(id,username,display_name,password_hash,is_admin,is_dev,bio,custom_status)
                    VALUES($1,$2,$3,$4,FALSE,TRUE,$5,$6)""",SUPPORT_BOT_ID,SUPPORT_BOT_NAME,SUPPORT_BOT_DISPLAY,hash_password("bot_"+SECRET_KEY),"🤖 Служба поддержки","🛡️ Здесь можно подать заявку")
                await conn.execute("SELECT setval(pg_get_serial_sequence('users','id'),GREATEST((SELECT MAX(id) FROM users),1))")
            except Exception as e: print(f"Bot: {e}")

        # BP автостарт
        bp_row=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE LIMIT 1")
        if not bp_row:
            preset=BP_PRESETS["halloween"]
            now=datetime.datetime.now(datetime.timezone.utc)
            ends=now+datetime.timedelta(days=preset["days_total"])
            await conn.execute("INSERT INTO bp_season(name,description,emoji,days_total,max_level,ends_at,active,xp_per_level) VALUES($1,$2,$3,$4,$5,$6,TRUE,1000)",preset["name"],preset["description"],preset["emoji"],preset["days_total"],preset["max_level"],ends)
            for q in preset["quests"]:
                await conn.execute("INSERT INTO bp_quests(name,description,goal,xp_reward,action_type,target_count) VALUES($1,'',$2,$3,$4,$2)",q["name"],q["target_count"],q["xp_reward"],q["action_type"])
            for r in preset["rewards"]:
                await conn.execute("INSERT INTO bp_rewards(level,reward,reward_type,reward_value,reward_item_id,track) VALUES($1,$2,$3,$4,$5,$6)",r["level"],r["reward"],r["reward_type"],r["reward_value"],r.get("reward_item_id"),r.get("track","free"))
            print(f"🎃 БП автостарт: {preset['name']}")

        print("✅ БД 3.1 готова (миграции применены)")

# ============ HELPERS ============
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

async def send_email(to_email,subject,html):
    if not RESEND_API_KEY: return {"ok":False,"error":"no_key"}
    try:
        async with httpx.AsyncClient() as client:
            r=await client.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {RESEND_API_KEY}","Content-Type":"application/json"},json={"from":"Belugacord <onboarding@resend.dev>","to":[to_email],"subject":subject,"html":html},timeout=15)
            return {"ok":r.status_code in (200,201)}
    except Exception as e: return {"ok":False,"error":str(e)}

async def grant_achievement(uid,key):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT achievements FROM users WHERE id=$1",uid)
            if not row: return False
            arr=_safe_json(row["achievements"],[])
            if key in arr or key not in ACHIEVEMENTS: return False
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
    if not isinstance(row,dict): row=dict(row)
    if row.get("username")==ADMIN_USERNAME: return True
    tier=row.get("premium_tier")
    if not tier: return False
    exp=row.get("premium_expires")
    if exp:
        try:
            now_utc=datetime.datetime.now(datetime.timezone.utc)
            e=_aware(exp)
            if e<now_utc: return False
        except: pass
    return tier in ("premium","pro")

def has_scam_perm(row,perm):
    if not row: return False
    if not row.get("is_scam"): return True
    perms=_safe_json(row.get("scam_perms"),{})
    return perms.get(perm,SCAM_DEFAULT_PERMS.get(perm,False))

def user_public(row,viewer_id=None):
    if row is None: return {}
    if not isinstance(row,dict): row=dict(row)
    try:
        status=row.get("online_status") or "online"
        uid=row["id"]
        is_online=uid in online_users and status!="invisible"
        if status=="invisible" and viewer_id!=uid: is_online=False
        scam_perms=_safe_json(row.get("scam_perms"),{})
        dn=row.get("display_name") or row.get("username") or "user"
        return {
            "id":row["id"],
            "username":row["username"],
            "display_name":dn,
            "avatar":row.get("avatar"),"banner":row.get("banner"),
            "gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
            "avatar_pos":row.get("avatar_pos") or "50% 50%",
            "banner_pos":row.get("banner_pos") or "50% 50%",
            "is_admin":bool(row.get("is_admin",False)),
            "is_moderator":bool(row.get("is_moderator",False)),
            "is_beta_tester":bool(row.get("is_beta_tester",False)),
            "is_scam":bool(row.get("is_scam",False)),
            "scam_perms":scam_perms,
            "is_dev":bool(row.get("is_dev",False)),
            "is_streamer":bool(row.get("is_streamer",False)),
            "is_verified":bool(row.get("is_verified",False)),
            "is_legend":bool(row.get("is_legend",False)),
            "premium_tier":row.get("premium_tier"),
            "premium_expires":_iso(row.get("premium_expires")),
            "is_premium":is_premium(row),
            "nickname_color":row.get("nickname_color"),
            "nickname_gradient":row.get("nickname_gradient"),
            "custom_status":row.get("custom_status"),
            "online_status":status,
            "bio":row.get("bio"),"fav_music":row.get("fav_music"),
            "coins":row.get("coins",0) or 0,
            "social_rating":row.get("social_rating",0) or 0,
            "messages_count":row.get("messages_count",0) or 0,
            "achievements":_safe_json(row.get("achievements"),[]),
            "quest_points":row.get("quest_points",0) or 0,
            "active_frame":row.get("active_frame"),
            "frame_owned":_safe_json(row.get("frame_owned"),[]),
            "title":row.get("title"),
            "title_owned":_safe_json(row.get("title_owned"),[]),
            "reputation":row.get("reputation",0) or 0,
            "level":row.get("level",1) or 1,
            "xp":row.get("xp",0) or 0,
            "candy":row.get("candy",0) or 0,
            "created_at":_iso(row.get("created_at")),
            "role":get_role(row),
            "online":is_online
        }
    except Exception as e:
        print(f"[user_public ERR] id={row.get('id')} {e}")
        traceback.print_exc()
        return {"id":row.get("id"),"username":row.get("username"),"display_name":row.get("display_name") or row.get("username"),"is_premium":False,"online":False}

async def get_all_gifts():
    gifts=dict(DEFAULT_GIFTS)
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM custom_gifts WHERE is_sticker=FALSE OR is_sticker IS NULL")
            for r in rows: gifts[r["gift_id"]]={"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"]}
    except: pass
    return gifts

async def is_blocked(user_id,other_id):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT id FROM blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user_id,other_id)
            return bool(row)
    except: return False

async def grant_xp(uid,amount):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT xp,level FROM users WHERE id=$1",uid)
            if not row: return
            new_xp=row["xp"]+amount
            new_level=row["level"]
            while new_xp>=(new_level*100):
                new_xp-=new_level*100
                new_level+=1
                await manager.send_to(uid,{"type":"level_up","level":new_level})
            await conn.execute("UPDATE users SET xp=$1,level=$2 WHERE id=$3",new_xp,new_level,uid)
    except: pass

async def bp_add_progress(uid,action_type,amount=1):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            season=await conn.fetchrow("SELECT id,xp_per_level,max_level FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
            if not season: return
            quests=await conn.fetch("SELECT id,xp_reward FROM bp_quests WHERE active=TRUE AND action_type=$1",action_type)
            if not quests: return
            total_xp=sum(q["xp_reward"] for q in quests)
            if total_xp==0: return
            prog=await conn.fetchrow("SELECT id,xp,level FROM bp_progress WHERE user_id=$1 AND season_id=$2",uid,season["id"])
            if not prog:
                await conn.execute("INSERT INTO bp_progress(user_id,season_id,xp,level) VALUES($1,$2,0,1)",uid,season["id"])
                prog=await conn.fetchrow("SELECT id,xp,level FROM bp_progress WHERE user_id=$1 AND season_id=$2",uid,season["id"])
            new_xp=prog["xp"]+total_xp
            new_level=prog["level"]
            xp_per=season["xp_per_level"] or 1000
            max_lv=season["max_level"] or 50
            while new_xp>=xp_per and new_level<max_lv:
                new_xp-=xp_per
                new_level+=1
                await manager.send_to(uid,{"type":"bp_level_up","level":new_level})
            await conn.execute("UPDATE bp_progress SET xp=$1,level=$2 WHERE id=$3",new_xp,new_level,prog["id"])
    except Exception as e: print(f"bp: {e}")

async def _get_target(conn,data):
    if data.get("user_id"):
        return await conn.fetchrow("SELECT id,username,display_name FROM users WHERE id=$1",int(data["user_id"]))
    if data.get("username"):
        return await conn.fetchrow("SELECT id,username,display_name FROM users WHERE username=$1",str(data["username"]).lstrip("@"))
    return None

# ============ STARTUP ============
@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e:
            print(f"❌ DB INIT ERROR: {e}")
            traceback.print_exc()

# ============ WS MANAGER ============
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
# ============ CHANGELOG ============
@app.get("/api/changelog")
async def changelog():
    return {"current":CURRENT_VERSION,"all":{
        "3.1":{"title":"Belugacord 3.1 Beta","items":[
            "🛡️ Кнопка «Админка» для админов и модераторов",
            "📢 Анонс всем — показывается у всех онлайн",
            "🎨 Рабочие рамки — предпросмотр + выбор",
            "📦 ZIP, RAR, 7Z архивы до 10 МБ",
            "💎 Премиум — до 25 МБ на файл",
            "🚀 Pro — до 50 МБ на файл",
            "📁 Иконки файлов (архивы/PDF/DOC/TXT)",
            "🎙️ Голосовые сообщения с плеером",
            "📞 Аудио/видеозвонки WebRTC",
            "🖥️ Демонстрация экрана",
            "⚙️ Выбор микрофона, камеры, динамика",
            "📥 История звонков",
            "🎭 Ник отдельно от username",
            "🔐 Секретный вход 5 кликов по логотипу",
            "🔔 Автопоказ кнопок по роли",
            "💾 file_size в сообщениях",
            "🎯 Пул соединений до 10",
            "🛡️ Отдельная call_history таблица"
        ]},
        "3.0":{"title":"Belugacord 3.0 Beta","items":["📞 Звонки","🖥️ Экран","🎙️ Голосовые","📷 Фото/видео до 10МБ"]},
        "2.9":{"title":"Belugacord 2.9 Beta","items":["🎭 Ник отдельно","🎨 Эффекты","👥 Друзья","🎁 Подарки"]},
    }}

@app.get("/api/achievements/all")
async def achievements_all(): return ACHIEVEMENTS

@app.get("/api/check_username")
async def check_username(username:str):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",sanitize_username(username))
    return {"available":row is None,"suggested":sanitize_username(username)}

# ============ AUTH ============
@app.post("/api/register")
async def register(data:dict):
    raw_username=(data.get("username") or "").strip()
    raw_display=(data.get("display_name") or data.get("nick") or "").strip()
    pw=data.get("password") or ""
    em=(data.get("email") or "").strip() or None
    if not raw_username and raw_display: raw_username=translit_to_username(raw_display)
    if not raw_display: raw_display=raw_username
    if len(raw_username)<2 or len(raw_username)>32: raise HTTPException(400,"Username 2-32")
    if len(pw)<4: raise HTTPException(400,"Пароль мин 4")
    if len(raw_display)<2 or len(raw_display)>64: raise HTTPException(400,"Ник 2-64")
    p=await get_pool()
    async with p.acquire() as conn:
        uname=await get_unique_username(conn,raw_username)
        row=await conn.fetchrow("INSERT INTO users(username,display_name,password_hash,email,is_admin) VALUES($1,$2,$3,$4,$5) RETURNING *",uname,raw_display,hash_password(pw),em,uname==ADMIN_USERNAME)
    if em:
        code=str(random.randint(100000,999999))
        try:
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET email_code=$1,email_code_expires=NOW()+INTERVAL '1 hour' WHERE id=$2",code,row["id"])
            asyncio.create_task(send_email(em,"Belugacord — подтверждение",f"<h2>Привет, {raw_display}!</h2><p>Код: <b>{code}</b></p>"))
        except: pass
    return {"token":make_token(row["id"],row["username"]),"user":user_public(row,row["id"])}

@app.post("/api/login")
async def login(data:dict):
    u=(data.get("username") or "").strip().lstrip("@").lower()
    pw=data.get("password") or ""
    if not u or not pw: raise HTTPException(400,"Заполни поля")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE username=$1 OR LOWER(display_name)=$2",u,u)
    if not row or not verify_password(pw,row["password_hash"]): raise HTTPException(400,"Неверный логин/пароль")
    if row["is_banned"]: raise HTTPException(403,row.get("ban_reason") or "Забанен")
    return {"token":make_token(row["id"],row["username"]),"user":user_public(row,row["id"])}

@app.get("/api/me")
async def me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return user_public(user,user["id"])

# ============ PROFILE ============
@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    premium=is_premium(user)
    if (data.get("gif_avatar") or data.get("gif_banner")) and not premium:
        raise HTTPException(403,"GIF только для премиума")
    if user.get("is_scam"):
        if data.get("avatar") and not has_scam_perm(user,"set_avatar"): raise HTTPException(403,"SCAM: ава запрещена")
        if data.get("banner") and not has_scam_perm(user,"set_banner"): raise HTTPException(403,"SCAM: баннер запрещён")
    new_display=data.get("display_name")
    if new_display is not None:
        new_display=str(new_display).strip()[:64]
        if len(new_display)<2: raise HTTPException(400,"Ник мин 2")
    p=await get_pool()
    async with p.acquire() as conn:
        if new_display is not None:
            await conn.execute("UPDATE users SET display_name=$1 WHERE id=$2",new_display,user["id"])
        await conn.execute("""UPDATE users SET
            avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),
            gif_avatar=COALESCE($3,gif_avatar),gif_banner=COALESCE($4,gif_banner),
            avatar_pos=COALESCE($5,avatar_pos),banner_pos=COALESCE($6,banner_pos),
            nickname_color=$7,nickname_gradient=$8,
            bio=COALESCE($9,bio),fav_music=COALESCE($10,fav_music),
            custom_status=COALESCE($11,custom_status)
            WHERE id=$12""",
            data.get("avatar"),data.get("banner"),data.get("gif_avatar"),data.get("gif_banner"),
            data.get("avatar_pos"),data.get("banner_pos"),
            data.get("nickname_color"),data.get("nickname_gradient"),
            data.get("bio"),data.get("fav_music"),data.get("custom_status"),user["id"])
    if new_display is not None:
        await manager.broadcast({"type":"user_updated","user_id":user["id"],"display_name":new_display})
    return {"ok":True}

@app.post("/api/user/change_username")
async def change_username(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    new=sanitize_username(data.get("username") or "")
    if not re.match(r'^[a-z0-9_]{2,24}$',new): raise HTTPException(400,"Только a-z, 0-9, _")
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",new,user["id"])
        if exists: raise HTTPException(400,"Занято")
        await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,user["id"])
    return {"ok":True,"token":make_token(user["id"],new),"username":new}

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
        row=await conn.fetchrow("SELECT * FROM users WHERE id=$1",user_id)
    if not row: raise HTTPException(404,"Не найден")
    return user_public(row,user_id)

@app.get("/api/users/search")
async def users_search(q:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip().lstrip("@")
    if len(q)<1: return []
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT * FROM users WHERE (username ILIKE $1 OR display_name ILIKE $1) AND id!=$2 AND id!=0 ORDER BY username LIMIT 25""",f"%{q}%",user["id"])
    return [user_public(r,user["id"]) for r in rows]

# ============ FRIENDS ============
@app.get("/api/friends/list")
async def friends_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    uid=user["id"]
    p=await get_pool()
    async with p.acquire() as conn:
        result=[]
        frows=await conn.fetch("SELECT f.id AS row_id, CASE WHEN f.user_a=$1 THEN f.user_b ELSE f.user_a END AS other_id FROM friendships f WHERE f.user_a=$1 OR f.user_b=$1",uid)
        for r in frows:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["other_id"])
            if not o: continue
            last=await conn.fetchval("SELECT MAX(created_at) FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",uid,r["other_id"])
            item=user_public(o,uid)
            item["status"]="accepted"
            item["friend_row_id"]=r["row_id"]
            item["last_message_at"]=_iso(last)
            result.append(item)
        inc=await conn.fetch("SELECT id AS request_id,from_user AS other_id,created_at FROM friend_requests WHERE to_user=$1 ORDER BY created_at DESC",uid)
        for r in inc:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["other_id"])
            if not o: continue
            item=user_public(o,uid)
            item["status"]="incoming"
            item["request_id"]=r["request_id"]
            item["requested_at"]=_iso(r["created_at"])
            result.append(item)
        out=await conn.fetch("SELECT id AS request_id,to_user AS other_id,created_at FROM friend_requests WHERE from_user=$1 ORDER BY created_at DESC",uid)
        for r in out:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["other_id"])
            if not o: continue
            item=user_public(o,uid)
            item["status"]="outgoing"
            item["request_id"]=r["request_id"]
            item["requested_at"]=_iso(r["created_at"])
            result.append(item)
    def sort_key(x):
        prio={"incoming":0,"accepted":1,"outgoing":2}.get(x.get("status"),3)
        return (prio,not x.get("online"),not x.get("is_premium"))
    result.sort(key=sort_key)
    return result

@app.post("/api/friends/request_by_id")
async def friends_request_by_id(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"add_friends"): raise HTTPException(403,"SCAM")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id нужен")
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    if tid==0: raise HTTPException(400,"Бота нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid):
            raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid):
            raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_request","from_id":user["id"],"username":user["username"],"display_name":user.get("display_name") or user["username"],"avatar":user.get("avatar")})
    return {"ok":True}

@app.post("/api/friends/accept")
async def friends_accept(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    if not rid: raise HTTPException(400,"request_id нужен")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT id,from_user,to_user FROM friend_requests WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Обработана")
        if r["to_user"]!=user["id"]: raise HTTPException(403,"Не твоя")
        a,b=sorted([r["from_user"],r["to_user"]])
        try: await conn.execute("INSERT INTO friendships(user_a,user_b) VALUES($1,$2) ON CONFLICT DO NOTHING",a,b)
        except: pass
        await conn.execute("DELETE FROM friend_requests WHERE id=$1",rid)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM friendships WHERE user_a=$1 OR user_b=$1",user["id"])
        if cnt==1: await grant_achievement(user["id"],"first_friend")
        if cnt>=10: await grant_achievement(user["id"],"friend_10")
        other=await conn.fetchrow("SELECT id,username,display_name,avatar FROM users WHERE id=$1",r["from_user"])
    await manager.send_to(r["from_user"],{"type":"friend_accepted","friend_id":user["id"],"username":user["username"],"display_name":user.get("display_name") or user["username"],"avatar":user.get("avatar")})
    if other:
        await manager.send_to(user["id"],{"type":"friend_accepted","friend_id":other["id"],"username":other["username"],"display_name":other.get("display_name") or other["username"],"avatar":other["avatar"]})
    try: await bp_add_progress(user["id"],"add_friend",1)
    except: pass
    return {"ok":True}

@app.post("/api/friends/decline")
async def friends_decline(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    if not rid: raise HTTPException(400,"request_id нужен")
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
    if not rid: raise HTTPException(400,"request_id нужен")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND from_user=$2",rid,user["id"])
    return {"ok":True}

@app.post("/api/friends/remove")
async def friends_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id нужен")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_removed","by_id":user["id"],"username":user["username"]})
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

@app.get("/api/servers/{server_id}/channels")
async def server_channels(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,type FROM channels WHERE server_id=$1 ORDER BY id",server_id)
    return [dict(r) for r in rows]

@app.post("/api/channels/create")
async def channel_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=int(data.get("server_id",0));name=(data.get("name") or "").strip()[:64]
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
        rows=await conn.fetch("""SELECT m.id,m.text,m.file_url,m.file_size,m.reactions,m.edited,m.reply_to,m.pinned,m.effect,m.created_at,m.user_id,m.msg_kind,m.voice_duration,
            u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.is_scam
            FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200""",channel_id)
    out=[]
    for r in rows:
        d=dict(r)
        d["created_at"]=_iso(d.get("created_at"))
        d["reactions"]=_safe_json(d.get("reactions"),{})
        out.append(d)
    return {"messages":out}

@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if await is_blocked(user["id"],user_id): raise HTTPException(403,"Заблокировано")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.file_size,d.created_at,d.read_at,d.msg_kind,d.voice_duration,
            u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.is_scam,u.title
            FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC LIMIT 200""",user["id"],user_id)
        await conn.execute("UPDATE dms SET read_at=NOW() WHERE from_user=$1 AND to_user=$2 AND read_at IS NULL",user_id,user["id"])
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=_iso(d.get("created_at"));d["read_at"]=_iso(d.get("read_at"))
        out.append(d)
    return out

# ============ GROUPS ============
@app.get("/api/groups/list")
async def groups_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.* FROM groups g JOIN group_members gm ON gm.group_id=g.id WHERE gm.user_id=$1 ORDER BY COALESCE(g.last_message_at,g.created_at) DESC",user["id"])
    return [{"id":r["id"],"name":r["name"],"avatar":r["avatar"],"description":r["description"],"owner_id":r["owner_id"]} for r in rows]

@app.post("/api/groups/create")
async def groups_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("INSERT INTO groups(name,avatar,description,owner_id) VALUES($1,$2,$3,$4) RETURNING *",name,data.get("avatar"),(data.get("description","") or "")[:256],user["id"])
        await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)",g["id"],user["id"])
    return {"id":g["id"],"name":g["name"],"avatar":g["avatar"]}

@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        rows=await conn.fetch("""SELECT gm.id,gm.text,gm.file_url,gm.file_size,gm.created_at,gm.user_id,gm.msg_kind,gm.voice_duration,
            u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.is_scam
            FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200""",group_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=_iso(d.get("created_at"));out.append(d)
    return out

# ============ MESSAGES ============
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

@app.post("/api/messages/reaction")
async def message_reaction(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0));emoji=data.get("emoji","👍")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        react=_safe_json(row["reactions"],{})
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
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO user_saved_messages(user_id,text) VALUES($1,$2)",user["id"],text)
    return {"ok":True}

@app.get("/api/messages/saved")
async def messages_saved(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,text,created_at FROM user_saved_messages WHERE user_id=$1 ORDER BY id DESC",user["id"])
    return [{"id":r["id"],"text":r["text"],"created_at":_iso(r["created_at"])} for r in rows]

# ============ UPLOAD (с новыми лимитами и ZIP) ============
def _get_file_limit(user):
    if not user: return 10*1024*1024
    if user.get("username")==ADMIN_USERNAME: return 50*1024*1024
    tier=user.get("premium_tier")
    if tier=="pro": return 50*1024*1024
    if tier=="premium" or is_premium(user): return 25*1024*1024
    return 10*1024*1024

@app.post("/api/upload")
async def upload(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    lim=_get_file_limit(user)
    mime=(file.content_type or "application/octet-stream").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(400,f"Тип файла запрещён: {mime}")
    ext=os.path.splitext(file.filename or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT:
        raise HTTPException(400,f"Расширение запрещено: {ext}")
    content=await file.read()
    if len(content)>lim:
        mb=lim//1024//1024
        raise HTTPException(400,f"Файл больше {mb} МБ")
    if len(content)==0:
        raise HTTPException(400,"Пустой файл")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}","size":len(content),"mime":mime,"limit":lim,"name":file.filename or name}

@app.post("/api/upload_voice")
async def upload_voice(token:str=Form(...),file:UploadFile=File(...),duration:int=Form(0)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"chat_send"): raise HTTPException(403,"SCAM")
    mime=(file.content_type or "audio/webm").lower()
    if not mime.startswith("audio/"): raise HTTPException(400,"Только аудио")
    content=await file.read()
    if len(content)>5*1024*1024: raise HTTPException(400,"Голосовое макс 5 МБ")
    ext=".webm" if "webm" in mime else (".ogg" if "ogg" in mime else ".mp3")
    name=f"voice_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    if duration<1: duration=1
    if duration>300: duration=300
    await grant_achievement(user["id"],"first_voice")
    await bp_add_progress(user["id"],"voice",1)
    return {"url":f"/uploads/{name}","duration":duration,"size":len(content)}

# ============ GIFTS / NFT / CASES ============
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
    if user.get("is_scam") and not has_scam_perm(user,"gift_send"): raise HTTPException(403,"SCAM")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    gift=g[gift_id];price=gift["price"]
    if user.get("coins",0)<price: raise HTTPException(400,"Не хватает")
    to_id=int(data.get("to_user",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",price,user["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],to_id,gift_id)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1",user["id"])
    if cnt==1: await grant_achievement(user["id"],"first_gift")
    await manager.send_to(to_id,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"from_name":user.get("display_name") or user["username"]})
    await bp_add_progress(user["id"],"give_gift",1)
    return {"ok":True}

@app.get("/api/cases/list")
async def cases_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,emoji,image,price FROM cases WHERE is_active=TRUE ORDER BY id DESC")
    return [dict(r) for r in rows]

# ============ BP ============
@app.get("/api/bp/current")
async def bp_current(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT * FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: return {"active":False}
        prog=await conn.fetchrow("SELECT * FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        quests=await conn.fetch("SELECT * FROM bp_quests WHERE active=TRUE ORDER BY id")
        rewards=await conn.fetch("SELECT * FROM bp_rewards WHERE active=TRUE ORDER BY level,track")
    my_xp=prog["xp"] if prog else 0
    my_level=prog["level"] if prog else 1
    claimed=_safe_json(prog["claimed"],[]) if prog else []
    has_pp=prog["has_premium_pass"] if prog else False
    ends_in_days=None
    if season.get("ends_at"):
        try:
            ea=_aware(season["ends_at"])
            ends_in_days=max(0,int((ea-datetime.datetime.now(datetime.timezone.utc)).total_seconds()//86400))
        except: pass
    return {"active":True,"name":season["name"],"description":season["description"],"emoji":season["emoji"],
            "my_xp":my_xp,"my_level":my_level,"xp_per_level":season.get("xp_per_level") or 1000,"max_level":season.get("max_level") or 50,
            "ends_in_days":ends_in_days,"has_premium_pass":has_pp,
            "quests":[{"id":q["id"],"name":q["name"],"xp_reward":q["xp_reward"]} for q in quests],
            "rewards":[{"id":r["id"],"level":r["level"],"reward":r["reward"],"track":r.get("track","free"),"unlocked":my_level>=r["level"] and str(r["id"]) not in claimed,"locked_premium":r.get("track")=="premium" and not has_pp} for r in rewards]}

@app.post("/api/bp/claim")
async def bp_claim(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    level=int(data.get("level",0))
    track=(data.get("track") or "free").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: raise HTTPException(404,"Нет сезона")
        r=await conn.fetchrow("SELECT * FROM bp_rewards WHERE level=$1 AND active=TRUE AND track=$2 LIMIT 1",level,track)
        if not r: raise HTTPException(404,"Нет награды")
        prog=await conn.fetchrow("SELECT * FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        if not prog or prog["level"]<level: raise HTTPException(400,"Уровень мал")
        if track=="premium" and not prog["has_premium_pass"]: raise HTTPException(403,"Нужен премиум-пропуск")
        claimed=_safe_json(prog["claimed"],[])
        rid=str(r["id"])
        if rid in claimed: raise HTTPException(400,"Уже забрано")
        claimed.append(rid)
        await conn.execute("UPDATE bp_progress SET claimed=$1 WHERE id=$2",json.dumps(claimed),prog["id"])
        rt=r.get("reward_type");rv=r.get("reward_value") or 0
        if rt=="coins": await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",rv,user["id"])
        elif rt=="kp": await conn.execute("UPDATE users SET quest_points=quest_points+$1 WHERE id=$2",rv,user["id"])
        elif rt=="candy": await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",rv,user["id"])
        elif rt=="premium": await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",rv,user["id"])
    return {"ok":True}

@app.post("/api/bp/buy_premium_pass")
async def bp_buy_premium_pass(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if (user.get("coins") or 0)<2000: raise HTTPException(400,"Нужно 2000 🏅")
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: raise HTTPException(404,"Нет сезона")
        prog=await conn.fetchrow("SELECT id,has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        if prog and prog["has_premium_pass"]: raise HTTPException(400,"Уже куплен")
        await conn.execute("UPDATE users SET coins=coins-2000 WHERE id=$1",user["id"])
        if prog: await conn.execute("UPDATE bp_progress SET has_premium_pass=TRUE WHERE id=$1",prog["id"])
        else: await conn.execute("INSERT INTO bp_progress(user_id,season_id,xp,level,has_premium_pass) VALUES($1,$2,0,1,TRUE)",user["id"],season["id"])
    return {"ok":True}

# ============ HOLIDAYS ============
@app.get("/api/holiday/today")
async def holiday_today():
    global forced_holiday
    if forced_holiday:
        h=next((x for x in HOLIDAYS if x[1]==forced_holiday),None)
        if h: return {"active":True,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"forced":True}
    return get_today_holiday()

@app.get("/api/holiday/all")
async def holiday_all():
    return [{"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"date":h[0]} for h in HOLIDAYS]

# ============ TITLES ============
@app.get("/api/titles/list")
async def titles_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        owned_raw=_safe_json(user.get("title_owned"),[])
        owned_ids=[]
        for x in owned_raw:
            try: owned_ids.append(int(x))
            except: pass
        rows=await conn.fetch("SELECT * FROM titles_catalog WHERE is_public=TRUE OR creator_id=$1 OR id = ANY($2::int[]) ORDER BY is_public DESC, id DESC",user["id"],owned_ids)
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"is_public":r["is_public"],"condition_type":r["condition_type"],"condition_value":r["condition_value"],"creator_id":r["creator_id"]} for r in rows]

@app.post("/api/titles/set")
async def titles_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    title_id=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",title_id)
        if not t: raise HTTPException(404,"Нет титула")
        owned_raw=_safe_json(user.get("title_owned"),[])
        owned=[]
        for x in owned_raw:
            try: owned.append(int(x))
            except: pass
        if t["is_public"]:
            ct=t["condition_type"];cv=t["condition_value"] or 0
            if ct=="level" and user.get("level",1)<cv: raise HTTPException(403,f"Нужен ур.{cv}")
            if ct=="messages" and user.get("messages_count",0)<cv: raise HTTPException(403,f"Нужно {cv} сообщений")
            if ct=="custom": raise HTTPException(403,"Только по выдаче")
        else:
            if title_id not in owned and t["creator_id"]!=user["id"]: raise HTTPException(403,"Нет доступа")
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",t["name"],user["id"])
        if title_id not in owned:
            owned.append(title_id)
            await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True}

@app.post("/api/titles/create")
async def titles_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:20]
    if not name: raise HTTPException(400,"Название нужно")
    emoji=(data.get("emoji") or "⭐")[:8]
    color=(data.get("color") or "#d946ef")[:32]
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value,creator_id) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,emoji,color,False,"custom",0,user["id"])
        owned=_safe_json(user.get("title_owned"),[])
        owned.append(r["id"])
        await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True,"id":r["id"]}

@app.post("/api/titles/give")
async def titles_give(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет титула")
        is_owner=user["username"]==ADMIN_USERNAME
        is_creator=t["creator_id"]==user["id"]
        if not (is_owner or is_creator): raise HTTPException(403,"Только владелец или создатель")
        target=await _get_target(conn,data)
        if not target: raise HTTPException(404,"Юзер не найден")
        target_full=await conn.fetchrow("SELECT title_owned FROM users WHERE id=$1",target["id"])
        owned=_safe_json(target_full["title_owned"],[])
        if tid not in owned: owned.append(tid)
        await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),target["id"])
    await manager.send_to(target["id"],{"type":"title_given","title_id":tid,"name":t["name"],"emoji":t["emoji"]})
    return {"ok":True}

@app.post("/api/titles/delete")
async def titles_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет")
        is_owner=user["username"]==ADMIN_USERNAME
        is_creator=t["creator_id"]==user["id"]
        if not (is_owner or is_creator): raise HTTPException(403,"Нет прав")
        await conn.execute("DELETE FROM titles_catalog WHERE id=$1",tid)
    return {"ok":True}

# ============ SUPPORT ============
@app.post("/api/support/ticket")
async def support_ticket(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ticket_type=(data.get("ticket_type") or "").strip()
    if ticket_type not in ("unscam","unban","report_scam","report_spam","other"): raise HTTPException(400,"Тип")
    title=(data.get("title") or "")[:128]
    description=(data.get("description") or "")[:2000]
    evidence=(data.get("evidence") or "")[:1000]
    target=int(data.get("target_user") or 0)
    if not description: raise HTTPException(400,"Опиши ситуацию")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("INSERT INTO support_tickets(from_user,ticket_type,target_user,title,description,evidence) VALUES($1,$2,$3,$4,$5,$6) RETURNING id",user["id"],ticket_type,target or None,title,description,evidence)
        owner=await conn.fetchrow("SELECT id FROM users WHERE username=$1",ADMIN_USERNAME)
        if owner: await manager.send_to(owner["id"],{"type":"support_ticket_new","id":row["id"],"from":user["username"],"type":ticket_type})
    return {"ok":True,"ticket_id":row["id"]}

@app.get("/api/support/my_tickets")
async def my_tickets(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM support_tickets WHERE from_user=$1 ORDER BY id DESC LIMIT 50",user["id"])
    return [{"id":r["id"],"ticket_type":r["ticket_type"],"title":r["title"],"description":r["description"],"status":r["status"],"created_at":_iso(r["created_at"])} for r in rows]

# ============ COINS / LEVELS / FRAMES / PREMIUM ============
@app.get("/api/coins/balance")
async def coins_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"coins":user.get("coins",0),"candy":user.get("candy",0)}

@app.get("/api/levels/me")
async def levels_me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"level":user.get("level",1),"xp":user.get("xp",0),"next_xp":(user.get("level",1))*100}

@app.get("/api/frames/list")
async def frames_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM frames_catalog ORDER BY price_coins,price_kp")
        owned=_safe_json(user.get("frame_owned"),[])
    return [{"frame_id":r["frame_id"],"name":r["name"],"emoji":r["emoji"],"owned":r["frame_id"] in owned or r["frame_id"]=="none"} for r in rows]

@app.post("/api/frames/set")
async def frames_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    fid=data.get("frame_id","none")
    p=await get_pool()
    async with p.acquire() as conn:
        if fid!="none":
            owned=_safe_json(user.get("frame_owned"),[])
            if fid not in owned: raise HTTPException(403,"Не куплена")
        await conn.execute("UPDATE users SET active_frame=$1 WHERE id=$2",fid if fid!="none" else None,user["id"])
    return {"ok":True}

@app.post("/api/premium/buy")
async def premium_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan","month")
    if plan not in PREMIUM_PRICES: raise HTTPException(400,"Нет плана")
    price=PREMIUM_PRICES[plan];days=30 if plan=="month" else 365
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT coins,premium_expires FROM users WHERE id=$1",user["id"])
        if (row["coins"] or 0)<price: raise HTTPException(400,f"Нужно {price} 🏅")
        now=datetime.datetime.now(datetime.timezone.utc)
        base=now
        if row["premium_expires"]:
            e=_aware(row["premium_expires"])
            if e>now: base=e
        new_exp=base+datetime.timedelta(days=days)
        await conn.execute("UPDATE users SET coins=coins-$1,premium_tier='premium',premium_expires=$2 WHERE id=$3",price,new_exp,user["id"])
    return {"ok":True}

@app.post("/api/duel/fire")
async def duel_fire(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bet=int(data.get("bet",0))
    if bet<50: raise HTTPException(400,"Мин 50")
    if (user.get("coins") or 0)<bet: raise HTTPException(400,"Не хватает")
    win=random.random()<0.5
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",bet,user["id"])
        if win: await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",bet*2,user["id"])
    return {"ok":True,"win":win}

@app.post("/api/games/submit")
async def games_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    game=data.get("game");score=int(data.get("score",0))
    if game not in GAME_LIST: raise HTTPException(400,"Игра?")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO game_scores(user_id,game,score) VALUES($1,$2,$3)",user["id"],game,score)
    await grant_xp(user["id"],5)
    await bp_add_progress(user["id"],"play_game",1)
    return {"ok":True}

# ============ CALL HISTORY ============
@app.get("/api/calls/history")
async def calls_history(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT ch.*,
            c.username AS caller_username, c.display_name AS caller_display,
            e.username AS callee_username, e.display_name AS callee_display
            FROM call_history ch
            LEFT JOIN users c ON c.id=ch.caller
            LEFT JOIN users e ON e.id=ch.callee
            WHERE ch.caller=$1 OR ch.callee=$1
            ORDER BY ch.id DESC LIMIT 50""",user["id"])
    return [{"id":r["id"],"caller":r["caller"],"callee":r["callee"],
             "caller_name":r["caller_display"] or r["caller_username"],
             "callee_name":r["callee_display"] or r["callee_username"],
             "call_type":r["call_type"],"status":r["status"],"duration":r["duration"],
             "created_at":_iso(r["created_at"])} for r in rows]10