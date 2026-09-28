# BELUGACORD 2.5 — api/gifts.py
# Подарки, апгрейдер 2.0, NFT, кейсы, бекоины
import json, random, datetime
from fastapi import APIRouter, HTTPException

from api._shared import (
    get_pool, get_current_user, get_all_gifts, is_premium,
    grant_achievement, grant_quest_progress, apply_event_multiplier,
    upgrade_chance_bonus, manager, is_blocked
)

router = APIRouter()

# ============================================================
# GIFTS — LIST
# ============================================================
@router.get("/gifts/all")
async def gifts_all():
    g = await get_all_gifts()
    return [{"gift_id":k, "name":v["name"], "emoji":v.get("emoji"),
             "image":v.get("image"), "price":v["price"]} for k, v in g.items()]

@router.get("/gifts/list/{user_id}")
async def gifts_list(user_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT gift FROM gifts WHERE to_user=$1 ORDER BY id DESC", user_id)
    return {"gifts": [dict(r) for r in rows]}

# ============================================================
# GIFTS — SEND
# ============================================================
@router.post("/gifts/send")
async def gift_send(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gift_id = data.get("gift")
    g = await get_all_gifts()
    if gift_id not in g: raise HTTPException(400, "Нет подарка")
    gift = g[gift_id]
    price = gift["price"]
    if user.get("coins", 0) < price: raise HTTPException(400, "Не хватает")
    to_id = int(data.get("to_user", 0))
    if to_id == user["id"]: raise HTTPException(400, "Себе нельзя")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", price, user["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",
            user["id"], to_id, gift_id)
        await conn.execute("UPDATE users SET social_rating=social_rating+$1 WHERE id=$2",
            price, user["id"])
        cnt = await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1", user["id"])
        newrating = await conn.fetchval("SELECT social_rating FROM users WHERE id=$1", user["id"])
    if cnt == 1: await grant_achievement(user["id"], "first_gift")
    if newrating >= 100: await grant_achievement(user["id"], "rating_100")
    if newrating >= 10000: await grant_achievement(user["id"], "rating_10000")
    await manager.send_to(to_id, {
        "type": "gift_received",
        "gift_emoji": gift.get("emoji"),
        "gift_name": gift["name"],
        "gift_image": gift.get("image"),
        "from_name": user["username"]
    })
    await grant_quest_progress(user["id"], "give_gift", 1)
    return {"ok": True}

# ============================================================
# GIFTS — SELL
# ============================================================
@router.post("/gifts/sell")
async def gift_sell(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gift_id = data.get("gift")
    g = await get_all_gifts()
    if gift_id not in g: raise HTTPException(400, "Нет")
    price = g[gift_id]["price"]
    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",
            user["id"], gift_id)
        if not row: raise HTTPException(400, "Нет")
        await conn.execute("DELETE FROM gifts WHERE id=$1", row["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", price, user["id"])
    return {"ok": True, "got": price}

# ============================================================
# GIFTS — TRANSFER
# ============================================================
@router.post("/gifts/transfer")
async def gift_transfer(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    gift_id = data.get("gift")
    to_id = int(data.get("to_user", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        fr = await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",
            user["id"], to_id)
        if not fr: raise HTTPException(400, "Только друзьям")
        row = await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",
            user["id"], gift_id)
        if not row: raise HTTPException(400, "Нет")
        await conn.execute("UPDATE gifts SET to_user=$1, from_user=$2 WHERE id=$3",
            to_id, user["id"], row["id"])
        t = await conn.fetchrow("SELECT username FROM users WHERE id=$1", to_id)
    return {"ok": True, "to": t["username"]}

# ============================================================
# UPGRADE WHEEL 2.0
# ============================================================
@router.post("/gifts/upgrade_wheel")
async def gifts_upgrade_wheel(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    from_id = data.get("from_gift")
    to_id = data.get("to_gift")
    multiplier = int(data.get("multiplier", 2))

    g = await get_all_gifts()
    if from_id not in g or to_id not in g:
        raise HTTPException(400, "Нет подарка")
    if g[to_id]["price"] <= g[from_id]["price"]:
        raise HTTPException(400, "Цель должна быть дороже")

    chance_map = {2: 75, 4: 50, 6: 25, 8: 12.5}
    base_chance = chance_map.get(multiplier, 75)
    bonus = upgrade_chance_bonus.get(user["id"], 0)
    chance = max(1, min(100, base_chance + bonus))

    p = await get_pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 ORDER BY id LIMIT 1",
            user["id"], from_id)
        if not row: raise HTTPException(400, "Нет у тебя такого")

        roll = random.random() * 100
        success = roll <= chance

        await conn.execute("DELETE FROM gifts WHERE id=$1", row["id"])
        if success:
            await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",
                user["id"], user["id"], to_id)
        await conn.execute("""INSERT INTO upgrade_log(user_id,from_gift,to_gift,success,chance)
            VALUES($1,$2,$3,$4,$5)""", user["id"], from_id, to_id, success, chance)

    if success:
        return {"ok": True, "success": True, "got_name": g[to_id]["name"], "chance": chance}
    return {"ok": True, "success": False, "chance": chance}

# ============================================================
# NFT — LIST
# ============================================================
@router.get("/nft/list")
async def nft_list():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM nft_series WHERE sold<total ORDER BY id DESC")
    return [{"id":r["id"], "name":r["name"], "emoji":r["emoji"], "image":r.get("image"),
             "price":r["price"], "total":r["total"], "sold":r["sold"], "rarity":r["rarity"],
             "number":(r["sold"] or 0) + 1} for r in rows]

@router.get("/nft/my")
async def nft_my(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT ni.id,ni.number,ns.name,ns.emoji,ns.image,ns.price,ns.total,ns.rarity
            FROM nft_items ni JOIN nft_series ns ON ns.id=ni.series_id
            WHERE ni.owner_id=$1 ORDER BY ni.id DESC""", user["id"])
    return [dict(r) for r in rows]

@router.post("/nft/buy")
async def nft_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    nid = int(data.get("nft_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        s = await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1", nid)
        if not s: raise HTTPException(404, "Нет")
        if s["sold"] >= s["total"]: raise HTTPException(400, "Распродано")
        if user.get("coins", 0) < s["price"]: raise HTTPException(400, "Не хватает")
        num = s["sold"] + 1
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", s["price"], user["id"])
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",
            nid, num, user["id"])
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1", nid)
        cnt = await conn.fetchval("SELECT COUNT(*) FROM nft_items WHERE owner_id=$1", user["id"])
    if cnt == 1: await grant_achievement(user["id"], "first_nft")
    return {"ok": True, "number": num}

@router.post("/nft/sell")
async def nft_sell(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    item_id = int(data.get("item_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        item = await conn.fetchrow("""SELECT ni.id,ni.owner_id,ns.price FROM nft_items ni
            JOIN nft_series ns ON ns.id=ni.series_id WHERE ni.id=$1""", item_id)
        if not item: raise HTTPException(404, "Не найден")
        if item["owner_id"] != user["id"]: raise HTTPException(403, "Не твой")
        sp = item["price"] // 2
        await conn.execute("DELETE FROM nft_items WHERE id=$1", item_id)
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", sp, user["id"])
    return {"ok": True, "got": sp}

@router.get("/nft_market/list")
async def nft_market_list(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT nm.id,nm.price,nm.seller_id,ni.id AS item_id,ni.number,
            ns.name,ns.emoji,ns.image,ns.rarity,u.username AS seller_name
            FROM nft_market nm JOIN nft_items ni ON ni.id=nm.item_id
            JOIN nft_series ns ON ns.id=ni.series_id JOIN users u ON u.id=nm.seller_id
            WHERE nm.status='active' ORDER BY nm.id DESC""")
    return [{"id":r["id"], "item_id":r["item_id"], "price":r["price"], "number":r["number"],
             "name":r["name"], "emoji":r["emoji"], "image":r["image"], "rarity":r["rarity"],
             "seller_id":r["seller_id"], "seller_name":r["seller_name"]} for r in rows]

@router.post("/nft_market/sell")
async def nft_market_sell(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    item_id = int(data.get("item_id", 0))
    price = int(data.get("price", 0))
    if price <= 0: raise HTTPException(400, "Цена >0")
    p = await get_pool()
    async with p.acquire() as conn:
        item = await conn.fetchrow("SELECT owner_id FROM nft_items WHERE id=$1", item_id)
        if not item: raise HTTPException(404, "Не найден")
        if item["owner_id"] != user["id"]: raise HTTPException(403, "Не твой")
        if await conn.fetchrow("SELECT id FROM nft_market WHERE item_id=$1 AND status='active'", item_id):
            raise HTTPException(400, "Уже на рынке")
        await conn.execute("INSERT INTO nft_market(item_id,seller_id,price) VALUES($1,$2,$3)",
            item_id, user["id"], price)
    return {"ok": True}

@router.post("/nft_market/buy")
async def nft_market_buy(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    mid = int(data.get("market_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        m = await conn.fetchrow("SELECT * FROM nft_market WHERE id=$1 AND status='active'", mid)
        if not m: raise HTTPException(404, "Нет лота")
        if m["seller_id"] == user["id"]: raise HTTPException(400, "Свой лот")
        if user.get("coins", 0) < m["price"]: raise HTTPException(400, "Не хватает")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", m["price"], user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", m["price"], m["seller_id"])
        await conn.execute("UPDATE nft_items SET owner_id=$1 WHERE id=$2", user["id"], m["item_id"])
        await conn.execute("UPDATE nft_market SET status='sold' WHERE id=$1", mid)
    await manager.send_to(m["seller_id"], {"type": "nft_sold", "price": m["price"]})
    return {"ok": True}

# ============================================================
# CASES
# ============================================================
@router.get("/cases/list")
async def cases_list():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT id,name,emoji,image,price FROM cases WHERE is_active=TRUE ORDER BY id DESC")
    return [dict(r) for r in rows]

@router.get("/cases/{case_id}/prizes")
async def case_prizes(case_id: int):
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT kind,item_id,item_name,item_emoji,item_image,chance,
            coins_min,coins_max FROM case_prizes WHERE case_id=$1 ORDER BY chance DESC""", case_id)
    return [dict(r) for r in rows]

@router.post("/cases/open")
async def cases_open(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    cid = int(data.get("case_id", 0))
    p = await get_pool()
    async with p.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM cases WHERE id=$1 AND is_active=TRUE", cid)
        if not c: raise HTTPException(404, "Нет кейса")
        if user.get("coins", 0) < c["price"]: raise HTTPException(400, "Не хватает")
        prizes = await conn.fetch("SELECT * FROM case_prizes WHERE case_id=$1", cid)
        if not prizes: raise HTTPException(400, "Нет призов")
        total = sum(p["chance"] for p in prizes)
        roll = random.randint(1, total)
        acc = 0
        chosen = None
        for p in prizes:
            acc += p["chance"]
            if roll <= acc:
                chosen = p
                break
        if not chosen: chosen = prizes[-1]
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", c["price"], user["id"])

        if chosen["kind"] == "coins":
            amt = random.randint(chosen["coins_min"] or 1, chosen["coins_max"] or chosen["coins_min"] or 1)
            amt = apply_event_multiplier(amt, "coins_x")
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", amt, user["id"])
            prize_text = f"🏅 {amt} бекоинов"
        elif chosen["kind"] == "gift":
            gid = chosen["item_id"]
            if gid:
                await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",
                    user["id"], user["id"], gid)
            prize_text = f"🎀 {chosen['item_name'] or gid}"
        elif chosen["kind"] == "nft":
            try:
                nid = int(chosen["item_id"])
                s = await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1", nid)
                if s and s["sold"] < s["total"]:
                    num = s["sold"] + 1
                    await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",
                        nid, num, user["id"])
                    await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1", nid)
                    prize_text = f"🎨 {s['name']} #{num}"
                else:
                    prize_text = "😢 пусто"
            except:
                prize_text = "😢 пусто"
        else:
            prize_text = f"❓ {chosen['item_name'] or '???'}"

        await conn.execute("INSERT INTO case_opens(user_id,case_id,prize_text) VALUES($1,$2,$3)",
            user["id"], cid, prize_text)
    await grant_quest_progress(user["id"], "open_1_case", 1)
    return {"ok": True, "prize": prize_text}

# ============================================================
# COINS — BALANCE
# ============================================================
@router.get("/coins/balance")
async def coins_balance(token: str):
    user = await get_current_user(token)
    if not user: raise HTTPException(401, "Не авторизован")
    return {"coins": user.get("coins", 0), "social_rating": user.get("social_rating", 0)}

# ============================================================
# COINS — REQUEST (заявка владельцу)
# ============================================================
@router.post("/coins/request")
async def coins_request(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO coin_requests(user_id,coins,price) VALUES($1,$2,$3)",
            user["id"], int(data.get("coins", 0)), int(data.get("price", 0)))
    return {"ok": True}

# ============================================================
# COINS — TRANSFER
# ============================================================
@router.post("/coins/transfer")
async def coins_transfer(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    tid = int(data.get("to_user", 0))
    amt = int(data.get("amount", 0))
    if amt <= 0: raise HTTPException(400, "Сумма >0")
    if user.get("coins", 0) < amt: raise HTTPException(400, "Не хватает")
    p = await get_pool()
    async with p.acquire() as conn:
        fr = await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",
            user["id"], tid)
        if not fr: raise HTTPException(400, "Только друзьям")
        if await is_blocked(user["id"], tid): raise HTTPException(403, "Заблокирован")
        t = await conn.fetchrow("SELECT username FROM users WHERE id=$1", tid)
        if not t: raise HTTPException(404, "Не найден")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2", amt, user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2", amt, tid)
    await manager.send_to(tid, {"type": "coins_received", "amount": amt, "from_name": user["username"]})
    return {"ok": True, "to": t["username"]}

# ============================================================
# COINS — LEADERS
# ============================================================
@router.get("/coins/leaders")
async def coins_leaders():
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT username,coins FROM users ORDER BY coins DESC LIMIT 20")
    return [dict(r) for r in rows]