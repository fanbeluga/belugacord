import hashlib
import hmac
import json
import base64
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# ==========================================
# CONFIGURATION & SECURITY (STDLIB ONLY)
# ==========================================
SECRET_KEY = "belugacord_super_secret_key_change_in_prod_2026" # CHANGE THIS!

def verify_password(plain_password, hashed_password):
    # Сравнение SHA256 хешей
    return get_password_hash(plain_password) == hashed_password

def get_password_hash(password):
    # Хешируем пароль через SHA256 (достаточно для беты, в проде лучше bcrypt/argon2)
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=30) # Долгий срок для мобильного приложения
    
    to_encode.update({"exp": int(expire.timestamp())})
    
    # Кодируем payload в Base64 URL-safe
    payload_bytes = json.dumps(to_encode).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode('utf-8')
    
    # Создаем подпись (Signature)
    signature_input = f"{payload_b64}".encode('utf-8')
    signature = hmac.new(SECRET_KEY.encode('utf-8'), signature_input, hashlib.sha256).hexdigest()
    
    # Формируем токен: payload.signature
    return f"{payload_b64}.{signature}"

async def decode_token(token: str):
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        
        payload_b64, provided_signature = parts
        
        # Проверяем подпись
        signature_input = f"{payload_b64}".encode('utf-8')
        expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), signature_input, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None
            
        # Декодируем payload
        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
        payload = json.loads(payload_bytes.decode('utf-8'))
        
        # Проверяем срок годности
        exp = payload.get("exp")
        if exp and time.time() > exp:
            return None
            
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except Exception:
        return None

# ==========================================
# DATABASE POOL & INITIALIZATION
# ==========================================
pool: Optional[asyncpg.Pool] = None

async def get_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DB_DSN, min_size=1, max_size=10)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        # 1. Users Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                nickname VARCHAR(50) DEFAULT 'User',
                avatar_url TEXT DEFAULT '',
                coins INTEGER DEFAULT 0,
                candy_balance INTEGER DEFAULT 0,
                is_premium BOOLEAN DEFAULT FALSE,
                role VARCHAR(20) DEFAULT 'user', -- user, admin, owner
                is_scammer BOOLEAN DEFAULT FALSE,
                active_custom_title_id INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 2. Chats & Messages
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                user1_id INTEGER REFERENCES users(id),
                user2_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(user1_id, user2_id)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER REFERENCES chats(id),
                sender_id INTEGER REFERENCES users(id),
                content TEXT,
                read_status BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 3. Friends System
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id SERIAL PRIMARY KEY,
                user1_id INTEGER REFERENCES users(id),
                user2_id INTEGER REFERENCES users(id),
                status VARCHAR(20) DEFAULT 'pending', -- pending, accepted, rejected
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(user1_id, user2_id)
            );
        """)

        # 4. Battle Pass Progress
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bp_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                season_name VARCHAR(100),
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                has_premium_pass BOOLEAN DEFAULT FALSE,
                claimed_levels TEXT DEFAULT '{}', -- Array of claimed level numbers stored as string for simplicity
                UNIQUE(user_id, season_name)
            );
        """)

        # 5. Teacher Quiz Progress
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS teacher_quiz_progress (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                current_question_index INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT FALSE,
                score INTEGER DEFAULT 0,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 6. System Settings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key VARCHAR(50) PRIMARY KEY,
                value TEXT
            );
            INSERT INTO system_settings (key, value) VALUES ('teacher_quiz_active', 'true') ON CONFLICT DO NOTHING;
        """)

        # 7. Custom Titles
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_titles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                color_hex VARCHAR(7) DEFAULT '#FFFFFF',
                bg_color_hex VARCHAR(7) DEFAULT 'transparent',
                is_global BOOLEAN DEFAULT FALSE,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # Seed Admin User if empty
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count == 0:
            hash_pw = get_password_hash("admin123")
            await conn.execute("""
                INSERT INTO users (username, email, password_hash, nickname, role, coins, candy_balance)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, "admin", "admin@beluga.com", hash_pw, "Beluga Owner", "owner", 999999, 999999)
            print(">>> Created default admin user: username='admin', password='admin123'")

# ==========================================
# DATA MODELS (Pydantic)
# ==========================================
class Token(BaseModel):
    access_token: str
    token_type: str

class UserPublic(BaseModel):
    id: int
    username: str
    nickname: str
    avatar_url: str
    is_scammer: bool
    role: str

class LoginRequest(BaseModel):
    identifier: str # Username or Email
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str

# ==========================================
# FASTAPP SETUP
# ==========================================
app = FastAPI(title="Belugacord API v2.8")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for APK WebView compatibility during dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()
    print("Database initialized successfully.")

# Dependency to get current user from Bearer Token
async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(" ")[1]
    user_id = await decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
            
        # Fetch Title info
        title_data = {}
        if row['active_custom_title_id']:
            t_row = await conn.fetchrow("SELECT name, color_hex, bg_color_hex FROM custom_titles WHERE id=$1", row['active_custom_title_id'])
            if t_row:
                title_data = {
                    "active_custom_title_name": t_row['name'],
                    "active_custom_title_color": t_row['color_hex'],
                    "active_custom_title_bg": t_row['bg_color_hex']
                }
                
        # Fetch BP info
        bp_row = await conn.fetchrow("SELECT level, xp, has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_name='Halloween Spooktober'", user_id)
        bp_level = bp_row['level'] if bp_row else 1
        bp_xp = bp_row['xp'] if bp_row else 0
        has_bp_premium = bp_row['has_premium_pass'] if bp_row else False

        return {
            "id": row['id'],
            "username": row['username'],
            "nickname": row['nickname'],
            "avatar_url": row['avatar_url'],
            "coins": row['coins'],
            "candy": row['candy_balance'],
            "is_premium": row['is_premium'],
            "role": row['role'],
            "is_scammer": row['is_scammer'],
            "bp_level": bp_level,
            "bp_xp": bp_xp,
            "has_bp_premium": has_bp_premium,
            **title_data
        }

def require_admin(user: dict = Depends(get_current_user)):
    if user['role'] not in ['admin', 'owner']:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

# ==========================================
# AUTH ENDPOINTS
# ==========================================
@app.post("/api/login", response_model=Token)
async def login(req: LoginRequest):
    p = await get_pool()
    async with p.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE username=$1 OR email=$1", req.identifier)
        if not user or not verify_password(req.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Incorrect credentials")
        
        token = create_access_token(data={"sub": str(user['id'])})
        return {"access_token": token, "token_type": "bearer"}

@app.post("/api/register")
async def register(req: RegisterRequest):
    p = await get_pool()
    async with p.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM users WHERE username=$1", req.username)
        if exists:
            raise HTTPException(status_code=400, detail="Username taken")
        
        hashed_pw = get_password_hash(req.password)
        new_id = await conn.fetchval("""
            INSERT INTO users (username, password_hash, nickname, role) 
            VALUES ($1, $2, $3, 'user') RETURNING id
        """, req.username, hashed_pw, req.nickname)
        
        # Auto-init BP
        await conn.execute("""
            INSERT INTO bp_progress (user_id, season_name, level, xp, has_premium_pass)
            VALUES ($1, 'Halloween Spooktober', 1, 0, FALSE)
        """, new_id)

        token = create_access_token(data={"sub": str(new_id)})
        return {"access_token": token, "token_type": "bearer"}

@app.get("/api/me")
async def me(user: dict = Depends(get_current_user)):
    return user

# ==========================================
# CHATS & MESSAGES
# ==========================================
@app.get("/api/chats/list")
async def get_chats_list(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                c.id,
                CASE WHEN c.user1_id = $1 THEN u2.nickname ELSE u1.nickname END as partner_nickname,
                CASE WHEN c.user1_id = $1 THEN u2.avatar_url ELSE u1.avatar_url END as partner_avatar,
                CASE WHEN c.user1_id = $1 THEN u2.is_scammer ELSE u1.is_scammer END as is_scam,
                (SELECT content FROM messages WHERE chat_id=c.id ORDER BY created_at DESC LIMIT 1) as last_msg_preview,
                (SELECT COUNT(*) FROM messages WHERE chat_id=c.id AND sender_id != $1 AND read_status=false) as unread_count
            FROM chats c
            JOIN users u1 ON c.user1_id = u1.id
            JOIN users u2 ON c.user2_id = u2.id
            WHERE c.user1_id = $1 OR c.user2_id = $1
            ORDER BY (SELECT MAX(created_at) FROM messages WHERE chat_id=c.id) DESC
        """, user['id'])
        
        result = []
        for r in rows:
            result.append({
                "id": r['id'],
                "partner_nickname": r['partner_nickname'],
                "partner_avatar": r['partner_avatar'],
                "is_scam": bool(r['is_scam']),
                "last_msg_preview": r['last_msg_preview'] or "",
                "unread": r['unread_count']
            })
        return result

@app.get("/api/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: int, user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM chats WHERE id=$1 AND (user1_id=$2 OR user2_id=$2)", chat_id, user['id'])
        if not exists:
            raise HTTPException(status_code=403, detail="Access denied")
            
        rows = await conn.fetch("""
            SELECT id, sender_id, content, created_at as timestamp 
            FROM messages 
            WHERE chat_id=$1 
            ORDER BY created_at ASC
        """, chat_id)
        return [dict(r) for r in rows]

# Helper to find/create DM chat
async def get_or_create_dm(conn, user1_id, user2_id):
    # Ensure order doesn't matter for uniqueness constraint logic if implemented differently, 
    # but our schema uses unique pair. Let's normalize IDs.
    min_id = min(user1_id, user2_id)
    max_id = max(user1_id, user2_id)
    
    chat = await conn.fetchrow("SELECT id FROM chats WHERE user1_id=$1 AND user2_id=$2", min_id, max_id)
    if chat:
        return chat['id']
    
    new_chat_id = await conn.fetchval("INSERT INTO chats (user1_id, user2_id) VALUES ($1, $2) RETURNING id", min_id, max_id)
    return new_chat_id

# ==========================================
# FRIENDS SYSTEM
# ==========================================
@app.get("/api/friends/list")
async def get_friends_list(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.id, u.nickname, u.username, u.avatar_url, f.status 
            FROM friends fl 
            JOIN users u ON (CASE WHEN fl.user1_id=$1 THEN fl.user2_id ELSE fl.user1_id END)=u.id 
            WHERE fl.user1_id=$1 OR fl.user2_id=$1
        """, user['id'])
        
        result = []
        for r in rows:
            result.append({
                "id": r['id'],
                "nickname": r['nickname'],
                "username": r['username'],
                "avatar": r['avatar_url'],
                "online": True, # Mock online status
                "status": r['status']
            })
        return result

@app.post("/api/friends/request")
async def send_friend_request(target_username: str, user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT id FROM users WHERE username=$1", target_username.lstrip('@'))
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        
        if target['id'] == user['id']:
            raise HTTPException(status_code=400, detail="Cannot add yourself")
            
        # Check existing relationship
        existing = await conn.fetchrow("SELECT 1 FROM friends WHERE (user1_id=$1 AND user2_id=$2) OR (user1_id=$2 AND user2_id=$1)", user['id'], target['id'])
        if existing:
             raise HTTPException(status_code=400, detail="Already requested or friends")

        await conn.execute("""
            INSERT INTO friends (user1_id, user2_id, status) VALUES ($1, $2, 'pending')
        """, user['id'], target['id'])
        
        # Notify via WS if online
        if target['id'] in active_connections:
            await active_connections[target['id']].send_json({
                "type": "FRIEND_REQUEST",
                "payload": {"from_user": user['username'], "from_id": user['id']}
            })
            
    return {"status": "sent"}

# ==========================================
# BATTLE PASS SYSTEM
# ==========================================
BP_SEASON_CONFIG = {
    "season_name": "Halloween Spooktober",
    "max_level": 50,
    "xp_per_level": 100,
}

def generate_static_bp_rewards():
    """Generates consistent rewards so client/server match without DB storage of catalog."""
    rewards = []
    emojis_free = ["🎃", "🕷️", "🦇", "🕸️", "💀", "🧟", "", ""]
    emojis_vip = ["✨", "🏆", "👑", "🔥", "", "🌟", "💎", ""]
    
    for lvl in range(1, 51):
        # Deterministic selection based on level number
        free_idx = lvl % len(emojis_free)
        vip_idx = lvl % len(emojis_vip)
        
        rewards.append({
            "level": lvl,
            "track": "free",
            "type": "coins" if lvl % 2 == 0 else "candy",
            "value": f"{lvl * 10}",
            "emoji": emojis_free[free_idx],
            "name": f"L{lvl} Free Reward"
        })
        rewards.append({
            "level": lvl,
            "track": "vip",
            "type": "premium_days" if lvl % 5 == 0 else "rare_frame",
            "value": "7 Days" if lvl % 5 == 0 else "Exclusive",
            "emoji": emojis_vip[vip_idx],
            "name": f"L{lvl} VIP Reward"
        })
    return rewards

ALL_BP_REWARDS_CACHE = generate_static_bp_rewards()

@app.get("/api/bp/data")
async def get_battle_pass_data(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        record = await conn.fetchrow("""
            SELECT level, xp, has_premium_pass 
            FROM bp_progress 
            WHERE user_id = $1 AND season_name = $2
        """, user['id'], BP_SEASON_CONFIG["season_name"])

        if not record:
            # Should be caught by registration/init, but safety net:
            await conn.execute("""
                INSERT INTO bp_progress (user_id, season_name, level, xp, has_premium_pass)
                VALUES ($1, $2, 1, 0, FALSE)
            """, user['id'], BP_SEASON_CONFIG["season_name"])
            user_level, user_xp, is_prem = 1, 0, False
        else:
            user_level = record['level']
            user_xp = record['xp']
            is_prem = record['has_premium_pass']

    return {
        "config": BP_SEASON_CONFIG,
        "user_progress": {
            "level": user_level,
            "xp": user_xp,
            "next_level_xp_needed": BP_SEASON_CONFIG["xp_per_level"],
            "is_premium_owner": is_prem
        },
        "rewards_catalog": ALL_BP_REWARDS_CACHE
    }

# Internal function to add XP (called from WS handler)
async def add_bp_xp_logic(conn, user_id, amount):
    season = BP_SEASON_CONFIG["season_name"]
    
    # Upsert pattern
    res = await conn.fetchval(f"""
        UPDATE bp_progress SET xp = xp + $1 
        WHERE user_id = $2 AND season_name = '{season}'
        RETURNING level, xp
    """, amount, user_id)
    
    if not res:
         # Create if missing
         await conn.execute(f"""
            INSERT INTO bp_progress (user_id, season_name, level, xp) VALUES ($1, '{season}', 1, $2)
         """, user_id, amount)
         return 1, amount

    lvl, xp = res
    threshold = BP_SEASON_CONFIG["xp_per_level"]
    
    leveled_up = False
    while xp >= threshold:
        xp -= threshold
        lvl += 1
        leveled_up = True
        
    if leveled_up:
        await conn.execute(f"""
            UPDATE bp_progress SET level=$1, xp=$2 
            WHERE user_id=$3 AND season_name='{season}'
        """, lvl, xp, user_id)
        
    return lvl, xp, leveled_up

# ==========================================
# TEACHER QUIZ SYSTEM
# ==========================================
TEACHER_QUIZ_DATA = [
    {"q": "Столица Франции?", "opts": ["Лондон", "Париж", "Берлин", "Мадрид"], "ans": 1},
    {"q": "Сколько сторон у куба?", "opts": ["4", "6", "8", "12"], "ans": 1},
    {"q": "Автор романа 'Война и мир'?", "opts": ["Достоевский", "Толстой", "Чехов", "Пушкин"], "ans": 1},
    {"q": "Химический символ золота?", "opts": ["Ag", "Au", "Fe", "Cu"], "ans": 1},
    {"q": "Самая длинная река в мире?", "opts": ["Нил", "Амазонка", "Янцзы", "Миссисипи"], "ans": 0},
    {"q": "Год начала Второй мировой войны?", "opts": ["1939", "1941", "1914", "1945"], "ans": 0},
    {"q": "Кто открыл Америку?", "opts": ["Магеллан", "Колумб", "Васко да Гама", "Кук"], "ans": 1},
    {"q": "Формула воды?", "opts": ["CO2", "H2O", "O2", "NaCl"], "ans": 1},
    {"q": "Сколько цветов в радуге?", "opts": ["5", "6", "7", "8"], "ans": 2},
    {"q": "Кто написал картину 'Мона Лиза'?", "opts": ["Рафаэль", "Леонардо да Винчи", "Микеланджело", "Тициан"], "ans": 1},
    {"q": "Столица Японии?", "opts": ["Пекин", "Сеул", "Токио", "Бангкок"], "ans": 2},
    {"q": "Какое животное самое большое на Земле?", "opts": ["Слон", "Жираф", "Синий кит", "Африканский буйвол"], "ans": 2},
    {"q": "Сколько планет в Солнечной системе?", "opts": ["7", "8", "9", "10"], "ans": 1},
    {"q": "Кто изобрел лампочку?", "opts": ["Эдисон", "Тесла", "Маркони", "Попов"], "ans": 0},
    {"q": "Единица измерения силы тока?", "opts": ["Вольт", "Ампер", "Ом", "Ватт"], "ans": 1},
    {"q": "Самый высокий горный пик?", "opts": ["К2", "Эверест", "Килиманджаро", "Монблан"], "ans": 1},
    {"q": "В каком году человек впервые полетел в космос?", "opts": ["1957", "1961", "1969", "1975"], "ans": 1},
    {"q": "Главный герой повести 'Капитанская дочка'?", "opts": ["Швабрин", "Гринев", "Пугачев", "Маша"], "ans": 1},
    {"q": "Что такое Photosynthesis (Фотосинтез)?", "opts": ["Дыхание животных", "Процесс питания растений", "Разложение органики", "Испарение воды"], "ans": 1},
    {"q": "Сколько дней в високосном году?", "opts": ["364", "365", "366", "367"], "ans": 2}
]

@app.get("/api/quiz/status")
async def get_quiz_status():
    p = await get_pool()
    async with p.acquire() as conn:
        setting = await conn.fetchval("SELECT value FROM system_settings WHERE key='teacher_quiz_active'")
    return {"active": setting == 'true'}

@app.post("/api/admin/toggle-quiz")
async def toggle_quiz(active: bool, admin: dict = Depends(require_admin)):
    p = await get_pool()
    async with p.acquire() as conn:
        val = 'true' if active else 'false'
        await conn.execute("""
            INSERT INTO system_settings (key, value) VALUES ('teacher_quiz_active', $1)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, val)
    return {"status": "ok", "active": active}

@app.get("/api/quiz/question")
async def get_next_question(user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        progress = await conn.fetchrow("SELECT * FROM teacher_quiz_progress WHERE user_id=$1", user['id'])
        if not progress:
            await conn.execute("INSERT INTO teacher_quiz_progress (user_id) VALUES ($1)", user['id'])
            idx = 0
        else:
            idx = progress['current_question_index']
            
        if idx >= len(TEACHER_QUIZ_DATA):
            return {"finished": True, "score": progress['score']}
            
        q_data = TEACHER_QUIZ_DATA[idx]
        return {
            "finished": False,
            "question_index": idx,
            "total_questions": len(TEACHER_QUIZ_DATA),
            "question": q_data["q"],
            "options": q_data["opts"]
        }

@app.post("/api/quiz/answer")
async def submit_answer(answer_idx: int, user: dict = Depends(get_current_user)):
    p = await get_pool()
    async with p.acquire() as conn:
        progress = await conn.fetchrow("SELECT * FROM teacher_quiz_progress WHERE user_id=$1", user['id'])
        if not progress or progress['completed']:
             return {"error": "Quiz already finished or not started"}
             
        idx = progress['current_question_index']
        correct_ans = TEACHER_QUIZ_DATA[idx]['ans']
        is_correct = (answer_idx == correct_ans)
        
        new_score = progress['score'] + (1 if is_correct else 0)
        next_idx = idx + 1
        
        await conn.execute("""
            UPDATE teacher_quiz_progress 
            SET current_question_index=$1, score=$2, completed=(CASE WHEN $3 >= $4 THEN TRUE ELSE FALSE END)
            WHERE user_id=$5
        """, next_idx, new_score, next_idx, len(TEACHER_QUIZ_DATA), user['id'])
        
        rewards_given = []
        if next_idx >= len(TEACHER_QUIZ_DATA):
            if new_score == 20:
                # Give Title
                tid = await conn.fetchval("SELECT id FROM custom_titles WHERE name='Учитель года 👑'")
                if not tid:
                    tid = await conn.fetchval("""
                        INSERT INTO custom_titles (name, color_hex, is_global, created_by) 
                        VALUES ('Учитель года 👑', '#FFD700', TRUE, 0) RETURNING id
                    """)
                await conn.execute("UPDATE users SET active_custom_title_id=$1 WHERE id=$2", tid, user['id'])
                rewards_given.append({"type":"title","name":"Учитель года 👑"})
            elif new_score >= 15:
                await conn.execute("UPDATE users SET candy_balance = candy_balance + 500 WHERE id=$1", user['id'])
                rewards_given.append({"type":"candy","amount":500})
            else:
                await conn.execute("UPDATE users SET candy_balance = candy_balance + 100 WHERE id=$1", user['id'])
                rewards_given.append({"type":"candy","amount":100})
                
        return {"correct": is_correct, "next_index": next_idx, "finished": next_idx >= len(TEACHER_QUIZ_DATA), "rewards": rewards_given}

# ==========================================
# SHOP SYSTEM
# ==========================================
SHOP_ITEMS_STATIC = [
    {"id": 1, "name": "Рамка 'Призрак'", "price": 500, "currency": "candy", "emoji": "👻", "type": "frame"},
    {"id": 2, "name": "Премиум 1 день", "price": 1000, "currency": "coins", "emoji": "⭐", "type": "premium"},
    {"id": 3, "name": "XP Boost x2", "price": 200, "currency": "candy", "emoji": "🚀", "type": "boost"},
    {"id": 4, "name": "Подарок 'Тыква'", "price": 50, "currency": "candy", "emoji": "🎃", "type": "gift"},
]

@app.get("/api/shop/items")
async def get_shop_items(user: dict = Depends(get_current_user)):
    return SHOP_ITEMS_STATIC

@app.post("/api/shop/buy")
async def buy_item(item_id: int, user: dict = Depends(get_current_user)):
    item = next((i for i in SHOP_ITEMS_STATIC if i['id'] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
        
    p = await get_pool()
    async with p.acquire() as conn:
        # Check Balance
        balance_field = 'candy_balance' if item['currency'] == 'candy' else 'coins'
        current_bal = user[balance_field.replace('_balance','')] if balance_field=='candy_balance' else user['coins']
        # Note: user dict from dependency has 'candy' and 'coins'. Adjust mapping.
        actual_bal = user['candy'] if item['currency']=='candy' else user['coins']
        
        if actual_bal < item['price']:
            raise HTTPException(status_code=400, detail="Insufficient funds")
            
        # Deduct
        col = 'candy_balance' if item['currency']=='candy' else 'coins'
        await conn.execute(f"UPDATE users SET {col} = {col} - $1 WHERE id=$2", item['price'], user['id'])
        
        # Grant Item (Mock logic: just update premium flag if it's premium item)
        if item['type'] == 'premium':
             await conn.execute("UPDATE users SET is_premium = TRUE WHERE id=$1", user['id'])
             
    return {"status": "success", "message": f"Bought {item['name']}"}

# ==========================================
# ADMIN TITLES & SCAM
# ==========================================
@app.get("/api/admin/titles/list")
async def list_all_titles(admin: dict = Depends(require_admin)):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM custom_titles ORDER BY created_at DESC")
    return [dict(r) for r in rows]

@app.post("/api/admin/titles/create")
async def create_new_title(name: str, color: str, is_global: bool, admin: dict = Depends(require_admin)):
    p = await get_pool()
    async with p.acquire() as conn:
        tid = await conn.fetchval("""
            INSERT INTO custom_titles (name, color_hex, is_global, created_by) 
            VALUES ($1, $2, $3, $4) RETURNING id
        """, name, color, is_global, admin['id'])
    return {"id": tid, "status": "created"}

@app.post("/api/admin/titles/grant")
async def grant_title_to_user(target_user_id: int, title_id: int, admin: dict = Depends(require_admin)):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET active_custom_title_id=$1 WHERE id=$2", title_id, target_user_id)
    return {"status": "granted"}

@app.post("/api/admin/scam/toggle")
async def toggle_scam_mode(user_id: int, is_scammer: bool, admin: dict = Depends(require_admin)):
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_scammer=$1 WHERE id=$2", is_scammer, user_id)
    return {"status": "updated", "is_scammer": is_scammer}

# ==========================================
# WEBSOCKET HANDLER
# ==========================================
active_connections: Dict[int, WebSocket] = {}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    
    try:
        while True:
            data_json = await websocket.receive_text()
            data = json.loads(data_json)
            
            if data["type"] == "AUTH":
                token = data["token"]
                uid = await decode_token(token)
                if not uid:
                    await websocket.close(code=4001)
                    return
                
                user_id = uid
                active_connections[user_id] = websocket
                await websocket.send_json({"type": "SYSTEM", "payload": {"message": "Connected"}})
            
            elif data["type"] == "SEND_MSG":
                if not user_id: continue
                
                payload = data["payload"]
                chat_id = payload["chat_id"]
                content = payload["content"]
                
                p = await get_pool()
                async with p.acquire() as conn:
                    # Save Message
                    msg_id = await conn.fetchval("""
                        INSERT INTO messages (chat_id, sender_id, content) 
                        VALUES ($1, $2, $3) RETURNING id
                    """, chat_id, user_id, content)
                    
                    # Get Receiver ID
                    receiver_query = """
                        SELECT CASE WHEN user1_id=$1 THEN user2_id ELSE user1_id END as rid 
                        FROM chats WHERE id=$2
                    """
                    receiver_id = await conn.fetchval(receiver_query, user_id, chat_id)
                    
                    # Add XP for sending message (1 XP per message)
                    new_lvl, new_xp, leveled_up = await add_bp_xp_logic(conn, user_id, 1)
                    
                    if leveled_up and user_id in active_connections:
                         await active_connections[user_id].send_json({
                            "type": "BP_LEVEL_UP",
                            "payload": {"new_level": new_lvl}
                        })

                # Notify Receiver if online
                if receiver_id and receiver_id in active_connections:
                    recipient_ws = active_connections[receiver_id]
                    await recipient_ws.send_json({
                        "type": "NEW_MESSAGE",
                        "payload": {
                            "chat_id": chat_id,
                            "content": content,
                            "timestamp": datetime.now().isoformat(),
                            "sender_id": user_id
                        }
                    })
                    
                # Acknowledge Sender
                await websocket.send_json({
                    "type": "MSG_SENT",
                    "payload": {"chat_id": chat_id, "msg_id": msg_id}
                })

    except WebSocketDisconnect:
        if user_id and user_id in active_connections:
            del active_connections[user_id]
    except Exception as e:
        print(f"WS Error: {e}")
        if user_id and user_id in active_connections:
            del active_connections[user_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)