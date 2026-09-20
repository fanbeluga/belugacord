from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os

app = FastAPI()
clients = []

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            for c in clients:
                await c.send_text(msg)
    except WebSocketDisconnect:
        clients.remove(websocket)

@app.get("/")
async def get():
    return HTMLResponse(open("index.html", encoding="utf-8").read())

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)