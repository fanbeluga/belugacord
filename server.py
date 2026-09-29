import os
import secrets
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json

# === НАСТРОЙКИ ===
SECRET_KEY = os.environ.get("SECRET_KEY", "fallback_secret_key_for_local_dev")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "fallback_admin_pass")

app = FastAPI(title="Belugacord 2.5 API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика
app.mount("/css", StaticFiles(directory="css", check_dir=False), name="css")
app.mount("/js", StaticFiles(directory="js", check_dir=False), name="js")
app.mount("/uploads", StaticFiles(directory="uploads", check_dir=False), name="uploads")

# === ИМИТАЦИЯ БД (в памяти) ===
db_users = {}
db_codes = {}
active_websockets = {}

# === ГЛАВНАЯ СТРАНИЦА ===
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("index.html")

# === АВТОРИЗАЦИЯ ===

@app.post("/api/auth/register")
async def register(data: dict):
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or len(username) < 3 or len(username) > 32:
        raise HTTPException(status_code=400, detail="Ник должен быть 3-32 символа")
    
    if username in db_users:
        raise HTTPException(status_code=400, detail="Никнейм занят")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль минимум 6 символов")

    # Генерируем 6-значный код
    code = str(secrets.randbelow(900000) + 100000)
    db_codes[username] = {
        "code": code,
        "email": email,
        "password": password
    }
    
    # Пока выводим в консоль (потом подключим Resend API)
    print(f"\n📧 EMAIL CODE for {username}: {code}\n")
    
    return {"message": "Код отправлен на почту"}


@app.post("/api/auth/verify_email")
async def verify_email(data: dict):
    username = data.get("username", "").strip()
    code = data.get("code", "").strip()

    if username not in db_codes:
        raise HTTPException(status_code=400, detail="Пользователь не найден")
    
    if db_codes[username]["code"] != code:
        raise HTTPException(status_code=400, detail="Неверный код")
    
    # Переносим в базу
    user_data = db_codes.pop(username)
    db_users[username] = {
        "username": username,
        "email": user_data["email"],
        "password": user_data["password"],
        "coins": 0,
        "level": 1,
        "xp": 0,
        "is_admin": (username == "_fan_beluga_"),
        "avatar": "",
        "banner": "",
        "bio": "",
        "status": ""
    }
    
    return {"message": "Почта подтверждена!"}


@app.post("/api/auth/resend_code")
async def resend_code(data: dict):
    username = data.get("username", "").strip()
    
    if username not in db_codes:
        raise HTTPException(status_code=404, detail="Код не запрашивался")
    
    code = str(secrets.randbelow(900000) + 100000)
    db_codes[username]["code"] = code
    print(f"\n📧 RESEND CODE for {username}: {code}\n")
    
    return {"message": "Код отправлен снова"}


@app.post("/api/auth/login")
async def login(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = db_users.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Неверный ник или пароль")
    
    token = secrets.token_hex(32)
    user["token"] = token
    
    return {"token": token, "username": username}


@app.get("/api/me")
async def get_me(token: str):
    for user in db_users.values():
        if user.get("token") == token:
            return user
    raise HTTPException(status_code=401, detail="Неверный токен")


# === WEBSOCKET (ЧАТ) ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await websocket.accept()
    username = None
    
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
            
            # Рассылаем всем
            for u, ws in active_websockets.items():
                await ws.send_json({
                    "type": "message",
                    "user": username,
                    "text": data.get("text", ""),
                    "time": __import__('datetime').datetime.now().isoformat()
                })
    except WebSocketDisconnect:
        if username in active_websockets:
            del active_websockets[username]
            print(f" {username} отключился")


# === ЗАПУСК ===
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)