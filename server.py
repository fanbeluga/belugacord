# BELUGACORD 2.5 — server.py
import os, asyncio, datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Создаём папки ДО любых импортов api
for d in ["uploads", "styles", "js", "features", "api"]:
    os.makedirs(d, exist_ok=True)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Статика
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/styles", StaticFiles(directory="styles"), name="styles")
app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/features", StaticFiles(directory="features"), name="features")

# Импорты api
from api._shared import (
    manager, init_db, startup_tasks, get_pool, online_users,
    get_current_user, handle_ws_message
)

# Роуты
from api import core, chat, gifts, economy, admin, games, calls

app.include_router(core.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(gifts.router, prefix="/api")
app.include_router(economy.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(games.router, prefix="/api")
app.include_router(calls.router, prefix="/api")

@app.get("/manifest.json")
async def manifest():
    return {
        "name": "Belugacord 2.5",
        "short_name": "Belugacord",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0a0a12",
        "theme_color": "#0a0a12",
        "icons": [{"src": "/uploads/icon.png", "sizes": "192x192", "type": "image/png"}]
    }

@app.get("/fanchipromo")
async def fanchipromo_landing():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/")
async def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str):
    user = await get_current_user(token)
    if not user:
        await ws.close()
        return
    if user.get("is_banned"):
        await ws.close()
        return
    uid = user["id"]
    await manager.connect(uid, ws)
    try:
        await ws.send_json({"type": "online_list", "users": list(online_users)})
    except:
        pass
    await manager.broadcast({"type": "user_online", "user_id": uid}, exclude=uid)

    try:
        while True:
            raw = await ws.receive_text()
            await handle_ws_message(uid, user, raw)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS error: {e}")
    finally:
        manager.disconnect(uid, ws)
        try:
            p = await get_pool()
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET last_seen=NOW() WHERE id=$1", uid)
        except:
            pass
        await manager.broadcast({"type": "user_offline", "user_id": uid})

@app.on_event("startup")
async def startup():
    if os.environ.get("DATABASE_URL"):
        try:
            await init_db()
            await startup_tasks()
        except Exception as e:
            print(f"DB init error: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, ws="websockets",
                proxy_headers=True, forwarded_allow_ips="*")