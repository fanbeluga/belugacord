import os
import json
import time
import secrets
import hashlib
import random
import datetime
import asyncio
from typing import Optional
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ===== КОНФИГУРАЦИЯ =====
DATABASE_URL = os.environ.get("DATABASE_URL", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Belugacord 2.5 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика
for d in ["uploads", "css", "js"]:
    os.makedirs(d, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/css", StaticFiles(directory="css", check_dir=False), name="css")
app.mount("/js", StaticFiles(directory="js", check_dir=False), name="js")

# ===== IN-MEMORY БД (Для быстрого старта без PostgreSQL) =====
# Если DATABASE_URL есть, можно переключить на asyncpg, но для тестов и Render Free это идеальный вариант
db_users = {}
db_codes = {}  # {username: {"code": "123456", "password": "...", "email": "..."}}
active_websockets = {}

# ===== ХЕЛПЕРЫ =====
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def make_token(user_id: int, username: str) -> str:
    return f"{user_id}:{username}:{int(time.time())}:{secrets.token_hex(8)}"

async def get_current_user(token: str):
    if not token:
        return None
    for user in db_users.values():
        if user.get("token") == token:
            return user
    return None

# ===== ЭНДПОИНТЫ: АВТОРИЗАЦИЯ =====
@app.get("/api/check_username")
async def check_username(username: str):
    return {"available": username not in db_users}

@app.post("/api/register")
async def register(data: dict):
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    em = (data.get("email") or "").strip()

    if len(u) < 3 or len(u) > 32:
        raise HTTPException(400, "Ник должен быть 3-32 символа")
    if len(pw) < 6:
        raise HTTPException(400, "Пароль минимум 6 символов")
    if u in db_users:
        raise HTTPException(400, "Этот никнейм уже занят")

    # Генерируем 6-значный код
    code = str(random.randint(100000, 999999))
    db_codes[u] = {
        "code": code,
        "email": em or f"{u}@belugacord.local",
        "password": hash_password(pw)
    }
    
    # Выводим код в консоль (в логах Render)
    print(f"\n📧 [EMAIL VERIFY] Код для {u}: {code}\n")
    
    return {"message": "Код отправлен (смотри логи сервера)"}

@app.post("/api/verify_email")
async def verify_email(data: dict):
    u = (data.get("username") or "").strip()
    code = (data.get("code") or "").strip()

    if u not in db_codes:
        raise HTTPException(400, "Пользователь не найден или код истёк")
    
    if db_codes[u]["code"] != code:
        raise HTTPException(400, "Неверный код подтверждения")
    
    # Переносим в основную БД
    user_data = db_codes.pop(u)
    new_id = len(db_users) + 1
    db_users[u] = {
        "id": new_id,
        "username": u,
        "email": user_data["email"],
        "password_hash": user_data["password"],
        "coins": 0,
        "level": 1,
        "xp": 0,
        "is_admin": (u == "_fan_beluga_"),
        "avatar": "",
        "banner": "",
        "bio": "",
        "custom_status": "В сети"
    }
    
    token = make_token(new_id, u)
    db_users[u]["token"] = token
    
    return {"token": token, "user": {"username": u, "id": new_id}}

@app.post("/api/login")
async def login(data: dict):
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    
    user = db_users.get(u)
    if not user or user["password_hash"] != hash_password(pw):
        raise HTTPException(401, "Неверный никнейм или пароль")
    
    token = make_token(user["id"], u)
    user["token"] = token
    
    return {"token": token, "user": {"username": u, "id": user["id"], "level": user["level"], "coins": user["coins"]}}

@app.get("/api/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    return {
        "id": user["id"],
        "username": user["username"],
        "level": user["level"],
        "coins": user["coins"],
        "is_admin": user["is_admin"],
        "avatar": user["avatar"],
        "banner": user["banner"],
        "bio": user["bio"],
        "custom_status": user["custom_status"]
    }

# ===== ЭНДПОИНТЫ: ПРОФИЛЬ =====
@app.post("/api/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    user["avatar"] = data.get("avatar", user["avatar"])
    user["banner"] = data.get("banner", user["banner"])
    user["bio"] = data.get("bio", user["bio"])
    user["custom_status"] = data.get("custom_status", user["custom_status"])
    
    return {"ok": True}

# ===== ЭНДПОИНТЫ: АДМИНКА (БОГ-ГУИ) =====
@app.get("/api/admin/users")
async def admin_get_users(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Доступ запрещён")
    
    return [{"id": u["id"], "username": u["username"], "coins": u["coins"], "level": u["level"], "is_admin": u["is_admin"]} for u in db_users.values()]

@app.post("/api/admin/action")
async def admin_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Доступ запрещён")
    
    action = data.get("action")
    target_id = data.get("user_id")
    
    for u in db_users.values():
        if u["id"] == target_id:
            if action == "ban":
                u["is_banned"] = True
            elif action == "coins":
                u["coins"] = u.get("coins", 0) + int(data.get("amount", 0))
            elif action == "admin":
                u["is_admin"] = not u.get("is_admin", False)
            return {"ok": True}
    
    raise HTTPException(404, "Пользователь не найден")

# ===== WEBSOCKET =====
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket
        print(f"✅ {username} подключился к WebSocket")

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
            print(f"❌ {username} отключился")

    async def broadcast(self, message: dict, exclude: str = None):
        for username, ws in list(self.active_connections.items()):
            if username != exclude:
                try:
                    await ws.send_json(message)
                except:
                    self.disconnect(username)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    user = await get_current_user(token)
    if not user:
        await websocket.close(code=4001)
        return

    await manager.connect(user["username"], websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Эхо для чата
            if data.get("type") == "message":
                msg_payload = {
                    "type": "message",
                    "author": user["username"],
                    "text": data.get("text", ""),
                    "time": datetime.datetime.now().isoformat(),
                    "channel": data.get("channel", "general")
                }
                await manager.broadcast(msg_payload)
                
    except WebSocketDisconnect:
        manager.disconnect(user["username"])

# ===== ГЛАВНАЯ СТРАНИЦА =====
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/version")
async def version():
    return {"current": "2.5", "all": {"2.5": {"title": "Belugacord Beta 2.5", "items": ["🚀 Полный релиз", "📧 Email верификация", "📞 Звонки", "👑 БОГ-Админка"]}}}

# ===== ЗАПУСК =====
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)