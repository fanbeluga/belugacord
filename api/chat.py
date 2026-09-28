# BELUGACORD 2.5 — api/chat.py (part 1/2)
# Friends, blocks, groups, servers, channels

import json, secrets, datetime
from fastapi import APIRouter, HTTPException

from api._shared import (
    get_pool, get_current_user, is_premium, is_blocked,
    check_friend_spam, grant_achievement, get_role, user_public,
    online_users, manager
)

router = APIRouter()

# ============================================================
# FRIENDS
# ============================================================
@router.get("/friends/list")
async def friends_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    uid = user["id"]
    p = await get_pool()
    async with p.acquire() as conn:
        frows = await conn.fetch("SELECT id,user_a,user_b FROM friendships WHERE user_a=$1 OR user_b=$1", uid)
        inc = await conn.fetch("""SELECT r.id, r.from_user, u.username, u.avatar, u.gif_avatar,
            u.is_admin, u.is_moderator, u.is_beta_tester, u.is_scam, u.is_streamer,
            u.premium_tier, u.premium_expires
            FROM friend_requests r JOIN users u ON u.id=r.from_user
            WHERE r.to_user=$1 ORDER BY r.created_at DESC""", uid)
        out = await conn.fetch("""SELECT r.id, r.to_user, u.username, u.avatar
            FROM friend_requests r JOIN users u ON u.id=r.to_user
            WHERE r.from_user=$1 ORDER BY r.created_at DESC""", uid)

        result = []
        for r in frows:
            oid = r["user_b"] if r["user_a"] == uid else r["user_a"]
            o = await conn.fetchrow("""SELECT id,username,avatar,gif_avatar,is_admin,is_moderator,
                is_beta_tester,is_scam,is_streamer,last_seen,online_status,custom_status,
                premium_tier,premium_expires,title FROM users WHERE id=$1""", oid)
            if not o: continue
            last = await conn.fetchval("SELECT MAX(created_at) FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", uid, oid)
            has_story = await conn.fetchval("SELECT id FROM stories WHERE user_id=$1 AND expires_at>NOW() LIMIT 1", oid)
            result.append({
                "id": o["id"], "username": o["username"], "avatar": o["avatar"],
                "gif_avatar": o.get("gif_avatar"), "status": "accepted",
                "friend_row_id": r["id"],
                "online": o["id"] in online_users and (o.get("online_status") or "online") != "invisible",
                "last_seen": o["last_seen"].isoformat() if o.get("last_seen") else None,
                "is_admin": o["is_admin"], "is_moderator": o["is_moderator"],
                "is_beta_tester": o["is_beta_tester"], "is_scam": o["is_scam"],
                "is_streamer": o.get("is_streamer", False),
                "custom_status": o.get("custom_status"),
                "online_status": o.get("online_status") or "online",
                "role": get_role(o), "is_premium": is_premium(o),
                "last_message_at": last.isoformat() if last else None,
                "has_story": bool(has_story), "title": o.get("title")
            })
        for r in inc:
            result.append({
                "id": r["from_user"], "username": r["username"], "avatar": r["avatar"],
                "gif_avatar": r.get("gif_avatar"), "status": "incoming",
                "request_id": r["id"], "online": r["from_user"] in online_users,
                "is_admin": r["is_admin"], "is_moderator": r["is_moderator"],
                "is_beta_tester": r["is_beta_tester"], "is_scam": r["is_scam"],
                "is_streamer": r.get("is_streamer", False),
                "role": get_role(r), "is_premium": is_premium(r)
            })
        for r in out:
            result.append({
                "id": r["to_user"], "username": r["username"], "avatar": r["avatar"],
                "status": "outgoing", "request_id": r["id"],
                "online": r["to_user"] in online_users,
                "is_admin": False, "is_moderator": False, "is_beta_tester": False,
                "is_scam": False, "role": "user"
            })

    result.sort(key=lambda x: (
        not x.get("online"), not x.get("is_premium"),
        -(datetime.datetime.fromisoformat(x["last_message_at"]).timestamp() if x.get("last_message_at") else 0)
    ))
    return result

@router.post("/friends/request")
async def friends_request(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tn = (data.get("username") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,username FROM users WHERE username=$1", tn)
        if not t: raise HTTPException(404, "Не найден")
        if await check_friend_spam(user["id"], t["id"]):
            raise HTTPException(429, "Слишком много заявок")
        if t["id"] == user["id"]: raise HTTPException(400, "Себя нельзя")
        if await is_blocked(user["id"], t["id"]): raise HTTPException(403, "Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], t["id"]):
            raise HTTPException(400, "Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], t["id"]):
            raise HTTPException(400, "Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)", user["id"], t["id"])
    await manager.send_to(t["id"], {"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok": True}

@router.post("/friends/request_by_id")
async def friends_request_by_id(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id", 0))
    if tid == user["id"]: raise HTTPException(400, "Себя нельзя")
    p = await get_pool()
    async with p.acquire() as conn:
        t = await conn.fetchrow("SELECT id,username FROM users WHERE id=$1", tid)
        if not t: raise HTTPException(404, "Не найден")
        if await check_friend_spam(user["id"], tid):
            raise HTTPException(429, "Слишком много заявок")
        if await is_blocked(user["id"], tid): raise HTTPException(403, "Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], tid):
            raise HTTPException(400, "Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], tid):
            raise HTTPException(400, "Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)", user["id"], tid)
    await manager.send_to(tid, {"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok": True}

@router.post("/friends/accept")
async def friends_accept(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT id,from_user,to_user FROM friend_requests WHERE id=$1", rid)
        if not r: raise HTTPException(404, "Заявка обработана")
        if r["to_user"] != user["id"]: raise HTTPException(403, "Не твоя")
        a, b = sorted([r["from_user"], r["to_user"]])
        try: await conn.execute("INSERT INTO friendships(user_a,user_b) VALUES($1,$2)", a, b)
        except: pass
        await conn.execute("DELETE FROM friend_requests WHERE id=$1", rid)
        cnt = await conn.fetchval("SELECT COUNT(*) FROM friendships WHERE user_a=$1 OR user_b=$1", user["id"])
        if cnt == 1: await grant_achievement(user["id"], "first_friend")
        if cnt >= 10: await grant_achievement(user["id"], "friend_10")
        other = await conn.fetchrow("SELECT id,username,avatar FROM users WHERE id=$1", r["from_user"])
    await manager.send_to(r["from_user"], {"type":"friend_accepted","friend_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    await manager.send_to(user["id"], {"type":"friend_accepted","friend_id":r["from_user"],"username":other["username"],"avatar":other["avatar"]})
    return {"ok": True}

@router.post("/friends/decline")
async def friends_decline(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("SELECT from_user,to_user FROM friend_requests WHERE id=$1", rid)
        if not r: return {"ok": True}
        if r["to_user"] != user["id"]: raise HTTPException(403, "Не твоя")
        await conn.execute("DELETE FROM friend_requests WHERE id=$1", rid)
    await manager.send_to(r["from_user"], {"type":"friend_declined","by_id":user["id"]})
    return {"ok": True}

@router.post("/friends/cancel")
async def friends_cancel(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    rid = int(data.get("request_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND from_user=$2", rid, user["id"])
    return {"ok": True}

@router.post("/friends/remove")
async def friends_remove(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("user_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], tid)
    await manager.send_to(tid, {"type":"friend_removed","by_id":user["id"]})
    return {"ok": True}

@router.get("/friends/check/{user_id}")
async def friends_check(user_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)", user["id"], user_id):
            return {"status": "accepted"}
        req = await conn.fetchrow("SELECT id,from_user FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)", user["id"], user_id)
        if req:
            return {"status": "incoming" if req["from_user"] != user["id"] else "outgoing", "request_id": req["id"]}
        return {"status": "none"}

@router.get("/friends/count")
async def friends_count(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        n = await conn.fetchval("SELECT COUNT(*) FROM friend_requests WHERE to_user=$1", user["id"])
    return {"count": n or 0}

# ============================================================
# GROUPS
# ============================================================
@router.get("/groups/list")
async def groups_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT g.id,g.name,g.avatar,g.gif_avatar,g.description,g.owner_id,g.last_message_at
            FROM groups g JOIN group_members gm ON gm.group_id=g.id
            WHERE gm.user_id=$1 ORDER BY COALESCE(g.last_message_at, g.created_at) DESC""", user["id"])
    return [{"id":r["id"], "name":r["name"], "avatar":r["avatar"],
             "gif_avatar":r.get("gif_avatar"), "description":r["description"],
             "owner_id":r["owner_id"],
             "last_message_at":r["last_message_at"].isoformat() if r.get("last_message_at") else None} for r in rows]

@router.post("/groups/create")
async def groups_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя нужно")
    members = data.get("members") or []
    max_members = 30 if is_premium(user) else 10
    if len(members) + 1 > max_members:
        raise HTTPException(400, f"Макс {max_members} участников")
    p = await get_pool()
    async with p.acquire() as conn:
        g = await conn.fetchrow("INSERT INTO groups(name,avatar,description,owner_id) VALUES($1,$2,$3,$4) RETURNING *",
            name, data.get("avatar"), (data.get("description") or "")[:256], user["id"])
        await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)", g["id"], user["id"])
        for m in members:
            try:
                mid = int(m)
                if mid != user["id"]:
                    await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING", g["id"], mid)
                    await manager.send_to(mid, {"type":"group_added","group_id":g["id"],"name":name})
            except: pass
    return {"id": g["id"], "name": g["name"]}

@router.get("/groups/{group_id}")
async def group_get(group_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        g = await conn.fetchrow("SELECT * FROM groups WHERE id=$1", group_id)
        if not g: raise HTTPException(404, "Нет")
        m = await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2", group_id, user["id"])
        if not m: raise HTTPException(403, "Не участник")
    d = dict(g)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["last_message_at"] = d["last_message_at"].isoformat() if d.get("last_message_at") else None
    return d

@router.get("/groups/{group_id}/messages")
async def group_messages(group_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        m = await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2", group_id, user["id"])
        if not m: raise HTTPException(403, "Не участник")
        rows = await conn.fetch("""SELECT gm.id,gm.text,gm.file_url,gm.created_at,gm.user_id,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_admin,u.is_moderator,
            u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires,
            u.active_frame,u.title
            FROM group_messages gm JOIN users u ON u.id=gm.user_id
            WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200""", group_id)
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        d["role"] = get_role(r)
        d["is_premium"] = is_premium(r)
        out.append(d)
    return out

@router.get("/groups/{group_id}/members")
async def group_members_get(group_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id,u.username,u.avatar,u.gif_avatar,u.is_admin,
            u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,
            u.premium_expires,u.title FROM users u
            JOIN group_members gm ON gm.user_id=u.id WHERE gm.group_id=$1""", group_id)
    out = []
    for r in rows:
        d = dict(r)
        d["role"] = get_role(r)
        d["is_premium"] = is_premium(r)
        out.append(d)
    return out

@router.post("/groups/add_member")
async def group_add_member(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gid = int(data.get("group_id", 0))
    username = (data.get("username") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        g = await conn.fetchrow("SELECT owner_id,name FROM groups WHERE id=$1", gid)
        if not g: raise HTTPException(404, "Нет группы")
        if g["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        cnt = await conn.fetchval("SELECT COUNT(*) FROM group_members WHERE group_id=$1", gid)
        max_members = 30 if is_premium(user) else 10
        if cnt >= max_members: raise HTTPException(400, f"Макс {max_members}")
        t = await conn.fetchrow("SELECT id FROM users WHERE username=$1", username)
        if not t: raise HTTPException(404, "Юзер не найден")
        try: await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)", gid, t["id"])
        except: raise HTTPException(400, "Уже в группе")
    await manager.send_to(t["id"], {"type":"group_added","group_id":gid,"name":g["name"]})
    return {"ok": True}

@router.post("/groups/kick")
async def group_kick(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gid = int(data.get("group_id", 0)); tid = int(data.get("user_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        g = await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1", gid)
        if not g or g["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        if tid == user["id"]: raise HTTPException(400, "Себя через выход")
        await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2", gid, tid)
    await manager.send_to(tid, {"type":"group_kicked","group_id":gid})
    return {"ok": True}

@router.post("/groups/leave")
async def group_leave(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gid = int(data.get("group_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        g = await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1", gid)
        if not g: raise HTTPException(404, "Нет")
        if g["owner_id"] == user["id"]:
            await conn.execute("DELETE FROM groups WHERE id=$1", gid)
        else:
            await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2", gid, user["id"])
    return {"ok": True}

@router.post("/groups/update")
async def group_update(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gid = int(data.get("group_id", 0))
    gif_av = data.get("gif_avatar")
    if gif_av and not is_premium(user): raise HTTPException(403, "GIF только для премиума")
    p = await get_pool()
    async with p.acquire() as conn:
        g = await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1", gid)
        if not g or g["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        await conn.execute("""UPDATE groups SET
            name=COALESCE($1,name), description=COALESCE($2,description),
            avatar=COALESCE($3,avatar), gif_avatar=COALESCE($4,gif_avatar)
            WHERE id=$5""",
            data.get("name"), data.get("description"), data.get("avatar"), gif_av, gid)
    return {"ok": True}

# ============================================================
# SERVERS
# ============================================================
@router.get("/servers/list")
async def servers_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id,s.name,s.avatar FROM servers s
            JOIN server_members sm ON sm.server_id=s.id WHERE sm.user_id=$1 ORDER BY s.id""", user["id"])
    return [dict(r) for r in rows]

@router.post("/servers/create")
async def servers_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя нужно")
    p = await get_pool()
    async with p.acquire() as conn:
        code = secrets.token_urlsafe(8)[:12]
        s = await conn.fetchrow("INSERT INTO servers(name,owner_id,invite_code) VALUES($1,$2,$3) RETURNING *", name, user["id"], code)
        await conn.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)", s["id"], user["id"])
        await conn.execute("INSERT INTO channels(server_id,name) VALUES($1,'общий')", s["id"])
        await grant_achievement(user["id"], "first_server")
    return {"id": s["id"], "name": s["name"], "invite_code": code}

@router.post("/servers/join")
async def servers_join(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    code = (data.get("invite") or "").strip()
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM servers WHERE invite_code=$1", code)
        if not s: raise HTTPException(404, "Неверный код")
        try: await conn.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)", s["id"], user["id"])
        except: pass
    return {"id": s["id"], "name": s["name"]}

@router.get("/servers/{server_id}")
async def server_get(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM servers WHERE id=$1", server_id)
    if not s: raise HTTPException(404, "Нет")
    d = dict(s)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    return d

@router.get("/servers/{server_id}/channels")
async def server_channels(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT id,name,type,mode,last_message_at FROM channels
            WHERE server_id=$1 ORDER BY COALESCE(last_message_at, created_at) DESC, id""", server_id)
    return [{"id":r["id"], "name":r["name"], "type":r["type"],
             "mode":r.get("mode") or "public",
             "last_message_at":r["last_message_at"].isoformat() if r.get("last_message_at") else None} for r in rows]

@router.get("/servers/{server_id}/members")
async def server_members(server_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.id,u.username,u.avatar,u.gif_avatar,u.is_admin,
            u.is_moderator,u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,
            u.premium_expires,u.title FROM users u
            JOIN server_members sm ON sm.user_id=u.id WHERE sm.server_id=$1""", server_id)
    out = []
    for r in rows:
        d = dict(r)
        d["role"] = get_role(r)
        d["is_premium"] = is_premium(r)
        out.append(d)
    return out

@router.post("/servers/update")
async def server_update(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1", int(data.get("server_id", 0)))
        if not s or s["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        await conn.execute("""UPDATE servers SET
            name=COALESCE($1,name), description=COALESCE($2,description), avatar=COALESCE($3,avatar)
            WHERE id=$4""",
            data.get("name"), data.get("description"), data.get("avatar"), int(data.get("server_id", 0)))
    return {"ok": True}

@router.post("/servers/delete")
async def server_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1", int(data.get("server_id", 0)))
        if not s or s["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        await conn.execute("DELETE FROM servers WHERE id=$1", int(data.get("server_id", 0)))
    return {"ok": True}

@router.post("/servers/leave")
async def server_leave(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM server_members WHERE server_id=$1 AND user_id=$2", int(data.get("server_id", 0)), user["id"])
    return {"ok": True}

@router.post("/servers/regen_invite")
async def server_regen_invite(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1", int(data.get("server_id", 0)))
        if not s or s["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец")
        code = secrets.token_urlsafe(8)[:12]
        await conn.execute("UPDATE servers SET invite_code=$1 WHERE id=$2", code, int(data.get("server_id", 0)))
    return {"ok": True, "invite_code": code}

# ============================================================
# CHANNELS
# ============================================================
@router.post("/channels/create")
async def channel_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    sid = int(data.get("server_id", 0))
    name = (data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400, "Имя нужно")
    p = await get_pool()
    async with p.acquire() as conn:
        r = await conn.fetchrow("INSERT INTO channels(server_id,name) VALUES($1,$2) RETURNING id,name", sid, name)
    return {"id": r["id"], "name": r["name"]}

@router.post("/channels/set_mode")
async def channel_set_mode(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    cid = int(data.get("channel_id", 0))
    mode = data.get("mode", "public")
    if mode not in ("public", "readonly", "paid_reactions", "forum"):
        raise HTTPException(400, "Плохой режим")
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT s.owner_id FROM channels c JOIN servers s ON s.id=c.server_id WHERE c.id=$1", cid)
        if not c or c["owner_id"] != user["id"]: raise HTTPException(403, "Только владелец сервера")
        await conn.execute("UPDATE channels SET mode=$1 WHERE id=$2", mode, cid)
    return {"ok": True, "mode": mode}

# ============================================================
# CHANNEL MESSAGES
# ============================================================
@router.get("/channels/{channel_id}/messages")
async def channel_messages(channel_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT m.id,m.text,m.file_url,m.reactions,m.edited,m.reply_to,
            m.thread_root,m.pinned,m.effect,m.created_at,m.user_id,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_admin,u.is_moderator,
            u.is_beta_tester,u.is_scam,u.is_streamer,u.premium_tier,u.premium_expires,
            u.active_frame,u.title
            FROM messages m JOIN users u ON u.id=m.user_id
            WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200""", channel_id)
        pinned = await conn.fetch("""SELECT m.id,m.text,m.user_id,u.username
            FROM messages m JOIN users u ON u.id=m.user_id
            WHERE m.channel_id=$1 AND m.pinned=TRUE ORDER BY m.id DESC LIMIT 5""", channel_id)
        chan = await conn.fetchrow("SELECT mode,paid_reaction_cost FROM channels WHERE id=$1", channel_id)
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        d["role"] = get_role(r)
        d["is_premium"] = is_premium(r)
        d["reactions"] = json.loads(d.get("reactions") or "{}")
        out.append(d)
    return {
        "messages": out,
        "pinned": [dict(p) for p in pinned],
        "mode": chan["mode"] if chan else "public",
        "paid_cost": chan["paid_reaction_cost"] if chan else 10
    }

# ============================================================
# DM MESSAGES
# ============================================================
@router.get("/dm/{user_id}/messages")
async def dm_messages(user_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    if await is_blocked(user["id"], user_id): raise HTTPException(403, "Заблокировано")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.created_at,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.premium_tier,u.premium_expires,
            u.active_frame,u.title
            FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1)
            ORDER BY d.id ASC LIMIT 200""", user["id"], user_id)
    out = []
    for r in rows:
        d = dict(r)
        d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
        d["is_premium"] = is_premium(r)
        out.append(d)
    return out

# ============================================================
# EDIT / DELETE / PIN MESSAGE
# ============================================================
@router.post("/messages/edit")
async def message_edit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("message_id", 0))
    new_text = data.get("text", "")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("UPDATE messages SET text=$1, edited=TRUE WHERE id=$2 AND user_id=$3 RETURNING id",
            new_text, mid, user["id"])
    if not row: return {"ok": False, "reason": "not_found_or_not_yours"}
    await manager.broadcast({"type": "message_edited", "id": mid, "text": new_text})
    return {"ok": True}

@router.post("/messages/delete")
async def message_delete(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("message_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        if user.get("is_admin") or user["username"] == "_fan_beluga_":
            row = await conn.fetchrow("DELETE FROM messages WHERE id=$1 RETURNING id", mid)
        else:
            row = await conn.fetchrow("DELETE FROM messages WHERE id=$1 AND user_id=$2 RETURNING id", mid, user["id"])
    if not row: return {"ok": False}
    await manager.broadcast({"type": "message_deleted", "id": mid})
    return {"ok": True}

@router.post("/messages/pin")
async def message_pin(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("message_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT pinned FROM messages WHERE id=$1", mid)
        if not row: raise HTTPException(404, "Нет")
        new = not row["pinned"]
        await conn.execute("UPDATE messages SET pinned=$1 WHERE id=$2", new, mid)
    await manager.broadcast({"type": "message_pinned", "id": mid, "pinned": new})
    return {"ok": True, "pinned": new}

# ============================================================
# REACTIONS
# ============================================================
@router.post("/messages/reaction")
async def message_reaction(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("message_id", 0))
    emoji = data.get("emoji", "👍")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT reactions,channel_id FROM messages WHERE id=$1", mid)
        if not row: raise HTTPException(404, "Нет")
        chan = None
        if row["channel_id"]:
            chan = await conn.fetchrow("SELECT mode,paid_reaction_cost FROM channels WHERE id=$1", row["channel_id"])
        if chan and chan["mode"] == "paid_reactions":
            cost = chan["paid_reaction_cost"] or 10
            if (user.get("coins") or 0) < cost:
                raise HTTPException(400, f"Нужно {cost} 🏅")
            await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", cost, user["id"])
        react = json.loads(row["reactions"] or "{}")
        arr = react.get(emoji, [])
        if user["id"] in arr:
            arr.remove(user["id"])
        else:
            arr.append(user["id"])
        react[emoji] = arr
        await conn.execute("UPDATE messages SET reactions=$1 WHERE id=$2", json.dumps(react), mid)
    await manager.broadcast({"type": "reaction_update", "id": mid, "reactions": react})
    return {"ok": True}

# ============================================================
# SAVE / SAVED
# ============================================================
@router.post("/messages/save")
async def message_save(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("message_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        msg = await conn.fetchrow("SELECT text,user_id FROM messages WHERE id=$1", mid)
        if not msg: raise HTTPException(404, "Нет")
        await conn.execute("INSERT INTO saved_messages(user_id,message_id,text,from_user) VALUES($1,$2,$3,$4)",
            user["id"], mid, msg["text"], msg["user_id"])
    return {"ok": True}

@router.get("/messages/saved")
async def messages_saved(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT sm.id,sm.text,sm.created_at,u.username
            FROM saved_messages sm LEFT JOIN users u ON u.id=sm.from_user
            WHERE sm.user_id=$1 ORDER BY sm.id DESC""", user["id"])
    return [{"id":r["id"], "text":r["text"], "username":r["username"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

# ============================================================
# SEARCH MESSAGES
# ============================================================
@router.get("/messages/search")
async def messages_search(q: str, channel_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    q = (q or "").strip()
    if len(q) < 2: return []
    p = await get_pool()
    async with p.acquire() as conn:
        if channel_id:
            rows = await conn.fetch("""SELECT m.id,m.text,m.created_at,u.username
                FROM messages m JOIN users u ON u.id=m.user_id
                WHERE m.channel_id=$1 AND m.text ILIKE $2 ORDER BY m.id DESC LIMIT 50""", channel_id, f"%{q}%")
        else:
            rows = await conn.fetch("""SELECT m.id,m.text,m.created_at,u.username
                FROM messages m JOIN users u ON u.id=m.user_id
                WHERE m.text ILIKE $1 ORDER BY m.id DESC LIMIT 50""", f"%{q}%")
    return [{"id":r["id"], "text":r["text"], "username":r["username"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

# ============================================================
# THREADS
# ============================================================
@router.get("/threads/{msg_id}")
async def threads_get(msg_id: int, token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT t.id,t.text,t.created_at,u.username,u.avatar
            FROM threads t JOIN users u ON u.id=t.author_id
            WHERE t.root_msg=$1 ORDER BY t.id ASC""", msg_id)
    return [{"id":r["id"], "text":r["text"], "username":r["username"],
             "avatar":r["avatar"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@router.post("/threads/{msg_id}/reply")
async def threads_reply(msg_id: int, data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    text = (data.get("text") or "").strip()
    if not text: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO threads(root_msg,author_id,text) VALUES($1,$2,$3)",
            msg_id, user["id"], text)
        cnt = await conn.fetchval("SELECT COUNT(*) FROM threads WHERE root_msg=$1", msg_id)
    await manager.broadcast({"type": "thread_update", "root": msg_id, "count": cnt})
    return {"ok": True, "count": cnt}

# ============================================================
# STICKERS
# ============================================================
@router.get("/stickers/list")
async def stickers_list():
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            rows = await conn.fetch("""SELECT gift_id,name,emoji,image FROM custom_gifts
                WHERE is_sticker=TRUE ORDER BY created_at DESC""")
        return [{"id":r["gift_id"], "name":r["name"], "emoji":r["emoji"], "image":r["image"]} for r in rows]
    except: return []

# ============================================================
# STORIES
# ============================================================
@router.get("/stories/list")
async def stories_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT s.id,s.image,s.text,s.bg_color,s.created_at,s.user_id,
            u.username,u.avatar FROM stories s JOIN users u ON u.id=s.user_id
            WHERE s.expires_at>NOW() ORDER BY s.created_at DESC LIMIT 100""")
    return [{"id":r["id"], "image":r["image"], "text":r["text"], "bg_color":r["bg_color"],
             "username":r["username"], "avatar":r["avatar"], "user_id":r["user_id"],
             "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@router.post("/stories/create")
async def stories_create(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    image = (data.get("image") or "").strip() or None
    text = (data.get("text") or "").strip() or None
    bg = data.get("bg_color", "#000")
    if not image and not text: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO stories(user_id,image,text,bg_color) VALUES($1,$2,$3,$4)",
            user["id"], image, text, bg)
    await manager.broadcast({"type": "story_new", "user_id": user["id"], "username": user["username"]})
    return {"ok": True}

@router.post("/stories/react")
async def stories_react(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    sid = int(data.get("story_id", 0))
    emoji = data.get("emoji", "❤️")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT reactions,user_id FROM stories WHERE id=$1", sid)
        if not row: raise HTTPException(404, "Нет")
        react = json.loads(row["reactions"] or "{}")
        arr = react.get(emoji, [])
        if user["id"] in arr:
            arr.remove(user["id"])
        else:
            arr.append(user["id"])
        react[emoji] = arr
        await conn.execute("UPDATE stories SET reactions=$1 WHERE id=$2", json.dumps(react), sid)
    await manager.send_to(row["user_id"], {"type": "story_reaction", "emoji": emoji, "from": user["username"]})
    return {"ok": True}

@router.post("/stories/reply")
async def stories_reply(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    sid = int(data.get("story_id", 0))
    text = (data.get("text") or "").strip()
    if not text: raise HTTPException(400, "Пусто")
    p = await get_pool()
    async with p.acquire() as conn:
        st = await conn.fetchrow("SELECT user_id FROM stories WHERE id=$1", sid)
        if not st: raise HTTPException(404, "Нет")
        await conn.execute("INSERT INTO story_replies(story_id,from_user,text) VALUES($1,$2,$3)",
            sid, user["id"], text)
    await manager.send_to(st["user_id"], {"type": "story_reply", "username": user["username"], "text": text})
    return {"ok": True}