# BELUGACORD 3.3 — server.py — ЧАСТЬ 1/2
import os,json,time,secrets,hashlib,random,datetime,asyncio,re,traceback
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
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2032")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","")
ADMIN_USERNAME="_fan_beluga_"
ADMIN_DISPLAY="👑 Владелец"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="3.3"
SUPPORT_BOT_ID=0
SUPPORT_BOT_NAME="support_bot"
SUPPORT_BOT_DISPLAY="🤖 Support Bot"
NOTIF_ICON="/icon-192×192.png"
MAX_TEXT=10000

ALLOWED_EXT={'.png','.jpg','.jpeg','.gif','.webp','.svg','.bmp','.avif','.ico','.mp4','.webm','.mov','.mkv','.avi','.mp3','.wav','.ogg','.m4a','.opus','.aac','.flac','.pdf','.txt','.json','.csv','.xml','.zip','.rar','.7z','.tar','.gz','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.py','.js','.html','.css','.md'}
ALLOWED_MIME={'image/png','image/jpeg','image/jpg','image/gif','image/webp','image/svg+xml','image/bmp','image/avif','image/x-icon','video/mp4','video/webm','video/quicktime','video/x-matroska','video/x-msvideo','audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/ogg','audio/mp4','audio/webm','audio/opus','audio/aac','audio/x-m4a','audio/flac','application/zip','application/x-zip-compressed','application/x-zip','application/x-rar-compressed','application/vnd.rar','application/x-7z-compressed','application/x-7z','application/x-tar','application/gzip','application/pdf','text/plain','application/json','text/csv','application/xml','text/xml','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','application/vnd.ms-powerpoint','application/vnd.openxmlformats-officedocument.presentationml.presentation','text/javascript','application/javascript','text/html','text/css','text/markdown','application/octet-stream'}
LIMITS={None:{"file":10*1024*1024,"msg":10000},"premium":{"file":25*1024*1024,"msg":25000},"pro":{"file":50*1024*1024,"msg":50000}}
PREMIUM_PRICES={"month":1500,"year":18000}

DEFAULT_GIFTS={
    "rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},
    "cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},
    "crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},
    "legend":{"name":"Легендарка","emoji":"💠","price":5000},"pumpkin":{"name":"Тыква","emoji":"🎃","price":150},
    "ghost":{"name":"Призрак","emoji":"👻","price":250},"skull":{"name":"Череп","emoji":"💀","price":400},
    "bat":{"name":"Летучая мышь","emoji":"🦇","price":300},"heart":{"name":"Сердце","emoji":"❤️","price":50},
    "bouquet":{"name":"Букет","emoji":"💐","price":200},"book":{"name":"Книга","emoji":"📚","price":150},
    "graduation":{"name":"Диплом","emoji":"🎓","price":500},"alien":{"name":"Инопланетянин","emoji":"👽","price":10000},
    "galaxy":{"name":"Галактика","emoji":"🌌","price":100000},"tree":{"name":"Ёлка","emoji":"🎄","price":200},
    "santa":{"name":"Дед Мороз","emoji":"🎅","price":400},"snowman":{"name":"Снеговик","emoji":"⛄","price":150},
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
TRANSLIT={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya','А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'E','Ж':'Zh','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M','Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'H','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Sch','Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Yu','Я':'Ya'}
def translit_to_username(s):
    out=''
    for ch in str(s):
        if ch in TRANSLIT: out+=TRANSLIT[ch]
        elif ch.isalnum(): out+=ch
        elif ch in '_-. ': out+='_'
    if not out: out='user'
    return sanitize_username(out)
async def get_unique_username(conn,base,exclude_id=None):
    base=sanitize_username(base);u=base;n=0
    while True:
        if exclude_id: row=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",u,exclude_id)
        else: row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",u)
        if not row: return u
        n+=1;u=f"{base}_{n}"
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
    ts=today.strftime("%m-%d")
    for h in HOLIDAYS:
        if h[0]==ts: return {"active":True,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"exact":True}
    return {"active":False}

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

@app.get("/icon.png")
async def serve_icon():
    for path in ["icon-192x192.png","icon.png",os.path.join(UPLOAD_DIR,"icon.png")]:
        if os.path.exists(path):
            with open(path,"rb") as f: return HTMLResponse(content=f.read(),media_type="image/png")
    return HTMLResponse("",status_code=404)

pool=None
online_users=set()
forced_holiday=None
active_calls={}

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=10)
    return pool

async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,username VARCHAR(64) UNIQUE NOT NULL,display_name VARCHAR(64),
            password_hash VARCHAR(128) NOT NULL,avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',
            email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,email_code VARCHAR(16),email_code_expires TIMESTAMPTZ,
            is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,is_beta_tester BOOLEAN DEFAULT FALSE,
            is_scam BOOLEAN DEFAULT FALSE,is_dev BOOLEAN DEFAULT FALSE,is_streamer BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,is_legend BOOLEAN DEFAULT FALSE,
            premium_tier VARCHAR(8),premium_expires TIMESTAMPTZ,
            is_banned BOOLEAN DEFAULT FALSE,ban_reason VARCHAR(256),mute_until TIMESTAMPTZ,
            nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),custom_status VARCHAR(128),
            online_status VARCHAR(16) DEFAULT 'online',bio VARCHAR(256),fav_music VARCHAR(128),
            admin_password VARCHAR(128),coins INTEGER DEFAULT 0,social_rating INTEGER DEFAULT 0,
            messages_count INTEGER DEFAULT 0,achievements TEXT DEFAULT '[]',quest_points INTEGER DEFAULT 0,
            active_frame VARCHAR(32),frame_owned TEXT DEFAULT '[]',title VARCHAR(64),title_owned TEXT DEFAULT '[]',
            reputation INTEGER DEFAULT 0,level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,
            chest_streak INTEGER DEFAULT 0,chest_at TIMESTAMPTZ,candy INTEGER DEFAULT 0,
            scam_perms TEXT DEFAULT '{}',airplane_mode BOOLEAN DEFAULT FALSE,
            notif_enabled BOOLEAN DEFAULT TRUE,sound_enabled BOOLEAN DEFAULT TRUE,theme VARCHAR(16) DEFAULT 'dark',
            font_size VARCHAR(8) DEFAULT 'md',rank_id INTEGER,double_xp_until TIMESTAMPTZ,
            last_seen TIMESTAMPTZ DEFAULT NOW(),created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,description TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',last_message_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(
            id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,
            reply_to INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,
            effect VARCHAR(16) DEFAULT 'none',msg_kind VARCHAR(16) DEFAULT 'text',voice_duration INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,chat_cleared BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,last_message_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,msg_kind VARCHAR(16) DEFAULT 'text',voice_duration INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(
            id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,
            msg_kind VARCHAR(16) DEFAULT 'text',voice_duration INTEGER DEFAULT 0,
            read_at TIMESTAMPTZ,forwarded_from VARCHAR(64),pinned BOOLEAN DEFAULT FALSE,starred TEXT DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS support_tickets(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,ticket_type VARCHAR(32),target_user INTEGER REFERENCES users(id) ON DELETE SET NULL,title VARCHAR(128),description TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',admin_reply TEXT,resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW(),resolved_at TIMESTAMPTZ)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),is_premium BOOLEAN DEFAULT FALSE,price_coins INTEGER DEFAULT 0,price_kp INTEGER DEFAULT 0)""")
        for f in [("none","Без рамки","",0,0),("gold","Золотая","👑",500,0),("fire","Огненная","🔥",800,0),("ice","Ледяная","❄️",800,0),("rainbow","Радужная","🌈",0,3000),("pumpkin","Тыква","🎃",0,2000),("ghost","Призрак","👻",0,2500),("teacher","Учитель года","🎓",0,1500)]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,price_coins,price_kp) VALUES($1,$2,$3,$4,$5) ON CONFLICT (frame_id) DO NOTHING",*f)
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS titles_catalog(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),color VARCHAR(32),is_public BOOLEAN DEFAULT TRUE,condition_type VARCHAR(32),condition_value INTEGER,creator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM titles_catalog")
        if cnt==0:
            for t in [("Призрак","👻","#a855f7",True,"free",0),("Вампир","🧛","#dc2626",True,"level",10),("Ведьма","🧙","#ec4899",True,"level",20),("Владыка тьмы","💀","#8b5cf6",True,"level",50),("Учитель года","🎓","#f59e0b",True,"custom",0),("Легенда","🏅","#ffd700",True,"messages",1000)]:
                await conn.execute("INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value) VALUES($1,$2,$3,$4,$5,$6)",*t)
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_quests(id SERIAL PRIMARY KEY,name VARCHAR(128),description TEXT,goal INTEGER,xp_reward INTEGER DEFAULT 100,action_type VARCHAR(32),target_count INTEGER DEFAULT 1,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_rewards(id SERIAL PRIMARY KEY,level INTEGER,reward TEXT,reward_type VARCHAR(32),reward_value INTEGER DEFAULT 0,reward_item_id VARCHAR(64),track VARCHAR(16) DEFAULT 'free',active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_season(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🏆',started_at TIMESTAMPTZ DEFAULT NOW(),ended_at TIMESTAMPTZ,ends_at TIMESTAMPTZ,days_total INTEGER DEFAULT 30,max_level INTEGER DEFAULT 50,xp_per_level INTEGER DEFAULT 1000,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_progress(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_id INTEGER,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,claimed TEXT DEFAULT '[]',has_premium_pass BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS system_settings(key VARCHAR(64) PRIMARY KEY,value TEXT,updated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_history(id SERIAL PRIMARY KEY,call_id VARCHAR(32),caller INTEGER REFERENCES users(id) ON DELETE CASCADE,callee INTEGER REFERENCES users(id) ON DELETE CASCADE,call_type VARCHAR(16) DEFAULT 'audio',status VARCHAR(16) DEFAULT 'ended',duration INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ranks(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8) DEFAULT '🏆',color VARCHAR(32) DEFAULT '#d946ef',priority INTEGER DEFAULT 10,perms TEXT DEFAULT '{}',created_at TIMESTAMPTZ DEFAULT NOW())""")

        migrations=[
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_legend BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS title VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS title_owned TEXT DEFAULT '[]'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS candy INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS scam_perms TEXT DEFAULT '{}'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_frame VARCHAR(32)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS frame_owned TEXT DEFAULT '[]'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS airplane_mode BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_enabled BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS sound_enabled BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS theme VARCHAR(16) DEFAULT 'dark'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS font_size VARCHAR(8) DEFAULT 'md'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS rank_id INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS double_xp_until TIMESTAMPTZ",
            "ALTER TABLE users ALTER COLUMN premium_expires TYPE TIMESTAMPTZ USING premium_expires AT TIME ZONE 'UTC'",
            "ALTER TABLE users ALTER COLUMN mute_until TYPE TIMESTAMPTZ USING mute_until AT TIME ZONE 'UTC'",
            "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE users ALTER COLUMN last_seen TYPE TIMESTAMPTZ USING last_seen AT TIME ZONE 'UTC'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS effect VARCHAR(16) DEFAULT 'none'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS edited BOOLEAN DEFAULT FALSE",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reactions TEXT DEFAULT '{}'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply_to INTEGER",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS msg_kind VARCHAR(16) DEFAULT 'text'",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS voice_duration INTEGER DEFAULT 0",
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT 0",
            "ALTER TABLE messages ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS msg_kind VARCHAR(16) DEFAULT 'text'",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS voice_duration INTEGER DEFAULT 0",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT 0",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS forwarded_from VARCHAR(64)",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS starred TEXT DEFAULT '[]'",
            "ALTER TABLE dms ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS msg_kind VARCHAR(16) DEFAULT 'text'",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS voice_duration INTEGER DEFAULT 0",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS file_size BIGINT DEFAULT 0",
            "ALTER TABLE group_messages ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ",
            "ALTER TABLE bp_progress ADD COLUMN IF NOT EXISTS has_premium_pass BOOLEAN DEFAULT FALSE",
            "ALTER TABLE bp_progress ADD COLUMN IF NOT EXISTS claimed TEXT DEFAULT '[]'",
            "ALTER TABLE bp_season ALTER COLUMN ends_at TYPE TIMESTAMPTZ USING ends_at AT TIME ZONE 'UTC'",
            "ALTER TABLE bp_season ALTER COLUMN started_at TYPE TIMESTAMPTZ USING started_at AT TIME ZONE 'UTC'",
            "ALTER TABLE friendships ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE friend_requests ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC'",
            "ALTER TABLE user_blocks ADD COLUMN IF NOT EXISTS chat_cleared BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN IF NOT EXISTS duration INTEGER DEFAULT 0",
            "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
        ]
        for sql in migrations:
            try: await conn.execute(sql)
            except Exception as e: print(f"[migr] {str(e)[:100]}")

        try:
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_dms_users ON dms(from_user,to_user,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_ranks_priority ON ranks(priority DESC)")
        except Exception as e: print(f"[idx] {str(e)[:80]}")

        await conn.execute("UPDATE users SET display_name=username WHERE display_name IS NULL")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2",ADMIN_DISPLAY,ADMIN_USERNAME)

        bot_exists=await conn.fetchval("SELECT 1 FROM users WHERE id=$1",SUPPORT_BOT_ID)
        if not bot_exists:
            try:
                await conn.execute("""INSERT INTO users(id,username,display_name,password_hash,is_admin,is_dev,bio,custom_status)
                    VALUES($1,$2,$3,$4,FALSE,TRUE,$5,$6)""",SUPPORT_BOT_ID,SUPPORT_BOT_NAME,SUPPORT_BOT_DISPLAY,hash_password("bot_"+SECRET_KEY),"🤖 Служба поддержки","🛡️ Здесь можно подать заявку")
                await conn.execute("SELECT setval(pg_get_serial_sequence('users','id'),GREATEST((SELECT MAX(id) FROM users),1))")
            except Exception as e: print(f"Bot: {e}")

        ranks_cnt=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if ranks_cnt==0:
            try:
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","👑 Владелец","👑","#ffd700",1000,json.dumps({"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"manage_shop":True,"manage_cosmetics":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True,"bypass_limits":True,"verified":True,"custom_title":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🛡️ Администратор","🛡️","#d946ef",500,json.dumps({"admin_panel":True,"manage_users":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True,"broadcast":True,"verified":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🔨 Модератор","🔨","#22c55e",100,json.dumps({"mute":True,"delete_msgs":True}))
                print("✅ Дефолтные ранги созданы")
            except Exception as e: print(f"[ranks init] {e}")

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

        print("✅ БД 3.3 готова")

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
            r=await client.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {RESEND_API_KEY}","Content-Type":"application/json"},json={"from":"BelugaCord <onboarding@resend.dev>","to":[to_email],"subject":subject,"html":html},timeout=15)
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
            if _aware(exp)<datetime.datetime.now(datetime.timezone.utc): return False
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
        return {"id":row["id"],"username":row["username"],"display_name":dn,
            "avatar":row.get("avatar"),"banner":row.get("banner"),
            "gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
            "avatar_pos":row.get("avatar_pos") or "50% 50%","banner_pos":row.get("banner_pos") or "50% 50%",
            "is_admin":bool(row.get("is_admin",False)),"is_moderator":bool(row.get("is_moderator",False)),
            "is_beta_tester":bool(row.get("is_beta_tester",False)),"is_scam":bool(row.get("is_scam",False)),
            "scam_perms":scam_perms,"is_dev":bool(row.get("is_dev",False)),"is_streamer":bool(row.get("is_streamer",False)),
            "is_verified":bool(row.get("is_verified",False)),"is_legend":bool(row.get("is_legend",False)),
            "premium_tier":row.get("premium_tier"),"premium_expires":_iso(row.get("premium_expires")),
            "is_premium":is_premium(row),"nickname_color":row.get("nickname_color"),
            "nickname_gradient":row.get("nickname_gradient"),"custom_status":row.get("custom_status"),
            "online_status":status,"bio":row.get("bio"),"fav_music":row.get("fav_music"),
            "coins":row.get("coins",0) or 0,"social_rating":row.get("social_rating",0) or 0,
            "messages_count":row.get("messages_count",0) or 0,"achievements":_safe_json(row.get("achievements"),[]),
            "quest_points":row.get("quest_points",0) or 0,"active_frame":row.get("active_frame"),
            "frame_owned":_safe_json(row.get("frame_owned"),[]),"title":row.get("title"),
            "title_owned":_safe_json(row.get("title_owned"),[]),"reputation":row.get("reputation",0) or 0,
            "level":row.get("level",1) or 1,"xp":row.get("xp",0) or 0,"candy":row.get("candy",0) or 0,
            "rank_id":row.get("rank_id"),"font_size":row.get("font_size") or "md",
            "airplane_mode":bool(row.get("airplane_mode",False)),"notif_enabled":bool(row.get("notif_enabled",True)),
            "sound_enabled":bool(row.get("sound_enabled",True)),"theme":row.get("theme") or "dark",
            "created_at":_iso(row.get("created_at")),"role":get_role(row),"online":is_online}
    except Exception as e:
        print(f"[user_public ERR] id={row.get('id')} {e}")
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

async def get_xp_rate():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            v=await conn.fetchval("SELECT value FROM system_settings WHERE key='xp_rate'")
            return int(v) if v else 5
    except: return 5

async def grant_xp(uid,amount):
    try:
        rate=await get_xp_rate()
        amount=amount*rate//5
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT xp,level,double_xp_until FROM users WHERE id=$1",uid)
            if not row: return
            if row.get("double_xp_until"):
                try:
                    if _aware(row["double_xp_until"])>datetime.datetime.now(datetime.timezone.utc): amount*=2
                except: pass
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
    if data.get("user_id"): return await conn.fetchrow("SELECT id,username,display_name FROM users WHERE id=$1",int(data["user_id"]))
    if data.get("username"): return await conn.fetchrow("SELECT id,username,display_name FROM users WHERE username=$1",str(data["username"]).lstrip("@"))
    return None

async def is_blocked(user_id,other_id):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT id FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user_id,other_id)
            return bool(row)
    except: return False

def _user_perms(user):
    if not user: return {}
    if user["username"]==ADMIN_USERNAME:
        return {"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"manage_shop":True,"manage_cosmetics":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True,"bypass_limits":True,"verified":True,"custom_title":True}
    perms={}
    if user.get("is_admin"): perms["admin_panel"]=True
    if user.get("is_moderator"): perms["mute"]=True;perms["delete_msgs"]=True
    return perms

async def get_user_perms_full(conn,uid):
    row=await conn.fetchrow("SELECT * FROM users WHERE id=$1",uid)
    if not row: return {},None
    u=dict(row)
    perms=_user_perms(u)
    if u.get("rank_id"):
        r=await conn.fetchrow("SELECT perms,name,emoji,color,priority FROM ranks WHERE id=$1",u["rank_id"])
        if r:
            rp=_safe_json(r["perms"],{})
            perms={**perms,**rp}
            return perms,{"id":u["rank_id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"priority":r["priority"]}
    return perms,None

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e:
            print(f"❌ DB INIT ERROR: {e}")
            traceback.print_exc()

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

@app.get("/api/changelog")
async def changelog():
    return {"current":CURRENT_VERSION,"all":{
        "3.3":{"title":"BelugaCord 3.3 — Мобильный юбилей","items":[
            "📱 Новый мобильный интерфейс с табами сверху",
            "💬 Вкладки: Чаты / Друзья / Каналы / Стол / Я",
            "👥 Экран друзей с 3 табами",
            "➕ Кнопка быстрого добавления в друзья",
            "👤 Экран профиля с загрузкой аватара и баннера",
            "⚙️ Настройки с тумблерами",
            "🎨 3 темы: тёмная / светлая / AMOLED",
            "📝 4 размера шрифта",
            "📋 Долгий тап на сообщении → меню",
            "↪️ Пересылка, ⭐ избранное, 📌 закреп",
            "🔎 Поиск по чату",
            "🖼️ Обои для чата",
            "✍️ Индикатор «печатает...»",
            "👑 Бог-панель на 10 разделов",
            "🏆 Система рангов с 15 правами",
            "💰 Массовая раздача коинов и конфет",
            "🛒 Управление магазином и кейсами",
            "🎉 Ивенты (x2 XP, скидки, дроп)",
            "📊 Полная статистика мессенджера",
            "📢 Рассылки и анонсы",
            "🚀 Убрано ограничение длины чата",
            "📝 Лимит текста поднят до 10000"
        ]},
        "3.2":{"title":"BelugaCord 3.2 Beta","items":["📱 Мобильный UI","✈️ Режим полёта","🚫 Блокировка","🗑️ Стереть переписку","🔔 Push-уведомления"]},
        "3.1":{"title":"BelugaCord 3.1 Beta","items":["🛡️ Админка","🎨 Рамки","📦 ZIP","📞 Звонки"]},
        "3.0":{"title":"BelugaCord 3.0 Beta","items":["📞 WebRTC","🎙️ Голосовые","📷 Медиа"]},
    }}

@app.get("/api/achievements/all")
async def achievements_all(): return ACHIEVEMENTS

@app.get("/api/check_username")
async def check_username(username:str):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",sanitize_username(username))
    return {"available":row is None,"suggested":sanitize_username(username)}

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
            asyncio.create_task(send_email(em,"BelugaCord — подтверждение",f"<h2>Привет, {raw_display}!</h2><p>Код: <b>{code}</b></p>"))
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
    pub=user_public(user,user["id"])
    p=await get_pool()
    async with p.acquire() as conn:
        perms,rank=await get_user_perms_full(conn,user["id"])
    pub["perms"]=perms
    pub["rank"]=rank
    return pub

@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    premium=is_premium(user)
    if (data.get("gif_avatar") or data.get("gif_banner")) and not premium: raise HTTPException(403,"GIF только для премиума")
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
            nickname_color=$7,nickname_gradient=$8,bio=COALESCE($9,bio),
            fav_music=COALESCE($10,fav_music),custom_status=COALESCE($11,custom_status)
            WHERE id=$12""",
            data.get("avatar"),data.get("banner"),data.get("gif_avatar"),data.get("gif_banner"),
            data.get("avatar_pos"),data.get("banner_pos"),data.get("nickname_color"),
            data.get("nickname_gradient"),data.get("bio"),data.get("fav_music"),
            data.get("custom_status"),user["id"])
    if new_display is not None:
        await manager.broadcast({"type":"user_updated","user_id":user["id"],"display_name":new_display})
    return {"ok":True}

@app.post("/api/upload_avatar")
async def upload_avatar(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"set_avatar"): raise HTTPException(403,"SCAM")
    mime=(file.content_type or "").lower()
    if not mime.startswith("image/"): raise HTTPException(400,"Только картинка")
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(400,"Макс 10 МБ")
    ext=os.path.splitext(file.filename or "")[1].lower() or ".png"
    name=f"av_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    url=f"/uploads/{name}"
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET avatar=$1 WHERE id=$2",url,user["id"])
    await manager.broadcast({"type":"user_updated","user_id":user["id"]})
    return {"ok":True,"url":url}

@app.post("/api/upload_banner")
async def upload_banner(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"set_banner"): raise HTTPException(403,"SCAM")
    mime=(file.content_type or "").lower()
    if not mime.startswith("image/"): raise HTTPException(400,"Только картинка")
    content=await file.read()
    if len(content)>15*1024*1024: raise HTTPException(400,"Макс 15 МБ")
    ext=os.path.splitext(file.filename or "")[1].lower() or ".png"
    name=f"bn_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    url=f"/uploads/{name}"
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET banner=$1 WHERE id=$2",url,user["id"])
    await manager.broadcast({"type":"user_updated","user_id":user["id"]})
    return {"ok":True,"url":url}

@app.post("/api/user/quick_setting")
async def quick_setting(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    key=str(data.get("key") or "")
    val=data.get("value")
    allowed={"airplane_mode":"airplane_mode","notif_enabled":"notif_enabled","sound_enabled":"sound_enabled","theme":"theme","font_size":"font_size"}
    col=allowed.get(key)
    if not col: raise HTTPException(400,"Неизвестный ключ")
    p=await get_pool()
    async with p.acquire() as conn:
        if col in ("theme","font_size"):
            await conn.execute(f"UPDATE users SET {col}=$1 WHERE id=$2",str(val)[:16],user["id"])
        else:
            await conn.execute(f"UPDATE users SET {col}=$1 WHERE id=$2",bool(val),user["id"])
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
        rows=await conn.fetch("SELECT * FROM users WHERE (username ILIKE $1 OR display_name ILIKE $1) AND id!=$2 AND id!=0 ORDER BY username LIMIT 25",f"%{q}%",user["id"])
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
            item["status"]="accepted";item["friend_row_id"]=r["row_id"];item["last_message_at"]=_iso(last)
            result.append(item)
        inc=await conn.fetch("SELECT id AS request_id,from_user AS other_id,created_at FROM friend_requests WHERE to_user=$1 ORDER BY created_at DESC",uid)
        for r in inc:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["other_id"])
            if not o: continue
            item=user_public(o,uid);item["status"]="incoming";item["request_id"]=r["request_id"];result.append(item)
        out=await conn.fetch("SELECT id AS request_id,to_user AS other_id,created_at FROM friend_requests WHERE from_user=$1 ORDER BY created_at DESC",uid)
        for r in out:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["other_id"])
            if not o: continue
            item=user_public(o,uid);item["status"]="outgoing";item["request_id"]=r["request_id"];result.append(item)
    def sk(x):
        prio={"incoming":0,"accepted":1,"outgoing":2}.get(x.get("status"),3)
        return (prio,not x.get("online"),not x.get("is_premium"))
    result.sort(key=sk)
    return result

@app.post("/api/friends/request")
async def friends_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"add_friends"): raise HTTPException(403,"SCAM")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id")
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    if tid==0: raise HTTPException(400,"Бота нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid): raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_request","from_id":user["id"],"username":user["username"],"display_name":user.get("display_name") or user["username"],"avatar":user.get("avatar")})
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
    await bp_add_progress(user["id"],"add_friend",1)
    return {"ok":True}

@app.post("/api/friends/decline")
async def friends_decline(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    if not rid: raise HTTPException(400,"request_id")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT from_user,to_user FROM friend_requests WHERE id=$1",rid)
        if not r: return {"ok":True}
        if r["to_user"]!=user["id"]: raise HTTPException(403,"Не твоя")
        await conn.execute("DELETE FROM friend_requests WHERE id=$1",rid)
    await manager.send_to(r["from_user"],{"type":"friend_declined","by_id":user["id"]})
    return {"ok":True}

@app.post("/api/friends/cancel")
async def friends_cancel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    if not rid: raise HTTPException(400,"request_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND from_user=$2",rid,user["id"])
    return {"ok":True}

@app.post("/api/friends/remove")
async def friends_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_removed","by_id":user["id"]})
    return {"ok":True}

# ============ БЛОКИРОВКА ============
@app.post("/api/block/add")
async def block_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id")
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        try: await conn.execute("INSERT INTO user_blocks(blocker,blocked) VALUES($1,$2) ON CONFLICT DO NOTHING",user["id"],tid)
        except: pass
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
        await conn.execute("DELETE FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid)
    await manager.send_to(tid,{"type":"you_are_blocked","by_id":user["id"]})
    return {"ok":True}

@app.post("/api/block/remove")
async def block_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM user_blocks WHERE blocker=$1 AND blocked=$2",user["id"],tid)
    await manager.send_to(tid,{"type":"you_are_unblocked","by_id":user["id"]})
    return {"ok":True}

@app.get("/api/block/list")
async def block_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT b.blocked AS id,u.username,u.display_name,u.avatar,b.chat_cleared FROM user_blocks b JOIN users u ON u.id=b.blocked WHERE b.blocker=$1 ORDER BY b.created_at DESC""",user["id"])
    return [dict(r) for r in rows]

@app.post("/api/dm/clear")
async def dm_clear(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM user_blocks WHERE blocker=$1 AND blocked=$2",user["id"],tid)
        if not row: raise HTTPException(403,"Только при блокировке")
        await conn.execute("DELETE FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid)
        await conn.execute("UPDATE user_blocks SET chat_cleared=TRUE WHERE blocker=$1 AND blocked=$2",user["id"],tid)
    await manager.send_to(tid,{"type":"chat_cleared","by_id":user["id"]})
    return {"ok":True}

# ============ DM — БЕЗ ЛИМИТА ============
@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str,force:int=0):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        block_row=await conn.fetchrow("SELECT blocker,chat_cleared FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user["id"],user_id)
        if block_row:
            blocked_by_me=(block_row["blocker"]==user["id"])
            cleared=block_row["chat_cleared"]
            if cleared and not force:
                return {"blocked":True,"blocked_by_me":blocked_by_me,"cleared":True,"messages":[],"user_id":user_id}
            rows=await conn.fetch("""SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.file_size,d.created_at,d.read_at,d.msg_kind,d.voice_duration,d.forwarded_from,d.pinned,
                u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.is_scam,u.title FROM dms d JOIN users u ON u.id=d.from_user
                WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC""",user["id"],user_id)
            out=[]
            for r in rows:
                dd=dict(r);dd["created_at"]=_iso(dd.get("created_at"));dd["read_at"]=_iso(dd.get("read_at"));out.append(dd)
            return {"blocked":True,"blocked_by_me":blocked_by_me,"cleared":False,"messages":out,"user_id":user_id}
        rows=await conn.fetch("""SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.file_size,d.created_at,d.read_at,d.msg_kind,d.voice_duration,d.forwarded_from,d.pinned,
            u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.is_scam,u.title FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC""",user["id"],user_id)
        await conn.execute("UPDATE dms SET read_at=NOW() WHERE from_user=$1 AND to_user=$2 AND read_at IS NULL",user_id,user["id"])
    out=[]
    for r in rows:
        dd=dict(r);dd["created_at"]=_iso(dd.get("created_at"));dd["read_at"]=_iso(dd.get("read_at"));out.append(dd)
    return out

# ============ SERVERS / GROUPS ============
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
    if not name: raise HTTPException(400,"Имя")
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

@app.get("/api/channels/{channel_id}/messages")
async def channel_messages(channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT m.id,m.text,m.file_url,m.file_size,m.reactions,m.edited,m.reply_to,m.pinned,m.effect,m.created_at,m.user_id,m.msg_kind,m.voice_duration,
            u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.is_scam FROM messages m JOIN users u ON u.id=m.user_id
            WHERE m.channel_id=$1 ORDER BY m.id ASC""",channel_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=_iso(d.get("created_at"));d["reactions"]=_safe_json(d.get("reactions"),{});out.append(d)
    return {"messages":out}

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
    if not name: raise HTTPException(400,"Имя")
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
            FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC""",group_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=_iso(d.get("created_at"));out.append(d)
    return out

# ============ MESSAGES 3.3 ============
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
    if not mid: raise HTTPException(400,"message_id")
    if len(emoji)>8: emoji=emoji[:8]
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет сообщения")
        react=_safe_json(row["reactions"],{})
        arr=react.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        if arr: react[emoji]=arr
        else:
            try: del react[emoji]
            except: pass
        await conn.execute("UPDATE messages SET reactions=$1 WHERE id=$2",json.dumps(react),mid)
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":react})
    return {"ok":True,"reactions":react}

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

@app.post("/api/messages/forward")
async def messages_forward(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0));to_id=int(data.get("to_user",0))
    if not mid or not to_id: raise HTTPException(400,"message_id и to_user")
    p=await get_pool()
    async with p.acquire() as conn:
        src=await conn.fetchrow("SELECT * FROM dms WHERE id=$1",mid)
        if not src:
            src=await conn.fetchrow("SELECT * FROM messages WHERE id=$1",mid)
        if not src: raise HTTPException(404,"Нет сообщения")
        origin_name=src.get("display_name") or "юзер"
        new=await conn.fetchrow("""INSERT INTO dms(from_user,to_user,text,file_url,file_size,msg_kind,voice_duration,forwarded_from)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
            user["id"],to_id,src.get("text"),src.get("file_url"),src.get("file_size") or 0,
            src.get("msg_kind") or "text",src.get("voice_duration") or 0,origin_name)
    dn=user.get("display_name") or user["username"]
    payload={"type":"dm","id":new["id"],"from_user":user["id"],"to_user":to_id,
        "username":user["username"],"display_name":dn,"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),
        "text":src.get("text"),"file_url":src.get("file_url"),"file_size":src.get("file_size") or 0,
        "msg_kind":src.get("msg_kind") or "text","voice_duration":src.get("voice_duration") or 0,
        "forwarded_from":origin_name,"created_at":_iso(new["created_at"])}
    await manager.send_to(to_id,payload)
    await manager.send_to(user["id"],payload)
    return {"ok":True}

@app.post("/api/messages/star")
async def messages_star(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    if not mid: raise HTTPException(400,"message_id")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT starred FROM dms WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        arr=_safe_json(row["starred"],[])
        if user["id"] in arr: arr.remove(user["id"]);new_state=False
        else: arr.append(user["id"]);new_state=True
        await conn.execute("UPDATE dms SET starred=$1 WHERE id=$2",json.dumps(arr),mid)
    return {"ok":True,"starred":new_state}

@app.post("/api/messages/pin")
async def messages_pin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    if not mid: raise HTTPException(400,"message_id")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT pinned FROM dms WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        new_state=not bool(row["pinned"])
        await conn.execute("UPDATE dms SET pinned=$1 WHERE id=$2",new_state,mid)
    await manager.broadcast({"type":"message_pinned","id":mid,"pinned":new_state})
    return {"ok":True,"pinned":new_state}

@app.post("/api/upload")
async def upload(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    lim=_get_file_limit(user)
    mime=(file.content_type or "application/octet-stream").lower()
    if mime not in ALLOWED_MIME: raise HTTPException(400,f"Тип запрещён: {mime}")
    ext=os.path.splitext(file.filename or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT: raise HTTPException(400,f"Расш. запрещено: {ext}")
    content=await file.read()
    if len(content)>lim:
        mb=lim//1024//1024
        raise HTTPException(400,f"Файл больше {mb} МБ")
    if len(content)==0: raise HTTPException(400,"Пустой файл")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}","size":len(content),"mime":mime,"limit":lim,"name":file.filename or name}

def _get_file_limit(user):
    if not user: return 10*1024*1024
    if user.get("username")==ADMIN_USERNAME: return 50*1024*1024
    tier=user.get("premium_tier")
    if tier=="pro": return 50*1024*1024
    if tier=="premium" or is_premium(user): return 25*1024*1024
    return 10*1024*1024

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
    return {"ok":True}

@app.get("/api/cases/list")
async def cases_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,emoji,image,price FROM cases WHERE is_active=TRUE ORDER BY id DESC")
    return [dict(r) for r in rows]

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
    level=int(data.get("level",0));track=(data.get("track") or "free").strip()
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
    if not name: raise HTTPException(400,"Название")
    emoji=(data.get("emoji") or "⭐")[:8]
    color=(data.get("color") or "#d946ef")[:32]
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value,creator_id) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,emoji,color,False,"custom",0,user["id"])
        owned=_safe_json(user.get("title_owned"),[])
        owned.append(r["id"])
        await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True,"id":r["id"]}

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
        now=datetime.datetime.now(datetime.timezone.utc);base=now
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

@app.get("/api/calls/history")
async def calls_history(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT ch.*,c.username AS caller_username,c.display_name AS caller_display,e.username AS callee_username,e.display_name AS callee_display
            FROM call_history ch LEFT JOIN users c ON c.id=ch.caller LEFT JOIN users e ON e.id=ch.callee
            WHERE ch.caller=$1 OR ch.callee=$1 ORDER BY ch.id DESC LIMIT 50""",user["id"])
    return [{"id":r["id"],"caller":r["caller"],"callee":r["callee"],
             "caller_name":r["caller_display"] or r["caller_username"],
             "callee_name":r["callee_display"] or r["callee_username"],
             "call_type":r["call_type"],"status":r["status"],"duration":r["duration"],
             "created_at":_iso(r["created_at"])} for r in rows]

# ============ КОНЕЦ ЧАСТИ 1/2 ============
# ПРОДОЛЖЕНИЕ В ЧАСТИ 2/2 — Owner/Admin/Ranks/Events/WS/Static
# ============================================================
# BELUGACORD 3.3 — ЧАСТЬ 2a — ADMIN, RANKS, USERS, LOGS
# ============================================================

async def check_owner(user):
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")

async def check_admin(user):
    if not user: raise HTTPException(401,"Не авторизован")
    if not (user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Не админ")

async def check_perm(user,perm):
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
    if not perms.get(perm): raise HTTPException(403,f"Нет права: {perm}")
    return perms

async def get_my_rank_priority(uid):
    """Возвращает приоритет ранга юзера. Владелец = 9999."""
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT username,rank_id FROM users WHERE id=$1",uid)
        if not row: return 0
        if row["username"]==ADMIN_USERNAME: return 9999
        if not row["rank_id"]: return 0
        r=await conn.fetchrow("SELECT priority FROM ranks WHERE id=$1",row["rank_id"])
        return r["priority"] if r else 0

async def am_i_owner(user):
    return bool(user and user.get("username")==ADMIN_USERNAME)

# ============ ОБЫЧНАЯ АДМИНКА ============
@app.post("/api/admin/verify")
async def admin_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
    if not (perms.get("admin_panel") or perms.get("owner_panel")):
        raise HTTPException(403,"Нет доступа")
    pw=data.get("password") or ""
    if pw!=OWNER_PASSWORD: raise HTTPException(403,"Неверный пароль")
    return {"ok":True}

@app.get("/api/admin/users")
async def admin_users(token:str,limit:int=500):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("admin_panel") or perms.get("owner_panel")):
            raise HTTPException(403,"Нет доступа")
        rows=await conn.fetch("SELECT id,username,display_name,is_admin,is_moderator,is_scam,is_banned,coins,candy,level,title,rank_id FROM users WHERE id!=0 ORDER BY id LIMIT $1",limit)
    return {"users":[dict(r) for r in rows]}

@app.post("/api/admin/action")
async def admin_action(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
    tid=int(data.get("target_id",0) or data.get("user_id",0))
    action=data.get("action")
    if not tid: raise HTTPException(400,"target_id нужен")
    if action=="ban" and not perms.get("ban"): raise HTTPException(403,"Нет права ban")
    if action=="unban" and not perms.get("ban"): raise HTTPException(403,"Нет права ban")
    if action=="mute" and not perms.get("mute"): raise HTTPException(403,"Нет права mute")
    async with p.acquire() as conn:
        if action=="ban":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",data.get("reason",""),tid)
        elif action=="unban":
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",tid)
        elif action=="mute":
            d=int(data.get("duration",3600))
            await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",d,tid)
    await log_admin(user["id"],action,tid,data.get("reason",""))
    if action=="ban":
        await manager.send_to(tid,{"type":"banned","reason":data.get("reason","")})
        await manager.kick(tid)
    return {"ok":True}

@app.post("/api/admin/toggle_scam")
async def admin_toggle_scam(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("ban"): raise HTTPException(403,"Нет права")
    tid=int(data.get("target_id",0) or data.get("user_id",0))
    async with p.acquire() as conn:
        if not tid and data.get("username"):
            row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data["username"])
            if row: tid=row["id"]
        if not tid: raise HTTPException(404,"Не найден")
        cur=await conn.fetchval("SELECT is_scam FROM users WHERE id=$1",tid)
        new=not bool(cur)
        perms2=json.dumps(SCAM_DEFAULT_PERMS) if new else "{}"
        await conn.execute("UPDATE users SET is_scam=$1,scam_perms=$2 WHERE id=$3",new,perms2,tid)
    await manager.broadcast({"type":"user_updated","user_id":tid})
    return {"ok":True,"is_scam":new}

# ============ ЛОГИ ============
@app.get("/api/owner/logs")
async def owner_logs(token:str,limit:int=200):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT al.id,al.action,al.target_id,al.details,al.created_at,
            u.username AS admin_username,u.display_name AS admin_display,
            t.username AS target_username
            FROM admin_logs al
            LEFT JOIN users u ON u.id=al.admin_id
            LEFT JOIN users t ON t.id=al.target_id
            ORDER BY al.id DESC LIMIT $1""",limit)
    return [{"id":r["id"],"admin":r["admin_display"] or r["admin_username"] or "?",
             "action":r["action"],"target":r["target_username"] or r["target_id"],
             "details":r["details"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/owner/logs/clear")
async def owner_logs_clear(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM admin_logs")
    return {"ok":True}

# ============ РАНГИ (полная система) ============
ALL_RANK_PERMS=[
    "owner_panel","admin_panel","manage_ranks","manage_users","manage_shop",
    "manage_cosmetics","broadcast","give_coins","take_coins","give_candy",
    "ban","mute","delete_msgs","bypass_limits","verified","custom_title",
    "give_gifts","give_premium","manage_games","spy","force_logout","global_theme"
]

@app.get("/api/owner/ranks/perms_list")
async def ranks_perms_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
    if not (perms.get("manage_ranks") or perms.get("owner_panel")):
        raise HTTPException(403,"Нет права")
    return {"perms":ALL_RANK_PERMS}

@app.get("/api/owner/ranks/list")
async def ranks_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("manage_ranks") or perms.get("owner_panel")):
            raise HTTPException(403,"Нет права")
        rows=await conn.fetch("SELECT * FROM ranks ORDER BY priority DESC,id")
        out=[]
        for r in rows:
            cnt=await conn.fetchval("SELECT COUNT(*) FROM users WHERE rank_id=$1",r["id"])
            out.append({"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],
                        "priority":r["priority"],"perms":_safe_json(r["perms"],{}),"users_count":cnt})
    return {"ranks":out}

@app.get("/api/owner/ranks/get")
async def ranks_get(id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("manage_ranks") or perms.get("owner_panel")):
            raise HTTPException(403,"Нет права")
        r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",id)
        if not r: raise HTTPException(404,"Нет ранга")
    return {"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],
            "priority":r["priority"],"perms":_safe_json(r["perms"],{})}

@app.post("/api/owner/ranks/create")
async def ranks_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    is_owner=await am_i_owner(user)
    my_prio=await get_my_rank_priority(user["id"])
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет права")
        name=(data.get("name") or "").strip()[:64]
        if not name: raise HTTPException(400,"Название нужно")
        emoji=(data.get("emoji") or "🏆")[:8]
        color=(data.get("color") or "#d946ef")[:32]
        priority=int(data.get("priority",10))
        if not is_owner and priority>my_prio:
            raise HTTPException(403,f"Твой приоритет {my_prio}, не можешь создать выше")
        rp=data.get("perms") or {}
        if not isinstance(rp,dict): rp={}
        clean={k:bool(v) for k,v in rp.items() if k in ALL_RANK_PERMS}
        if not is_owner:
            clean.pop("owner_panel",None)
        r=await conn.fetchrow("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5) RETURNING id",
            name,emoji,color,priority,json.dumps(clean))
    await log_admin(user["id"],"rank_create",r["id"],name)
    return {"ok":True,"id":r["id"]}

@app.post("/api/owner/ranks/edit")
async def ranks_edit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    is_owner=await am_i_owner(user)
    my_prio=await get_my_rank_priority(user["id"])
    rid=int(data.get("id",0))
    if not rid: raise HTTPException(400,"id нужен")
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет права")
        old=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not old: raise HTTPException(404,"Нет ранга")
        if not is_owner and old["priority"]>my_prio:
            raise HTTPException(403,"Не можешь редактировать ранг выше себя")
        name=(data.get("name") or old["name"]).strip()[:64]
        emoji=(data.get("emoji") or old["emoji"])[:8]
        color=(data.get("color") or old["color"])[:32]
        priority=int(data.get("priority",old["priority"]))
        if not is_owner and priority>my_prio:
            raise HTTPException(403,"Приоритет выше твоего")
        rp=data.get("perms") or {}
        if not isinstance(rp,dict): rp={}
        clean={k:bool(v) for k,v in rp.items() if k in ALL_RANK_PERMS}
        if not is_owner: clean.pop("owner_panel",None)
        await conn.execute("UPDATE ranks SET name=$1,emoji=$2,color=$3,priority=$4,perms=$5 WHERE id=$6",
            name,emoji,color,priority,json.dumps(clean),rid)
    await log_admin(user["id"],"rank_edit",rid,name)
    return {"ok":True}

@app.post("/api/owner/ranks/delete")
async def ranks_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    is_owner=await am_i_owner(user)
    my_prio=await get_my_rank_priority(user["id"])
    rid=int(data.get("id",0))
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет права")
        old=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not old: raise HTTPException(404,"Нет ранга")
        if not is_owner and old["priority"]>my_prio:
            raise HTTPException(403,"Не можешь удалять ранг выше себя")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if cnt<=1: raise HTTPException(400,"Нельзя удалить последний ранг")
        await conn.execute("UPDATE users SET rank_id=NULL WHERE rank_id=$1",rid)
        await conn.execute("DELETE FROM ranks WHERE id=$1",rid)
    await log_admin(user["id"],"rank_delete",rid,old["name"])
    return {"ok":True}

@app.post("/api/owner/ranks/assign")
async def ranks_assign(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    is_owner=await am_i_owner(user)
    my_prio=await get_my_rank_priority(user["id"])
    uid=int(data.get("user_id",0))
    rid=int(data.get("rank_id",0))
    if not uid: raise HTTPException(400,"user_id нужен")
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет права")
        target=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",uid)
        if not target: raise HTTPException(404,"Юзер не найден")
        if rid<=0:
            if target["username"]==ADMIN_USERNAME and not is_owner:
                raise HTTPException(403,"Нельзя снять ранг с владельца")
            await conn.execute("UPDATE users SET rank_id=NULL WHERE id=$1",uid)
            await log_admin(user["id"],"rank_unassign",uid)
            await manager.send_to(uid,{"type":"rank_changed","rank":None})
            return {"ok":True,"rank_id":None}
        r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Нет ранга")
        if not is_owner and r["priority"]>my_prio:
            raise HTTPException(403,f"Твой приоритет {my_prio}, не можешь выдать выше")
        await conn.execute("UPDATE users SET rank_id=$1 WHERE id=$2",rid,uid)
    await log_admin(user["id"],"rank_assign",uid,f"{target['username']} → {r['name']}")
    await manager.send_to(uid,{"type":"rank_changed","rank":{"id":rid,"name":r["name"],"emoji":r["emoji"],"color":r["color"]}})
    return {"ok":True,"rank_id":rid}

@app.post("/api/owner/ranks/assign_mass")
async def ranks_assign_mass(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    is_owner=await am_i_owner(user)
    my_prio=await get_my_rank_priority(user["id"])
    uids=data.get("user_ids") or []
    if not isinstance(uids,list): raise HTTPException(400,"user_ids список")
    rid=int(data.get("rank_id",0))
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет права")
        if rid>0:
            r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
            if not r: raise HTTPException(404,"Нет ранга")
            if not is_owner and r["priority"]>my_prio:
                raise HTTPException(403,"Ранг выше твоего")
            for uid in uids:
                try:
                    await conn.execute("UPDATE users SET rank_id=$1 WHERE id=$2",rid,int(uid))
                except: pass
        else:
            for uid in uids:
                try:
                    await conn.execute("UPDATE users SET rank_id=NULL WHERE id=$1",int(uid))
                except: pass
    await log_admin(user["id"],"rank_assign_mass",rid,f"{len(uids)} юзеров")
    return {"ok":True,"count":len(uids)}

@app.post("/api/owner/ranks/users")
async def ranks_users(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("manage_ranks") or perms.get("admin_panel")):
            raise HTTPException(403,"Нет права")
        rid=int(data.get("rank_id",0))
        if rid<=0:
            rows=await conn.fetch("SELECT id,username,display_name FROM users WHERE rank_id IS NULL AND id!=0 ORDER BY id LIMIT 200")
        else:
            rows=await conn.fetch("SELECT id,username,display_name FROM users WHERE rank_id=$1 ORDER BY id LIMIT 200",rid)
    return {"users":[dict(r) for r in rows]}

# ============ ВЫДАТЬ ЛЮБОЙ РАНГ (BOG-ONLY) ============
@app.post("/api/owner/ranks/godmode_assign")
async def ranks_godmode_assign(data:dict):
    """BOG выдаёт любой ранг любому юзеру без ограничений."""
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    uid=int(data.get("user_id",0))
    rid=int(data.get("rank_id",0))
    if not uid: raise HTTPException(400,"user_id нужен")
    async with p.acquire() as conn:
        target=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",uid)
        if not target: raise HTTPException(404,"Юзер не найден")
        if rid<=0:
            await conn.execute("UPDATE users SET rank_id=NULL WHERE id=$1",uid)
            return {"ok":True,"rank_id":None}
        r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Нет ранга")
        await conn.execute("UPDATE users SET rank_id=$1 WHERE id=$2",rid,uid)
    await log_admin(user["id"],"GODMODE_rank_assign",uid,f"{target['username']} → {r['name']}")
    await manager.send_to(uid,{"type":"rank_changed","rank":{"id":rid,"name":r["name"],"emoji":r["emoji"],"color":r["color"]}})
    return {"ok":True,"rank_id":rid}

# ============ НАЗНАЧЕНИЕ АВТО-РАНГОВ (по условию) ============
@app.post("/api/owner/ranks/auto_add")
async def ranks_auto_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    cond_type=(data.get("condition_type") or "").strip()
    cond_value=int(data.get("condition_value",0))
    rid=int(data.get("rank_id",0))
    if cond_type not in ("messages","level","friends","days","coins"): raise HTTPException(400,"Тип условия")
    if not rid: raise HTTPException(400,"rank_id")
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO system_settings(key,value,updated_at) VALUES($1,$2,NOW())
            ON CONFLICT (key) DO UPDATE SET value=$2,updated_at=NOW()""",
            f"autorank_{cond_type}_{rid}",json.dumps({"rank_id":rid,"type":cond_type,"value":cond_value}))
    return {"ok":True}

@app.get("/api/owner/ranks/auto_list")
async def ranks_auto_list(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT key,value FROM system_settings WHERE key LIKE 'autorank_%'")
    out=[]
    for r in rows:
        try:
            d=json.loads(r["value"])
            rk=await conn.fetchrow("SELECT name,emoji,color FROM ranks WHERE id=$1",d["rank_id"]) if False else None
            out.append({"key":r["key"],"rank_id":d.get("rank_id"),"type":d.get("type"),"value":d.get("value")})
        except: pass
    return {"rules":out}

@app.post("/api/owner/ranks/auto_delete")
async def ranks_auto_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    key=(data.get("key") or "").strip()
    if not key.startswith("autorank_"): raise HTTPException(400,"Плохой ключ")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM system_settings WHERE key=$1",key)
    return {"ok":True}

# ============ УПРАВЛЕНИЕ ЮЗЕРОМ ============
@app.get("/api/owner/user_full/{user_id}")
async def owner_user_full(user_id:int,token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE id=$1",user_id)
        if not row: raise HTTPException(404,"Нет юзера")
        perms,rank=await get_user_perms_full(conn,user_id)
        rank_users_cnt=0
        if row["rank_id"]:
            rank_users_cnt=await conn.fetchval("SELECT COUNT(*) FROM users WHERE rank_id=$1",row["rank_id"])
    pub=user_public(row,user_id)
    pub["perms"]=perms
    pub["rank"]=rank
    pub["rank_users_count"]=rank_users_cnt
    return pub

@app.post("/api/owner/user/edit")
async def owner_user_edit(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        fields=[]
        params=[]
        idx=1
        mapping={
            "display_name":"display_name","bio":"bio","title":"title","avatar":"avatar",
            "banner":"banner","coins":"coins","candy":"candy","level":"level","xp":"xp",
            "is_admin":"is_admin","is_moderator":"is_moderator","is_verified":"is_verified",
            "is_scam":"is_scam","is_banned":"is_banned","is_legend":"is_legend",
            "is_dev":"is_dev","is_streamer":"is_streamer","theme":"theme","font_size":"font_size",
        }
        for k,col in mapping.items():
            if k in data and data[k] is not None:
                fields.append(f"{col}=${idx}")
                params.append(data[k])
                idx+=1
        if not fields: raise HTTPException(400,"Нечего менять")
        params.append(uid)
        await conn.execute(f"UPDATE users SET {','.join(fields)} WHERE id=${idx}",*params)
    await log_admin(user["id"],"user_edit",uid,json.dumps({k:data[k] for k in mapping if k in data}))
    await manager.broadcast({"type":"user_updated","user_id":uid})
    return {"ok":True}

@app.post("/api/owner/user/set_password")
async def owner_user_set_password(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    new_pw=str(data.get("new_password") or "").strip()
    if not uid or len(new_pw)<4: raise HTTPException(400,"user_id и пароль ≥4")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET password_hash=$1 WHERE id=$2",hash_password(new_pw),uid)
    await log_admin(user["id"],"user_set_password",uid)
    return {"ok":True,"new_password":new_pw}

@app.post("/api/owner/user/change_username")
async def owner_user_change_username(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    new=sanitize_username(data.get("new_username") or "")
    if not uid or not new: raise HTTPException(400,"user_id и username")
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",new,uid)
        if exists: raise HTTPException(400,"Занято")
        await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,uid)
    await log_admin(user["id"],"user_change_username",uid,new)
    return {"ok":True,"username":new}

@app.post("/api/owner/user/clear_chats")
async def owner_user_clear_chats(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM dms WHERE from_user=$1 OR to_user=$1",uid)
    await manager.send_to(uid,{"type":"force_reload"})
    await log_admin(user["id"],"user_clear_chats",uid)
    return {"ok":True}

@app.post("/api/owner/user/force_theme")
async def owner_user_force_theme(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    theme=(data.get("theme") or "dark").strip()
    font=(data.get("font_size") or "md").strip()
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET theme=$1,font_size=$2 WHERE id=$3",theme,font,uid)
    await manager.send_to(uid,{"type":"force_theme","theme":theme,"font_size":font})
    await log_admin(user["id"],"user_force_theme",uid,f"{theme}/{font}")
    return {"ok":True}

@app.post("/api/owner/user/spy")
async def owner_user_spy(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    other=int(data.get("other_id",0))
    if not uid or not other: raise HTTPException(400,"user_id и other_id")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT d.id,d.text,d.file_url,d.created_at,d.from_user,u.username,u.display_name
            FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id DESC LIMIT 200""",uid,other)
    return {"messages":[{"id":r["id"],"text":r["text"],"file_url":r["file_url"],
             "created_at":_iso(r["created_at"]),"from_user":r["from_user"],
             "username":r["username"],"display_name":r["display_name"]} for r in rows]}

@app.post("/api/owner/user/send_as")
async def owner_user_send_as(data:dict):
    """BOG пишет от имени любого юзера."""
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    to_id=int(data.get("to_user",0))
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    if not uid or not to_id or not text: raise HTTPException(400,"user_id, to_user, text")
    p=await get_pool()
    async with p.acquire() as conn:
        sender=await conn.fetchrow("SELECT username,display_name,avatar,gif_avatar,title FROM users WHERE id=$1",uid)
        msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text) VALUES($1,$2,$3) RETURNING id,created_at",uid,to_id,text)
    payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,
        "username":sender["username"],"display_name":sender["display_name"],
        "avatar":sender["avatar"],"gif_avatar":sender["gif_avatar"],
        "text":text,"msg_kind":"text","created_at":_iso(msg["created_at"]),
        "title":sender["title"]}
    await manager.send_to(to_id,payload)
    await manager.send_to(uid,payload)
    await log_admin(user["id"],"GODMODE_send_as",uid,f"→ {to_id}")
    return {"ok":True}

@app.post("/api/owner/user/delete")
async def owner_user_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        target=await conn.fetchrow("SELECT username FROM users WHERE id=$1",uid)
        if not target: raise HTTPException(404,"Нет юзера")
        if target["username"]==ADMIN_USERNAME: raise HTTPException(400,"Себя нельзя")
        await conn.execute("DELETE FROM users WHERE id=$1",uid)
    try: await manager.kick(uid)
    except: pass
    await log_admin(user["id"],"user_delete",uid,target["username"])
    return {"ok":True}

@app.post("/api/owner/user/restore")
async def owner_user_restore(data:dict):
    """Разбан + снятие скама + снятие мьюта одной кнопкой."""
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_banned=FALSE,ban_reason=NULL,is_scam=FALSE,scam_perms='{}',mute_until=NULL WHERE id=$1",uid)
    await log_admin(user["id"],"user_restore",uid)
    await manager.send_to(uid,{"type":"you_are_unblocked","by_id":0})
    return {"ok":True}

# ============ МАССОВЫЕ ОПЕРАЦИИ (для всех) ============
@app.post("/api/owner/mass/give")
async def owner_mass_give(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    field=(data.get("field") or "").strip()
    amount=int(data.get("amount",0))
    if field not in ("coins","candy","xp","quest_points"): raise HTTPException(400,"field")
    if amount==0: raise HTTPException(400,"amount")
    p=await get_pool()
    async with p.acquire() as conn:
        if amount>0: await conn.execute(f"UPDATE users SET {field}={field}+$1 WHERE id!=0",amount)
        else: await conn.execute(f"UPDATE users SET {field}=GREATEST(0,{field}+$1) WHERE id!=0",amount)
    await log_admin(user["id"],"mass_give",0,f"{field} {amount}")
    await manager.broadcast({"type":"mass_give","field":field,"amount":amount})
    return {"ok":True}

@app.post("/api/owner/mass/set_premium")
async def owner_mass_set_premium(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    days=int(data.get("days",30))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=GREATEST(COALESCE(premium_expires,NOW()),NOW())+INTERVAL '1 day' * $1 WHERE id!=0",days)
    await log_admin(user["id"],"mass_premium",0,str(days))
    await manager.broadcast({"type":"mass_premium","days":days})
    return {"ok":True}

@app.post("/api/owner/mass/theme")
async def owner_mass_theme(data:dict):
    """Смена темы ВСЕМ одной кнопкой."""
    user=await get_current_user(data.get("token")); await check_owner(user)
    theme=(data.get("theme") or "dark").strip()
    font=(data.get("font_size") or "").strip()
    if theme not in ("dark","light","amoled"): raise HTTPException(400,"theme")
    p=await get_pool()
    async with p.acquire() as conn:
        if font:
            await conn.execute("UPDATE users SET theme=$1,font_size=$2 WHERE id!=0",theme,font)
        else:
            await conn.execute("UPDATE users SET theme=$1 WHERE id!=0",theme)
    payload={"type":"force_theme","theme":theme}
    if font: payload["font_size"]=font
    await manager.broadcast(payload)
    await log_admin(user["id"],"mass_theme",0,f"{theme}/{font}")
    return {"ok":True}

@app.post("/api/owner/mass/notif")
async def owner_mass_notif(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    enabled=bool(data.get("enabled",True))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET notif_enabled=$1 WHERE id!=0",enabled)
    await log_admin(user["id"],"mass_notif",0,str(enabled))
    return {"ok":True}

@app.post("/api/owner/mass/sound")
async def owner_mass_sound(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    enabled=bool(data.get("enabled",True))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET sound_enabled=$1 WHERE id!=0",enabled)
    await log_admin(user["id"],"mass_sound",0,str(enabled))
    return {"ok":True}

@app.post("/api/owner/mass/airplane")
async def owner_mass_airplane(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    enabled=bool(data.get("enabled",False))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET airplane_mode=$1 WHERE id!=0",enabled)
    await manager.broadcast({"type":"force_airplane","enabled":enabled})
    await log_admin(user["id"],"mass_airplane",0,str(enabled))
    return {"ok":True}

# ============ LIVE ============
@app.get("/api/owner/live")
async def owner_live(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    online_ids=list(online_users)
    users_info=[]
    if online_ids:
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,username,display_name,avatar,gif_avatar FROM users WHERE id=ANY($1::int[])",online_ids)
            users_info=[dict(r) for r in rows]
    active_call_ids=[]
    for cid,c in active_calls.items():
        active_call_ids.append({"call_id":cid,"caller":c["caller"],"callee":c["callee"],"type":c["type"]})
    return {"online_count":len(online_users),"online_users":users_info,
            "active_calls":active_call_ids,"call_count":len(active_call_ids)}

# ============ КОНЕЦ ЧАСТИ 2a ============
# ============================================================
# BELUGACORD 3.3 — ЧАСТЬ 2b — ФИНАЛ
# ============================================================

# ============ СИСТЕМНЫЕ НАСТРОЙКИ САЙТА ============
DEFAULT_SITE_SETTINGS={
    "site_name":"BelugaCord",
    "site_subtitle":"Мессенджер для посёлка",
    "site_icon":"🐱",
    "site_logo_url":"",
    "site_rules":"1. Будь вежлив\n2. Без спама\n3. Без скама\n4. Уважай других",
    "welcome_message":"Добро пожаловать в BelugaCord! 🐱",
    "support_link":"",
    "donate_link":"",
    "telegram_link":"",
    "max_message_length":10000,
    "max_file_size_mb":50,
    "rate_limit_per_min":60,
    "registration_open":True,
    "maintenance_mode":False,
    "maintenance_text":"🛠️ Тех.работы. Скоро вернёмся!",
    "features":{
        "calls":True,"dm":True,"registration":True,"games":True,
        "shop":True,"gifts":True,"bp":True,"premium":True,
        "file_upload":True,"voice":True,"groups":True,"servers":True
    }
}

async def get_site_settings():
    p=await get_pool()
    out=dict(DEFAULT_SITE_SETTINGS)
    try:
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT key,value FROM system_settings WHERE key LIKE 'site_%'")
            for r in rows:
                k=r["key"].replace("site_","",1)
                try:
                    v=json.loads(r["value"])
                    if k=="features" and isinstance(v,dict):
                        out["features"]={**out["features"],**v}
                    else:
                        out[k]=v
                except:
                    out[k]=r["value"]
    except: pass
    return out

async def save_site_setting(key,value):
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO system_settings(key,value,updated_at) VALUES($1,$2,NOW())
            ON CONFLICT (key) DO UPDATE SET value=$2,updated_at=NOW()""",
            f"site_{key}",json.dumps(value) if not isinstance(value,str) else value)

@app.get("/api/site/settings")
async def site_settings():
    return await get_site_settings()

@app.post("/api/owner/site/update")
async def owner_site_update(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    allowed={"site_name","site_subtitle","site_icon","site_logo_url","site_rules",
             "welcome_message","support_link","donate_link","telegram_link",
             "max_message_length","max_file_size_mb","rate_limit_per_min",
             "registration_open","maintenance_mode","maintenance_text"}
    updated=[]
    for k,v in (data.get("settings") or {}).items():
        if k in allowed:
            await save_site_setting(k,v)
            updated.append(k)
    await log_admin(user["id"],"site_update",0,",".join(updated))
    await manager.broadcast({"type":"site_updated","fields":updated})
    return {"ok":True,"updated":updated}

@app.post("/api/owner/site/feature")
async def owner_site_feature(data:dict):
    """Включить/выключить глобальную фичу."""
    user=await get_current_user(data.get("token")); await check_owner(user)
    feat=(data.get("feature") or "").strip()
    enabled=bool(data.get("enabled",True))
    cur=await get_site_settings()
    feats=cur.get("features",{})
    if feat not in feats: raise HTTPException(400,"Нет такой фичи")
    feats[feat]=enabled
    await save_site_setting("features",feats)
    await log_admin(user["id"],"feature_toggle",0,f"{feat}={enabled}")
    await manager.broadcast({"type":"feature_toggle","feature":feat,"enabled":enabled})
    return {"ok":True}

@app.get("/api/site/features")
async def site_features():
    s=await get_site_settings()
    return {"features":s.get("features",{}),"maintenance":s.get("maintenance_mode",False),
            "maintenance_text":s.get("maintenance_text",""),"registration_open":s.get("registration_open",True)}

# ============ ГЛОБАЛЬНЫЕ ТЕМЫ И ФИЧИ ============
@app.post("/api/owner/global/theme")
async def owner_global_theme(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    theme=(data.get("theme") or "dark").strip()
    font=(data.get("font_size") or "").strip()
    if theme not in ("dark","light","amoled"): raise HTTPException(400,"theme")
    p=await get_pool()
    async with p.acquire() as conn:
        if font:
            await conn.execute("UPDATE users SET theme=$1,font_size=$2 WHERE id!=0",theme,font)
        else:
            await conn.execute("UPDATE users SET theme=$1 WHERE id!=0",theme)
    payload={"type":"force_theme","theme":theme}
    if font: payload["font_size"]=font
    await manager.broadcast(payload)
    await log_admin(user["id"],"global_theme",0,f"{theme}/{font}")
    return {"ok":True}

@app.get("/api/owner/global/features")
async def owner_global_features(token:str):
    user=await get_current_user(token); await check_owner(user)
    return await get_site_settings()

# ============ ИВЕНТЫ ============
@app.get("/api/owner/events/list")
async def owner_events_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("owner_panel") or perms.get("admin_panel")):
            raise HTTPException(403,"Нет права")
        rows=await conn.fetch("SELECT * FROM system_settings WHERE key LIKE 'event_%'")
    events=[];now=datetime.datetime.now(datetime.timezone.utc)
    for r in rows:
        try:
            d=json.loads(r["value"])
            ea=_aware(d.get("ends_at"))
            if ea and ea>now:
                events.append({"id":d.get("id"),"name":d.get("name"),"emoji":d.get("emoji"),"ends_at":_iso(ea)})
        except: pass
    return {"events":events}

@app.post("/api/owner/events/start")
async def owner_events_start(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    eid=(data.get("event_id") or "").strip()
    minutes=int(data.get("minutes",60))
    names={"x2xp":("x2 XP","✨"),"x2coins":("x2 Беккоины","🏅"),"x2candy":("x2 Конфеты","🍬"),
           "discount50":("Скидка 50%","🏷️"),"freeGift":("Всем подарок","🎁"),"randomDrop":("Случайный дроп","🎲")}
    if eid not in names: raise HTTPException(400,"Нет ивента")
    name,emoji=names[eid]
    ends=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=minutes)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO system_settings(key,value,updated_at) VALUES($1,$2,NOW())
            ON CONFLICT (key) DO UPDATE SET value=$2,updated_at=NOW()""",
            f"event_{eid}",json.dumps({"id":eid,"name":name,"emoji":emoji,"ends_at":ends.isoformat()}))
        if eid=="x2xp":
            await conn.execute("UPDATE users SET double_xp_until=NOW()+INTERVAL '1 minute' * $1 WHERE id!=0",minutes)
    await manager.broadcast({"type":"event_started","id":eid,"name":name,"emoji":emoji,"ends_at":ends.isoformat()})
    await log_admin(user["id"],"event_start",0,f"{eid} {minutes}м")
    return {"ok":True}

@app.post("/api/owner/events/stop")
async def owner_events_stop(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    eid=(data.get("event_id") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        if eid: await conn.execute("DELETE FROM system_settings WHERE key=$1",f"event_{eid}")
        else: await conn.execute("DELETE FROM system_settings WHERE key LIKE 'event_%'")
    await manager.broadcast({"type":"events_stopped","id":eid})
    return {"ok":True}

# ============ CRUD МАГАЗИН / КЕЙСЫ / ПОДАРКИ ============
@app.get("/api/owner/shop/list")
async def owner_shop_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("manage_shop") or perms.get("owner_panel")):
            raise HTTPException(403,"Нет права")
        rows=await conn.fetch("SELECT * FROM custom_gifts ORDER BY id DESC")
    return {"items":[{"id":r["gift_id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"]} for r in rows]}

@app.post("/api/owner/shop/add")
async def owner_shop_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название")
    gid=sanitize_username(name)[:32]
    price=int(data.get("price",100))
    emoji=(data.get("emoji") or "🎁")[:8]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO custom_gifts(gift_id,name,emoji,price) VALUES($1,$2,$3,$4)
            ON CONFLICT (gift_id) DO UPDATE SET name=$2,emoji=$3,price=$4""",gid,name,emoji,price)
    await log_admin(user["id"],"shop_add",0,name)
    return {"ok":True,"id":gid}

@app.post("/api/owner/shop/edit")
async def owner_shop_edit(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    gid=(data.get("id") or "").strip()
    if not gid: raise HTTPException(400,"id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE custom_gifts SET name=$1,emoji=$2,price=$3 WHERE gift_id=$4",
            (data.get("name") or "").strip()[:64],(data.get("emoji") or "🎁")[:8],int(data.get("price",100)),gid)
    return {"ok":True}

@app.post("/api/owner/shop/delete")
async def owner_shop_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_gifts WHERE gift_id=$1",str(data.get("id","")))
    return {"ok":True}

@app.post("/api/owner/shop/clear")
async def owner_shop_clear(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_gifts")
    return {"ok":True}

# ============ КЕЙСЫ ============
@app.post("/api/owner/cases/add")
async def owner_cases_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO cases(name,emoji,price,is_active) VALUES($1,$2,$3,TRUE) RETURNING id",
            name,(data.get("emoji") or "📦")[:8],int(data.get("price",500)))
    return {"ok":True,"id":r["id"]}

@app.post("/api/owner/cases/delete")
async def owner_cases_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM cases WHERE id=$1",int(data.get("id",0)))
    return {"ok":True}

@app.get("/api/owner/cases/list")
async def owner_cases_list(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM cases ORDER BY id DESC")
    return {"items":[dict(r) for r in rows]}

@app.post("/api/owner/cases/multiplier")
async def owner_cases_multiplier(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    value=float(data.get("value",1.0))
    await save_site_setting("case_multiplier",str(value))
    return {"ok":True}

# ============ КОСМЕТИКА ============
@app.post("/api/owner/cosmetics/title/add")
async def owner_cosm_title_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("""INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value,creator_id)
            VALUES($1,$2,$3,TRUE,'free',0,$4) RETURNING id""",
            name,(data.get("emoji") or "⭐")[:8],(data.get("color") or "#d946ef")[:32],user["id"])
    return {"ok":True,"id":r["id"]}

@app.post("/api/owner/cosmetics/title/delete")
async def owner_cosm_title_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM titles_catalog WHERE id=$1",int(data.get("id",0)))
    return {"ok":True}

@app.post("/api/owner/cosmetics/frame/add")
async def owner_cosm_frame_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название")
    fid=sanitize_username(name)[:32]
    price=int(data.get("price",500))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO frames_catalog(frame_id,name,emoji,price_coins) VALUES($1,$2,$3,$4)
            ON CONFLICT (frame_id) DO UPDATE SET name=$2,emoji=$3,price_coins=$4""",
            fid,name,(data.get("emoji") or "🎨")[:8],price)
    return {"ok":True,"frame_id":fid}

@app.post("/api/owner/cosmetics/frame/delete")
async def owner_cosm_frame_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM frames_catalog WHERE frame_id=$1",str(data.get("id","")))
    return {"ok":True}

# ============ СЕРВЕРЫ / КАНАЛЫ / ГРУППЫ CRUD ============
@app.get("/api/owner/servers/list")
async def owner_servers_list(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT s.*,u.username AS owner_name FROM servers s LEFT JOIN users u ON u.id=s.owner_id ORDER BY s.id DESC")
    return {"servers":[dict(r) for r in rows]}

@app.post("/api/owner/servers/delete")
async def owner_servers_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM servers WHERE id=$1",int(data.get("id",0)))
    return {"ok":True}

@app.get("/api/owner/groups/list")
async def owner_groups_list(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.*,u.username AS owner_name FROM groups g LEFT JOIN users u ON u.id=g.owner_id ORDER BY g.id DESC")
    return {"groups":[dict(r) for r in rows]}

@app.post("/api/owner/groups/delete")
async def owner_groups_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM groups WHERE id=$1",int(data.get("id",0)))
    return {"ok":True}

# ============ РАССЫЛКИ ============
@app.post("/api/owner/broadcast/all")
async def owner_broadcast_all(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    from_name=(data.get("from_name") or "📢 Система").strip()[:64]
    if not text: raise HTTPException(400,"Текст")
    payload={"type":"abuse_announce","username":from_name,"avatar":"","text":text}
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,payload); sent+=1
        except: pass
    await log_admin(user["id"],"broadcast_all",0,text[:100])
    return {"ok":True,"sent":sent}

@app.post("/api/owner/broadcast/system")
async def owner_broadcast_system(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    if not text: raise HTTPException(400,"Текст")
    payload={"type":"abuse_announce","username":"🤖 Система","avatar":"","text":text}
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,payload)
        except: pass
    return {"ok":True}

@app.post("/api/owner/broadcast/user")
async def owner_broadcast_user(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    if not text: raise HTTPException(400,"Текст")
    await manager.send_to(t["id"],{"type":"abuse_announce","username":"👑 Владелец","avatar":"","text":text})
    return {"ok":True}

@app.post("/api/owner/broadcast/maintenance")
async def owner_broadcast_maintenance(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    text=(data.get("text") or "").strip()[:500]
    await save_site_setting("maintenance_text",text)
    await save_site_setting("maintenance_mode",True)
    await manager.broadcast({"type":"maintenance","text":text})
    return {"ok":True}

# ============ СИСТЕМА ============
@app.post("/api/owner/system/hot_reload")
async def owner_system_hot_reload(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,{"type":"force_reload"}); sent+=1
        except: pass
    await log_admin(user["id"],"hot_reload",0,str(sent))
    return {"ok":True,"sent":sent}

@app.post("/api/owner/system/clear_cache")
async def owner_system_clear_cache(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    await manager.broadcast({"type":"clear_cache"})
    return {"ok":True}

@app.post("/api/owner/system/maintenance")
async def owner_system_maintenance(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    enabled=bool(data.get("enabled",False))
    text=(data.get("text") or "").strip()[:500]
    await save_site_setting("maintenance_mode",enabled)
    if text: await save_site_setting("maintenance_text",text)
    await manager.broadcast({"type":"maintenance","enabled":enabled,"text":text})
    return {"ok":True}

@app.post("/api/owner/system/backup")
async def owner_system_backup(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    stats={}
    async with p.acquire() as conn:
        for tbl in ["users","messages","dms","gifts","servers","groups","ranks"]:
            try: stats[tbl]=await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")
            except: pass
    return {"ok":True,"tables":stats,"time":_iso(datetime.datetime.now(datetime.timezone.utc))}

@app.post("/api/owner/system/delete_all_msgs")
async def owner_system_delete_all_msgs(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages")
        await conn.execute("DELETE FROM dms")
        await conn.execute("DELETE FROM group_messages")
    await manager.broadcast({"type":"force_reload"})
    await log_admin(user["id"],"delete_all_msgs",0)
    return {"ok":True}

@app.post("/api/owner/system/reset_economy")
async def owner_system_reset_economy(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=0,candy=0,xp=0,level=1 WHERE id!=0")
    await manager.broadcast({"type":"force_reload"})
    return {"ok":True}

# ============ ДАШБОРД / СТАТИСТИКА ============
@app.get("/api/owner/stats")
async def owner_stats(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        m=await conn.fetchval("SELECT COUNT(*) FROM messages")
        c=await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        g=await conn.fetchval("SELECT COUNT(*) FROM gifts")
        scam=await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_scam=TRUE")
        prem=await conn.fetchval("SELECT COUNT(*) FROM users WHERE premium_tier IS NOT NULL")
        dms=await conn.fetchval("SELECT COUNT(*) FROM dms")
        srv=await conn.fetchval("SELECT COUNT(*) FROM servers")
        grp=await conn.fetchval("SELECT COUNT(*) FROM groups")
        rnk=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        try: calls=await conn.fetchval("SELECT COUNT(*) FROM call_history")
        except: calls=0
    return {"users":u,"messages":m,"coins":c,"gifts":g,"online":len(online_users),
            "scam_count":scam,"premium":prem,"dms":dms,"servers":srv,"groups":grp,
            "ranks":rnk,"calls":calls}

@app.get("/api/owner/full_stats")
async def owner_full_stats(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        users=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        msgs=await conn.fetchval("SELECT COUNT(*) FROM messages")
        dms_c=await conn.fetchval("SELECT COUNT(*) FROM dms")
        coins=await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        gifts=await conn.fetchval("SELECT COUNT(*) FROM gifts")
        premium=await conn.fetchval("SELECT COUNT(*) FROM users WHERE premium_tier IS NOT NULL")
        new_today=await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '1 day'")
        try: calls=await conn.fetchval("SELECT COUNT(*) FROM call_history")
        except: calls=0
        top=await conn.fetch("SELECT username,messages_count FROM users WHERE id!=0 ORDER BY messages_count DESC LIMIT 10")
    return {"users":users,"online":len(online_users),"messages":msgs+dms_c,
            "coins_total":coins,"gifts":gifts,"premium":premium,"new_today":new_today,
            "calls":calls,"top_users":[{"username":r["username"],"messages":r["messages_count"]} for r in top]}

# ============ АНОНС ОТ БОГА (совместимость) ============
@app.post("/api/owner/announce_full")
async def owner_announce_full(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    username=(data.get("username") or user["username"])[:32]
    avatar=(data.get("avatar") or user.get("avatar") or "")
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    if not text: raise HTTPException(400,"Пусто")
    payload={"type":"abuse_announce","username":username,"avatar":avatar,"text":text}
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,payload); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

# ============ ХЕЛПЕРЫ ДЛЯ OWNER ============
@app.post("/api/owner/give_coins")
async def owner_give_coins(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,t["id"])
    await log_admin(user["id"],"give_coins",t["id"],str(amt))
    return {"ok":True}

@app.post("/api/owner/take_coins")
async def owner_take_coins(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins=GREATEST(0,coins-$1) WHERE id=$2",amt,t["id"])
    return {"ok":True}

@app.post("/api/owner/give_candy")
async def owner_give_candy(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",50))
        await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",amt,t["id"])
    await manager.send_to(t["id"],{"type":"candy_received","amount":amt})
    return {"ok":True}

@app.post("/api/owner/give_all")
async def owner_give_all(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    amt=int(data.get("amount",100))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id!=0",amt)
    await manager.broadcast({"type":"coins_approved","amount":amt})
    return {"ok":True}

@app.post("/api/owner/give_premium")
async def owner_give_premium(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    days=int(data.get("days",30))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",days,t["id"])
    return {"ok":True}

@app.post("/api/owner/mute")
async def owner_mute(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    minutes=int(data.get("minutes",60))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 minute' * $1 WHERE id=$2",minutes,t["id"])
    await manager.send_to(t["id"],{"type":"muted","reason":f"Мут {minutes} мин"})
    return {"ok":True}

@app.post("/api/owner/unmute")
async def owner_unmute(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET mute_until=NULL WHERE id=$1",t["id"])
    return {"ok":True}

@app.post("/api/owner/reset_pass")
async def owner_reset_pass(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    new_pw=str(data.get("new_password") or "beluga123")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET password_hash=$1 WHERE id=$2",hash_password(new_pw),t["id"])
    return {"ok":True,"new_password":new_pw}

@app.post("/api/owner/change_nick")
async def owner_change_nick(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    new=sanitize_username(data.get("new_username") or "")
    if not new: raise HTTPException(400,"Ник")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        exists=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",new,t["id"])
        if exists: raise HTTPException(400,"Занято")
        await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,t["id"])
        if data.get("new_display_name"):
            await conn.execute("UPDATE users SET display_name=$1 WHERE id=$2",str(data["new_display_name"])[:64],t["id"])
    return {"ok":True,"new_username":new}

@app.post("/api/owner/force_logout")
async def owner_force_logout(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
    await manager.send_to(t["id"],{"type":"force_logout"})
    await manager.kick(t["id"])
    return {"ok":True}

@app.post("/api/owner/grant_admin")
async def owner_grant_admin(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE id=$1",t["id"])
    return {"ok":True}

@app.post("/api/owner/revoke_admin")
async def owner_revoke_admin(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("UPDATE users SET is_admin=FALSE WHERE id=$1",t["id"])
    return {"ok":True}

@app.post("/api/owner/level_up")
async def owner_level_up(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        levels=int(data.get("levels",1))
        await conn.execute("UPDATE users SET level=level+$1 WHERE id=$2",levels,t["id"])
    return {"ok":True}

@app.post("/api/owner/give_title")
async def owner_give_title(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        title=(data.get("title") or "")[:64]
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",title,t["id"])
    return {"ok":True}

@app.post("/api/owner/give_frame")
async def owner_give_frame(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        fid=(data.get("frame_id") or "").strip()
        row=await conn.fetchrow("SELECT frame_owned FROM users WHERE id=$1",t["id"])
        owned=_safe_json(row["frame_owned"],[])
        if fid and fid not in owned: owned.append(fid)
        await conn.execute("UPDATE users SET frame_owned=$1 WHERE id=$2",json.dumps(owned),t["id"])
    return {"ok":True}

@app.post("/api/owner/delete_user")
async def owner_delete_user(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Не найден")
        if t["username"]==ADMIN_USERNAME: raise HTTPException(400,"Себя нельзя")
        await conn.execute("DELETE FROM users WHERE id=$1",t["id"])
    try: await manager.kick(t["id"])
    except: pass
    return {"ok":True}

@app.post("/api/owner/delete_all_msgs")
async def owner_delete_all_msgs(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages")
        await conn.execute("DELETE FROM dms")
        await conn.execute("DELETE FROM group_messages")
    await manager.broadcast({"type":"force_reload"})
    return {"ok":True}

@app.post("/api/owner/hot_swap")
async def owner_hot_swap(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,{"type":"force_reload"}); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.get("/api/owner/online")
async def owner_online(token:str):
    user=await get_current_user(token); await check_owner(user)
    if not online_users: return {"users":[]}
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username,display_name FROM users WHERE id=ANY($1::int[])",list(online_users))
    return {"users":[dict(r) for r in rows]}

@app.post("/api/owner/holiday/force")
async def owner_holiday_force(data:dict):
    global forced_holiday
    user=await get_current_user(data.get("token")); await check_owner(user)
    hid=(data.get("holiday_id") or "").strip()
    if hid=="none" or not hid:
        forced_holiday=None
        await manager.broadcast({"type":"holiday_theme","holiday":None})
        return {"ok":True,"forced":None}
    h=next((x for x in HOLIDAYS if x[1]==hid),None)
    if not h: raise HTTPException(404,"Не найден")
    forced_holiday=hid
    payload={"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"forced":True}
    await manager.broadcast({"type":"holiday_theme","holiday":payload})
    return {"ok":True,"forced":payload}

# ============ SUPPORT ВЛАДЕЛЬЦА ============
@app.get("/api/support/all")
async def support_all(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT st.*,u.username AS from_username,u.display_name AS from_display,t.username AS target_username
            FROM support_tickets st LEFT JOIN users u ON u.id=st.from_user LEFT JOIN users t ON t.id=st.target_user
            ORDER BY st.status='pending' DESC, st.id DESC LIMIT 200""")
    return [{"id":r["id"],"from_username":r["from_username"],"target_username":r["target_username"],"ticket_type":r["ticket_type"],"title":r["title"],"description":r["description"],"evidence":r["evidence"],"status":r["status"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/support/resolve")
async def support_resolve(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    tid=int(data.get("ticket_id",0))
    action=(data.get("action") or "reject").strip()
    reply=(data.get("reply") or "")[:1000]
    if action not in ("approve","reject"): raise HTTPException(400,"approve/reject")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM support_tickets WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет заявки")
        await conn.execute("UPDATE support_tickets SET status=$1,admin_reply=$2,resolved_by=$3,resolved_at=NOW() WHERE id=$4","approved" if action=="approve" else "rejected",reply,user["id"],tid)
        if action=="approve" and t["ticket_type"]=="unscam" and t["from_user"]:
            await conn.execute("UPDATE users SET is_scam=FALSE,scam_perms='{}' WHERE id=$1",t["from_user"])
        if action=="approve" and t["ticket_type"]=="unban" and t["from_user"]:
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",t["from_user"])
        if action=="approve" and t["ticket_type"] in ("report_scam","report_spam") and t["target_user"]:
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",f"По жалобе #{tid}",t["target_user"])
            try: await manager.kick(t["target_user"])
            except: pass
    return {"ok":True}

# ============ КОМАНДНАЯ СТРОКА (BOG) ============
@app.post("/api/owner/console")
async def owner_console(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    cmd=(data.get("command") or "").strip()
    if not cmd: raise HTTPException(400,"Пусто")
    parts=cmd.split()
    if len(parts)<2: raise HTTPException(400,"Формат: give @user 100")
    action=parts[0].lower()
    p=await get_pool()
    try:
        if action=="give" and len(parts)>=3:
            target=parts[1].lstrip("@")
            amount=int(parts[2])
            field=parts[3] if len(parts)>3 else "coins"
            if field not in ("coins","candy","xp"): field="coins"
            async with p.acquire() as conn:
                if target.isdigit():
                    await conn.execute(f"UPDATE users SET {field}={field}+$1 WHERE id=$2",amount,int(target))
                else:
                    await conn.execute(f"UPDATE users SET {field}={field}+$1 WHERE username=$2",amount,target)
            return {"ok":True,"result":f"+{amount} {field} → @{target}"}
        if action=="take" and len(parts)>=3:
            target=parts[1].lstrip("@")
            amount=int(parts[2])
            field=parts[3] if len(parts)>3 else "coins"
            async with p.acquire() as conn:
                if target.isdigit():
                    await conn.execute(f"UPDATE users SET {field}=GREATEST(0,{field}-$1) WHERE id=$2",amount,int(target))
                else:
                    await conn.execute(f"UPDATE users SET {field}=GREATEST(0,{field}-$1) WHERE username=$2",amount,target)
            return {"ok":True,"result":f"-{amount} {field} от @{target}"}
        if action=="ban" and len(parts)>=2:
            target=parts[1].lstrip("@")
            async with p.acquire() as conn:
                if target.isdigit(): await conn.execute("UPDATE users SET is_banned=TRUE WHERE id=$1",int(target))
                else: await conn.execute("UPDATE users SET is_banned=TRUE WHERE username=$1",target)
            return {"ok":True,"result":f"🚫 @{target} забанен"}
        if action=="unban" and len(parts)>=2:
            target=parts[1].lstrip("@")
            async with p.acquire() as conn:
                if target.isdigit(): await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",int(target))
                else: await conn.execute("UPDATE users SET is_banned=FALSE WHERE username=$1",target)
            return {"ok":True,"result":f"✅ @{target} разбанен"}
        if action=="mute" and len(parts)>=3:
            target=parts[1].lstrip("@")
            minutes=int(parts[2])
            async with p.acquire() as conn:
                if target.isdigit(): await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 minute' * $1 WHERE id=$2",minutes,int(target))
                else: await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 minute' * $1 WHERE username=$2",minutes,target)
            return {"ok":True,"result":f"🔇 @{target} мут {minutes}м"}
        if action=="announce" and len(parts)>=2:
            text=" ".join(parts[1:])[:1000]
            for uid in list(manager.connections.keys()):
                try: await manager.send_to(uid,{"type":"abuse_announce","username":"👑 Владелец","avatar":"","text":text})
                except: pass
            return {"ok":True,"result":f"📢 Отправлено"}
        if action=="theme" and len(parts)>=2:
            theme=parts[1]
            if theme not in ("dark","light","amoled"): raise HTTPException(400,"Тема")
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET theme=$1 WHERE id!=0",theme)
            await manager.broadcast({"type":"force_theme","theme":theme})
            return {"ok":True,"result":f"🎨 Тема {theme} всем"}
        if action=="nick" and len(parts)>=3:
            target=parts[1].lstrip("@")
            new_nick=parts[2]
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2",new_nick,target)
            return {"ok":True,"result":f"✏️ @{target} → {new_nick}"}
        if action=="help":
            return {"ok":True,"result":"give @user 100 [coins/candy/xp] | take @user 50 | ban @user | unban @user | mute @user 60 | announce текст | theme dark | nick @user Новый"}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,f"Ошибка: {e}")
    raise HTTPException(400,"Неизвестная команда. help")

# ============ WEBSOCKET ============
@app.websocket("/ws")
async def websocket_endpoint(ws:WebSocket,token:str):
    user=await get_current_user(token)
    if not user: await ws.close(); return
    if user.get("is_banned"): await ws.close(); return
    uid=user["id"]
    await manager.connect(uid,ws)
    try: await ws.send_json({"type":"online_list","users":list(online_users)})
    except: pass
    await manager.broadcast({"type":"user_online","user_id":uid},exclude=uid)
    try:
        while True:
            raw=await ws.receive_text()
            try: data=json.loads(raw)
            except: continue
            t=data.get("type")
            if t=="ping":
                try: await ws.send_json({"type":"pong"})
                except: pass
                continue
            is_muted=False
            if user.get("mute_until"):
                try:
                    mu=_aware(user["mute_until"])
                    if mu and mu>datetime.datetime.now(datetime.timezone.utc): is_muted=True
                except: pass
            if t in ("message","dm","group_msg") and is_muted:
                await manager.send_to(uid,{"type":"muted","reason":"Ты в муте"})
                continue
            if t in ("message","dm","group_msg") and user.get("airplane_mode"):
                await manager.send_to(uid,{"type":"error","detail":"✈️ Режим полёта"})
                continue

            # ЗВОНКИ
            if t=="call_invite":
                to_id=int(data.get("to_user",0))
                call_type=data.get("call_type","audio")
                if not to_id: continue
                if user.get("is_scam") and not has_scam_perm(user,"call"):
                    await manager.send_to(uid,{"type":"call_error","reason":"SCAM"}); continue
                busy=False
                for cid,c in list(active_calls.items()):
                    if c["caller"]==uid or c["callee"]==uid or c["caller"]==to_id or c["callee"]==to_id: busy=True;break
                if busy:
                    await manager.send_to(uid,{"type":"call_busy","reason":"Занято"});continue
                call_id=secrets.token_hex(8)
                active_calls[call_id]={"caller":uid,"callee":to_id,"type":call_type,"started":time.time()}
                dn=user.get("display_name") or user["username"]
                await manager.send_to(to_id,{"type":"call_incoming","call_id":call_id,"from_user":uid,"from_name":dn,"from_avatar":user.get("avatar") or user.get("gif_avatar"),"call_type":call_type})
                await manager.send_to(uid,{"type":"call_ringing","call_id":call_id})
                await grant_achievement(uid,"first_call")
                await bp_add_progress(uid,"call",1)

            elif t=="call_accept":
                call_id=data.get("call_id")
                if call_id not in active_calls: continue
                c=active_calls[call_id]
                if c["callee"]!=uid: continue
                await manager.send_to(c["caller"],{"type":"call_accepted","call_id":call_id,"by_user":uid,"by_name":user.get("display_name") or user["username"]})

            elif t=="call_reject":
                call_id=data.get("call_id")
                if call_id in active_calls:
                    c=active_calls[call_id]
                    await manager.send_to(c["caller"],{"type":"call_rejected","call_id":call_id})
                    del active_calls[call_id]

            elif t=="call_cancel":
                call_id=data.get("call_id")
                if call_id in active_calls:
                    c=active_calls[call_id]
                    await manager.send_to(c["callee"],{"type":"call_cancelled","call_id":call_id})
                    del active_calls[call_id]

            elif t=="call_end":
                call_id=data.get("call_id")
                dur=int(data.get("duration",0))
                if call_id in active_calls:
                    c=active_calls[call_id]
                    other=c["callee"] if c["caller"]==uid else c["caller"]
                    await manager.send_to(other,{"type":"call_ended","call_id":call_id})
                    try:
                        p=await get_pool()
                        async with p.acquire() as conn:
                            await conn.execute("INSERT INTO call_history(call_id,caller,callee,call_type,status,duration) VALUES($1,$2,$3,$4,'ended',$5)",call_id,c["caller"],c["callee"],c["type"],dur)
                    except: pass
                    del active_calls[call_id]

            elif t in ("webrtc_offer","webrtc_answer","webrtc_ice"):
                to_id=int(data.get("to_user",0))
                call_id=data.get("call_id")
                if not to_id: continue
                payload={"type":t,"from_user":uid,"call_id":call_id}
                if t=="webrtc_offer": payload["sdp"]=data.get("sdp")
                elif t=="webrtc_answer": payload["sdp"]=data.get("sdp")
                else: payload["candidate"]=data.get("candidate")
                await manager.send_to(to_id,payload)

            elif t=="call_media_state":
                call_id=data.get("call_id")
                if call_id not in active_calls: continue
                c=active_calls[call_id]
                other=c["callee"] if c["caller"]==uid else c["caller"]
                await manager.send_to(other,{"type":"call_media_state","call_id":call_id,"from_user":uid,"mic":data.get("mic",True),"cam":data.get("cam",False),"screen":data.get("screen",False)})

            # СООБЩЕНИЯ
            elif t=="message":
                ch=data.get("channel_id");text=(data.get("text") or "")[:MAX_TEXT]
                furl=data.get("file_url");tid=data.get("temp_id");reply=data.get("reply_to")
                effect=data.get("effect","none");msg_kind=data.get("msg_kind","text")
                voice_dur=int(data.get("voice_duration",0));fsize=int(data.get("file_size",0))
                if not ch: continue
                if user.get("is_scam") and not has_scam_perm(user,"chat_send"):
                    await manager.send_to(uid,{"type":"muted","reason":"SCAM"}); continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,file_size,reply_to,effect,msg_kind,voice_duration) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *",int(ch),uid,text,furl,fsize,reply,effect,msg_kind,voice_dur)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    mc=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                if mc==1: await grant_achievement(uid,"first_msg")
                if fsize>0: await grant_achievement(uid,"first_file")
                await grant_xp(uid,1)
                await bp_add_progress(uid,"send_message",1)
                dn=user.get("display_name") or user["username"]
                payload={"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,
                    "username":user["username"],"display_name":dn,"avatar":user.get("avatar"),
                    "gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),
                    "text":text,"file_url":furl,"file_size":fsize,"reply_to":reply,"effect":effect,
                    "msg_kind":msg_kind,"voice_duration":voice_dur,"created_at":_iso(msg["created_at"]),
                    "is_scam":user.get("is_scam"),"title":user.get("title"),"active_frame":user.get("active_frame"),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)

            elif t=="dm":
                to_id=int(data.get("to_user",0));text=(data.get("text") or "")[:MAX_TEXT]
                furl=data.get("file_url");tid=data.get("temp_id");msg_kind=data.get("msg_kind","text")
                voice_dur=int(data.get("voice_duration",0));fsize=int(data.get("file_size",0))
                if not to_id: continue
                blocked=False
                p=await get_pool()
                async with p.acquire() as conn:
                    blk=await conn.fetchrow("SELECT blocker,chat_cleared FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",uid,to_id)
                    if blk: blocked=True
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url,file_size,msg_kind,voice_duration) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *",uid,to_id,text,furl,fsize,msg_kind,voice_dur)
                await grant_xp(uid,1)
                await bp_add_progress(uid,"send_dm",1)
                if fsize>0: await grant_achievement(uid,"first_file")
                dn=user.get("display_name") or user["username"]
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,
                    "username":user["username"],"display_name":dn,"avatar":user.get("avatar"),
                    "gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),
                    "text":text,"file_url":furl,"file_size":fsize,"msg_kind":msg_kind,"voice_duration":voice_dur,
                    "created_at":_iso(msg["created_at"]),"temp_id":tid,"is_scam":user.get("is_scam"),"title":user.get("title")}
                if not blocked: await manager.send_to(to_id,payload)
                await manager.send_to(uid,payload)

            elif t=="group_msg":
                gid=int(data.get("group_id",0));text=(data.get("text") or "")[:MAX_TEXT]
                furl=data.get("file_url");tid=data.get("temp_id");msg_kind=data.get("msg_kind","text")
                voice_dur=int(data.get("voice_duration",0));fsize=int(data.get("file_size",0))
                if user.get("is_scam") and not has_scam_perm(user,"chat_send"): continue
                p=await get_pool()
                async with p.acquire() as conn:
                    m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
                    if not m: continue
                    msg=await conn.fetchrow("INSERT INTO group_messages(group_id,user_id,text,file_url,file_size,msg_kind,voice_duration) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *",gid,uid,text,furl,fsize,msg_kind,voice_dur)
                    members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                if fsize>0: await grant_achievement(uid,"first_file")
                dn=user.get("display_name") or user["username"]
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,
                    "username":user["username"],"display_name":dn,"avatar":user.get("avatar"),
                    "gif_avatar":user.get("gif_avatar"),"text":text,"file_url":furl,"file_size":fsize,
                    "msg_kind":msg_kind,"voice_duration":voice_dur,"created_at":_iso(msg["created_at"]),
                    "temp_id":tid,"is_scam":user.get("is_scam"),"title":user.get("title")}
                for m in members: await manager.send_to(m["user_id"],payload)

            elif t=="typing":
                to_id=int(data.get("to_user",0))
                group_id=int(data.get("group_id",0))
                payload={"type":"typing","from_user":uid,"display_name":user.get("display_name") or user["username"]}
                if to_id: await manager.send_to(to_id,payload)
                if group_id:
                    p=await get_pool()
                    async with p.acquire() as conn:
                        members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",group_id)
                    for m in members:
                        if m["user_id"]!=uid: await manager.send_to(m["user_id"],payload)

    except WebSocketDisconnect: pass
    except Exception as e:
        print("="*60)
        print(f"[WS ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        print("="*60)
        try: await ws.send_json({"type":"error","detail":f"{type(e).__name__}: {e}"})
        except: pass
    finally:
        manager.disconnect(uid,ws)
        for cid,c in list(active_calls.items()):
            if c["caller"]==uid or c["callee"]==uid:
                other=c["callee"] if c["caller"]==uid else c["caller"]
                try: await manager.send_to(other,{"type":"call_ended","call_id":cid})
                except: pass
                del active_calls[cid]
        try:
            p=await get_pool()
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET last_seen=NOW() WHERE id=$1",uid)
        except: pass
        await manager.broadcast({"type":"user_offline","user_id":uid})

# ============ STATIC ============
@app.get("/manifest.json")
async def manifest():
    return {"name":"BelugaCord 3.3","short_name":"BelugaCord","start_url":"/","display":"standalone",
            "background_color":"#1a0a2e","theme_color":"#1a0a2e",
            "icons":[{"src":"/icon-192x192.png","sizes":"192x192","type":"image/png"}]}

@app.get("/sw.js")
async def service_worker():
    try:
        with open("sw.js","r",encoding="utf-8") as f:
            return HTMLResponse(f.read(),media_type="application/javascript")
    except: return HTMLResponse("// no sw",media_type="application/javascript")

@app.get("/")
async def index():
    try:
        with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())
    except Exception as e:
        return HTMLResponse(f"<h1>index.html не найден</h1><p>{e}</p>",status_code=500)

if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")