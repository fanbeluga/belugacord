import asyncio
import os
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg

# ==========================================
# CONFIG & SECURITY (STDLIB ONLY)
# ==========================================
SECRET_KEY = os.getenv("SECRET_KEY", "belugacord_secret_2026_change_me")
ADMIN_PIN_DEFAULT = "1234" # Пароль от Бог-админки

_raw_dsn = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/belugacord")
DB_DSN = _raw_dsn.replace("postgres://", "postgresql://", 1)

def get_password_hash(password: str) -> str:
    return hashlib.sha256((password + SECRET_KEY).encode("utf-8")).hexdigest()

def verify_password(plain: str, hashed: str) -> bool:
    return get_password_hash(plain) == hashed

def create_access_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + 30 * 24 * 3600}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def decode_token(token: str) -> Optional[int]:
    try:
        parts = token.split(".")
        if len(parts) != 2: return None
        payload_b64, provided_sig = parts
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided_sig, expected_sig): return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if payload.get("exp", 0) < time.time(): return None
        return int(payload["sub"])
    except Exception:
        return None

# ==========================================
# DB POOL
# ==========================================
pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        # Settings Table (stores Admin Pin)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (key VARCHAR(50) PRIMARY KEY, value TEXT);
        """)
        
        # Seed Default Admin Pin if missing
        pin_exists = await conn.fetchval("SELECT 1 FROM system_settings WHERE key='admin_pin'")
        if not pin_exists:
            await conn.execute("INSERT INTO system_settings (key, value) VALUES ('admin_pin', $1)", ADMIN_PIN_DEFAULT)
            print(f">>> Seeded Admin PIN: {ADMIN_PIN_DEFAULT}")

        # Other Tables...
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_titles (
                id SERIAL PRIMARY KEY, name VARCHAR(50) NOT NULL, color_hex VARCHAR(7) DEFAULT '#FFFFFF',
                bg_color_hex VARCHAR(7) DEFAULT 'transparent', is_global BOOLEAN DEFAULT FALSE,
                created_by INTEGER, created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255) NOT NULL, nickname VARCHAR(50) DEFAULT 'User', avatar_url TEXT DEFAULT '',
                coins INTEGER DEFAULT 0, candy_balance INTEGER DEFAULT 0, is_premium BOOLEAN DEFAULT FALSE,
                role VARCHAR(20) DEFAULT 'user', is_scammer BOOLEAN DEFAULT FALSE,
                active_custom_title_id INTEGER REFERENCES custom_titles(id), created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY, user1_id INTEGER REFERENCES users(id), user2_id INTEGER REFERENCES users(id),
                created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(user1_id, user2_id)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY, chat_id INTEGER REFERENCES chats(id), sender_id INTEGER REFERENCES users(id),
                content TEXT, read_status BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id SERIAL PRIMARY KEY, user1_id INTEGER REFERENCES users(id), user2_id INTEGER REFERENCES users(id),
                status VARCHAR(20) DEFAULT 'pending', created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(user1_id, user2_id)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bp_progress (
                id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id), season_name VARCHAR(100),
                level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, has_premium_pass BOOLEAN DEFAULT FALSE,
                UNIQUE(user_id, season_name)
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS teacher_quiz_progress (
                user_id INTEGER PRIMARY KEY REFERENCES users(id), current_question_index INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT FALSE, score INTEGER DEFAULT 0, updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Seed OWNER (_fan_beluga_) ONLY if table is empty
        cnt = await conn.fetchval("SELECT COUNT(*) FROM users")
        if cnt == 0:
            print(">>> Database empty. Seeding Owner...")
            
            # Main Owner: _fan_beluga_ / lolotrek
            hash_main = get_password_hash("lolotrek")
            await conn.execute("""
                INSERT INTO users (username, email, password_hash, nickname, role, coins, candy_balance)
                VALUES ('_fan_beluga_', 'fanbeluga@beluga.com', $1, 'Beluga Owner', 'owner', 999999, 999999)
            """, hash_main)
            print(">>> Seeded OWNER: login=_fan_beluga_ pass=lolotrek")

# ==========================================
# MODELS
# ==========================================
class LoginReq(BaseModel):
    identifier: str
    password: str

class RegisterReq(BaseModel):
    username: str
    password: str
    nickname: str

# ==========================================
# APP
# ==========================================
app = FastAPI(title="Belugacord API v2.8")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _startup():
    await init_db()
    print("DB ready.")

async def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    uid = decode_token(auth.split(" ", 1)[1])
    if not uid:
        raise HTTPException(401, "Invalid token")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", uid)
        if not row:
            raise HTTPException(401, "User gone")
        title = {}
        if row["active_custom_title_id"]:
            t = await conn.fetchrow("SELECT name,color_hex,bg_color_hex FROM custom_titles WHERE id=$1", row["active_custom_title_id"])
            if t:
                title = {"active_custom_title_name": t["name"], "active_custom_title_color": t["color_hex"], "active_custom_title_bg": t["bg_color_hex"]}
        bp = await conn.fetchrow("SELECT level,xp,has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_name='Halloween Spooktober'", uid)
        return {
            "id": row["id"], "username": row["username"], "nickname": row["nickname"],
            "avatar_url": row["avatar_url"], "coins": row["coins"], "candy": row["candy_balance"],
            "is_premium": row["is_premium"], "role": row["role"], "is_scammer": row["is_scammer"],
            "bp_level": bp["level"] if bp else 1, "bp_xp": bp["xp"] if bp else 0,
            "has_bp_premium": bp["has_premium_pass"] if bp else False, **title
        }

# Dependency for Admin Routes: Checks Role + PIN
async def require_admin_with_pin(user: dict = Depends(get_current_user), x_admin_pin: str = Header(None)):
    if user["role"] not in ("admin", "owner"):
        raise HTTPException(403, "Admin only")
    
    # Check PIN against DB
    p = await get_pool()
    async with p.acquire() as conn:
        stored_pin = await conn.fetchval("SELECT value FROM system_settings WHERE key='admin_pin'")
        
    if not x_admin_pin or x_admin_pin != stored_pin:
        raise HTTPException(401, "Invalid Admin PIN")
        
    return user

# ==========================================
# AUTH
# ==========================================
@app.post("/api/login")
async def login(req: LoginReq):
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchrow("SELECT * FROM users WHERE username=$1 OR email=$1", req.identifier)
        if not u or not verify_password(req.password, u["password_hash"]):
            raise HTTPException(401, "Wrong credentials")
        return {"access_token": create_access_token(u["id"]), "token_type": "bearer"}

@app.post("/api/register")
async def register(req: RegisterReq):
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchval("SELECT 1 FROM users WHERE username=$1", req.username):
            raise HTTPException(400, "Username taken")
        nid = await conn.fetchval("""
            INSERT INTO users (username,password_hash,nickname,role) VALUES ($1,$2,$3,'user') RETURNING id
        """, req.username, get_password_hash(req.password), req.nickname)
        await conn.execute("""
            INSERT INTO bp_progress (user_id,season_name,level,xp,has_premium_pass) VALUES ($1,'Halloween Spooktober',1,0,FALSE)
        """, nid)
        return {"access_token": create_access_token(nid), "token_type": "bearer"}

@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return user

# ==========================================
# CHATS
# ==========================================
@app.get("/api/chats/list")
async def chats_list(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.id,
                CASE WHEN c.user1_id=$1 THEN u2.nickname ELSE u1.nickname END AS partner_nickname,
                CASE WHEN c.user1_id=$1 THEN u2.avatar_url ELSE u1.avatar_url END AS partner_avatar,
                CASE WHEN c.user1_id=$1 THEN u2.is_scammer ELSE u1.is_scammer END AS is_scam,
                (SELECT content FROM messages WHERE chat_id=c.id ORDER BY created_at DESC LIMIT 1) AS last_msg_preview,
                (SELECT COUNT(*) FROM messages WHERE chat_id=c.id AND sender_id!=$1 AND read_status=FALSE) AS unread_count
            FROM chats c
            JOIN users u1 ON c.user1_id=u1.id
            JOIN users u2 ON c.user2_id=u2.id
            WHERE c.user1_id=$1 OR c.user2_id=$1
            ORDER BY (SELECT MAX(created_at) FROM messages WHERE chat_id=c.id) DESC NULLS LAST
        """, user["id"])
        return [{
            "id": r["id"], "partner_nickname": r["partner_nickname"], "partner_avatar": r["partner_avatar"],
            "is_scam": bool(r["is_scam"]), "last_msg_preview": r["last_msg_preview"] or "", "unread": r["unread_count"]
        } for r in rows]

@app.get("/api/chats/{chat_id}/messages")
async def chat_messages(chat_id: int, user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        ok = await conn.fetchval("SELECT 1 FROM chats WHERE id=$1 AND (user1_id=$2 OR user2_id=$2)", chat_id, user["id"])
        if not ok:
            raise HTTPException(403, "Denied")
        rows = await conn.fetch("SELECT id,sender_id,content,created_at AS timestamp FROM messages WHERE chat_id=$1 ORDER BY created_at ASC", chat_id)
        return [dict(r) for r in rows]

@app.post("/api/chats/create")
async def create_dm(target_user_id: int, user: dict = Depends(get_current_user)):
    if target_user_id == user["id"]:
        raise HTTPException(400, "Self")
    a, b = min(user["id"], target_user_id), max(user["id"], target_user_id)
    p = await get_pool()
    async with p.acquire() as conn:
        cid = await conn.fetchval("SELECT id FROM chats WHERE user1_id=$1 AND user2_id=$2", a, b)
        if not cid:
            cid = await conn.fetchval("INSERT INTO chats (user1_id,user2_id) VALUES ($1,$2) RETURNING id", a, b)
        return {"chat_id": cid}

# ==========================================
# FRIENDS
# ==========================================
@app.get("/api/friends/list")
async def friends_list(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.id,u.nickname,u.username,u.avatar_url,f.status
            FROM friends f JOIN users u ON (CASE WHEN f.user1_id=$1 THEN f.user2_id ELSE f.user1_id END)=u.id
            WHERE f.user1_id=$1 OR f.user2_id=$1
        """, user["id"])
        return [{"id": r["id"], "nickname": r["nickname"], "username": r["username"],
                 "avatar": r["avatar_url"], "online": True, "status": r["status"]} for r in rows]

@app.post("/api/friends/request")
async def friend_request(target_username: str, user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", target_username.lstrip("@"))
        if not t:
            raise HTTPException(404, "User not found")
        if t["id"] == user["id"]:
            raise HTTPException(400, "Self")
        ex = await conn.fetchrow("SELECT 1 FROM friends WHERE (user1_id=$1 AND user2_id=$2) OR (user1_id=$2 AND user2_id=$1)", user["id"], t["id"])
        if ex:
            raise HTTPException(400, "Already exists")
        await conn.execute("INSERT INTO friends (user1_id,user2_id,status) VALUES ($1,$2,'pending')", user["id"], t["id"])
        if t["id"] in active_connections:
            await active_connections[t["id"]].send_json({"type": "FRIEND_REQUEST", "payload": {"from_user": user["username"], "from_id": user["id"]}})
        return {"status": "sent"}

# ==========================================
# BATTLE PASS
# ==========================================
BP_SEASON = {"season_name": "Halloween Spooktober", "max_level": 50, "xp_per_level": 100}

def _gen_bp_rewards():
    out = []
    fe = ["🎃","️","🦇","️","💀","","","🍬"]
    ve = ["✨","🏆","","🔥","","🌟","💎","🎁"]
    for lvl in range(1, 51):
        out.append({"level": lvl, "track": "free", "type": "coins" if lvl % 2 == 0 else "candy",
                    "value": str(lvl * 10), "emoji": fe[lvl % len(fe)], "name": f"L{lvl} Free"})
        out.append({"level": lvl, "track": "vip", "type": "premium_days" if lvl % 5 == 0 else "rare_frame",
                    "value": "7 Days" if lvl % 5 == 0 else "Exclusive", "emoji": ve[lvl % len(ve)], "name": f"L{lvl} VIP"})
    return out

BP_REWARDS = _gen_bp_rewards()

@app.get("/api/bp/data")
async def bp_data(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        rec = await conn.fetchrow("SELECT level,xp,has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_name=$2", user["id"], BP_SEASON["season_name"])
        if not rec:
            await conn.execute("INSERT INTO bp_progress (user_id,season_name,level,xp,has_premium_pass) VALUES ($1,$2,1,0,FALSE)", user["id"], BP_SEASON["season_name"])
            lvl, xp, prem = 1, 0, False
        else:
            lvl, xp, prem = rec["level"], rec["xp"], rec["has_premium_pass"]
    return {"config": BP_SEASON, "user_progress": {"level": lvl, "xp": xp, "next_level_xp_needed": BP_SEASON["xp_per_level"], "is_premium_owner": prem}, "rewards_catalog": BP_REWARDS}

async def add_bp_xp_logic(conn, user_id: int, amount: int):
    season = BP_SEASON["season_name"]
    res = await conn.fetchrow("UPDATE bp_progress SET xp=xp+$1 WHERE user_id=$2 AND season_name=$3 RETURNING level,xp", amount, user_id, season)
    if not res:
        await conn.execute("INSERT INTO bp_progress (user_id,season_name,level,xp) VALUES ($1,$2,1,$3)", user_id, season, amount)
        return 1, amount, False
    lvl, xp = res["level"], res["xp"]
    th = BP_SEASON["xp_per_level"]
    up = False
    while xp >= th:
        xp -= th; lvl += 1; up = True
    if up:
        await conn.execute("UPDATE bp_progress SET level=$1,xp=$2 WHERE user_id=$3 AND season_name=$4", lvl, xp, user_id, season)
    return lvl, xp, up

# ==========================================
# TEACHER QUIZ
# ==========================================
QUIZ = [
    {"q":"Столица Франции?","opts":["Лондон","Париж","Берлин","Мадрид"],"ans":1},
    {"q":"Сколько сторон у куба?","opts":["4","6","8","12"],"ans":1},
    {"q":"Автор 'Войны и мира'?","opts":["Достоевский","Толстой","Чехов","Пушкин"],"ans":1},
    {"q":"Символ золота?","opts":["Ag","Au","Fe","Cu"],"ans":1},
    {"q":"Самая длинная река?","opts":["Нил","Амазонка","Янцзы","Миссисипи"],"ans":0},
    {"q":"Год начала ВМВ?","opts":["1939","1941","1914","1945"],"ans":0},
    {"q":"Кто открыл Америку?","opts":["Магеллан","Колумб","Васко да Гама","Кук"],"ans":1},
    {"q":"Формула воды?","opts":["CO2","H2O","O2","NaCl"],"ans":1},
    {"q":"Цветов в радуге?","opts":["5","6","7","8"],"ans":2},
    {"q":"Автор 'Моны Лизы'?","opts":["Рафаэль","Леонардо","Микеланджело","Тициан"],"ans":1},
    {"q":"Столица Японии?","opts":["Пекин","Сеул","Токио","Бангкок"],"ans":2},
    {"q":"Самое большое животное?","opts":["Слон","Жираф","Синий кит","Буйвол"],"ans":2},
    {"q":"Планет в системе?","opts":["7","8","9","10"],"ans":1},
    {"q":"Кто изобрел лампочку?","opts":["Эдисон","Тесла","Маркони","Попов"],"ans":0},
    {"q":"Единица силы тока?","opts":["Вольт","Ампер","Ом","Ватт"],"ans":1},
    {"q":"Высочайший пик?","opts":["К2","Эверест","Килиманджаро","Монблан"],"ans":1},
    {"q":"Год полёта в космос?","opts":["1957","1961","1969","1975"],"ans":1},
    {"q":"Герой 'Капитанской дочки'?","opts":["Швабрин","Гринев","Пугачев","Маша"],"ans":1},
    {"q":"Фотосинтез это?","opts":["Дыхание","Питание растений","Разложение","Испарение"],"ans":1},
    {"q":"Дней в високосном?","opts":["364","365","366","367"],"ans":2},
]

@app.get("/api/quiz/status")
async def quiz_status():
    p = await get_pool()
    async with p.acquire() as conn:
        v = await conn.fetchval("SELECT value FROM system_settings WHERE key='teacher_quiz_active'")
    return {"active": v == "true"}

@app.post("/api/admin/toggle-quiz")
async def toggle_quiz(active: bool, admin: dict = Depends(require_admin_with_pin)):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO system_settings (key,value) VALUES ('teacher_quiz_active',$1) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", "true" if active else "false")
    return {"status": "ok", "active": active}

@app.get("/api/quiz/question")
async def quiz_question(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        pr = await conn.fetchrow("SELECT * FROM teacher_quiz_progress WHERE user_id=$1", user["id"])
        if not pr:
            await conn.execute("INSERT INTO teacher_quiz_progress (user_id) VALUES ($1)", user["id"])
            idx = 0
        else:
            idx = pr["current_question_index"]
        if idx >= len(QUIZ):
            return {"finished": True, "score": pr["score"] if pr else 0}
        q = QUIZ[idx]
        return {"finished": False, "question_index": idx, "total_questions": len(QUIZ), "question": q["q"], "options": q["opts"]}

@app.post("/api/quiz/answer")
async def quiz_answer(answer_idx: int, user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        pr = await conn.fetchrow("SELECT * FROM teacher_quiz_progress WHERE user_id=$1", user["id"])
        if not pr or pr["completed"]:
            return {"error": "not started/finished"}
        idx = pr["current_question_index"]
        correct = (answer_idx == QUIZ[idx]["ans"])
        new_score = pr["score"] + (1 if correct else 0)
        nxt = idx + 1
        done = nxt >= len(QUIZ)
        await conn.execute("UPDATE teacher_quiz_progress SET current_question_index=$1,score=$2,completed=$3 WHERE user_id=$4", nxt, new_score, done, user["id"])
        rewards = []
        if done:
            if new_score == 20:
                tid = await conn.fetchval("SELECT id FROM custom_titles WHERE name='Учитель года 👑'")
                if not tid:
                    tid = await conn.fetchval("INSERT INTO custom_titles (name,color_hex,is_global,created_by) VALUES ('Учитель года 👑','#FFD700',TRUE,0) RETURNING id")
                await conn.execute("UPDATE users SET active_custom_title_id=$1 WHERE id=$2", tid, user["id"])
                rewards.append({"type": "title", "name": "Учитель года 👑"})
            elif new_score >= 15:
                await conn.execute("UPDATE users SET candy_balance=candy_balance+500 WHERE id=$1", user["id"])
                rewards.append({"type": "candy", "amount": 500})
            else:
                await conn.execute("UPDATE users SET candy_balance=candy_balance+100 WHERE id=$1", user["id"])
                rewards.append({"type": "candy", "amount": 100})
        return {"correct": correct, "next_index": nxt, "finished": done, "rewards": rewards}

# ==========================================
# SHOP
# ==========================================
SHOP = [
    {"id":1,"name":"Рамка Призрак","price":500,"currency":"candy","emoji":"👻","type":"frame"},
    {"id":2,"name":"Премиум 1 день","price":1000,"currency":"coins","emoji":"⭐","type":"premium"},
    {"id":3,"name":"XP Boost","price":200,"currency":"candy","emoji":"🚀","type":"boost"},
    {"id":4,"name":"Подарок Тыква","price":50,"currency":"candy","emoji":"🎃","type":"gift"},
]

@app.get("/api/shop/items")
async def shop_items(user: dict = Depends(get_current_user)):
    return SHOP

@app.post("/api/shop/buy")
async def shop_buy(item_id: int, user: dict = Depends(get_current_user)):
    item = next((i for i in SHOP if i["id"] == item_id), None)
    if not item:
        raise HTTPException(404, "No item")
    bal = user["candy"] if item["currency"] == "candy" else user["coins"]
    if bal < item["price"]:
        raise HTTPException(400, "Insufficient funds")
    col = "candy_balance" if item["currency"] == "candy" else "coins"
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(f"UPDATE users SET {col}={col}-$1 WHERE id=$2", item["price"], user["id"])
        if item["type"] == "premium":
            await conn.execute("UPDATE users SET is_premium=TRUE WHERE id=$1", user["id"])
    return {"status": "success", "message": f"Куплено: {item['name']}"}

# ==========================================
# ADMIN TITLES & SCAM (Protected by PIN)
# ==========================================
@app.get("/api/admin/titles/list")
async def titles_list(admin: dict = Depends(require_admin_with_pin)):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM custom_titles ORDER BY created_at DESC")
    return [dict(r) for r in rows]

@app.post("/api/admin/titles/create")
async def title_create(name: str, color: str, is_global: bool, admin: dict = Depends(require_admin_with_pin)):
    p = await get_pool()
    async with p.acquire() as conn:
        tid = await conn.fetchval("INSERT INTO custom_titles (name,color_hex,is_global,created_by) VALUES ($1,$2,$3,$4) RETURNING id", name, color, is_global, admin["id"])
    return {"id": tid, "status": "created"}

@app.post("/api/admin/titles/grant")
async def title_grant(target_user_id: int, title_id: int, admin: dict = Depends(require_admin_with_pin)):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET active_custom_title_id=$1 WHERE id=$2", title_id, target_user_id)
    return {"status": "granted"}

@app.post("/api/admin/scam/toggle")
async def scam_toggle(user_id: int, is_scammer: bool, admin: dict = Depends(require_admin_with_pin)):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_scammer=$1 WHERE id=$2", is_scammer, user_id)
    return {"status": "updated", "is_scammer": is_scammer}

# ==========================================
# WEBSOCKET
# ==========================================
active_connections: Dict[int, WebSocket] = {}

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            if data["type"] == "AUTH":
                uid = decode_token(data["token"])
                if not uid:
                    await websocket.close(code=4001); return
                user_id = uid
                active_connections[user_id] = websocket
                await websocket.send_json({"type": "SYSTEM", "payload": {"message": "Connected"}})
            elif data["type"] == "SEND_MSG":
                if not user_id: continue
                pl = data["payload"]
                cid, content = pl["chat_id"], pl["content"]
                p = await get_pool()
                async with p.acquire() as conn:
                    mid = await conn.fetchval("INSERT INTO messages (chat_id,sender_id,content) VALUES ($1,$2,$3) RETURNING id", cid, user_id, content)
                    rid = await conn.fetchval("SELECT CASE WHEN user1_id=$1 THEN user2_id ELSE user1_id END FROM chats WHERE id=$2", user_id, cid)
                    nl, nx, up = await add_bp_xp_logic(conn, user_id, 1)
                    if up and user_id in active_connections:
                        await active_connections[user_id].send_json({"type": "BP_LEVEL_UP", "payload": {"new_level": nl}})
                if rid and rid in active_connections:
                    await active_connections[rid].send_json({"type": "NEW_MESSAGE", "payload": {"chat_id": cid, "content": content, "timestamp": datetime.now().isoformat(), "sender_id": user_id}})
                await websocket.send_json({"type": "MSG_SENT", "payload": {"chat_id": cid, "msg_id": mid}})
    except WebSocketDisconnect:
        if user_id in active_connections: del active_connections[user_id]
    except Exception as e:
        print("WS err:", e)
        if user_id in active_connections: del active_connections[user_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)