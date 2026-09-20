# belugacord
A lightweight web messenger for friends. No registration, no ads, no tracking.

## Features
- Real-time text chat via WebSocket
- Works in any modern browser
- PWA-ready: install as app on phone or desktop
- Simple deployment: works on Render, Railway, Koyeb
- 100% free and open-source

## Tech Stack
- Backend: Python (FastAPI + WebSocket)
- Frontend: HTML + JavaScript (no frameworks)

## How to Use
1. Deploy the server (Render / Railway / Koyeb)
2. Share the link with friends
3. Open in browser, start chatting

## Self-Host
```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000