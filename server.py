import os
import json
import time
import secrets
import hashlib
import random
import datetime
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ===== КОНФИГУРАЦИЯ =====
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Belugacord 2.5 API")

# Разрешаем все запросы (для разработки и Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы (аватарки, баннеры)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ===== IN-MEMORY БАЗА ДАННЫХ (Для мгновенного запуска на Render без ошибок БД) =====
db_users = {}       # {username: {id, password_hash, token, coins, level, is_admin, avatar, banner, bio, status}}
db_codes = {}       # {username: {code, email, password_hash}} (для верификации)
db_servers = {}     # {id: {name, owner_id, channels: [{id, name, type}], members: [user_ids]}}
db_friends = {}     # {user_id: {friends: [user_ids], requests: [user_ids]}}
db_messages = {}    # {channel_id_or_dm_key: [{author, text, time}]}
active_websockets = {} # {username: WebSocket}

# ===== ХЕЛПЕРЫ =====
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def make_token(username: str) -> str:
    return f"{username}:{int(time.time())}:{secrets.token_hex(16)}"

async def get_current_user(token: str):
    if not token:
        return None
    for user in db_users.values():
        if user.get("token") == token:
            return user
    return None

# ===== 1. АВТОРИЗАЦИЯ И ВЕРИФИКАЦИЯ =====
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
    if u in db_users or u in db_codes:
        raise HTTPException(400, "Этот никнейм уже занят")

    # Генерируем 6-значный код
    code = str(random.randint(100000, 999999))
    db_codes[u] = {
        "code": code,
        "email": em or f"{u}@belugacord.local",
        "password_hash": hash_password(pw)
    }
    
    # ВАЖНО: Код выводится прямо в логи Render, чтобы ты мог его скопировать!
    print(f"\n📧 [BELUGACORD VERIFY] Код для {u}: {code}\n")
    
    return {"message": "Код отправлен (смотри логи сервера в Render)"}

@app.post("/api/verify_email")
async def verify_email(data: dict):
    u = (data.get("username") or "").strip()
    code = (data.get("code") or "").strip()

    if u not in db_codes:
        raise HTTPException(400, "Пользователь не найден или код истёк")
    
    if db_codes[u]["code"] != code:
        raise HTTPException(400, "Неверный код подтверждения")
    
    # Переносим в основную базу
    user_data = db_codes.pop(u)
    new_id = len(db_users) + 1
    db_users[u] = {
        "id": new_id,
        "username": u,
        "email": user_data["email"],
        "password_hash": user_data["password_hash"],
        "coins": 0,
        "level": 1,
        "is_admin": (u == "_fan_beluga_"), # Ты автоматически админ
        "avatar": "",
        "banner": "",
        "bio": "Привет! Я использую Belugacord 🐱",
        "status": "online"
    }
    db_friends[new_id] = {"friends": [], "requests": []}
    
    token = make_token(u)
    db_users[u]["token"] = token
    
    return {"token": token, "user": {"username": u, "id": new_id, "level": 1, "coins": 0}}

@app.post("/api/login")
async def login(data: dict):
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    
    user = db_users.get(u)
    if not user or user["password_hash"] != hash_password(pw):
        raise HTTPException(401, "Неверный никнейм или пароль")
    
    token = make_token(u)
    user["token"] = token
    user["status"] = "online"
    
    return {"token": token, "user": {"username": u, "id": user["id"], "level": user["level"], "coins": user["coins"], "avatar": user["avatar"]}}

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
        "status": user["status"]
    }

# ===== 2. ПРОФИЛЬ =====
@app.post("/api/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    user["avatar"] = data.get("avatar", user["avatar"])
    user["banner"] = data.get("banner", user["banner"])
    user["bio"] = data.get("bio", user["bio"])
    user["status"] = data.get("status", user["status"])
    
    return {"ok": True}

# ===== 3. СЕРВЕРА И КАНАЛЫ =====
@app.post("/api/servers/create")
async def create_server(data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    name = (data.get("name") or "Новый сервер").strip()
    server_id = len(db_servers) + 1
    
    db_servers[server_id] = {
        "id": server_id,
        "name": name,
        "owner_id": user["id"],
        "channels": [{"id": 1, "name": "общий", "type": "text"}],
        "members": [user["id"]]
    }
    
    return {"id": server_id, "name": name}

@app.get("/api/servers/list")
async def list_servers(token: str):
    user = await get_current_user(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    # Возвращаем серверы, где пользователь является участником
    my_servers = [s for s in db_servers.values() if user["id"] in s["members"]]
    return my_servers

@app.post("/api/servers/{server_id}/channels")
async def create_channel(server_id: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    server = db_servers.get(server_id)
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Только владелец может создавать каналы")
    
    new_channel = {
        "id": len(server["channels"]) + 1,
        "name": data.get("name", "новый-канал"),
        "type": data.get("type", "text")
    }
    server["channels"].append(new_channel)
    return {"ok": True, "channel": new_channel}

@app.post("/api/servers/delete")
async def delete_server(data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    server_id = data.get("server_id")
    server = db_servers.get(server_id)
    
    if not server or server["owner_id"] != user["id"]:
        raise HTTPException(403, "Только владелец может удалить сервер")
    
    del db_servers[server_id]
    return {"ok": True}

# ===== 4. ДРУЗЬЯ =====
@app.get("/api/friends/list")
async def get_friends(token: str):
    user = await get_current_user(token)
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    f_data = db_friends.get(user["id"], {"friends": [], "requests": []})
    
    friends_list = []
    for fid in f_data["friends"]:
        for u in db_users.values():
            if u["id"] == fid:
                friends_list.append({"id": u["id"], "username": u["username"], "status": u["status"]})
                
    requests_list = []
    for rid in f_data["requests"]:
        for u in db_users.values():
            if u["id"] == rid:
                requests_list.append({"id": u["id"], "username": u["username"]})
                
    return {"friends": friends_list, "requests": requests_list}

@app.post("/api/friends/request")
async def send_friend_request(data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    target_username = data.get("username")
    target_user = db_users.get(target_username)
    if not target_user or target_user["id"] == user["id"]:
        raise HTTPException(400, "Пользователь не найден")
    
    target_f_data = db_friends.setdefault(target_user["id"], {"friends": [], "requests": []})
    if user["id"] not in target_f_data["requests"]:
        target_f_data["requests"].append(user["id"])
        
    return {"ok": True}

@app.post("/api/friends/accept")
async def accept_friend(data: dict):
    user = await get_current_user(data.get("token"))
    if not user:
        raise HTTPException(401, "Не авторизован")
    
    requester_id = data.get("user_id")
    f_data = db_friends.setdefault(user["id"], {"friends": [], "requests": []})
    
    if requester_id in f_data["requests"]:
        f_data["requests"].remove(requester_id)
        f_data["friends"].append(requester_id)
        
        # Добавляем себя в друзья к запрашивающему
        req_f_data = db_friends.setdefault(requester_id, {"friends": [], "requests": []})
        req_f_data["friends"].append(user["id"])
        
    return {"ok": True}

# ===== 5. БОГ-АДМИНКА =====
@app.get("/api/admin/users")
async def admin_get_users(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Доступ запрещён. Только для Бога.")
    
    return [{"id": u["id"], "username": u["username"], "coins": u["coins"], "level": u["level"], "is_admin": u["is_admin"]} for u in db_users.values()]

@app.post("/api/admin/action")
async def admin_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Доступ запрещён.")
    
    action = data.get("action")
    target_id = data.get("user_id")
    
    for u in db_users.values():
        if u["id"] == target_id:
            if action == "ban":
                u["is_banned"] = True
            elif action == "coins":
                u["coins"] = u.get("coins", 0) + int(data.get("amount", 1000))
            elif action == "admin":
                u["is_admin"] = not u.get("is_admin", False)
            return {"ok": True, "message": f"Действие {action} выполнено"}
    
    raise HTTPException(404, "Пользователь не найден")

# ===== 6. WEBSOCKET (ЧАТ В РЕАЛЬНОМ ВРЕМЕНИ) =====
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

# ===== 7. ГЛАВНАЯ СТРАНИЦА И ВЕРСИЯ =====
@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return JSONResponse({"error": "index.html not found. Deploy it to GitHub first."}, status_code=404)

@app.get("/api/version")
async def version():
    return {
        "current": "2.5.0",
        "all": {
            "2.5.0": {"title": "Belugacord Beta 2.5", "items": ["🚀 Полный релиз", "📧 Email верификация", "📞 Звонки", "👑 БОГ-Админка", "🎮 Игры"]}
        }
    }

# ===== ЗАПУСК =====
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)