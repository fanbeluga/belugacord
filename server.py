	import os,json,time,secrets,hashlib,random,datetime,asyncio
from typing import Optional
import asyncpg
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL=os.environ.get("DATABASE_URL","")
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2026")
ADMIN_USERNAME="_fan_beluga_"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="1.9"
LIMITS={None:{"file":10*1024*1024,"msg":2000,"servers":10,"channels":20},"premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100},"pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999}}
DEFAULT_GIFTS={"rose":{"name":"Роза","emoji":"🌹","price":15},"bear":{"name":"Мишка","emoji":"🧸","price":25},"cake":{"name":"Торт","emoji":"🎂","price":50},"diamond":{"name":"Алмаз","emoji":"💎","price":100},"crown":{"name":"Корона","emoji":"👑","price":500},"dragon":{"name":"Дракон","emoji":"🐉","price":1000},"legend":{"name":"Легендарка","emoji":"💠","price":5000},"alien":{"name":"Инопланетянин","emoji":"👽","price":10000},"galaxy":{"name":"Галактика","emoji":"🌌","price":100000},"goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},"universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000}}
EASTER_EGGS=["song","cat","beluga"]
GAME_LIST=["penguin","minesweeper","snake","2048","flappy","tetris","memory","reaction"]
ACHIEVEMENTS={"first_msg":{"name":"Первое слово","emoji":"💬","desc":"Отправь первое сообщение"},"msg_100":{"name":"Болтун","emoji":"🗣️","desc":"100 сообщений"},"msg_1000":{"name":"Оратор","emoji":"🎤","desc":"1000 сообщений"},"msg_10000":{"name":"Легенда чата","emoji":"📢","desc":"10000 сообщений"},"first_friend":{"name":"Дружелюбный","emoji":"👥","desc":"Первый друг"},"friend_10":{"name":"Тусовщик","emoji":"🎉","desc":"10 друзей"},"first_gift":{"name":"Щедрый","emoji":"🎁","desc":"Первый подарок"},"first_nft":{"name":"Коллекционер","emoji":"🎨","desc":"Первый NFT"},"snake_100":{"name":"Змеелов","emoji":"🐍","desc":"100 очков в Змейке"},"flappy_50":{"name":"Летун","emoji":"🐦","desc":"50 очков в Flappy"},"first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},"coins_10k":{"name":"Богач","emoji":"💰","desc":"10000 бекоинов"}}
CHANGELOG={"1.9":{"title":"Belugacord Beta 1.9","items":["🎨 Тема CS 1.6","👥 Группы (создание, аватар, кик, добавление)","💬 Ответы на сообщения","📌 Пин сообщений","🔍 Поиск по сообщениям","✅ Метка (изменено)","📝 Черновики","@️⃣ Упоминания @ник","📞 Групповые звонки","🎤 Индикатор говорит","🎬 Запись звонка","😴 Статусы (онлайн/DND/невидимка)","💭 Кастомный статус","🚫 Блок-лист","📊 Сортировка друзей","🏆 Достижения","🥇 Топ-3 игр","💰 Рынок NFT","🎁 Кейсы","💸 Перевод бекоинов","⏰ Авто-абьюз по расписанию","😈 Troll-меню","🌩️ Шторм","✏️ Массовое переименование","👁️ Шпион","📜 Логи админов в GUI","👑 Владелецский чат","🌓 Авто тема","🖼️ Кастомные обои","📐 Компактный режим","🔤 Смена шрифта","✨ Анимация сообщений","🎨 Свои стикеры","📱 PWA","📴 Оффлайн-очередь","🔄 Reconnect WS"]},"1.8":{"title":"Belugacord Beta 1.8","items":["✅ Друзья переписаны","😈 ADMIN ABUSE","🤝 Кооп-абьюз","🚨 Бан-заявки","📊 Suspicious-логи","🎮 Новые игры","🏆 Турниры","🖥️ Звонки с экраном","⏱️ Таймер абьюза"]},"1.7":{"title":"Belugacord Beta 1.7","items":["📞 Звонки","📑 Табы","🟢 Онлайн-кружок","🎁 Кастом подарки","🎨 NFT с картинками"]},"1.6":{"title":"Belugacord Beta 1.6","items":["🔍 Поиск","👥 Друзья","⚙️ Настройки сервера","📱 Мобилка"]},"0.6":{"title":"Belugacord 0.6","items":["Первый релиз","Темы, магазин, NFT"]}}

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
abuse_timer_task=None
auto_abuse_task=None
draft_store={}
blocked_cache={}

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=5)
    return pool

async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY,username VARCHAR(32) UNIQUE NOT NULL,password_hash VARCHAR(128) NOT NULL,avatar TEXT,banner TEXT,avatar_pos TEXT DEFAULT '50% 50%',banner_pos TEXT DEFAULT '50% 50%',email VARCHAR(128),is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,is_beta_tester BOOLEAN DEFAULT FALSE,is_scam BOOLEAN DEFAULT FALSE,is_dev BOOLEAN DEFAULT FALSE,premium_tier VARCHAR(8),is_banned BOOLEAN DEFAULT FALSE,ban_reason VARCHAR(256),mute_until TIMESTAMP,nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),custom_status VARCHAR(128),online_status VARCHAR(16) DEFAULT 'online',bio VARCHAR(256),fav_music VARCHAR(128),gifts_hidden BOOLEAN DEFAULT FALSE,easter_found TEXT DEFAULT '[]',easter_rewarded BOOLEAN DEFAULT FALSE,admin_password VARCHAR(128),coins INTEGER DEFAULT 0,messages_count INTEGER DEFAULT 0,frozen BOOLEAN DEFAULT FALSE,is_legend BOOLEAN DEFAULT FALSE,wallpaper TEXT,font_choice VARCHAR(32),compact_mode BOOLEAN DEFAULT FALSE,achievements TEXT DEFAULT '[]',last_seen TIMESTAMP DEFAULT NOW(),created_at TIMESTAMP DEFAULT NOW())""")
        for c,t in [("is_admin","BOOLEAN DEFAULT FALSE"),("is_moderator","BOOLEAN DEFAULT FALSE"),("is_beta_tester","BOOLEAN DEFAULT FALSE"),("is_scam","BOOLEAN DEFAULT FALSE"),("is_dev","BOOLEAN DEFAULT FALSE"),("premium_tier","VARCHAR(8)"),("is_banned","BOOLEAN DEFAULT FALSE"),("ban_reason","VARCHAR(256)"),("email","VARCHAR(128)"),("mute_until","TIMESTAMP"),("nickname_color","VARCHAR(32)"),("nickname_gradient","VARCHAR(128)"),("custom_status","VARCHAR(128)"),("online_status","VARCHAR(16) DEFAULT 'online'"),("bio","VARCHAR(256)"),("fav_music","VARCHAR(128)"),("gifts_hidden","BOOLEAN DEFAULT FALSE"),("easter_found","TEXT DEFAULT '[]'"),("easter_rewarded","BOOLEAN DEFAULT FALSE"),("admin_password","VARCHAR(128)"),("coins","INTEGER DEFAULT 0"),("messages_count","INTEGER DEFAULT 0"),("frozen","BOOLEAN DEFAULT FALSE"),("is_legend","BOOLEAN DEFAULT FALSE"),("wallpaper","TEXT"),("font_choice","VARCHAR(32)"),("compact_mode","BOOLEAN DEFAULT FALSE"),("achievements","TEXT DEFAULT '[]'"),("last_seen","TIMESTAMP DEFAULT NOW()")]:
            try: await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {c} {t}")
            except: pass
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,banner TEXT,description TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,reply_to INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        for c,t in [("reply_to","INTEGER"),("reactions","TEXT DEFAULT '{}'"),("pinned","BOOLEAN DEFAULT FALSE"),("edited","BOOLEAN DEFAULT FALSE")]:
            try: await conn.execute(f"ALTER TABLE messages ADD COLUMN IF NOT EXISTS {c} {t}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_appeals(id SERIAL PRIMARY KEY,username VARCHAR(32),text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS reports(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,coins INTEGER NOT NULL,price INTEGER DEFAULT 0,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        try: await conn.execute("ALTER TABLE custom_gifts ADD COLUMN IF NOT EXISTS is_sticker BOOLEAN DEFAULT FALSE")
        except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_market(id SERIAL PRIMARY KEY,item_id INTEGER REFERENCES nft_items(id) ON DELETE CASCADE,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,price INTEGER NOT NULL,status VARCHAR(16) DEFAULT 'active',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),item_image TEXT,chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_opens(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,prize_text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS abuse_grants(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,can_gift BOOLEAN DEFAULT TRUE,can_nft BOOLEAN DEFAULT TRUE,can_coins BOOLEAN DEFAULT TRUE,can_online BOOLEAN DEFAULT TRUE,can_timer BOOLEAN DEFAULT TRUE,expires_at TIMESTAMP NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_tournament(id SERIAL PRIMARY KEY,game VARCHAR(32),started_at TIMESTAMP DEFAULT NOW(),active BOOLEAN DEFAULT FALSE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_requests(id SERIAL PRIMARY KEY,from_admin INTEGER REFERENCES users(id) ON DELETE SET NULL,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,reason TEXT,evidence TEXT,status VARCHAR(16) DEFAULT 'pending',resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS suspicious_logs(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,action VARCHAR(64),details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS auto_abuse(id SERIAL PRIMARY KEY,enabled BOOLEAN DEFAULT FALSE,kind VARCHAR(16),every_minutes INTEGER DEFAULT 60,next_run TIMESTAMP,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS owner_messages(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS notifications(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,kind VARCHAR(32),text TEXT,is_read BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try: await init_db()
        except Exception as e: print(f"DB init: {e}")

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
    if row.get("is_beta_tester"): return "beta"
    return "user"

def user_public(row,viewer_id=None):
    status=row.get("online_status") or "online"
    uid=row["id"]
    is_online=uid in online_users and status!="invisible"
    if status=="invisible" and viewer_id!=uid and viewer_id!=row.get("id"):
        is_online=False
    return {"id":row["id"],"username":row["username"],"avatar":row["avatar"],"banner":row["banner"],"avatar_pos":row["avatar_pos"],"banner_pos":row["banner_pos"],"is_admin":row["is_admin"],"is_moderator":row["is_moderator"],"is_beta_tester":row.get("is_beta_tester",False),"is_scam":row.get("is_scam",False),"is_dev":row.get("is_dev",False),"premium_tier":row.get("premium_tier"),"nickname_color":row.get("nickname_color"),"nickname_gradient":row.get("nickname_gradient"),"custom_status":row.get("custom_status"),"online_status":status,"bio":row.get("bio"),"fav_music":row.get("fav_music"),"coins":row.get("coins",0),"messages_count":row.get("messages_count",0),"is_legend":row.get("is_legend",False),"has_admin_pass":bool(row.get("admin_password")),"wallpaper":row.get("wallpaper"),"font_choice":row.get("font_choice"),"compact_mode":row.get("compact_mode",False),"achievements":json.loads(row.get("achievements") or "[]"),"created_at":row["created_at"].isoformat() if row.get("created_at") else None,"role":get_role(row),"online":is_online}

async def get_all_gifts():
    gifts=dict(DEFAULT_GIFTS)
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM custom_gifts WHERE is_sticker=FALSE OR is_sticker IS NULL")
            for r in rows:
                gifts[r["gift_id"]]={"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"]}
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
    if user["username"]==ADMIN_USERNAME:
        return {"owner":True,"can_gift":True,"can_nft":True,"can_coins":True,"can_online":True,"can_timer":True}
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

async def check_friend_spam(uid):
    now=time.time()
    arr=friend_spam_tracker.get(uid,[])
    arr=[t for t in arr if now-t<600]
    arr.append(now)
    friend_spam_tracker[uid]=arr
    if len(arr)>=10:
        friend_spam_tracker[uid]=[]
        await log_suspicious(uid,"friend_spam","10+ заявок за 10 мин")
        return True
    return False

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

@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),avatar_pos=COALESCE($3,avatar_pos),banner_pos=COALESCE($4,banner_pos),nickname_color=$5,nickname_gradient=$6,bio=COALESCE($7,bio),fav_music=COALESCE($8,fav_music),wallpaper=COALESCE($9,wallpaper),font_choice=COALESCE($10,font_choice),compact_mode=COALESCE($11,compact_mode) WHERE id=$12""",data.get("avatar"),data.get("banner"),data.get("avatar_pos"),data.get("banner_pos"),data.get("nickname_color"),data.get("nickname_gradient"),data.get("bio"),data.get("fav_music"),data.get("wallpaper"),data.get("font_choice"),data.get("compact_mode"),user["id"])
    return {"ok":True}

@app.post("/api/user/status")
async def set_status(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    st=data.get("online_status","online")
    if st not in ("online","dnd","invisible"): raise HTTPException(400,"online/dnd/invisible")
    custom=(data.get("custom_status") or "")[:128]
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
        row=await conn.fetchrow("""SELECT id,username,avatar,banner,avatar_pos,banner_pos,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,premium_tier,nickname_color,nickname_gradient,bio,fav_music,custom_status,online_status,messages_count,is_legend,achievements,created_at,last_seen FROM users WHERE id=$1""",user_id)
    if not row: raise HTTPException(404,"Не найден")
    d=dict(row)
    d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
    d["last_seen"]=d["last_seen"].isoformat() if d.get("last_seen") else None
    d["role"]=get_role(row)
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
        rows=await conn.fetch("SELECT id,username,avatar,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,online_status FROM users WHERE username ILIKE $1 AND id!=$2 ORDER BY username LIMIT 20",f"%{q}%",user["id"])
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); d["online"]=r["id"] in online_users and (r.get("online_status") or "online")!="invisible"; out.append(d)
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

@app.get("/api/friends/list")
async def friends_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    uid=user["id"]
    p=await get_pool()
    async with p.acquire() as conn:
        frows=await conn.fetch("SELECT id,user_a,user_b FROM friendships WHERE user_a=$1 OR user_b=$1",uid)
        inc=await conn.fetch("SELECT r.id,r.from_user,u.username,u.avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev FROM friend_requests r JOIN users u ON u.id=r.from_user WHERE r.to_user=$1 ORDER BY r.created_at DESC",uid)
        out=await conn.fetch("SELECT r.id,r.to_user,u.username,u.avatar FROM friend_requests r JOIN users u ON u.id=r.to_user WHERE r.from_user=$1 ORDER BY r.created_at DESC",uid)
        result=[]
        for r in frows:
            oid=r["user_b"] if r["user_a"]==uid else r["user_a"]
            o=await conn.fetchrow("SELECT id,username,avatar,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,last_seen,online_status,custom_status FROM users WHERE id=$1",oid)
            if not o: continue
            result.append({"id":o["id"],"username":o["username"],"avatar":o["avatar"],"status":"accepted","friend_row_id":r["id"],"online":o["id"] in online_users and (o.get("online_status") or "online")!="invisible","last_seen":o["last_seen"].isoformat() if o.get("last_seen") else None,"is_admin":o["is_admin"],"is_moderator":o["is_moderator"],"is_beta_tester":o["is_beta_tester"],"is_scam":o["is_scam"],"custom_status":o.get("custom_status"),"online_status":o.get("online_status") or "online","role":get_role(o)})
        for r in inc:
            result.append({"id":r["from_user"],"username":r["username"],"avatar":r["avatar"],"status":"incoming","request_id":r["id"],"online":r["from_user"] in online_users,"is_admin":r["is_admin"],"is_moderator":r["is_moderator"],"is_beta_tester":r["is_beta_tester"],"is_scam":r["is_scam"],"role":get_role(r)})
        for r in out:
            result.append({"id":r["to_user"],"username":r["username"],"avatar":r["avatar"],"status":"outgoing","request_id":r["id"],"online":r["to_user"] in online_users,"is_admin":False,"is_moderator":False,"is_beta_tester":False,"is_scam":False,"role":"user"})
    return result

@app.post("/api/friends/request")
async def friends_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    await check_friend_spam(user["id"])
    tn=(data.get("username") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",tn)
        if not t: raise HTTPException(404,"Не найден")
        if t["id"]==user["id"]: raise HTTPException(400,"Себя нельзя")
        if await is_blocked(user["id"],t["id"]): raise HTTPException(403,"Заблокирован")
        ex=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],t["id"])
        if ex: raise HTTPException(400,"Уже друзья")
        ex2=await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],t["id"])
        if ex2: raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],t["id"])
    await manager.send_to(t["id"],{"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok":True}

@app.post("/api/friends/request_by_id")
async def friends_request_by_id(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    await check_friend_spam(user["id"])
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        ex=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
        if ex: raise HTTPException(400,"Уже друзья")
        ex2=await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid)
        if ex2: raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok":True}

@app.post("/api/friends/accept")
async def friends_accept(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    if not rid: raise HTTPException(400,"request_id обязателен")
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
        fr=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],user_id)
        if fr: return {"status":"accepted"}
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

@app.get("/api/groups/list")
async def groups_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.id,g.name,g.avatar,g.description,g.owner_id FROM groups g JOIN group_members gm ON gm.group_id=g.id WHERE gm.user_id=$1 ORDER BY g.id DESC",user["id"])
    return [dict(r) for r in rows]

@app.post("/api/groups/create")
async def groups_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    members=data.get("members") or []
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("INSERT INTO groups(name,avatar,description,owner_id) VALUES($1,$2,$3,$4) RETURNING *",name,data.get("avatar"),data.get("description","")[:256],user["id"])
        await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)",g["id"],user["id"])
        for m in members:
            try:
                mid=int(m) if not isinstance(m,str) else int(m)
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
    return d

@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        rows=await conn.fetch("SELECT gm.id,gm.text,gm.file_url,gm.created_at,gm.user_id,u.username,u.avatar,u.avatar_pos,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200",group_id)
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None; d["role"]=get_role(r); out.append(d)
    return out

@app.get("/api/groups/{group_id}/members")
async def group_members_get(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.id,u.username,u.avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev FROM users u JOIN group_members gm ON gm.user_id=u.id WHERE gm.group_id=$1",group_id)
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); out.append(d)
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
    gid=int(data.get("group_id",0))
    tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет")
        if g["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        if tid==user["id"]: raise HTTPException(400,"Себя кикни через выход")
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
        if g["owner_id"]==user["id"]:
            await conn.execute("DELETE FROM groups WHERE id=$1",gid)
        else:
            await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
    return {"ok":True}

@app.post("/api/groups/update")
async def group_update(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g or g["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("UPDATE groups SET name=COALESCE($1,name),description=COALESCE($2,description),avatar=COALESCE($3,avatar) WHERE id=$4",data.get("name"),data.get("description"),data.get("avatar"),gid)
        row=await conn.fetchrow("SELECT * FROM groups WHERE id=$1",gid)
    return dict(row)

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
        cnt=await conn.fetchval("SELECT COUNT(*) FROM servers WHERE owner_id=$1",user["id"])
        if cnt and cnt>=5: await log_suspicious(user["id"],"many_servers",f"{cnt} серверов")
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
        rows=await conn.fetch("SELECT id,name,type FROM channels WHERE server_id=$1 ORDER BY id",server_id)
    return [dict(r) for r in rows]

@app.get("/api/servers/{server_id}/members")
async def server_members(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.id,u.username,u.avatar,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev FROM users u JOIN server_members sm ON sm.user_id=u.id WHERE sm.server_id=$1",server_id)
    out=[]
    for r in rows:
        d=dict(r); d["role"]=get_role(r); out.append(d)
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
        rows=await conn.fetch("SELECT m.id,m.text,m.file_url,m.reactions,m.edited,m.reply_to,m.pinned,m.created_at,m.user_id,u.username,u.avatar,u.avatar_pos,u.is_admin,u.is_moderator,u.is_beta_tester,u.is_scam,u.is_dev FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200",channel_id)
        pinned=await conn.fetch("SELECT m.id,m.text,m.user_id,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.pinned=TRUE ORDER BY m.id DESC LIMIT 5",channel_id)
    out=[]
    for r in rows:
        d=dict(r)
        d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["role"]=get_role(r)
        d["reactions"]=json.loads(d.get("reactions") or "{}")
        out.append(d)
    return {"messages":out,"pinned":[dict(p) for p in pinned]}

@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.created_at,u.username,u.avatar,u.avatar_pos FROM dms d JOIN users u ON u.id=d.from_user WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC LIMIT 200",user["id"],user_id)
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None; out.append(d)
    return out

@app.post("/api/messages/edit")
async def message_edit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE messages SET text=$1,edited=TRUE WHERE id=$2 AND user_id=$3",data.get("text",""),int(data.get("message_id",0)),user["id"])
    await manager.broadcast({"type":"message_edited","id":int(data.get("message_id",0)),"text":data.get("text","")})
    return {"ok":True}

@app.post("/api/messages/delete")
async def message_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if user.get("is_admin") or user["username"]==ADMIN_USERNAME:
            await conn.execute("DELETE FROM messages WHERE id=$1",int(data.get("message_id",0)))
        else:
            await conn.execute("DELETE FROM messages WHERE id=$1 AND user_id=$2",int(data.get("message_id",0)),user["id"])
    await manager.broadcast({"type":"message_deleted","id":int(data.get("message_id",0))})
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
        row=await conn.fetchrow("SELECT reactions FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        react=json.loads(row["reactions"] or "{}")
        arr=react.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        react[emoji]=arr
        await conn.execute("UPDATE messages SET reactions=$1 WHERE id=$2",json.dumps(react),mid)
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":react})
    return {"ok":True}

@app.post("/api/messages/search")
async def message_search(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    q=(data.get("q") or "").strip()
    ch=int(data.get("channel_id",0))
    if len(q)<2 or not ch: return []
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT m.id,m.text,m.created_at,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.text ILIKE $2 ORDER BY m.id DESC LIMIT 50",ch,f"%{q}%")
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"created_at":r["created_at"].isoformat()} for r in rows]

@app.post("/api/drafts/save")
async def draft_save(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    key=data.get("key")
    text=(data.get("text") or "")[:4000]
    if not key: return {"ok":True}
    draft_store[f"{user['id']}:{key}"]=text
    return {"ok":True}

@app.get("/api/drafts/get")
async def draft_get(key:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"text":draft_store.get(f"{user['id']}:{key}","")}
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
        rows=await conn.fetch("SELECT id,username,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,premium_tier,is_banned,coins FROM users ORDER BY id")
    return [dict(r) for r in rows]

@app.post("/api/admin/action")
async def admin_action(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    tid=data.get("target_id"); action=data.get("action")
    is_owner=user["username"]==ADMIN_USERNAME
    if action=="ban" and not is_owner: raise HTTPException(403,"Отправь заявку")
    owner_only=["grant_premium","grant_pro","scam","unscam"]
    if action in owner_only and not is_owner: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        if action=="ban": await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",data.get("reason",""),tid)
        elif action=="unban": await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",tid)
        elif action=="mute":
            d=int(data.get("duration",3600))
            await conn.execute(f"UPDATE users SET mute_until=NOW()+INTERVAL '{d} seconds' WHERE id=$1",tid)
        elif action=="grant_premium": await conn.execute("UPDATE users SET premium_tier='premium' WHERE id=$1",tid)
        elif action=="grant_pro": await conn.execute("UPDATE users SET premium_tier='pro' WHERE id=$1",tid)
        elif action=="scam": await conn.execute("UPDATE users SET is_scam=TRUE WHERE id=$1",tid)
    await log_admin(user["id"],action,tid)
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
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat(); out.append(d)
    return out

@app.get("/api/admin/logs")
async def admin_logs(token:str):
    user=await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT l.id,l.action,l.details,l.created_at,a.username AS admin_name FROM admin_logs l LEFT JOIN users a ON a.id=l.admin_id ORDER BY l.id DESC LIMIT 100")
    out=[]
    for r in rows:
        d=dict(r); d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None; out.append(d)
    return out

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
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        target=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not target: raise HTTPException(404,"Не найден")
        ex=await conn.fetchrow("SELECT id FROM ban_requests WHERE target_user=$1 AND status='pending'",tid)
        if ex: raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO ban_requests(from_admin,target_user,reason,evidence) VALUES($1,$2,$3,$4)",user["id"],tid,reason,evidence)
    try:
        p2=await get_pool()
        async with p2.acquire() as conn2:
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
        rows=await conn.fetch("SELECT br.id,br.reason,br.evidence,br.created_at,fa.username AS from_username,tu.username AS target_username,br.target_user,br.from_admin FROM ban_requests br LEFT JOIN users fa ON fa.id=br.from_admin LEFT JOIN users tu ON tu.id=br.target_user WHERE br.status='pending' ORDER BY br.id DESC")
    return [{"id":r["id"],"reason":r["reason"],"evidence":r["evidence"],"from_username":r["from_username"],"target_username":r["target_username"],"target_user":r["target_user"],"from_admin":r["from_admin"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

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
        await conn.execute(f"UPDATE users SET mute_until=NOW()+INTERVAL '{m*60} seconds' WHERE id=$1",int(data.get("user_id",0)))
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
        await conn.execute(f"UPDATE users SET mute_until=NOW()+INTERVAL '{m*60} seconds' WHERE id=$1",t["id"])
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
        cnt=await conn.fetchval("SELECT COUNT(*) FROM reports WHERE target_user=$1 AND status='pending'",tid)
        if cnt and cnt>=5: await log_suspicious(tid,"many_reports",f"{cnt} жалоб")
    return {"ok":True}

@app.post("/api/appeal/submit")
async def appeal_submit(data:dict):
    u=(data.get("username") or "").strip(); t=(data.get("text") or "").strip()
    if not u or not t: raise HTTPException(400,"Заполни")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO ban_appeals(username,text) VALUES($1,$2)",u,t)
    return {"ok":True}

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
    tid=int(data.get("user_id",0))
    kind=data.get("kind")
    dur=int(data.get("duration",10))
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
    prefix=(data.get("prefix") or "")[:16]
    suffix=(data.get("suffix") or "")[:16]
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username FROM users WHERE username!=$1",ADMIN_USERNAME)
        for r in rows:
            new=(prefix+r["username"]+suffix)[:32]
            try: await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,r["id"])
            except: pass
    await manager.broadcast({"type":"mass_renamed"})
    return {"ok":True,"count":len(rows)}

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
    enabled=bool(data.get("enabled",False))
    kind=data.get("kind","gift")
    every=int(data.get("every_minutes",60))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM auto_abuse")
        if enabled:
            await conn.execute("INSERT INTO auto_abuse(enabled,kind,every_minutes,next_run,created_by) VALUES(TRUE,$1,$2,NOW()+INTERVAL '1 minute' * $3,$4)",kind,every,every,user["id"])
    if enabled:
        asyncio.create_task(run_auto_abuse_loop())
    return {"ok":True,"enabled":enabled}

async def run_auto_abuse_loop():
    while True:
        try:
            await asyncio.sleep(60)
            p=await get_pool()
            async with p.acquire() as conn:
                row=await conn.fetchrow("SELECT * FROM auto_abuse WHERE enabled=TRUE LIMIT 1")
                if not row: return
                if row["next_run"] and row["next_run"]<=datetime.datetime.now(datetime.timezone.utc):
                    await conn.execute("UPDATE auto_abuse SET next_run=NOW()+INTERVAL '1 minute' * $1",row["every_minutes"])
                    kind=row["kind"]
            if online_users:
                await _random_abuse_by_kind(kind)
        except asyncio.CancelledError: return
        except Exception as e: print(f"AutoAbuse: {e}")

async def _random_abuse_by_kind(kind):
    if not online_users: return
    tid=random.choice(list(online_users))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT username,avatar FROM users WHERE id=$1",tid)
        if not t: return
        if kind=="coins":
            amt=random.randint(100,10000)
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,tid)
            payload={"type":"abuse_win","kind":"coins","username":t["username"],"avatar":t.get("avatar"),"item_name":f"{amt} 🏅","item_emoji":"🏅","price":amt}
        elif kind=="nft":
            sr=await conn.fetch("SELECT * FROM nft_series WHERE sold<total")
            if not sr: return
            s=random.choice(sr); num=(s["sold"] or 0)+1
            await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",s["id"],num,tid)
            await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",s["id"])
            payload={"type":"abuse_win","kind":"nft","username":t["username"],"avatar":t.get("avatar"),"item_name":f"{s['name']} #{num}","item_emoji":s.get("emoji"),"item_image":s.get("image"),"price":s["price"]}
        else:
            g=await get_all_gifts()
            if not g: return
            gid=random.choice(list(g.keys())); gift=g[gid]
            await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",0,tid,gid)
            payload={"type":"abuse_win","kind":"gift","username":t["username"],"avatar":t.get("avatar"),"item_name":gift["name"],"item_emoji":gift.get("emoji"),"item_image":gift.get("image"),"price":gift["price"]}
    await manager.broadcast(payload)

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
        new=t["coins"]+amt
        if new>=10000: await grant_achievement(t["id"],"coins_10k")
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

@app.post("/api/owner/announce")
async def owner_announce(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    await manager.broadcast({"type":"abuse","from_name":user["username"],"from_avatar":user.get("avatar"),"text":data.get("text","")})
    return {"ok":True}

@app.post("/api/owner/mass_dm")
async def owner_mass_dm(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    for uid in list(online_users):
        await manager.send_to(uid,{"type":"abuse","from_name":user["username"],"from_avatar":user.get("avatar"),"text":data.get("text","")})
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
        await conn.execute(f"UPDATE users SET mute_until=NOW()+INTERVAL '{m*60} seconds' WHERE id=$1",t["id"])
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
        await conn.execute("UPDATE users SET premium_tier=$1 WHERE username=$2",data.get("tier","premium"),data.get("username"))
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
async def owner_read_chat(token:str,username:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",username)
        if not t: raise HTTPException(404,"Не найден")
        rows=await conn.fetch("SELECT m.text,u.username AS from_user,m.created_at FROM messages m JOIN users u ON u.id=m.user_id WHERE m.user_id=$1 ORDER BY m.id DESC LIMIT 50",t["id"])
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

@app.get("/api/owner/chat")
async def owner_chat_get(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT om.id,om.text,om.created_at,u.username,u.avatar FROM owner_messages om LEFT JOIN users u ON u.id=om.from_user ORDER BY om.id ASC LIMIT 200")
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"avatar":r["avatar"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/owner/chat/send")
async def owner_chat_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    txt=(data.get("text") or "").strip()
    if not txt: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        msg=await conn.fetchrow("INSERT INTO owner_messages(from_user,text) VALUES($1,$2) RETURNING *",user["id"],txt)
    await manager.broadcast({"type":"owner_chat","id":msg["id"],"username":user["username"],"avatar":user.get("avatar"),"text":txt,"created_at":msg["created_at"].isoformat()})
    return {"ok":True}

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
    payload={"type":"abuse_win","kind":"gift","username":t["username"],"avatar":t.get("avatar"),"item_name":gift["name"],"item_emoji":gift.get("emoji"),"item_image":gift.get("image"),"price":gift["price"]}
    await manager.broadcast(payload)
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
        t=await conn.fetchrow("SELECT username,avatar FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        s=random.choice(sr); num=(s["sold"] or 0)+1
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",s["id"],num,tid)
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",s["id"])
    payload={"type":"abuse_win","kind":"nft","username":t["username"],"avatar":t.get("avatar"),"item_name":f"{s['name']} #{num}","item_emoji":s.get("emoji"),"item_image":s.get("image"),"price":s["price"]}
    await manager.broadcast(payload)
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
        t=await conn.fetchrow("SELECT username,avatar FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,tid)
    payload={"type":"abuse_win","kind":"coins","username":t["username"],"avatar":t.get("avatar"),"item_name":f"{amt} 🏅","item_emoji":"🏅","price":amt}
    await manager.broadcast(payload)
    return {"ok":True,"target":t["username"],"amount":amt}

@app.get("/api/abuse/access")
async def abuse_access(token:str):
    user=await get_current_user(token)
    acc=await has_abuse_access(user)
    if not acc: return {"access":False}
    return {"access":True,"owner":acc.get("owner",False),"can_gift":acc.get("can_gift",False),"can_nft":acc.get("can_nft",False),"can_coins":acc.get("can_coins",False),"can_online":acc.get("can_online",False),"can_timer":acc.get("can_timer",False)}

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

async def run_abuse_timer(delay,kind):
    try:
        await asyncio.sleep(delay)
        await manager.broadcast({"type":"abuse_owner_announce"})
        await asyncio.sleep(5)
        await manager.broadcast({"type":"abuse_timer_cancel"})
        await _random_abuse_by_kind(kind)
    except asyncio.CancelledError: pass
    except Exception as e: print(f"Timer: {e}")

@app.post("/api/abuse/coop_start")
async def abuse_coop_start(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    target_name=(data.get("username") or "").strip()
    minutes=int(data.get("minutes",60))
    cg=bool(data.get("can_gift",True)); cn=bool(data.get("can_nft",True)); cc=bool(data.get("can_coins",True)); co=bool(data.get("can_online",True)); ct=bool(data.get("can_timer",True))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",target_name)
        if not t: raise HTTPException(404,"Не найден")
        await conn.execute("""INSERT INTO abuse_grants(user_id,granted_by,can_gift,can_nft,can_coins,can_online,can_timer,expires_at) VALUES($1,$2,$3,$4,$5,$6,$7,NOW()+INTERVAL '1 minute' * $8) ON CONFLICT (user_id) DO UPDATE SET can_gift=$3,can_nft=$4,can_coins=$5,can_online=$6,can_timer=$7,expires_at=NOW()+INTERVAL '1 minute' * $8""",t["id"],user["id"],cg,cn,cc,co,ct,minutes)
    await manager.send_to(t["id"],{"type":"coop_started","minutes":minutes,"username":user["username"]})
    return {"ok":True,"target":t["username"],"minutes":minutes}

@app.get("/api/abuse/coop_grants")
async def abuse_coop_grants(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.user_id,g.can_gift,g.can_nft,g.can_coins,g.can_online,g.can_timer,g.expires_at,u.username FROM abuse_grants g JOIN users u ON u.id=g.user_id WHERE g.expires_at>NOW() ORDER BY g.expires_at DESC")
    return [{"user_id":r["user_id"],"username":r["username"],"can_gift":r["can_gift"],"can_nft":r["can_nft"],"can_coins":r["can_coins"],"can_online":r["can_online"],"can_timer":r["can_timer"],"expires_at":r["expires_at"].isoformat()} for r in rows]
    
    @app.post("/api/abuse/broadcast")
async def abuse_broadcast(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc: raise HTTPException(403,"Нет доступа")
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    if len(text)>500: text=text[:500]
    await manager.broadcast({"type":"abuse","from_name":user["username"],"from_avatar":user.get("avatar"),"text":text})
    return {"ok":True}

@app.post("/api/abuse/start")
async def abuse_start(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc: raise HTTPException(403,"Нет доступа")
    await manager.broadcast({"type":"abuse","from_name":user["username"],"from_avatar":user.get("avatar"),"text":"🚀 НАЧИНАЕМ! 🚀"})
    return {"ok":True}
    
@app.post("/api/abuse/coop_revoke")
async def abuse_coop_revoke(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM abuse_grants WHERE user_id=$1",int(data.get("user_id",0)))
    return {"ok":True}

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
    return {"ok":True}

@app.get("/api/games/leaders")
async def games_leaders(game:str):
    if game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    p=await get_pool()
    async with p.acquire() as conn:
        if active_tournament.get("game")==game and active_tournament.get("started_at"):
            rows=await conn.fetch("SELECT u.username,MAX(gs.score) AS best FROM game_scores gs JOIN users u ON u.id=gs.user_id WHERE gs.game=$1 AND gs.created_at >= $2 GROUP BY u.id,u.username ORDER BY best DESC LIMIT 20",game,active_tournament["started_at"])
        else:
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
        active_tournament["game"]=None
        active_tournament["started_at"]=None
    else:
        active_tournament["game"]=game
        active_tournament["started_at"]=datetime.datetime.now(datetime.timezone.utc)
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

@app.get("/api/coins/balance")
async def coins_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"coins":user.get("coins",0)}

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
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1",user["id"])
    if cnt==1: await grant_achievement(user["id"],"first_gift")
    await manager.send_to(to_id,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"gift_image":gift.get("image"),"from_name":user["username"]})
    return {"ok":True}

@app.get("/api/gifts/list/{user_id}")
async def gifts_list(user_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT gift FROM gifts WHERE to_user=$1 ORDER BY id DESC",user_id)
    return {"gifts":[dict(r) for r in rows]}

@app.post("/api/gifts/sell")
async def gift_sell(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет")
    price=g[gift_id]["price"]//2
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",user["id"],gift_id)
        if not row: raise HTTPException(400,"Нет")
        await conn.execute("DELETE FROM gifts WHERE id=$1",row["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",price,user["id"])
    return {"ok":True,"got":price}

@app.post("/api/gifts/transfer")
async def gift_transfer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift"); to_id=int(data.get("to_user",0))
    p=await get_pool()
    async with p.acquire() as conn:
        fr=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],to_id)
        if not fr: raise HTTPException(400,"Только друзьям")
        row=await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",user["id"],gift_id)
        if not row: raise HTTPException(400,"Нет")
        await conn.execute("UPDATE gifts SET to_user=$1,from_user=$2 WHERE id=$3",to_id,user["id"],row["id"])
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",to_id)
    return {"ok":True,"to":t["username"]}

@app.get("/api/gifts/all")
async def gifts_all():
    g=await get_all_gifts()
    return [{"gift_id":k,"name":v["name"],"emoji":v.get("emoji"),"image":v.get("image"),"price":v["price"]} for k,v in g.items()]

@app.get("/api/stickers/list")
async def stickers_list():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT gift_id,name,emoji,image FROM custom_gifts WHERE is_sticker=TRUE ORDER BY created_at DESC")
        return [{"id":r["gift_id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"]} for r in rows]
    except: return []

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

@app.get("/api/nft/{nft_id}")
async def nft_get(nft_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",nft_id)
    if not r: raise HTTPException(404,"Не найден")
    return {"id":r["id"],"name":r["name"],"emoji":r["emoji"],"image":r.get("image"),"price":r["price"],"total":r["total"],"sold":r["sold"],"rarity":r["rarity"]}

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

@app.post("/api/nft/transfer")
async def nft_transfer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    item_id=int(data.get("item_id",0)); to_id=int(data.get("to_user",0))
    p=await get_pool()
    async with p.acquire() as conn:
        fr=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],to_id)
        if not fr: raise HTTPException(400,"Только друзьям")
        item=await conn.fetchrow("SELECT id,owner_id FROM nft_items WHERE id=$1",item_id)
        if not item: raise HTTPException(404,"Не найден")
        if item["owner_id"]!=user["id"]: raise HTTPException(403,"Не твой")
        await conn.execute("UPDATE nft_items SET owner_id=$1 WHERE id=$2",to_id,item_id)
    return {"ok":True}

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
        ex=await conn.fetchrow("SELECT id FROM nft_market WHERE item_id=$1 AND status='active'",item_id)
        if ex: raise HTTPException(400,"Уже на рынке")
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

@app.post("/api/nft_market/cancel")
async def nft_market_cancel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("market_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT seller_id FROM nft_market WHERE id=$1 AND status='active'",mid)
        if not m or m["seller_id"]!=user["id"]: raise HTTPException(403,"Не твой")
        await conn.execute("UPDATE nft_market SET status='cancelled' WHERE id=$1",mid)
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
        if total<=0: raise HTTPException(400,"Пусто")
        roll=random.randint(1,total)
        acc=0; chosen=None
        for p in prizes:
            acc+=p["chance"]
            if roll<=acc: chosen=p; break
        if not chosen: chosen=prizes[-1]
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",c["price"],user["id"])
        if chosen["kind"]=="coins":
            amt=random.randint(chosen["coins_min"] or 1,chosen["coins_max"] or chosen["coins_min"] or 1)
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,user["id"])
            prize_text=f"🏅 {amt} бекоинов"
        elif chosen["kind"]=="gift":
            gid=chosen["item_id"]
            if gid:
                await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],gid)
            prize_text=f"🎁 {chosen['item_name'] or gid}"
        elif chosen["kind"]=="nft":
            try:
                nid=int(chosen["item_id"])
                s=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",nid)
                if s and s["sold"]<s["total"]:
                    num=s["sold"]+1
                    await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",nid,num,user["id"])
                    await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",nid)
                    prize_text=f"🎨 {s['name']} #{num}"
                else: prize_text="😢 пусто (NFT кончились)"
            except: prize_text="😢 пусто"
        else:
            prize_text=f"❓ {chosen['item_name'] or '???'}"
        await conn.execute("INSERT INTO case_opens(user_id,case_id,prize_text) VALUES($1,$2,$3)",user["id"],cid,prize_text)
    return {"ok":True,"prize":prize_text}

@app.get("/api/owner/cases/list")
async def owner_cases_list(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM cases ORDER BY id DESC")
        result=[]
        for r in rows:
            prizes=await conn.fetch("SELECT * FROM case_prizes WHERE case_id=$1",r["id"])
            d=dict(r); d["prizes"]=[dict(p) for p in prizes]
            result.append(d)
    return result

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

@app.post("/api/owner/create_nft")
async def owner_create_nft(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("INSERT INTO nft_series(name,emoji,image,total,price,rarity,created_by) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING *",data.get("name"),data.get("emoji","🎨"),data.get("image"),int(data.get("total",1)),int(data.get("price",0)),data.get("rarity","common"),user["id"])
    return {"ok":True,"id":row["id"]}

@app.post("/api/owner/give_nft")
async def owner_give_nft(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        s=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",int(data.get("nft_id",0)))
        if not s: raise HTTPException(404,"NFT не найден")
        num=(s["sold"] or 0)+1
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",s["id"],num,t["id"])
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",s["id"])
    return {"ok":True}

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

@app.get("/api/themes/list")
async def themes_list():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT id,name,emoji,vars,bg_image,border_radius,blur,created_at FROM custom_themes ORDER BY id DESC")
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
        try:
            r=await conn.fetchrow("INSERT INTO custom_themes(name,emoji,vars,bg_image,border_radius,blur,created_by) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,data.get("emoji","🎨"),json.dumps(data.get("vars") or {}),data.get("bg_image"),data.get("border_radius","12px"),data.get("blur","blur(30px)"),user["id"])
        except Exception:
            await conn.execute("CREATE TABLE IF NOT EXISTS custom_themes(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),vars TEXT,bg_image TEXT,border_radius VARCHAR(16),blur VARCHAR(32),created_by INTEGER,created_at TIMESTAMP DEFAULT NOW())")
            r=await conn.fetchrow("INSERT INTO custom_themes(name,emoji,vars,bg_image,border_radius,blur,created_by) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,data.get("emoji","🎨"),json.dumps(data.get("vars") or {}),data.get("bg_image"),data.get("border_radius","12px"),data.get("blur","blur(30px)"),user["id"])
    await manager.broadcast({"type":"theme_added","id":r["id"],"name":name})
    return {"ok":True,"id":r["id"]}

@app.post("/api/owner/theme/delete")
async def owner_theme_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_themes WHERE id=$1",int(data.get("theme_id",0)))
    await manager.broadcast({"type":"theme_deleted","id":int(data.get("theme_id",0))})
    return {"ok":True}

@app.get("/api/themes/export/{theme_id}")
async def themes_export(theme_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM custom_themes WHERE id=$1",theme_id)
    if not r: raise HTTPException(404,"Нет")
    payload={"name":r["name"],"emoji":r["emoji"],"vars":json.loads(r["vars"] or "{}"),"bg_image":r["bg_image"],"border_radius":r["border_radius"],"blur":r["blur"]}
    code="BELUGA_THEME_"+secrets.token_urlsafe(0)[:0]+__import__("base64").b64encode(json.dumps(payload).encode()).decode()
    return {"code":code}

@app.post("/api/themes/import")
async def themes_import(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    code=(data.get("code") or "").strip()
    if not code.startswith("BELUGA_THEME_"): raise HTTPException(400,"Плохой код")
    try:
        import base64
        payload=json.loads(base64.b64decode(code[13:]).decode())
    except: raise HTTPException(400,"Не распарсилось")
    return {"ok":True,"theme":payload}

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
            except: pass
    async def broadcast(self,data,exclude=None):
        for uid,conns in list(self.connections.items()):
            if exclude and uid==exclude: continue
            for ws in list(conns):
                try: await ws.send_json(data)
                except: pass
manager=ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws:WebSocket,token:str):
    user=await get_current_user(token)
    if not user:
        await ws.close(); return
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
            if t=="message":
                ch=data.get("channel_id"); text=(data.get("text") or "")[:2000]
                furl=data.get("file_url"); tid=data.get("temp_id"); reply=data.get("reply_to")
                if not ch: continue
                await check_spam(uid)
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,reply_to) VALUES($1,$2,$3,$4,$5) RETURNING *",int(ch),uid,text,furl,reply)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    mc=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                if mc==1: await grant_achievement(uid,"first_msg")
                if mc==100: await grant_achievement(uid,"msg_100")
                if mc==1000: await grant_achievement(uid,"msg_1000")
                if mc==10000: await grant_achievement(uid,"msg_10000")
                mentions=[]
                if text:
                    import re
                    for m in re.findall(r"@([A-Za-z0-9_]{2,32})",text):
                        mentions.append(m)
                payload={"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"reply_to":reply,"created_at":msg["created_at"].isoformat(),"is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),"is_beta_tester":user.get("is_beta_tester"),"is_scam":user.get("is_scam"),"role":get_role(user),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)
                if mentions:
                    for mn in set(mentions):
                        if mn==user["username"]: continue
                        p2=await get_pool()
                        async with p2.acquire() as conn2:
                            tgt=await conn2.fetchrow("SELECT id FROM users WHERE username=$1",mn)
                        if tgt: await manager.send_to(tgt["id"],{"type":"mention","from":user["username"],"channel_id":int(ch),"text":text[:80]})
            elif t=="dm":
                to_id=int(data.get("to_user",0)); text=(data.get("text") or "")[:2000]
                furl=data.get("file_url"); tid=data.get("temp_id")
                if await is_blocked(uid,to_id): continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",uid,to_id,text,furl)
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"avatar":user.get("avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"temp_id":tid}
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
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"temp_id":tid}
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
            elif t=="speaking":
                to=int(data.get("to",0))
                if to: await manager.send_to(to,{"type":"speaking","from":uid,"value":bool(data.get("value"))})
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

@app.get("/manifest.json")
async def manifest():
    return {"name":"Belugacord Beta 1.9","short_name":"Belugacord","start_url":"/","display":"standalone","background_color":"#0a0a12","theme_color":"#0a0a12","icons":[{"src":"/uploads/icon.png","sizes":"192x192","type":"image/png"}]}

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