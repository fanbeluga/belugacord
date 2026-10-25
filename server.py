# ========== BELUGACORD 4.5 BETA — SERVER PART 1/3 ==========
import os,json,time,secrets,hashlib,random,datetime,asyncio,re,traceback,mimetypes
import asyncpg,httpx,shutil
from pathlib import Path
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,FileResponse,StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL=os.environ.get("DATABASE_URL","")
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2032")
ADMIN_USERNAME="_fan_beluga_"
ADMIN_DISPLAY="👑 Владелец"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="4.5-beta"
SUPPORT_BOT_ID=0
SUPPORT_BOT_NAME="support_bot"
SUPPORT_BOT_DISPLAY="🤖 Support Bot"
MAX_TEXT=10000

# ============ GOODRA WORLD ============
GOODRA_API_URL=os.environ.get("GOODRA_API_URL","")
GOODRA_API_KEY=os.environ.get("GOODRA_API_KEY","")
GOODRA_ENABLED=bool(GOODRA_API_URL and GOODRA_API_KEY)

# ============ ФАЙЛОВОЕ ХРАНЕНИЕ ============
UPLOAD_ROOT=Path(os.environ.get("UPLOAD_ROOT","uploads"))
UPLOAD_ROOT.mkdir(parents=True,exist_ok=True)

UPLOAD_DIRS={
    "avatar":UPLOAD_ROOT/"avatars",
    "banner":UPLOAD_ROOT/"banners",
    "photo":UPLOAD_ROOT/"photos",
    "video":UPLOAD_ROOT/"videos",
    "voice":UPLOAD_ROOT/"voice",
    "vnote":UPLOAD_ROOT/"vnotes",
    "file":UPLOAD_ROOT/"files",
    "channel_avatar":UPLOAD_ROOT/"channels"/"avatars",
    "channel_banner":UPLOAD_ROOT/"channels"/"banners",
    "sticker":UPLOAD_ROOT/"stickers",
    "story":UPLOAD_ROOT/"stories",
    "custom_emoji":UPLOAD_ROOT/"emoji",
    "reaction":UPLOAD_ROOT/"reactions",
    "draw":UPLOAD_ROOT/"draws",
}
for d in UPLOAD_DIRS.values():
    d.mkdir(parents=True,exist_ok=True)

ALLOWED_EXT={
    '.png','.jpg','.jpeg','.gif','.webp','.svg','.bmp','.avif','.ico','.heic',
    '.mp4','.webm','.mov','.mkv','.avi','.m4v',
    '.mp3','.wav','.ogg','.opus','.m4a','.aac','.flac',
    '.pdf','.txt','.json','.csv','.xml',
    '.zip','.rar','.7z','.tar','.gz',
    '.doc','.docx','.xls','.xlsx','.ppt','.pptx',
}
ALLOWED_MIME={
    'image/png','image/jpeg','image/jpg','image/gif','image/webp',
    'image/svg+xml','image/bmp','image/avif','image/heic',
    'video/mp4','video/webm','video/quicktime','video/x-matroska',
    'video/x-msvideo','video/x-m4v',
    'audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/ogg',
    'audio/mp4','audio/webm','audio/opus','audio/aac','audio/flac',
    'application/zip','application/x-zip','application/x-zip-compressed',
    'application/x-rar-compressed','application/x-7z-compressed',
    'application/pdf','text/plain','application/json','text/csv','application/xml',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/octet-stream',
}

def _detect_category(mime:str, filename:str="")->str:
    mime=(mime or "").lower()
    ext=os.path.splitext(filename or "")[1].lower()
    if mime.startswith("image/"): return "photo"
    if mime.startswith("video/"): return "video"
    if mime.startswith("audio/"): return "voice"
    if ext in (".zip",".rar",".7z",".tar",".gz"): return "file"
    return "file"

def save_uploaded_file(content:bytes,original_name:str,mime:str,category:str)->dict:
    if not content: raise HTTPException(400,"Пустой файл")
    mime=(mime or "application/octet-stream").lower().split(";")[0]
    if mime not in ALLOWED_MIME: raise HTTPException(400,f"Тип не разрешён: {mime}")
    ext=os.path.splitext(original_name or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT: raise HTTPException(400,f"Расширение не разрешено: {ext}")
    if not ext:
        ext=mimetypes.guess_extension(mime) or ".bin"
    if category not in UPLOAD_DIRS:
        category=_detect_category(mime,original_name)
    today=datetime.datetime.now(datetime.timezone.utc).strftime("%Y/%m/%d")
    subdir=UPLOAD_DIRS[category]/today
    subdir.mkdir(parents=True,exist_ok=True)
    fname=f"{secrets.token_hex(12)}{ext}"
    fpath=subdir/fname
    with open(fpath,"wb") as f: f.write(content)
    url=f"/uploads/{category}/{today}/{fname}"
    return {"url":url,"size":len(content),"mime":mime,
            "name":original_name or fname,"path":str(fpath),
            "category":category,"ext":ext}

def delete_uploaded_file(url:str)->bool:
    if not url or not url.startswith("/uploads/"): return False
    rel=url[len("/uploads/"):]
    if ".." in rel or rel.startswith("/"): return False
    target=(UPLOAD_ROOT/rel).resolve()
    try:
        if UPLOAD_ROOT.resolve() not in target.parents: return False
    except Exception: return False
    try:
        if target.exists(): target.unlink();return True
    except Exception: pass
    return False

def save_bytes_from_dataurl(data_url:str,category:str="draw")->dict:
    import base64
    if not data_url or not data_url.startswith("data:"): raise HTTPException(400,"Не data URL")
    try:
        header,b64=data_url.split(",",1)
        mime=header.split(";")[0].split(":")[1] or "image/jpeg"
        raw=base64.b64decode(b64)
    except Exception: raise HTTPException(400,"Битый data URL")
    return save_uploaded_file(raw,f"draw.{mimetypes.guess_extension(mime) or 'jpg'}",mime,category)

# ============ КОНСТАНТЫ ============
PREMIUM_PRICES={"month":1500,"year":18000}
DEFAULT_GIFTS={"rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},"cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},"crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},"legend":{"name":"Легендарка","emoji":"💠","price":5000},"pumpkin":{"name":"Тыква","emoji":"🎃","price":150},"ghost":{"name":"Призрак","emoji":"👻","price":250},"skull":{"name":"Череп","emoji":"💀","price":400},"heart":{"name":"Сердце","emoji":"❤️","price":50},"galaxy":{"name":"Галактика","emoji":"🌌","price":100000}}
ACHIEVEMENTS={"first_msg":{"name":"Первое слово","emoji":"💬"},"msg_100":{"name":"Болтун","emoji":"🗣️"},"msg_1000":{"name":"Оратор","emoji":"🎤"},"first_friend":{"name":"Дружелюбный","emoji":"👥"},"friend_10":{"name":"Тусовщик","emoji":"🎉"},"first_gift":{"name":"Щедрый","emoji":"🎁"},"first_call":{"name":"Звонкий","emoji":"📞"},"first_voice":{"name":"Голос","emoji":"🎙️"},"first_file":{"name":"Загрузчик","emoji":"📎"}}
HOLIDAYS=[("01-01","newyear","Новый год","🎄","#dc2626"),("02-14","valentine","День Валентина","💕","#ec4899"),("03-08","womens_day","8 марта","🌷","#f472b6"),("04-01","fools_day","День смеха","🤡","#facc15"),("05-09","victory_day","День Победы","🎖️","#f97316"),("09-01","knowledge_day","День знаний","📚","#8b5cf6"),("10-31","halloween","Хэллоуин","🎃","#ff6b1a"),("12-25","christmas_catholic","Рождество","🎅","#dc2626")]
SCAM_DEFAULT_PERMS={"dm_send":False,"dm_reply":True,"gift_send":False,"gift_receive":True,"chat_send":True,"chat_create":False,"set_avatar":False,"set_banner":False,"call":False,"add_friends":False}
RESERVED_USERNAMES={"admin","support","system","belugacord","help","api","c","join","me","root","official","user","moderator"}

STREET_DEFAULT={"x":50,"y":50,"location":"street"}
FURNITURE_DEFAULT=[("sofa","Диван","🛋️",500),("table","Стол","🪑",300),("bed","Кровать","🛏️",800),("tv","Телевизор","📺",1500),("plant","Растение","🪴",200),("lamp","Лампа","💡",250),("carpet","Ковёр","🟫",400),("fridge","Холодильник","🧊",1200),("flashlight","Фонарик","🔦",1000)]
PET_SPECIES={"cat":"🐱","dog":"🐶","dragon":"🐉","fox":"🦊","hamster":"🐹","owl":"🦉"}
LOOTBOX_DEFAULT={"common":{"name":"Обычный сундук","emoji":"🎁","price":500},"rare":{"name":"Редкий сундук","emoji":"💎","price":2000},"legend":{"name":"Легендарный сундук","emoji":"👑","price":10000}}
DUEL_TARGET_TAPS=20
BOMB_FUSE_SECONDS=10
CAPSULE_MIN_DAYS=1
CAPSULE_MAX_DAYS=3650
BAD_WORDS_DEFAULT=["бля","хуй","пизда","еба","сука","долбо","мразь","гандон","жопа","дерьмо","говно","нахуй","похуй","залупа","мудак","уебок","уёбок","срать","пидор","гей"]
MSG_SHAPES={"round":"Круглый","square":"Квадрат","dot":"Точка","cloud":"Облако","none":"Без бабла"}
STORY_TTL_HOURS=24
SLOW_MODE_MAX_SECONDS=600
PROMO_MAX_ACTIVATIONS=10000
DONATE_REQUESTS_TIMEOUT_HOURS=72

SKINS_CATALOG=[
    {"id":"default","name":"Зелёный закат","emoji":"🌿","price":0,"ac":"#22c55e","ac2":"#ff8c00"},
    {"id":"forest","name":"Лес","emoji":"🌲","price":2000,"ac":"#16a34a","ac2":"#ea580c"},
    {"id":"ember","name":"Угли","emoji":"🔥","price":3000,"ac":"#ea580c","ac2":"#22c55e"},
    {"id":"matrix","name":"Матрица","emoji":"🟢","price":5000,"ac":"#22c55e","ac2":"#16a34a"},
    {"id":"sunset","name":"Закат","emoji":"🌅","price":3000,"ac":"#f97316","ac2":"#ec4899"},
    {"id":"ocean","name":"Океан","emoji":"🌊","price":3000,"ac":"#06b6d4","ac2":"#0ea5e9"},
    {"id":"lava","name":"Лава","emoji":"🌋","price":7000,"ac":"#dc2626","ac2":"#f97316"},
    {"id":"ghost","name":"Призрак","emoji":"👻","price":4000,"ac":"#a855f7","ac2":"#6366f1"},
]

# ============ ХЕЛПЕРЫ ============
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
    if not u: u="user"
    if len(u)>24: u=u[:24]
    if u[0].isdigit(): u="_"+u
    return u

def validate_username(u):
    if not u: return False,"Пусто"
    if len(u)<4 or len(u)>32: return False,"4-32 символа"
    if not re.match(r'^[a-z][a-z0-9_]*$',u): return False,"Только a-z, 0-9, _"
    if u in RESERVED_USERNAMES: return False,"Зарезервировано"
    return True,None

TRANSLIT={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def translit(s): return ''.join(TRANSLIT.get(c,c) for c in str(s))

def _iso(dt):
    if not dt: return None
    try: return dt.isoformat()
    except: return str(dt)

def _aware(dt):
    if dt is None: return None
    if isinstance(dt,str): return dt
    if dt.tzinfo is None: return dt.replace(tzinfo=datetime.timezone.utc)
    return dt

def _safe_json(v,default=None):
    if default is None: default={}
    try:
        if isinstance(v,str): return json.loads(v)
        return v
    except: return default

def get_today_holiday():
    ts=datetime.datetime.now(datetime.timezone.utc).strftime("%m-%d")
    for h in HOLIDAYS:
        if h[0]==ts: return {"active":True,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4]}
    return {"active":False}

def has_bad_words(text,words):
    if not text or not words: return False
    low=text.lower()
    for w in words:
        if w and w.lower() in low: return True
    return False

# ============ APP ============
app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def no_cache(request:Request,call_next):
    r=await call_next(request)
    if request.url.path.startswith("/api/"):
        r.headers["Cache-Control"]="no-store"
    return r

# Статика — всё дерево uploads
app.mount("/uploads",StaticFiles(directory=str(UPLOAD_ROOT)),name="uploads")

@app.get("/icon.png")
async def serve_icon():
    for p in ["icon-192x192.png","icon.png"]:
        if os.path.exists(p):
            with open(p,"rb") as f: return HTMLResponse(content=f.read(),media_type="image/png")
    return HTMLResponse("",status_code=404)

# ============ СОСТОЯНИЯ ============
pool=None
online_users=set()
active_calls={}
active_group_calls={}
street_state={"rain":False,"night":False,"vote_active":False,"vote_options":[],"vote_zones":{}}
active_whispers={}
active_duels={}
active_bombs={}
klondike_active=[]
draw_battles_active={}
slow_mode_cache={}
typing_last={}

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=10)
    return pool

# ============ INIT DB ============
async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        # users (с mood_enabled)
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,username VARCHAR(64) UNIQUE NOT NULL,display_name VARCHAR(64),
            password_hash VARCHAR(128) NOT NULL,avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',
            is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,
            is_scam BOOLEAN DEFAULT FALSE,is_banned BOOLEAN DEFAULT FALSE,ban_reason VARCHAR(256),mute_until TIMESTAMPTZ,
            premium_tier VARCHAR(8),premium_expires TIMESTAMPTZ,
            online_status VARCHAR(16) DEFAULT 'online',custom_status VARCHAR(128),bio VARCHAR(256),
            coins INTEGER DEFAULT 0,messages_count INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]',active_frame VARCHAR(32),frame_owned TEXT DEFAULT '[]',
            title VARCHAR(64),title_owned TEXT DEFAULT '[]',level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,
            candy INTEGER DEFAULT 0,scam_perms TEXT DEFAULT '{}',
            airplane_mode BOOLEAN DEFAULT FALSE,notif_enabled BOOLEAN DEFAULT TRUE,sound_enabled BOOLEAN DEFAULT TRUE,
            theme VARCHAR(16) DEFAULT 'dark',font_size VARCHAR(8) DEFAULT 'md',rank_id INTEGER,
            double_xp_until TIMESTAMPTZ,nick_gradient VARCHAR(64),status_emoji VARCHAR(8),bio_bg TEXT,
            hide_typing BOOLEAN DEFAULT FALSE,mood_enabled BOOLEAN DEFAULT TRUE,
            last_seen TIMESTAMPTZ DEFAULT NOW(),created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        # Основные
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,chat_cleared BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE,name VARCHAR(64) NOT NULL,avatar TEXT,banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,last_message_at TIMESTAMPTZ,slow_mode INTEGER DEFAULT 0,bad_words TEXT DEFAULT '[]',created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,is_admin BOOLEAN DEFAULT FALSE,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,msg_kind VARCHAR(16) DEFAULT 'text',voice_duration INTEGER DEFAULT 0,reply_to_id INTEGER,edited_at TIMESTAMPTZ,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,thread_id INTEGER,post_id INTEGER,as_channel BOOLEAN DEFAULT FALSE,msg_shape VARCHAR(16),created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(
            id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,msg_kind VARCHAR(16) DEFAULT 'text',voice_duration INTEGER DEFAULT 0,
            read_at TIMESTAMPTZ,forwarded_from VARCHAR(64),pinned BOOLEAN DEFAULT FALSE,starred TEXT DEFAULT '[]',
            reply_to_id INTEGER,edited_at TIMESTAMPTZ,reactions TEXT DEFAULT '{}',deleted_for_all BOOLEAN DEFAULT FALSE,album_id VARCHAR(32),
            expires_at TIMESTAMPTZ,msg_shape VARCHAR(16),created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        # Каналы
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE,name VARCHAR(64) NOT NULL,bio VARCHAR(256),avatar TEXT,banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,is_private BOOLEAN DEFAULT FALSE,category VARCHAR(32),subscribers_count INTEGER DEFAULT 0,username_changed_at TIMESTAMPTZ,linked_group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_admins(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,perms TEXT DEFAULT '{"post":true}',added_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(channel_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_subscribers(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,muted_until TIMESTAMPTZ,subscribed_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(channel_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_posts(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,text TEXT,media_urls TEXT DEFAULT '[]',media_kind VARCHAR(16) DEFAULT 'text',reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,views INTEGER DEFAULT 0,edited BOOLEAN DEFAULT FALSE,comments_count INTEGER DEFAULT 0,discussion_msg_id INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_post_views(post_id INTEGER REFERENCES channel_posts(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,viewed_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(post_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_bans(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,reason VARCHAR(256),banned_by INTEGER,banned_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(channel_id,user_id))""")
        # Остальные таблицы 4.2
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS support_tickets(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,ticket_type VARCHAR(32),target_user INTEGER,title VARCHAR(128),description TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',admin_reply TEXT,resolved_by INTEGER,created_at TIMESTAMPTZ DEFAULT NOW(),resolved_at TIMESTAMPTZ)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),price_coins INTEGER DEFAULT 0)""")
        for f in [("none","Без рамки","",0),("gold","Золотая","👑",500),("fire","Огненная","🔥",800),("ice","Ледяная","❄️",800),("rainbow","Радужная","🌈",0),("pumpkin","Тыква","🎃",0),("ghost","Призрак","👻",0)]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,price_coins) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",*f)
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS titles_catalog(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),color VARCHAR(32),is_public BOOLEAN DEFAULT TRUE,condition_type VARCHAR(32),condition_value INTEGER,creator_id INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM titles_catalog")
        if cnt==0:
            for t in [("Призрак","👻","#a855f7"),("Вампир","🧛","#dc2626"),("Ведьма","🧙","#ec4899"),("Легенда","🏅","#ffb020")]:
                await conn.execute("INSERT INTO titles_catalog(name,emoji,color) VALUES($1,$2,$3)",*t)
        await conn.execute("""CREATE TABLE IF NOT EXISTS system_settings(key VARCHAR(64) PRIMARY KEY,value TEXT,updated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_history(id SERIAL PRIMARY KEY,call_id VARCHAR(32),caller INTEGER REFERENCES users(id) ON DELETE CASCADE,callee INTEGER REFERENCES users(id) ON DELETE CASCADE,call_type VARCHAR(16) DEFAULT 'audio',status VARCHAR(16) DEFAULT 'ended',duration INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ranks(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8) DEFAULT '🏆',color VARCHAR(32) DEFAULT '#22c55e',priority INTEGER DEFAULT 10,perms TEXT DEFAULT '{}',created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_chat_settings(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,chat_type VARCHAR(16),chat_id INTEGER,pinned BOOLEAN DEFAULT FALSE,archived BOOLEAN DEFAULT FALSE,mute_until TIMESTAMPTZ,UNIQUE(user_id,chat_type,chat_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS referrals(id SERIAL PRIMARY KEY,code VARCHAR(16) UNIQUE NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,clicks INTEGER DEFAULT 0,registrations INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS referral_uses(id SERIAL PRIMARY KEY,code VARCHAR(16),referrer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,new_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,reward_ref INTEGER DEFAULT 0,reward_new INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS chat_drafts(user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,chat_type VARCHAR(16),chat_id INTEGER,text TEXT,updated_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(user_id,chat_type,chat_id))""")
        # 4.0
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_positions(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,x REAL DEFAULT 50,y REAL DEFAULT 50,location VARCHAR(32) DEFAULT 'street',house_id INTEGER,updated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS houses(id SERIAL PRIMARY KEY,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,name VARCHAR(64) DEFAULT 'Мой дом',bg VARCHAR(64) DEFAULT 'room1',has_flashlight BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS furniture_catalog(id SERIAL PRIMARY KEY,item_id VARCHAR(32) UNIQUE,name VARCHAR(64),emoji VARCHAR(8),price INTEGER DEFAULT 0,category VARCHAR(16) DEFAULT 'furniture')""")
        for _f in FURNITURE_DEFAULT:
            try: await conn.execute("INSERT INTO furniture_catalog(item_id,name,emoji,price,category) VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",_f[0],_f[1],_f[2],_f[3],"tool" if _f[0]=="flashlight" else "furniture")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS house_items(id SERIAL PRIMARY KEY,house_id INTEGER REFERENCES houses(id) ON DELETE CASCADE,item_id VARCHAR(32),x REAL DEFAULT 50,y REAL DEFAULT 50,rot REAL DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS house_locks(house_id INTEGER PRIMARY KEY REFERENCES houses(id) ON DELETE CASCADE,password VARCHAR(64),created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS market_listings(id SERIAL PRIMARY KEY,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,item_type VARCHAR(16),item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),price INTEGER NOT NULL,sold BOOLEAN DEFAULT FALSE,buyer_id INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_rate(id SERIAL PRIMARY KEY,rate REAL DEFAULT 1.0,updated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("INSERT INTO coin_rate(id,rate) VALUES(1,1.0) ON CONFLICT DO NOTHING")
        await conn.execute("""CREATE TABLE IF NOT EXISTS families(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,wallet INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS family_members(family_id INTEGER REFERENCES families(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,role VARCHAR(16) DEFAULT 'member',joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(family_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS lootboxes(id SERIAL PRIMARY KEY,name VARCHAR(64),price INTEGER,emoji VARCHAR(8) DEFAULT '🎁',is_active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS lootbox_items(id SERIAL PRIMARY KEY,box_id INTEGER REFERENCES lootboxes(id) ON DELETE CASCADE,item_type VARCHAR(16),item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),chance REAL DEFAULT 10,rarity VARCHAR(16) DEFAULT 'common')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS luck_counter(user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,box_id INTEGER,attempts INTEGER DEFAULT 0,PRIMARY KEY(user_id,box_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS wishlist(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,item_name VARCHAR(64),item_emoji VARCHAR(8),price INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS pets(id SERIAL PRIMARY KEY,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,name VARCHAR(32),species VARCHAR(16) DEFAULT 'cat',level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,hunger INTEGER DEFAULT 100,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS pet_market(id SERIAL PRIMARY KEY,pet_id INTEGER REFERENCES pets(id) ON DELETE CASCADE,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,price INTEGER,sold BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS stocks(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,price INTEGER DEFAULT 100,holders INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS stock_holders(stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,holder_id INTEGER REFERENCES users(id) ON DELETE CASCADE,shares INTEGER DEFAULT 1,bought_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(stock_id,holder_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS time_capsules(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,open_at TIMESTAMPTZ NOT NULL,opened BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS duels(id SERIAL PRIMARY KEY,challenger INTEGER REFERENCES users(id) ON DELETE CASCADE,opponent INTEGER REFERENCES users(id) ON DELETE CASCADE,bet INTEGER DEFAULT 0,target_taps INTEGER DEFAULT 20,challenger_taps INTEGER DEFAULT 0,opponent_taps INTEGER DEFAULT 0,status VARCHAR(16) DEFAULT 'pending',winner INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS anonymous_messages(id SERIAL PRIMARY KEY,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,question_mode BOOLEAN DEFAULT FALSE,answer TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS confessions(id SERIAL PRIMARY KEY,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,read_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS secret_santa(id SERIAL PRIMARY KEY,event_id INTEGER,giver INTEGER REFERENCES users(id) ON DELETE CASCADE,receiver INTEGER REFERENCES users(id) ON DELETE CASCADE,gift_sent BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS truth_detector(id SERIAL PRIMARY KEY,asker INTEGER REFERENCES users(id) ON DELETE CASCADE,target INTEGER REFERENCES users(id) ON DELETE CASCADE,question TEXT,answer_time_ms INTEGER,verdict VARCHAR(16),created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bombs(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,explodes_at TIMESTAMPTZ,defused BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bets(id SERIAL PRIMARY KEY,creator INTEGER REFERENCES users(id) ON DELETE CASCADE,opponent INTEGER REFERENCES users(id) ON DELETE CASCADE,amount INTEGER,condition_text TEXT,status VARCHAR(16) DEFAULT 'pending',winner INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS draw_battles(id SERIAL PRIMARY KEY,drawer INTEGER REFERENCES users(id) ON DELETE CASCADE,guesser INTEGER REFERENCES users(id) ON DELETE CASCADE,word VARCHAR(64),guesses TEXT DEFAULT '[]',status VARCHAR(16) DEFAULT 'active',created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blind_zones(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,answers TEXT DEFAULT '[]',created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS fate_buttons(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,effect VARCHAR(32),claimed BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS klondike(id SERIAL PRIMARY KEY,x REAL,y REAL,coins INTEGER DEFAULT 500,claimed BOOLEAN DEFAULT FALSE,claimed_by INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        # 4.2
        await conn.execute("""CREATE TABLE IF NOT EXISTS disappearing_messages(id SERIAL PRIMARY KEY,chat_type VARCHAR(16),chat_id INTEGER,message_id INTEGER,expires_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS polls(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,creator INTEGER REFERENCES users(id) ON DELETE CASCADE,question VARCHAR(256) NOT NULL,options TEXT DEFAULT '[]',votes TEXT DEFAULT '{}',multiple BOOLEAN DEFAULT FALSE,closes_at TIMESTAMPTZ,closed BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS promocodes(id SERIAL PRIMARY KEY,code VARCHAR(32) UNIQUE NOT NULL,reward INTEGER DEFAULT 0,max_activations INTEGER DEFAULT 1,activations INTEGER DEFAULT 0,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,for_user INTEGER REFERENCES users(id) ON DELETE CASCADE,expires_at TIMESTAMPTZ,active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS promo_activations(id SERIAL PRIMARY KEY,promo_id INTEGER REFERENCES promocodes(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,reward INTEGER DEFAULT 0,activated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS donate_requests(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,amount INTEGER NOT NULL,message TEXT,status VARCHAR(16) DEFAULT 'pending',reviewed_by INTEGER,reviewed_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS stories(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,kind VARCHAR(16) DEFAULT 'text',content TEXT,file_url TEXT,views INTEGER DEFAULT 0,expires_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS story_views(story_id INTEGER REFERENCES stories(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,viewed_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(story_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS profile_wall(id SERIAL PRIMARY KEY,profile_user INTEGER REFERENCES users(id) ON DELETE CASCADE,author INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_reactions(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,emoji_id VARCHAR(32) UNIQUE NOT NULL,name VARCHAR(64),image_url TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS link_previews(url VARCHAR(512) PRIMARY KEY,title VARCHAR(256),description TEXT,image TEXT,site_name VARCHAR(64),fetched_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS events_calendar(id SERIAL PRIMARY KEY,title VARCHAR(128) NOT NULL,description TEXT,event_date TIMESTAMPTZ NOT NULL,emoji VARCHAR(8) DEFAULT '📅',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS secret_rooms(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,password_hash VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,capacity INTEGER DEFAULT 10,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS room_members(room_id INTEGER REFERENCES secret_rooms(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(room_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_skins(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,active_skin VARCHAR(32) DEFAULT 'default',owned TEXT DEFAULT '["default"]',updated_at TIMESTAMPTZ DEFAULT NOW())""")
        # Миграции
        migrations=[
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS hide_typing BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS mood_enabled BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS nick_gradient VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS status_emoji VARCHAR(8)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio_bg TEXT",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS reply_to_id INTEGER",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS reactions TEXT DEFAULT '{}'",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS deleted_for_all BOOLEAN DEFAULT FALSE",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS album_id VARCHAR(32)",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
            "ALTER TABLE dms ADD COLUMN IF NOT EXISTS msg_shape VARCHAR(16)",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS username VARCHAR(32)",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS banner TEXT",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS avatar_pos TEXT DEFAULT '50% 50%'",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS banner_pos TEXT DEFAULT '50% 50%'",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS slow_mode INTEGER DEFAULT 0",
            "ALTER TABLE groups ADD COLUMN IF NOT EXISTS bad_words TEXT DEFAULT '[]'",
            "ALTER TABLE group_members ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS reply_to_id INTEGER",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS reactions TEXT DEFAULT '{}'",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS thread_id INTEGER",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS post_id INTEGER",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS as_channel BOOLEAN DEFAULT FALSE",
            "ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS msg_shape VARCHAR(16)",
        ]
        for sql in migrations:
            try: await conn.execute(sql)
            except: pass
        # Индексы
        try:
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_dms_users ON dms(from_user,to_user,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chan_posts ON channel_posts(channel_id,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_gmsgs ON group_messages(group_id,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_positions ON user_positions(location)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_exp ON stories(expires_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_dismsg_exp ON disappearing_messages(expires_at)")
        except: pass
        # Дефолтные данные
        await conn.execute("UPDATE users SET display_name=username WHERE display_name IS NULL")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2",ADMIN_DISPLAY,ADMIN_USERNAME)
        bot_exists=await conn.fetchval("SELECT 1 FROM users WHERE id=$1",SUPPORT_BOT_ID)
        if not bot_exists:
            try:
                await conn.execute("INSERT INTO users(id,username,display_name,password_hash) VALUES($1,$2,$3,$4)",SUPPORT_BOT_ID,SUPPORT_BOT_NAME,SUPPORT_BOT_DISPLAY,hash_password("bot_"+SECRET_KEY))
                await conn.execute("SELECT setval(pg_get_serial_sequence('users','id'),GREATEST((SELECT MAX(id) FROM users),1))")
            except: pass
        ranks_cnt=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if ranks_cnt==0:
            try:
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","👑 Владелец","👑","#ffb020",1000,json.dumps({"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True,"give_premium":True,"manage_shop":True,"manage_cosmetics":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🛡️ Администратор","🛡️","#22c55e",500,json.dumps({"admin_panel":True,"manage_users":True,"give_coins":True,"ban":True,"mute":True,"delete_msgs":True,"broadcast":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🔨 Модератор","🔨","#84cc16",100,json.dumps({"mute":True,"delete_msgs":True}))
            except: pass
        print("✅ БД 4.5 BETA готова")

# ============ USER HELPERS ============
async def get_current_user(token):
    parsed=parse_token(token)
    if not parsed: return None
    uid,_=parsed
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

async def grant_achievement(uid,key):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            exists=await conn.fetchval("SELECT 1 FROM achievement_log WHERE user_id=$1 AND key=$2",uid,key) if False else None
            await conn.execute("INSERT INTO users(achievements) VALUES('[]') ON CONFLICT DO NOTHING") if False else None
            # achievements храним в JSON в users
            row=await conn.fetchrow("SELECT achievements FROM users WHERE id=$1",uid)
            if not row: return False
            arr=_safe_json(row["achievements"],[])
            if key in arr: return False
            arr.append(key)
            await conn.execute("UPDATE users SET achievements=$1,coins=coins+50 WHERE id=$2",json.dumps(arr),uid)
            return True
    except: return False

def get_role(row):
    if not row: return "user"
    if row.get("username")==ADMIN_USERNAME: return "owner"
    if row.get("is_admin"): return "admin"
    if row.get("is_moderator"): return "moderator"
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
        return {"id":row["id"],"username":row["username"],"display_name":row.get("display_name") or row["username"],
            "avatar":row.get("avatar"),"banner":row.get("banner"),"gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
            "avatar_pos":row.get("avatar_pos") or "50% 50%","banner_pos":row.get("banner_pos") or "50% 50%",
            "is_admin":bool(row.get("is_admin")),"is_moderator":bool(row.get("is_moderator")),
            "is_scam":bool(row.get("is_scam")),"premium_tier":row.get("premium_tier"),
            "is_premium":is_premium(row),"online_status":status,"bio":row.get("bio"),
            "custom_status":row.get("custom_status"),"status_emoji":row.get("status_emoji"),
            "nick_gradient":row.get("nick_gradient"),"bio_bg":row.get("bio_bg"),
            "coins":row.get("coins",0),"messages_count":row.get("messages_count",0),
            "active_frame":row.get("active_frame"),"frame_owned":_safe_json(row.get("frame_owned"),[]),
            "title":row.get("title"),"title_owned":_safe_json(row.get("title_owned"),[]),
            "level":row.get("level",1),"xp":row.get("xp",0),"candy":row.get("candy",0),
            "rank_id":row.get("rank_id"),"font_size":row.get("font_size") or "md",
            "airplane_mode":bool(row.get("airplane_mode")),"notif_enabled":bool(row.get("notif_enabled",True)),
            "sound_enabled":bool(row.get("sound_enabled",True)),"theme":row.get("theme") or "dark",
            "hide_typing":bool(row.get("hide_typing")),"mood_enabled":bool(row.get("mood_enabled",True)),
            "created_at":_iso(row.get("created_at")),"role":get_role(row),"online":is_online,
            "achievements":_safe_json(row.get("achievements"),[])}
    except Exception as e:
        print(f"[user_public ERR] {e}")
        return {"id":row.get("id"),"username":row.get("username"),"is_premium":False,"online":False}

async def get_all_gifts():
    gifts=dict(DEFAULT_GIFTS)
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM custom_gifts")
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

async def _get_target(conn,data):
    if data.get("user_id"): return await conn.fetchrow("SELECT id,username,display_name FROM users WHERE id=$1",int(data["user_id"]))
    if data.get("username"): return await conn.fetchrow("SELECT id,username,display_name FROM users WHERE username=$1",str(data["username"]).lstrip("@"))
    return None

async def is_blocked(a,b):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT id FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",a,b)
            return bool(row)
    except: return False

def _user_perms(user):
    if not user: return {}
    if user["username"]==ADMIN_USERNAME:
        return {"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"manage_shop":True,"manage_cosmetics":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True,"bypass_limits":True,"verified":True,"custom_title":True,"give_premium":True,"spy":True,"global_theme":True}
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

async def check_owner(user):
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")

async def get_my_rank_priority(uid):
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

# ============ CONNECTION MANAGER ============
class ConnectionManager:
    def __init__(self): self.connections={}
    async def connect(self,uid,ws):
        await ws.accept()
        self.connections.setdefault(uid,[]).append(ws)
        online_users.add(uid)
    def disconnect(self,uid,ws):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except: pass
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

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e:
            print(f"❌ DB INIT: {e}")
            traceback.print_exc()

# ============ CHANGELOG / VERSION ============
@app.get("/api/changelog")
async def changelog():
    return {"current":"4.5-beta","all":{
        "4.5-beta":{"title":"BelugaCord 4.5 BETA — Зелёный рассвет 🌿","items":[
            "🌿 Новая зелёно-оранжевая тема и скины",
            "📞 Переделанный UI звонков (полноэкранный)",
            "📢 Починены каналы полностью",
            "🎥 Видео-кружки и голосовые в каналах",
            "🖼️ Drag-n-drop для аватарок и баннеров (профиль + каналы)",
            "🌿 Оценка настроения по общению (без ИИ) рядом с «Печатает...»",
            "💾 Хранение файлов на сервере (без base64)",
            "🔗 Интеграция с Goodra World",
        ]},
        "4.2":{"title":"BelugaCord 4.2 — «НЕ ВОШЕДШЕЕ?» 🔥😈","items":["⏱️ Исчезающие","📊 Опросы","🎟️ Промокоды","💸 Донат","📸 Истории","💬 Стена","😀 Реакции","🔗 Превью ссылок","🔍 Поиск","🐢 Slow-mode","🚫 Bad words","📢 @all","📅 Календарь","🎨 Коллекции","🔐 Комнаты","🖌️ Скины"]},
        "4.0":{"title":"BelugaCord 4.0 — Восставший с Ада","items":["🏙️ Улица","🏠 Дом","💰 Биржа","👨‍👩‍👧 Семья","🐱 Питомцы","📈 Акции","⏳ Капсулы","🎲 Дуэли","🕵️ Анонимки"]},
        "3.6":{"title":"BelugaCord 3.6 — Титан","items":["📢 Каналы","💬 Обсуждения","🎥 Кружки"]}
    }}

@app.get("/api/version")
async def version():
    return {"version":CURRENT_VERSION,"name":"BelugaCord","emoji":"🌿"}

# ============ GOODRA STATUS ============
@app.get("/api/goodra/status")
async def goodra_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"enabled":GOODRA_ENABLED,"api_url":GOODRA_API_URL if GOODRA_ENABLED else None,"version":CURRENT_VERSION}
# ========== BELUGACORD 4.5 BETA — SERVER PART 2/3 ==========

# ============ AUTH ============
@app.post("/api/register")
async def register(data:dict):
    raw_u=(data.get("username") or "").strip().lower()
    raw_d=(data.get("display_name") or raw_u).strip()
    pw=data.get("password") or ""
    ref_code=(data.get("ref_code") or "").strip()
    promo_code=(data.get("promo_code") or "").strip()
    if not raw_u and raw_d: raw_u=translit(raw_d).lower()
    raw_u=sanitize_username(raw_u)
    if len(pw)<4: raise HTTPException(400,"Пароль мин 4")
    if len(raw_d)<2 or len(raw_d)>64: raise HTTPException(400,"Ник 2-64")
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM users WHERE username=$1",raw_u)
        if exists: raise HTTPException(400,"Занято")
        row=await conn.fetchrow("INSERT INTO users(username,display_name,password_hash,is_admin) VALUES($1,$2,$3,$4) RETURNING *",raw_u,raw_d,hash_password(pw),raw_u==ADMIN_USERNAME)
        if ref_code:
            ref=await conn.fetchrow("SELECT owner_id FROM referrals WHERE code=$1",ref_code)
            if ref and ref["owner_id"]!=row["id"]:
                try:
                    await conn.execute("UPDATE users SET coins=coins+20000 WHERE id=$1",ref["owner_id"])
                    await conn.execute("UPDATE users SET coins=coins+500 WHERE id=$1",row["id"])
                    await conn.execute("INSERT INTO referral_uses(code,referrer_id,new_user_id,reward_ref,reward_new) VALUES($1,$2,$3,20000,500)",ref_code,ref["owner_id"],row["id"])
                    await conn.execute("UPDATE referrals SET registrations=registrations+1 WHERE code=$1",ref_code)
                    await manager.send_to(ref["owner_id"],{"type":"referral_bonus","amount":20000,"new_username":raw_u})
                except Exception as e: print(f"[referral] {e}")
        if promo_code:
            pr=await conn.fetchrow("SELECT * FROM promocodes WHERE code=$1 AND active=TRUE",promo_code.upper())
            if pr and (pr["max_activations"]==0 or pr["activations"]<pr["max_activations"]):
                if not pr["for_user"] or pr["for_user"]==row["id"]:
                    await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",pr["reward"],row["id"])
                    await conn.execute("UPDATE promocodes SET activations=activations+1 WHERE id=$1",pr["id"])
                    await conn.execute("INSERT INTO promo_activations(promo_id,user_id,reward) VALUES($1,$2,$3)",pr["id"],row["id"],pr["reward"])
        try: await conn.execute("INSERT INTO user_positions(user_id,x,y,location) VALUES($1,50,50,'street') ON CONFLICT DO NOTHING",row["id"])
        except: pass
        try: await conn.execute("INSERT INTO user_skins(user_id) VALUES($1) ON CONFLICT DO NOTHING",row["id"])
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
async def me_api(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    pub=user_public(user,user["id"])
    p=await get_pool()
    async with p.acquire() as conn:
        perms,rank=await get_user_perms_full(conn,user["id"])
        try:
            sk=await conn.fetchrow("SELECT active_skin,owned FROM user_skins WHERE user_id=$1",user["id"])
            if sk:
                pub["active_skin"]=sk["active_skin"]
                pub["owned_skins"]=_safe_json(sk["owned"],["default"])
        except: pass
    pub["perms"]=perms
    pub["rank"]=rank
    return pub

@app.post("/api/user/quick_setting")
async def quick_setting(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    key=str(data.get("key") or "")
    val=data.get("value")
    allowed={"airplane_mode":"airplane_mode","notif_enabled":"notif_enabled","sound_enabled":"sound_enabled","theme":"theme","font_size":"font_size","hide_typing":"hide_typing","mood_enabled":"mood_enabled"}
    col=allowed.get(key)
    if not col: raise HTTPException(400,"Ключ?")
    p=await get_pool()
    async with p.acquire() as conn:
        if col in ("theme","font_size"):
            await conn.execute(f"UPDATE users SET {col}=$1 WHERE id=$2",str(val)[:16],user["id"])
        else:
            await conn.execute(f"UPDATE users SET {col}=$1 WHERE id=$2",bool(val),user["id"])
    return {"ok":True}

@app.post("/api/user/status_full")
async def user_status_full(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    st=data.get("online_status","online")
    if st not in ("online","dnd","away","invisible"): raise HTTPException(400,"Неверный статус")
    custom=(data.get("custom_status") or "")[:64]
    emoji=(data.get("status_emoji") or "")[:8]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET online_status=$1,custom_status=$2,status_emoji=$3 WHERE id=$4",st,custom or None,emoji or None,user["id"])
    await manager.broadcast({"type":"status_update","user_id":user["id"],"online_status":st,"custom_status":custom,"status_emoji":emoji})
    return {"ok":True}

@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    new_d=(data.get("display_name") or "").strip()[:64] if "display_name" in data else None
    p=await get_pool()
    async with p.acquire() as conn:
        if new_d:
            await conn.execute("UPDATE users SET display_name=$1 WHERE id=$2",new_d,user["id"])
        await conn.execute("""UPDATE users SET avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),
            gif_avatar=COALESCE($3,gif_avatar),gif_banner=COALESCE($4,gif_banner),
            avatar_pos=COALESCE($5,avatar_pos),banner_pos=COALESCE($6,banner_pos),
            bio=COALESCE($7,bio),nick_gradient=COALESCE($8,nick_gradient),status_emoji=COALESCE($9,status_emoji),
            bio_bg=COALESCE($10,bio_bg) WHERE id=$11""",
            data.get("avatar"),data.get("banner"),data.get("gif_avatar"),data.get("gif_banner"),
            data.get("avatar_pos"),data.get("banner_pos"),data.get("bio"),data.get("nick_gradient"),
            data.get("status_emoji"),data.get("bio_bg"),user["id"])
    await manager.broadcast({"type":"user_updated","user_id":user["id"]})
    return {"ok":True}

@app.post("/api/upload_avatar")
async def upload_avatar(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400,"Только картинка")
    content=await file.read()
    if len(content)>10*1024*1024: raise HTTPException(400,"Макс 10 МБ")
    saved=save_uploaded_file(content,file.filename or "avatar.png",file.content_type,"avatar")
    p=await get_pool()
    async with p.acquire() as conn:
        old=await conn.fetchval("SELECT avatar FROM users WHERE id=$1",user["id"])
        if old: delete_uploaded_file(old)
        await conn.execute("UPDATE users SET avatar=$1 WHERE id=$2",saved["url"],user["id"])
    await manager.broadcast({"type":"user_updated","user_id":user["id"]})
    return {"ok":True,"url":saved["url"]}

@app.post("/api/upload_banner")
async def upload_banner(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400,"Только картинка")
    content=await file.read()
    if len(content)>15*1024*1024: raise HTTPException(400,"Макс 15 МБ")
    saved=save_uploaded_file(content,file.filename or "banner.png",file.content_type,"banner")
    p=await get_pool()
    async with p.acquire() as conn:
        old=await conn.fetchval("SELECT banner FROM users WHERE id=$1",user["id"])
        if old: delete_uploaded_file(old)
        await conn.execute("UPDATE users SET banner=$1 WHERE id=$2",saved["url"],user["id"])
    await manager.broadcast({"type":"user_updated","user_id":user["id"]})
    return {"ok":True,"url":saved["url"]}

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
        frows=await conn.fetch("SELECT CASE WHEN user_a=$1 THEN user_b ELSE user_a END AS oid FROM friendships WHERE user_a=$1 OR user_b=$1",uid)
        for r in frows:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["oid"])
            if not o: continue
            last=await conn.fetchval("SELECT MAX(created_at) FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",uid,r["oid"])
            item=user_public(o,uid)
            item["status"]="accepted";item["last_message_at"]=_iso(last)
            result.append(item)
        inc=await conn.fetch("SELECT id AS rid,from_user AS oid FROM friend_requests WHERE to_user=$1 ORDER BY created_at DESC",uid)
        for r in inc:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["oid"])
            if not o: continue
            item=user_public(o,uid);item["status"]="incoming";item["request_id"]=r["rid"];result.append(item)
        out=await conn.fetch("SELECT id AS rid,to_user AS oid FROM friend_requests WHERE from_user=$1 ORDER BY created_at DESC",uid)
        for r in out:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["oid"])
            if not o: continue
            item=user_public(o,uid);item["status"]="outgoing";item["request_id"]=r["rid"];result.append(item)
    def sk(x):
        prio={"incoming":0,"accepted":1,"outgoing":2}.get(x.get("status"),3)
        return (prio,not x.get("online"))
    result.sort(key=sk)
    return result

@app.post("/api/friends/request")
async def friends_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid or tid==user["id"] or tid==0: raise HTTPException(400,"Неверный user_id")
    p=await get_pool()
    async with p.acquire() as conn:
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

# ============ BLOCK ============
@app.post("/api/block/add")
async def block_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if not tid or tid==user["id"]: raise HTTPException(400,"Неверный")
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

# ============ DM ============
@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str,force:int=0):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        block_row=await conn.fetchrow("SELECT blocker,chat_cleared FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user["id"],user_id)
        if block_row:
            bm=(block_row["blocker"]==user["id"]);cl=block_row["chat_cleared"]
            if cl and not force: return {"blocked":True,"blocked_by_me":bm,"cleared":True,"messages":[],"user_id":user_id}
            rows=await conn.fetch("""SELECT d.*,u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.is_scam,u.title
                FROM dms d JOIN users u ON u.id=d.from_user
                WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC""",user["id"],user_id)
            out=[]
            for r in rows:
                dd=dict(r)
                for k in ("created_at","read_at","edited_at","expires_at"): dd[k]=_iso(dd.get(k))
                dd["reactions"]=_safe_json(dd.get("reactions"),{})
                out.append(dd)
            return {"blocked":True,"blocked_by_me":bm,"cleared":False,"messages":out,"user_id":user_id}
        rows=await conn.fetch("""SELECT d.*,u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.is_scam,u.title
            FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC""",user["id"],user_id)
        await conn.execute("UPDATE dms SET read_at=NOW() WHERE from_user=$1 AND to_user=$2 AND read_at IS NULL",user_id,user["id"])
    out=[]
    for r in rows:
        dd=dict(r)
        for k in ("created_at","read_at","edited_at","expires_at"): dd[k]=_iso(dd.get(k))
        dd["reactions"]=_safe_json(dd.get("reactions"),{})
        out.append(dd)
    return out

# ============ GROUPS ============
@app.get("/api/groups/list")
async def groups_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.*,gm.is_admin FROM groups g JOIN group_members gm ON gm.group_id=g.id WHERE gm.user_id=$1 ORDER BY COALESCE(g.last_message_at,g.created_at) DESC",user["id"])
    return [{"id":r["id"],"name":r["name"],"username":r["username"],"avatar":r["avatar"],"description":r["description"],"owner_id":r["owner_id"],"is_admin":r["is_admin"],"invite_code":r["invite_code"],"slow_mode":r["slow_mode"],"last_message_at":_iso(r["last_message_at"])} for r in rows]

@app.post("/api/groups/create")
async def groups_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя")
    p=await get_pool()
    async with p.acquire() as conn:
        code=secrets.token_urlsafe(6)[:10]
        g=await conn.fetchrow("INSERT INTO groups(name,avatar,description,owner_id,invite_code) VALUES($1,$2,$3,$4,$5) RETURNING *",name,data.get("avatar"),(data.get("description","") or "")[:256],user["id"],code)
        await conn.execute("INSERT INTO group_members(group_id,user_id,is_admin) VALUES($1,$2,TRUE)",g["id"],user["id"])
    return {"id":g["id"],"name":g["name"],"invite_code":code}

@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        rows=await conn.fetch("""SELECT gm.*,u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.is_scam
            FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 AND gm.thread_id IS NULL ORDER BY gm.id ASC""",group_id)
    out=[]
    for r in rows:
        d=dict(r)
        for k in ("created_at","edited_at"): d[k]=_iso(d.get(k))
        d["reactions"]=_safe_json(d.get("reactions"),{})
        out.append(d)
    return out

@app.post("/api/groups/leave")
async def group_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    if not gid: raise HTTPException(400,"group_id")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if g and g["owner_id"]==user["id"]: raise HTTPException(400,"Владелец не может выйти")
        await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
    return {"ok":True}

@app.post("/api/groups/{gid}/slow_mode")
async def group_slow_mode(gid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sec=int(data.get("seconds",0))
    if sec<0 or sec>SLOW_MODE_MAX_SECONDS: raise HTTPException(400,f"0-{SLOW_MODE_MAX_SECONDS}")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT is_admin FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет группы")
        if g["owner_id"]!=user["id"] and (not m or not m["is_admin"]): raise HTTPException(403,"Только админ")
        await conn.execute("UPDATE groups SET slow_mode=$1 WHERE id=$2",sec,gid)
    await manager.broadcast({"type":"slow_mode_set","group_id":gid,"seconds":sec})
    return {"ok":True,"seconds":sec}

@app.post("/api/groups/{gid}/bad_words")
async def group_bad_words(gid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    words=data.get("words") or []
    if not isinstance(words,list): raise HTTPException(400,"words[]")
    clean=[str(w).lower().strip()[:32] for w in words if str(w).strip()][:100]
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT is_admin FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет группы")
        if g["owner_id"]!=user["id"] and (not m or not m["is_admin"]): raise HTTPException(403,"Только админ")
        await conn.execute("UPDATE groups SET bad_words=$1 WHERE id=$2",json.dumps(clean),gid)
    return {"ok":True,"words":clean}

@app.get("/api/groups/{gid}/bad_words")
async def group_bad_words_get(gid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT bad_words FROM groups WHERE id=$1",gid)
    if not row: raise HTTPException(404,"Нет")
    return {"words":_safe_json(row["bad_words"],[])}

# ============ CHANNELS ============
@app.get("/api/channels/my")
async def channels_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT c.* FROM channels c JOIN channel_subscribers cs ON cs.channel_id=c.id WHERE cs.user_id=$1 ORDER BY c.id DESC""",user["id"])
        owned=await conn.fetch("SELECT * FROM channels WHERE owner_id=$1",user["id"])
    subs=[dict(r) for r in rows]
    for o in owned:
        od=dict(o)
        if not any(s["id"]==od["id"] for s in subs): subs.append(od)
    return [{"id":r["id"],"username":r["username"],"name":r["name"],"bio":r["bio"],"avatar":r["avatar"],"subscribers_count":r["subscribers_count"],"is_owner":r["owner_id"]==user["id"]} for r in subs]

@app.get("/api/channels/search")
async def channels_search(q:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip().lstrip("@")
    if len(q)<1: return []
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM channels WHERE (name ILIKE $1 OR username ILIKE $1) AND is_private=FALSE ORDER BY subscribers_count DESC LIMIT 25",f"%{q}%")
    return [{"id":r["id"],"username":r["username"],"name":r["name"],"bio":r["bio"],"avatar":r["avatar"],"subscribers_count":r["subscribers_count"]} for r in rows]

@app.get("/api/channels/catalog")
async def channels_catalog(category:str="",token:str=""):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if category:
            rows=await conn.fetch("SELECT * FROM channels WHERE is_private=FALSE AND category=$1 ORDER BY subscribers_count DESC LIMIT 50",category)
        else:
            rows=await conn.fetch("SELECT * FROM channels WHERE is_private=FALSE ORDER BY subscribers_count DESC LIMIT 50")
    return [{"id":r["id"],"username":r["username"],"name":r["name"],"bio":r["bio"],"avatar":r["avatar"],"category":r["category"],"subscribers_count":r["subscribers_count"]} for r in rows]

@app.post("/api/channels/create")
async def channels_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя")
    uname=(data.get("username") or "").strip().lower()
    if uname:
        ok,err=validate_username(uname)
        if not ok: raise HTTPException(400,err)
    p=await get_pool()
    async with p.acquire() as conn:
        if uname:
            u1=await conn.fetchval("SELECT 1 FROM users WHERE username=$1",uname)
            u2=await conn.fetchval("SELECT 1 FROM channels WHERE username=$1",uname)
            u3=await conn.fetchval("SELECT 1 FROM groups WHERE username=$1",uname)
            if u1 or u2 or u3: raise HTTPException(409,"Username занят")
        c=await conn.fetchrow("""INSERT INTO channels(username,name,bio,avatar,owner_id,is_private,category)
            VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
            uname or None,name,(data.get("bio") or "")[:256],data.get("avatar"),user["id"],
            bool(data.get("is_private",False)),(data.get("category") or "")[:32])
        await conn.execute("INSERT INTO channel_admins(channel_id,user_id,perms) VALUES($1,$2,$3)",c["id"],user["id"],json.dumps({"post":True,"edit":True,"delete":True,"ban":True,"add_members":True}))
    return {"id":c["id"],"username":c["username"],"name":c["name"]}

@app.get("/api/channels/{cid}")
async def channel_get(cid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT * FROM channels WHERE id=$1",cid)
        if not c: raise HTTPException(404,"Нет канала")
        is_sub=await conn.fetchval("SELECT 1 FROM channel_subscribers WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        is_adm=await conn.fetchval("SELECT 1 FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        is_banned=await conn.fetchval("SELECT 1 FROM channel_bans WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        is_owner=c["owner_id"]==user["id"]
    return {"id":c["id"],"username":c["username"],"name":c["name"],"bio":c["bio"],"avatar":c["avatar"],"banner":c["banner"],
        "avatar_pos":c["avatar_pos"],"banner_pos":c["banner_pos"],"is_private":c["is_private"],"category":c["category"],
        "subscribers_count":c["subscribers_count"],"is_owner":is_owner,"is_admin":bool(is_adm) or is_owner,
        "is_subscribed":bool(is_sub),"is_banned":bool(is_banned),"linked_group_id":c["linked_group_id"]}

@app.post("/api/channels/{cid}/subscribe")
async def channel_subscribe(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchval("SELECT 1 FROM channel_bans WHERE channel_id=$1 AND user_id=$2",cid,user["id"]): raise HTTPException(403,"Забанен")
        try: await conn.execute("INSERT INTO channel_subscribers(channel_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",cid,user["id"])
        except: pass
        await conn.execute("UPDATE channels SET subscribers_count=(SELECT COUNT(*) FROM channel_subscribers WHERE channel_id=$1) WHERE id=$1",cid)
    return {"ok":True}

@app.post("/api/channels/{cid}/unsubscribe")
async def channel_unsubscribe(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM channel_subscribers WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        await conn.execute("UPDATE channels SET subscribers_count=(SELECT COUNT(*) FROM channel_subscribers WHERE channel_id=$1) WHERE id=$1",cid)
    return {"ok":True}

@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid:int,token:str,limit:int=50,before_id:int=0):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if before_id>0:
            rows=await conn.fetch("SELECT p.*,u.username AS author_name FROM channel_posts p LEFT JOIN users u ON u.id=p.author_id WHERE p.channel_id=$1 AND p.id<$2 ORDER BY p.pinned DESC,p.id DESC LIMIT $3",cid,before_id,limit)
        else:
            rows=await conn.fetch("SELECT p.*,u.username AS author_name FROM channel_posts p LEFT JOIN users u ON u.id=p.author_id WHERE p.channel_id=$1 ORDER BY p.pinned DESC,p.id DESC LIMIT $2",cid,limit)
    return [{"id":r["id"],"text":r["text"],"media_urls":_safe_json(r["media_urls"],[]),"media_kind":r["media_kind"],"reactions":_safe_json(r["reactions"],{}),"pinned":r["pinned"],"views":r["views"],"edited":r["edited"],"comments_count":r["comments_count"],"author_name":r["author_name"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/channels/{cid}/post")
async def channel_post(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        if not adm: raise HTTPException(403,"Не админ канала")
        perms=_safe_json(adm["perms"],{})
        if not perms.get("post"): raise HTTPException(403,"Нет права post")
        text=(data.get("text") or "")[:MAX_TEXT]
        media=data.get("media_urls") or []
        if not isinstance(media,list): media=[]
        media=media[:10]
        kind=(data.get("media_kind") or "text")[:16]
        if not text and not media: raise HTTPException(400,"Пусто")
        r=await conn.fetchrow("""INSERT INTO channel_posts(channel_id,author_id,text,media_urls,media_kind)
            VALUES($1,$2,$3,$4,$5) RETURNING *""",cid,user["id"],text,json.dumps(media),kind)
        subs=await conn.fetch("SELECT user_id FROM channel_subscribers WHERE channel_id=$1 AND (muted_until IS NULL OR muted_until<NOW())",cid)
    payload={"type":"channel_post","channel_id":cid,"post_id":r["id"],"text":text,"media_urls":media,"media_kind":kind,"created_at":_iso(r["created_at"])}
    for s in subs:
        if s["user_id"]!=user["id"]:
            await manager.send_to(s["user_id"],payload)
    return {"ok":True,"post_id":r["id"]}

@app.post("/api/channels/{cid}/posts/{pid}/delete")
async def channel_post_delete(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        if not adm: raise HTTPException(403,"Не админ")
        # удалить медиа-файлы поста
        row=await conn.fetchrow("SELECT media_urls FROM channel_posts WHERE id=$1 AND channel_id=$2",pid,cid)
        if row:
            for u in _safe_json(row["media_urls"],[]):
                delete_uploaded_file(u)
        await conn.execute("DELETE FROM channel_posts WHERE id=$1 AND channel_id=$2",pid,cid)
    return {"ok":True}

@app.post("/api/channels/{cid}/posts/{pid}/pin")
async def channel_post_pin(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        if not adm: raise HTTPException(403,"Не админ")
        cur=await conn.fetchval("SELECT pinned FROM channel_posts WHERE id=$1",pid)
        await conn.execute("UPDATE channel_posts SET pinned=$1 WHERE id=$2",not cur,pid)
    return {"ok":True}

@app.post("/api/channels/{cid}/posts/{pid}/react")
async def channel_post_react(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    emoji=(data.get("emoji") or "👍")[:8]
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions FROM channel_posts WHERE id=$1",pid)
        if not row: raise HTTPException(404,"Нет поста")
        rx=_safe_json(row["reactions"],{})
        arr=rx.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        if arr: rx[emoji]=arr
        else:
            try: del rx[emoji]
            except: pass
        await conn.execute("UPDATE channel_posts SET reactions=$1 WHERE id=$2",json.dumps(rx),pid)
    return {"ok":True,"reactions":rx}

@app.post("/api/channels/{cid}/posts/{pid}/view")
async def channel_post_view(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        try:
            await conn.execute("INSERT INTO channel_post_views(post_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",pid,user["id"])
            await conn.execute("UPDATE channel_posts SET views=(SELECT COUNT(*) FROM channel_post_views WHERE post_id=$1) WHERE id=$1",pid)
        except: pass
    return {"ok":True}

@app.post("/api/channels/{cid}/edit")
async def channel_edit(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c: raise HTTPException(404,"Нет")
        if c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        fields=[];params=[];idx=1
        for k in ["name","bio","avatar","banner","avatar_pos","banner_pos","category"]:
            if k in data and data[k] is not None:
                fields.append(f"{k}=${idx}");params.append(str(data[k])[:512]);idx+=1
        if "is_private" in data:
            fields.append(f"is_private=${idx}");params.append(bool(data["is_private"]));idx+=1
        if not fields: raise HTTPException(400,"Нечего менять")
        params.append(cid)
        await conn.execute(f"UPDATE channels SET {','.join(fields)} WHERE id=${idx}",*params)
    return {"ok":True}

@app.post("/api/channels/{cid}/upload_avatar")
async def channel_upload_avatar(cid:int,token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400,"Картинка")
    content=await file.read()
    if len(content)>5*1024*1024: raise HTTPException(400,"Макс 5 МБ")
    saved=save_uploaded_file(content,file.filename or "ch_av.png",file.content_type,"channel_avatar")
    async with p.acquire() as conn:
        old=await conn.fetchval("SELECT avatar FROM channels WHERE id=$1",cid)
        if old: delete_uploaded_file(old)
        await conn.execute("UPDATE channels SET avatar=$1 WHERE id=$2",saved["url"],cid)
    return {"ok":True,"url":saved["url"]}

@app.post("/api/channels/{cid}/upload_banner")
async def channel_upload_banner(cid:int,token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400,"Картинка")
    content=await file.read()
    if len(content)>8*1024*1024: raise HTTPException(400,"Макс 8 МБ")
    saved=save_uploaded_file(content,file.filename or "ch_bn.png",file.content_type,"channel_banner")
    async with p.acquire() as conn:
        old=await conn.fetchval("SELECT banner FROM channels WHERE id=$1",cid)
        if old: delete_uploaded_file(old)
        await conn.execute("UPDATE channels SET banner=$1 WHERE id=$2",saved["url"],cid)
    return {"ok":True,"url":saved["url"]}

@app.post("/api/channels/{cid}/change_username")
async def channel_change_username(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    new_u=(data.get("new_username") or "").strip().lower()
    ok,err=validate_username(new_u)
    if not ok: raise HTTPException(400,err)
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id,username_changed_at FROM channels WHERE id=$1",cid)
        if not c: raise HTTPException(404,"Нет")
        if c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        if c["username_changed_at"]:
            delta=(datetime.datetime.now(datetime.timezone.utc)-_aware(c["username_changed_at"])).total_seconds()
            if delta<86400: raise HTTPException(429,f"Можно менять раз в 24ч. Осталось {int((86400-delta)/3600)}ч")
        u1=await conn.fetchval("SELECT 1 FROM users WHERE username=$1",new_u)
        if u1: raise HTTPException(409,"Занято юзером")
        u2=await conn.fetchval("SELECT 1 FROM channels WHERE username=$1 AND id!=$2",new_u,cid)
        if u2: raise HTTPException(409,"Занято каналом")
        u3=await conn.fetchval("SELECT 1 FROM groups WHERE username=$1",new_u)
        if u3: raise HTTPException(409,"Занято группой")
        await conn.execute("UPDATE channels SET username=$1,username_changed_at=NOW() WHERE id=$2",new_u,cid)
    return {"ok":True,"username":new_u}

@app.post("/api/channels/{cid}/delete")
async def channel_delete(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id,avatar,banner FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        if c["avatar"]: delete_uploaded_file(c["avatar"])
        if c["banner"]: delete_uploaded_file(c["banner"])
        posts=await conn.fetch("SELECT media_urls FROM channel_posts WHERE channel_id=$1",cid)
        for p2 in posts:
            for u in _safe_json(p2["media_urls"],[]):
                delete_uploaded_file(u)
        await conn.execute("DELETE FROM channels WHERE id=$1",cid)
    return {"ok":True}

# ============ CHANNEL COMMENTS ============
@app.get("/api/channels/{cid}/posts/{pid}/comments")
async def post_comments(cid:int,pid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT linked_group_id FROM channels WHERE id=$1",cid)
        if not c or not c["linked_group_id"]: return {"comments":[],"group_id":None}
        rows=await conn.fetch("""SELECT gm.*,u.username,u.display_name,u.avatar,u.gif_avatar FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 AND gm.post_id=$2 ORDER BY gm.id ASC""",c["linked_group_id"],pid)
    return {"comments":[{"id":r["id"],"text":r["text"],"reply_to_id":r["reply_to_id"],"as_channel":r["as_channel"],"username":r["username"],"display_name":r["display_name"],"avatar":r["gif_avatar"] or r["avatar"],"created_at":_iso(r["created_at"])} for r in rows],"group_id":c["linked_group_id"]}

@app.post("/api/channels/{cid}/posts/{pid}/comment")
async def post_comment(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    text=(data.get("text") or "")[:MAX_TEXT]
    if not text: raise HTTPException(400,"Текст")
    reply_to=data.get("reply_to_id") or None
    as_channel=bool(data.get("as_channel",False))
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT linked_group_id FROM channels WHERE id=$1",cid)
        if not c or not c["linked_group_id"]: raise HTTPException(400,"Обсуждение не включено")
        if as_channel:
            adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
            if not adm: raise HTTPException(403,"Только админ")
        try: await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",c["linked_group_id"],user["id"])
        except: pass
        msg=await conn.fetchrow("""INSERT INTO group_messages(group_id,user_id,text,post_id,reply_to_id,as_channel)
            VALUES($1,$2,$3,$4,$5,$6) RETURNING *""",c["linked_group_id"],user["id"],text,pid,reply_to,as_channel)
        await conn.execute("UPDATE channel_posts SET comments_count=(SELECT COUNT(*) FROM group_messages WHERE post_id=$1) WHERE id=$1",pid)
        members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",c["linked_group_id"])
    payload={"type":"group_msg","id":msg["id"],"group_id":c["linked_group_id"],"user_id":user["id"],"username":user["username"],"display_name":user.get("display_name") or user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"text":text,"post_id":pid,"reply_to_id":reply_to,"as_channel":as_channel,"created_at":_iso(msg["created_at"])}
    for m in members:
        if m["user_id"]!=user["id"]: await manager.send_to(m["user_id"],payload)
    return {"ok":True,"comment_id":msg["id"]}

# ============ CHANNEL DISCUSSION ============
@app.post("/api/channels/{cid}/discussion/enable")
async def discussion_enable(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id,name FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        gid=int(data.get("group_id",0))
        if not gid:
            code=secrets.token_urlsafe(6)[:10]
            g=await conn.fetchrow("INSERT INTO groups(name,owner_id,invite_code) VALUES($1,$2,$3) RETURNING id",f"Обсуждение: {c['name']}",user["id"],code)
            gid=g["id"]
            await conn.execute("INSERT INTO group_members(group_id,user_id,is_admin) VALUES($1,$2,TRUE)",gid,user["id"])
        await conn.execute("UPDATE channels SET linked_group_id=$1 WHERE id=$2",gid,cid)
    return {"ok":True,"group_id":gid}

@app.post("/api/channels/{cid}/discussion/disable")
async def discussion_disable(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("UPDATE channels SET linked_group_id=NULL WHERE id=$1",cid)
    return {"ok":True}

@app.get("/api/check_channel_username")
async def check_channel_username(u:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    u=(u or "").lower().strip()
    if len(u)<4: return {"available":False,"reason":"Мин 4"}
    if len(u)>32: return {"available":False,"reason":"Макс 32"}
    if not re.match(r'^[a-z][a-z0-9_]*$',u): return {"available":False,"reason":"Только a-z, 0-9, _"}
    if u in RESERVED_USERNAMES: return {"available":False,"reason":"Зарезервировано"}
    p=await get_pool()
    async with p.acquire() as conn:
        u1=await conn.fetchval("SELECT 1 FROM users WHERE username=$1",u)
        if u1: return {"available":False,"reason":"Занято юзером"}
        u2=await conn.fetchval("SELECT 1 FROM channels WHERE username=$1",u)
        if u2: return {"available":False,"reason":"Занято каналом"}
        u3=await conn.fetchval("SELECT 1 FROM groups WHERE username=$1",u)
        if u3: return {"available":False,"reason":"Занято группой"}
    return {"available":True}

# ============ MESSAGES: edit/delete/reaction ============
@app.post("/api/messages/edit")
async def message_edit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    text=(data.get("text") or "")[:MAX_TEXT]
    chat_type=data.get("chat_type","dm")
    if not mid or not text: raise HTTPException(400,"message_id и text")
    p=await get_pool()
    async with p.acquire() as conn:
        if chat_type=="dm":
            await conn.execute("UPDATE dms SET text=$1,edited_at=NOW() WHERE id=$2 AND from_user=$3",text,mid,user["id"])
        else:
            await conn.execute("UPDATE group_messages SET text=$1,edited_at=NOW() WHERE id=$2 AND user_id=$3",text,mid,user["id"])
    return {"ok":True}

@app.post("/api/messages/delete_for_all")
async def message_delete_for_all(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    chat_type=data.get("chat_type","dm")
    if not mid: raise HTTPException(400,"message_id")
    p=await get_pool()
    async with p.acquire() as conn:
        if chat_type=="dm":
            row=await conn.fetchrow("SELECT file_url FROM dms WHERE id=$1 AND from_user=$2",mid,user["id"])
            if row and row["file_url"]: delete_uploaded_file(row["file_url"])
            await conn.execute("UPDATE dms SET text='[удалено]',file_url=NULL,deleted_for_all=TRUE WHERE id=$1 AND from_user=$2",mid,user["id"])
        else:
            row=await conn.fetchrow("SELECT file_url FROM group_messages WHERE id=$1 AND user_id=$2",mid,user["id"])
            if row and row["file_url"]: delete_uploaded_file(row["file_url"])
            await conn.execute("UPDATE group_messages SET text='[удалено]',file_url=NULL WHERE id=$1 AND user_id=$2",mid,user["id"])
    await manager.broadcast({"type":"message_edited","id":mid,"text":"[удалено]"})
    return {"ok":True}

@app.post("/api/messages/reaction")
async def message_reaction(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    emoji=(data.get("emoji") or "👍")[:32]
    chat_type=data.get("chat_type","dm")
    if not mid: raise HTTPException(400,"message_id")
    p=await get_pool()
    async with p.acquire() as conn:
        if chat_type=="dm":
            row=await conn.fetchrow("SELECT reactions FROM dms WHERE id=$1",mid)
            if not row: raise HTTPException(404,"Нет")
            rx=_safe_json(row["reactions"],{})
            arr=rx.get(emoji,[])
            if user["id"] in arr: arr.remove(user["id"])
            else: arr.append(user["id"])
            if arr: rx[emoji]=arr
            else:
                try: del rx[emoji]
                except: pass
            await conn.execute("UPDATE dms SET reactions=$1 WHERE id=$2",json.dumps(rx),mid)
        else:
            row=await conn.fetchrow("SELECT reactions FROM group_messages WHERE id=$1",mid)
            if not row: raise HTTPException(404,"Нет")
            rx=_safe_json(row["reactions"],{})
            arr=rx.get(emoji,[])
            if user["id"] in arr: arr.remove(user["id"])
            else: arr.append(user["id"])
            if arr: rx[emoji]=arr
            else:
                try: del rx[emoji]
                except: pass
            await conn.execute("UPDATE group_messages SET reactions=$1 WHERE id=$2",json.dumps(rx),mid)
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":rx,"chat_type":chat_type})
    return {"ok":True,"reactions":rx}

@app.post("/api/messages/disappearing")
async def message_disappearing(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    chat_type=data.get("chat_type","dm")
    chat_id=int(data.get("chat_id",0))
    message_id=int(data.get("message_id",0))
    seconds=int(data.get("seconds",0))
    if seconds<5 or seconds>86400: raise HTTPException(400,"5-86400 сек")
    if not message_id or not chat_id: raise HTTPException(400,"message_id и chat_id")
    expires_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=seconds)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO disappearing_messages(chat_type,chat_id,message_id,expires_at) VALUES($1,$2,$3,$4)",chat_type,chat_id,message_id,expires_at)
        if chat_type=="dm":
            await conn.execute("UPDATE dms SET expires_at=$1 WHERE id=$2",expires_at,message_id)
    return {"ok":True,"expires_at":_iso(expires_at)}

# ============ CHATS: pin/archive/mute ============
@app.post("/api/chats/pin")
async def chat_pin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ct=data.get("chat_type","dm");cid=int(data.get("chat_id",0))
    if not cid: raise HTTPException(400,"chat_id")
    p=await get_pool()
    async with p.acquire() as conn:
        existing=await conn.fetchrow("SELECT id,pinned FROM user_chat_settings WHERE user_id=$1 AND chat_type=$2 AND chat_id=$3",user["id"],ct,cid)
        if existing:
            await conn.execute("UPDATE user_chat_settings SET pinned=$1 WHERE id=$2",not existing["pinned"],existing["id"])
            new_val=not existing["pinned"]
        else:
            await conn.execute("INSERT INTO user_chat_settings(user_id,chat_type,chat_id,pinned) VALUES($1,$2,$3,TRUE)",user["id"],ct,cid)
            new_val=True
    return {"ok":True,"pinned":new_val}

@app.post("/api/chats/archive")
async def chat_archive(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ct=data.get("chat_type","dm");cid=int(data.get("chat_id",0))
    if not cid: raise HTTPException(400,"chat_id")
    p=await get_pool()
    async with p.acquire() as conn:
        existing=await conn.fetchrow("SELECT id,archived FROM user_chat_settings WHERE user_id=$1 AND chat_type=$2 AND chat_id=$3",user["id"],ct,cid)
        if existing:
            await conn.execute("UPDATE user_chat_settings SET archived=$1 WHERE id=$2",not existing["archived"],existing["id"])
            new_val=not existing["archived"]
        else:
            await conn.execute("INSERT INTO user_chat_settings(user_id,chat_type,chat_id,archived) VALUES($1,$2,$3,TRUE)",user["id"],ct,cid)
            new_val=True
    return {"ok":True,"archived":new_val}

@app.post("/api/chats/mute")
async def chat_mute(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ct=data.get("chat_type","dm");cid=int(data.get("chat_id",0));minutes=int(data.get("minutes",0))
    if not cid: raise HTTPException(400,"chat_id")
    p=await get_pool()
    async with p.acquire() as conn:
        existing=await conn.fetchrow("SELECT id FROM user_chat_settings WHERE user_id=$1 AND chat_type=$2 AND chat_id=$3",user["id"],ct,cid)
        if existing:
            if minutes<=0: await conn.execute("UPDATE user_chat_settings SET mute_until=NULL WHERE id=$1",existing["id"])
            else: await conn.execute("UPDATE user_chat_settings SET mute_until=NOW()+INTERVAL '1 minute' * $1 WHERE id=$2",minutes,existing["id"])
        else:
            if minutes>0: await conn.execute("INSERT INTO user_chat_settings(user_id,chat_type,chat_id,mute_until) VALUES($1,$2,$3,NOW()+INTERVAL '1 minute' * $4)",user["id"],ct,cid,minutes)
    return {"ok":True}

# ============ DRAFTS ============
@app.post("/api/chat/draft")
async def chat_draft(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ct=data.get("chat_type","dm");cid=int(data.get("chat_id",0));text=(data.get("text") or "")[:MAX_TEXT]
    p=await get_pool()
    async with p.acquire() as conn:
        if text:
            await conn.execute("INSERT INTO chat_drafts(user_id,chat_type,chat_id,text) VALUES($1,$2,$3,$4) ON CONFLICT(user_id,chat_type,chat_id) DO UPDATE SET text=$4,updated_at=NOW()",user["id"],ct,cid,text)
        else:
            await conn.execute("DELETE FROM chat_drafts WHERE user_id=$1 AND chat_type=$2 AND chat_id=$3",user["id"],ct,cid)
    return {"ok":True}

@app.get("/api/chat/draft/{ct}/{cid}")
async def chat_draft_get(ct:str,cid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT text FROM chat_drafts WHERE user_id=$1 AND chat_type=$2 AND chat_id=$3",user["id"],ct,cid)
    return {"text":row["text"] if row else ""}

# ============ UPLOAD ============
@app.post("/api/upload")
async def upload(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    lim=50*1024*1024 if is_premium(user) else 10*1024*1024
    mime=(file.content_type or "application/octet-stream").lower()
    if mime not in ALLOWED_MIME: raise HTTPException(400,f"Тип: {mime}")
    ext=os.path.splitext(file.filename or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT: raise HTTPException(400,f"Расш.: {ext}")
    content=await file.read()
    if len(content)>lim: raise HTTPException(400,f">{lim//1024//1024} МБ")
    category=_detect_category(mime,file.filename or "")
    saved=save_uploaded_file(content,file.filename or "file",mime,category)
    return {"url":saved["url"],"size":saved["size"],"mime":saved["mime"],"name":saved["name"]}

@app.post("/api/upload_voice")
async def upload_voice(token:str=Form(...),file:UploadFile=File(...),duration:int=Form(0)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("audio/"): raise HTTPException(400,"Аудио")
    content=await file.read()
    if len(content)>5*1024*1024: raise HTTPException(400,"Макс 5 МБ")
    saved=save_uploaded_file(content,file.filename or "voice.webm",file.content_type,"voice")
    if duration<1: duration=1
    if duration>300: duration=300
    await grant_achievement(user["id"],"first_voice")
    return {"url":saved["url"],"duration":duration,"size":saved["size"]}

@app.post("/api/upload_video_note")
async def upload_video_note(token:str=Form(...),file:UploadFile=File(...),duration:int=Form(0)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("video/"): raise HTTPException(400,"Видео")
    content=await file.read()
    if len(content)>8*1024*1024: raise HTTPException(400,"Макс 8 МБ")
    saved=save_uploaded_file(content,file.filename or "vnote.webm",file.content_type,"vnote")
    if duration<1: duration=1
    if duration>60: duration=60
    return {"url":saved["url"],"duration":duration,"size":saved["size"]}

# ============ GIFTS / FRAMES / TITLES / PREMIUM / COINS ============
@app.get("/api/gifts/all")
async def gifts_all():
    g=await get_all_gifts()
    return [{"gift_id":k,"name":v["name"],"emoji":v.get("emoji"),"price":v["price"]} for k,v in g.items()]

@app.post("/api/gifts/send")
async def gift_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    gift=g[gift_id];price=gift["price"]
    if user.get("coins",0)<price: raise HTTPException(400,"Мало коинов")
    to_id=int(data.get("to_user",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",price,user["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],to_id,gift_id)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1",user["id"])
    if cnt==1: await grant_achievement(user["id"],"first_gift")
    await manager.send_to(to_id,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"from_name":user.get("display_name") or user["username"]})
    return {"ok":True}

@app.get("/api/coins/balance")
async def coins_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"coins":user.get("coins",0),"candy":user.get("candy",0)}

@app.post("/api/premium/buy")
async def premium_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan","month")
    if plan not in PREMIUM_PRICES: raise HTTPException(400,"План?")
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

@app.get("/api/titles/list")
async def titles_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM titles_catalog WHERE is_public=TRUE OR creator_id=$1 ORDER BY id DESC",user["id"])
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"creator_id":r["creator_id"]} for r in rows]

@app.post("/api/titles/set")
async def titles_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    title_id=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",title_id)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",t["name"],user["id"])
    return {"ok":True}

@app.post("/api/titles/create")
async def titles_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:20]
    if not name: raise HTTPException(400,"Название")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO titles_catalog(name,emoji,color,is_public,creator_id) VALUES($1,$2,$3,FALSE,$4) RETURNING id",name,(data.get("emoji") or "⭐")[:8],(data.get("color") or "#22c55e")[:32],user["id"])
    return {"ok":True,"id":r["id"]}

@app.get("/api/frames/list")
async def frames_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM frames_catalog ORDER BY price_coins")
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

# ============ SUPPORT / CALLS / CHANGELOG ============
@app.post("/api/support/ticket")
async def support_ticket(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    t_type=(data.get("ticket_type") or "other").strip()[:32]
    desc=(data.get("description") or "")[:2000]
    if not desc: raise HTTPException(400,"Опиши")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("INSERT INTO support_tickets(from_user,ticket_type,title,description) VALUES($1,$2,$3,$4) RETURNING id",user["id"],t_type,(data.get("title") or "")[:128],desc)
    return {"ok":True,"ticket_id":row["id"]}

@app.get("/api/calls/history")
async def calls_history(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT ch.*,c.username AS cu,c.display_name AS cd,e.username AS eu,e.display_name AS ed FROM call_history ch LEFT JOIN users c ON c.id=ch.caller LEFT JOIN users e ON e.id=ch.callee WHERE ch.caller=$1 OR ch.callee=$1 ORDER BY ch.id DESC LIMIT 50""",user["id"])
    return [{"id":r["id"],"caller":r["caller"],"callee":r["callee"],"caller_name":r["cd"] or r["cu"],"callee_name":r["ed"] or r["eu"],"call_type":r["call_type"],"duration":r["duration"],"created_at":_iso(r["created_at"])} for r in rows]

# ============ SKINS ============
@app.get("/api/skins/catalog")
async def skins_catalog(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        sk=await conn.fetchrow("SELECT active_skin,owned FROM user_skins WHERE user_id=$1",user["id"])
        owned=_safe_json(sk["owned"],["default"]) if sk else ["default"]
        active=sk["active_skin"] if sk else "default"
    return {"catalog":SKINS_CATALOG,"owned":owned,"active":active}

@app.post("/api/skins/buy")
async def skins_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=data.get("skin_id")
    sk=next((s for s in SKINS_CATALOG if s["id"]==sid),None)
    if not sk: raise HTTPException(404,"Нет скина")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT owned FROM user_skins WHERE user_id=$1",user["id"])
        owned=_safe_json(row["owned"],["default"]) if row else ["default"]
        if sid in owned: raise HTTPException(400,"Уже есть")
        if sk["price"]>0:
            if (user.get("coins") or 0)<sk["price"]: raise HTTPException(400,"Мало")
            await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",sk["price"],user["id"])
        owned.append(sid)
        await conn.execute("INSERT INTO user_skins(user_id,active_skin,owned) VALUES($1,'default',$2) ON CONFLICT(user_id) DO UPDATE SET owned=$2",user["id"],json.dumps(owned))
    return {"ok":True}

@app.post("/api/skins/set")
async def skins_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=data.get("skin_id","default")
    if not any(s["id"]==sid for s in SKINS_CATALOG): raise HTTPException(404,"Нет скина")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT owned FROM user_skins WHERE user_id=$1",user["id"])
        owned=_safe_json(row["owned"],["default"]) if row else ["default"]
        if sid not in owned: raise HTTPException(403,"Не куплен")
        await conn.execute("INSERT INTO user_skins(user_id,active_skin) VALUES($1,$2) ON CONFLICT(user_id) DO UPDATE SET active_skin=$2,updated_at=NOW()",user["id"],sid)
    return {"ok":True}

# ============ LINK PREVIEW ============
@app.get("/api/link_preview")
async def link_preview(url:str):
    if not url or not url.startswith(("http://","https://")): raise HTTPException(400,"URL")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM link_previews WHERE url=$1",url)
        if row: return {"title":row["title"],"description":row["description"],"image":row["image"],"site_name":row["site_name"]}
    title="";desc="";img="";site=""
    try:
        async with httpx.AsyncClient(timeout=5,follow_redirects=True) as cl:
            resp=await cl.get(url,headers={"User-Agent":"Mozilla/5.0 BelugaCordBot"})
            html=resp.text[:50000]
            m=re.search(r'<title[^>]*>([^<]+)</title>',html,re.I)
            if m: title=m.group(1).strip()[:256]
            m=re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',html,re.I)
            if m: desc=m.group(1).strip()[:1000]
            m=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',html,re.I)
            if m: img=m.group(1).strip()[:512]
            m=re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)',html,re.I)
            if m: site=m.group(1).strip()[:64]
        async with p.acquire() as conn:
            await conn.execute("""INSERT INTO link_previews(url,title,description,image,site_name) VALUES($1,$2,$3,$4,$5)
                ON CONFLICT(url) DO UPDATE SET title=$2,description=$3,image=$4,site_name=$5,fetched_at=NOW()""",url,title,desc,img,site)
    except Exception as e: print(f"[link_preview] {e}")
    return {"title":title,"description":desc,"image":img,"site_name":site}

# ============ SEARCH MESSAGES ============
@app.get("/api/search/messages")
async def search_messages(token:str,q:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip()
    if len(q)<2: return {"dm":[],"groups":[]}
    p=await get_pool()
    async with p.acquire() as conn:
        dm_rows=await conn.fetch("""SELECT id,from_user,to_user,text,created_at FROM dms
            WHERE (from_user=$1 OR to_user=$1) AND text ILIKE $2 ORDER BY id DESC LIMIT 50""",user["id"],f"%{q}%")
        grp_rows=await conn.fetch("""SELECT gm.id,gm.group_id,gm.user_id,gm.text,gm.created_at FROM group_messages gm
            JOIN group_members gmem ON gmem.group_id=gm.group_id AND gmem.user_id=$1
            WHERE gm.text ILIKE $2 ORDER BY gm.id DESC LIMIT 50""",user["id"],f"%{q}%")
    return {"dm":[{"id":r["id"],"from_user":r["from_user"],"to_user":r["to_user"],"text":r["text"],"created_at":_iso(r["created_at"])} for r in dm_rows],
            "groups":[{"id":r["id"],"group_id":r["group_id"],"user_id":r["user_id"],"text":r["text"],"created_at":_iso(r["created_at"])} for r in grp_rows]}

# ============ REFERRALS ============
@app.post("/api/referral/create")
async def referral_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    owner_id=int(data.get("owner_id",0))
    if not owner_id: raise HTTPException(400,"owner_id")
    p=await get_pool()
    async with p.acquire() as conn:
        target=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",owner_id)
        if not target: raise HTTPException(404,"Юзер не найден")
        existing=await conn.fetchrow("SELECT code FROM referrals WHERE owner_id=$1",owner_id)
        if existing: return {"ok":True,"code":existing["code"],"existing":True,"owner_username":target["username"]}
        code=secrets.token_urlsafe(8)[:10]
        await conn.execute("INSERT INTO referrals(code,owner_id) VALUES($1,$2)",code,owner_id)
    return {"ok":True,"code":code,"owner_username":target["username"]}

@app.get("/api/referral/list")
async def referral_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT r.*,u.username AS owner_username,u.display_name AS owner_display
            FROM referrals r JOIN users u ON u.id=r.owner_id ORDER BY r.id DESC""")
    return [{"id":r["id"],"code":r["code"],"owner_id":r["owner_id"],"owner_username":r["owner_username"],
             "owner_display":r["owner_display"],"clicks":r["clicks"],"registrations":r["registrations"],
             "created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/referral/delete")
async def referral_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    rid=int(data.get("id",0))
    if not rid: raise HTTPException(400,"id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM referrals WHERE id=$1",rid)
    return {"ok":True}

@app.post("/api/referral/click")
async def referral_click(data:dict):
    code=(data.get("code") or "").strip()
    if not code: raise HTTPException(400,"code")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE referrals SET clicks=clicks+1 WHERE code=$1",code)
    return {"ok":True}

# ============ GOODRA LINK/SYNC ============
@app.post("/api/goodra/link")
async def goodra_link(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if not GOODRA_ENABLED: raise HTTPException(503,"Goodra World не подключён")
    gw_user=(data.get("goodra_username") or "").strip()
    if not gw_user: raise HTTPException(400,"goodra_username")
    try:
        async with httpx.AsyncClient(timeout=8) as cl:
            r=await cl.post(GOODRA_API_URL.rstrip("/")+"/api/link",
                headers={"Authorization":f"Bearer {GOODRA_API_KEY}"},
                json={"beluga_id":user["id"],"beluga_username":user["username"],"goodra_username":gw_user})
            if r.status_code!=200: raise HTTPException(400,f"Goodra: {r.status_code}")
            resp=r.json()
    except httpx.HTTPError as e: raise HTTPException(502,f"Goodra недоступен: {e}")
    return {"ok":True,"goodra_user":resp.get("user",{}),"linked":True}

@app.post("/api/goodra/sync")
async def goodra_sync(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if not GOODRA_ENABLED: raise HTTPException(503,"Goodra World не подключён")
    payload={"beluga_id":user["id"],"username":user["username"],"display_name":user.get("display_name"),
             "level":user.get("level",1),"xp":user.get("xp",0),"coins":user.get("coins",0),"messages_count":user.get("messages_count",0)}
    try:
        async with httpx.AsyncClient(timeout=8) as cl:
            r=await cl.post(GOODRA_API_URL.rstrip("/")+"/api/sync",headers={"Authorization":f"Bearer {GOODRA_API_KEY}"},json=payload)
            if r.status_code!=200: raise HTTPException(400,f"Goodra: {r.status_code}")
    except httpx.HTTPError as e: raise HTTPException(502,f"Goodra недоступен: {e}")
    return {"ok":True}
# ========== BELUGACORD 4.5 BETA — SERVER PART 3/3 ==========

# ============ TURN / ICE ============
TURN_URLS=[u.strip() for u in (os.environ.get("TURN_URLS","") or "").split(",") if u.strip()]
TURN_USERNAME=os.environ.get("TURN_USERNAME","")
TURN_PASSWORD=os.environ.get("TURN_PASSWORD","")
TURN_SECRET=os.environ.get("TURN_SECRET","")

@app.get("/api/ice")
async def ice_servers(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    servers=[{"urls":"stun:stun.l.google.com:19302"},{"urls":"stun:stun1.l.google.com:19302"}]
    if TURN_URLS and TURN_USERNAME and TURN_PASSWORD:
        servers.append({"urls":TURN_URLS,"username":TURN_USERNAME,"credential":TURN_PASSWORD})
    elif TURN_SECRET and TURN_URLS:
        import hmac,base64
        ttl=3600
        expiry=int(time.time())+ttl
        turn_user=f"{expiry}:{user['id']}"
        cred=base64.b64encode(hmac.new(TURN_SECRET.encode(),turn_user.encode(),hashlib.sha1).digest()).decode()
        servers.append({"urls":TURN_URLS,"username":turn_user,"credential":cred})
    return {"iceServers":servers}

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

            # PING
            if t=="ping":
                try: await ws.send_json({"type":"pong"})
                except: pass
                continue

            # проверка мута / авиарежима для отправки
            is_muted=False
            if user.get("mute_until"):
                try:
                    mu=_aware(user["mute_until"])
                    if mu and mu>datetime.datetime.now(datetime.timezone.utc): is_muted=True
                except: pass
            if t in ("dm","group_msg") and is_muted:
                await manager.send_to(uid,{"type":"muted","reason":"Ты в муте"})
                continue
            if t in ("dm","group_msg") and user.get("airplane_mode"):
                await manager.send_to(uid,{"type":"error","detail":"✈️ Авиарежим"})
                continue

            # ========== ЗВОНКИ ==========
            if t=="call_invite":
                to_id=int(data.get("to_user",0))
                call_type=data.get("call_type","audio")
                if not to_id: continue
                busy=False
                for cid,c in list(active_calls.items()):
                    if c["caller"]==uid or c["callee"]==uid or c["caller"]==to_id or c["callee"]==to_id: busy=True;break
                if busy:
                    await manager.send_to(uid,{"type":"call_busy"});continue
                call_id=secrets.token_hex(8)
                active_calls[call_id]={"caller":uid,"callee":to_id,"type":call_type,"started":time.time()}
                dn=user.get("display_name") or user["username"]
                await manager.send_to(to_id,{"type":"call_incoming","call_id":call_id,"from_user":uid,"from_name":dn,"from_avatar":user.get("avatar") or user.get("gif_avatar"),"call_type":call_type})
                await manager.send_to(uid,{"type":"call_ringing","call_id":call_id})
                await grant_achievement(uid,"first_call")
            elif t=="call_accept":
                cid=data.get("call_id")
                if cid in active_calls:
                    c=active_calls[cid]
                    if c["callee"]!=uid: continue
                    await manager.send_to(c["caller"],{"type":"call_accepted","call_id":cid})
            elif t=="call_reject":
                cid=data.get("call_id")
                if cid in active_calls:
                    c=active_calls[cid]
                    await manager.send_to(c["caller"],{"type":"call_rejected","call_id":cid})
                    del active_calls[cid]
            elif t=="call_end":
                cid=data.get("call_id")
                dur=int(data.get("duration",0))
                if cid in active_calls:
                    c=active_calls[cid]
                    other=c["callee"] if c["caller"]==uid else c["caller"]
                    await manager.send_to(other,{"type":"call_ended","call_id":cid})
                    try:
                        p=await get_pool()
                        async with p.acquire() as conn:
                            await conn.execute("INSERT INTO call_history(call_id,caller,callee,call_type,status,duration) VALUES($1,$2,$3,$4,'ended',$5)",cid,c["caller"],c["callee"],c["type"],dur)
                    except: pass
                    del active_calls[cid]
            elif t in ("webrtc_offer","webrtc_answer","webrtc_ice"):
                to_id=int(data.get("to_user",0))
                cid=data.get("call_id")
                if not to_id: continue
                payload={"type":t,"from_user":uid,"call_id":cid}
                if t=="webrtc_offer": payload["sdp"]=data.get("sdp")
                elif t=="webrtc_answer": payload["sdp"]=data.get("sdp")
                else: payload["candidate"]=data.get("candidate")
                await manager.send_to(to_id,payload)

            # ========== DM ==========
            elif t=="dm":
                to_id=int(data.get("to_user",0));text=(data.get("text") or "")[:MAX_TEXT]
                furl=data.get("file_url");tid=data.get("temp_id");msg_kind=data.get("msg_kind","text")
                voice_dur=int(data.get("voice_duration",0));fsize=int(data.get("file_size",0))
                reply_to=data.get("reply_to_id") or None
                expires_sec=int(data.get("expires_in",0)) or 0
                msg_shape=(data.get("msg_shape") or None)
                if not to_id: continue
                blocked=False
                p=await get_pool()
                async with p.acquire() as conn:
                    blk=await conn.fetchrow("SELECT blocker FROM user_blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",uid,to_id)
                    if blk: blocked=True
                    expires_at=None
                    if expires_sec>=5:
                        expires_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=expires_sec)
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url,file_size,msg_kind,voice_duration,reply_to_id,expires_at,msg_shape) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING *",uid,to_id,text,furl,fsize,msg_kind,voice_dur,reply_to,expires_at,msg_shape)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    if expires_at:
                        try: await conn.execute("INSERT INTO disappearing_messages(chat_type,chat_id,message_id,expires_at) VALUES('dm',$1,$2,$3)",to_id,msg["id"],expires_at)
                        except: pass
                    # ачивки по количеству
                    cnt=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    if cnt==1: await grant_achievement(uid,"first_msg")
                    if cnt>=100: await grant_achievement(uid,"msg_100")
                    if cnt>=1000: await grant_achievement(uid,"msg_1000")
                if fsize>0: await grant_achievement(uid,"first_file")
                await grant_xp(uid,1)
                dn=user.get("display_name") or user["username"]
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"display_name":dn,"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"text":text,"file_url":furl,"file_size":fsize,"msg_kind":msg_kind,"voice_duration":voice_dur,"reply_to_id":reply_to,"expires_at":_iso(expires_at),"msg_shape":msg_shape,"created_at":_iso(msg["created_at"]),"temp_id":tid}
                if not blocked: await manager.send_to(to_id,payload)
                await manager.send_to(uid,payload)

            # ========== GROUP ==========
            elif t=="group_msg":
                gid=int(data.get("group_id",0));text=(data.get("text") or "")[:MAX_TEXT]
                furl=data.get("file_url");tid=data.get("temp_id");msg_kind=data.get("msg_kind","text")
                voice_dur=int(data.get("voice_duration",0));fsize=int(data.get("file_size",0))
                reply_to=data.get("reply_to_id") or None
                msg_shape=(data.get("msg_shape") or None)
                p=await get_pool()
                async with p.acquire() as conn:
                    m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
                    if not m: continue
                    g=await conn.fetchrow("SELECT slow_mode,bad_words FROM groups WHERE id=$1",gid)
                    if g and g["slow_mode"] and g["slow_mode"]>0:
                        key=f"{gid}:{uid}"
                        last=slow_mode_cache.get(key,0)
                        now=time.time()
                        if now-last<g["slow_mode"]:
                            await manager.send_to(uid,{"type":"error","detail":f"🐢 Медленный режим: {g['slow_mode']}с"})
                            continue
                        slow_mode_cache[key]=now
                    if g and g["bad_words"]:
                        bw=_safe_json(g["bad_words"],[])
                        if has_bad_words(text,bw):
                            await manager.send_to(uid,{"type":"error","detail":"🚫 Мат запрещён"})
                            continue
                    msg=await conn.fetchrow("INSERT INTO group_messages(group_id,user_id,text,file_url,file_size,msg_kind,voice_duration,reply_to_id,msg_shape) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *",gid,uid,text,furl,fsize,msg_kind,voice_dur,reply_to,msg_shape)
                    members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                if fsize>0: await grant_achievement(uid,"first_file")
                dn=user.get("display_name") or user["username"]
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,"username":user["username"],"display_name":dn,"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"text":text,"file_url":furl,"file_size":fsize,"msg_kind":msg_kind,"voice_duration":voice_dur,"reply_to_id":reply_to,"msg_shape":msg_shape,"created_at":_iso(msg["created_at"]),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)

            # ========== TYPING ==========
            elif t=="typing":
                to_id=int(data.get("to_user",0))
                gid=int(data.get("group_id",0))
                if user.get("hide_typing"): continue
                payload={"type":"typing","from_user":uid,"display_name":user.get("display_name") or user["username"]}
                if to_id: await manager.send_to(to_id,payload)
                if gid:
                    p=await get_pool()
                    async with p.acquire() as conn:
                        members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                    for m in members:
                        if m["user_id"]!=uid: await manager.send_to(m["user_id"],payload)

            # ========== @ALL ==========
            elif t=="at_all":
                gid=int(data.get("group_id",0))
                p=await get_pool()
                async with p.acquire() as conn:
                    m=await conn.fetchrow("SELECT is_admin FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
                    g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
                    if not g: continue
                    if g["owner_id"]!=uid and (not m or not m["is_admin"]):
                        await manager.send_to(uid,{"type":"error","detail":"Только админ @all"})
                        continue
                    members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                dn=user.get("display_name") or user["username"]
                payload={"type":"group_msg","id":0,"group_id":gid,"user_id":uid,"username":user["username"],"display_name":dn,"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"text":"@all","msg_kind":"text","created_at":_iso(datetime.datetime.now(datetime.timezone.utc)),"is_at_all":True}
                for m in members:
                    if m["user_id"]!=uid: await manager.send_to(m["user_id"],payload)

            # ========== РИСОВАНИЕ (data URL → сохраняем на диск) ==========
            elif t=="draw_stroke":
                to_id=int(data.get("to_user",0))
                if not to_id: continue
                durl=data.get("data") or ""
                url=None
                try:
                    if durl.startswith("data:"):
                        saved=save_bytes_from_dataurl(durl,category="draw")
                        url=saved["url"]
                    else:
                        url=durl
                except Exception as e:
                    print(f"[draw_save] {e}")
                    continue
                await manager.send_to(to_id,{"type":"draw_stroke","data":url})

    except WebSocketDisconnect: pass
    except Exception as e:
        print(f"[WS] {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        manager.disconnect(uid,ws)
        # прибираем звонки
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

# ============ АВТО-УДАЛЕНИЕ ИСЧЕЗАЮЩИХ ============
async def disappearing_cleaner():
    while True:
        try:
            await asyncio.sleep(30)
            p=await get_pool()
            async with p.acquire() as conn:
                rows=await conn.fetch("SELECT id,chat_type,message_id FROM disappearing_messages WHERE expires_at<=NOW()")
                for r in rows:
                    try:
                        if r["chat_type"]=="dm":
                            row=await conn.fetchrow("SELECT file_url FROM dms WHERE id=$1",r["message_id"])
                            if row and row["file_url"]: delete_uploaded_file(row["file_url"])
                            await conn.execute("UPDATE dms SET text='[исчезло]',file_url=NULL WHERE id=$1",r["message_id"])
                        else:
                            row=await conn.fetchrow("SELECT file_url FROM group_messages WHERE id=$1",r["message_id"])
                            if row and row["file_url"]: delete_uploaded_file(row["file_url"])
                            await conn.execute("UPDATE group_messages SET text='[исчезло]',file_url=NULL WHERE id=$1",r["message_id"])
                        await manager.broadcast({"type":"message_vanished","chat_type":r["chat_type"],"message_id":r["message_id"]})
                        await conn.execute("DELETE FROM disappearing_messages WHERE id=$1",r["id"])
                    except Exception as e:
                        print(f"[vanish] {e}")
                await conn.execute("DELETE FROM stories WHERE expires_at<=NOW()")
        except Exception as e:
            print(f"[disappearing] {e}")

@app.on_event("startup")
async def start_cleaner():
    asyncio.create_task(disappearing_cleaner())

# ============ MANIFEST / SW / STATIC ============
@app.get("/manifest.json")
async def manifest():
    return {"name":"BelugaCord 4.5 BETA","short_name":"BelugaCord",
            "start_url":"/","display":"standalone",
            "background_color":"#0d1410","theme_color":"#22c55e",
            "icons":[{"src":"/icon-192x192.png","sizes":"192x192","type":"image/png"}]}

@app.get("/sw.js")
async def sw():
    try:
        with open("sw.js","r",encoding="utf-8") as f:
            return HTMLResponse(f.read(),media_type="application/javascript")
    except:
        return HTMLResponse("// no sw",media_type="application/javascript")

@app.get("/ref/{code}")
async def ref_redirect(code:str):
    try:
        with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())
    except: return HTMLResponse("<h1>index.html нет</h1>",status_code=500)

@app.get("/c/{channel}")
async def channel_redirect(channel:str):
    try:
        with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())
    except: return HTMLResponse("<h1>index.html нет</h1>",status_code=500)

@app.get("/")
async def index():
    try:
        with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())
    except Exception as e:
        return HTMLResponse(f"<h1>index.html нет</h1><p>{e}</p>",status_code=500)

# ============ MAIN ============
if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")