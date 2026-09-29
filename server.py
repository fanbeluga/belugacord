import os
import secrets
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# === БЕЗОПАСНОСТЬ (Берем из переменных окружения Render) ===
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback_secret_key_for_local_dev")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "fallback_admin_pass")

app = FastAPI(title="Belugacord 2.5 API")

# Разрешаем запросы с любого домена (для разработки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === ИМИТАЦИЯ БАЗЫ ДАННЫХ (В памяти) ===
# В продакшене тут должен быть asyncpg (PostgreSQL)
db_users = {} 
db_codes = {} # {username: "123456"}
active_websockets = {}

# === МОДЕЛИ (Pydantic) ===
class RegisterReq(BaseModel):
    username: str
    email: str
    password: str

class VerifyReq(BaseModel):
    username: str
    code: str

class LoginReq(BaseModel):
    username: str
    password: str

# === АВТОРИЗАЦИЯ И EMAIL ===

@app.post("/api/auth/register")
async def register(req: RegisterReq):
    if req.username in db_users:
        raise HTTPException(status_code=400, detail="Никнейм занят")
    
    # Генерируем 6-значный код
    code = str(secrets.randbelow(900000) + 100000)
    db_codes[req.username] = {
        "code": code,
        "email": req.email,
        "password": req.password # В реальном проекте пароль нужно хешировать через bcrypt!
    }
    
    # ТУТ ДОЛЖНА БЫТЬ ОТПРАВКА НА ПОЧТУ (например, через Resend API)
    # Пока просто выводим в консоль сервера, чтобы ты мог протестировать
    print(f"\n📧 EMAIL CODE for {req.username}: {code}\n")
    
    return {"message": "Код отправлен на почту (смотри консоль сервера)"}

@app.post("/api/auth/verify_email")
async def verify_email(req: VerifyReq):
    if req.username not in db_codes:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
        
    if db_codes[req.username]["code"] != req.code:
        raise HTTPException(status_code=400, detail="Неверный код")
        
    # Переносим в базу пользователей
    data = db_codes.pop(req.username)
    db_users[req.username] = {
        "username": req.username,
        "email": data["email"],
        "password": data["password"],
        "coins": 0,
        "level": 1,
        "is_admin": (req.username == "_fan_beluga_")
    }
    
    return {"message": "Почта подтверждена!"}

@app.post("/api/auth/resend_code")
async def resend_code(req: dict):
    username = req.get("username")
    if username in db_codes:
        code = str(secrets.randbelow(900000) + 100000)
        db_codes[username]["code"] = code
        print(f"\n📧 RESEND CODE for {username}: {code}\n")
        return {"message": "Код отправлен снова"}
    raise HTTPException(status_code=404, detail="Код не запрашивался")

@app.post("/api/auth/login")
async def login(req: LoginReq):
    user = db_users.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Неверный ник или пароль")
        
    # Генерируем простой токен (в идеале использовать JWT)
    token = secrets.token_hex(32)
    user["token"] = token
    return {"token": token, "username": req.username}

@app.get("/api/me")
async def get_me(token: str):
    for user in db_users.values():
        if user.get("token") == token:
            return user
    raise HTTPException(status_code=401, detail="Неверный токен")

# === WEBSOCKET (ЧАТ В РЕАЛЬНОМ ВРЕМЕНИ) ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await websocket.accept()
    username = None
    
    # Ищем юзера по токену
    for user in db_users.values():
        if user.get("token") == token:
            username = user["username"]
            break
            
    if not username:
        await websocket.close(code=4001)
        return

    active_websockets[username] = websocket
    print(f"✅ {username} подключился к WebSocket")

    try:
        while True:
            data = await websocket.receive_json()
            # Эхо-тест: отправляем сообщение всем (упрощенно)
            for u, ws in active_websockets.items():
                if u != username:
                    await ws.send_json({
                        "type": "message",
                        "user": username,
                        "text": data.get("text", "")
                    })
    except WebSocketDisconnect:
        del active_websockets[username]
        print(f"❌ {username} отключился")

# === ЗАПУСК ===
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)