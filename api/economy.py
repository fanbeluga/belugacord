# BELUGACORD 2.5 — api/economy.py
# Банк, лотерея, аукцион, сундук, БП, ивенты, дейли, репы, команды, титулы
import json, random, datetime, time
from fastapi import APIRouter, HTTPException

from api._shared import (
    get_pool, get_current_user, is_premium, manager,
    active_events, active_tournament, custom_commands
)

router = APIRouter()

# ============================================================
# CHEST (Сундук дня)
# ============================================================
@router.get("/chest/status")
async def chest_status(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    now = datetime.datetime.now(datetime.timezone.utc)
    last = user.get("chest_at")
    available = not last or (now - last).total_seconds() >= 86400
    next_in = 0 if available else int(86400 - (now - last).total_seconds())
    return {"available": available, "next_in": next_in, "streak": user.get("chest_streak", 0)}

@router.post("/chest/open")
async def chest_open(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT chest_at,chest_streak FROM users WHERE id=$1", user["id"])
        now = datetime.datetime.now(datetime.timezone.utc)
        last = row["chest_at"]
        if last and (now - last).total_seconds() < 86400:
            raise HTTPException(400, "Рано")
        streak = row["chest_streak"] + 1 if last and (now - last).total_seconds() < 172800 else 1
        roll = random.random() * 100
        if roll < 0.1:
            await conn.execute("""UPDATE users SET premium_tier='premium',
                premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '7 days',
                chest_at=$1,chest_streak=$2 WHERE id=$3""", now, streak, user["id"])
            return {"ok": True, "type": "premium", "days": 7}
        elif roll < 3.1:
            await conn.execute("""UPDATE users SET premium_tier='premium',
                premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '2 days',
                chest_at=$1,chest_streak=$2 WHERE id=$3""", now, streak, user["id"])
            return {"ok": True, "type": "premium", "days": 2}
        elif roll < 6.1:
            await conn.execute("""UPDATE users SET premium_tier='premium',
                premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day',
                chest_at=$1,chest_streak=$2 WHERE id=$3""", now, streak, user["id"])
            return {"ok": True, "type": "premium", "days": 1}
        else:
            amount = random.randint(1, 10) + streak
            await conn.execute("""UPDATE users SET coins=coins+$1,chest_at=$2,chest_streak=$3
                WHERE id=$4""", amount, now, streak, user["id"])
            return {"ok": True, "type": "coins", "amount": amount, "streak": streak}

# ============================================================
# LOTTERY (Лотерея)
# ============================================================
@router.get("/lottery/status")
async def lottery_status(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        total = await conn.fetchval("SELECT COALESCE(SUM(tickets),0) FROM lottery")
        players = await conn.fetchval("SELECT COUNT(*) FROM lottery WHERE tickets>0")
        my = await conn.fetchval("SELECT tickets FROM lottery WHERE user_id=$1", user["id"]) or 0
        hist = await conn.fetch("""SELECT winner_name,amount,created_at FROM lottery_history
            ORDER BY id DESC LIMIT 10""")
        next_draw = 3600 - (int(time.time()) % 3600)
    return {
        "jackpot": total * 100,
        "tickets": my,
        "players": players,
        "next_in": next_draw,
        "history": [{"winner":r["winner_name"], "amount":r["amount"],
                     "created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in hist]
    }

@router.post("/lottery/buy")
async def lottery_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    if (user.get("coins") or 0) < 100: raise HTTPException(400, "Нужно 100 🏅")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-100 WHERE id=$1", user["id"])
        await conn.execute("""INSERT INTO lottery(user_id,tickets,updated_at) VALUES($1,1,NOW())
            ON CONFLICT (user_id) DO UPDATE SET tickets=lottery.tickets+1,updated_at=NOW()""", user["id"])
    return {"ok": True}

# ============================================================
# BANK (Банк)
# ============================================================
@router.get("/bank/status")
async def bank_status(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    dep = user.get("bank_deposit", 0) or 0
    last = user.get("bank_at")
    interest = 0
    if last and dep > 0:
        days = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() / 86400
        interest = int(dep * 0.015 * days)
    return {"deposit": dep, "interest": interest}

@router.post("/bank/deposit")
async def bank_deposit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    amt = int(data.get("amount", 0))
    if amt <= 0: raise HTTPException(400, "Сумма>0")
    if (user.get("coins") or 0) < amt: raise HTTPException(400, "Не хватает")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET coins=coins-$1,bank_deposit=bank_deposit+$1,
            bank_at=NOW() WHERE id=$2""", amt, user["id"])
    return {"ok": True}

@router.post("/bank/withdraw")
async def bank_withdraw(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT bank_deposit,bank_at FROM users WHERE id=$1", user["id"])
        if not row or not row["bank_deposit"]: raise HTTPException(400, "Пусто")
        days = (datetime.datetime.now(datetime.timezone.utc) - row["bank_at"]).total_seconds() / 86400 if row["bank_at"] else 0
        interest = int(row["bank_deposit"] * 0.015 * days)
        total = row["bank_deposit"] + interest
        await conn.execute("""UPDATE users SET coins=coins+$1,bank_deposit=0,bank_at=NULL
            WHERE id=$2""", total, user["id"])
    return {"ok": True, "got": total, "interest": interest}

# ============================================================
# AUCTION (Аукцион)
# ============================================================
@router.get("/auction/list")
async def auction_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE auction SET status='ended'
            WHERE ends_at<NOW() AND status='active'""")
        cur = await conn.fetchrow("""SELECT a.*,u.username AS leader FROM auction a
            LEFT JOIN users u ON u.id=a.current_bidder
            WHERE a.status='active' ORDER BY a.id DESC LIMIT 1""")
        if cur:
            timer = int((cur["ends_at"] - datetime.datetime.now(datetime.timezone.utc)).total_seconds())
            return {"current": {
                "id": cur["id"], "name": cur["item_name"], "emoji": cur["item_emoji"],
                "price": cur["current_price"] or cur["start_price"],
                "leader": cur["leader"], "timer": max(0, timer)
            }}
    return {"current": None}

@router.post("/auction/bid")
async def auction_bid(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    amt = int(data.get("amount", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        cur = await conn.fetchrow("""SELECT id,current_price,start_price,current_bidder
            FROM auction WHERE status='active' ORDER BY id DESC LIMIT 1""")
        if not cur: raise HTTPException(404, "Нет лота")
        min_price = max(cur["current_price"] or cur["start_price"], cur["start_price"]) + 1
        if amt < min_price: raise HTTPException(400, f"Мин {min_price}")
        if (user.get("coins") or 0) < amt: raise HTTPException(400, "Не хватает")
        if cur["current_bidder"]:
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",
                cur["current_price"], cur["current_bidder"])
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", amt, user["id"])
        await conn.execute("""UPDATE auction SET current_price=$1,current_bidder=$2
            WHERE id=$3""", amt, user["id"], cur["id"])
    return {"ok": True}

# ============================================================
# QUESTS (Ежедневные)
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
            premium_tier='premium',premium_expires=$2 WHERE id=$3""",
            info["cost"], new_exp, user["id"])
    return {"ok": True, "premium_until": new_exp.isoformat(), "days": info["days"]}

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
# BATTLE PASS
# ============================================================
@router.get("/bp/current")
async def bp_current(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        season = await conn.fetchrow("""SELECT * FROM bp_season WHERE active=TRUE
            ORDER BY id DESC LIMIT 1""")
        if not season: return {"active": False}
        prog = await conn.fetchrow("""SELECT xp,level,claimed FROM bp_progress
            WHERE user_id=$1 AND season_id=$2""", user["id"], season["id"])
        quests = await conn.fetch("SELECT id,name,description,goal,xp_reward FROM bp_quests WHERE active=TRUE")
        rewards = await conn.fetch("SELECT id,level,reward FROM bp_rewards WHERE active=TRUE ORDER BY level")
    my_xp = prog["xp"] if prog else 0
    my_level = prog["level"] if prog else 1
    claimed = json.loads(prog["claimed"] or "[]") if prog else []
    return {
        "active": True, "name": season["name"], "description": season["description"],
        "emoji": season["emoji"], "my_xp": my_xp, "my_level": my_level,
        "next_xp": my_level * 1000,
        "quests": [{"id":q["id"], "name":q["name"], "desc":q["description"],
                    "goal":q["goal"], "progress":0, "xp_reward":q["xp_reward"], "done":False} for q in quests],
        "rewards": [{"id":r["id"], "level":r["level"], "reward":r["reward"],
                     "unlocked": my_level >= r["level"] and str(r["id"]) not in claimed} for r in rewards]
    }

@router.post("/bp/claim")
async def bp_claim(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    level = int(data.get("level", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        season = await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: raise HTTPException(404, "Нет сезона")
        r = await conn.fetchrow("SELECT id,reward FROM bp_rewards WHERE level=$1 AND active=TRUE LIMIT 1", level)
        if not r: raise HTTPException(404, "Нет награды")
        prog = await conn.fetchrow("""SELECT id,level,claimed FROM bp_progress
            WHERE user_id=$1 AND season_id=$2""", user["id"], season["id"])
        if prog and prog["level"] < level: raise HTTPException(400, "Уровень мал")
        claimed = json.loads(prog["claimed"] or "[]") if prog else []
        rid = str(r["id"])
        if rid in claimed: raise HTTPException(400, "Уже забрано")
        claimed.append(rid)
        if prog:
            await conn.execute("UPDATE bp_progress SET claimed=$1 WHERE id=$2", json.dumps(claimed), prog["id"])
        else:
            await conn.execute("""INSERT INTO bp_progress(user_id,season_id,claimed)
                VALUES($1,$2,$3)""", user["id"], season["id"], json.dumps(claimed))
    return {"ok": True}

# ============================================================
# EVENTS (Ивенты)
# ============================================================
@router.get("/events/active")
async def events_active():
    now = datetime.datetime.now(datetime.timezone.utc)
    for e in active_events[:]:
        if e.get("end_at") and e["end_at"] <= now:
            e["active"] = False
    cur = [e for e in active_events if e.get("active")]
    if cur:
        e = cur[0]
        return {
            "active": True, "id": e["id"], "name": e["name"],
            "description": e.get("description"), "emoji": e.get("emoji", "🎉"),
            "event_type": e.get("event_type"), "multiplier": e.get("multiplier"),
            "end_at": e["end_at"].isoformat() if e.get("end_at") else None
        }
    return {"active": False}

# ============================================================
# LEVELS / REPUTATION
# ============================================================
@router.get("/levels/me")
async def levels_me(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"level": user.get("level", 1), "xp": user.get("xp", 0),
            "next_xp": user.get("level", 1) * 100}

@router.get("/levels/leaders")
async def levels_leaders():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT username,level,xp FROM users
            ORDER BY level DESC, xp DESC LIMIT 20""")
    return [dict(r) for r in rows]

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

@router.get("/rep/leaders")
async def rep_leaders():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT username,reputation FROM users ORDER BY reputation DESC LIMIT 20")
    return [dict(r) for r in rows]

# ============================================================
# TITLES
# ============================================================
TITLES_DEFAULT = [
    {"name":"Легенда","emoji":"🏅"},{"name":"Стример","emoji":"🎥"},
    {"name":"Олдфаг","emoji":"👴"},{"name":"Бета","emoji":"🧪"},
    {"name":"Админ","emoji":"🛡️"},{"name":"Меценат","emoji":"💰"}
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
# PREMIUM (перенесено из core, для единства)
# ============================================================
@router.get("/premium/status")
async def premium_status(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"is_premium": is_premium(user), "tier": user.get("premium_tier"),
            "expires": user["premium_expires"].isoformat() if user.get("premium_expires") else None}