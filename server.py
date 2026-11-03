
BelugaCord backend — PostgreSQL (asyncpg). Real auth, DMs over WebSocket,
file/voice/circle uploads, username+number marketplace with gifting,
channels, BotFather-style bots, promo codes, WebRTC call signaling.

Safe to redeploy: every table is CREATE TABLE IF NOT EXISTS, every new column
is ALTER TABLE ... ADD COLUMN IF NOT EXISTS. If the database already has
these tables, startup adds nothing new and touches no existing data.

Run:
    pip install fastapi uvicorn[standard] asyncpg passlib[bcrypt] python-multipart
    export DATABASE_URL=postgresql://belugacord_user:1VSALM1cow@localhost/belugacord_zjgh
    uvicorn server:app --host 0.0.0.0 --port 8000

import os, secrets, time, random, string
from pathlib import Path
import asyncpg
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from passlib.hash import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/belugacord")
UP_DIR = Path(os.getenv("BC_UPLOADS", "uploads")); UP_DIR.mkdir(exist_ok=True)

MB = 1024 * 1024
MAX_FREE = 100 * MB            # обычный пользователь — 100 МБ
MAX_PREM = 1024 * MB           # Premium — 1 ГБ
MAX_OWNER = 20 * 1024 * MB     # роль owner — 20 ГБ
ANON_NUMBER_COUNT = 500        # размер биржи анонимных номеров

app = FastAPI()
pool: asyncpg.Pool = None
live: dict[int, set[WebSocket]] = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    pw_hash TEXT NOT NULL,
    token TEXT UNIQUE,
    becoins INT NOT NULL DEFAULT 0,
    premium_until BIGINT NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'user',
    bio TEXT NOT NULL DEFAULT '',
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS usernames(
    uname TEXT PRIMARY KEY,
    owner_id INT NOT NULL REFERENCES users(id),
    is_primary BOOLEAN NOT NULL DEFAULT false,
    for_sale_price INT,
    acquired_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages(
    id SERIAL PRIMARY KEY,
    frm INT NOT NULL, to_ INT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'text',
    text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT,
    meta JSONB, ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS channels(
    id SERIAL PRIMARY KEY,
    uname TEXT UNIQUE NOT NULL, title TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '',
    owner_id INT NOT NULL REFERENCES users(id),
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS channel_subs(
    channel_id INT REFERENCES channels(id),
    user_id INT REFERENCES users(id),
    PRIMARY KEY(channel_id, user_id)
);
CREATE TABLE IF NOT EXISTS channel_posts(
    id SERIAL PRIMARY KEY,
    channel_id INT NOT NULL REFERENCES channels(id),
    kind TEXT NOT NULL DEFAULT 'text',
    text TEXT, file_path TEXT, file_name TEXT, file_size BIGINT,
    ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS bots(
    id SERIAL PRIMARY KEY,
    owner_id INT NOT NULL REFERENCES users(id),
    bot_username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
    api_token TEXT UNIQUE NOT NULL, created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_codes(
    code TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    amount INT NOT NULL,
    uses_left INT NOT NULL
);
CREATE TABLE IF NOT EXISTS promo_redemptions(
    code TEXT NOT NULL REFERENCES promo_codes(code),
    user_id INT NOT NULL REFERENCES users(id),
    PRIMARY KEY(code, user_id)
);
"""
# Новые колонки добавляй сюда — ADD COLUMN IF NOT EXISTS никогда не трогает
# существующие данные, можно безопасно катить на прод-базу повторно.
ALTERS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen BIGINT NOT NULL DEFAULT 0",
]


def now(): return int(time.time())
def tok(n=40): return secrets.token_hex(n // 2)


async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as con:
        for stmt in filter(None, (s.strip() for s in SCHEMA.split(";"))):
            await con.execute(stmt)
        for stmt in ALTERS:
            await con.execute(stmt)
        have = await con.fetchval("SELECT count(*) FROM usernames WHERE uname LIKE 'n:%'")
        missing = ANON_NUMBER_COUNT - have
        if missing > 0:
            seen = set()
            while len(seen) < missing:
                seen.add("n:" + "".join(random.choice(string.digits) for _ in range(9)))
            await con.executemany(
                "INSERT INTO usernames(uname,owner_id,for_sale_price,acquired_at) VALUES($1,0,$2,$3) ON CONFLICT DO NOTHING",
                [(n, random.choice([2500, 5000, 7500, 9000, 15000]), now()) for n in seen])


@app.on_event("startup")
async def startup():
    await init_db()


def upload_limit(u) -> int:
    if u["role"] == "owner":
        return MAX_OWNER
    if u["premium_until"] > now():
        return MAX_PREM
    return MAX_FREE


async def auth(authorization: str = Header(None), x_token: str = Header(None)):
    t = x_token or (authorization.split(" ")[-1] if authorization else None)
    if not t:
        raise HTTPException(401, "Нужен вход")
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", t)
    if not u:
        raise HTTPException(401, "Нужен вход")
    return u


async def public_user(u, con) -> dict:
    extras = [r["uname"] for r in await con.fetch(
        "SELECT uname FROM usernames WHERE owner_id=$1 AND is_primary=false", u["id"])]
    return dict(id=u["id"], username=u["username"], name=u["name"], bio=u["bio"],
                premium=u["premium_until"] > now(),
                premium_until=u["premium_until"], role=u["role"],
                becoins=u["becoins"], upload_limit_mb=upload_limit(u) // MB,
                extra_usernames=extras)


# ---------- schemas ----------
class RegisterIn(BaseModel):
    username: str; name: str; password: str
class LoginIn(BaseModel):
    username: str; password: str
class DMIn(BaseModel):
    to: int; text: str
class SellIn(BaseModel):
    uname: str; price: int
class GiftUnameIn(BaseModel):
    uname: str; to: int
class PromoIn(BaseModel):
    code: str
class ChanIn(BaseModel):
    uname: str; title: str; bio: str = ""
class PostIn(BaseModel):
    text: str
class BotIn(BaseModel):
    name: str; bot_username: str


# ---------- auth ----------
@app.post("/api/register")
async def register(b: RegisterIn):
    u = b.username.strip().lower()
    if not (5 <= len(u) <= 32) or not u[0].isalpha() or not all(c.isalnum() or c == "_" for c in u):
        raise HTTPException(400, "Юзернейм: латиница/цифры/_, от 5 символов, начинается с буквы")
    if len(b.password) < 4:
        raise HTTPException(400, "Пароль минимум 4 символа")
    async with pool.acquire() as con, con.transaction():
        if await con.fetchval("SELECT 1 FROM usernames WHERE uname=$1", u):
            raise HTTPException(400, "Юзернейм занят")
        t = tok()
        uid = await con.fetchval(
            "INSERT INTO users(username,name,pw_hash,token,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id",
            u, b.name.strip()[:40] or u, bcrypt.hash(b.password), t, now())
        await con.execute(
            "INSERT INTO usernames(uname,owner_id,is_primary,acquired_at) VALUES($1,$2,true,$3)",
            u, uid, now())
    return {"token": t}


@app.post("/api/login")
async def login(b: LoginIn):
    u = b.username.strip().lower().lstrip("@")
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT owner_id FROM usernames WHERE uname=$1", u)
        if not row:
            raise HTTPException(403, "Такого аккаунта нет")
        acc = await con.fetchrow("SELECT * FROM users WHERE id=$1", row["owner_id"])
        if not bcrypt.verify(b.password, acc["pw_hash"]):
            raise HTTPException(403, "Неверный пароль")
        t = tok()
        await con.execute("UPDATE users SET token=$1, last_seen=$2 WHERE id=$3", t, now(), acc["id"])
    return {"token": t}


@app.get("/api/me")
async def me(u=Depends(auth)):
    async with pool.acquire() as con:
        return await public_user(u, con)


# ---------- бекоины / промокоды / премиум ----------
@app.post("/api/promo/redeem")
async def promo_redeem(b: PromoIn, u=Depends(auth)):
    code = b.code.strip().upper()
    async with pool.acquire() as con, con.transaction():
        p = await con.fetchrow("SELECT * FROM promo_codes WHERE code=$1 FOR UPDATE", code)
        if not p or p["uses_left"] < 1:
            raise HTTPException(400, "Промокод не найден")
        if await con.fetchval("SELECT 1 FROM promo_redemptions WHERE code=$1 AND user_id=$2", code, u["id"]):
            raise HTTPException(400, "Уже использован тобой")
        await con.execute("UPDATE promo_codes SET uses_left=uses_left-1 WHERE code=$1", code)
        await con.execute("INSERT INTO promo_redemptions(code,user_id) VALUES($1,$2)", code, u["id"])
        if p["kind"] == "becoins":
            await con.execute("UPDATE users SET becoins=becoins+$1 WHERE id=$2", p["amount"], u["id"])
        else:
            await con.execute(
                "UPDATE users SET premium_until=GREATEST(premium_until,$1)+$2 WHERE id=$3",
                now(), p["amount"] * 86400, u["id"])
    return {"ok": True}


# ---------- usernames / anon-number marketplace ----------
@app.get("/api/market")
async def market():
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT uname, for_sale_price FROM usernames WHERE for_sale_price IS NOT NULL")
    return [dict(kind="number" if r["uname"].startswith("n:") else "username",
                 value=r["uname"][2:] if r["uname"].startswith("n:") else r["uname"],
                 price=r["for_sale_price"]) for r in rows]


@app.post("/api/market/sell")
async def market_sell(b: SellIn, u=Depends(auth)):
    un = b.uname.strip().lower().lstrip("@")
    if b.price < 1:
        raise HTTPException(400, "Цена должна быть больше нуля")
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM usernames WHERE uname=$1", un)
        if not row or row["owner_id"] != u["id"]:
            raise HTTPException(400, "Это не твой юзернейм")
        if row["is_primary"]:
            raise HTTPException(400, "Нельзя продать основной юзернейм — сначала смени его")
        await con.execute("UPDATE usernames SET for_sale_price=$1 WHERE uname=$2", b.price, un)
    return {"ok": True}


@app.post("/api/market/unsell")
async def market_unsell(uname: str = Form(...), u=Depends(auth)):
    un = uname.strip().lower().lstrip("@")
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM usernames WHERE uname=$1", un)
        if not row or row["owner_id"] != u["id"]:
            raise HTTPException(400, "Это не твой юзернейм")
        await con.execute("UPDATE usernames SET for_sale_price=NULL WHERE uname=$1", un)
    return {"ok": True}


@app.post("/api/market/buy")
async def market_buy(uname: str = Form(...), u=Depends(auth)):
    un = uname.strip().lower().lstrip("@")
    async with pool.acquire() as con, con.transaction():
        row = await con.fetchrow("SELECT * FROM usernames WHERE uname=$1 FOR UPDATE", un)
        if not row or row["for_sale_price"] is None:
            raise HTTPException(400, "Лот не найден")
        price = row["for_sale_price"]
        bal = await con.fetchval(
            "UPDATE users SET becoins=becoins-$1 WHERE id=$2 AND becoins>=$1 RETURNING becoins", price, u["id"])
        if bal is None:
            raise HTTPException(400, "Не хватает бекоинов")
        if row["owner_id"]:
            await con.execute("UPDATE users SET becoins=becoins+$1 WHERE id=$2", price, row["owner_id"])
        await con.execute(
            "UPDATE usernames SET owner_id=$1, for_sale_price=NULL, acquired_at=$2 WHERE uname=$3",
            u["id"], now(), un)
    return {"becoins": bal}


@app.post("/api/username/gift")
async def username_gift(b: GiftUnameIn, u=Depends(auth)):
    un = b.uname.strip().lower().lstrip("@")
    async with pool.acquire() as con, con.transaction():
        row = await con.fetchrow("SELECT * FROM usernames WHERE uname=$1 FOR UPDATE", un)
        if not row or row["owner_id"] != u["id"]:
            raise HTTPException(400, "Это не твой юзернейм")
        if row["is_primary"]:
            raise HTTPException(400, "Нельзя подарить основной юзернейм")
        to = await con.fetchrow("SELECT * FROM users WHERE id=$1", b.to)
        if not to:
            raise HTTPException(404, "Получатель не найден")
        await con.execute(
            "UPDATE usernames SET owner_id=$1, for_sale_price=NULL, acquired_at=$2 WHERE uname=$3",
            b.to, now(), un)
        mid = await con.fetchval(
            "INSERT INTO messages(frm,to_,kind,meta,ts) VALUES($1,$2,'gift_username',$3,$4) RETURNING id",
            u["id"], b.to, {"uname": un, "to_name": to["name"]}, now())
    await push([u["id"], b.to], {"type": "msg", "msg": dict(
        id=mid, frm=u["id"], to=b.to, kind="gift_username", meta={"uname": un, "to_name": to["name"]}, ts=now())})
    return {"ok": True}


@app.get("/api/username/check")
async def username_check(v: str, u=Depends(auth)):
    un = v.strip().lower().lstrip("@")
    if not (5 <= len(un) <= 32) or not un[0].isalpha() or not all(c.isalnum() or c == "_" for c in un):
        return {"status": "invalid", "label": "Неверный формат"}
    async with pool.acquire() as con:
        row = await con.fetchrow("SELECT * FROM usernames WHERE uname=$1", un)
        ch = await con.fetchval("SELECT 1 FROM channels WHERE uname=$1", un)
    if un == u["username"]:
        return {"status": "self", "label": "Это твой юзернейм"}
    if ch:
        return {"status": "taken_channel", "label": "Занят каналом"}
    if row and row["for_sale_price"] is not None:
        return {"status": "for_sale", "label": f"На бирже за ◈ {row['for_sale_price']}", "price": row["for_sale_price"]}
    if row:
        return {"status": "taken_user", "label": "Занят пользователем"}
    return {"status": "free", "label": "Свободен"}


# ---------- DM ----------
async def push(uids, payload):
    for uid in set(uids):
        for ws in list(live.get(uid, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                live[uid].discard(ws)


@app.get("/api/chat/{peer_id}")
async def chat(peer_id: int, u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT * FROM messages WHERE (frm=$1 AND to_=$2) OR (frm=$2 AND to_=$1) ORDER BY id", u["id"], peer_id)
    return [dict(r) for r in rows]


@app.post("/api/dm/send")
async def dm_send(b: DMIn, u=Depends(auth)):
    if not b.text.strip():
        raise HTTPException(400, "Пусто")
    async with pool.acquire() as con:
        mid = await con.fetchval(
            "INSERT INTO messages(frm,to_,kind,text,ts) VALUES($1,$2,'text',$3,$4) RETURNING id",
            u["id"], b.to, b.text[:4000], now())
    msg = dict(id=mid, frm=u["id"], to=b.to, kind="text", text=b.text[:4000], ts=now())
    await push([u["id"], b.to], {"type": "msg", "msg": msg})
    return {"ok": True}


# ---------- файлы: обычный файл, голосовое, видео-кружок — один эндпоинт ----------
@app.post("/api/upload")
async def upload(to: int = Form(...), kind: str = Form("file"), file: UploadFile = File(...), u=Depends(auth)):
    limit = upload_limit(u)
    dest_dir = UP_DIR / str(u["id"]); dest_dir.mkdir(exist_ok=True)
    name = f"{int(time.time()*1000)}_{secrets.token_hex(4)}_{file.filename}"
    dest = dest_dir / name
    size = 0
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
        mid = await con.fetchval(
            "INSERT INTO messages(frm,to_,kind,file_path,file_name,file_size,ts) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",
            u["id"], to, k, rel, file.filename, size, now())
    msg = dict(id=mid, frm=u["id"], to=to, kind=k, file_path=rel, file_name=file.filename, file_size=size, ts=now())
    await push([u["id"], to], {"type": "msg", "msg": msg})
    return msg


@app.get("/files/{uid}/{name}")
def get_file(uid: int, name: str):
    p = UP_DIR / str(uid) / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


# ---------- каналы ----------
@app.post("/api/channels")
async def channel_create(b: ChanIn, u=Depends(auth)):
    un = b.uname.strip().lower().lstrip("@")
    async with pool.acquire() as con, con.transaction():
        if await con.fetchval("SELECT 1 FROM usernames WHERE uname=$1", un) or \
           await con.fetchval("SELECT 1 FROM channels WHERE uname=$1", un):
            raise HTTPException(400, "Юзернейм канала занят")
        cid = await con.fetchval(
            "INSERT INTO channels(uname,title,owner_id,bio,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id",
            un, b.title[:64], u["id"], b.bio[:200], now())
        await con.execute("INSERT INTO channel_subs(channel_id,user_id) VALUES($1,$2)", cid, u["id"])
    return {"id": cid, "uname": un}


@app.post("/api/channels/{cid}/subscribe")
async def channel_sub(cid: int, u=Depends(auth)):
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO channel_subs(channel_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING", cid, u["id"])
    return {"ok": True}


@app.post("/api/channels/{cid}/post")
async def channel_post(cid: int, b: PostIn, u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
        if not ch or ch["owner_id"] != u["id"]:
            raise HTTPException(403, "Постить может только владелец канала")
        pid = await con.fetchval(
            "INSERT INTO channel_posts(channel_id,kind,text,ts) VALUES($1,'text',$2,$3) RETURNING id",
            cid, b.text[:4000], now())
    return {"id": pid}


@app.post("/api/channels/{cid}/upload")
async def channel_upload(cid: int, kind: str = Form("file"), file: UploadFile = File(...), u=Depends(auth)):
    async with pool.acquire() as con:
        ch = await con.fetchrow("SELECT * FROM channels WHERE id=$1", cid)
    if not ch or ch["owner_id"] != u["id"]:
        raise HTTPException(403, "Постить может только владелец канала")
    limit = upload_limit(u)
    dest_dir = UP_DIR / "ch" / str(cid); dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time()*1000)}_{secrets.token_hex(4)}_{file.filename}"
    dest = dest_dir / name
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(4 * MB):
            size += len(chunk)
            if size > limit:
                out.close(); dest.unlink(missing_ok=True)
                raise HTTPException(413, "Файл больше лимита")
            out.write(chunk)
    rel = f"/files/ch/{cid}/{name}"
    k = kind if kind in ("file", "voice", "circle") else "file"
    async with pool.acquire() as con:
        pid = await con.fetchval(
            "INSERT INTO channel_posts(channel_id,kind,file_path,file_name,file_size,ts) VALUES($1,$2,$3,$4,$5,$6) RETURNING id",
            cid, k, rel, file.filename, size, now())
    return {"id": pid, "file_path": rel}


@app.get("/files/ch/{cid}/{name}")
def get_channel_file(cid: int, name: str):
    p = UP_DIR / "ch" / str(cid) / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/channels/{cid}/posts")
async def channel_posts(cid: int):
    async with pool.acquire() as con:
        rows = await con.fetch("SELECT * FROM channel_posts WHERE channel_id=$1 ORDER BY id DESC LIMIT 100", cid)
    return [dict(r) for r in rows]


# ---------- BotFather ----------
@app.post("/api/bots")
async def create_bot(b: BotIn, u=Depends(auth)):
    un = b.bot_username.strip().lower().lstrip("@")
    if not un.endswith("bot"):
        raise HTTPException(400, "Юзернейм бота должен заканчиваться на 'bot'")
    async with pool.acquire() as con, con.transaction():
        if await con.fetchval("SELECT 1 FROM usernames WHERE uname=$1", un) or \
           await con.fetchval("SELECT 1 FROM bots WHERE bot_username=$1", un):
            raise HTTPException(400, "Юзернейм занят")
        token = f"{random.randint(10**8,10**9-1)}:{secrets.token_urlsafe(27)}"
        bid = await con.fetchval(
            "INSERT INTO bots(owner_id,bot_username,name,api_token,created_at) VALUES($1,$2,$3,$4,$5) RETURNING id",
            u["id"], un, b.name[:40], token, now())
    return {"id": bid, "username": un, "token": token,
            "api_base": f"https://belugacord.duckdns.org/{un}/token={token}"}


@app.get("/api/bots")
async def my_bots(u=Depends(auth)):
    async with pool.acquire() as con:
        rows = await con.fetch(
            "SELECT bot_username, name, api_token, created_at FROM bots WHERE owner_id=$1", u["id"])
    return [dict(r) for r in rows]


@app.post("/{bot_username}/token={token}")
async def bot_api(bot_username: str, token: str, payload: dict):
    """POST https://belugacord.duckdns.org/<bot_username>/token=<api_token>
    body: {"method":"sendMessage","to":<user_id>,"text":"..."}"""
    async with pool.acquire() as con:
        bot = await con.fetchrow("SELECT * FROM bots WHERE bot_username=$1 AND api_token=$2", bot_username, token)
        if not bot:
            raise HTTPException(401, "Неверный токен бота")
        if payload.get("method") == "sendMessage":
            to = int(payload["to"]); text = str(payload.get("text", ""))[:4000]
            mid = await con.fetchval(
                "INSERT INTO messages(frm,to_,kind,text,ts) VALUES(0,$1,'text',$2,$3) RETURNING id",
                to, f"🤖 @{bot_username}: {text}", now())
    if payload.get("method") == "sendMessage":
        await push([to], {"type": "msg", "msg": dict(id=mid, frm=0, to=to, kind="text", text=text, ts=now())})
        return {"ok": True}
    raise HTTPException(400, "Неизвестный метод")


# ---------- овнерка: выдать/забрать бекоины, премиум, роль; создать промокод ----------
class OwnerCoinsIn(BaseModel):
    user_id: int; amount: int
class OwnerPremIn(BaseModel):
    user_id: int; days: int
class OwnerRoleIn(BaseModel):
    user_id: int; role: str
class OwnerPromoIn(BaseModel):
    code: str; kind: str; amount: int; uses: int


def require_owner(u):
    if u["role"] != "owner":
        raise HTTPException(403, "Только для владельца")


@app.post("/api/owner/coins")
async def owner_coins(b: OwnerCoinsIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        bal = await con.fetchval(
            "UPDATE users SET becoins=GREATEST(0,becoins+$1) WHERE id=$2 RETURNING becoins", b.amount, b.user_id)
    return {"becoins": bal}


@app.post("/api/owner/premium")
async def owner_premium(b: OwnerPremIn, u=Depends(auth)):
    require_owner(u)
    async with pool.acquire() as con:
        if b.days <= 0:
            until = await con.fetchval("UPDATE users SET premium_until=0 WHERE id=$1 RETURNING premium_until", b.user_id)
        else:
            until = await con.fetchval(
                "UPDATE users SET premium_until=GREATEST(premium_until,$1)+$2 WHERE id=$3 RETURNING premium_until",
                now(), b.days * 86400, b.user_id)
    return {"premium_until": until}


@app.post("/api/owner/role")
async def owner_role(b: OwnerRoleIn, u=Depends(auth)):
    require_owner(u)
    if b.role not in ("user", "admin", "owner"):
        raise HTTPException(400, "Роль: user/admin/owner")
    async with pool.acquire() as con:
        await con.execute("UPDATE users SET role=$1 WHERE id=$2", b.role, b.user_id)
    return {"ok": True}


@app.post("/api/owner/promo")
async def owner_promo(b: OwnerPromoIn, u=Depends(auth)):
    require_owner(u)
    if b.kind not in ("becoins", "premium_days"):
        raise HTTPException(400, "kind: becoins/premium_days")
    async with pool.acquire() as con:
        await con.execute(
            "INSERT INTO promo_codes(code,kind,amount,uses_left) VALUES($1,$2,$3,$4) "
            "ON CONFLICT (code) DO UPDATE SET kind=$2, amount=$3, uses_left=$4",
            b.code.strip().upper(), b.kind, b.amount, b.uses)
    return {"ok": True}


# ---------- WebSocket: доставка сообщений + сигналинг звонков ----------
@app.websocket("/ws")
async def ws(sock: WebSocket, token: str):
    async with pool.acquire() as con:
        u = await con.fetchrow("SELECT * FROM users WHERE token=$1", token)
    if not u:
        return await sock.close()
    await sock.accept()
    live.setdefault(u["id"], set()).add(sock)
    try:
        while True:
            data = await sock.receive_json()
            if data.get("type") in ("call-offer", "call-answer", "ice", "call-end"):
                data["frm"] = u["id"]
                await push([data["to"]], data)
    except WebSocketDisconnect:
        live[u["id"]].discard(sock)


@app.get("/", response_class=HTMLResponse)
def index():
    return open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read()