# BELUGACORD 2.5 — api/admin.py (part 1/2)
# Admin, mod, ban_requests, abuse, users_full, promo, release
import json, random, datetime, secrets
from fastapi import APIRouter, HTTPException

from api._shared import (
    get_pool, get_current_user, is_premium, get_role, hash_password,
    verify_password, log_admin, log_suspicious, ADMIN_USERNAME, OWNER_PASSWORD,
    manager, online_users, has_abuse_access, abuse_timer_task_placeholder
)

router = APIRouter()

# ============================================================
# ADMINS — set_password / verify / stats / users / action
# ============================================================
@router.post("/admin/set_password")
async def admin_set_password(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    pw = data.get("password") or ""
    if len(pw) < 4: raise HTTPException(400, "Мин 4")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET admin_password=$1 WHERE id=$2", hash_password(pw), user["id"])
    return {"ok": True}

@router.post("/admin/verify")
async def admin_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    pw = data.get("password") or ""
    stored = user.get("admin_password")
    if stored and not verify_password(pw, stored): raise HTTPException(403, "Неверный")
    if not stored and pw != "12344321": raise HTTPException(403, "Установи пароль")
    return {"ok": True}

@router.get("/admin/stats")
async def admin_stats(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM users")
        s = await conn.fetchval("SELECT COUNT(*) FROM servers")
        m = await conn.fetchval("SELECT COUNT(*) FROM messages")
    return {"users": u, "servers": s, "messages": m, "online": len(online_users)}

@router.get("/admin/users")
async def admin_users(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,username,is_admin,is_moderator,is_beta_tester,
            is_scam,is_dev,is_streamer,premium_tier,is_banned,coins,social_rating,title
            FROM users ORDER BY id""")
    return [dict(r) for r in rows]

@router.post("/admin/action")
async def admin_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    tid = data.get("target_id")
    action = data.get("action")
    is_owner = user["username"] == ADMIN_USERNAME
    if action == "ban" and not is_owner: raise HTTPException(403, "Отправь заявку")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",
                data.get("reason", ""), tid)
        elif action == "unban":
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1", tid)
        elif action == "mute":
            d = int(data.get("duration", 3600))
            await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2", d, tid)
    await log_admin(user["id"], action, tid)
    if action == "ban":
        await manager.send_to(tid, {"type": "banned", "reason": data.get("reason", "")})
        await manager.kick(tid)
    return {"ok": True}

@router.get("/admin/reports")
async def admin_reports(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id,r.text,r.target_user,
            f.username AS from_username,t.username AS target_username
            FROM reports r LEFT JOIN users f ON f.id=r.from_user
            LEFT JOIN users t ON t.id=r.target_user
            WHERE r.status='pending' ORDER BY r.id DESC""")
    return [dict(r) for r in rows]

@router.get("/admin/appeals")
async def admin_appeals(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,username,text,created_at FROM ban_appeals
            WHERE status='pending' ORDER BY id DESC""")
    return [{"id":r["id"], "username":r["username"], "text":r["text"],
             "created_at":r["created_at"].isoformat()} for r in rows]

@router.get("/admin/logs")
async def admin_logs(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT l.id,l.action,l.details,l.created_at,
            a.username AS admin_name FROM admin_logs l
            LEFT JOIN users a ON a.id=l.admin_id ORDER BY l.id DESC LIMIT 100""")
    return [{"id":r["id"], "action":r["action"], "details":r["details"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None,
             "admin_name":r["admin_name"]} for r in rows]

@router.get("/admin/spam_alerts")
async def admin_spam_alerts(token: str):
    user = await get_current_user(token)
    if not user or not (user.get("is_admin") or user.get("is_moderator")):
        raise HTTPException(403, "Нет прав")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT sa.id,sa.user_id,sa.text_sample,sa.count,sa.created_at,
            u.username FROM spam_alerts sa LEFT JOIN users u ON u.id=sa.user_id
            ORDER BY sa.id DESC LIMIT 50""")
    return [{"id":r["id"], "user_id":r["user_id"], "username":r["username"],
             "text":r["text_sample"], "count":r["count"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@router.get("/admin/coin_requests")
async def admin_coin_requests(token: str):
    user = await get_current_user(token)
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT cr.id,cr.coins,cr.price,u.username FROM coin_requests cr
            JOIN users u ON u.id=cr.user_id WHERE cr.status='pending' ORDER BY cr.id DESC""")
    return [dict(r) for r in rows]

@router.post("/admin/coin_resolve")
async def admin_coin_resolve(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403, "Не админ")
    p = await get_pool()
    async with p.acquire() as conn:
        req = await conn.fetchrow("SELECT * FROM coin_requests WHERE id=$1", int(data.get("request_id", 0)))
        if not req: raise HTTPException(404, "Не найдено")
        if data.get("action") == "approve":
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", req["coins"], req["user_id"])
            await conn.execute("UPDATE coin_requests SET status='approved',resolved_at=NOW() WHERE id=$1", req["id"])
            await manager.send_to(req["user_id"], {"type": "coins_approved", "amount": req["coins"]})
        else:
            await conn.execute("UPDATE coin_requests SET status='rejected',resolved_at=NOW() WHERE id=$1", req["id"])
            await manager.send_to(req["user_id"], {"type": "coins_rejected"})
    return {"ok": True}

# ============================================================
# MOD
# ============================================================
async def _check_mod(user):
    if not user: raise HTTPException(401, "Не авторизован")
    if not (user.get("is_moderator") or user.get("is_admin") or user["username"] == ADMIN_USERNAME):
        raise HTTPException(403, "Нет прав")

@router.get("/mod/reports")
async def mod_reports(token: str):
    user = await get_current_user(token); await _check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT r.id,r.text,r.target_user,
            f.username AS from_username,t.username AS target_username
            FROM reports r LEFT JOIN users f ON f.id=r.from_user
            LEFT JOIN users t ON t.id=r.target_user
            WHERE r.status='pending' ORDER BY r.id DESC""")
    return [dict(r) for r in rows]

@router.post("/mod/mute")
async def mod_mute(data: dict):
    user = await get_current_user(data.get("token")); await _check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        m = int(data.get("minutes", 60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",
            m * 60, int(data.get("user_id", 0)))
    await log_admin(user["id"], "mod_mute", int(data.get("user_id", 0)), f"{m} min")
    return {"ok": True}

@router.post("/mod/warn")
async def mod_warn(data: dict):
    user = await get_current_user(data.get("token")); await _check_mod(user)
    await log_admin(user["id"], "warn", int(data.get("user_id", 0)), data.get("reason", ""))
    return {"ok": True}

@router.post("/mod/dismiss_report")
async def mod_dismiss(data: dict):
    user = await get_current_user(data.get("token")); await _check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE reports SET status='dismissed' WHERE id=$1", int(data.get("report_id", 0)))
    return {"ok": True}

@router.post("/mod/mute_by_name")
async def mod_mute_by_name(data: dict):
    user = await get_current_user(data.get("token")); await _check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        m = int(data.get("minutes", 60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",
            m * 60, t["id"])
    return {"ok": True}

@router.post("/mod/warn_by_name")
async def mod_warn_by_name(data: dict):
    user = await get_current_user(data.get("token")); await _check_mod(user)
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
    await log_admin(user["id"], "warn", t["id"], data.get("reason", ""))
    return {"ok": True}

# ============================================================
# BAN REQUESTS
# ============================================================
@router.post("/ban_requests/submit")
async def ban_requests_submit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] == ADMIN_USERNAME: raise HTTPException(400, "Владелец банит напрямую")
    if not (user.get("is_admin") or user.get("is_moderator")): raise HTTPException(403, "Нет прав")
    tid = int(data.get("target_id", 0))
    reason = (data.get("reason") or "").strip()
    evidence = (data.get("evidence") or "").strip()
    if not reason: raise HTTPException(400, "Причина")
    p = await get_pool()
    async with p.acquire() as conn:
        target = await conn.fetchrow("SELECT username FROM users WHERE id=$1", tid)
        if not target: raise HTTPException(404, "Не найден")
        if await conn.fetchrow("SELECT id FROM ban_requests WHERE target_user=$1 AND status='pending'", tid):
            raise HTTPException(400, "Заявка уже есть")
        await conn.execute("""INSERT INTO ban_requests(from_admin,target_user,reason,evidence)
            VALUES($1,$2,$3,$4)""", user["id"], tid, reason, evidence)
    try:
        async with p.acquire() as conn2:
            owner = await conn2.fetchrow("SELECT id FROM users WHERE username=$1", ADMIN_USERNAME)
            if owner:
                await manager.send_to(owner["id"], {
                    "type": "ban_request_new", "from": user["username"],
                    "target": target["username"], "reason": reason
                })
    except: pass
    return {"ok": True}

@router.get("/ban_requests/list")
async def ban_requests_list(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT br.id,br.reason,br.evidence,br.created_at,
            fa.username AS from_username,tu.username AS target_username,br.target_user
            FROM ban_requests br LEFT JOIN users fa ON fa.id=br.from_admin
            LEFT JOIN users tu ON tu.id=br.target_user
            WHERE br.status='pending' ORDER BY br.id DESC""")
    return [{"id":r["id"], "reason":r["reason"], "evidence":r["evidence"],
             "from_username":r["from_username"], "target_username":r["target_username"],
             "target_user":r["target_user"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@router.post("/ban_requests/resolve")
async def ban_requests_resolve(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    rid = int(data.get("request_id", 0))
    action = data.get("action")
    if action not in ("approve", "reject"): raise HTTPException(400, "approve/reject")
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM ban_requests WHERE id=$1 AND status='pending'", rid)
        if not r: raise HTTPException(404, "Нет заявки")
        if action == "approve":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",
                r["reason"], r["target_user"])
            await conn.execute("""UPDATE ban_requests SET status='approved',
                resolved_by=$1,resolved_at=NOW() WHERE id=$2""", user["id"], rid)
            try: await manager.send_to(r["from_admin"], {"type": "ban_request_resolved", "status": "approved"})
            except: pass
            try: await manager.send_to(r["target_user"], {"type": "banned", "reason": r["reason"]})
            except: pass
            await manager.kick(r["target_user"])
        else:
            await conn.execute("""UPDATE ban_requests SET status='rejected',
                resolved_by=$1,resolved_at=NOW() WHERE id=$2""", user["id"], rid)
    return {"ok": True}

# ============================================================
# ABUSE — access, online, random
# ============================================================
@router.get("/abuse/access")
async def abuse_access(token: str):
    user = await get_current_user(token)
    acc = await has_abuse_access(user)
    if not acc: return {"access": False}
    return {
        "access": True, "owner": acc.get("owner", False),
        "can_gift": acc.get("can_gift", False), "can_nft": acc.get("can_nft", False),
        "can_coins": acc.get("can_coins", False), "can_online": acc.get("can_online", False),
        "can_timer": acc.get("can_timer", False), "can_write": acc.get("can_write", True)
    }

@router.get("/abuse/online")
async def abuse_online(token: str):
    user = await get_current_user(token)
    acc = await has_abuse_access(user)
    if not acc or not acc.get("can_online"): raise HTTPException(403, "Нет доступа")
    p = await get_pool()
    async with p.acquire() as conn:
        if not online_users: return {"users": []}
        rows = await conn.fetch("SELECT id,username,avatar FROM users WHERE id=ANY($1::int[]) ORDER BY username",
            list(online_users))
    return {"users": [dict(r) for r in rows]}

@router.post("/abuse/random_gift")
async def abuse_random_gift(data: dict):
    user = await get_current_user(data.get("token"))
    acc = await has_abuse_access(user)
    if not acc or not acc.get("can_gift"): raise HTTPException(403, "Нет доступа")
    if not online_users: raise HTTPException(400, "Никого онлайн")
    from api._shared import get_all_gifts
    g = await get_all_gifts()
    if not g: raise HTTPException(400, "Нет подарков")
    tid = random.choice(list(online_users))
    gid = random.choice(list(g.keys()))
    gift = g[gid]
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT username FROM users WHERE id=$1", tid)
        if not t: raise HTTPException(404, "Пропал")
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",
            user["id"], tid, gid)
    await manager.send_to(tid, {
        "type": "gift_received", "gift_emoji": gift.get("emoji"),
        "gift_name": gift["name"], "gift_image": gift.get("image"),
        "from_name": "🎁 ADMIN ABUSE"
    })
    return {"ok": True, "target": t["username"], "gift": gift["name"]}

@router.post("/abuse/random_nft")
async def abuse_random_nft(data: dict):
    user = await get_current_user(data.get("token"))
    acc = await has_abuse_access(user)
    if not acc or not acc.get("can_nft"): raise HTTPException(403, "Нет доступа")
    if not online_users: raise HTTPException(400, "Никого онлайн")
    p = await get_pool()
    async with p.acquire() as conn:
        sr = await conn.fetch("SELECT * FROM nft_series WHERE sold<total")
        if not sr: raise HTTPException(400, "Нет NFT")
        tid = random.choice(list(online_users))
        t = await conn.fetchrow("SELECT username FROM users WHERE id=$1", tid)
        if not t: raise HTTPException(404, "Пропал")
        s = random.choice(sr)
        num = (s["sold"] or 0) + 1
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",
            s["id"], num, tid)
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1", s["id"])
    return {"ok": True, "target": t["username"], "nft": s["name"], "number": num}

@router.post("/abuse/random_coins")
async def abuse_random_coins(data: dict):
    user = await get_current_user(data.get("token"))
    acc = await has_abuse_access(user)
    if not acc or not acc.get("can_coins"): raise HTTPException(403, "Нет доступа")
    if not online_users: raise HTTPException(400, "Никого онлайн")
    tid = random.choice(list(online_users))
    amt = random.randint(100, 10000)
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT username FROM users WHERE id=$1", tid)
        if not t: raise HTTPException(404, "Пропал")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", amt, tid)
    return {"ok": True, "target": t["username"], "amount": amt}

# ============================================================
# COOP — abuse grant
# ============================================================
@router.post("/abuse/coop_start")
async def abuse_coop_start(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    target_name = (data.get("username") or "").strip()
    minutes = int(data.get("minutes", 60))
    cg = bool(data.get("can_gift", True))
    cn = bool(data.get("can_nft", True))
    cc = bool(data.get("can_coins", True))
    co = bool(data.get("can_online", True))
    ct = bool(data.get("can_timer", True))
    cw = bool(data.get("can_write", True))
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,username FROM users WHERE username=$1", target_name)
        if not t: raise HTTPException(404, "Не найден")
        await conn.execute("""INSERT INTO abuse_grants(user_id,granted_by,can_gift,can_nft,
            can_coins,can_online,can_timer,can_write,expires_at)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,NOW()+INTERVAL '1 minute' * $9)
            ON CONFLICT (user_id) DO UPDATE SET
            can_gift=$3,can_nft=$4,can_coins=$5,can_online=$6,can_timer=$7,can_write=$8,
            expires_at=NOW()+INTERVAL '1 minute' * $9""",
            t["id"], user["id"], cg, cn, cc, co, ct, cw, minutes)
    await manager.send_to(t["id"], {"type": "coop_started", "minutes": minutes, "username": user["username"]})
    return {"ok": True, "target": t["username"], "minutes": minutes}

@router.get("/abuse/coop_grants")
async def abuse_coop_grants(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT g.user_id,g.can_gift,g.can_nft,g.can_coins,
            g.can_online,g.can_timer,g.can_write,g.expires_at,u.username
            FROM abuse_grants g JOIN users u ON u.id=g.user_id
            WHERE g.expires_at>NOW() ORDER BY g.expires_at DESC""")
    return [{"user_id":r["user_id"], "username":r["username"],
             "can_gift":r["can_gift"], "can_nft":r["can_nft"], "can_coins":r["can_coins"],
             "can_online":r["can_online"], "can_timer":r["can_timer"],
             "can_write":r["can_write"],
             "expires_at":r["expires_at"].isoformat()} for r in rows]

@router.post("/abuse/coop_revoke")
async def abuse_coop_revoke(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM abuse_grants WHERE user_id=$1", int(data.get("user_id", 0)))
    return {"ok": True}

# ============================================================
# USERS FULL (для БОГ-меню)
# ============================================================
@router.get("/owner/users_full")
async def owner_users_full(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,username,email,email_verified,created_at,last_seen,
            online_status,is_banned,is_scam,is_premium,premium_tier,premium_expires,
            is_admin,is_moderator,is_beta_tester,coins,social_rating,messages_count,
            role,referred_by,avatar
            FROM users ORDER BY id DESC""")
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        d["last_seen"] = d["last_seen"].isoformat() if d.get("last_seen") else None
        d["premium_expires"] = d["premium_expires"].isoformat() if d.get("premium_expires") else None
        d["online"] = r["id"] in online_users and (r.get("online_status") or "online") != "invisible"
        d["is_premium"] = bool(r.get("premium_tier"))
        out.append(d)
    return out

@router.post("/owner/user_action")
async def owner_user_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    tid = int(data.get("user_id", 0))
    action = data.get("action")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",
                data.get("reason", ""), tid)
            await manager.send_to(tid, {"type": "banned", "reason": data.get("reason", "")})
            await manager.kick(tid)
        elif action == "unban":
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1", tid)
        elif action == "toggle_scam":
            await conn.execute("UPDATE users SET is_scam=NOT is_scam WHERE id=$1", tid)
        elif action == "give_premium":
            await conn.execute("""UPDATE users SET premium_tier='premium',
                premium_expires=NOW()+INTERVAL '30 days' WHERE id=$1""", tid)
        elif action == "toggle_beta":
            await conn.execute("UPDATE users SET is_beta_tester=NOT is_beta_tester WHERE id=$1", tid)
        elif action == "toggle_streamer":
            await conn.execute("UPDATE users SET is_streamer=NOT is_streamer WHERE id=$1", tid)
    await log_admin(user["id"], f"owner_{action}", tid)
    return {"ok": True}

@router.post("/owner/mass_action")
async def owner_mass_action(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    action = data.get("action")
    ids = data.get("user_ids", [])
    if not ids: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        if action == "ban":
            await conn.execute("UPDATE users SET is_banned=TRUE WHERE id=ANY($1::int[])", ids)
            for uid in ids:
                await manager.send_to(uid, {"type": "banned", "reason": "Mass ban"})
                await manager.kick(uid)
        elif action == "unban":
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=ANY($1::int[])", ids)
        elif action == "scam":
            await conn.execute("UPDATE users SET is_scam=TRUE WHERE id=ANY($1::int[])", ids)
        elif action == "premium":
            await conn.execute("""UPDATE users SET premium_tier='premium',
                premium_expires=NOW()+INTERVAL '30 days' WHERE id=ANY($1::int[])""", ids)
    return {"ok": True, "updated": len(ids)}

@router.post("/owner/reset_pass_by_id")
async def owner_reset_pass_by_id(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    tid = int(data.get("user_id", 0))
    np = secrets.token_hex(4)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET password_hash=$1 WHERE id=$2", hash_password(np), tid)
    return {"ok": True, "new_password": np}

# ============================================================
# PROMO (рефералы)
# ============================================================
@router.get("/owner/promo_list")
async def owner_promo_list(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,username,email,created_at,is_premium,premium_tier
            FROM users WHERE referred_by IS NOT NULL ORDER BY created_at DESC""")
    return [{"id":r["id"], "username":r["username"], "email":r["email"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None,
             "is_premium":bool(r["premium_tier"])} for r in rows]

@router.post("/owner/promo_give_premium")
async def owner_promo_give_premium(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    ids = data.get("user_ids", [])
    if not ids: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET premium_tier='premium',
            premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '30 days'
            WHERE id=ANY($1::int[])""", ids)
    return {"ok": True, "updated": len(ids)}

# ============================================================
# OWNER — VERIFY / STATS
# ============================================================
@router.post("/owner/verify")
async def owner_verify(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    if data.get("password") != OWNER_PASSWORD: raise HTTPException(403, "Неверный")
    return {"ok": True}

@router.get("/owner/stats")
async def owner_stats(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM users")
        m = await conn.fetchval("SELECT COUNT(*) FROM messages")
        c = await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
        n = await conn.fetchval("SELECT COUNT(*) FROM nft_items")
        g = await conn.fetchval("SELECT COUNT(*) FROM gifts")
        gr = await conn.fetchval("SELECT COUNT(*) FROM groups")
    return {"users": u, "messages": m, "coins": c, "nfts": n, "gifts": g, "groups": gr,
            "online": len(online_users)}

# ============================================================
# OWNER — COINS
# ============================================================
@router.post("/owner/give_coins")
async def owner_give_coins(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,coins FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        amt = int(data.get("amount", 100))
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", amt, t["id"])
    return {"ok": True}

@router.post("/owner/take_coins")
async def owner_take_coins(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        await conn.execute("UPDATE users SET coins=GREATEST(coins-$1,0) WHERE id=$2",
            int(data.get("amount", 100)), t["id"])
    return {"ok": True}

@router.post("/owner/give_all")
async def owner_give_all(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins+$1", int(data.get("amount", 10)))
    return {"ok": True}

# ============================================================
# OWNER — USER ACTIONS
# ============================================================
@router.post("/owner/change_nick")
async def owner_change_nick(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET username=$1 WHERE username=$2",
            data.get("new_nick"), data.get("username"))
    return {"ok": True}

@router.post("/owner/reset_pass")
async def owner_reset_pass(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    np = secrets.token_hex(4)
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET password_hash=$1 WHERE username=$2",
            hash_password(np), data.get("username"))
    return {"ok": True, "new_password": np}

@router.post("/owner/mute")
async def owner_mute(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        m = int(data.get("minutes", 60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",
            m * 60, t["id"])
    return {"ok": True}

@router.post("/owner/delete_all_msgs")
async def owner_delete_all_msgs(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        await conn.execute("DELETE FROM messages WHERE user_id=$1", t["id"])
    return {"ok": True}

@router.post("/owner/legend")
async def owner_legend(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_legend=TRUE WHERE username=$1", data.get("username"))
    return {"ok": True}

@router.post("/owner/give_premium")
async def owner_give_premium(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET premium_tier=$1,
            premium_expires=NOW()+INTERVAL '30 days' WHERE username=$2""",
            data.get("tier", "premium"), data.get("username"))
    return {"ok": True}

@router.post("/owner/toggle_beta")
async def owner_toggle_beta(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_beta_tester=NOT is_beta_tester WHERE username=$1",
            data.get("username"))
    return {"ok": True}

@router.post("/owner/grant_admin")
async def owner_grant_admin(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1", data.get("username"))
    return {"ok": True}

@router.post("/owner/revoke_admin")
async def owner_revoke_admin(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET is_admin=FALSE WHERE username=$1", data.get("username"))
    return {"ok": True}

@router.post("/owner/toggle_scam")
async def owner_toggle_scam(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,is_scam FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        await conn.execute("UPDATE users SET is_scam=NOT is_scam WHERE id=$1", t["id"])
        new_val = not t["is_scam"]
    return {"ok": True, "is_scam": new_val}

@router.post("/owner/toggle_streamer")
async def owner_toggle_streamer(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,is_streamer FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        await conn.execute("UPDATE users SET is_streamer=NOT is_streamer WHERE id=$1", t["id"])
        new_status = not t["is_streamer"]
    await manager.broadcast({"type": "streamer_update", "user_id": t["id"], "is_streamer": new_status})
    return {"ok": True, "is_streamer": new_status}

@router.post("/owner/mass_rename")
async def owner_mass_rename(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    prefix = (data.get("prefix") or "")[:16]
    suffix = (data.get("suffix") or "")[:16]
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id,username FROM users WHERE username!=$1", ADMIN_USERNAME)
        for r in rows:
            new = (prefix + r["username"] + suffix)[:32]
            try: await conn.execute("UPDATE users SET username=$1 WHERE id=$2", new, r["id"])
            except: pass
    await manager.broadcast({"type": "mass_renamed"})
    return {"ok": True, "count": len(rows)}

@router.post("/owner/mass_color")
async def owner_mass_color(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    color = data.get("color")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET nickname_color=$1 WHERE username!=$2", color, ADMIN_USERNAME)
    return {"ok": True}

@router.post("/owner/force_logout")
async def owner_force_logout(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    tid = int(data.get("user_id", 0))
    await manager.send_to(tid, {"type": "force_logout"})
    return {"ok": True}

@router.post("/owner/read_chat")
async def owner_read_chat(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    username = data.get("username")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", username)
        if not t: raise HTTPException(404, "Не найден")
        rows = await conn.fetch("""SELECT m.text,u.username AS from_user FROM messages m
            JOIN users u ON u.id=m.user_id WHERE m.user_id=$1 ORDER BY m.id DESC LIMIT 50""", t["id"])
    return {"messages": [{"from":r["from_user"], "text":r["text"]} for r in rows]}

@router.post("/owner/write_as")
async def owner_write_as(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,username,avatar FROM users WHERE username=$1", data.get("username"))
        if not t: raise HTTPException(404, "Не найден")
        ch = await conn.fetchrow("""SELECT c.id FROM channels c
            JOIN server_members sm ON sm.server_id=c.server_id
            WHERE sm.user_id=$1 ORDER BY c.id LIMIT 1""", t["id"])
        if ch:
            msg = await conn.fetchrow("""INSERT INTO messages(channel_id,user_id,text)
                VALUES($1,$2,$3) RETURNING *""", ch["id"], t["id"], data.get("text", ""))
            await manager.broadcast({
                "type": "message", "id": msg["id"], "channel_id": ch["id"],
                "user_id": t["id"], "username": t["username"], "avatar": t["avatar"],
                "text": data.get("text", ""),
                "created_at": msg["created_at"].isoformat()
            })
    return {"ok": True}

# ============================================================
# OWNER — TROLL
# ============================================================
@router.post("/owner/troll")
async def owner_troll(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    await manager.broadcast({"type": "event", "event": data.get("troll")})
    return {"ok": True}

@router.post("/owner/troll_user")
async def owner_troll_user(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    tid = int(data.get("user_id", 0))
    kind = data.get("kind")
    dur = int(data.get("duration", 10))
    await manager.send_to(tid, {"type": "troll_user", "kind": kind, "duration": dur})
    return {"ok": True}

@router.post("/owner/storm")
async def owner_storm(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    dur = int(data.get("duration", 30))
    await manager.broadcast({"type": "storm", "duration": dur})
    return {"ok": True}

@router.post("/owner/suddness")
async def owner_suddness(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    evt = random.choice(["confetti", "balloons", "cat_mode"])
    await manager.broadcast({"type": "event", "event": evt})
    return {"ok": True, "event": evt}

@router.post("/owner/announce")
async def owner_announce(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    await manager.broadcast({"type": "abuse", "from_name": user["username"], "text": data.get("text", "")})
    return {"ok": True}

@router.post("/owner/self_destruct")
async def owner_self_destruct(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        ch = int(data.get("channel_id", 0))
        await conn.execute("DELETE FROM messages WHERE channel_id=$1", ch)
    await manager.broadcast({"type": "event", "event": "self_destruct", "channel_id": ch})
    return {"ok": True}

# ============================================================
# OWNER — AUTO ABUSE
# ============================================================
@router.post("/owner/auto_abuse")
async def owner_auto_abuse(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    enabled = bool(data.get("enabled", False))
    kind = data.get("kind", "gift")
    every = int(data.get("every_minutes", 60))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM auto_abuse")
        if enabled:
            await conn.execute("""INSERT INTO auto_abuse(enabled,kind,every_minutes,next_run,created_by)
                VALUES(TRUE,$1,$2,NOW()+INTERVAL '1 minute' * $3,$4)""",
                kind, every, every, user["id"])
    return {"ok": True, "enabled": enabled}

# ============================================================
# OWNER — SYSTEM
# ============================================================
@router.post("/owner/clean_db")
async def owner_clean_db(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE created_at<NOW()-INTERVAL '30 days'")
        await conn.execute("DELETE FROM dms WHERE created_at<NOW()-INTERVAL '30 days'")
    return {"ok": True}

@router.get("/owner/backup")
async def owner_backup(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    from fastapi.responses import JSONResponse
    p = await get_pool()
    data = {"users":[], "servers":[], "channels":[], "messages":[], "dms":[], "gifts":[], "nft_items":[]}
    async with p.acquire() as conn:
        data["users"] = [dict(r) for r in await conn.fetch("SELECT id,username,coins,social_rating,level,xp,reputation,title,created_at FROM users")]
        data["servers"] = [dict(r) for r in await conn.fetch("SELECT id,name,owner_id,invite_code FROM servers")]
        data["channels"] = [dict(r) for r in await conn.fetch("SELECT id,server_id,name,mode FROM channels")]
        data["messages"] = [dict(r) for r in await conn.fetch("SELECT id,channel_id,user_id,text,created_at FROM messages LIMIT 5000")]
        data["dms"] = [dict(r) for r in await conn.fetch("SELECT id,from_user,to_user,text,created_at FROM dms LIMIT 5000")]
        data["gifts"] = [dict(r) for r in await conn.fetch("SELECT id,from_user,to_user,gift FROM gifts")]
        data["nft_items"] = [dict(r) for r in await conn.fetch("SELECT id,series_id,number,owner_id FROM nft_items")]
    def conv(o):
        if isinstance(o, datetime.datetime): return o.isoformat()
        return str(o)
    return JSONResponse(data, default=conv)

# ============================================================
# OWNER — CREATE: GIFTS / STICKERS / NFT / CASES / THEMES
# ============================================================
@router.get("/owner/gifts_full")
async def owner_gifts_full(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    from api._shared import DEFAULT_GIFTS
    result = []
    for gid, g in DEFAULT_GIFTS.items():
        result.append({"db_id": None, "slug": gid, "name": g["name"], "emoji": g["emoji"],
                       "image": g.get("image"), "price": g["price"], "is_default": True})
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("""SELECT id,gift_id,name,emoji,image,price FROM custom_gifts
                WHERE is_sticker=FALSE OR is_sticker IS NULL ORDER BY id DESC""")
        for r in rows:
            result.append({"db_id": r["id"], "slug": r["gift_id"], "name": r["name"],
                           "emoji": r["emoji"], "image": r["image"], "price": r["price"],
                           "is_default": False})
    except: pass
    return result

@router.get("/owner/stickers_full")
async def owner_stickers_full(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("""SELECT id,gift_id,name,emoji,image FROM custom_gifts
                WHERE is_sticker=TRUE ORDER BY id DESC""")
        return [{"db_id":r["id"], "slug":r["gift_id"], "name":r["name"],
                 "emoji":r["emoji"], "image":r["image"]} for r in rows]
    except: return []

@router.get("/owner/nfts_full")
async def owner_nfts_full(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("""SELECT id,name,emoji,image,price,total,sold,rarity
                FROM nft_series ORDER BY id DESC""")
        return [{"db_id":r["id"], "name":r["name"], "emoji":r["emoji"], "image":r["image"],
                 "price":r["price"], "total":r["total"], "sold":r["sold"],
                 "rarity":r["rarity"]} for r in rows]
    except: return []

@router.post("/owner/create_nft")
async def owner_create_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("""INSERT INTO nft_series(name,emoji,image,total,price,rarity,created_by)
            VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
            data.get("name"), data.get("emoji", "🎨"), data.get("image"),
            int(data.get("total", 1)), int(data.get("price", 0)),
            data.get("rarity", "common"), user["id"])
    return {"ok": True, "id": row["id"]}

@router.post("/owner/delete_nft")
async def owner_delete_nft(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM nft_series WHERE id=$1", int(data.get("nft_id", 0)))
    return {"ok": True}

@router.post("/owner/create_gift")
async def owner_create_gift(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    gid = (data.get("gift_id") or "").strip().lower()
    if not gid or len(gid) > 32: raise HTTPException(400, "ID 1-32")
    name = (data.get("name") or "").strip()
    if not name: raise HTTPException(400, "Название")
    price = int(data.get("price", 0))
    if price <= 0: raise HTTPException(400, "Цена>0")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT gift_id FROM custom_gifts WHERE gift_id=$1", gid):
            raise HTTPException(400, "ID занят")
        await conn.execute("""INSERT INTO custom_gifts(gift_id,name,emoji,image,price,is_sticker)
            VALUES($1,$2,$3,$4,$5,FALSE)""",
            gid, name, data.get("emoji", "🎁"), data.get("image"), price)
    return {"ok": True}

@router.post("/owner/delete_gift")
async def owner_delete_gift(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""DELETE FROM custom_gifts WHERE gift_id=$1
            AND (is_sticker=FALSE OR is_sticker IS NULL)""", data.get("gift_id"))
    return {"ok": True}

@router.post("/owner/create_sticker")
async def owner_create_sticker(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    sid = (data.get("sticker_id") or "").strip().lower()
    if not sid or len(sid) > 32: raise HTTPException(400, "ID 1-32")
    name = (data.get("name") or "").strip()
    if not name: raise HTTPException(400, "Название")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT gift_id FROM custom_gifts WHERE gift_id=$1", sid):
            raise HTTPException(400, "ID занят")
        await conn.execute("""INSERT INTO custom_gifts(gift_id,name,emoji,image,price,is_sticker)
            VALUES($1,$2,$3,$4,0,TRUE)""",
            sid, name, data.get("emoji", "🎨"), data.get("image"))
    await manager.broadcast({"type": "sticker_added", "id": sid})
    return {"ok": True}

@router.post("/owner/delete_sticker")
async def owner_delete_sticker(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM custom_gifts WHERE gift_id=$1 AND is_sticker=TRUE", data.get("sticker_id"))
    return {"ok": True}

@router.get("/owner/cases_full")
async def owner_cases_full(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("SELECT id,name,emoji,image,price,is_active FROM cases ORDER BY id DESC")
            result = []
            for r in rows:
                prizes = await conn.fetch("""SELECT kind,item_id,item_name,item_emoji,item_image,
                    chance,coins_min,coins_max FROM case_prizes WHERE case_id=$1""", r["id"])
                result.append({"db_id":r["id"], "name":r["name"], "emoji":r["emoji"],
                               "image":r["image"], "price":r["price"], "is_active":r["is_active"],
                               "prizes":[dict(p) for p in prizes]})
            return result
    except: return []

@router.post("/owner/cases/create")
async def owner_cases_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Название")
    price = int(data.get("price", 0))
    if price <= 0: raise HTTPException(400, "Цена >0")
    prizes = data.get("prizes") or []
    if not prizes: raise HTTPException(400, "Хотя бы 1 приз")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("""INSERT INTO cases(name,emoji,image,price,created_by)
            VALUES($1,$2,$3,$4,$5) RETURNING id""",
            name, data.get("emoji", "🎁"), data.get("image"), price, user["id"])
        for pr in prizes:
            await conn.execute("""INSERT INTO case_prizes(case_id,kind,item_id,item_name,item_emoji,
                item_image,chance,coins_min,coins_max) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                c["id"], pr.get("kind", "coins"), str(pr.get("item_id") or ""),
                pr.get("item_name", ""), pr.get("item_emoji", ""), pr.get("item_image"),
                int(pr.get("chance", 0)), int(pr.get("coins_min", 0)), int(pr.get("coins_max", 0)))
    await manager.broadcast({"type": "case_added", "id": c["id"], "name": name})
    return {"ok": True, "id": c["id"]}

@router.post("/owner/cases/delete")
async def owner_cases_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM cases WHERE id=$1", int(data.get("case_id", 0)))
    return {"ok": True}

@router.post("/owner/cases/toggle")
async def owner_cases_toggle(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE cases SET is_active=NOT is_active WHERE id=$1", int(data.get("case_id", 0)))
    return {"ok": True}

@router.post("/owner/theme/create")
async def owner_theme_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Название")
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("""INSERT INTO custom_themes(name,emoji,vars,bg_image,border_radius,blur,created_by)
            VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
            name, data.get("emoji", "🎨"), json.dumps(data.get("vars") or {}),
            data.get("bg_image"), data.get("border_radius", "12px"),
            data.get("blur", "blur(30px)"), user["id"])
    await manager.broadcast({"type": "theme_added", "id": r["id"], "name": name})
    return {"ok": True, "id": r["id"]}

# ============================================================
# OWNER — BP EDITOR
# ============================================================
@router.get("/bp/admin/info")
async def bp_admin_info(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
    if not row: return {"name": "", "description": "", "emoji": "🏆"}
    return {"name": row["name"], "description": row["description"], "emoji": row["emoji"]}

@router.post("/bp/admin/save")
async def bp_admin_save(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if row:
            await conn.execute("UPDATE bp_season SET name=$1,description=$2,emoji=$3 WHERE id=$4",
                data.get("name", ""), data.get("description", ""), data.get("emoji", "🏆"), row["id"])
        else:
            await conn.execute("INSERT INTO bp_season(name,description,emoji) VALUES($1,$2,$3)",
                data.get("name", "Сезон 1"), data.get("description", ""), data.get("emoji", "🏆"))
    return {"ok": True}

@router.post("/bp/admin/start")
async def bp_admin_start(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE bp_season SET active=FALSE WHERE active=TRUE")
        await conn.execute("""INSERT INTO bp_season(name,description,emoji,active)
            VALUES('Новый сезон','','🏆',TRUE)""")
    await manager.broadcast({"type": "bp_update"})
    return {"ok": True}

@router.post("/bp/admin/end")
async def bp_admin_end(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE active=TRUE")
    await manager.broadcast({"type": "bp_update"})
    return {"ok": True}

@router.get("/bp/admin/quests")
async def bp_admin_quests(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,name,description,goal,xp_reward FROM bp_quests
            WHERE active=TRUE ORDER BY id""")
    return [dict(r) for r in rows]

@router.post("/bp/admin/quests/add")
async def bp_admin_quests_add(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO bp_quests(name,description,goal,xp_reward)
            VALUES($1,$2,$3,$4)""",
            data.get("name", ""), data.get("description", ""),
            int(data.get("goal", 10)), int(data.get("xp_reward", 100)))
    return {"ok": True}

@router.post("/bp/admin/quests/delete")
async def bp_admin_quests_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_quests WHERE id=$1", int(data.get("quest_id", 0)))
    return {"ok": True}

@router.get("/bp/admin/rewards")
async def bp_admin_rewards(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id,level,reward FROM bp_rewards WHERE active=TRUE ORDER BY level")
    return [dict(r) for r in rows]

@router.post("/bp/admin/rewards/add")
async def bp_admin_rewards_add(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO bp_rewards(level,reward) VALUES($1,$2)",
            int(data.get("level", 1)), data.get("reward", ""))
    return {"ok": True}

@router.post("/bp/admin/rewards/delete")
async def bp_admin_rewards_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_rewards WHERE id=$1", int(data.get("reward_id", 0)))
    return {"ok": True}

# ============================================================
# OWNER — EVENTS
# ============================================================
@router.post("/owner/events/create")
async def owner_events_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    name = data.get("name", "")
    desc = data.get("description", "")
    emoji = data.get("emoji", "🎉")
    etype = data.get("event_type", "coins_x")
    mult = int(data.get("multiplier", 1))
    dur = int(data.get("duration_minutes", 10))
    end_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=dur)
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("""INSERT INTO events(name,description,emoji,event_type,multiplier,
            created_by,end_at) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id""",
            name, desc, emoji, etype, mult, user["id"], end_at)
    active_events.append({"id": r["id"], "name": name, "description": desc, "emoji": emoji,
                          "event_type": etype, "multiplier": mult, "end_at": end_at, "active": True})
    await manager.broadcast({"type": "event_active", "id": r["id"], "name": name,
        "description": desc, "emoji": emoji, "event_type": etype, "multiplier": mult,
        "end_at": end_at.isoformat()})
    return {"ok": True, "id": r["id"]}

@router.get("/owner/events/list")
async def owner_events_list(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,name,event_type,multiplier,end_at FROM events
            WHERE active=TRUE AND end_at>NOW() ORDER BY id DESC""")
    return [{"id":r["id"], "name":r["name"], "event_type":r["event_type"],
             "multiplier":r["multiplier"],
             "end_at":r["end_at"].isoformat() if r["end_at"] else None} for r in rows]

@router.post("/owner/events/stop")
async def owner_events_stop(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    eid = int(data.get("event_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE events SET active=FALSE WHERE id=$1", eid)
    for e in active_events:
        if e["id"] == eid: e["active"] = False
    await manager.broadcast({"type": "event_end", "id": eid})
    return {"ok": True}

# ============================================================
# OWNER — COMMANDS
# ============================================================
@router.post("/owner/commands/create")
async def owner_commands_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    name = (data.get("name") or "").strip().lower()
    if not name: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM commands WHERE name=$1", name):
            raise HTTPException(400, "Занято")
        await conn.execute("""INSERT INTO commands(name,description,response,created_by)
            VALUES($1,$2,$3,$4)""",
            name, data.get("description", ""), data.get("response", ""), user["id"])
    custom_commands[name] = data.get("response", "")
    return {"ok": True}

@router.post("/owner/commands/delete")
async def owner_commands_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM commands WHERE id=$1", int(data.get("command_id", 0)))
    return {"ok": True}

@router.post("/owner/upgrade_chance")
async def owner_upgrade_chance(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    from api._shared import upgrade_chance_bonus
    un = data.get("username", "")
    bonus = int(data.get("bonus", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", un)
        if not t: raise HTTPException(404, "Не найден")
        upgrade_chance_bonus[t["id"]] = bonus
    return {"ok": True}

# ============================================================
# OWNER — OWNER CHAT
# ============================================================
@router.get("/owner/chat")
async def owner_chat_get(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT om.id,om.text,om.created_at,u.username FROM owner_messages om
            LEFT JOIN users u ON u.id=om.from_user ORDER BY om.id ASC LIMIT 100""")
    return [{"id":r["id"], "text":r["text"], "username":r["username"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@router.post("/owner/chat/send")
async def owner_chat_send(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    text = (data.get("text") or "").strip()
    if not text: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO owner_messages(from_user,text) VALUES($1,$2)", user["id"], text)
    return {"ok": True}

# ============================================================
# OWNER — RELEASE (hot-swap)
# ============================================================
@router.get("/owner/release/info")
async def owner_release_info(token: str):
    user = await get_current_user(token)
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    from api.core import RELEASE_STATE
    return RELEASE_STATE

@router.post("/owner/release/activate")
async def owner_release_activate(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    from api.core import RELEASE_STATE
    RELEASE_STATE["target_version"] = data.get("version", "2.5")
    RELEASE_STATE["notes"] = data.get("notes", "")
    RELEASE_STATE["force"] = bool(data.get("force", False))
    RELEASE_STATE["active"] = True
    await manager.broadcast({"type": "release_available",
        "version": RELEASE_STATE["target_version"],
        "notes": RELEASE_STATE["notes"],
        "force": RELEASE_STATE["force"]})
    return {"ok": True}

@router.post("/owner/release/deactivate")
async def owner_release_deactivate(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    from api.core import RELEASE_STATE
    RELEASE_STATE["active"] = False
    await manager.broadcast({"type": "release_cancelled"})
    return {"ok": True}