import os, secrets, time, random, string, hashlib, json
from pathlib import Path
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/belugacord")
UP_DIR = Path("uploads"); UP_DIR.mkdir(exist_ok=True)
MB = 1024 * 1024
MAX_FREE, MAX_PREM, MAX_OWNER = 100 * MB, 1024 * MB, 20 * 1024 * MB

app = FastAPI()
pool: asyncpg.Pool = None
live: dict[int, set[WebSocket]] = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, pw_hash TEXT NOT NULL, token TEXT UNIQUE, becoins INT DEFAULT 0, premium_until BIGINT DEFAULT 0, role TEXT DEFAULT 'user', bio TEXT DEFAULT '', created_at BIGINT, banned BOOLEAN DEFAULT false, avatar TEXT);
CREATE TABLE IF NOT EXISTS usernames(uname TEXT PRIMARY KEY, owner_id INT REFERENCES users(id), is_primary BOOLEAN DEFAULT false, for_sale_price INT, acquired_at BIGINT);
CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY, frm INT, to_ INT, kind TEXT DEFAULT 'text', text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT, ts BIGINT, pinned BOOLEAN DEFAULT false, reactions JSONB DEFAULT '{}');
CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY, uname TEXT UNIQUE NOT NULL, title TEXT NOT NULL, bio TEXT DEFAULT '', owner_id INT REFERENCES users(id), avatar TEXT, created_at BIGINT);
CREATE TABLE IF NOT EXISTS channel_subs(channel_id INT REFERENCES channels(id), user_id INT REFERENCES users(id), PRIMARY KEY(channel_id, user_id));
CREATE TABLE IF NOT EXISTS channel_posts(id SERIAL PRIMARY KEY, channel_id INT REFERENCES channels(id), text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT, kind TEXT DEFAULT 'text', pinned BOOLEAN DEFAULT false, ts BIGINT);
CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY, name TEXT NOT NULL, bio TEXT DEFAULT '', owner_id INT REFERENCES users(id), avatar TEXT, created_at BIGINT);
CREATE TABLE IF NOT EXISTS group_members(group_id INT REFERENCES groups(id), user_id INT REFERENCES users(id), role TEXT DEFAULT 'member', PRIMARY KEY(group_id, user_id));
CREATE TABLE IF NOT EXISTS group_msgs(id SERIAL PRIMARY KEY, group_id INT REFERENCES groups(id), frm INT REFERENCES users(id), text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT, kind TEXT DEFAULT 'text', pinned BOOLEAN DEFAULT false, ts BIGINT);
CREATE TABLE IF NOT EXISTS bots(id SERIAL PRIMARY KEY, owner_id INT, bot_username TEXT UNIQUE, name TEXT, api_token TEXT UNIQUE, created_at BIGINT);
CREATE TABLE IF NOT EXISTS promo_codes(code TEXT PRIMARY KEY, kind TEXT, amount INT, uses_left INT);
CREATE TABLE IF NOT EXISTS promo_redemptions(code TEXT REFERENCES promo_codes(code), user_id INT REFERENCES users(id), PRIMARY KEY(code, user_id));
"""

def now(): return int(time.time())
def tok(): return secrets.token_hex(20)
def hsh(p): return hashlib.sha256(p.encode()).hexdigest()

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as con:
        for s in SCHEMA.split(";"):
            if s.strip(): await con.execute(s)
        await con.execute("UPDATE users SET name = username WHERE name = '' OR name IS NULL")

@app.on_event("startup")
async def startup(): await init_db()

async def auth(authorization: str = Header(None), x_token: str = Header(None)):
    t = x_token or (authorization.split(" ")[-1] if authorization else None)
    if not t: raise HTTPException(401, "Нужен вход")
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", t)
    if not u: raise HTTPException(401, "Нужен вход")
    if u["banned"]: raise HTTPException(403, "Забанен")
    return u

async def push(uids, payload):
    for uid in set(uids):
        for ws in list(live.get(uid, [])):
            try: await ws.send_json(payload)
            except Exception: live[uid].discard(ws)

class RegIn(BaseModel): username: str; name: str; password: str
class LogIn(BaseModel): username: str; password: str
class MsgIn(BaseModel): to: int; text: str
class ChanIn(BaseModel): uname: str; title: str; bio: str = ""
class GroupIn(BaseModel): name: str; bio: str = ""
class PostIn(BaseModel): text: str
class EditMsgIn(BaseModel): text: str

@app.post("/api/register")
async def register(b: RegIn):
    u = b.username.strip().lower()
    if not (5 <= len(u) <= 32): raise HTTPException(400, "Юз от 5 символов")
    async with pool.acquire() as con, con.transaction():
        if await con.fetchval("SELECT 1 FROM usernames WHERE uname=$1", u): raise HTTPException(400, "Занят")
        t = tok()
        uid = await con.fetchval("INSERT INTO users(username,name,pw_hash,token,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", u, b.name[:40] or u, hsh(b.password), t, now())
        await con.execute("INSERT INTO usernames(uname,owner_id,is_primary,acquired_at) VALUES($1,$2,true,$3)", u, uid, now())
    return {"token": t}

@app.post("/api/login")
async def login(b: LogIn):
    u = b.username.strip().lower().lstrip("@")
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT owner_id FROM usernames WHERE uname=$1", u)
        if not row: raise HTTPException(403, "Нет аккаунта")
        acc = await con.fetchrow("SELECT * FROM users WHERE id=$1", row["owner_id"])
        if acc["banned"]: raise HTTPException(403, "Забанен")
        if hsh(b.password) != acc["pw_hash"]: raise HTTPException(403, "Неверный пароль")
        t = tok()
        await con.execute("UPDATE users SET token=$1 WHERE id=$2", t, acc["id"])
    return {"token": t}

@app.get("/api/me")
async def me(u=Depends(auth)):
    async with pool.acquire() as con:
        return dict(id=u["id"], username=u["username"], name=u["name"], role=u["role"], becoins=u["becoins"], bio=u["bio"], avatar=u["avatar"])

@app.post("/api/me/edit")
async def edit_me(b: EditMsgIn, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET name=$1 WHERE id=$2", b.text[:40], u["id"])
    return {"ok": True}

@app.get("/api/chats")
async def get_chats(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("""
            SELECT DISTINCT u.id, u.username, u.name, u.avatar,
            (SELECT text FROM messages WHERE (frm=$1 AND to_=u.id) OR (frm=u.id AND to_=$1) ORDER BY id DESC LIMIT 1) as last_msg,
            (SELECT ts FROM messages WHERE (frm=$1 AND to_=u.id) OR (frm=u.id AND to_=$1) ORDER BY id DESC LIMIT 1) as last_ts
            FROM users u
            WHERE u.id IN (SELECT to_ FROM messages WHERE frm=$1 UNION SELECT frm FROM messages WHERE to_=$1)
            AND u.id != $1 ORDER BY last_ts DESC
        """, u["id"])
    return [dict(r) for r in rows]

@app.get("/api/chat/{peer_id}")
async def chat(peer_id: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM messages WHERE (frm=$1 AND to_=$2) OR (frm=$2 AND to_=$1) ORDER BY id", u["id"], peer_id)
    return [dict(r) for r in rows]

@app.post("/api/dm/send")
async def dm_send(b: MsgIn, u=Depends(auth)):
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO messages(frm,to_,kind,text,ts) VALUES($1,$2,'text',$3,$4) RETURNING id", u["id"], b.to, b.text[:4000], now())
    msg = dict(id=mid, frm=u["id"], to=b.to, kind="text", text=b.text[:4000], ts=now())
    await push([u["id"], b.to], {"type": "msg", "msg": msg})
    return {"ok": True}

@app.post("/api/dm/edit/{mid}")
async def dm_edit(mid: int, b: EditMsgIn, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE messages SET text=$1 WHERE id=$2 AND frm=$3", b.text[:4000], mid, u["id"])
    return {"ok": True}

@app.post("/api/dm/del/{mid}")
async def dm_del(mid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM messages WHERE id=$1 AND frm=$2", mid, u["id"])
    return {"ok": True}

@app.post("/api/pin_dm/{mid}")
async def pin_dm(mid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE messages SET pinned = NOT pinned WHERE id=$1 AND (frm=$2 OR to_=$2)", mid, u["id"])
    return {"ok": True}

@app.post("/api/react/{mid}")
async def react(mid: int, emoji: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT reactions FROM messages WHERE id=$1", mid)
        rx = row["reactions"] or {}
        if emoji not in rx: rx[emoji] = []
        if u["id"] in rx[emoji]: rx[emoji].remove(u["id"])
        else: rx[emoji].append(u["id"])
        await con.execute("UPDATE messages SET reactions=$1 WHERE id=$2", json.dumps(rx), mid)
    return {"ok": True}

@app.post("/api/upload")
async def upload(to: int = Form(...), kind: str = Form("file"), file: UploadFile = File(...), u=Depends(auth)):
    dest_dir = UP_DIR / str(u["id"]); dest_dir.mkdir(exist_ok=True)
    name = f"{int(time.time()*1000)}_{secrets.token_hex(4)}_{file.filename}"
    dest = dest_dir / name; size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(4 * MB): size += len(chunk); out.write(chunk)
    rel = f"/files/{u['id']}/{name}"
    k = kind if kind in ("file", "voice", "circle") else "file"
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO messages(frm,to_,kind,file_path,file_name,file_size,ts) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id", u["id"], to, k, rel, file.filename, size, now())
    msg = dict(id=mid, frm=u["id"], to=to, kind=k, file_path=rel, file_name=file.filename, file_size=size, ts=now())
    await push([u["id"], to], {"type": "msg", "msg": msg})
    return msg

@app.get("/files/{uid}/{name}")
def get_file(uid: int, name: str):
    p = UP_DIR / str(uid) / name
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

@app.get("/api/search")
async def search(q: str, u=Depends(auth)):
    async with pool.acquire() as con:
        users = await con.fetch("SELECT id, username, name FROM users WHERE username ILIKE $1 OR name ILIKE $1 LIMIT 10", f"%{q}%")
        channels = await con.fetch("SELECT id, uname as username, title as name, avatar FROM channels WHERE uname ILIKE $1 OR title ILIKE $1 LIMIT 10", f"%{q}%")
        groups = await con.fetch("SELECT id, name, bio FROM groups WHERE name ILIKE $1 LIMIT 10", f"%{q}%")
    return {"users": [dict(r) for r in users], "channels": [dict(r) for r in channels], "groups": [dict(r) for r in groups]}

@app.websocket("/ws")
async def ws(sock: WebSocket, token: str):
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", token)
    if not u: return await sock.close()
    await sock.accept()
    live.setdefault(u["id"], set()).add(sock)
    try:
        while True:
            data = await sock.receive_json()
            if data.get("type") == "msg":
                to_id = int(data["to"])
                mid = await pool.fetchval("INSERT INTO messages(frm,to_,kind,text,ts) VALUES($1,$2,'text',$3,$4) RETURNING id", u["id"], to_id, data["text"], now())
                await push([u["id"], to_id], {"type": "msg", "msg": dict(id=mid, frm=u["id"], to=to_id, text=data["text"], kind="text", ts=now())})
    except: live[u["id"]].discard(sock)
# --- КАНАЛЫ ---
@app.get("/api/channels/search")
async def search_channels(q: str = "", u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, uname, title, bio, avatar, owner_id FROM channels WHERE uname ILIKE $1 OR title ILIKE $1", f"%{q}%")
    return [dict(r) for r in rows]

@app.post("/api/channels")
async def channel_create(b: ChanIn, u=Depends(auth)):
    un = b.uname.strip().lower().lstrip("@")
    async with pool.acquire() as con:
        if await con.fetchval("SELECT 1 FROM channels WHERE uname=$1", un): raise HTTPException(400, "Занят")
        cid = await con.fetchval("INSERT INTO channels(uname,title,owner_id,bio,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", un, b.title, u["id"], b.bio, now())
    return {"id": cid}

@app.post("/api/channels/{cid}/edit")
async def channel_edit(cid: int, b: ChanIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        await con.execute("UPDATE channels SET title=$1, bio=$2 WHERE id=$3", b.title, b.bio, cid)
    return {"ok": True}

@app.post("/api/channels/{cid}/avatar")
async def channel_avatar(cid: int, file: UploadFile = File(...), u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
    dest_dir = UP_DIR / "avatars"; dest_dir.mkdir(exist_ok=True)
    name = f"ch_{cid}_{secrets.token_hex(4)}.jpg"
    with open(dest_dir / name, "wb") as out: out.write(await file.read())
    async with pool.acquire() as con:
        await con.execute("UPDATE channels SET avatar=$1 WHERE id=$2", f"/files/avatars/{name}", cid)
    return {"ok": True}

@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM channel_posts WHERE channel_id=$1 ORDER BY id DESC", cid)
    return [dict(r) for r in rows]

@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        pid = await con.fetchval("INSERT INTO channel_posts(channel_id,text,ts) VALUES($1,$2,$3) RETURNING id", cid, b.text, now())
    return {"id": pid}

@app.post("/api/channels/post/edit/{pid}")
async def edit_post(pid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT channel_id FROM channel_posts WHERE id=$1", pid)
        if post:
            ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", post["channel_id"])
            if ch["owner_id"] == u["id"] or u["role"] == "owner":
                await con.execute("UPDATE channel_posts SET text=$1 WHERE id=$2", b.text, pid)
    return {"ok": True}

@app.post("/api/channels/post/del/{pid}")
async def del_post(pid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT channel_id FROM channel_posts WHERE id=$1", pid)
        if post:
            ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", post["channel_id"])
            if ch["owner_id"] == u["id"] or u["role"] == "owner":
                await con.execute("DELETE FROM channel_posts WHERE id=$1", pid)
    return {"ok": True}

@app.post("/api/channels/pin/{pid}")
async def pin_channel_post(pid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT channel_id FROM channel_posts WHERE id=$1", pid)
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", post["channel_id"])
        if ch["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        await con.execute("UPDATE channel_posts SET pinned = NOT pinned WHERE id=$1", pid)
    return {"ok": True}

@app.post("/api/channels/upload/{cid}")
async def channel_upload(cid: int, kind: str = Form("file"), file: UploadFile = File(...), u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
    dest_dir = UP_DIR / "ch" / str(cid); dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time())}_{file.filename}"
    with open(dest_dir / name, "wb") as out:
        while chunk := await file.read(4 * MB): out.write(chunk)
    rel = f"/files/ch/{cid}/{name}"
    async with pool.acquire() as con:
        await con.execute("INSERT INTO channel_posts(channel_id, kind, file_path, file_name, ts) VALUES($1,$2,$3,$4,$5)", cid, kind, rel, file.filename, now())
    return {"ok": True}

@app.get("/files/ch/{cid}/{name}")
def get_ch_file(cid: int, name: str):
    p = UP_DIR / "ch" / str(cid) / name
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

# --- ГРУППЫ ---
@app.post("/api/groups")
async def group_create(b: GroupIn, u=Depends(auth)):
    async with pool.acquire() as con:
        gid = await con.fetchval("INSERT INTO groups(name,owner_id,bio,created_at) VALUES($1,$2,$3,$4) RETURNING id", b.name, u["id"], b.bio, now())
        await con.execute("INSERT INTO group_members(group_id,user_id,role) VALUES($1,$2,'owner')", gid, u["id"])
    return {"id": gid}

@app.get("/api/groups")
async def my_groups(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT g.* FROM groups g JOIN group_members m ON g.id=m.group_id WHERE m.user_id=$1", u["id"])
    return [dict(r) for r in rows]

@app.get("/api/groups/{gid}/msgs")
async def group_msgs(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT m.*, u.username as author FROM group_msgs m JOIN users u ON m.frm=u.id WHERE group_id=$1 ORDER BY m.id", gid)
    return [dict(r) for r in rows]

@app.post("/api/groups/{gid}/send")
async def group_send(gid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO group_msgs(group_id,frm,text,ts) VALUES($1,$2,$3,$4) RETURNING id", gid, u["id"], b.text, now())
    return {"id": mid}

@app.post("/api/groups/{gid}/add")
async def group_add(gid: int, uname: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        g = await con.fetchrow("SELECT owner_id FROM groups WHERE id=$1", gid)
        if g["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        target = await con.fetchrow("SELECT id FROM users WHERE username=$1", uname.strip().lower().lstrip("@"))
        if target:
            await con.execute("INSERT INTO group_members(group_id,user_id,role) VALUES($1,$2,'member') ON CONFLICT DO NOTHING", gid, target["id"])
    return {"ok": True}

@app.get("/api/groups/{gid}/members")
async def group_members(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT u.id, u.username, u.name, m.role FROM users u JOIN group_members m ON u.id=m.user_id WHERE m.group_id=$1", gid)
    return [dict(r) for r in rows]

# --- ПАНЕЛЬ ВЛАДЕЛЬЦА ---
class OwnerUserIn(BaseModel): user_id: int
class OwnerCoinIn(BaseModel): user_id: int; amount: int
class OwnerBcIn(BaseModel): text: str
class OwnerPromoIn(BaseModel): code: str; kind: str; amount: int; uses: int
class OwnerRoleIn(BaseModel): user_id: int; role: str

def require_owner(u):
    if u["role"] != "owner": raise HTTPException(403, "Только для владельца")

@app.get("/api/owner/stats")
async def owner_stats(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        return {"users": await con.fetchval("SELECT count(*) FROM users"), "messages": await con.fetchval("SELECT count(*) FROM messages"), "channels": await con.fetchval("SELECT count(*) FROM channels"), "groups": await con.fetchval("SELECT count(*) FROM groups"), "banned": await con.fetchval("SELECT count(*) FROM users WHERE banned=true")}

@app.get("/api/owner/users")
async def owner_users(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, username, name, role, becoins, banned FROM users ORDER BY id DESC")
    return [dict(r) for r in rows]

@app.post("/api/owner/ban")
async def owner_ban(b: OwnerUserIn, u=Depends(auth)):
    require_owner(u)
    if b.user_id == u["id"]: raise HTTPException(400, "Себя нельзя")
    async with pool.acquire() as con: await con.execute("UPDATE users SET banned=true, token=NULL WHERE id=$1", b.user_id)
    return {"ok": True}

@app.post("/api/owner/unban")
async def owner_unban(b: OwnerUserIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con: await con.execute("UPDATE users SET banned=false WHERE id=$1", b.user_id)
    return {"ok": True}

@app.post("/api/owner/coins")
async def owner_coins(b: OwnerCoinIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con: await con.execute("UPDATE users SET becoins=GREATEST(0,becoins+$1) WHERE id=$2", b.amount, b.user_id)
    return {"ok": True}

@app.post("/api/owner/role")
async def owner_role(b: OwnerRoleIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con: await con.execute("UPDATE users SET role=$1 WHERE id=$2", b.role, b.user_id)
    return {"ok": True}

@app.post("/api/owner/broadcast")
async def owner_broadcast(b: OwnerBcIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        users = await con.fetch("SELECT id FROM users WHERE id != $1", u["id"])
        for usr in users: await con.execute("INSERT INTO messages(frm,to_,kind,text,ts) VALUES(0,$1,'system',$2,$3)", usr["id"], b.text, now())
    return {"ok": True}

@app.post("/api/owner/promo")
async def owner_promo(b: OwnerPromoIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        await con.execute("INSERT INTO promo_codes(code,kind,amount,uses_left) VALUES($1,$2,$3,$4) ON CONFLICT (code) DO UPDATE SET kind=$2, amount=$3, uses_left=$4", b.code.upper(), b.kind, b.amount, b.uses)
    return {"ok": True}

@app.post("/api/promo/redeem")
async def redeem(code: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con, con.transaction():
        p = await con.fetchrow("SELECT * FROM promo_codes WHERE code=$1 FOR UPDATE", code.upper())
        if not p or p["uses_left"] < 1: raise HTTPException(400, "Не найден")
        if await con.fetchval("SELECT 1 FROM promo_redemptions WHERE code=$1 AND user_id=$2", p["code"], u["id"]): raise HTTPException(400, "Уже использован")
        await con.execute("UPDATE promo_codes SET uses_left=uses_left-1 WHERE code=$1", p["code"])
        await con.execute("INSERT INTO promo_redemptions(code,user_id) VALUES($1,$2)", p["code"], u["id"])
        if p["kind"] == "becoins": await con.execute("UPDATE users SET becoins=becoins+$1 WHERE id=$2", p["amount"], u["id"])
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    return open("index.html", encoding="utf-8").read()
# ==========================================
# ДОБАВЛЕННЫЕ СИСТЕМЫ (ВСЁ, ЧТО БЫЛО ВЫРЕЗАНО)
# ==========================================

from pydantic import BaseModel

class EditMsgIn(BaseModel): text: str
class OwnerUserIn(BaseModel): user_id: int
class OwnerCoinIn(BaseModel): user_id: int; amount: int
class OwnerBcIn(BaseModel): text: str
class OwnerPromoIn(BaseModel): code: str; kind: str; amount: int; uses: int
class OwnerRoleIn(BaseModel): user_id: int; role: str

def require_owner(u):
    if u["role"] != "owner": raise HTTPException(403, "Только для владельца")

# --- DM: РЕДАКТИРОВАНИЕ, УДАЛЕНИЕ, ЗАКРЕПЛЕНИЕ, РЕАКЦИИ ---
@app.post("/api/dm/edit/{mid}")
async def dm_edit(mid: int, b: EditMsgIn, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE messages SET text=$1 WHERE id=$2 AND frm=$3", b.text[:4000], mid, u["id"])
    return {"ok": True}

@app.post("/api/dm/del/{mid}")
async def dm_del(mid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM messages WHERE id=$1 AND frm=$2", mid, u["id"])
    return {"ok": True}

@app.post("/api/pin_dm/{mid}")
async def pin_dm(mid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE messages SET pinned = NOT pinned WHERE id=$1 AND (frm=$2 OR to_=$2)", mid, u["id"])
    return {"ok": True}

@app.post("/api/react/{mid}")
async def react(mid: int, emoji: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT reactions FROM messages WHERE id=$1", mid)
        rx = row["reactions"] or {}
        if emoji not in rx: rx[emoji] = []
        if u["id"] in rx[emoji]: rx[emoji].remove(u["id"])
        else: rx[emoji].append(u["id"])
        await con.execute("UPDATE messages SET reactions=$1 WHERE id=$2", json.dumps(rx), mid)
    return {"ok": True}

# --- КАНАЛЫ (ПОЛНЫЙ CRUD + АВАТАРКИ + МЕДИА) ---
@app.get("/api/channels/search")
async def search_channels(q: str = "", u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, uname, title, bio, avatar, owner_id FROM channels WHERE uname ILIKE $1 OR title ILIKE $1", f"%{q}%")
    return [dict(r) for r in rows]

@app.post("/api/channels")
async def channel_create(b: ChanIn, u=Depends(auth)):
    un = b.uname.strip().lower().lstrip("@")
    async with pool.acquire() as con:
        if await con.fetchval("SELECT 1 FROM channels WHERE uname=$1", un): raise HTTPException(400, "Занят")
        cid = await con.fetchval("INSERT INTO channels(uname,title,owner_id,bio,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", un, b.title, u["id"], b.bio, now())
    return {"id": cid}

@app.post("/api/channels/{cid}/edit")
async def channel_edit(cid: int, b: ChanIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        await con.execute("UPDATE channels SET title=$1, bio=$2 WHERE id=$3", b.title, b.bio, cid)
    return {"ok": True}

@app.post("/api/channels/{cid}/avatar")
async def channel_avatar(cid: int, file: UploadFile = File(...), u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
    dest_dir = UP_DIR / "avatars"; dest_dir.mkdir(exist_ok=True)
    name = f"ch_{cid}_{secrets.token_hex(4)}.jpg"
    with open(dest_dir / name, "wb") as out: out.write(await file.read())
    async with pool.acquire() as con:
        await con.execute("UPDATE channels SET avatar=$1 WHERE id=$2", f"/files/avatars/{name}", cid)
    return {"ok": True}

@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM channel_posts WHERE channel_id=$1 ORDER BY id DESC", cid)
    return [dict(r) for r in rows]

@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        pid = await con.fetchval("INSERT INTO channel_posts(channel_id,text,ts) VALUES($1,$2,$3) RETURNING id", cid, b.text, now())
    return {"id": pid}

@app.post("/api/channels/post/edit/{pid}")
async def edit_post(pid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT channel_id FROM channel_posts WHERE id=$1", pid)
        if post:
            ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", post["channel_id"])
            if ch["owner_id"] == u["id"] or u["role"] == "owner":
                await con.execute("UPDATE channel_posts SET text=$1 WHERE id=$2", b.text, pid)
    return {"ok": True}

@app.post("/api/channels/post/del/{pid}")
async def del_post(pid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT channel_id FROM channel_posts WHERE id=$1", pid)
        if post:
            ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", post["channel_id"])
            if ch["owner_id"] == u["id"] or u["role"] == "owner":
                await con.execute("DELETE FROM channel_posts WHERE id=$1", pid)
    return {"ok": True}

@app.post("/api/channels/pin/{pid}")
async def pin_channel_post(pid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT channel_id FROM channel_posts WHERE id=$1", pid)
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", post["channel_id"])
        if ch["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        await con.execute("UPDATE channel_posts SET pinned = NOT pinned WHERE id=$1", pid)
    return {"ok": True}

@app.post("/api/channels/upload/{cid}")
async def channel_upload(cid: int, kind: str = Form("file"), file: UploadFile = File(...), u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT owner_id FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
    dest_dir = UP_DIR / "ch" / str(cid); dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time())}_{file.filename}"
    with open(dest_dir / name, "wb") as out:
        while chunk := await file.read(4 * MB): out.write(chunk)
    rel = f"/files/ch/{cid}/{name}"
    async with pool.acquire() as con:
        await con.execute("INSERT INTO channel_posts(channel_id, kind, file_path, file_name, ts) VALUES($1,$2,$3,$4,$5)", cid, kind, rel, file.filename, now())
    return {"ok": True}

@app.get("/files/ch/{cid}/{name}")
def get_ch_file(cid: int, name: str):
    p = UP_DIR / "ch" / str(cid) / name
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

@app.get("/files/avatars/{name}")
def get_avatar_file(name: str):
    p = UP_DIR / "avatars" / name
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p)

# --- ГРУППЫ (ПОЛНЫЙ CRUD) ---
@app.post("/api/groups")
async def group_create(b: GroupIn, u=Depends(auth)):
    async with pool.acquire() as con:
        gid = await con.fetchval("INSERT INTO groups(name,owner_id,bio,created_at) VALUES($1,$2,$3,$4) RETURNING id", b.name, u["id"], b.bio, now())
        await con.execute("INSERT INTO group_members(group_id,user_id,role) VALUES($1,$2,'owner')", gid, u["id"])
    return {"id": gid}

@app.get("/api/groups")
async def my_groups(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT g.* FROM groups g JOIN group_members m ON g.id=m.group_id WHERE m.user_id=$1", u["id"])
    return [dict(r) for r in rows]

@app.get("/api/groups/{gid}/msgs")
async def group_msgs(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT m.*, u.username as author FROM group_msgs m JOIN users u ON m.frm=u.id WHERE group_id=$1 ORDER BY m.id", gid)
    return [dict(r) for r in rows]

@app.post("/api/groups/{gid}/send")
async def group_send(gid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO group_msgs(group_id,frm,text,ts) VALUES($1,$2,$3,$4) RETURNING id", gid, u["id"], b.text, now())
    return {"id": mid}

@app.post("/api/groups/{gid}/add")
async def group_add(gid: int, uname: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        g = await con.fetchrow("SELECT owner_id FROM groups WHERE id=$1", gid)
        if g["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        target = await con.fetchrow("SELECT id FROM users WHERE username=$1", uname.strip().lower().lstrip("@"))
        if target:
            await con.execute("INSERT INTO group_members(group_id,user_id,role) VALUES($1,$2,'member') ON CONFLICT DO NOTHING", gid, target["id"])
    return {"ok": True}

@app.get("/api/groups/{gid}/members")
async def group_members(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT u.id, u.username, u.name, m.role FROM users u JOIN group_members m ON u.id=m.user_id WHERE m.group_id=$1", gid)
    return [dict(r) for r in rows]

# --- ПАНЕЛЬ ВЛАДЕЛЬЦА (ПОЛНАЯ) ---
@app.get("/api/owner/stats")
async def owner_stats(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        return {
            "users": await con.fetchval("SELECT count(*) FROM users"),
            "messages": await con.fetchval("SELECT count(*) FROM messages"),
            "channels": await con.fetchval("SELECT count(*) FROM channels"),
            "groups": await con.fetchval("SELECT count(*) FROM groups"),
            "banned": await con.fetchval("SELECT count(*) FROM users WHERE banned=true")
        }

@app.get("/api/owner/users")
async def owner_users(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, username, name, role, becoins, banned FROM users ORDER BY id DESC")
    return [dict(r) for r in rows]

@app.post("/api/owner/ban")
async def owner_ban(b: OwnerUserIn, u=Depends(auth)):
    require_owner(u)
    if b.user_id == u["id"]: raise HTTPException(400, "Себя нельзя")
    async with pool.acquire() as con: await con.execute("UPDATE users SET banned=true, token=NULL WHERE id=$1", b.user_id)
    return {"ok": True}

@app.post("/api/owner/unban")
async def owner_unban(b: OwnerUserIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con: await con.execute("UPDATE users SET banned=false WHERE id=$1", b.user_id)
    return {"ok": True}

@app.post("/api/owner/coins")
async def owner_coins(b: OwnerCoinIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con: await con.execute("UPDATE users SET becoins=GREATEST(0,becoins+$1) WHERE id=$2", b.amount, b.user_id)
    return {"ok": True}

@app.post("/api/owner/role")
async def owner_role(b: OwnerRoleIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con: await con.execute("UPDATE users SET role=$1 WHERE id=$2", b.role, b.user_id)
    return {"ok": True}

@app.post("/api/owner/broadcast")
async def owner_broadcast(b: OwnerBcIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        users = await con.fetch("SELECT id FROM users WHERE id != $1", u["id"])
        for usr in users: await con.execute("INSERT INTO messages(frm,to_,kind,text,ts) VALUES(0,$1,'system',$2,$3)", usr["id"], b.text, now())
    return {"ok": True}

@app.post("/api/owner/promo")
async def owner_promo(b: OwnerPromoIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        await con.execute("INSERT INTO promo_codes(code,kind,amount,uses_left) VALUES($1,$2,$3,$4) ON CONFLICT (code) DO UPDATE SET kind=$2, amount=$3, uses_left=$4", b.code.upper(), b.kind, b.amount, b.uses)
    return {"ok": True}

@app.post("/api/promo/redeem")
async def redeem(code: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con, con.transaction():
        p = await con.fetchrow("SELECT * FROM promo_codes WHERE code=$1 FOR UPDATE", code.upper())
        if not p or p["uses_left"] < 1: raise HTTPException(400, "Не найден")
        if await con.fetchval("SELECT 1 FROM promo_redemptions WHERE code=$1 AND user_id=$2", p["code"], u["id"]): raise HTTPException(400, "Уже использован")
        await con.execute("UPDATE promo_codes SET uses_left=uses_left-1 WHERE code=$1", p["code"])
        await con.execute("INSERT INTO promo_redemptions(code,user_id) VALUES($1,$2)", p["code"], u["id"])
        if p["kind"] == "becoins": await con.execute("UPDATE users SET becoins=becoins+$1 WHERE id=$2", p["amount"], u["id"])
    return {"ok": True}