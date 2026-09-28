# BELUGACORD 2.5 — api/games.py
# Игры, счёт, лидерборды, турниры
import datetime
from fastapi import APIRouter, HTTPException

from api._shared import (
    get_pool, get_current_user, GAME_LIST, grant_achievement, grant_xp,
    grant_quest_progress, active_tournament, manager, ADMIN_USERNAME
)

router = APIRouter()

# ============================================================
# SUBMIT SCORE
# ============================================================
@router.post("/games/submit")
async def games_submit(data: dict):
    user = await get_current_user(data.get("token"))
    if not user: raise HTTPException(401, "Не авторизован")
    game = data.get("game")
    score = int(data.get("score", 0))
    if game not in GAME_LIST: raise HTTPException(400, "Неизвестная игра")
    if score < 0 or score > 1000000: raise HTTPException(400, "Плохой счёт")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO game_scores(user_id,game,score) VALUES($1,$2,$3)",
            user["id"], game, score)
    if game == "snake" and score >= 100: await grant_achievement(user["id"], "snake_100")
    if game == "flappy" and score >= 50: await grant_achievement(user["id"], "flappy_50")
    await grant_xp(user["id"], 5)
    await grant_quest_progress(user["id"], "play_3_games", 1)
    return {"ok": True}

# ============================================================
# LEADERS
# ============================================================
@router.get("/games/leaders")
async def games_leaders(game: str):
    if game not in GAME_LIST: raise HTTPException(400, "Неизвестная игра")
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("""SELECT u.username,MAX(gs.score) AS best
            FROM game_scores gs JOIN users u ON u.id=gs.user_id
            WHERE gs.game=$1 GROUP BY u.id,u.username
            ORDER BY best DESC LIMIT 20""", game)
    return [{"username": r["username"], "score": r["best"]} for r in rows]

# ============================================================
# TOP3
# ============================================================
@router.get("/games/top3")
async def games_top3():
    p = await get_pool()
    result = {}
    async with p.acquire() as conn:
        for g in GAME_LIST:
            rows = await conn.fetch("""SELECT u.username,MAX(gs.score) AS best
                FROM game_scores gs JOIN users u ON u.id=gs.user_id
                WHERE gs.game=$1 GROUP BY u.id,u.username
                ORDER BY best DESC LIMIT 3""", g)
            result[g] = [{"username": r["username"], "score": r["best"]} for r in rows]
    return result

# ============================================================
# TOURNAMENT
# ============================================================
@router.get("/games/tournament")
async def games_tournament_get():
    return {
        "game": active_tournament.get("game"),
        "started_at": active_tournament.get("started_at").isoformat() if active_tournament.get("started_at") else None
    }

@router.post("/games/tournament_set")
async def games_tournament_set(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    game = data.get("game")
    if game and game not in GAME_LIST: raise HTTPException(400, "Неизвестная игра")
    if game is None:
        active_tournament["game"] = None
        active_tournament["started_at"] = None
    else:
        active_tournament["game"] = game
        active_tournament["started_at"] = datetime.datetime.now(datetime.timezone.utc)
    await manager.broadcast({"type": "tournament_update", "game": active_tournament.get("game")})
    return {"ok": True, "game": active_tournament.get("game")}

@router.post("/games/tournament_reset")
async def games_tournament_reset(data: dict):
    user = await get_current_user(data.get("token"))
    if not user or user["username"] != ADMIN_USERNAME: raise HTTPException(403, "Только владелец")
    game = data.get("game")
    if game not in GAME_LIST: raise HTTPException(400, "Неизвестная игра")
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM game_scores WHERE game=$1", game)
    if active_tournament.get("game") == game:
        active_tournament["started_at"] = datetime.datetime.now(datetime.timezone.utc)
    await manager.broadcast({"type": "tournament_update", "game": active_tournament.get("game")})
    return {"ok": True}

# ============================================================
# ITCH LIST (заглушка)
# ============================================================
@router.get("/itch/list")
async def itch_list():
    return {"games": [
        {"name": "Dungeon Dash", "url": "https://itch.io/embed-upload/0000?color=333333", "emoji": "🏰"},
        {"name": "Roguelike", "url": "https://itch.io/embed-upload/1111?color=333333", "emoji": "⚔️"}
    ]}