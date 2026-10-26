# server.py — BelugaCord 4.5 (Полный сервер + Авто-запуск Uvicorn)
# Запуск: python3 server.py (он сам поднимет uvicorn на 0.0.0.0:8000)
# Установка зависимостей: pip install fastapi uvicorn websockets python-multipart

import sqlite3, asyncio, json, os, hashlib, time, shutil, uuid, uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Создаем папки, если их нет
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
DB_PATH = "beluga.db"

# --- БАЗА ДАННЫХ ---
def db_init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE, pass_hash TEXT, display_name TEXT,
        role TEXT DEFAULT 'user', is_banned INTEGER DEFAULT 0,
        is_scam INTEGER DEFAULT 0, is_spam_blocked INTEGER DEFAULT 0,
        coins INTEGER DEFAULT 0, premium_until INTEGER DEFAULT 0,
        avatar TEXT DEFAULT '', bio TEXT DEFAULT '', last_seen INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, sender TEXT, text TEXT, type TEXT DEFAULT 'text', file_url TEXT DEFAULT '', timestamp INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, reason TEXT, status TEXT DEFAULT 'open', timestamp INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, bot_username TEXT UNIQUE, token TEXT UNIQUE
    )''')
    
    # Владелец _fan_beluga_ (пароль 12344321)
    c.execute("INSERT OR IGNORE INTO users (username, pass_hash, display_name, role) VALUES ('_fan_beluga_', ?, 'Саша', 'owner')", (hashlib.sha256(b'12344321').hexdigest(),))
    c.execute("UPDATE users SET role='owner', pass_hash=? WHERE username='_fan_beluga_'", (hashlib.sha256(b'12344321').hexdigest(),))
    
    # Тестовые акки
    c.execute("INSERT OR IGNORE INTO users (username, pass_hash, display_name, role) VALUES ('admin', ?, 'Админ', 'admin')", (hashlib.sha256(b'admin123').hexdigest(),))
    c.execute("INSERT OR IGNORE INTO users (username, pass_hash, display_name, role) VALUES ('mod', ?, 'Модер', 'moderator')", (hashlib.sha256(b'mod123').hexdigest(),))
    conn.commit()
    conn.close()

db_init()

# --- WEBSOCKET МЕНЕДЖЕР ---
class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
    async def connect(self, user: str, ws: WebSocket):
        await ws.accept()
        self.active[user] = ws
    def disconnect(self, user: str):
        self.active.pop(user, None)
    async def send(self, user: str, data: dict):
        if user in self.active:
            try: await self.active[user].send_json(data)
            except: self.disconnect(user)
    async def broadcast(self, data: dict):
        for ws in list(self.active.values()):
            try: await ws.send_json(data)
            except: pass

manager = ConnectionManager()

# --- СХЕМЫ ---
class LoginData(BaseModel):
    username: str
    password: str

class ActionData(BaseModel):
    target: str
    value: str = ""

# --- ЗАГРУЗКА ФАЙЛОВ (до 1 ГБ, потоково) ---
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1]
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = os.path.join("uploads", fname)
    
    with open(fpath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"url": f"/uploads/{fname}", "type": "file", "name": file.filename}

# --- АВТОРИЗАЦИЯ ---
@app.post("/api/login")
async def login(data: LoginData):
    c = sqlite3.connect(DB_PATH)
    cur = c.execute("SELECT role, is_banned FROM users WHERE username=? AND pass_hash=?", 
                    (data.username, hashlib.sha256(data.password.encode()).hexdigest()))
    res = cur.fetchone(); c.close()
    if not res: raise HTTPException(401, "Неверные данные")
    if res[1]: raise HTTPException(403, "Забанен")
    return {"status": "ok", "role": res[0]}

# --- ПАНЕЛЬ МОДЕРА ---
@app.post("/api/mod/mute")
async def mod_mute(data: ActionData):
    await manager.send(data.target, {"event": "muted", "until": int(time.time()) + int(data.value)*60})
    return {"ok": True}

@app.post("/api/mod/warn")
async def mod_warn(data: ActionData):
    await manager.send(data.target, {"event": "warned"})
    return {"ok": True}

@app.post("/api/mod/kick")
async def mod_kick(data: ActionData):
    await manager.send(data.target, {"event": "kicked"})
    return {"ok": True}

# --- ПАНЕЛЬ АДМИНА ---
@app.post("/api/admin/ban")
async def admin_ban(data: ActionData):
    c = sqlite3.connect(DB_PATH)
    c.execute("UPDATE users SET is_banned=1 WHERE username=?", (data.target,))
    c.commit(); c.close()
    await manager.send(data.target, {"event": "banned"})
    return {"ok": True}

@app.post("/api/admin/unban")
async def admin_unban(data: ActionData):
    c = sqlite3.connect(DB_PATH)
    c.execute("UPDATE users SET is_banned=0 WHERE username=?", (data.target,))
    c.commit(); c.close()
    return {"ok": True}

@app.post("/api/admin/force_logout")
async def admin_force_logout(data: ActionData):
    if data.target in manager.active:
        await manager.active[data.target].close()
        manager.disconnect(data.target)
    return {"ok": True}

# --- ПАНЕЛЬ ВЛАДЕЛЬЦА ---
@app.post("/api/owner/give_coins")
async def owner_coins(data: ActionData):
    c = sqlite3.connect(DB_PATH)
    c.execute("UPDATE users SET coins = coins + ? WHERE username=?", (int(data.value), data.target))
    c.commit(); c.close()
    await manager.send(data.target, {"event": "coins_given", "amount": data.value})
    return {"ok": True}

@app.post("/api/owner/give_premium")
async def owner_premium(data: ActionData):
    days = int(data.value) * 86400
    c = sqlite3.connect(DB_PATH)
    c.execute("UPDATE users SET premium_until=? WHERE username=?", (int(time.time()) + days, data.target))
    c.commit(); c.close()
    return {"ok": True}

@app.post("/api/owner/give_scam")
async def owner_scam(data: ActionData):
    c = sqlite3.connect(DB_PATH)
    c.execute("UPDATE users SET is_scam=1 WHERE username=?", (data.target,))
    c.commit(); c.close()
    return {"ok": True}

@app.post("/api/owner/troll")
async def owner_troll(data: ActionData):
    await manager.send(data.target, {"event": data.value})
    return {"ok": True}

# --- BotFather ---
@app.post("/api/botfather/newbot")
async def newbot(data: ActionData):
    bot_name = data.target
    token = hashlib.sha256(f"{bot_name}{time.time()}".encode()).hexdigest()
    c = sqlite3.connect(DB_PATH)
    try:
        c.execute("INSERT INTO bots (bot_username, token) VALUES (?, ?)", (bot_name, token))
        c.commit()
    except:
        c.close()
        raise HTTPException(400, "Имя занято")
    c.close()
    return {"bot": bot_name, "token": token}

# --- ЧАТ И ЗВОНКИ (WEBSOCKET) ---
@app.websocket("/ws/{username}")
async def ws_endpoint(ws: WebSocket, username: str):
    await manager.connect(username, ws)
    try:
        c = sqlite3.connect(DB_PATH)
        cur = c.execute("SELECT sender, text, type, file_url, timestamp FROM messages ORDER BY id DESC LIMIT 50")
        history = [{"sender": r[0], "text": r[1], "type": r[2], "file_url": r[3], "ts": r[4]} for r in cur.fetchall()][::-1]
        c.close()
        await ws.send_json({"event": "history", "messages": history})

        while True:
            data = await ws.receive_json()
            ev = data.get("event")
            
            if ev == "message":
                msg_type = data.get("type", "text")
                text = data.get("text", "")
                file_url = data.get("file_url", "")
                
                c = sqlite3.connect(DB_PATH)
                c.execute("INSERT INTO messages (chat_id, sender, text, type, file_url, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                          (data.get("chat_id", "general"), username, text, msg_type, file_url, int(time.time())))
                c.commit(); c.close()

                await manager.broadcast({
                    "event": "new_message",
                    "sender": username,
                    "text": text,
                    "type": msg_type,
                    "file_url": file_url,
                    "ts": int(time.time())
                })
            
            # WebRTC Сигналинг (Звонки)
            elif ev in ["call_offer", "call_answer", "call_ice", "call_end"]:
                target = data.get("target")
                data["sender"] = username
                await manager.send(target, data)
                
    except WebSocketDisconnect:
        manager.disconnect(username)

# --- ОТДАЧА ФРОНТЕНДА ---
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# --- АВТО-ЗАПУСК UVICORN ---
if __name__ == "__main__":
    print("=== BelugaCord Server Started ===")
    print("URL: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")