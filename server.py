# BELUGACORD 4.2 — «НЕ ВОШЕДШЕЕ?» 🔥😈
# server.py — часть 1/6
import os,json,time,secrets,hashlib,random,datetime,asyncio,re,traceback
import asyncpg,httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse
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
CURRENT_VERSION="4.2"
SUPPORT_BOT_ID=0
SUPPORT_BOT_NAME="support_bot"
SUPPORT_BOT_DISPLAY="🤖 Support Bot"
MAX_TEXT=10000

ALLOWED_EXT={'.png','.jpg','.jpeg','.gif','.webp','.svg','.bmp','.avif','.ico','.mp4','.webm','.mov','.mkv','.avi','.mp3','.wav','.ogg','.m4a','.opus','.aac','.flac','.pdf','.txt','.json','.csv','.xml','.zip','.rar','.7z','.tar','.gz','.doc','.docx','.xls','.xlsx','.ppt','.pptx'}
ALLOWED_MIME={'image/png','image/jpeg','image/jpg','image/gif','image/webp','image/svg+xml','image/bmp','image/avif','video/mp4','video/webm','video/quicktime','video/x-matroska','audio/mpeg','audio/mp3','audio/wav','audio/ogg','audio/mp4','audio/webm','audio/opus','audio/aac','audio/flac','application/zip','application/x-zip','application/x-rar-compressed','application/x-7z-compressed','application/pdf','text/plain','application/json','text/csv','application/xml','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document','application/octet-stream'}
PREMIUM_PRICES={"month":1500,"year":18000}

DEFAULT_GIFTS={"rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},"cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},"crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},"legend":{"name":"Легендарка","emoji":"💠","price":5000},"pumpkin":{"name":"Тыква","emoji":"🎃","price":150},"ghost":{"name":"Призрак","emoji":"👻","price":250},"skull":{"name":"Череп","emoji":"💀","price":400},"heart":{"name":"Сердце","emoji":"❤️","price":50},"galaxy":{"name":"Галактика","emoji":"🌌","price":100000}}

ACHIEVEMENTS={"first_msg":{"name":"Первое слово","emoji":"💬"},"msg_100":{"name":"Болтун","emoji":"🗣️"},"msg_1000":{"name":"Оратор","emoji":"🎤"},"first_friend":{"name":"Дружелюбный","emoji":"👥"},"friend_10":{"name":"Тусовщик","emoji":"🎉"},"first_gift":{"name":"Щедрый","emoji":"🎁"},"first_call":{"name":"Звонкий","emoji":"📞"},"first_voice":{"name":"Голос","emoji":"🎙️"},"first_file":{"name":"Загрузчик","emoji":"📎"}}

HOLIDAYS=[("01-01","newyear","Новый год","🎄","#dc2626"),("02-14","valentine","День Валентина","💕","#ec4899"),("03-08","womens_day","8 марта","🌷","#f472b6"),("04-01","fools_day","День смеха","🤡","#facc15"),("05-09","victory_day","День Победы","🎖️","#f97316"),("09-01","knowledge_day","День знаний","📚","#8b5cf6"),("10-31","halloween","Хэллоуин","🎃","#ff6b1a"),("12-25","christmas_catholic","Рождество","🎅","#dc2626")]

SCAM_DEFAULT_PERMS={"dm_send":False,"dm_reply":True,"gift_send":False,"gift_receive":True,"chat_send":True,"chat_create":False,"set_avatar":False,"set_banner":False,"call":False,"add_friends":False}

RESERVED_USERNAMES={"admin","support","system","belugacord","help","api","c","join","me","root","official","user","moderator"}

# ============ 4.0: КОНСТАНТЫ ============
STREET_DEFAULT={"x":50,"y":50,"location":"street"}
FURNITURE_DEFAULT=[("sofa","Диван","🛋️",500),("table","Стол","🪑",300),("bed","Кровать","🛏️",800),("tv","Телевизор","📺",1500),("plant","Растение","🪴",200),("lamp","Лампа","💡",250),("carpet","Ковёр","🟫",400),("fridge","Холодильник","🧊",1200),("flashlight","Фонарик","🔦",1000)]
PET_SPECIES={"cat":"🐱","dog":"🐶","dragon":"🐉","fox":"🦊","hamster":"🐹","owl":"🦉"}
LOOTBOX_DEFAULT={"common":{"name":"Обычный сундук","emoji":"🎁","price":500},"rare":{"name":"Редкий сундук","emoji":"💎","price":2000},"legend":{"name":"Легендарный сундук","emoji":"👑","price":10000}}
DUEL_TARGET_TAPS=20
BOMB_FUSE_SECONDS=10
CAPSULE_MIN_DAYS=1
CAPSULE_MAX_DAYS=3650

# ============ 4.2: КОНСТАНТЫ ============
BAD_WORDS_DEFAULT=["бля","хуй","пизда","еба","сука","долбо","мразь","гандон","жопа","дерьмо","говно","нахуй","похуй","залупа","мудак","уебок","уёбок","срать","пидор","гей"]
MSG_SHAPES={"round":"Круглый","square":"Квадрат","dot":"Точка","cloud":"Облако","none":"Без бабла"}
STORY_TTL_HOURS=24
SKINS_CATALOG=[
    {"id":"default","name":"Стандарт","emoji":"🎨","price":0,"ac":"#d946ef","ac2":"#8b5cf6"},
    {"id":"vk2010","name":"ВК 2010","emoji":"💙","price":2000,"ac":"#4a76a8","ac2":"#5b88c4"},
    {"id":"skype","name":"Скайп","emoji":"💠","price":2000,"ac":"#00aff0","ac2":"#008dd6"},
    {"id":"matrix","name":"Матрица","emoji":"🟢","price":5000,"ac":"#22c55e","ac2":"#16a34a"},
    {"id":"sunset","name":"Закат","emoji":"🌅","price":3000,"ac":"#f97316","ac2":"#ec4899"},
    {"id":"ocean","name":"Океан","emoji":"🌊","price":3000,"ac":"#06b6d4","ac2":"#0ea5e9"},
    {"id":"lava","name":"Лава","emoji":"🌋","price":7000,"ac":"#dc2626","ac2":"#f97316"},
    {"id":"ghost","name":"Призрак","emoji":"👻","price":4000,"ac":"#a855f7","ac2":"#6366f1"},
]
SLOW_MODE_MAX_SECONDS=600
PROMO_MAX_ACTIVATIONS=10000
DONATE_REQUESTS_TIMEOUT_HOURS=72

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
def validate_username(u):
    if not u: return False,"Пусто"
    if len(u)<4 or len(u)>32: return False,"4-32 символа"
    if not re.match(r'^[a-z][a-z0-9_]*$',u): return False,"Только a-z, 0-9, _"
    if u in RESERVED_USERNAMES: return False,"Зарезервировано"
    return True,None
TRANSLIT={'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def translit(s):
    return ''.join(TRANSLIT.get(c,c) for c in str(s))
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

app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
@app.middleware("http")
async def no_cache(request:Request,call_next):
    r=await call_next(request)
    if request.url.path.startswith("/api/"):
        r.headers["Cache-Control"]="no-store"
    return r
app.mount("/uploads",StaticFiles(directory=UPLOAD_DIR),name="uploads")

@app.get("/icon.png")
async def serve_icon():
    for p in ["icon-192x192.png","icon.png"]:
        if os.path.exists(p):
            with open(p,"rb") as f: return HTMLResponse(content=f.read(),media_type="image/png")
    return HTMLResponse("",status_code=404)

pool=None
online_users=set()
forced_holiday=None
active_calls={}
active_group_calls={}

# ============ 4.0: СОСТОЯНИЯ ============
street_state={"rain":False,"night":False,"vote_active":False,"vote_options":[],"vote_zones":{}}
active_whispers={}
active_duels={}
active_bombs={}
klondike_active=[]
draw_battles_active={}

# ============ 4.2: СОСТОЯНИЯ ============
slow_mode_cache={}
typing_last={}

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
            hide_typing BOOLEAN DEFAULT FALSE,
            last_seen TIMESTAMPTZ DEFAULT NOW(),created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
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
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,file_size BIGINT DEFAULT 0,msg_kind VARCHAR(16) DEFAULT 'text',voice_duration INTEGER DEFAULT 0,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE,name VARCHAR(64) NOT NULL,bio VARCHAR(256),avatar TEXT,banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,is_private BOOLEAN DEFAULT FALSE,category VARCHAR(32),subscribers_count INTEGER DEFAULT 0,username_changed_at TIMESTAMPTZ,linked_group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_admins(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,perms TEXT DEFAULT '{"post":true}',added_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(channel_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_subscribers(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,muted_until TIMESTAMPTZ,subscribed_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(channel_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_posts(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,text TEXT,media_urls TEXT DEFAULT '[]',media_kind VARCHAR(16) DEFAULT 'text',reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,views INTEGER DEFAULT 0,edited BOOLEAN DEFAULT FALSE,comments_count INTEGER DEFAULT 0,discussion_msg_id INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_post_views(post_id INTEGER REFERENCES channel_posts(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,viewed_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(post_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channel_bans(channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,reason VARCHAR(256),banned_by INTEGER,banned_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(channel_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS support_tickets(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,ticket_type VARCHAR(32),target_user INTEGER,title VARCHAR(128),description TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',admin_reply TEXT,resolved_by INTEGER,created_at TIMESTAMPTZ DEFAULT NOW(),resolved_at TIMESTAMPTZ)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),price_coins INTEGER DEFAULT 0)""")
        for f in [("none","Без рамки","",0),("gold","Золотая","👑",500),("fire","Огненная","🔥",800),("ice","Ледяная","❄️",800),("rainbow","Радужная","🌈",0),("pumpkin","Тыква","🎃",0),("ghost","Призрак","👻",0)]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,price_coins) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",*f)
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS titles_catalog(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),color VARCHAR(32),is_public BOOLEAN DEFAULT TRUE,condition_type VARCHAR(32),condition_value INTEGER,creator_id INTEGER,created_at TIMESTAMPTZ DEFAULT NOW())""")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM titles_catalog")
        if cnt==0:
            for t in [("Призрак","👻","#a855f7"),("Вампир","🧛","#dc2626"),("Ведьма","🧙","#ec4899"),("Легенда","🏅","#ffd700")]:
                await conn.execute("INSERT INTO titles_catalog(name,emoji,color) VALUES($1,$2,$3)",*t)
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_season(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🎃',started_at TIMESTAMPTZ DEFAULT NOW(),ends_at TIMESTAMPTZ,days_total INTEGER DEFAULT 30,max_level INTEGER DEFAULT 50,xp_per_level INTEGER DEFAULT 1000,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_progress(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_id INTEGER,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,claimed TEXT DEFAULT '[]',has_premium_pass BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_quests(id SERIAL PRIMARY KEY,name VARCHAR(128),action_type VARCHAR(32),target_count INTEGER DEFAULT 1,xp_reward INTEGER DEFAULT 100,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS system_settings(key VARCHAR(64) PRIMARY KEY,value TEXT,updated_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS call_history(id SERIAL PRIMARY KEY,call_id VARCHAR(32),caller INTEGER REFERENCES users(id) ON DELETE CASCADE,callee INTEGER REFERENCES users(id) ON DELETE CASCADE,call_type VARCHAR(16) DEFAULT 'audio',status VARCHAR(16) DEFAULT 'ended',duration INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ranks(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8) DEFAULT '🏆',color VARCHAR(32) DEFAULT '#d946ef',priority INTEGER DEFAULT 10,perms TEXT DEFAULT '{}',created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_chat_settings(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,chat_type VARCHAR(16),chat_id INTEGER,pinned BOOLEAN DEFAULT FALSE,archived BOOLEAN DEFAULT FALSE,mute_until TIMESTAMPTZ,UNIQUE(user_id,chat_type,chat_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS saved_searches(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,name VARCHAR(64),query TEXT,filters TEXT DEFAULT '{}',created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS daily_bonus(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,streak INTEGER DEFAULT 0,last_claim DATE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS referrals(id SERIAL PRIMARY KEY,code VARCHAR(16) UNIQUE NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,clicks INTEGER DEFAULT 0,registrations INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS referral_uses(id SERIAL PRIMARY KEY,code VARCHAR(16),referrer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,new_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,reward_ref INTEGER DEFAULT 0,reward_new INTEGER DEFAULT 0,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_sessions(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,token_hash VARCHAR(64),device VARCHAR(128),ip VARCHAR(64),last_active TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_emoji(id SERIAL PRIMARY KEY,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,emoji_id VARCHAR(32) UNIQUE,url TEXT,created_at TIMESTAMPTZ DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS achievement_log(user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,key VARCHAR(32),got_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(user_id,key))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS chat_drafts(user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,chat_type VARCHAR(16),chat_id INTEGER,text TEXT,updated_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(user_id,chat_type,chat_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_call_members(call_id VARCHAR(32),user_id INTEGER,joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(call_id,user_id))""")
        # ============ 4.0: ТАБЛИЦЫ ============
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
        # ============ 4.2: ТАБЛИЦЫ ============
        await conn.execute("""CREATE TABLE IF NOT EXISTS disappearing_messages(
            id SERIAL PRIMARY KEY,chat_type VARCHAR(16),chat_id INTEGER,message_id INTEGER,
            expires_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS polls(
            id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
            creator INTEGER REFERENCES users(id) ON DELETE CASCADE,question VARCHAR(256) NOT NULL,
            options TEXT DEFAULT '[]',votes TEXT DEFAULT '{}',multiple BOOLEAN DEFAULT FALSE,
            closes_at TIMESTAMPTZ,closed BOOLEAN DEFAULT FALSE,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS promocodes(
            id SERIAL PRIMARY KEY,code VARCHAR(32) UNIQUE NOT NULL,reward INTEGER DEFAULT 0,
            max_activations INTEGER DEFAULT 1,activations INTEGER DEFAULT 0,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            for_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ,active BOOLEAN DEFAULT TRUE,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS promo_activations(
            id SERIAL PRIMARY KEY,promo_id INTEGER REFERENCES promocodes(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            reward INTEGER DEFAULT 0,activated_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS donate_requests(
            id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,message TEXT,status VARCHAR(16) DEFAULT 'pending',
            reviewed_by INTEGER,reviewed_at TIMESTAMPTZ,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS stories(
            id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            kind VARCHAR(16) DEFAULT 'text',content TEXT,file_url TEXT,
            views INTEGER DEFAULT 0,expires_at TIMESTAMPTZ NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS story_views(
            story_id INTEGER REFERENCES stories(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            viewed_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(story_id,user_id)
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS profile_wall(
            id SERIAL PRIMARY KEY,profile_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            author INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_reactions(
            id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            emoji_id VARCHAR(32) UNIQUE NOT NULL,name VARCHAR(64),image_url TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS link_previews(
            url VARCHAR(512) PRIMARY KEY,title VARCHAR(256),description TEXT,
            image TEXT,site_name VARCHAR(64),fetched_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS events_calendar(
            id SERIAL PRIMARY KEY,title VARCHAR(128) NOT NULL,description TEXT,
            event_date TIMESTAMPTZ NOT NULL,emoji VARCHAR(8) DEFAULT '📅',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS secret_rooms(
            id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,password_hash VARCHAR(64),
            owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            capacity INTEGER DEFAULT 10,created_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS room_members(
            room_id INTEGER REFERENCES secret_rooms(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            joined_at TIMESTAMPTZ DEFAULT NOW(),PRIMARY KEY(room_id,user_id)
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_skins(
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            active_skin VARCHAR(32) DEFAULT 'default',owned TEXT DEFAULT '["default"]',
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""")
        migrations=[
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS hide_typing BOOLEAN DEFAULT FALSE",
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
        try:
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_dms_users ON dms(from_user,to_user,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chan_posts ON channel_posts(channel_id,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_gmsgs ON group_messages(group_id,id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_positions ON user_positions(location)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_exp ON stories(expires_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_dismsg_exp ON disappearing_messages(expires_at)")
        except: pass
        await conn.execute("UPDATE users SET display_name=username WHERE display_name IS NULL")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("UPDATE users SET display_name=$1 WHERE username=$2",ADMIN_DISPLAY,ADMIN_USERNAME)
        bot_exists=await conn.fetchval("SELECT 1 FROM users WHERE id=$1",SUPPORT_BOT_ID)
        if not bot_exists:
            try:
                await conn.execute("INSERT INTO users(id,username,display_name,password_hash,is_dev) VALUES($1,$2,$3,$4,TRUE)",SUPPORT_BOT_ID,SUPPORT_BOT_NAME,SUPPORT_BOT_DISPLAY,hash_password("bot_"+SECRET_KEY))
                await conn.execute("SELECT setval(pg_get_serial_sequence('users','id'),GREATEST((SELECT MAX(id) FROM users),1))")
            except: pass
        ranks_cnt=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if ranks_cnt==0:
            try:
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","👑 Владелец","👑","#ffd700",1000,json.dumps({"owner_panel":True,"admin_panel":True,"manage_ranks":True,"manage_users":True,"broadcast":True,"give_coins":True,"take_coins":True,"ban":True,"mute":True,"delete_msgs":True,"give_premium":True,"manage_shop":True,"manage_cosmetics":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🛡️ Администратор","🛡️","#d946ef",500,json.dumps({"admin_panel":True,"manage_users":True,"give_coins":True,"ban":True,"mute":True,"delete_msgs":True,"broadcast":True}))
                await conn.execute("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5)","🔨 Модератор","🔨","#22c55e",100,json.dumps({"mute":True,"delete_msgs":True}))
            except: pass
        bp_row=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE LIMIT 1")
        if not bp_row:
            ends=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=30)
            await conn.execute("INSERT INTO bp_season(name,description,emoji,days_total,max_level,ends_at,active) VALUES($1,$2,$3,$4,$5,$6,TRUE)","Жуткий месяц","Хэллоуин","🎃",30,50,ends)
            for q in [("Напиши 10 сообщений","send_message",10,100),("Сыграй 1 игру","play_game",1,100),("Отправь 1 DM","send_dm",1,100),("Позвони другу","call",1,500),("Голосовое","voice",1,300)]:
                await conn.execute("INSERT INTO bp_quests(name,action_type,target_count,xp_reward) VALUES($1,$2,$3,$4)",*q)
        print("✅ БД 4.2 готова")

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
            exists=await conn.fetchval("SELECT 1 FROM achievement_log WHERE user_id=$1 AND key=$2",uid,key)
            if exists: return False
            await conn.execute("INSERT INTO achievement_log(user_id,key) VALUES($1,$2) ON CONFLICT DO NOTHING",uid,key)
            await conn.execute("UPDATE users SET coins=coins+50 WHERE id=$1",uid)
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
            "avatar":row.get("avatar"),"banner":row.get("banner"),"gif_avatar":row.get("gif_avatar"),
            "avatar_pos":row.get("avatar_pos") or "50% 50%","banner_pos":row.get("banner_pos") or "50% 50%",
            "is_admin":bool(row.get("is_admin")),"is_moderator":bool(row.get("is_moderator")),
            "is_scam":bool(row.get("is_scam")),"premium_tier":row.get("premium_tier"),
            "is_premium":is_premium(row),"online_status":status,"bio":row.get("bio"),
            "custom_status":row.get("custom_status"),"status_emoji":row.get("status_emoji"),
            "nick_gradient":row.get("nick_gradient"),"bio_bg":row.get("bio_bg"),
            "coins":row.get("coins",0),"messages_count":row.get("messages_count",0),
            "quest_points":0,"active_frame":row.get("active_frame"),
            "frame_owned":_safe_json(row.get("frame_owned"),[]),"title":row.get("title"),
            "title_owned":_safe_json(row.get("title_owned"),[]),
            "level":row.get("level",1),"xp":row.get("xp",0),"candy":row.get("candy",0),
            "rank_id":row.get("rank_id"),"font_size":row.get("font_size") or "md",
            "airplane_mode":bool(row.get("airplane_mode")),"notif_enabled":bool(row.get("notif_enabled",True)),
            "sound_enabled":bool(row.get("sound_enabled",True)),"theme":row.get("theme") or "dark",
            "hide_typing":bool(row.get("hide_typing")),
            "created_at":_iso(row.get("created_at")),"role":get_role(row),"online":is_online,
            "achievements":_safe_json(row.get("achievements"),[])}
    except Exception as e:
        print(f"[user_public ERR] {e}")
        return {"id":row.get("id"),"username":row.get("username"),"display_name":row.get("display_name") or row.get("username"),"is_premium":False,"online":False}

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

async def get_bad_words_for_group(gid):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT bad_words FROM groups WHERE id=$1",gid)
            if row: return _safe_json(row["bad_words"],[])
    except: pass
    return []

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

@app.get("/api/changelog")
async def changelog():
    return {"current":CURRENT_VERSION,"all":{"4.2":{"title":"BelugaCord 4.2 — «НЕ ВОШЕДШЕЕ?» 🔥😈","items":["⏱️ Исчезающие сообщения","📊 Опросы","🎟️ Промокоды","💸 Донат-заявки","📸 Истории 24ч","💬 Стена профиля","😀 Кастомные реакции","🔗 Превью ссылок","🔍 Поиск по сообщениям","🐢 Медленный режим","🚫 Чёрный список","📢 @all","📅 Календарь ивентов","🎨 Коллекции","🔐 Тайные комнаты","🖌️ Скины (19 фич)"]},"4.0":{"title":"BelugaCord 4.0 — Восставший с Ада","items":["🏙️ Улица и Дом","💰 Биржа и лутбоксы","👨‍👩‍👧 Семьи и питомцы","📈 Акции юзеров","⏳ Капсулы времени","🎲 Дуэли и игры","🕵️ Анонимки"]},"3.6":{"title":"BelugaCord 3.6 — Титан","items":["📢 Каналы","💬 Обсуждения","🎥 Видео-кружки"]}}}

@app.get("/api/version")
async def version():
    return {"version":CURRENT_VERSION,"name":"НЕ ВОШЕДШЕЕ?","emoji":"🔥😈"}
# ============ ЮЗЕРЫ ============
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
                    await conn.execute("""INSERT INTO referral_uses(code,referrer_id,new_user_id,reward_ref,reward_new) VALUES($1,$2,$3,20000,500)""",ref_code,ref["owner_id"],row["id"])
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
async def me(token:str):
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

@app.post("/api/owner/verify")
async def owner_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    pw=data.get("password") or ""
    if pw!=OWNER_PASSWORD: raise HTTPException(403,"Неверный пароль")
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
            gif_avatar=COALESCE($3,gif_avatar),avatar_pos=COALESCE($4,avatar_pos),banner_pos=COALESCE($5,banner_pos),
            bio=COALESCE($6,bio),nick_gradient=COALESCE($7,nick_gradient),status_emoji=COALESCE($8,status_emoji),
            bio_bg=COALESCE($9,bio_bg) WHERE id=$10""",
            data.get("avatar"),data.get("banner"),data.get("gif_avatar"),data.get("avatar_pos"),
            data.get("banner_pos"),data.get("bio"),data.get("nick_gradient"),data.get("status_emoji"),
            data.get("bio_bg"),user["id"])
    await manager.broadcast({"type":"user_updated","user_id":user["id"]})
    return {"ok":True}

@app.post("/api/upload_avatar")
async def upload_avatar(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400,"Только картинка")
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
    if not (file.content_type or "").startswith("image/"): raise HTTPException(400,"Только картинка")
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
    allowed={"airplane_mode":"airplane_mode","notif_enabled":"notif_enabled","sound_enabled":"sound_enabled","theme":"theme","font_size":"font_size","hide_typing":"hide_typing"}
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

# ============ БЛОКИРОВКА ============
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

# ============ ГРУППЫ ============
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

@app.post("/api/groups/{gid}/add_member")
async def group_add_member(gid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT is_admin FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
        if not m or not m["is_admin"]: raise HTTPException(403,"Только админ")
        try: await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",gid,uid)
        except: pass
    await manager.send_to(uid,{"type":"group_added","group_id":gid})
    return {"ok":True}

@app.post("/api/groups/{gid}/kick")
async def group_kick(gid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет группы")
        m=await conn.fetchrow("SELECT is_admin FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
        if g["owner_id"]!=user["id"] and (not m or not m["is_admin"]): raise HTTPException(403,"Только админ")
        await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
    await manager.send_to(uid,{"type":"group_kicked","group_id":gid})
    return {"ok":True}

@app.post("/api/groups/leave")
async def group_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    if not gid: raise HTTPException(400,"group_id")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if g and g["owner_id"]==user["id"]: raise HTTPException(400,"Владелец не может выйти, передай владение")
        await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
    return {"ok":True}

@app.post("/api/groups/join/{code}")
async def group_join(code:str,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT id,name FROM groups WHERE invite_code=$1",code)
        if not g: raise HTTPException(404,"Неверный код")
        try: await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",g["id"],user["id"])
        except: pass
    return {"ok":True,"group_id":g["id"],"name":g["name"]}

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

# ============ КАНАЛЫ ============
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

@app.post("/api/channels/{cid}/mute")
async def channel_mute(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    minutes=int(data.get("minutes",0))
    p=await get_pool()
    async with p.acquire() as conn:
        if minutes<=0:
            await conn.execute("UPDATE channel_subscribers SET muted_until=NULL WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        else:
            await conn.execute("UPDATE channel_subscribers SET muted_until=NOW()+INTERVAL '1 minute' * $1 WHERE channel_id=$2 AND user_id=$3",minutes,cid,user["id"])
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

@app.post("/api/channels/{cid}/posts/{pid}/edit")
async def channel_post_edit(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        if not adm: raise HTTPException(403,"Не админ")
        text=(data.get("text") or "")[:MAX_TEXT]
        await conn.execute("UPDATE channel_posts SET text=$1,edited=TRUE WHERE id=$2 AND channel_id=$3",text,pid,cid)
    return {"ok":True}

@app.post("/api/channels/{cid}/posts/{pid}/delete")
async def channel_post_delete(cid:int,pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        if not adm: raise HTTPException(403,"Не админ")
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
                fields.append(f"{k}=${idx}");params.append(str(data[k])[:256]);idx+=1
        if "is_private" in data:
            fields.append(f"is_private=${idx}");params.append(bool(data["is_private"]));idx+=1
        if not fields: raise HTTPException(400,"Нечего менять")
        params.append(cid)
        await conn.execute(f"UPDATE channels SET {','.join(fields)} WHERE id=${idx}",*params)
    return {"ok":True}

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
    ext=os.path.splitext(file.filename or "")[1].lower() or ".png"
    name=f"ch_av_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    url=f"/uploads/{name}"
    async with p.acquire() as conn:
        await conn.execute("UPDATE channels SET avatar=$1 WHERE id=$2",url,cid)
    return {"ok":True,"url":url}

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
    ext=os.path.splitext(file.filename or "")[1].lower() or ".png"
    name=f"ch_bn_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    url=f"/uploads/{name}"
    async with p.acquire() as conn:
        await conn.execute("UPDATE channels SET banner=$1 WHERE id=$2",url,cid)
    return {"ok":True,"url":url}

@app.post("/api/channels/{cid}/save_pos")
async def channel_save_pos(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        if data.get("avatar_pos"): await conn.execute("UPDATE channels SET avatar_pos=$1 WHERE id=$2",str(data["avatar_pos"])[:16],cid)
        if data.get("banner_pos"): await conn.execute("UPDATE channels SET banner_pos=$1 WHERE id=$2",str(data["banner_pos"])[:16],cid)
    return {"ok":True}

@app.post("/api/channels/{cid}/admin/add")
async def channel_admin_add(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    uid=int(data.get("user_id",0))
    perms=data.get("perms") or {"post":True}
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("INSERT INTO channel_admins(channel_id,user_id,perms) VALUES($1,$2,$3) ON CONFLICT(channel_id,user_id) DO UPDATE SET perms=$3",cid,uid,json.dumps(perms))
    await manager.send_to(uid,{"type":"channel_admin_added","channel_id":cid})
    return {"ok":True}

@app.post("/api/channels/{cid}/admin/remove")
async def channel_admin_remove(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    uid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("DELETE FROM channel_admins WHERE channel_id=$1 AND user_id=$2 AND user_id!=owner_id",cid,uid)
    return {"ok":True}

@app.post("/api/channels/{cid}/ban")
async def channel_ban(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    uid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        adm=await conn.fetchrow("SELECT perms FROM channel_admins WHERE channel_id=$1 AND user_id=$2",cid,user["id"])
        if not adm or not _safe_json(adm["perms"],{}).get("ban"): raise HTTPException(403,"Нет права")
        await conn.execute("INSERT INTO channel_bans(channel_id,user_id,reason,banned_by) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING",cid,uid,(data.get("reason") or "")[:256],user["id"])
        await conn.execute("DELETE FROM channel_subscribers WHERE channel_id=$1 AND user_id=$2",cid,uid)
    return {"ok":True}

@app.post("/api/channels/{cid}/transfer")
async def channel_transfer(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    new_owner=int(data.get("new_owner_id",0))
    if not new_owner: raise HTTPException(400,"new_owner_id")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("UPDATE channels SET owner_id=$1 WHERE id=$2",new_owner,cid)
        await conn.execute("INSERT INTO channel_admins(channel_id,user_id,perms) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",cid,new_owner,json.dumps({"post":True,"edit":True,"delete":True,"ban":True}))
    return {"ok":True}

@app.post("/api/channels/{cid}/delete")
async def channel_delete(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT owner_id FROM channels WHERE id=$1",cid)
        if not c or c["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("DELETE FROM channels WHERE id=$1",cid)
    return {"ok":True}

# ============ ОБСУЖДЕНИЯ ============
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

# ============ MESSAGES EDIT/DELETE/REPLY ============
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
            await conn.execute("UPDATE dms SET text='[удалено]',file_url=NULL,deleted_for_all=TRUE WHERE id=$1 AND from_user=$2",mid,user["id"])
        else:
            await conn.execute("UPDATE group_messages SET text='[удалено]',file_url=NULL WHERE id=$1 AND user_id=$2",mid,user["id"])
    await manager.broadcast({"type":"message_edited","id":mid,"text":"[удалено]"})
    return {"ok":True}

@app.get("/api/messages/pinned/{user_id}")
async def messages_pinned(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,text,created_at FROM dms WHERE pinned=TRUE AND ((from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)) ORDER BY id DESC",user["id"],user_id)
    return [{"id":r["id"],"text":r["text"],"created_at":_iso(r["created_at"])} for r in rows]

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

# ============ ЧАТЫ: PIN/ARCHIVE/MUTE ============
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
    if not content: raise HTTPException(400,"Пусто")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}","size":len(content),"mime":mime,"name":file.filename or name}

@app.post("/api/upload_voice")
async def upload_voice(token:str=Form(...),file:UploadFile=File(...),duration:int=Form(0)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("audio/"): raise HTTPException(400,"Аудио")
    content=await file.read()
    if len(content)>5*1024*1024: raise HTTPException(400,"Макс 5 МБ")
    ext=".webm" if "webm" in (file.content_type or "") else ".ogg"
    name=f"voice_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    if duration<1: duration=1
    if duration>300: duration=300
    await grant_achievement(user["id"],"first_voice")
    return {"url":f"/uploads/{name}","duration":duration,"size":len(content)}

@app.post("/api/upload_video_note")
async def upload_video_note(token:str=Form(...),file:UploadFile=File(...),duration:int=Form(0)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if not (file.content_type or "").startswith("video/"): raise HTTPException(400,"Видео")
    content=await file.read()
    if len(content)>8*1024*1024: raise HTTPException(400,"Макс 8 МБ")
    ext=".webm" if "webm" in (file.content_type or "") else ".mp4"
    name=f"vnote_{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    if duration<1: duration=1
    if duration>60: duration=60
    return {"url":f"/uploads/{name}","duration":duration,"size":len(content)}

# ============ GIFTS/SHOP/FRAMES/TITLES ============
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

@app.get("/api/cases/list")
async def cases_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,emoji,price FROM cases WHERE is_active=TRUE ORDER BY id DESC")
    return [dict(r) for r in rows]

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
    emoji=(data.get("emoji") or "⭐")[:8]
    color=(data.get("color") or "#d946ef")[:32]
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO titles_catalog(name,emoji,color,is_public,creator_id) VALUES($1,$2,$3,FALSE,$4) RETURNING id",name,emoji,color,user["id"])
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

@app.get("/api/messages/saved")
async def messages_saved(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,text,created_at FROM user_saved_messages WHERE user_id=$1 ORDER BY id DESC LIMIT 100",user["id"])
    return [{"id":r["id"],"text":r["text"],"created_at":_iso(r["created_at"])} for r in rows]

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
# ============ АДМИНКА ============
@app.post("/api/admin/verify")
async def admin_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
    if not (perms.get("admin_panel") or perms.get("owner_panel")):
        raise HTTPException(403,"Нет доступа")
    if (data.get("password") or "")!=OWNER_PASSWORD: raise HTTPException(403,"Неверный пароль")
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
    if not tid: raise HTTPException(400,"target_id")
    if action=="ban" and not perms.get("ban"): raise HTTPException(403,"Нет права")
    if action=="unban" and not perms.get("ban"): raise HTTPException(403,"Нет права")
    if action=="mute" and not perms.get("mute"): raise HTTPException(403,"Нет права")
    async with p.acquire() as conn:
        if action=="ban":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",(data.get("reason") or "")[:256],tid)
        elif action=="unban":
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",tid)
        elif action=="mute":
            await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",int(data.get("duration",3600)),tid)
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
    if not tid: raise HTTPException(404,"Не найден")
    async with p.acquire() as conn:
        cur=await conn.fetchval("SELECT is_scam FROM users WHERE id=$1",tid)
        new=not bool(cur)
        perms2=json.dumps(SCAM_DEFAULT_PERMS) if new else "{}"
        await conn.execute("UPDATE users SET is_scam=$1,scam_perms=$2 WHERE id=$3",new,perms2,tid)
    await manager.broadcast({"type":"user_updated","user_id":tid})
    return {"ok":True,"is_scam":new}

@app.post("/api/admin/mass_delete")
async def admin_mass_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("admin_panel"): raise HTTPException(403,"Нет права")
    uid=int(data.get("user_id",0))
    days=int(data.get("days",7))
    if not uid: raise HTTPException(400,"user_id")
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM dms WHERE from_user=$1 AND created_at>NOW()-INTERVAL '1 day' * $2",uid,days)
        await conn.execute("DELETE FROM group_messages WHERE user_id=$1 AND created_at>NOW()-INTERVAL '1 day' * $2",uid,days)
    await manager.send_to(uid,{"type":"force_reload"})
    return {"ok":True}

# ============ ЛОГИ ============
@app.get("/api/owner/logs")
async def owner_logs(token:str,limit:int=200):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT al.id,al.action,al.target_id,al.details,al.created_at,u.username AS admin_username,u.display_name AS admin_display,t.username AS target_username
            FROM admin_logs al LEFT JOIN users u ON u.id=al.admin_id LEFT JOIN users t ON t.id=al.target_id
            ORDER BY al.id DESC LIMIT $1""",limit)
    return [{"id":r["id"],"admin":r["admin_display"] or r["admin_username"] or "?","action":r["action"],"target":r["target_username"] or r["target_id"],"details":r["details"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/owner/logs/clear")
async def owner_logs_clear(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM admin_logs")
    return {"ok":True}

# ============ РАНГИ ============
ALL_RANK_PERMS=["owner_panel","admin_panel","manage_ranks","manage_users","manage_shop","manage_cosmetics","broadcast","give_coins","take_coins","give_candy","ban","mute","delete_msgs","bypass_limits","verified","custom_title","give_gifts","give_premium","manage_games","spy","force_logout","global_theme"]

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
            out.append({"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"priority":r["priority"],"perms":_safe_json(r["perms"],{}),"users_count":cnt})
    return {"ranks":out}

@app.get("/api/owner/ranks/get")
async def ranks_get(id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not (perms.get("manage_ranks") or perms.get("owner_panel")):
            raise HTTPException(403,"Нет")
        r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",id)
        if not r: raise HTTPException(404,"Нет")
    return {"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"priority":r["priority"],"perms":_safe_json(r["perms"],{})}

@app.post("/api/owner/ranks/create")
async def ranks_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    is_owner=await am_i_owner(user)
    my_prio=await get_my_rank_priority(user["id"])
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет")
        name=(data.get("name") or "").strip()[:64]
        if not name: raise HTTPException(400,"Имя")
        priority=int(data.get("priority",10))
        if not is_owner and priority>my_prio: raise HTTPException(403,f"Твой приоритет {my_prio}")
        rp=data.get("perms") or {}
        if not isinstance(rp,dict): rp={}
        clean={k:bool(v) for k,v in rp.items() if k in ALL_RANK_PERMS}
        if not is_owner: clean.pop("owner_panel",None)
        r=await conn.fetchrow("INSERT INTO ranks(name,emoji,color,priority,perms) VALUES($1,$2,$3,$4,$5) RETURNING id",name,(data.get("emoji") or "🏆")[:8],(data.get("color") or "#d946ef")[:32],priority,json.dumps(clean))
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
    if not rid: raise HTTPException(400,"id")
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет")
        old=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not old: raise HTTPException(404,"Нет")
        if not is_owner and old["priority"]>my_prio: raise HTTPException(403,"Ранг выше тебя")
        rp=data.get("perms") or {}
        if not isinstance(rp,dict): rp={}
        clean={k:bool(v) for k,v in rp.items() if k in ALL_RANK_PERMS}
        if not is_owner: clean.pop("owner_panel",None)
        await conn.execute("UPDATE ranks SET name=$1,emoji=$2,color=$3,priority=$4,perms=$5 WHERE id=$6",(data.get("name") or old["name"])[:64],(data.get("emoji") or old["emoji"])[:8],(data.get("color") or old["color"])[:32],int(data.get("priority",old["priority"])),json.dumps(clean),rid)
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
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет")
        old=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not old: raise HTTPException(404,"Нет")
        if not is_owner and old["priority"]>my_prio: raise HTTPException(403,"Выше тебя")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        if cnt<=1: raise HTTPException(400,"Последний нельзя")
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
    if not uid: raise HTTPException(400,"user_id")
    async with p.acquire() as conn:
        perms,_=await get_user_perms_full(conn,user["id"])
        if not perms.get("manage_ranks"): raise HTTPException(403,"Нет")
        target=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",uid)
        if not target: raise HTTPException(404,"Нет")
        if rid<=0:
            if target["username"]==ADMIN_USERNAME and not is_owner: raise HTTPException(403,"Нельзя")
            await conn.execute("UPDATE users SET rank_id=NULL WHERE id=$1",uid)
            await manager.send_to(uid,{"type":"rank_changed","rank":None})
            return {"ok":True,"rank_id":None}
        r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Нет")
        if not is_owner and r["priority"]>my_prio: raise HTTPException(403,f"Твой приоритет {my_prio}")
        await conn.execute("UPDATE users SET rank_id=$1 WHERE id=$2",rid,uid)
    await log_admin(user["id"],"rank_assign",uid,f"{target['username']} → {r['name']}")
    await manager.send_to(uid,{"type":"rank_changed","rank":{"id":rid,"name":r["name"],"emoji":r["emoji"],"color":r["color"]}})
    return {"ok":True,"rank_id":rid}

@app.post("/api/owner/ranks/godmode_assign")
async def ranks_godmode_assign(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    uid=int(data.get("user_id",0))
    rid=int(data.get("rank_id",0))
    if not uid: raise HTTPException(400,"user_id")
    async with p.acquire() as conn:
        target=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",uid)
        if not target: raise HTTPException(404,"Нет")
        if rid<=0:
            await conn.execute("UPDATE users SET rank_id=NULL WHERE id=$1",uid)
            return {"ok":True,"rank_id":None}
        r=await conn.fetchrow("SELECT * FROM ranks WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET rank_id=$1 WHERE id=$2",rid,uid)
    await log_admin(user["id"],"GODMODE_rank",uid,f"{target['username']} → {r['name']}")
    await manager.send_to(uid,{"type":"rank_changed","rank":{"id":rid,"name":r["name"],"emoji":r["emoji"],"color":r["color"]}})
    return {"ok":True,"rank_id":rid}

# ============ МАССОВЫЕ ============
@app.post("/api/owner/mass/give")
async def owner_mass_give(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    field=(data.get("field") or "").strip()
    amount=int(data.get("amount",0))
    if field not in ("coins","candy","xp"): raise HTTPException(400,"field")
    if amount==0: raise HTTPException(400,"amount")
    p=await get_pool()
    async with p.acquire() as conn:
        if amount>0: await conn.execute(f"UPDATE users SET {field}={field}+$1 WHERE id!=0",amount)
        else: await conn.execute(f"UPDATE users SET {field}=GREATEST(0,{field}+$1) WHERE id!=0",amount)
    await log_admin(user["id"],"mass_give",0,f"{field} {amount}")
    await manager.broadcast({"type":"mass_give","field":field,"amount":amount})
    return {"ok":True}

@app.post("/api/owner/mass/theme")
async def owner_mass_theme(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    theme=(data.get("theme") or "dark").strip()
    font=(data.get("font_size") or "").strip()
    if theme not in ("dark","light","amoled"): raise HTTPException(400,"theme")
    p=await get_pool()
    async with p.acquire() as conn:
        if font: await conn.execute("UPDATE users SET theme=$1,font_size=$2 WHERE id!=0",theme,font)
        else: await conn.execute("UPDATE users SET theme=$1 WHERE id!=0",theme)
    payload={"type":"force_theme","theme":theme}
    if font: payload["font_size"]=font
    await manager.broadcast(payload)
    await log_admin(user["id"],"mass_theme",0,f"{theme}/{font}")
    return {"ok":True}

@app.post("/api/owner/mass/notif")
async def owner_mass_notif(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    return {"ok":True}

# ============ STATS/LIVE ============
@app.get("/api/owner/stats")
async def owner_stats(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        m=await conn.fetchval("SELECT COUNT(*) FROM messages")
        c=await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        g=await conn.fetchval("SELECT COUNT(*) FROM gifts")
        prem=await conn.fetchval("SELECT COUNT(*) FROM users WHERE premium_tier IS NOT NULL")
        dms=await conn.fetchval("SELECT COUNT(*) FROM dms")
        grp=await conn.fetchval("SELECT COUNT(*) FROM groups")
        rnk=await conn.fetchval("SELECT COUNT(*) FROM ranks")
        chn=await conn.fetchval("SELECT COUNT(*) FROM channels")
        try: calls=await conn.fetchval("SELECT COUNT(*) FROM call_history")
        except: calls=0
    return {"users":u,"messages":m,"coins":c,"gifts":g,"online":len(online_users),"premium":prem,"dms":dms,"servers":0,"groups":grp,"ranks":rnk,"calls":calls,"channels":chn}

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
    calls=[{"call_id":cid,"caller":c["caller"],"callee":c["callee"],"type":c["type"]} for cid,c in active_calls.items()]
    return {"online_count":len(online_users),"online_users":users_info,"active_calls":calls,"call_count":len(calls)}

@app.get("/api/owner/full_stats")
async def owner_full_stats(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        users=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        msgs=await conn.fetchval("SELECT COUNT(*) FROM dms")
        coins=await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        new_today=await conn.fetchval("SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '1 day'")
        top=await conn.fetch("SELECT username,messages_count FROM users WHERE id!=0 ORDER BY messages_count DESC LIMIT 10")
    return {"users":users,"online":len(online_users),"messages":msgs,"coins_total":coins,"new_today":new_today,"top_users":[{"username":r["username"],"messages":r["messages_count"]} for r in top]}

# ============ OWNER ACTIONS ============
@app.post("/api/owner/give_coins")
async def owner_give_coins(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",int(data.get("amount",100)),t["id"])
    await log_admin(user["id"],"give_coins",t["id"],str(data.get("amount")))
    return {"ok":True}

@app.post("/api/owner/take_coins")
async def owner_take_coins(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET coins=GREATEST(0,coins-$1) WHERE id=$2",int(data.get("amount",100)),t["id"])
    return {"ok":True}

@app.post("/api/owner/give_candy")
async def owner_give_candy(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",int(data.get("amount",50)),t["id"])
    return {"ok":True}

@app.post("/api/owner/give_premium")
async def owner_give_premium(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",int(data.get("days",30)),t["id"])
    return {"ok":True}

@app.post("/api/owner/mute")
async def owner_mute(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 minute' * $1 WHERE id=$2",int(data.get("minutes",60)),t["id"])
    await manager.send_to(t["id"],{"type":"muted","reason":f"Мут {data.get('minutes',60)} мин"})
    return {"ok":True}

@app.post("/api/owner/reset_pass")
async def owner_reset_pass(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    new_pw=str(data.get("new_password") or "beluga123")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
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
        if not t: raise HTTPException(404,"Нет")
        exists=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",new,t["id"])
        if exists: raise HTTPException(400,"Занято")
        await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,t["id"])
    return {"ok":True,"new_username":new}

@app.post("/api/owner/force_logout")
async def owner_force_logout(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
    await manager.send_to(t["id"],{"type":"force_logout"})
    await manager.kick(t["id"])
    return {"ok":True}

@app.post("/api/owner/grant_admin")
async def owner_grant_admin(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE id=$1",t["id"])
    return {"ok":True}

@app.post("/api/owner/revoke_admin")
async def owner_revoke_admin(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET is_admin=FALSE WHERE id=$1",t["id"])
    return {"ok":True}

@app.post("/api/owner/level_up")
async def owner_level_up(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET level=level+$1 WHERE id=$2",int(data.get("levels",1)),t["id"])
    return {"ok":True}

@app.post("/api/owner/give_title")
async def owner_give_title(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",(data.get("title") or "")[:64],t["id"])
    return {"ok":True}

@app.post("/api/owner/give_frame")
async def owner_give_frame(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await _get_target(conn,data)
        if not t: raise HTTPException(404,"Нет")
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
        if not t: raise HTTPException(404,"Нет")
        if t["username"]==ADMIN_USERNAME: raise HTTPException(400,"Себя нельзя")
        await conn.execute("DELETE FROM users WHERE id=$1",t["id"])
    try: await manager.kick(t["id"])
    except: pass
    return {"ok":True}

@app.post("/api/owner/user/restore")
async def owner_user_restore(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uid=int(data.get("user_id",0))
    if not uid: raise HTTPException(400,"user_id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_banned=FALSE,ban_reason=NULL,is_scam=FALSE,scam_perms='{}',mute_until=NULL WHERE id=$1",uid)
    await log_admin(user["id"],"user_restore",uid)
    return {"ok":True}

@app.post("/api/owner/system/hot_reload")
async def owner_hot_reload(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,{"type":"force_reload"}); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.post("/api/owner/system/clear_cache")
async def owner_clear_cache(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    await manager.broadcast({"type":"clear_cache"})
    return {"ok":True}

@app.post("/api/owner/system/maintenance")
async def owner_maintenance(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    enabled=bool(data.get("enabled",False))
    text=(data.get("text") or "")[:500]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO system_settings(key,value) VALUES('maintenance_mode',$1) ON CONFLICT(key) DO UPDATE SET value=$1",json.dumps(enabled))
        if text: await conn.execute("INSERT INTO system_settings(key,value) VALUES('maintenance_text',$1) ON CONFLICT(key) DO UPDATE SET value=$1",json.dumps(text))
    await manager.broadcast({"type":"maintenance","enabled":enabled,"text":text})
    return {"ok":True}

@app.post("/api/owner/system/backup")
async def owner_backup(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    stats={}
    async with p.acquire() as conn:
        for tbl in ["users","dms","group_messages","gifts","groups","ranks","channels","channel_posts"]:
            try: stats[tbl]=await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")
            except: pass
    return {"ok":True,"tables":stats,"time":_iso(datetime.datetime.now(datetime.timezone.utc))}

@app.post("/api/owner/system/delete_all_msgs")
async def owner_delete_all_msgs(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM dms")
        await conn.execute("DELETE FROM group_messages")
        await conn.execute("DELETE FROM channel_posts")
    await manager.broadcast({"type":"force_reload"})
    return {"ok":True}

@app.post("/api/owner/system/reset_economy")
async def owner_reset_economy(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=0,candy=0,xp=0,level=1 WHERE id!=0")
    await manager.broadcast({"type":"force_reload"})
    return {"ok":True}

@app.post("/api/owner/broadcast/all")
async def owner_broadcast_all(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    from_name=(data.get("from_name") or "📢 Система").strip()[:64]
    if not text: raise HTTPException(400,"Текст")
    payload={"type":"abuse_announce","username":from_name,"text":text}
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,payload); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.post("/api/owner/announce_full")
async def owner_announce_full(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    text=(data.get("text") or "").strip()[:MAX_TEXT]
    if not text: raise HTTPException(400,"Пусто")
    payload={"type":"abuse_announce","username":(data.get("username") or user["username"])[:32],"text":text}
    sent=0
    for uid in list(manager.connections.keys()):
        try: await manager.send_to(uid,payload); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

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
            target=parts[1].lstrip("@");amount=int(parts[2]);field=parts[3] if len(parts)>3 else "coins"
            if field not in ("coins","candy","xp"): field="coins"
            async with p.acquire() as conn:
                if target.isdigit(): await conn.execute(f"UPDATE users SET {field}={field}+$1 WHERE id=$2",amount,int(target))
                else: await conn.execute(f"UPDATE users SET {field}={field}+$1 WHERE username=$2",amount,target)
            return {"ok":True,"result":f"+{amount} {field} → @{target}"}
        if action=="take" and len(parts)>=3:
            target=parts[1].lstrip("@");amount=int(parts[2]);field=parts[3] if len(parts)>3 else "coins"
            async with p.acquire() as conn:
                if target.isdigit(): await conn.execute(f"UPDATE users SET {field}=GREATEST(0,{field}-$1) WHERE id=$2",amount,int(target))
                else: await conn.execute(f"UPDATE users SET {field}=GREATEST(0,{field}-$1) WHERE username=$2",amount,target)
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
        if action=="announce" and len(parts)>=2:
            text=" ".join(parts[1:])[:1000]
            for uid in list(manager.connections.keys()):
                try: await manager.send_to(uid,{"type":"abuse_announce","username":"👑 Владелец","text":text})
                except: pass
            return {"ok":True,"result":f"📢 Отправлено"}
        if action=="theme" and len(parts)>=2:
            theme=parts[1]
            if theme not in ("dark","light","amoled"): raise HTTPException(400,"Тема")
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET theme=$1 WHERE id!=0",theme)
            await manager.broadcast({"type":"force_theme","theme":theme})
            return {"ok":True,"result":f"🎨 Тема {theme} всем"}
        if action=="help":
            return {"ok":True,"result":"give @user 100 [coins/candy/xp] | take @user 50 | ban @user | unban @user | announce текст | theme dark"}
    except HTTPException: raise
    except Exception as e: raise HTTPException(400,f"Ошибка: {e}")
    raise HTTPException(400,"Неизвестная. help")

@app.get("/api/site/features")
async def site_features():
    return {"features":{"calls":True,"dm":True,"registration":True,"games":True,"shop":True,"gifts":True,"bp":True,"premium":True,"file_upload":True,"voice":True,"groups":True,"channels":True,"street":True,"house":True,"market":True,"families":True,"pets":True,"capsules":True,"duels":True,"anonymous":True,"disappearing":True,"polls":True,"promocodes":True,"donate":True,"stories":True,"wall":True,"custom_reactions":True,"link_previews":True,"search":True,"slow_mode":True,"bad_words":True,"at_all":True,"calendar":True,"collections":True,"secret_rooms":True,"skins":True},"maintenance":False}

@app.post("/api/owner/site/feature")
async def owner_site_feature(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    return {"ok":True}

# ============ GAMES ============
@app.post("/api/games/submit")
async def games_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    game=data.get("game");score=int(data.get("score",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO game_scores(user_id,game,score) VALUES($1,$2,$3)",user["id"],game,score)
    await grant_xp(user["id"],5)
    return {"ok":True}

@app.get("/api/games/leaderboard")
async def games_leaderboard(game:str=""):
    p=await get_pool()
    async with p.acquire() as conn:
        if game:
            rows=await conn.fetch("SELECT gs.score,u.username,u.display_name FROM game_scores gs JOIN users u ON u.id=gs.user_id WHERE gs.game=$1 ORDER BY gs.score DESC LIMIT 50",game)
        else:
            rows=await conn.fetch("SELECT gs.score,u.username FROM game_scores gs JOIN users u ON u.id=gs.user_id ORDER BY gs.score DESC LIMIT 50")
    return [{"score":r["score"],"username":r["username"],"display_name":r.get("display_name") if "display_name" in r else r["username"]} for r in rows]

@app.post("/api/duel/fire")
async def duel_fire(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bet=int(data.get("bet",0))
    if bet<50: raise HTTPException(400,"Мин 50")
    if (user.get("coins") or 0)<bet: raise HTTPException(400,"Мало")
    win=random.random()<0.5
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",bet,user["id"])
        if win: await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",bet*2,user["id"])
    return {"ok":True,"win":win}

# ============ РЕФЕРАЛЬНАЯ ПРОГРАММА ============
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
        if existing:
            return {"ok":True,"code":existing["code"],"existing":True,"owner_username":target["username"]}
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

@app.get("/api/check_channel_username")
async def check_channel_username(u:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    u=(u or "").lower().strip()
    if len(u)<4: return {"available":False,"reason":"Мин 4"}
    if len(u)>32: return {"available":False,"reason":"Макс 32"}
    if not re.match(r'^[a-z][a-z0-9_]*$',u):
        return {"available":False,"reason":"Только a-z, 0-9, _"}
    if u in RESERVED_USERNAMES:
        return {"available":False,"reason":"Зарезервировано"}
    p=await get_pool()
    async with p.acquire() as conn:
        u1=await conn.fetchval("SELECT 1 FROM users WHERE username=$1",u)
        if u1: return {"available":False,"reason":"Занято юзером"}
        u2=await conn.fetchval("SELECT 1 FROM channels WHERE username=$1",u)
        if u2: return {"available":False,"reason":"Занято каналом"}
        u3=await conn.fetchval("SELECT 1 FROM groups WHERE username=$1",u)
        if u3: return {"available":False,"reason":"Занято группой"}
    return {"available":True}
# ============ 4.0: УЛИЦА ============
@app.get("/api/street/state")
async def street_state_get(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"rain":street_state["rain"],"night":street_state["night"],
            "vote_active":street_state["vote_active"],"vote_options":street_state["vote_options"],
            "klondike_active":len(klondike_active)>0}

@app.get("/api/street/users")
async def street_users(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT up.user_id,up.x,up.y,up.location,u.username,u.display_name,u.avatar,u.gif_avatar,u.avatar_pos,u.active_frame
            FROM user_positions up JOIN users u ON u.id=up.user_id WHERE up.location='street'""")
    return [{"user_id":r["user_id"],"x":r["x"],"y":r["y"],"username":r["username"],"display_name":r["display_name"],
             "avatar":r["gif_avatar"] or r["avatar"],"avatar_pos":r["avatar_pos"],"active_frame":r["active_frame"]} for r in rows]

@app.post("/api/street/move")
async def street_move(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    x=max(0,min(100,float(data.get("x",50))))
    y=max(0,min(100,float(data.get("y",50))))
    loc=data.get("location","street")
    if loc not in ("street","house"): loc="street"
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO user_positions(user_id,x,y,location,updated_at) VALUES($1,$2,$3,$4,NOW())
            ON CONFLICT(user_id) DO UPDATE SET x=$2,y=$3,location=$4,updated_at=NOW()""",user["id"],x,y,loc)
    await manager.broadcast({"type":"street_move","user_id":user["id"],"x":x,"y":y,"location":loc},exclude=user["id"])
    return {"ok":True}

@app.post("/api/street/rain")
async def street_rain(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    street_state["rain"]=bool(data.get("enabled",False))
    await manager.broadcast({"type":"street_rain","enabled":street_state["rain"]})
    return {"ok":True,"rain":street_state["rain"]}

@app.post("/api/street/night")
async def street_night(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    street_state["night"]=bool(data.get("enabled",False))
    await manager.broadcast({"type":"street_night","enabled":street_state["night"]})
    return {"ok":True,"night":street_state["night"]}

@app.post("/api/street/vote/start")
async def street_vote_start(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    opts=data.get("options") or ["ЗА","ПРОТИВ"]
    street_state["vote_active"]=True
    street_state["vote_options"]=opts
    street_state["vote_zones"]={o:[] for o in opts}
    await manager.broadcast({"type":"street_vote_start","options":opts})
    return {"ok":True}

@app.post("/api/street/vote/cast")
async def street_vote_cast(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if not street_state["vote_active"]: raise HTTPException(400,"Голосование не идёт")
    opt=data.get("option")
    if opt not in street_state["vote_zones"]: raise HTTPException(400,"Нет такой опции")
    for o in street_state["vote_zones"]:
        if user["id"] in street_state["vote_zones"][o]:
            street_state["vote_zones"][o].remove(user["id"])
    street_state["vote_zones"][opt].append(user["id"])
    await manager.broadcast({"type":"street_vote_update","zones":{k:len(v) for k,v in street_state["vote_zones"].items()}})
    return {"ok":True}

@app.post("/api/street/vote/end")
async def street_vote_end(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    street_state["vote_active"]=False
    result={k:len(v) for k,v in street_state["vote_zones"].items()}
    await manager.broadcast({"type":"street_vote_end","result":result})
    return {"ok":True,"result":result}

@app.post("/api/street/whisper/start")
async def whisper_start(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_id=int(data.get("to_user",0))
    if not to_id: raise HTTPException(400,"to_user")
    wid=secrets.token_hex(6)
    active_whispers[wid]={"a":user["id"],"b":to_id,"started":time.time()}
    await manager.send_to(to_id,{"type":"whisper_incoming","whisper_id":wid,"from_user":user["id"],"from_name":user.get("display_name") or user["username"]})
    return {"ok":True,"whisper_id":wid}

@app.post("/api/street/whisper/end")
async def whisper_end(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    wid=data.get("whisper_id")
    if wid in active_whispers:
        w=active_whispers[wid]
        other=w["b"] if w["a"]==user["id"] else w["a"]
        await manager.send_to(other,{"type":"whisper_ended","whisper_id":wid})
        del active_whispers[wid]
    return {"ok":True}

# ============ 4.0: ДОМ ============
@app.get("/api/house/my")
async def house_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        h=await conn.fetchrow("SELECT * FROM houses WHERE owner_id=$1",user["id"])
        if not h:
            h=await conn.fetchrow("INSERT INTO houses(owner_id,name,bg) VALUES($1,'Мой дом','room1') RETURNING *",user["id"])
        items=await conn.fetch("SELECT * FROM house_items WHERE house_id=$1",h["id"])
        lock=await conn.fetchrow("SELECT password FROM house_locks WHERE house_id=$1",h["id"])
    return {"id":h["id"],"name":h["name"],"bg":h["bg"],"has_flashlight":h["has_flashlight"],
            "items":[{"id":i["id"],"item_id":i["item_id"],"x":i["x"],"y":i["y"],"rot":i["rot"]} for i in items],
            "locked":bool(lock and lock["password"])}

@app.get("/api/house/catalog")
async def house_catalog():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM furniture_catalog ORDER BY price")
    return [{"item_id":r["item_id"],"name":r["name"],"emoji":r["emoji"],"price":r["price"],"category":r["category"]} for r in rows]

@app.post("/api/house/buy")
async def house_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    item_id=data.get("item_id")
    p=await get_pool()
    async with p.acquire() as conn:
        it=await conn.fetchrow("SELECT * FROM furniture_catalog WHERE item_id=$1",item_id)
        if not it: raise HTTPException(404,"Нет такого")
        h=await conn.fetchrow("SELECT id FROM houses WHERE owner_id=$1",user["id"])
        if not h:
            h=await conn.fetchrow("INSERT INTO houses(owner_id,name,bg) VALUES($1,'Мой дом','room1') RETURNING id",user["id"])
        if item_id!="flashlight":
            existing=await conn.fetchval("SELECT 1 FROM house_items WHERE house_id=$1 AND item_id=$2",h["id"],item_id)
            if existing: raise HTTPException(400,"Уже есть")
        if (user.get("coins") or 0)<it["price"]: raise HTTPException(400,"Мало коинов")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",it["price"],user["id"])
        await conn.execute("INSERT INTO house_items(house_id,item_id) VALUES($1,$2)",h["id"],item_id)
        if item_id=="flashlight":
            await conn.execute("UPDATE houses SET has_flashlight=TRUE WHERE id=$1",h["id"])
    return {"ok":True}

@app.post("/api/house/place")
async def house_place(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    iid=int(data.get("item_row_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        h=await conn.fetchrow("SELECT id FROM houses WHERE owner_id=$1",user["id"])
        if not h: raise HTTPException(404,"Нет дома")
        item=await conn.fetchrow("SELECT * FROM house_items WHERE id=$1 AND house_id=$2",iid,h["id"])
        if not item: raise HTTPException(404,"Нет предмета")
        await conn.execute("UPDATE house_items SET x=$1,y=$2,rot=$3 WHERE id=$4",float(data.get("x",50)),float(data.get("y",50)),float(data.get("rot",0)),iid)
    return {"ok":True}

@app.post("/api/house/lock")
async def house_lock(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    pw=(data.get("password") or "").strip()[:64]
    p=await get_pool()
    async with p.acquire() as conn:
        h=await conn.fetchrow("SELECT id FROM houses WHERE owner_id=$1",user["id"])
        if not h: raise HTTPException(404,"Нет дома")
        if not pw:
            await conn.execute("DELETE FROM house_locks WHERE house_id=$1",h["id"])
        else:
            await conn.execute("INSERT INTO house_locks(house_id,password) VALUES($1,$2) ON CONFLICT(house_id) DO UPDATE SET password=$2",h["id"],hashlib.sha256(pw.encode()).hexdigest()[:32])
    return {"ok":True}

@app.post("/api/house/enter")
async def house_enter(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    hid=int(data.get("house_id",0))
    pw=(data.get("password") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        h=await conn.fetchrow("SELECT * FROM houses WHERE id=$1",hid)
        if not h: raise HTTPException(404,"Нет дома")
        lock=await conn.fetchrow("SELECT password FROM house_locks WHERE house_id=$1",hid)
        if lock and lock["password"]:
            if hashlib.sha256(pw.encode()).hexdigest()[:32]!=lock["password"]:
                raise HTTPException(403,"Неверный пароль")
        items=await conn.fetch("SELECT * FROM house_items WHERE house_id=$1",hid)
    return {"ok":True,"house":{"id":h["id"],"name":h["name"],"bg":h["bg"],"has_flashlight":h["has_flashlight"],
            "items":[{"id":i["id"],"item_id":i["item_id"],"x":i["x"],"y":i["y"],"rot":i["rot"]} for i in items]}}

# ============ 4.0: БИРЖА ============
@app.get("/api/market/list")
async def market_list(token:str=""):
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT ml.*,u.username AS seller_name FROM market_listings ml JOIN users u ON u.id=ml.seller_id WHERE ml.sold=FALSE ORDER BY ml.id DESC LIMIT 100""")
    return [{"id":r["id"],"seller_id":r["seller_id"],"seller_name":r["seller_name"],"item_type":r["item_type"],
             "item_id":r["item_id"],"item_name":r["item_name"],"item_emoji":r["item_emoji"],"price":r["price"],
             "created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/market/sell")
async def market_sell(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    price=int(data.get("price",0))
    if price<1: raise HTTPException(400,"Цена")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO market_listings(seller_id,item_type,item_id,item_name,item_emoji,price)
            VALUES($1,$2,$3,$4,$5,$6)""",user["id"],(data.get("item_type") or "title")[:16],
            (data.get("item_id") or "")[:64],(data.get("item_name") or "")[:64],(data.get("item_emoji") or "")[:8],price)
    return {"ok":True}

@app.post("/api/market/buy")
async def market_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    lid=int(data.get("listing_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        l=await conn.fetchrow("SELECT * FROM market_listings WHERE id=$1 AND sold=FALSE",lid)
        if not l: raise HTTPException(404,"Нет или продано")
        if l["seller_id"]==user["id"]: raise HTTPException(400,"Своё нельзя")
        if (user.get("coins") or 0)<l["price"]: raise HTTPException(400,"Мало коинов")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",l["price"],user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",l["price"],l["seller_id"])
        await conn.execute("UPDATE market_listings SET sold=TRUE,buyer_id=$1 WHERE id=$2",user["id"],lid)
    await manager.send_to(l["seller_id"],{"type":"market_sold","listing_id":lid,"item_name":l["item_name"],"price":l["price"]})
    return {"ok":True}

@app.get("/api/coin/rate")
async def coin_rate_get():
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT rate,updated_at FROM coin_rate WHERE id=1")
        online=len(online_users)
        base=1.0+online*0.05
        new_rate=round(base+(random.random()-0.5)*0.2,3)
        if new_rate<0.5: new_rate=0.5
        await conn.execute("UPDATE coin_rate SET rate=$1,updated_at=NOW() WHERE id=1",new_rate)
    return {"rate":new_rate,"online":online}

# ============ 4.0: ЛУТБОКСЫ ============
@app.get("/api/lootboxes/list")
async def lootboxes_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        boxes=await conn.fetch("SELECT * FROM lootboxes WHERE is_active=TRUE")
        if not boxes:
            for k,v in LOOTBOX_DEFAULT.items():
                b=await conn.fetchrow("INSERT INTO lootboxes(name,price,emoji) VALUES($1,$2,$3) RETURNING *",v["name"],v["price"],v["emoji"])
            boxes=await conn.fetch("SELECT * FROM lootboxes WHERE is_active=TRUE")
    return [{"id":b["id"],"name":b["name"],"price":b["price"],"emoji":b["emoji"]} for b in boxes]

@app.post("/api/lootboxes/open")
async def lootbox_open(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bid=int(data.get("box_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        box=await conn.fetchrow("SELECT * FROM lootboxes WHERE id=$1 AND is_active=TRUE",bid)
        if not box: raise HTTPException(404,"Нет сундука")
        if (user.get("coins") or 0)<box["price"]: raise HTTPException(400,"Мало коинов")
        lc=await conn.fetchrow("SELECT attempts FROM luck_counter WHERE user_id=$1 AND box_id=$2",user["id"],bid)
        attempts=(lc["attempts"] if lc else 0)+1
        if attempts>=11:
            prize={"type":"coins","value":box["price"]*2,"name":"Гарант: возврат x2","emoji":"💎"}
            await conn.execute("UPDATE luck_counter SET attempts=0 WHERE user_id=$1 AND box_id=$2",user["id"],bid)
        else:
            roll=random.random()
            if roll<0.01: prize={"type":"coins","value":10000,"name":"Джекпот","emoji":"💠"}
            elif roll<0.1: prize={"type":"frame","value":"gold","name":"Золотая рамка","emoji":"👑"}
            elif roll<0.3: prize={"type":"coins","value":box["price"]*2,"name":f"+{box['price']*2} коинов","emoji":"🏅"}
            else: prize={"type":"coins","value":100,"name":"+100 коинов","emoji":"🏅"}
            if lc: await conn.execute("UPDATE luck_counter SET attempts=$1 WHERE user_id=$2 AND box_id=$3",attempts,user["id"],bid)
            else: await conn.execute("INSERT INTO luck_counter(user_id,box_id,attempts) VALUES($1,$2,$3)",user["id"],bid,attempts)
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",box["price"],user["id"])
        if prize["type"]=="coins":
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",prize["value"],user["id"])
        elif prize["type"]=="frame":
            row=await conn.fetchrow("SELECT frame_owned FROM users WHERE id=$1",user["id"])
            owned=_safe_json(row["frame_owned"],[])
            if prize["value"] not in owned: owned.append(prize["value"])
            await conn.execute("UPDATE users SET frame_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True,"prize":prize,"attempts":attempts}

# ============ 4.0: СЕМЬЯ ============
@app.get("/api/family/my")
async def family_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        fm=await conn.fetchrow("SELECT family_id FROM family_members WHERE user_id=$1",user["id"])
        if not fm: return {"family":None}
        f=await conn.fetchrow("SELECT * FROM families WHERE id=$1",fm["family_id"])
        if not f: return {"family":None}
        members=await conn.fetch("""SELECT fm.role,u.id,u.username,u.display_name,u.avatar,u.gif_avatar
            FROM family_members fm JOIN users u ON u.id=fm.user_id WHERE fm.family_id=$1""",f["id"])
    return {"family":{"id":f["id"],"name":f["name"],"owner_id":f["owner_id"],"wallet":f["wallet"],
            "members":[{"id":m["id"],"username":m["username"],"display_name":m["display_name"],
                        "avatar":m["gif_avatar"] or m["avatar"],"role":m["role"]} for m in members]}}

@app.post("/api/family/create")
async def family_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT 1 FROM family_members WHERE user_id=$1",user["id"]):
            raise HTTPException(400,"Уже в семье")
        f=await conn.fetchrow("INSERT INTO families(name,owner_id) VALUES($1,$2) RETURNING *",name,user["id"])
        await conn.execute("INSERT INTO family_members(family_id,user_id,role) VALUES($1,$2,'owner')",f["id"],user["id"])
    return {"ok":True,"id":f["id"]}

@app.post("/api/family/deposit")
async def family_deposit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    amount=int(data.get("amount",0))
    if amount<1: raise HTTPException(400,"Сумма")
    p=await get_pool()
    async with p.acquire() as conn:
        fm=await conn.fetchrow("SELECT family_id FROM family_members WHERE user_id=$1",user["id"])
        if not fm: raise HTTPException(400,"Не в семье")
        if (user.get("coins") or 0)<amount: raise HTTPException(400,"Мало")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amount,user["id"])
        await conn.execute("UPDATE families SET wallet=wallet+$1 WHERE id=$2",amount,fm["family_id"])
    return {"ok":True}

# ============ 4.0: ПИТОМЦЫ ============
@app.get("/api/pets/my")
async def pets_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM pets WHERE owner_id=$1",user["id"])
    return [{"id":r["id"],"name":r["name"],"species":r["species"],"level":r["level"],"xp":r["xp"],"hunger":r["hunger"]} for r in rows]

@app.post("/api/pets/adopt")
async def pets_adopt(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "Питомец").strip()[:32]
    species=data.get("species","cat")
    if species not in PET_SPECIES: species="cat"
    p=await get_pool()
    async with p.acquire() as conn:
        cnt=await conn.fetchval("SELECT COUNT(*) FROM pets WHERE owner_id=$1",user["id"])
        if cnt>=3: raise HTTPException(400,"Макс 3 питомца")
        r=await conn.fetchrow("INSERT INTO pets(owner_id,name,species) VALUES($1,$2,$3) RETURNING *",user["id"],name,species)
    return {"ok":True,"id":r["id"]}

@app.post("/api/pets/feed")
async def pets_feed(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    pid=int(data.get("pet_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        pet=await conn.fetchrow("SELECT * FROM pets WHERE id=$1 AND owner_id=$2",pid,user["id"])
        if not pet: raise HTTPException(404,"Нет питомца")
        if (user.get("coins") or 0)<50: raise HTTPException(400,"Мало коинов")
        await conn.execute("UPDATE users SET coins=coins-50 WHERE id=$1",user["id"])
        await conn.execute("UPDATE pets SET hunger=LEAST(100,hunger+20),xp=xp+10 WHERE id=$1",pid)
    return {"ok":True}

@app.get("/api/pets/market")
async def pets_market():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT pm.*,p.name AS pet_name,p.species,p.level,u.username AS seller_name
            FROM pet_market pm JOIN pets p ON p.id=pm.pet_id JOIN users u ON u.id=pm.seller_id
            WHERE pm.sold=FALSE ORDER BY pm.id DESC LIMIT 50""")
    return [{"id":r["id"],"pet_id":r["pet_id"],"pet_name":r["pet_name"],"species":r["species"],
             "level":r["level"],"price":r["price"],"seller_name":r["seller_name"]} for r in rows]

@app.post("/api/pets/sell")
async def pets_sell(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    pid=int(data.get("pet_id",0))
    price=int(data.get("price",0))
    if price<1: raise HTTPException(400,"Цена")
    p=await get_pool()
    async with p.acquire() as conn:
        pet=await conn.fetchrow("SELECT * FROM pets WHERE id=$1 AND owner_id=$2",pid,user["id"])
        if not pet: raise HTTPException(404,"Нет питомца")
        await conn.execute("INSERT INTO pet_market(pet_id,seller_id,price) VALUES($1,$2,$3)",pid,user["id"],price)
    return {"ok":True}

# ============ 4.0: АКЦИИ ============
@app.get("/api/stocks/list")
async def stocks_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT s.*,u.username,u.display_name FROM stocks s JOIN users u ON u.id=s.user_id ORDER BY s.price DESC LIMIT 50""")
    return [{"id":r["id"],"user_id":r["user_id"],"username":r["username"],"display_name":r["display_name"],
             "price":r["price"],"holders":r["holders"]} for r in rows]

@app.post("/api/stocks/buy")
async def stocks_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=int(data.get("stock_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT * FROM stocks WHERE id=$1",sid)
        if not s: raise HTTPException(404,"Нет акции")
        if (user.get("coins") or 0)<s["price"]: raise HTTPException(400,"Мало")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",s["price"],user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",s["price"],s["user_id"])
        existing=await conn.fetchrow("SELECT shares FROM stock_holders WHERE stock_id=$1 AND holder_id=$2",sid,user["id"])
        if existing:
            await conn.execute("UPDATE stock_holders SET shares=shares+1 WHERE stock_id=$1 AND holder_id=$2",sid,user["id"])
        else:
            await conn.execute("INSERT INTO stock_holders(stock_id,holder_id) VALUES($1,$2)",sid,user["id"])
        await conn.execute("UPDATE stocks SET holders=holders+1 WHERE id=$1",sid)
    return {"ok":True}

@app.post("/api/stocks/create")
async def stocks_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT 1 FROM stocks WHERE user_id=$1",user["id"]):
            raise HTTPException(400,"Уже есть")
        await conn.execute("INSERT INTO stocks(user_id,price) VALUES($1,$2)",user["id"],int(data.get("price",100)))
    return {"ok":True}

# ============ 4.0: КАПСУЛЫ ============
@app.post("/api/capsules/create")
async def capsule_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_id=int(data.get("to_user",0))
    text=(data.get("text") or "")[:MAX_TEXT]
    days=int(data.get("days",30))
    if not to_id or not text: raise HTTPException(400,"to_user и text")
    if days<CAPSULE_MIN_DAYS or days>CAPSULE_MAX_DAYS: raise HTTPException(400,f"Дни {CAPSULE_MIN_DAYS}-{CAPSULE_MAX_DAYS}")
    open_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=days)
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO time_capsules(from_user,to_user,text,open_at) VALUES($1,$2,$3,$4) RETURNING id",user["id"],to_id,text,open_at)
    return {"ok":True,"id":r["id"],"open_at":_iso(open_at)}

@app.get("/api/capsules/my")
async def capsules_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT tc.*,u.username AS to_name FROM time_capsules tc JOIN users u ON u.id=tc.to_user
            WHERE tc.to_user=$1 OR tc.from_user=$1 ORDER BY tc.open_at""",user["id"])
    return [{"id":r["id"],"from_user":r["from_user"],"to_user":r["to_user"],"to_name":r["to_name"],
             "opened":r["opened"],"open_at":_iso(r["open_at"]),"can_open":_aware(r["open_at"])<=datetime.datetime.now(datetime.timezone.utc),"text":r["text"] if _aware(r["open_at"])<=datetime.datetime.now(datetime.timezone.utc) else "[заблокировано]"} for r in rows]

# ============ 4.0: ДУЭЛИ ============
@app.post("/api/duels/challenge")
async def duel_challenge(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_id=int(data.get("to_user",0))
    bet=int(data.get("bet",0))
    if not to_id: raise HTTPException(400,"to_user")
    if (user.get("coins") or 0)<bet: raise HTTPException(400,"Мало")
    p=await get_pool()
    async with p.acquire() as conn:
        d=await conn.fetchrow("INSERT INTO duels(challenger,opponent,bet) VALUES($1,$2,$3) RETURNING *",user["id"],to_id,bet)
    await manager.send_to(to_id,{"type":"duel_challenge","duel_id":d["id"],"from_user":user["id"],"from_name":user.get("display_name") or user["username"],"bet":bet})
    return {"ok":True,"duel_id":d["id"]}

@app.post("/api/duels/accept")
async def duel_accept(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    did=int(data.get("duel_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        d=await conn.fetchrow("SELECT * FROM duels WHERE id=$1 AND opponent=$2 AND status='pending'",did,user["id"])
        if not d: raise HTTPException(404,"Нет дуэли")
        if (user.get("coins") or 0)<d["bet"]: raise HTTPException(400,"Мало")
        await conn.execute("UPDATE duels SET status='active' WHERE id=$1",did)
    await manager.send_to(d["challenger"],{"type":"duel_started","duel_id":did,"target_taps":d["target_taps"]})
    await manager.send_to(user["id"],{"type":"duel_started","duel_id":did,"target_taps":d["target_taps"]})
    return {"ok":True,"target_taps":d["target_taps"]}

@app.post("/api/duels/tap")
async def duel_tap(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    did=int(data.get("duel_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        d=await conn.fetchrow("SELECT * FROM duels WHERE id=$1 AND status='active'",did)
        if not d: raise HTTPException(404,"Нет активной")
        if user["id"]==d["challenger"]:
            await conn.execute("UPDATE duels SET challenger_taps=challenger_taps+1 WHERE id=$1",did)
            new=d["challenger_taps"]+1
            if new>=d["target_taps"]:
                await conn.execute("UPDATE duels SET status='finished',winner=$1 WHERE id=$2",user["id"],did)
                await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",d["bet"]*2,user["id"])
                await manager.send_to(d["opponent"],{"type":"duel_end","duel_id":did,"winner":user["id"],"bet":d["bet"]})
                return {"ok":True,"finished":True,"winner":user["id"]}
        elif user["id"]==d["opponent"]:
            await conn.execute("UPDATE duels SET opponent_taps=opponent_taps+1 WHERE id=$1",did)
            new=d["opponent_taps"]+1
            if new>=d["target_taps"]:
                await conn.execute("UPDATE duels SET status='finished',winner=$1 WHERE id=$2",user["id"],did)
                await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",d["bet"]*2,user["id"])
                await manager.send_to(d["challenger"],{"type":"duel_end","duel_id":did,"winner":user["id"],"bet":d["bet"]})
                return {"ok":True,"finished":True,"winner":user["id"]}
        else: raise HTTPException(403,"Не твоя дуэль")
    await manager.send_to(d["challenger"] if user["id"]==d["opponent"] else d["opponent"],{"type":"duel_progress","duel_id":did,"taps":new})
    return {"ok":True,"taps":new,"finished":False}

# ============ 4.0: АНОНИМКИ ============
@app.post("/api/anonymous/send")
async def anonymous_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_id=int(data.get("to_user",0))
    text=(data.get("text") or "")[:MAX_TEXT]
    q_mode=bool(data.get("question_mode",False))
    if not to_id or not text: raise HTTPException(400,"to_user и text")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO anonymous_messages(to_user,text,question_mode) VALUES($1,$2,$3) RETURNING id",to_id,text,q_mode)
    await manager.send_to(to_id,{"type":"anonymous_message","id":r["id"],"text":text,"question_mode":q_mode})
    return {"ok":True,"id":r["id"]}

@app.get("/api/anonymous/my")
async def anonymous_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM anonymous_messages WHERE to_user=$1 ORDER BY id DESC LIMIT 100",user["id"])
    return [{"id":r["id"],"text":r["text"],"question_mode":r["question_mode"],"answer":r["answer"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/anonymous/answer")
async def anonymous_answer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    answer=(data.get("answer") or "")[:MAX_TEXT]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE anonymous_messages SET answer=$1 WHERE id=$2 AND to_user=$3",answer,mid,user["id"])
    return {"ok":True}

@app.post("/api/confession/send")
async def confession_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_id=int(data.get("to_user",0))
    text=(data.get("text") or "")[:MAX_TEXT]
    if not to_id or not text: raise HTTPException(400,"to_user и text")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO confessions(to_user,text) VALUES($1,$2) RETURNING id",to_id,text)
    await manager.send_to(to_id,{"type":"confession_received","id":r["id"]})
    return {"ok":True,"id":r["id"]}

@app.get("/api/confessions/my")
async def confessions_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM confessions WHERE to_user=$1 ORDER BY id DESC LIMIT 100",user["id"])
    return [{"id":r["id"],"text":r["text"],"read_at":_iso(r["read_at"]),"created_at":_iso(r["created_at"])} for r in rows]

# ============ 4.0: САНТА ============
@app.post("/api/santa/create")
async def santa_create(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        users_list=await conn.fetch("SELECT id FROM users WHERE id!=0 ORDER BY RANDOM()")
    ids=[u["id"] for u in users_list]
    if len(ids)<2: raise HTTPException(400,"Мало юзеров")
    shuffled=ids[:]
    random.shuffle(shuffled)
    async with p.acquire() as conn:
        for i,uid in enumerate(ids):
            await conn.execute("INSERT INTO secret_santa(event_id,giver,receiver) VALUES($1,$2,$3)",int(data.get("event_id",1)),uid,shuffled[i])
    return {"ok":True,"count":len(ids)}

@app.get("/api/santa/my")
async def santa_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("""SELECT ss.*,u.username AS recv_name,u.display_name AS recv_display
            FROM secret_santa ss JOIN users u ON u.id=ss.receiver
            WHERE ss.giver=$1 ORDER BY ss.id DESC LIMIT 1""",user["id"])
    if not r: return {"santa":None}
    return {"santa":{"id":r["id"],"receiver_id":r["receiver"],"receiver_name":r["recv_display"] or r["recv_name"],"gift_sent":r["gift_sent"]}}

# ============ 4.0: ДЕТЕКТОР ЛЖИ ============
@app.post("/api/truth/start")
async def truth_start(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    target=int(data.get("target",0))
    question=(data.get("question") or "")[:500]
    if not target or not question: raise HTTPException(400,"target и question")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO truth_detector(asker,target,question) VALUES($1,$2,$3) RETURNING id",user["id"],target,question)
    await manager.send_to(target,{"type":"truth_question","id":r["id"],"question":question,"from_name":user.get("display_name") or user["username"]})
    return {"ok":True,"id":r["id"]}

@app.post("/api/truth/answer")
async def truth_answer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("id",0))
    time_ms=int(data.get("time_ms",0))
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM truth_detector WHERE id=$1 AND target=$2",tid,user["id"])
        if not r: raise HTTPException(404,"Нет вопроса")
        verdict="правда" if time_ms<3000 else "возможно врёт" if time_ms<6000 else "врёт"
        await conn.execute("UPDATE truth_detector SET answer_time_ms=$1,verdict=$2 WHERE id=$3",time_ms,verdict,tid)
    await manager.send_to(r["asker"],{"type":"truth_result","id":tid,"verdict":verdict,"time_ms":time_ms})
    return {"ok":True,"verdict":verdict}

# ============ 4.0: БОМБА ============
@app.post("/api/bomb/throw")
async def bomb_throw(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_id=int(data.get("to_user",0))
    if not to_id: raise HTTPException(400,"to_user")
    explodes_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=BOMB_FUSE_SECONDS)
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO bombs(from_user,to_user,explodes_at) VALUES($1,$2,$3) RETURNING id",user["id"],to_id,explodes_at)
    active_bombs[r["id"]]={"from":user["id"],"to":to_id,"explodes_at":explodes_at.timestamp()}
    await manager.send_to(to_id,{"type":"bomb_received","bomb_id":r["id"],"from_name":user.get("display_name") or user["username"],"fuse":BOMB_FUSE_SECONDS})
    return {"ok":True,"bomb_id":r["id"],"fuse":BOMB_FUSE_SECONDS}

@app.post("/api/bomb/pass")
async def bomb_pass(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bid=int(data.get("bomb_id",0))
    to_id=int(data.get("to_user",0))
    if bid not in active_bombs: raise HTTPException(404,"Нет бомбы")
    b=active_bombs[bid]
    if b["to"]!=user["id"]: raise HTTPException(403,"Не твоя")
    b["to"]=to_id
    await manager.send_to(to_id,{"type":"bomb_received","bomb_id":bid,"from_name":user.get("display_name") or user["username"],"fuse":int(b["explodes_at"]-time.time())})
    return {"ok":True}

@app.post("/api/bomb/defuse")
async def bomb_defuse(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bid=int(data.get("bomb_id",0))
    if bid in active_bombs: del active_bombs[bid]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE bombs SET defused=TRUE WHERE id=$1",bid)
    return {"ok":True}

# ============ 4.0: СПОР ============
@app.post("/api/bets/create")
async def bets_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    opp=int(data.get("opponent",0))
    amount=int(data.get("amount",0))
    cond=(data.get("condition_text") or "")[:256]
    if not opp or amount<1 or not cond: raise HTTPException(400,"Заполни всё")
    if (user.get("coins") or 0)<amount: raise HTTPException(400,"Мало")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amount,user["id"])
        r=await conn.fetchrow("INSERT INTO bets(creator,opponent,amount,condition_text) VALUES($1,$2,$3,$4) RETURNING id",user["id"],opp,amount,cond)
    await manager.send_to(opp,{"type":"bet_offer","id":r["id"],"from_name":user.get("display_name") or user["username"],"amount":amount,"condition":cond})
    return {"ok":True,"id":r["id"]}

@app.post("/api/bets/accept")
async def bets_accept(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bid=int(data.get("id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        b=await conn.fetchrow("SELECT * FROM bets WHERE id=$1 AND opponent=$2 AND status='pending'",bid,user["id"])
        if not b: raise HTTPException(404,"Нет спора")
        if (user.get("coins") or 0)<b["amount"]: raise HTTPException(400,"Мало")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",b["amount"],user["id"])
        await conn.execute("UPDATE bets SET status='active' WHERE id=$1",bid)
    return {"ok":True}

@app.post("/api/bets/resolve")
async def bets_resolve(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bid=int(data.get("id",0))
    winner=int(data.get("winner",0))
    p=await get_pool()
    async with p.acquire() as conn:
        b=await conn.fetchrow("SELECT * FROM bets WHERE id=$1 AND (creator=$2 OR opponent=$2)",bid,user["id"])
        if not b: raise HTTPException(404,"Нет спора")
        if winner not in (b["creator"],b["opponent"]): raise HTTPException(400,"Не тот")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",b["amount"]*2,winner)
        await conn.execute("UPDATE bets SET status='finished',winner=$1 WHERE id=$2",winner,bid)
    return {"ok":True}

# ============ 4.0: РИСОВАНИЕ ============
@app.post("/api/draw/start")
async def draw_start(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    guesser=int(data.get("guesser",0))
    word=(data.get("word") or "").strip()[:64]
    if not guesser or not word: raise HTTPException(400,"guesser и word")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO draw_battles(drawer,guesser,word) VALUES($1,$2,$3) RETURNING id",user["id"],guesser,word)
    draw_battles_active[r["id"]]={"drawer":user["id"],"guesser":guesser,"word":word.lower()}
    await manager.send_to(guesser,{"type":"draw_started","id":r["id"],"from_name":user.get("display_name") or user["username"]})
    return {"ok":True,"id":r["id"]}

@app.post("/api/draw/guess")
async def draw_guess(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    did=int(data.get("id",0))
    g=(data.get("guess") or "").strip().lower()
    if did not in draw_battles_active: raise HTTPException(404,"Нет игры")
    b=draw_battles_active[did]
    if b["guesser"]!=user["id"]: raise HTTPException(403,"Не ты угадываешь")
    correct=(g==b["word"])
    if correct:
        await manager.send_to(b["drawer"],{"type":"draw_won","id":did,"guesser_name":user.get("display_name") or user["username"]})
        del draw_battles_active[did]
    return {"ok":True,"correct":correct}

# ============ 4.0: СЛЕПАЯ ЗОНА ============
@app.post("/api/blind/send")
async def blind_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    text=(data.get("text") or "")[:MAX_TEXT]
    if not text: raise HTTPException(400,"text")
    p=await get_pool()
    async with p.acquire() as conn:
        online_ids=[u for u in list(online_users) if u!=user["id"]]
        random.shuffle(online_ids)
        targets=online_ids[:5]
        r=await conn.fetchrow("INSERT INTO blind_zones(from_user,text,answers) VALUES($1,$2,'[]') RETURNING id",user["id"],text)
    for t in targets:
        await manager.send_to(t,{"type":"blind_question","id":r["id"],"text":text})
    return {"ok":True,"id":r["id"],"sent_to":len(targets)}

@app.post("/api/blind/answer")
async def blind_answer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    bid=int(data.get("id",0))
    answer=(data.get("answer") or "")[:MAX_TEXT]
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM blind_zones WHERE id=$1",bid)
        if not r: raise HTTPException(404,"Нет")
        answers=_safe_json(r["answers"],[])
        answers.append({"from":user["id"],"answer":answer,"at":_iso(datetime.datetime.now(datetime.timezone.utc))})
        await conn.execute("UPDATE blind_zones SET answers=$1 WHERE id=$2",json.dumps(answers),bid)
    return {"ok":True}

@app.get("/api/blind/my")
async def blind_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM blind_zones WHERE from_user=$1 ORDER BY id DESC LIMIT 50",user["id"])
    return [{"id":r["id"],"text":r["text"],"answers":_safe_json(r["answers"],[]),"created_at":_iso(r["created_at"])} for r in rows]

# ============ 4.0: СУДЬБА ============
@app.post("/api/fate/spawn")
async def fate_spawn(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    effects=["bonus_500","mute_5m","avatar_random","bonus_1000","free_box"]
    eff=random.choice(effects)
    p=await get_pool()
    async with p.acquire() as conn:
        online=list(online_users)
        if not online: return {"ok":True,"spawned":0}
        tgt=random.choice(online)
        await conn.execute("INSERT INTO fate_buttons(user_id,effect) VALUES($1,$2)",tgt,eff)
    await manager.send_to(tgt,{"type":"fate_button","effect":eff})
    return {"ok":True,"spawned":1}

@app.post("/api/fate/claim")
async def fate_claim(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM fate_buttons WHERE user_id=$1 AND claimed=FALSE ORDER BY id DESC LIMIT 1",user["id"])
        if not r: raise HTTPException(404,"Нет кнопки")
        eff=r["effect"]
        if eff=="bonus_500": await conn.execute("UPDATE users SET coins=coins+500 WHERE id=$1",user["id"])
        elif eff=="bonus_1000": await conn.execute("UPDATE users SET coins=coins+1000 WHERE id=$1",user["id"])
        elif eff=="mute_5m": await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '5 minutes' WHERE id=$1",user["id"])
        elif eff=="avatar_random": pass
        await conn.execute("UPDATE fate_buttons SET claimed=TRUE WHERE id=$1",r["id"])
    return {"ok":True,"effect":eff}

# ============ 4.0: КЛОНДАЙК ============
@app.post("/api/klondike/spawn")
async def klondike_spawn(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    coins=int(data.get("coins",500))
    x=random.uniform(10,90);y=random.uniform(10,90)
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO klondike(x,y,coins) VALUES($1,$2,$3) RETURNING id",x,y,coins)
    klondike_active.append({"id":r["id"],"x":x,"y":y,"coins":coins})
    await manager.broadcast({"type":"klondike_spawned","id":r["id"],"x":x,"y":y,"coins":coins})
    return {"ok":True,"id":r["id"]}

@app.post("/api/klondike/claim")
async def klondike_claim(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    kid=int(data.get("id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        k=await conn.fetchrow("SELECT * FROM klondike WHERE id=$1 AND claimed=FALSE",kid)
        if not k: raise HTTPException(404,"Уже забрали")
        await conn.execute("UPDATE klondike SET claimed=TRUE,claimed_by=$1 WHERE id=$2",user["id"],kid)
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",k["coins"],user["id"])
    for i,kx in enumerate(klondike_active):
        if kx["id"]==kid: klondike_active.pop(i);break
    await manager.broadcast({"type":"klondike_claimed","id":kid,"by_user":user["id"],"by_name":user.get("display_name") or user["username"]})
    return {"ok":True,"coins":k["coins"]}
# ============ 4.2: ИСЧЕЗАЮЩИЕ СООБЩЕНИЯ ============
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
        else:
            await conn.execute("UPDATE group_messages SET edited_at=edited_at WHERE id=$1",message_id)
    await manager.broadcast({"type":"disappearing_set","chat_type":chat_type,"chat_id":chat_id,"message_id":message_id,"expires_at":_iso(expires_at)})
    return {"ok":True,"expires_at":_iso(expires_at)}

@app.get("/api/messages/disappearing/{ct}/{cid}")
async def messages_disappearing_list(ct:str,cid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT message_id,expires_at FROM disappearing_messages WHERE chat_type=$1 AND chat_id=$2 AND expires_at>NOW()",ct,cid)
    return [{"message_id":r["message_id"],"expires_at":_iso(r["expires_at"])} for r in rows]

# ============ 4.2: ОПРОСЫ ============
@app.post("/api/polls/create")
async def poll_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    question=(data.get("question") or "").strip()[:256]
    options=data.get("options") or []
    if not gid or not question: raise HTTPException(400,"group_id и question")
    if not isinstance(options,list) or len(options)<2 or len(options)>10: raise HTTPException(400,"2-10 вариантов")
    clean=[str(o)[:64] for o in options if str(o).strip()]
    if len(clean)<2: raise HTTPException(400,"2-10 вариантов")
    multiple=bool(data.get("multiple",False))
    closes_at=None
    if data.get("closes_in_minutes"):
        closes_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=int(data["closes_in_minutes"]))
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        r=await conn.fetchrow("""INSERT INTO polls(group_id,creator,question,options,votes,multiple,closes_at)
            VALUES($1,$2,$3,$4,'{}',$5,$6) RETURNING *""",gid,user["id"],question,json.dumps(clean),multiple,closes_at)
        members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
    payload={"type":"poll_created","poll_id":r["id"],"group_id":gid,"question":question,"options":clean,"multiple":multiple,"creator_name":user.get("display_name") or user["username"]}
    for m in members:
        if m["user_id"]!=user["id"]: await manager.send_to(m["user_id"],payload)
    return {"ok":True,"id":r["id"]}

@app.get("/api/polls/{gid}")
async def polls_list(gid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        rows=await conn.fetch("SELECT * FROM polls WHERE group_id=$1 ORDER BY id DESC LIMIT 50",gid)
    out=[]
    for r in rows:
        out.append({"id":r["id"],"question":r["question"],"options":_safe_json(r["options"],[]),"votes":_safe_json(r["votes"],{}),"multiple":r["multiple"],"closed":r["closed"],"closes_at":_iso(r["closes_at"]),"created_at":_iso(r["created_at"])})
    return out

@app.post("/api/polls/{pid}/vote")
async def poll_vote(pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    opt=data.get("option")
    if opt is None: raise HTTPException(400,"option")
    p=await get_pool()
    async with p.acquire() as conn:
        poll=await conn.fetchrow("SELECT * FROM polls WHERE id=$1",pid)
        if not poll: raise HTTPException(404,"Нет опроса")
        if poll["closed"]: raise HTTPException(400,"Опрос закрыт")
        opts=_safe_json(poll["options"],[])
        if opt not in opts: raise HTTPException(400,"Нет такого варианта")
        votes=_safe_json(poll["votes"],{})
        arr=votes.get(opt,[])
        if user["id"] in arr:
            if poll["multiple"]: arr.remove(user["id"])
            else: raise HTTPException(400,"Уже голосовал")
        else:
            if not poll["multiple"]:
                for k in votes:
                    if user["id"] in votes[k]: votes[k].remove(user["id"])
            arr.append(user["id"])
        votes[opt]=arr
        await conn.execute("UPDATE polls SET votes=$1 WHERE id=$2",json.dumps(votes),pid)
    await manager.broadcast({"type":"poll_updated","poll_id":pid,"votes":{k:len(v) for k,v in votes.items()}})
    return {"ok":True,"votes":{k:len(v) for k,v in votes.items()}}

@app.post("/api/polls/{pid}/close")
async def poll_close(pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        poll=await conn.fetchrow("SELECT * FROM polls WHERE id=$1",pid)
        if not poll: raise HTTPException(404,"Нет опроса")
        if poll["creator"]!=user["id"] and user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только создатель")
        await conn.execute("UPDATE polls SET closed=TRUE WHERE id=$1",pid)
    await manager.broadcast({"type":"poll_closed","poll_id":pid})
    return {"ok":True}

# ============ 4.2: ПРОМОКОДЫ ============
@app.post("/api/promocodes/create")
async def promocodes_create(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    code=(data.get("code") or "").strip().upper()[:32]
    reward=int(data.get("reward",100))
    max_act=int(data.get("max_activations",1))
    for_user=data.get("for_user")
    if not code: raise HTTPException(400,"Код")
    if reward<1: raise HTTPException(400,"Reward")
    if max_act<0 or max_act>PROMO_MAX_ACTIVATIONS: raise HTTPException(400,"Max")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT 1 FROM promocodes WHERE code=$1",code):
            raise HTTPException(400,"Код занят")
        r=await conn.fetchrow("""INSERT INTO promocodes(code,reward,max_activations,created_by,for_user)
            VALUES($1,$2,$3,$4,$5) RETURNING id""",code,reward,max_act,user["id"],int(for_user) if for_user else None)
    await log_admin(user["id"],"promo_create",r["id"],code)
    return {"ok":True,"id":r["id"],"code":code}

@app.post("/api/promocodes/activate")
async def promocodes_activate(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    code=(data.get("code") or "").strip().upper()
    if not code: raise HTTPException(400,"Код")
    p=await get_pool()
    async with p.acquire() as conn:
        pr=await conn.fetchrow("SELECT * FROM promocodes WHERE code=$1 AND active=TRUE",code)
        if not pr: raise HTTPException(404,"Нет такого кода")
        if pr["max_activations"]>0 and pr["activations"]>=pr["max_activations"]: raise HTTPException(400,"Код исчерпан")
        if pr["for_user"] and pr["for_user"]!=user["id"]: raise HTTPException(403,"Код не для тебя")
        if pr["expires_at"] and _aware(pr["expires_at"])<datetime.datetime.now(datetime.timezone.utc): raise HTTPException(400,"Код истёк")
        prev=await conn.fetchrow("SELECT 1 FROM promo_activations WHERE promo_id=$1 AND user_id=$2",pr["id"],user["id"])
        if prev: raise HTTPException(400,"Ты уже активировал")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",pr["reward"],user["id"])
        await conn.execute("UPDATE promocodes SET activations=activations+1 WHERE id=$1",pr["id"])
        await conn.execute("INSERT INTO promo_activations(promo_id,user_id,reward) VALUES($1,$2,$3)",pr["id"],user["id"],pr["reward"])
    return {"ok":True,"reward":pr["reward"]}

@app.get("/api/promocodes/list")
async def promocodes_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if user["username"]==ADMIN_USERNAME:
            rows=await conn.fetch("""SELECT p.*,u.username AS creator_name FROM promocodes p LEFT JOIN users u ON u.id=p.created_by ORDER BY p.id DESC LIMIT 200""")
        else:
            rows=await conn.fetch("SELECT * FROM promocodes WHERE for_user=$1 AND active=TRUE ORDER BY id DESC",user["id"])
    return [{"id":r["id"],"code":r["code"],"reward":r["reward"],"max_activations":r["max_activations"],"activations":r["activations"],"for_user":r["for_user"],"creator_name":r.get("creator_name") if "creator_name" in r else None,"active":r["active"],"expires_at":_iso(r["expires_at"]),"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/promocodes/deactivate")
async def promocodes_deactivate(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    pid=int(data.get("id",0))
    if not pid: raise HTTPException(400,"id")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE promocodes SET active=FALSE WHERE id=$1",pid)
    return {"ok":True}

@app.get("/api/promocodes/logs")
async def promocodes_logs(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT pa.*,u.username,p.code FROM promo_activations pa
            JOIN users u ON u.id=pa.user_id JOIN promocodes p ON p.id=pa.promo_id
            ORDER BY pa.id DESC LIMIT 500""")
    return [{"id":r["id"],"promo_code":r["code"],"username":r["username"],"reward":r["reward"],"activated_at":_iso(r["activated_at"])} for r in rows]

# ============ 4.2: ДОНАТ-ЗАЯВКИ ============
@app.post("/api/donate/request")
async def donate_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    amount=int(data.get("amount",0))
    msg=(data.get("message") or "")[:500]
    if amount<1: raise HTTPException(400,"Сумма")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO donate_requests(user_id,amount,message) VALUES($1,$2,$3) RETURNING id",user["id"],amount,msg)
    return {"ok":True,"id":r["id"]}

@app.get("/api/donate/requests")
async def donate_requests_list(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT dr.*,u.username,u.display_name FROM donate_requests dr JOIN users u ON u.id=dr.user_id ORDER BY dr.id DESC LIMIT 200""")
    return [{"id":r["id"],"user_id":r["user_id"],"username":r["username"],"display_name":r["display_name"],"amount":r["amount"],"message":r["message"],"status":r["status"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/donate/{rid}/approve")
async def donate_approve(rid:int,data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM donate_requests WHERE id=$1 AND status='pending'",rid)
        if not r: raise HTTPException(404,"Нет или уже обработана")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",r["amount"],r["user_id"])
        await conn.execute("UPDATE donate_requests SET status='approved',reviewed_by=$1,reviewed_at=NOW() WHERE id=$2",user["id"],rid)
    await manager.send_to(r["user_id"],{"type":"donate_approved","amount":r["amount"]})
    return {"ok":True}

@app.post("/api/donate/{rid}/reject")
async def donate_reject(rid:int,data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE donate_requests SET status='rejected',reviewed_by=$1,reviewed_at=NOW() WHERE id=$2 AND status='pending'",user["id"],rid)
    return {"ok":True}

# ============ 4.2: ИСТОРИИ ============
@app.post("/api/stories/create")
async def story_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    kind=data.get("kind","text")[:16]
    content=(data.get("content") or "")[:500]
    file_url=data.get("file_url")
    if not content and not file_url: raise HTTPException(400,"Пусто")
    expires_at=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=STORY_TTL_HOURS)
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO stories(user_id,kind,content,file_url,expires_at) VALUES($1,$2,$3,$4,$5) RETURNING id",user["id"],kind,content,file_url,expires_at)
    await manager.broadcast({"type":"new_story","user_id":user["id"],"username":user["username"]})
    return {"ok":True,"id":r["id"]}

@app.get("/api/stories/feed")
async def stories_feed(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT s.*,u.username,u.display_name,u.avatar,u.gif_avatar FROM stories s
            JOIN users u ON u.id=s.user_id
            WHERE s.expires_at>NOW() AND (u.id=$1 OR u.id IN (SELECT CASE WHEN user_a=$1 THEN user_b ELSE user_a END FROM friendships WHERE user_a=$1 OR user_b=$1))
            ORDER BY s.id DESC LIMIT 100""",user["id"])
    return [{"id":r["id"],"user_id":r["user_id"],"username":r["username"],"display_name":r["display_name"],"avatar":r["gif_avatar"] or r["avatar"],"kind":r["kind"],"content":r["content"],"file_url":r["file_url"],"views":r["views"],"expires_at":_iso(r["expires_at"]),"created_at":_iso(r["created_at"])} for r in rows]

@app.get("/api/stories/user/{uid}")
async def stories_user(uid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM stories WHERE user_id=$1 AND expires_at>NOW() ORDER BY id DESC",uid)
        for r in rows:
            try: await conn.execute("INSERT INTO story_views(story_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",r["id"],user["id"])
            except: pass
        await conn.execute("UPDATE stories SET views=(SELECT COUNT(*) FROM story_views WHERE story_id=stories.id) WHERE user_id=$1 AND expires_at>NOW()",uid)
    return [{"id":r["id"],"kind":r["kind"],"content":r["content"],"file_url":r["file_url"],"views":r["views"],"expires_at":_iso(r["expires_at"]),"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/stories/{sid}/delete")
async def story_delete(sid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT user_id FROM stories WHERE id=$1",sid)
        if not r: raise HTTPException(404,"Нет")
        if r["user_id"]!=user["id"] and user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Не твоя")
        await conn.execute("DELETE FROM stories WHERE id=$1",sid)
    return {"ok":True}

# ============ 4.2: СТЕНА ПРОФИЛЯ ============
@app.get("/api/wall/{uid}")
async def wall_list(uid:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT pw.*,u.username,u.display_name,u.avatar,u.gif_avatar FROM profile_wall pw
            JOIN users u ON u.id=pw.author WHERE pw.profile_user=$1 ORDER BY pw.id DESC LIMIT 100""",uid)
    return [{"id":r["id"],"author_id":r["author"],"username":r["username"],"display_name":r["display_name"],"avatar":r["gif_avatar"] or r["avatar"],"text":r["text"],"created_at":_iso(r["created_at"])} for r in rows]

@app.post("/api/wall/{uid}/post")
async def wall_post(uid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    text=(data.get("text") or "").strip()[:1000]
    if not text: raise HTTPException(400,"Текст")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO profile_wall(profile_user,author,text) VALUES($1,$2,$3) RETURNING id",uid,user["id"],text)
    if uid!=user["id"]:
        await manager.send_to(uid,{"type":"wall_post","from_name":user.get("display_name") or user["username"]})
    return {"ok":True,"id":r["id"]}

@app.post("/api/wall/{pid}/delete")
async def wall_delete(pid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM profile_wall WHERE id=$1",pid)
        if not r: raise HTTPException(404,"Нет")
        if r["author"]!=user["id"] and r["profile_user"]!=user["id"] and user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Нельзя")
        await conn.execute("DELETE FROM profile_wall WHERE id=$1",pid)
    return {"ok":True}

# ============ 4.2: КАСТОМНЫЕ РЕАКЦИИ ============
@app.get("/api/custom_reactions/my")
async def custom_reactions_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM custom_reactions WHERE user_id=$1 ORDER BY id DESC",user["id"])
    return [{"id":r["id"],"emoji_id":r["emoji_id"],"name":r["name"],"image_url":r["image_url"]} for r in rows]

@app.post("/api/custom_reactions/create")
async def custom_reactions_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    image_url=(data.get("image_url") or "").strip()
    if not name or not image_url: raise HTTPException(400,"name и image_url")
    eid=f"cr_{secrets.token_hex(6)}"
    p=await get_pool()
    async with p.acquire() as conn:
        cnt=await conn.fetchval("SELECT COUNT(*) FROM custom_reactions WHERE user_id=$1",user["id"])
        if cnt>=30: raise HTTPException(400,"Макс 30")
        r=await conn.fetchrow("INSERT INTO custom_reactions(user_id,emoji_id,name,image_url) VALUES($1,$2,$3,$4) RETURNING *",user["id"],eid,name,image_url)
    return {"ok":True,"id":r["id"],"emoji_id":r["emoji_id"]}

@app.post("/api/custom_reactions/{cid}/delete")
async def custom_reactions_delete(cid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM custom_reactions WHERE id=$1",cid)
        if not r: raise HTTPException(404,"Нет")
        if r["user_id"]!=user["id"]: raise HTTPException(403,"Не твоя")
        await conn.execute("DELETE FROM custom_reactions WHERE id=$1",cid)
    return {"ok":True}

# ============ 4.2: ПРЕВЬЮ ССЫЛОК ============
@app.get("/api/link_preview")
async def link_preview(url:str):
    if not url or not url.startswith(("http://","https://")): raise HTTPException(400,"URL")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM link_previews WHERE url=$1",url)
        if row:
            return {"title":row["title"],"description":row["description"],"image":row["image"],"site_name":row["site_name"]}
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

# ============ 4.2: ПОИСК ПО СООБЩЕНИЯМ ============
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

# ============ 4.2: МЕДЛЕННЫЙ РЕЖИМ ============
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

# ============ 4.2: ЧЁРНЫЙ СПИСОК СЛОВ ============
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

# ============ 4.2: КАЛЕНДАРЬ ИВЕНТОВ ============
@app.get("/api/events/upcoming")
async def events_upcoming(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM events_calendar WHERE event_date>=NOW() ORDER BY event_date ASC LIMIT 50")
    return [{"id":r["id"],"title":r["title"],"description":r["description"],"event_date":_iso(r["event_date"]),"emoji":r["emoji"]} for r in rows]

@app.post("/api/events/create")
async def events_create(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    title=(data.get("title") or "").strip()[:128]
    desc=(data.get("description") or "")[:1000]
    dt=data.get("event_date")
    if not title or not dt: raise HTTPException(400,"title и event_date")
    try:
        event_date=datetime.datetime.fromisoformat(dt.replace("Z","+00:00"))
    except: raise HTTPException(400,"Неверная дата")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO events_calendar(title,description,event_date,emoji,created_by) VALUES($1,$2,$3,$4,$5) RETURNING id",title,desc,event_date,(data.get("emoji") or "📅")[:8],user["id"])
    await manager.broadcast({"type":"new_event","title":title,"event_date":_iso(event_date),"emoji":data.get("emoji") or "📅"})
    return {"ok":True,"id":r["id"]}

@app.post("/api/events/{eid}/delete")
async def events_delete(eid:int,data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM events_calendar WHERE id=$1",eid)
    return {"ok":True}

# ============ 4.2: КОЛЛЕКЦИИ ============
@app.get("/api/collections/{uid}")
async def collections_get(uid:int,token:str):
    viewer=await get_current_user(token)
    if not viewer: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchrow("SELECT * FROM users WHERE id=$1",uid)
        if not u: raise HTTPException(404,"Нет юзера")
        gift_rows=await conn.fetch("SELECT gift,COUNT(*) AS cnt FROM gifts WHERE to_user=$1 GROUP BY gift",uid)
        pet_rows=await conn.fetch("SELECT species,COUNT(*) AS cnt FROM pets WHERE owner_id=$1 GROUP BY species",uid)
    return {"frames":_safe_json(u["frame_owned"],[]),"titles":_safe_json(u["title_owned"],[]),"achievements":_safe_json(u["achievements"],[]),"gifts":[{"gift":r["gift"],"count":r["cnt"]} for r in gift_rows],"pets":[{"species":r["species"],"count":r["cnt"]} for r in pet_rows]}

# ============ 4.2: ТАЙНЫЕ КОМНАТЫ ============
@app.post("/api/rooms/create")
async def room_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    pw=(data.get("password") or "").strip()
    if not name: raise HTTPException(400,"Имя")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO secret_rooms(name,password_hash,owner_id,capacity) VALUES($1,$2,$3,$4) RETURNING id",name,hashlib.sha256(pw.encode()).hexdigest()[:64] if pw else None,user["id"],int(data.get("capacity",10)))
        await conn.execute("INSERT INTO room_members(room_id,user_id) VALUES($1,$2)",r["id"],user["id"])
    return {"ok":True,"id":r["id"]}

@app.post("/api/rooms/join/{rid}")
async def room_join(rid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    pw=(data.get("password") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM secret_rooms WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Нет комнаты")
        if r["password_hash"] and hashlib.sha256(pw.encode()).hexdigest()[:64]!=r["password_hash"]:
            raise HTTPException(403,"Неверный пароль")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM room_members WHERE room_id=$1",rid)
        if cnt>=r["capacity"]: raise HTTPException(400,"Комната заполнена")
        await conn.execute("INSERT INTO room_members(room_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",rid,user["id"])
    return {"ok":True}

@app.get("/api/rooms/my")
async def rooms_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT r.*,u.username AS owner_name,(SELECT COUNT(*) FROM room_members WHERE room_id=r.id) AS members FROM secret_rooms r
            JOIN users u ON u.id=r.owner_id
            WHERE r.id IN (SELECT room_id FROM room_members WHERE user_id=$1) ORDER BY r.id DESC""",user["id"])
    return [{"id":r["id"],"name":r["name"],"owner_id":r["owner_id"],"owner_name":r["owner_name"],"capacity":r["capacity"],"members":r["members"],"locked":bool(r["password_hash"])} for r in rows]

@app.post("/api/rooms/{rid}/leave")
async def room_leave(rid:int,data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM room_members WHERE room_id=$1 AND user_id=$2",rid,user["id"])
    return {"ok":True}

# ============ 4.2: СКИНЫ ============
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
                await manager.send_to(uid,{"type":"error","detail":"✈️ Авиарежим"})
                continue

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
                if fsize>0: await grant_achievement(uid,"first_file")
                await grant_xp(uid,1)
                dn=user.get("display_name") or user["username"]
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"display_name":dn,"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"text":text,"file_url":furl,"file_size":fsize,"msg_kind":msg_kind,"voice_duration":voice_dur,"reply_to_id":reply_to,"expires_at":_iso(expires_at),"msg_shape":msg_shape,"created_at":_iso(msg["created_at"]),"temp_id":tid}
                if not blocked: await manager.send_to(to_id,payload)
                await manager.send_to(uid,payload)
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
            elif t=="whisper_ice":
                to_id=int(data.get("to_user",0))
                wid=data.get("whisper_id")
                cand=data.get("candidate")
                if to_id: await manager.send_to(to_id,{"type":"whisper_ice","from_user":uid,"whisper_id":wid,"candidate":cand})
            elif t=="bomb_tick":
                bid=int(data.get("bomb_id",0))
                if bid in active_bombs:
                    remaining=int(active_bombs[bid]["explodes_at"]-time.time())
                    if remaining<=0:
                        target=active_bombs[bid]["to"]
                        try:
                            p=await get_pool()
                            async with p.acquire() as conn:
                                await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '10 minutes' WHERE id=$1",target)
                        except: pass
                        await manager.send_to(target,{"type":"bomb_exploded","bomb_id":bid,"muted_minutes":10})
                        del active_bombs[bid]
                    else:
                        await manager.send_to(active_bombs[bid]["to"],{"type":"bomb_tick","bomb_id":bid,"remaining":remaining})
            elif t=="draw_stroke":
                to_id=int(data.get("to_user",0))
                if not to_id: continue
                await manager.send_to(to_id,{"type":"draw_stroke","data":data.get("data")})
    except WebSocketDisconnect: pass
    except Exception as e:
        print(f"[WS] {type(e).__name__}: {e}")
        traceback.print_exc()
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

# ============ ИСЧЕЗАЮЩИЕ СООБЩЕНИЯ — АВТО-УДАЛЕНИЕ ============
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
                            await conn.execute("UPDATE dms SET text='[исчезло]',file_url=NULL WHERE id=$1",r["message_id"])
                        else:
                            await conn.execute("UPDATE group_messages SET text='[исчезло]',file_url=NULL WHERE id=$1",r["message_id"])
                        await manager.broadcast({"type":"message_vanished","chat_type":r["chat_type"],"message_id":r["message_id"]})
                        await conn.execute("DELETE FROM disappearing_messages WHERE id=$1",r["id"])
                    except: pass
                await conn.execute("DELETE FROM stories WHERE expires_at<=NOW()")
        except Exception as e:
            print(f"[disappearing] {e}")

@app.on_event("startup")
async def start_cleaner():
    asyncio.create_task(disappearing_cleaner())

# ============ STATIC ============
@app.get("/manifest.json")
async def manifest():
    return {"name":"BelugaCord 4.2","short_name":"BelugaCord","start_url":"/","display":"standalone","background_color":"#1a0a2e","theme_color":"#dc2626","icons":[{"src":"/icon-192x192.png","sizes":"192x192","type":"image/png"}]}

@app.get("/sw.js")
async def sw():
    try:
        with open("sw.js","r",encoding="utf-8") as f: return HTMLResponse(f.read(),media_type="application/javascript")
    except: return HTMLResponse("// no sw",media_type="application/javascript")

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
    except Exception as e: return HTMLResponse(f"<h1>index.html нет</h1><p>{e}</p>",status_code=500)

if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")