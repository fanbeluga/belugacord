from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel
import random, string, uuid, time, json

# ==================== НАСТРОЙКИ ====================
# ВСТАВЬ СВОЙ ПАРОЛЬ ОТ POSTGRES ЗДЕСЬ!
DATABASE_URL = "postgresql://postgres:твой_пароль@localhost:5432/belugacord"

# ==================== БАЗА ДАННЫХ ====================
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    balance = Column(Integer, default=1000)
    role = Column(String, default="user")
    token = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text)
    timestamp = Column(Integer)

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    username = Column(String, unique=True, index=True)
    name = Column(String)
    api_token = Column(String, unique=True, index=True)

Base.metadata.create_all(bind=engine)

# ==================== БЕЗОПАСНОСТЬ ====================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def get_password_hash(password): return pwd_context.hash(password)
def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ==================== FASTAPI ====================
app = FastAPI(title="BelugaCord API + WebRTC")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# === WEBSOCKET МЕНЕДЖЕР (ЗВОНКИ) ===
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

manager = ConnectionManager()

# === МОДЕЛИ ЗАПРОСОВ ===
class UserAuth(BaseModel):
    username: str
    password: str

class MessageSend(BaseModel):
    sender_id: int
    receiver_id: int
    text: str

class BotCreate(BaseModel):
    owner_id: int
    name: str
    username: str

# ==================== ЭНДПОИНТЫ ====================

# 1. АВТОРИЗАЦИЯ
@app.post("/api/register")
def register(user: UserAuth, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first(): raise HTTPException(400, "Логин занят")
    new_user = User(username=user.username, password_hash=get_password_hash(user.password))
    db.add(new_user); db.commit(); db.refresh(new_user)
    return {"status": "ok", "user_id": new_user.id, "username": new_user.username}

@app.post("/api/login")
def login(user: UserAuth, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.password_hash): raise HTTPException(401, "Неверный логин/пароль")
    return {"status": "ok", "user_id": db_user.id, "username": db_user.username, "balance": db_user.balance}

# 2. СООБЩЕНИЯ
@app.post("/api/messages/send")
def send_message(msg: MessageSend, db: Session = Depends(get_db)):
    new_msg = Message(sender_id=msg.sender_id, receiver_id=msg.receiver_id, text=msg.text, timestamp=int(time.time()))
    db.add(new_msg); db.commit()
    return {"status": "ok"}

@app.get("/api/messages/{u1}/{u2}")
def get_messages(u1: int, u2: int, db: Session = Depends(get_db)):
    msgs = db.query(Message).filter(((Message.sender_id == u1) & (Message.receiver_id == u2)) | ((Message.sender_id == u2) & (Message.receiver_id == u1))).order_by(Message.timestamp).all()
    return [{"sender_id": m.sender_id, "text": m.text, "timestamp": m.timestamp} for m in msgs]

# 3. БОТЫ
@app.post("/api/bots/create")
def create_bot(bot: BotCreate, db: Session = Depends(get_db)):
    if not bot.username.endswith("bot"): raise HTTPException(400, "Юзернейм должен заканчиваться на 'bot'")
    if db.query(Bot).filter(Bot.username == bot.username).first(): raise HTTPException(400, "Юзернейм занят")
    raw_token = f"{random.randint(100000000, 999999999)}:{''.join(random.choices(string.ascii_letters + string.digits + '_-', k=35))}"
    new_bot = Bot(owner_id=bot.owner_id, username=bot.username, name=bot.name, api_token=raw_token)
    db.add(new_bot); db.commit()
    return {"status": "ok", "api_url": f"https://belugacord.com/bot/{bot.username}?token={raw_token}", "token": raw_token}

@app.get("/bot/{bot_username}")
def bot_api(bot_username: str, token: str = None, db: Session = Depends(get_db)):
    if not token: raise HTTPException(401, "Токен не передан")
    bot = db.query(Bot).filter(Bot.username == bot_username).first()
    if not bot or bot.api_token != token: raise HTTPException(403, "Неверный токен")
    return {"status": "ok", "bot_name": bot.name, "message": "Авторизация успешна"}

# 4. ЗВОНКИ (WebSocket)
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            target_id = message.get("target_id")
            if target_id:
                await manager.send_personal_message(json.dumps({
                    "from_id": user_id,
                    "type": message.get("type"), 
                    "data": message.get("data")
                }), target_id)
    except WebSocketDisconnect:
        manager.disconnect(user_id)

# 5. КОНФИГ TURN (ТВОИ ДАННЫЕ УЖЕ ВПИСАНЫ)
@app.get("/api/turn_config")
def get_turn_config():
    return {
        "iceServers": [
            {"urls": "stun:stun.l.google.com:19302"},
            {
                "urls": "turn:189.74.125.21:3478",
                "username": "beluga",
                "credential": "1VSALM1cow"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)