# BELUGACORD 2.5 — api/core.py
# Auth, profile, email, version, release, upload, themes, titles, commands
import os, json, random, time, datetime, secrets
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from api._shared import (
    get_pool, get_current_user, hash_password, verify_password,
    make_token, user_public, is_valid_email, send_email, is_premium,
    get_role, online_users, manager,
    EMAIL_CODE_TTL_MINUTES, EMAIL_CODE_MAX_ATTEMPTS, EMAIL_RESEND_COOLDOWN,
    CURRENT_VERSION, CHANGELOG, ACHIEVEMENTS, LIMITS, email_last_sent
)

router = APIRouter()

UPLOAD_DIR = "uploads"

# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ РЕЛИЗА (hot-swap)
# ============================================================
RELEASE_STATE = {
    "current_version": CURRENT_VERSION,
    "target_version": CURRENT_VERSION,
    "notes": "",
    "force": False,
    "active": False
}

# ============================================================
# CHANGELOG / ACHIEVEMENTS
# ============================================================
@router.get("/changelog")
async def changelog():
    return {"current": CURRENT_VERSION, "all": CHANGELOG}

@router.get("/achievements/all")
async def achievements_all():
    return ACHIEVEMENTS

# ============================================================
# CHECK USERNAME
# ============================================================
@router.get("/check_username")
async def check_username(username: str):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE username=$1", username)
    return {"available": row is None}

# ============================================================
# REGISTER
# ============================================================
@router.post("/register")
async def register(data: dict):
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    em = (data.get("email") or "").strip() or None
    ref = (data.get("referrer") or "").strip()[:32] or None

    if len(u) < 2 or len(u) > 32: raise HTTPException(400, "Ник 2-32")
    if len(pw) < 4: raise HTTPException(400, "Пароль мин 4")
    if em and not is_valid_email(em): raise HTTPException(400, "Плохой email")

    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM users WHERE username=$1", u):
            raise HTTPException(400, "Занят")
        row = await conn.fetchrow(
            "INSERT INTO users(username,password_hash,email,is_admin,referred_by) VALUES($1,$2,$3,$4,$5) RETURNING *",
            u, hash_password(pw), em, u == "_fan_beluga_", ref
        )
    if em:
        code = str(random.randint(100000, 999999))
        try:
            async with p.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET email_code=$1, email_code_expires=NOW()+INTERVAL '1 minute' * $2, email_code_attempts=0 WHERE id=$3",
                    code, EMAIL_CODE_TTL_MINUTES, row["id"]
                )
        except:
            pass
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

# ============================================================
# LOGIN
# ============================================================
@router.post("/login")
async def login(data: dict):
    u = (data.get("username") or "").strip()
    pw = data.get("password") or ""
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username=$1", u)
    if not row or not verify_password(pw, row["password_hash"]):
        raise HTTPException(400, "Неверный ник/пароль")
    if row["is_banned"]:
        raise HTTPException(403, row.get("ban_reason") or "Забанен")
    return {"token": make_token(row["id"], row["username"]), "user": user_public(row, row["id"])}

# ============================================================
# ME
# ============================================================
@router.get("/me")
async def me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return user_public(user, user["id"])

# ============================================================
# UPDATE PROFILE
# ============================================================
@router.post("/update_profile")
async def update_profile(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    premium = is_premium(user)
    gif_av = data.get("gif_avatar")
    gif_bn = data.get("gif_banner")
    if (gif_av or gif_bn) and not premium:
        raise HTTPException(403, "GIF только для премиума")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET
            avatar=COALESCE($1,avatar), banner=COALESCE($2,banner),
            gif_avatar=COALESCE($3,gif_avatar), gif_banner=COALESCE($4,gif_banner),
            avatar_pos=COALESCE($5,avatar_pos), banner_pos=COALESCE($6,banner_pos),
            nickname_color=$7, nickname_gradient=$8,
            bio=COALESCE($9,bio), fav_music=COALESCE($10,fav_music),
            wallpaper=COALESCE($11,wallpaper), font_choice=$12,
            compact_mode=COALESCE($13,compact_mode), custom_status=COALESCE($14,custom_status)
            WHERE id=$15""",
            data.get("avatar"), data.get("banner"), gif_av, gif_bn,
            data.get("avatar_pos"), data.get("banner_pos"),
            data.get("nickname_color"), data.get("nickname_gradient"),
            data.get("bio"), data.get("fav_music"),
            data.get("wallpaper"), data.get("font_choice"),
            data.get("compact_mode"), data.get("custom_status"),
            user["id"])
    return {"ok": True}

# ============================================================
# STATUS
# ============================================================
@router.post("/user/status")
async def set_status(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    st = data.get("online_status", "online")
    if st not in ("online", "dnd", "invisible"):
        raise HTTPException(400, "online/dnd/invisible")
    custom = (data.get("custom_status") or "")[:64]
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "UPDATE users SET online_status=$1, custom_status=$2 WHERE id=$3",
            st, custom or None, user["id"]
        )
    await manager.broadcast({
        "type": "status_update", "user_id": user["id"],
        "online_status": st, "custom_status": custom or None
    })
    return {"ok": True}

# ============================================================
# GET USER PUBLIC
# ============================================================
@router.get("/user/{user_id}")
async def get_user(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT id,username,avatar,banner,gif_avatar,gif_banner,
            avatar_pos,banner_pos,is_admin,is_moderator,is_beta_tester,is_scam,is_dev,is_streamer,
            premium_tier,premium_expires,nickname_color,nickname_gradient,bio,fav_music,
            custom_status,online_status,messages_count,is_legend,achievements,social_rating,
            coins,quest_points,active_frame,title,reputation,level,xp,created_at,last_seen
            FROM users WHERE id=$1""", user_id)
    if not row: raise HTTPException(404, "Не найден")
    d = dict(row)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["last_seen"] = d["last_seen"].isoformat() if d.get("last_seen") else None
    d["premium_expires"] = d["premium_expires"].isoformat() if d.get("premium_expires") else None
    d["role"] = get_role(row)
    d["is_premium"] = is_premium(row)
    d["online"] = user_id in online_users and (row.get("online_status") or "online") != "invisible"
    d["achievements"] = json.loads(row.get("achievements") or "[]")
    return d

# ============================================================
# SEARCH USERS
# ============================================================
@router.get("/users/search")
async def users_search(q: str, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    q = (q or "").strip()
    if len(q) < 2: return []
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,username,avatar,gif_avatar,is_admin,is_moderator,
            is_beta_tester,is_scam,is_dev,is_streamer,premium_tier,premium_expires,online_status,title
            FROM users WHERE username ILIKE $1 AND id!=$2 ORDER BY username LIMIT 20""",
            f"%{q}%", user["id"])
    out = []
    for r in rows:
        d = dict(r)
        d["role"] = get_role(r)
        d["is_premium"] = is_premium(r)
        d["online"] = r["id"] in online_users
        out.append(d)
    return out

# ============================================================
# EMAIL — SEND CODE
# ============================================================
@router.post("/email/send_code")
async def email_send_code(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    em = (data.get("email") or "").strip()
    if not is_valid_email(em): raise HTTPException(400, "Плохой email")
    uid = user["id"]
    now = time.time()
    last = email_last_sent.get(uid, 0)
    if now - last < EMAIL_RESEND_COOLDOWN:
        wait = int(EMAIL_RESEND_COOLDOWN - (now - last))
        raise HTTPException(429, f"Подожди {wait}с")
    email_last_sent[uid] = now
    code = str(random.randint(100000, 999999))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET email=$1, email_code=$2,
            email_code_expires=NOW()+INTERVAL '1 minute' * $3,
            email_code_attempts=0, email_verified=FALSE WHERE id=$4""",
            em, code, EMAIL_CODE_TTL_MINUTES, uid)
    r = await send_email(em, "Belugacord — подтверждение",
        f"<h2>Привет, {user['username']}!</h2><p>Код: <b style='font-size:24px;color:#d946ef'>{code}</b></p><p>Действует {EMAIL_CODE_TTL_MINUTES} минут.</p>")
    if r.get("ok"):
        return {"ok": True, "sent": True, "cooldown": EMAIL_RESEND_COOLDOWN}
    return {"ok": True, "sent": False, "code_hint": code, "cooldown": EMAIL_RESEND_COOLDOWN, "error": r.get("error", "")}

# ============================================================
# EMAIL — RESEND
# ============================================================
@router.post("/email/resend")
async def email_resend(data: dict):
    return await email_send_code(data)

# ============================================================
# EMAIL — VERIFY
# ============================================================
@router.post("/email/verify")
async def email_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    code = (data.get("code") or "").strip()
    if not code or len(code) != 6 or not code.isdigit():
        raise HTTPException(400, "Код — 6 цифр")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email_code,email_code_expires,email_code_attempts FROM users WHERE id=$1",
            user["id"]
        )
        if not row or not row["email_code"]:
            raise HTTPException(400, "Сначала запроси код")
        if row["email_code_expires"] and row["email_code_expires"] < datetime.datetime.now(datetime.timezone.utc):
            await conn.execute("UPDATE users SET email_code=NULL,email_code_expires=NULL WHERE id=$1", user["id"])
            raise HTTPException(400, "Код истёк. Запроси новый.")
        attempts = row["email_code_attempts"] or 0
        if attempts >= EMAIL_CODE_MAX_ATTEMPTS:
            await conn.execute("""UPDATE users SET email_code=NULL,email_code_expires=NULL,
                email_code_attempts=0 WHERE id=$1""", user["id"])
            raise HTTPException(400, "Слишком много попыток. Запроси новый код.")
        if row["email_code"] != code:
            await conn.execute("UPDATE users SET email_code_attempts=email_code_attempts+1 WHERE id=$1", user["id"])
            left = EMAIL_CODE_MAX_ATTEMPTS - attempts - 1
            raise HTTPException(400, f"Неверный код. Осталось попыток: {left}")
        await conn.execute("""UPDATE users SET email_verified=TRUE,email_code=NULL,
            email_code_expires=NULL,email_code_attempts=0 WHERE id=$1""", user["id"])
    return {"ok": True}

# ============================================================
# EMAIL — STATUS
# ============================================================
@router.get("/email/status")
async def email_status(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"email": user.get("email"), "verified": bool(user.get("email_verified"))}

# ============================================================
# VERSION (hot-swap — читается фронтом)
# ============================================================
@router.get("/version")
async def version():
    return RELEASE_STATE

# ============================================================
# UPLOAD FILE
# ============================================================
@router.post("/upload")
async def upload(token: str = Form(...), file: UploadFile = File(...)):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    lim = LIMITS.get(user.get("premium_tier"), LIMITS[None])["file"]
    content = await file.read()
    if len(content) > lim: raise HTTPException(400, "Файл большой")
    ext = os.path.splitext(file.filename or "")[1][:8]
    name = f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
        f.write(content)
    return {"url": f"/uploads/{name}"}

# ============================================================
# THEMES
# ============================================================
@router.get("/themes/list")
async def themes_list():
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("SELECT id,name,emoji,vars,bg_image,border_radius,blur FROM custom_themes ORDER BY id DESC")
        return [{"id":r["id"], "name":r["name"], "emoji":r["emoji"],
                 "vars":json.loads(r["vars"] or "{}"), "bg_image":r["bg_image"],
                 "border_radius":r["border_radius"], "blur":r["blur"]} for r in rows]
    except:
        return []

# ============================================================
# TITLES
# ============================================================
TITLES_DEFAULT = [
    {"name": "Легенда", "emoji": "🏅"},
    {"name": "Стример", "emoji": "🎥"},
    {"name": "Олдфаг", "emoji": "👴"},
    {"name": "Бета", "emoji": "🧪"},
    {"name": "Админ", "emoji": "🛡️"},
    {"name": "Меценат", "emoji": "💰"}
]

@router.get("/titles/list")
async def titles_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT title FROM users WHERE title IS NOT NULL")
    all_titles = TITLES_DEFAULT[:]
    for r in rows:
        if r["title"] and not any(t["name"] == r["title"] for t in all_titles):
            all_titles.append({"name": r["title"], "emoji": "⭐"})
    return all_titles

@router.post("/titles/set")
async def titles_set(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    title = (data.get("title") or "").strip()[:32]
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2", title or None, user["id"])
    return {"ok": True}

# ============================================================
# COMMANDS
# ============================================================
@router.get("/commands/list")
async def commands_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id,name,description FROM commands ORDER BY name")
    return [dict(r) for r in rows]

# ============================================================
# CUSTOM REACTIONS
# ============================================================
@router.get("/reactions/custom/list")
async def custom_reactions_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id,url FROM custom_reactions WHERE user_id=$1 ORDER BY id DESC", user["id"])
    return [dict(r) for r in rows]

@router.post("/reactions/custom/add")
async def custom_reactions_add(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    url = (data.get("url") or "").strip()
    if not url: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        cnt = await conn.fetchval("SELECT COUNT(*) FROM custom_reactions WHERE user_id=$1", user["id"])
        if cnt >= 5: raise HTTPException(400, "Макс 5")
        await conn.execute("INSERT INTO custom_reactions(user_id,url) VALUES($1,$2)", user["id"], url)
    return {"ok": True}

# ============================================================
# BLOCKS
# ============================================================
@router.post("/blocks/add")
async def blocks_add(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id", 0))
    if tid == user["id"]: raise HTTPException(400, "Себя нельзя")
    p = await get_pool()
    async with p.acquire() as conn:
        try:
            await conn.execute("INSERT INTO blocks(blocker,blocked) VALUES($1,$2)", user["id"], tid)
        except:
            pass
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], tid)
        await conn.execute("DELETE FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], tid)
    return {"ok": True}

@router.post("/blocks/remove")
async def blocks_remove(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM blocks WHERE blocker=$1 AND blocked=$2", user["id"], tid)
    return {"ok": True}

@router.get("/blocks/list")
async def blocks_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT b.blocked AS id, u.username, u.avatar FROM blocks b
            JOIN users u ON u.id=b.blocked WHERE b.blocker=$1 ORDER BY b.created_at DESC""", user["id"])
    return [dict(r) for r in rows]

# ============================================================
# REPUTATION
# ============================================================
@router.post("/rep/give")
async def rep_give(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id", 0))
    if tid == user["id"]: raise HTTPException(400, "Себя нельзя")
    p = await get_pool()
    async with p.acquire() as conn:
        exists = await conn.fetchrow("""SELECT id FROM rep_given WHERE from_user=$1 AND to_user=$2
            AND created_at>NOW()-INTERVAL '24 hours'""", user["id"], tid)
        if exists: raise HTTPException(400, "Уже давал сегодня")
        await conn.execute("INSERT INTO rep_given(from_user,to_user) VALUES($1,$2)", user["id"], tid)
        await conn.execute("UPDATE users SET reputation=reputation+1 WHERE id=$1", tid)
    await manager.send_to(tid, {"type": "rep_update", "from": user["username"]})
    return {"ok": True}

# ============================================================
# REPORTS / APPEALS
# ============================================================
@router.post("/reports/submit")
async def report_submit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    txt = (data.get("text") or "").strip()
    if not txt: raise HTTPException(400, "Опиши")
    tid = data.get("target_id")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO reports(from_user,target_user,text) VALUES($1,$2,$3)",
            user["id"], tid, txt
        )
    return {"ok": True}

@router.post("/appeal/submit")
async def appeal_submit(data: dict):
    u = (data.get("username") or "").strip()
    t = (data.get("text") or "").strip()
    if not u or not t: raise HTTPException(400, "Заполни")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO ban_appeals(username,text) VALUES($1,$2)", u, t)
    return {"ok": True}

# ============================================================
# PREMIUM
# ============================================================
@router.get("/premium/status")
async def premium_status(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {
        "is_premium": is_premium(user),
        "tier": user.get("premium_tier"),
        "expires": user["premium_expires"].isoformat() if user.get("premium_expires") else None
    }

@router.post("/premium/buy")
async def premium_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    plan = data.get("plan", "month")
    from api._shared import PREMIUM_PRICES
    if plan not in PREMIUM_PRICES: raise HTTPException(400, "Нет такого плана")
    price = PREMIUM_PRICES[plan]
    days = 30 if plan == "month" else 365
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT coins,premium_expires FROM users WHERE id=$1", user["id"])
        if (row["coins"] or 0) < price:
            raise HTTPException(400, f"Нужно {price} 🏅")
        now = datetime.datetime.now(datetime.timezone.utc)
        base = row["premium_expires"] if row["premium_expires"] and row["premium_expires"] > now else now
        new_exp = base + datetime.timedelta(days=days)
        await conn.execute("""UPDATE users SET coins=coins-$1,
            premium_tier='premium', premium_expires=$2 WHERE id=$3""",
            price, new_exp, user["id"])
        await conn.execute("""INSERT INTO premium_log(user_id,tier,days,paid_coins,method)
            VALUES($1,'premium',$2,$3,'coins')""", user["id"], days, price)
    return {"ok": True, "premium_until": new_exp.isoformat(), "days": days, "price": price}

# ============================================================
# FRAMES
# ============================================================
@router.get("/frames/list")
async def frames_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM frames_catalog ORDER BY is_premium, price_coins, price_kp")
        owned = json.loads(user.get("frame_owned") or "[]")
    return [{"frame_id":r["frame_id"], "name":r["name"], "emoji":r["emoji"], "css":r["css"],
             "is_animated":r["is_animated"], "is_premium":r["is_premium"],
             "price_coins":r["price_coins"], "price_kp":r["price_kp"],
             "owned": r["frame_id"] in owned or r["frame_id"] == "none"} for r in rows]

@router.post("/frames/buy")
async def frames_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    fid = data.get("frame_id")
    p = await get_pool()
    async with p.acquire() as conn:
        f = await conn.fetchrow("SELECT * FROM frames_catalog WHERE frame_id=$1", fid)
        if not f: raise HTTPException(404, "Нет рамки")
        owned = json.loads(user.get("frame_owned") or "[]")
        if fid in owned: raise HTTPException(400, "Уже есть")
        if f["is_premium"] and not is_premium(user):
            raise HTTPException(403, "Только для премиума")
        method = data.get("method", "coins")
        if method == "coins" and f["price_coins"]:
            if (user.get("coins") or 0) < f["price_coins"]:
                raise HTTPException(400, "Не хватает 🏅")
            await conn.execute("""UPDATE users SET coins=coins-$1, frame_owned=$2
                WHERE id=$3""", f["price_coins"], json.dumps(owned + [fid]), user["id"])
        elif method == "kp" and f["price_kp"]:
            if (user.get("quest_points") or 0) < f["price_kp"]:
                raise HTTPException(400, "Не хватает КП")
            await conn.execute("""UPDATE users SET quest_points=quest_points-$1,
                frame_owned=$2 WHERE id=$3""",
                f["price_kp"], json.dumps(owned + [fid]), user["id"])
        else:
            raise HTTPException(400, "Способ оплаты не подходит")
    return {"ok": True}

@router.post("/frames/set")
async def frames_set(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    fid = data.get("frame_id", "none")
    p = await get_pool()
    async with p.acquire() as conn:
        f = await conn.fetchrow("SELECT * FROM frames_catalog WHERE frame_id=$1", fid)
        if not f: raise HTTPException(404, "Нет рамки")
        if fid != "none":
            owned = json.loads(user.get("frame_owned") or "[]")
            if fid not in owned: raise HTTPException(403, "Не куплена")
            if f["is_premium"] and not is_premium(user):
                raise HTTPException(403, "Только для премиума")
        await conn.execute("UPDATE users SET active_frame=$1 WHERE id=$2",
            fid if fid != "none" else None, user["id"])
    return {"ok": True}

# ============================================================
# DAILY BONUS
# ============================================================
@router.post("/daily/bonus")
async def daily_bonus(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    from api._shared import check_daily_bonus
    r = await check_daily_bonus(user["id"])
    if not r.get("ok"):
        if r.get("reason") == "already":
            raise HTTPException(429, f"Через {r['next_in']} сек")
        raise HTTPException(400, r.get("reason", "Ошибка"))
    return r

# ============================================================
# QUESTS
# ============================================================
@router.get("/quests/list")
async def quests_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    from api._shared import QUEST_TEMPLATES, get_today_key
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""SELECT quest_day,quest_progress,quest_claimed,quest_points
            FROM users WHERE id=$1""", user["id"])
    today = get_today_key()
    prog = {}
    claimed = []
    if row["quest_day"] == today:
        prog = json.loads(row["quest_progress"] or "{}")
        claimed = json.loads(row["quest_claimed"] or "[]")
    result = []
    for q in QUEST_TEMPLATES:
        result.append({
            "key": q["key"], "name": q["name"], "desc": q["desc"], "emoji": q["emoji"],
            "goal": q["goal"], "reward_kp": q["reward_kp"],
            "progress": prog.get(q["key"], 0), "claimed": q["key"] in claimed
        })
    return {"quests": result, "quest_points": row["quest_points"] or 0}

@router.post("/quests/exchange")
async def quests_exchange(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    plan = data.get("plan")
    from api._shared import QUEST_EXCHANGE
    if plan not in QUEST_EXCHANGE: raise HTTPException(400, "Нет такого плана")
    info = QUEST_EXCHANGE[plan]
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT quest_points,premium_expires FROM users WHERE id=$1", user["id"])
        if (row["quest_points"] or 0) < info["cost"]:
            raise HTTPException(400, f"Нужно {info['cost']} КП")
        now = datetime.datetime.now(datetime.timezone.utc)
        base = row["premium_expires"] if row["premium_expires"] and row["premium_expires"] > now else now
        new_exp = base + datetime.timedelta(days=info["days"])
        await conn.execute("""UPDATE users SET quest_points=quest_points-$1,
            premium_tier='premium', premium_expires=$2 WHERE id=$3""",
            info["cost"], new_exp, user["id"])
    return {"ok": True, "premium_until": new_exp.isoformat(), "days": info["days"]}

# ============================================================
# LEVELS
# ============================================================
@router.get("/levels/me")
async def levels_me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {
        "level": user.get("level", 1),
        "xp": user.get("xp", 0),
        "next_xp": user.get("level", 1) * 100
    }

@router.get("/levels/leaders")
async def levels_leaders():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT username,level,xp FROM users
            ORDER BY level DESC, xp DESC LIMIT 20""")
    return [dict(r) for r in rows]

# ============================================================
# ACHIEVEMENTS ME
# ============================================================
@router.get("/achievements/me")
async def achievements_me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"achievements": json.loads(user.get("achievements") or "[]")}