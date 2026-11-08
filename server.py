import os, secrets, time, random, string, hashlib, json, shutil
from pathlib import Path
from typing import Optional
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/belugacord")
UP_DIR = Path(os.getenv("BC_UPLOADS", "uploads")); UP_DIR.mkdir(exist_ok=True)
MB = 1024 * 1024
MAX_FREE, MAX_PREM, MAX_OWNER = 100 * MB, 1024 * MB, 20 * 1024 * MB

app = FastAPI()
pool: asyncpg.Pool = None
live: dict[int, set[WebSocket]] = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    pw_hash TEXT NOT NULL, token TEXT UNIQUE, becoins INT NOT NULL DEFAULT 0,
    premium_until BIGINT NOT NULL DEFAULT 0, role TEXT NOT NULL DEFAULT 'user',
    bio TEXT NOT NULL DEFAULT '', created_at BIGINT NOT NULL, banned BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS usernames(
    uname TEXT PRIMARY KEY, owner_id INT NOT NULL REFERENCES users(id),
    is_primary BOOLEAN NOT NULL DEFAULT false, for_sale_price INT, acquired_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages(
    id SERIAL PRIMARY KEY, frm INT NOT NULL, to_ INT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'text', text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT,
    meta JSONB, ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels(
    id SERIAL PRIMARY KEY, uname TEXT UNIQUE NOT NULL, title TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '',
    owner_id INT NOT NULL REFERENCES users(id), avatar TEXT, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS channel_subs(
    channel_id INT REFERENCES channels(id), user_id INT REFERENCES users(id), PRIMARY KEY(channel_id, user_id)
);
CREATE TABLE IF NOT EXISTS channel_posts(
    id SERIAL PRIMARY KEY, channel_id INT NOT NULL REFERENCES channels(id),
    kind TEXT NOT NULL DEFAULT 'text', text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT, edited BOOLEAN DEFAULT false, ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS groups(
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, bio TEXT DEFAULT '', owner_id INT REFERENCES users(id), avatar TEXT, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS group_members(
    group_id INT REFERENCES groups(id), user_id INT REFERENCES users(id), role TEXT DEFAULT 'member', PRIMARY KEY(group_id, user_id)
);
CREATE TABLE IF NOT EXISTS group_msgs(
    id SERIAL PRIMARY KEY, group_id INT REFERENCES groups(id), frm INT REFERENCES users(id),
    text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT, ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS bots(
    id SERIAL PRIMARY KEY, owner_id INT NOT NULL REFERENCES users(id),
    bot_username TEXT UNIQUE NOT NULL, name TEXT NOT NULL, api_token TEXT UNIQUE NOT NULL, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_codes(
    code TEXT PRIMARY KEY, kind TEXT NOT NULL, amount INT NOT NULL, uses_left INT NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_redemptions(
    code TEXT NOT NULL REFERENCES promo_codes(code), user_id INT NOT NULL REFERENCES users(id), PRIMARY KEY(code, user_id)
);
"""

ALTERS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen BIGINT NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN NOT NULL DEFAULT false"
]

def now(): return int(time.time())
def tok(n=40): return secrets.token_hex(n // 2)
def hsh(p): return hashlib.sha256(p.encode()).hexdigest()

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as con:
        for stmt in filter(None, (s.strip() for s in SCHEMA.split(";"))):
            await con.execute(stmt)
        for stmt in ALTERS:
            await con.execute(stmt)
        await con.execute("UPDATE users SET name = username WHERE name = '' OR name IS NULL")

@app.on_event("startup")
async def startup(): await init_db()

def upload_limit(u) -> int:
    if u["role"] == "owner": return MAX_OWNER
    if u["premium_until"] > now(): return MAX_PREM
    return MAX_FREE

async def auth(authorization: str = Header(None), x_token: str = Header(None)):
    t = x_token or (authorization.split(" ")[-1] if authorization else None)
    if not t: raise HTTPException(401, "Нужен вход")
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", t)
    if not u: raise HTTPException(401, "Нужен вход")
    if u["banned"]: raise HTTPException(403, "Забанен")
    return u

async def public_user(u, con) -> dict:
    extras = [r["uname"] for r in await con.fetch("SELECT uname FROM usernames WHERE owner_id=$1 AND is_primary=false", u["id"])]
    return dict(id=u["id"], username=u["username"], name=u["name"], bio=u["bio"],
                premium=u["premium_until"] > now(), premium_until=u["premium_until"],
                role=u["role"], becoins=u["becoins"], upload_limit_mb=upload_limit(u) // MB,
                extra_usernames=extras, banned=u["banned"])

# --- МОДЕЛИ ---
class RegisterIn(BaseModel): username: str; name: str; password: str
class LoginIn(BaseModel): username: str; password: str
class DMIn(BaseModel): to: int; text: str
class SellIn(BaseModel): uname: str; price: int
class GiftUnameIn(BaseModel): uname: str; to: int
class PromoIn(BaseModel): code: str
class ChanIn(BaseModel): uname: str; title: str; bio: str = ""
class GroupIn(BaseModel): name: str; bio: str = ""
class PostIn(BaseModel): text: str
class BotIn(BaseModel): name: str; bot_username: str
class EditMsgIn(BaseModel): text: str
class EditProfileIn(BaseModel): name: str; bio: str

# --- АВТОРИЗАЦИЯ ---
@app.post("/api/register")
async def register(b: RegisterIn):
    u = b.username.strip().lower()
    if not (5 <= len(u) <= 32) or not u[0].isalpha() or not all(c.isalnum() or c == "_" for c in u):
        raise HTTPException(400, "Юзернейм: латиница/цифры/_, от 5 символов")
    if len(b.password) < 4: raise HTTPException(400, "Пароль минимум 4 символа")
    async with pool.acquire() as con, con.transaction():
        if await con.fetchval("SELECT 1 FROM usernames WHERE uname=$1", u): raise HTTPException(400, "Занят")
        t = tok()
        uid = await con.fetchval("INSERT INTO users(username,name,pw_hash,token,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", u, b.name.strip()[:40] or u, hsh(b.password), t, now())
        await con.execute("INSERT INTO usernames(uname,owner_id,is_primary,acquired_at) VALUES($1,$2,true,$3)", u, uid, now())
    return {"token": t}

@app.post("/api/login")
async def login(b: LoginIn):
    u = b.username.strip().lower().lstrip("@")
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT owner_id FROM usernames WHERE uname=$1", u)
        if not row: raise HTTPException(403, "Аккаунта нет")
        acc = await con.fetchrow("SELECT * FROM users WHERE id=$1", row["owner_id"])
        if acc["banned"]: raise HTTPException(403, "Забанен")
        if not bcrypt.verify(b.password, acc["pw_hash"]): raise HTTPException(403, "Неверный пароль") if "bcrypt" in globals() else (None if hsh(b.password) == acc["pw_hash"] else (_ for _ in ()).throw(HTTPException(403, "Неверный пароль")))
        t = tok()
        await con.execute("UPDATE users SET token=$1, last_seen=$2 WHERE id=$3", t, now(), acc["id"])
    return {"token": t}

@app.get("/api/me")
async def me(u=Depends(auth)):
    async with pool.acquire() as con: return await public_user(u, con)

@app.post("/api/me/edit")
async def edit_me(b: EditProfileIn, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET name=$1, bio=$2 WHERE id=$3", b.name[:40], b.bio[:200], u["id"])
    return {"ok": True}

# --- ФАЙЛЫ ---
@app.post("/api/upload")
async def upload(to: int = Form(0), kind: str = Form("file"), file: UploadFile = File(...), u=Depends(auth)):
    limit = upload_limit(u); dest_dir = UP_DIR / str(u["id"]); dest_dir.mkdir(exist_ok=True)
    name = f"{int(time.time()*1000)}_{secrets.token_hex(4)}_{file.filename}"
    dest = dest_dir / name; size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(4 * MB):
            size += len(chunk)
            if size > limit:
                out.close(); dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Файл больше лимита ({limit // MB} МБ)")
            out.write(chunk)
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

# --- DM ---
async def push(uids, payload):
    for uid in set(uids):
        for ws in list(live.get(uid, [])):
            try: await ws.send_json(payload)
            except Exception: live[uid].discard(ws)

@app.get("/api/chat/{peer_id}")
async def chat(peer_id: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM messages WHERE (frm=$1 AND to_=$2) OR (frm=$2 AND to_=$1) ORDER BY id", u["id"], peer_id)
    return [dict(r) for r in rows]

@app.post("/api/dm/send")
async def dm_send(b: DMIn, u=Depends(auth)):
    if not b.text.strip(): raise HTTPException(400, "Пусто")
    async with pool.acquire() as con:
        mid = await con.fetchval("INSERT INTO messages(frm,to_,kind,text,ts) VALUES($1,$2,'text',$3,$4) RETURNING id", u["id"], b.to, b.text[:4000], now())
    msg = dict(id=mid, frm=u["id"], to=b.to, kind="text", text=b.text[:4000], ts=now())
    await push([u["id"], b.to], {"type": "msg", "msg": msg})
    return {"ok": True}
# --- КАНАЛЫ ---
@app.get("/api/channels/search")
async def search_channels(q: str = "", u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, uname, title, bio, avatar, (SELECT count(*) FROM channel_subs WHERE channel_id=channels.id) as subs FROM channels WHERE uname ILIKE $1 OR title ILIKE $1", f"%{q}%")
    return [dict(r) for r in rows]

@app.post("/api/channels")
async def channel_create(b: ChanIn, u=Depends(auth)):
    un = b.uname.strip().lower().lstrip("@")
    if not (5 <= len(un) <= 32) or not un[0].isalpha() or not all(c.isalnum() or c == "_" for c in un):
        raise HTTPException(400, "Юзернейм канала: латиница/цифры/_, от 5 символов")
    async with pool.acquire() as con, con.transaction():
        if await con.fetchval("SELECT 1 FROM usernames WHERE uname=$1", un) or await con.fetchval("SELECT 1 FROM channels WHERE uname=$1", un):
            raise HTTPException(400, "Занят")
        cid = await con.fetchval("INSERT INTO channels(uname,title,owner_id,bio,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id", un, b.title[:64], u["id"], b.bio[:200], now())
        await con.execute("INSERT INTO channel_subs(channel_id,user_id) VALUES($1,$2)", cid, u["id"])
    return {"id": cid, "uname": un}

@app.post("/api/channels/{cid}/edit")
async def channel_edit(cid: int, b: ChanIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        await con.execute("UPDATE channels SET title=$1, bio=$2 WHERE id=$3", b.title[:64], b.bio[:200], cid)
    return {"ok": True}

@app.post("/api/channels/{cid}/avatar")
async def channel_avatar(cid: int, file: UploadFile = File(...), u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        dest_dir = UP_DIR / "avatars" / "ch"; dest_dir.mkdir(parents=True, exist_ok=True)
        name = f"ch_{cid}_{secrets.token_hex(4)}.jpg"
        with open(dest_dir / name, "wb") as out: out.write(await file.read())
        await con.execute("UPDATE channels SET avatar=$1 WHERE id=$2", f"/files/avatars/ch/{name}", cid)
    return {"ok": True}

@app.post("/api/channels/{cid}/subscribe")
async def channel_sub(cid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("INSERT INTO channel_subs(channel_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING", cid, u["id"])
    return {"ok": True}

@app.post("/api/channels/{cid}/unsubscribe")
async def channel_unsub(cid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute("DELETE FROM channel_subs WHERE channel_id=$1 AND user_id=$2", cid, u["id"])
    return {"ok": True}

@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM channel_posts WHERE channel_id=$1 ORDER BY id DESC LIMIT 100", cid)
    return [dict(r) for r in rows]

@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]: raise HTTPException(403, "Только владелец")
        pid = await con.fetchval("INSERT INTO channel_posts(channel_id,kind,text,ts) VALUES($1,'text',$2,$3) RETURNING id", cid, b.text[:4000], now())
    return {"id": pid}

@app.post("/api/channels/posts/{pid}/edit")
async def post_edit(pid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT * FROM channel_posts WHERE id=$1", pid)
        if not post: raise HTTPException(404, "Нет поста")
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", post["channel_id"])
        if ch["owner_id"] != u["id"]: raise HTTPException(403, "Не твой канал")
        await con.execute("UPDATE channel_posts SET text=$1, edited=true WHERE id=$2", b.text[:4000], pid)
    return {"ok": True}

@app.post("/api/channels/posts/{pid}/delete")
async def post_del(pid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        post = await con.fetchrow("SELECT * FROM channel_posts WHERE id=$1", pid)
        if not post: raise HTTPException(404, "Нет поста")
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", post["channel_id"])
        if ch["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        await con.execute("DELETE FROM channel_posts WHERE id=$1", pid)
    return {"ok": True}

# --- ГРУППЫ ---
@app.post("/api/groups")
async def group_create(b: GroupIn, u=Depends(auth)):
    async with pool.acquire() as con, con.transaction():
        gid = await con.fetchval("INSERT INTO groups(name,owner_id,bio,created_at) VALUES($1,$2,$3,$4) RETURNING id", b.name[:64], u["id"], b.bio[:200], now())
        await con.execute("INSERT INTO group_members(group_id,user_id,role) VALUES($1,$2,'owner')", gid, u["id"])
    return {"id": gid}

@app.get("/api/groups")
async def my_groups(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT g.*, (SELECT count(*) FROM group_members WHERE group_id=g.id) as members FROM groups g JOIN group_members m ON g.id=m.group_id WHERE m.user_id=$1", u["id"])
    return [dict(r) for r in rows]

@app.get("/api/groups/{gid}/msgs")
async def group_msgs(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        if not await con.fetchval("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2", gid, u["id"]): raise HTTPException(403, "Не участник")
        rows = await con.fetch("SELECT m.*, u.username as author FROM group_msgs m JOIN users u ON m.frm=u.id WHERE group_id=$1 ORDER BY m.id", gid)
    return [dict(r) for r in rows]

@app.post("/api/groups/{gid}/send")
async def group_send(gid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        if not await con.fetchval("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2", gid, u["id"]): raise HTTPException(403, "Не участник")
        mid = await con.fetchval("INSERT INTO group_msgs(group_id,frm,text,ts) VALUES($1,$2,$3,$4) RETURNING id", gid, u["id"], b.text[:4000], now())
    return {"id": mid}

@app.post("/api/groups/{gid}/add")
async def group_add(gid: int, uname: str = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        g = await con.fetchrow("SELECT * FROM groups WHERE id=$1", gid)
        if not g: raise HTTPException(404, "Нет группы")
        if g["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        target = await con.fetchrow("SELECT id FROM users WHERE username=$1", uname.strip().lower().lstrip("@"))
        if not target: raise HTTPException(404, "Юзер не найден")
        await con.execute("INSERT INTO group_members(group_id,user_id,role) VALUES($1,$2,'member') ON CONFLICT DO NOTHING", gid, target["id"])
    return {"ok": True}

@app.post("/api/groups/{gid}/kick")
async def group_kick(gid: int, user_id: int = Form(...), u=Depends(auth)):
    async with pool.acquire() as con:
        g = await con.fetchrow("SELECT * FROM groups WHERE id=$1", gid)
        if not g: raise HTTPException(404, "Нет группы")
        if g["owner_id"] != u["id"] and u["role"] != "owner": raise HTTPException(403, "Нет прав")
        await con.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2", gid, user_id)
    return {"ok": True}

@app.get("/api/groups/{gid}/members")
async def group_members(gid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT u.id, u.username, u.name, m.role FROM users u JOIN group_members m ON u.id=m.user_id WHERE m.group_id=$1", gid)
    return [dict(r) for r in rows]

# --- ПОИСК ---
@app.get("/api/search")
async def global_search(q: str, u=Depends(auth)):
    async with pool.acquire() as con:
        users = await con.fetch("SELECT id, username, name FROM users WHERE username ILIKE $1 OR name ILIKE $1 LIMIT 10", f"%{q}%")
        channels = await con.fetch("SELECT id, uname as username, title as name, avatar FROM channels WHERE uname ILIKE $1 OR title ILIKE $1 LIMIT 10", f"%{q}%")
        groups = await con.fetch("SELECT id, name, bio FROM groups WHERE name ILIKE $1 LIMIT 10", f"%{q}%")
    return {"users": [dict(r) for r in users], "channels": [dict(r) for r in channels], "groups": [dict(r) for r in groups]}

# --- WEBSOCKET ---
@app.websocket("/ws")
async def ws(sock: WebSocket, token: str):
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", token)
    if not u: return await sock.close()
    await sock.accept()
    live.setdefault(u["id"], set()).add(sock)
    try:
        while True: await sock.receive_json()
    except WebSocketDisconnect:
        live[u["id"]].discard(sock)
# --- ПАНЕЛЬ ВЛАДЕЛЬЦА (ЧАСТЬ 3) ---
class OwnerUserIn(BaseModel): user_id: int
class OwnerCoinIn(BaseModel): user_id: int; amount: int
class OwnerPremIn(BaseModel): user_id: int; days: int
class OwnerRoleIn(BaseModel): user_id: int; role: str
class OwnerBroadcastIn(BaseModel): text: str
class OwnerPromoIn(BaseModel): code: str; kind: str; amount: int; uses: int
class OwnerChangeUnameIn(BaseModel): user_id: int; uname: str

def require_owner(u):
    if u["role"] != "owner":
        raise HTTPException(403, "Только для владельца")

# 1. Статистика
@app.get("/api/owner/stats")
async def owner_stats(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        users = await con.fetchval("SELECT count(*) FROM users")
        banned = await con.fetchval("SELECT count(*) FROM users WHERE banned=true")
        prem = await con.fetchval("SELECT count(*) FROM users WHERE premium_until > $1", now())
        msgs = await con.fetchval("SELECT count(*) FROM messages")
        channels = await con.fetchval("SELECT count(*) FROM channels")
        groups = await con.fetchval("SELECT count(*) FROM groups")
        posts = await con.fetchval("SELECT count(*) FROM channel_posts")
    return {"users": users, "banned": banned, "premium": prem, "messages": msgs, "channels": channels, "groups": groups, "posts": posts}

# 2. Список всех юзеров
@app.get("/api/owner/users")
async def owner_users(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT id, username, name, role, becoins, premium_until, banned, created_at FROM users ORDER BY id DESC")
    return [dict(r) for r in rows]

# 3. Бан / Разбан
@app.post("/api/owner/ban")
async def owner_ban(b: OwnerUserIn, u=Depends(auth)):
    require_owner(u)
    if b.user_id == u["id"]: raise HTTPException(400, "Себя банить нельзя")
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET banned=true, token=NULL WHERE id=$1", b.user_id)
    return {"ok": True}

@app.post("/api/owner/unban")
async def owner_unban(b: OwnerUserIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET banned=false WHERE id=$1", b.user_id)
    return {"ok": True}

# 4. Выдача бекоинов и премиума
@app.post("/api/owner/coins")
async def owner_coins(b: OwnerCoinIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        bal = await con.fetchval("UPDATE users SET becoins=GREATEST(0,becoins+$1) WHERE id=$2 RETURNING becoins", b.amount, b.user_id)
    return {"becoins": bal}

@app.post("/api/owner/premium")
async def owner_premium(b: OwnerPremIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        if b.days <= 0:
            until = await con.fetchval("UPDATE users SET premium_until=0 WHERE id=$1 RETURNING premium_until", b.user_id)
        else:
            until = await con.fetchval("UPDATE users SET premium_until=GREATEST(premium_until,$1)+$2 WHERE id=$3 RETURNING premium_until", now(), b.days * 86400, b.user_id)
    return {"premium_until": until}

# 5. Выдача ролей (owner/admin/user)
@app.post("/api/owner/role")
async def owner_role(b: OwnerRoleIn, u=Depends(auth)):
    require_owner(u)
    if b.role not in ("user", "admin", "owner"): raise HTTPException(400, "Роль: user/admin/owner")
    if b.user_id == u["id"]: raise HTTPException(400, "Свою роль менять нельзя")
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET role=$1 WHERE id=$2", b.role, b.user_id)
    return {"ok": True}

# 6. Рассылка всем (системные сообщения)
@app.post("/api/owner/broadcast")
async def owner_broadcast(b: OwnerBroadcastIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        users = await con.fetch("SELECT id FROM users WHERE id != $1", u["id"])
        for usr in users:
            await con.execute("INSERT INTO messages(frm,to_,kind,text,ts) VALUES(0,$1,'system',$2,$3)", usr["id"], b.text[:4000], now())
    return {"ok": True, "sent": len(users)}

# 7. Удаление канала
@app.post("/api/owner/channel/delete")
async def owner_del_channel(cid: int = Form(...), u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        await con.execute("DELETE FROM channel_posts WHERE channel_id=$1", cid)
        await con.execute("DELETE FROM channel_subs WHERE channel_id=$1", cid)
        await con.execute("DELETE FROM channels WHERE id=$1", cid)
    return {"ok": True}

# 8. Удаление группы
@app.post("/api/owner/group/delete")
async def owner_del_group(gid: int = Form(...), u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        await con.execute("DELETE FROM group_msgs WHERE group_id=$1", gid)
        await con.execute("DELETE FROM group_members WHERE group_id=$1", gid)
        await con.execute("DELETE FROM groups WHERE id=$1", gid)
    return {"ok": True}

# 9. Управление промокодами
@app.post("/api/owner/promo")
async def owner_promo(b: OwnerPromoIn, u=Depends(auth)):
    require_owner(u)
    if b.kind not in ("becoins", "premium_days"): raise HTTPException(400, "kind: becoins/premium_days")
    async with pool.acquire() as con:
        await con.execute("INSERT INTO promo_codes(code,kind,amount,uses_left) VALUES($1,$2,$3,$4) ON CONFLICT (code) DO UPDATE SET kind=$2, amount=$3, uses_left=$4", b.code.strip().upper(), b.kind, b.amount, b.uses)
    return {"ok": True}

@app.get("/api/owner/promos")
async def owner_promos(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM promo_codes ORDER BY code")
    return [dict(r) for r in rows]

# 10. Активация промокода пользователем
@app.post("/api/promo/redeem")
async def promo_redeem(b: PromoIn, u=Depends(auth)):
    async with pool.acquire() as con, con.transaction():
        p = await con.fetchrow("SELECT * FROM promo_codes WHERE code=$1 FOR UPDATE", b.code.strip().upper())
        if not p or p["uses_left"] < 1: raise HTTPException(400, "Промокод не найден или кончился")
        if await con.fetchval("SELECT 1 FROM promo_redemptions WHERE code=$1 AND user_id=$2", p["code"], u["id"]):
            raise HTTPException(400, "Уже использован")
        await con.execute("UPDATE promo_codes SET uses_left=uses_left-1 WHERE code=$1", p["code"])
        await con.execute("INSERT INTO promo_redemptions(code,user_id) VALUES($1,$2)", p["code"], u["id"])
        if p["kind"] == "becoins":
            await con.execute("UPDATE users SET becoins=becoins+$1 WHERE id=$2", p["amount"], u["id"])
        else:
            await con.execute("UPDATE users SET premium_until=GREATEST(premium_until,$1)+$2 WHERE id=$3", now(), p["amount"] * 86400, u["id"])
    return {"ok": True}

# 11. Смена юзернейма
@app.post("/api/owner/change_uname")
async def owner_change_uname(b: OwnerChangeUnameIn, u=Depends(auth)):
    require_owner(u)
    new = b.uname.strip().lower().lstrip("@")
    if not (5 <= len(new) <= 32): raise HTTPException(400, "Юз от 5 до 32 символов")
    async with pool.acquire() as con, con.transaction():
        old = await con.fetchrow("SELECT uname FROM usernames WHERE owner_id=$1 AND is_primary=true", b.user_id)
        if not old: raise HTTPException(404, "Основной юз не найден")
        await con.execute("UPDATE usernames SET uname=$1 WHERE uname=$2", new, old["uname"])
        await con.execute("UPDATE users SET username=$1 WHERE id=$2", new, b.user_id)
    return {"ok": True}

# 12. Список всех каналов и групп для управления
@app.get("/api/owner/all_channels")
async def owner_all_channels(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT c.*, u.username as owner_name, (SELECT count(*) FROM channel_subs WHERE channel_id=c.id) as subs FROM channels c JOIN users u ON c.owner_id=u.id")
    return [dict(r) for r in rows]

@app.get("/api/owner/all_groups")
async def owner_all_groups(u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT g.*, u.username as owner_name, (SELECT count(*) FROM group_members WHERE group_id=g.id) as members FROM groups g JOIN users u ON g.owner_id=u.id")
    return [dict(r) for r in rows]

# 13. Главная страница
@app.get("/", response_class=HTMLResponse)
def index():
    return open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read()