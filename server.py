# BELUGACORD 2.8 — server.py
# Часть 1/2: ядро, БД, helpers, BP 50 заданий, квест-линия, все базовые эндпоинты

import os,json,time,secrets,hashlib,random,datetime,asyncio,re
from typing import Optional
import asyncpg
import httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL=os.environ.get("DATABASE_URL","")
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)

_env_secret=os.environ.get("SECRET_KEY","")
if _env_secret:
    SECRET_KEY=_env_secret
else:
    _secret_file=".secret_key"
    if os.path.exists(_secret_file):
        try:
            with open(_secret_file,"r") as f: SECRET_KEY=f.read().strip()
        except: SECRET_KEY=secrets.token_hex(32)
    else:
        SECRET_KEY=secrets.token_hex(32)
        try:
            with open(_secret_file,"w") as f: f.write(SECRET_KEY)
        except: pass

RESEND_API_KEY=os.environ.get("RESEND_API_KEY","")
ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME","_fan_beluga_")
OWNER_PASSWORD=os.environ.get("OWNER_PASSWORD","1234")
CURRENT_VERSION="2.8"
SUPPORT_BOT_ID=0
SUPPORT_BOT_NAME="support_bot"
SUPPORT_BOT_DISPLAY="🤖 Support Bot"

ALLOWED_EXT={'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mov','.mp3','.wav','.ogg','.m4a','.pdf','.txt','.zip','.json'}
ALLOWED_MIME={'image/png','image/jpeg','image/gif','image/webp','image/svg+xml','video/mp4','video/webm','video/quicktime','audio/mpeg','audio/wav','audio/ogg','audio/mp4','audio/webm','application/pdf','text/plain','application/zip','application/json','application/octet-stream'}

LIMITS={None:{"file":10*1024*1024,"msg":2000,"servers":10,"channels":20,"groups":10},"premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100,"groups":30},"pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999,"groups":30}}
PREMIUM_PRICES={"month":1500,"year":18000}

DEFAULT_GIFTS={
    "rose":{"name":"Роза","emoji":"🌹","price":15},
    "bear":{"name":"Мишка","emoji":"🧸","price":25},
    "cake":{"name":"Торт","emoji":"🎂","price":50},
    "diamond":{"name":"Алмаз","emoji":"💎","price":100},
    "crown":{"name":"Корона","emoji":"👑","price":500},
    "dragon":{"name":"Дракон","emoji":"🐉","price":1000},
    "legend":{"name":"Легендарка","emoji":"💠","price":5000},
    "pumpkin":{"name":"Тыква","emoji":"🎃","price":150},
    "ghost":{"name":"Призрак","emoji":"👻","price":250},
    "skull":{"name":"Череп","emoji":"💀","price":400},
    "bat":{"name":"Летучая мышь","emoji":"🦇","price":300},
    "witch":{"name":"Ведьма","emoji":"🧙","price":800},
    "vampire":{"name":"Вампир","emoji":"🧛","price":900},
    "spider":{"name":"Паук","emoji":"🕷️","price":200},
    "candy_gift":{"name":"Конфета","emoji":"🍬","price":100},
    "candle":{"name":"Свеча","emoji":"🕯️","price":180},
    "tree":{"name":"Ёлка","emoji":"🎄","price":200},
    "santa":{"name":"Дед Мороз","emoji":"🎅","price":400},
    "snowman":{"name":"Снеговик","emoji":"⛄","price":150},
    "snowflake":{"name":"Снежинка","emoji":"❄️","price":100},
    "bell":{"name":"Колокольчик","emoji":"🔔","price":120},
    "giftbox":{"name":"Подарок","emoji":"🎁","price":250},
    "champagne":{"name":"Шампанское","emoji":"🍾","price":500},
    "sock":{"name":"Носок","emoji":"🧦","price":80},
    "heart":{"name":"Сердце","emoji":"❤️","price":50},
    "hearts":{"name":"Сердечки","emoji":"💕","price":100},
    "bouquet":{"name":"Букет","emoji":"💐","price":200},
    "chocolate":{"name":"Шоколад","emoji":"🍫","price":150},
    "kiss":{"name":"Поцелуй","emoji":"💋","price":300},
    "love_letter":{"name":"Love Letter","emoji":"💌","price":400},
    "balloon":{"name":"Шарик","emoji":"🎈","price":80},
    "party":{"name":"Хлопушка","emoji":"🎉","price":150},
    "cupcake":{"name":"Капкейк","emoji":"🧁","price":120},
    "sparkles":{"name":"Искры","emoji":"✨","price":100},
    "crown_bd":{"name":"Праздничная корона","emoji":"👑","price":600},
    "book":{"name":"Книга","emoji":"📚","price":150},
    "pencil":{"name":"Карандаш","emoji":"✏️","price":50},
    "apple":{"name":"Яблоко","emoji":"🍎","price":80},
    "graduation":{"name":"Диплом","emoji":"🎓","price":500},
    "backpack":{"name":"Рюкзак","emoji":"🎒","price":200},
    "notebook":{"name":"Тетрадь","emoji":"📓","price":100},
    "paperclip":{"name":"Скрепка","emoji":"📎","price":30},
    "ruler":{"name":"Линейка","emoji":"📏","price":60},
    "russia_flag":{"name":"Флаг России","emoji":"🇷🇺","price":300},
    "bear_ru":{"name":"Медведь","emoji":"🐻","price":400},
    "sun_ru":{"name":"Солнце","emoji":"☀️","price":200},
    "castle_ru":{"name":"Кремль","emoji":"🏰","price":700},
    "usa_flag":{"name":"Флаг США","emoji":"🇺🇸","price":300},
    "eagle":{"name":"Орёл","emoji":"🦅","price":400},
    "statue":{"name":"Статуя Свободы","emoji":"🗽","price":800},
    "burger":{"name":"Бургер","emoji":"🍔","price":100},
    "hotdog":{"name":"Хот-дог","emoji":"🌭","price":100},
    "easter_egg":{"name":"Пасхальное яйцо","emoji":"🥚","price":150},
    "bunny":{"name":"Кролик","emoji":"🐰","price":250},
    "chick":{"name":"Цыплёнок","emoji":"🐣","price":180},
    "tulip":{"name":"Тюльпан","emoji":"🌷","price":120},
    "dove":{"name":"Голубь","emoji":"🕊️","price":300},
    "alien":{"name":"Инопланетянин","emoji":"👽","price":10000},
    "galaxy":{"name":"Галактика","emoji":"🌌","price":100000},
    "goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},
    "universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000},
}

GAME_LIST=["snake","tetris","2048","memory","tictactoe","rps","duel","teacher_quiz","chess","checkers","uno","quiz_battle","pvp"]

ACHIEVEMENTS={
    "first_msg":{"name":"Первое слово","emoji":"💬","desc":"Отправь первое сообщение"},
    "msg_100":{"name":"Болтун","emoji":"🗣️","desc":"100 сообщений"},
    "msg_1000":{"name":"Оратор","emoji":"🎤","desc":"1000 сообщений"},
    "msg_10000":{"name":"Легенда чата","emoji":"📢","desc":"10000 сообщений"},
    "first_friend":{"name":"Дружелюбный","emoji":"👥","desc":"Первый друг"},
    "friend_10":{"name":"Тусовщик","emoji":"🎉","desc":"10 друзей"},
    "first_gift":{"name":"Щедрый","emoji":"🎁","desc":"Первый подарок"},
    "first_nft":{"name":"Коллекционер","emoji":"🎨","desc":"Первый NFT"},
    "snake_100":{"name":"Змеелов","emoji":"🐍","desc":"100 очков в Змейке"},
    "first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},
    "coins_10k":{"name":"Богач","emoji":"💰","desc":"10000 бекоинов"},
    "rating_100":{"name":"Щедрая душа","emoji":"💎","desc":"Рейтинг 100"},
    "rating_10000":{"name":"Меценат","emoji":"👑","desc":"Рейтинг 10000"},
    "halloween_10":{"name":"Тыква-новичок","emoji":"🎃","desc":"10 конфет"},
    "halloween_100":{"name":"Тыквенный лорд","emoji":"🎃","desc":"100 конфет"},
    "halloween_500":{"name":"Владыка Хэллоуина","emoji":"👻","desc":"500 конфет"},
    "teacher_quiz_all":{"name":"Отличник","emoji":"🎓","desc":"Пройди викторину"},
    "teacher_perfect":{"name":"Учитель года","emoji":"📚","desc":"Без ошибок"},
    "scam_cleared":{"name":"Чистая репутация","emoji":"✅","desc":"Снят SCAM"},
    "reporter":{"name":"Бдительный","emoji":"🚨","desc":"Первая жалоба"},
    "title_master":{"name":"Мастер титулов","emoji":"👑","desc":"Создай свой титул"},
    "pvp_win":{"name":"Гладиатор","emoji":"⚔️","desc":"Победа на арене"},
    "trader":{"name":"Торговец","emoji":"📈","desc":"Первая сделка на бирже"},
    "crafter":{"name":"Крафтер","emoji":"⚒️","desc":"Первый крафт"},
    "auctioneer":{"name":"Аукционист","emoji":"🔨","desc":"Выиграл аукцион"},
    "credit_ok":{"name":"Надёжный","emoji":"💳","desc":"Погасил кредит"},
}

HOLIDAYS=[
    ("01-01","newyear","Новый год","🎄","#dc2626","world"),
    ("01-07","christmas_orthodox","Православное Рождество","✝️","#fbbf24","ru"),
    ("02-14","valentine","День Валентина","💕","#ec4899","world"),
    ("02-23","defender_day","День защитника Отечества","🎖️","#22c55e","ru"),
    ("03-08","womens_day","Международный женский день","🌷","#f472b6","world"),
    ("04-01","fools_day","День смеха","🤡","#facc15","world"),
    ("04-12","cosmonautics","День космонавтики","🚀","#3b82f6","ru"),
    ("05-01","labour_day","День труда","⚒️","#dc2626","world"),
    ("05-09","victory_day","День Победы","🎖️","#f97316","ru"),
    ("06-01","children_day","День защиты детей","🧒","#22d3ee","world"),
    ("06-12","russia_day","День России","🇷🇺","#ffffff","ru"),
    ("07-04","usa_independence","День независимости США","🇺🇸","#3b82f6","us"),
    ("07-08","family_day","День семьи","👨‍👩‍👧","#f97316","ru"),
    ("09-01","knowledge_day","День знаний","📚","#8b5cf6","ru"),
    ("10-01","teachers_day","День учителя","🍎","#f59e0b","world"),
    ("10-31","halloween","Хэллоуин","🎃","#ff6b1a","world"),
    ("11-04","unity_day","День народного единства","🤝","#dc2626","ru"),
    ("11-24","thanksgiving","День благодарения","🦃","#92400e","us"),
    ("11-28","mothers_day","День матери","💐","#f472b6","world"),
    ("12-25","christmas_catholic","Католическое Рождество","🎅","#dc2626","world"),
    ("03-20","spring_day","Первый день весны","🌸","#f472b6","world"),
    ("06-21","summer_solstice","Летнее солнцестояние","☀️","#fbbf24","world"),
    ("09-22","autumn_day","Первый день осени","🍂","#d97706","world"),
    ("12-21","winter_solstice","Зимнее солнцестояние","❄️","#22d3ee","world"),
]

DEFAULT_CANDY_CURRENCIES={
    "halloween":{"name":"Конфеты","emoji":"🍬"},
    "newyear":{"name":"Ёлочные шарики","emoji":"🎄"},
    "easter":{"name":"Яйца","emoji":"🥚"},
    "valentine":{"name":"Сердечки","emoji":"❤️"},
    "teacher":{"name":"Яблоки","emoji":"🍎"},
    "birthday":{"name":"Шарики","emoji":"🎈"},
}

DEFAULT_CANDY_SHOP=[
    {"id":"ghost_frame","emoji":"👻","name":"Рамка Призрак","price":50,"kind":"frame","item":"ghost"},
    {"id":"pumpkin_frame","emoji":"🎃","name":"Рамка Тыква","price":80,"kind":"frame","item":"pumpkin"},
    {"id":"bat_frame","emoji":"🦇","name":"Рамка Мышь","price":60,"kind":"frame","item":"bat"},
    {"id":"teacher_frame","emoji":"🎓","name":"Рамка Учитель","price":300,"kind":"frame","item":"teacher"},
    {"id":"vampire_title","emoji":"🧛","name":"Титул Вампир","price":200,"kind":"title","item":"🧛 Вампир"},
    {"id":"witch_title","emoji":"🧙","name":"Титул Ведьма","price":250,"kind":"title","item":"🧙 Ведьма"},
    {"id":"candy_gift","emoji":"🍬","name":"5× Торт","price":30,"kind":"gift","item":"cake","count":5},
    {"id":"pumpkin_gift","emoji":"🎃","name":"3× Тыква","price":100,"kind":"gift","item":"pumpkin","count":3},
    {"id":"premium_1d","emoji":"💎","name":"Premium 1 день","price":500,"kind":"premium","value":1},
    {"id":"coins_1000","emoji":"💰","name":"1000 бекоинов","price":150,"kind":"coins","value":1000},
]

DEFAULT_TEACHER_QUIZ=[
    {"q":"Сколько будет 7 × 8?","a":["54","56","64"],"correct":1},
    {"q":"Кто написал «Война и мир»?","a":["Достоевский","Толстой","Пушкин"],"correct":1},
    {"q":"Какой газ преобладает в атмосфере Земли?","a":["Кислород","Азот","Углекислый газ"],"correct":1},
    {"q":"Столица Франции?","a":["Лондон","Париж","Берлин"],"correct":1},
    {"q":"Сколько букв в русском алфавите?","a":["31","33","35"],"correct":1},
    {"q":"Кто открыл закон всемирного тяготения?","a":["Эйнштейн","Ньютон","Галилей"],"correct":1},
    {"q":"Самая длинная река в мире?","a":["Амазонка","Нил","Янцзы"],"correct":0},
    {"q":"Химический символ золота?","a":["Au","Ag","Go"],"correct":0},
    {"q":"Сколько континентов на Земле?","a":["6","7","8"],"correct":1},
    {"q":"Кто написал «Евгений Онегин»?","a":["Лермонтов","Пушкин","Гоголь"],"correct":1},
    {"q":"Год начала Второй мировой войны?","a":["1939","1941","1945"],"correct":0},
    {"q":"Какой океан самый большой?","a":["Атлантический","Тихий","Индийский"],"correct":1},
    {"q":"Формула воды?","a":["H2O","CO2","O2"],"correct":0},
    {"q":"Кто автор «Гарри Поттера»?","a":["Дж. Роулинг","Толкин","Льюис"],"correct":0},
    {"q":"Сколько сторон у ромба?","a":["3","4","5"],"correct":1},
    {"q":"Планета, ближайшая к Солнцу?","a":["Венера","Меркурий","Земля"],"correct":1},
    {"q":"Кто написал «Преступление и наказание»?","a":["Толстой","Достоевский","Тургенев"],"correct":1},
    {"q":"Сколько дней в високосном году?","a":["365","366","367"],"correct":1},
    {"q":"Столица Японии?","a":["Сеул","Токио","Пекин"],"correct":1},
    {"q":"Какой зверь — символ мудрости?","a":["Сова","Лев","Тигр"],"correct":0},
]

# ==== АВТО-СТАРТ БП: 50 заданий ====
AUTO_BP_QUESTS=[
    {"name":"Напиши 5 сообщений","action_type":"send_message","target_count":5,"xp_reward":50},
    {"name":"Напиши 10 сообщений","action_type":"send_message","target_count":10,"xp_reward":100},
    {"name":"Напиши 25 сообщений","action_type":"send_message","target_count":25,"xp_reward":250},
    {"name":"Напиши 50 сообщений","action_type":"send_message","target_count":50,"xp_reward":500},
    {"name":"Напиши 100 сообщений","action_type":"send_message","target_count":100,"xp_reward":1000},
    {"name":"Напиши 250 сообщений","action_type":"send_message","target_count":250,"xp_reward":2500},
    {"name":"Напиши 500 сообщений","action_type":"send_message","target_count":500,"xp_reward":5000},
    {"name":"Напиши 1000 сообщений","action_type":"send_message","target_count":1000,"xp_reward":10000},
    {"name":"Отправь 3 DM","action_type":"send_dm","target_count":3,"xp_reward":150},
    {"name":"Отправь 10 DM","action_type":"send_dm","target_count":10,"xp_reward":500},
    {"name":"Отправь 50 DM","action_type":"send_dm","target_count":50,"xp_reward":2500},
    {"name":"Сыграй 1 игру","action_type":"play_game","target_count":1,"xp_reward":50},
    {"name":"Сыграй 3 игры","action_type":"play_game","target_count":3,"xp_reward":150},
    {"name":"Сыграй 10 игр","action_type":"play_game","target_count":10,"xp_reward":500},
    {"name":"Сыграй 25 игр","action_type":"play_game","target_count":25,"xp_reward":1500},
    {"name":"Сыграй 50 игр","action_type":"play_game","target_count":50,"xp_reward":3000},
    {"name":"Поставь 5 реакций","action_type":"react","target_count":5,"xp_reward":100},
    {"name":"Поставь 25 реакций","action_type":"react","target_count":25,"xp_reward":500},
    {"name":"Поставь 100 реакций","action_type":"react","target_count":100,"xp_reward":2000},
    {"name":"Добавь 1 друга","action_type":"add_friend","target_count":1,"xp_reward":200},
    {"name":"Добавь 3 друга","action_type":"add_friend","target_count":3,"xp_reward":600},
    {"name":"Добавь 10 друзей","action_type":"add_friend","target_count":10,"xp_reward":2000},
    {"name":"Подари 1 подарок","action_type":"give_gift","target_count":1,"xp_reward":300},
    {"name":"Подари 5 подарков","action_type":"give_gift","target_count":5,"xp_reward":1500},
    {"name":"Подари 20 подарков","action_type":"give_gift","target_count":20,"xp_reward":6000},
    {"name":"Открой 1 кейс","action_type":"open_case","target_count":1,"xp_reward":200},
    {"name":"Открой 5 кейсов","action_type":"open_case","target_count":5,"xp_reward":1000},
    {"name":"Открой 20 кейсов","action_type":"open_case","target_count":20,"xp_reward":4000},
    {"name":"Купи 1 NFT","action_type":"buy_nft","target_count":1,"xp_reward":500},
    {"name":"Купи 3 NFT","action_type":"buy_nft","target_count":3,"xp_reward":1500},
    {"name":"Купи 10 NFT","action_type":"buy_nft","target_count":10,"xp_reward":5000},
    {"name":"Победи в 1 дуэли","action_type":"win_duel","target_count":1,"xp_reward":200},
    {"name":"Победи в 5 дуэлях","action_type":"win_duel","target_count":5,"xp_reward":1000},
    {"name":"Победи в 20 дуэлях","action_type":"win_duel","target_count":20,"xp_reward":4000},
    {"name":"Собери 10 конфет","action_type":"collect_candy","target_count":10,"xp_reward":100},
    {"name":"Собери 50 конфет","action_type":"collect_candy","target_count":50,"xp_reward":500},
    {"name":"Собери 100 конфет","action_type":"collect_candy","target_count":100,"xp_reward":1000},
    {"name":"Собери 500 конфет","action_type":"collect_candy","target_count":500,"xp_reward":5000},
    {"name":"Установи рамку","action_type":"set_frame","target_count":1,"xp_reward":100},
    {"name":"Опубликуй сторис","action_type":"post_story","target_count":1,"xp_reward":300},
    {"name":"Зайди 2 дня подряд","action_type":"daily_streak","target_count":2,"xp_reward":200},
    {"name":"Зайди 7 дней подряд","action_type":"daily_streak","target_count":7,"xp_reward":1000},
    {"name":"Зайди 30 дней подряд","action_type":"daily_streak","target_count":30,"xp_reward":5000},
    {"name":"Достигни 5 уровня","action_type":"reach_level","target_count":5,"xp_reward":500},
    {"name":"Достигни 10 уровня","action_type":"reach_level","target_count":10,"xp_reward":1500},
    {"name":"Достигни 25 уровня","action_type":"reach_level","target_count":25,"xp_reward":5000},
    {"name":"Достигни 50 уровня","action_type":"reach_level","target_count":50,"xp_reward":15000},
    {"name":"Победи в турнире","action_type":"win_tournament","target_count":1,"xp_reward":10000},
    {"name":"Напиши владельцу","action_type":"write_owner","target_count":1,"xp_reward":50000},
    {"name":"Накопи 100000 бекоинов","action_type":"save_coins","target_count":100000,"xp_reward":50000},
]

AUTO_BP_REWARDS=[
    {"level":1,"reward":"💰 100 бекоинов","reward_type":"coins","reward_value":100,"track":"free"},
    {"level":1,"reward":"💎 Premium 1д","reward_type":"premium","reward_value":1,"track":"premium"},
    {"level":2,"reward":"🎨 Рамка «Тыква»","reward_type":"frame","reward_value":1,"reward_item_id":"pumpkin","track":"free"},
    {"level":3,"reward":"👑 Титул «Призрак»","reward_type":"title","reward_value":1,"reward_item_id":"👻 Призрак","track":"free"},
    {"level":3,"reward":"🎨 Рамка «Мышь» + 💰 2000","reward_type":"frame","reward_value":1,"reward_item_id":"bat","track":"premium"},
    {"level":4,"reward":"💰 500 бекоинов","reward_type":"coins","reward_value":500,"track":"free"},
    {"level":5,"reward":"🎟️ 100 КП","reward_type":"kp","reward_value":100,"track":"free"},
    {"level":5,"reward":"💎 Premium 7д","reward_type":"premium","reward_value":7,"track":"premium"},
    {"level":7,"reward":"💎 Premium 3 дня","reward_type":"premium","reward_value":3,"track":"free"},
    {"level":8,"reward":"👑 Титул «Вампир»","reward_type":"title","reward_value":1,"reward_item_id":"🧛 Вампир","track":"free"},
    {"level":9,"reward":"🍬 50 конфет","reward_type":"candy","reward_value":50,"track":"free"},
    {"level":10,"reward":"💰 50000 бекоинов","reward_type":"coins","reward_value":50000,"track":"free"},
    {"level":10,"reward":"👑 Титул «Владыка тьмы»","reward_type":"title","reward_value":1,"reward_item_id":"💀 Владыка тьмы","track":"premium"},
    {"level":15,"reward":"💰 100000 бекоинов","reward_type":"coins","reward_value":100000,"track":"free"},
    {"level":20,"reward":"🎨 Легендарная рамка","reward_type":"frame","reward_value":1,"reward_item_id":"spin","track":"free"},
    {"level":25,"reward":"💰 250000 бекоинов","reward_type":"coins","reward_value":250000,"track":"free"},
    {"level":30,"reward":"💎 Premium 30 дней","reward_type":"premium","reward_value":30,"track":"free"},
    {"level":40,"reward":"💰 500000 бекоинов","reward_type":"coins","reward_value":500000,"track":"free"},
    {"level":50,"reward":"👑 Титул «ЛЕГЕНДА»","reward_type":"title","reward_value":1,"reward_item_id":"👑 ЛЕГЕНДА","track":"free"},
]

SCAM_DEFAULT_PERMS={
    "dm_send":False,"dm_reply":True,"gift_send":False,"gift_receive":True,
    "chat_send":True,"chat_create":False,"set_avatar":False,"set_banner":False,
    "open_cases":False,"buy_nft":False,"transfer_coins":False,"join_bp":False,
    "play_games":True,"call":False,"add_friends":False,"post_story":False,
}

def hash_password(p):
    s=secrets.token_hex(16)
    return f"{s}${hashlib.sha256((s+p).encode()).hexdigest()}"

def verify_password(p,st):
    try:
        s,h=st.split("$",1)
        return hashlib.sha256((s+p).encode()).hexdigest()==h
    except: return False

def make_token(uid,un):
    d=f"{uid}:{un}:{int(time.time())}"
    return f"{d}:{hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]}"

def parse_token(t):
    try:
        parts=t.split(":")
        if len(parts)!=4: return None
        uid,un,ts,sig=parts
        d=f"{uid}:{un}:{ts}"
        if sig!=hashlib.sha256((d+SECRET_KEY).encode()).hexdigest()[:32]: return None
        return int(uid),un
    except: return None

def sanitize_username(u):
    u=re.sub(r'[^a-zA-Z0-9_]','_',u.lower())
    if not u:u="user"
    if len(u)>24:u=u[:24]
    if u[0].isdigit():u="_"+u
    return u

async def get_unique_username(conn,base,exclude_id=None):
    base=sanitize_username(base)
    u=base;n=0
    while True:
        if exclude_id:
            row=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",u,exclude_id)
        else:
            row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",u)
        if not row: return u
        n+=1
        u=f"{base}_{n}"
        if len(u)>32:u=base[:28]+f"_{n}"

def get_today_holiday():
    today=datetime.datetime.now(datetime.timezone.utc)
    today_str=today.strftime("%m-%d")
    for h in HOLIDAYS:
        if h[0]==today_str:
            return {"active":True,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"exact":True}
    for offset in range(1,8):
        for direction in (1,-1):
            d=today+datetime.timedelta(days=offset*direction)
            ds=d.strftime("%m-%d")
            for h in HOLIDAYS:
                if h[0]==ds:
                    return {"active":False,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"exact":False,"in_days":offset*direction,"date":ds}
    return {"active":False}

app=FastAPI()
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

@app.middleware("http")
async def no_cache_api(request:Request,call_next):
    r=await call_next(request)
    if request.url.path.startswith("/api/"):
        r.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"
        r.headers["Pragma"]="no-cache"
    return r

app.mount("/uploads",StaticFiles(directory=UPLOAD_DIR),name="uploads")

pool=None
online_users=set()
spam_tracker={}
friend_spam_tracker={}
friend_target_spam={}
flood_tracker={}
last_cleanup=time.time()
active_events=[]
upgrade_chance_bonus={}
custom_commands={}
forced_holiday=None
teacher_quiz_enabled=True
candy_currency="halloween"
START_TIME=time.time()

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=5)
    return pool

async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%',
            banner_pos TEXT DEFAULT '50% 50%',
            email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,
            email_code VARCHAR(16),email_code_expires TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,is_moderator BOOLEAN DEFAULT FALSE,
            is_beta_tester BOOLEAN DEFAULT FALSE,is_scam BOOLEAN DEFAULT FALSE,
            is_dev BOOLEAN DEFAULT FALSE,is_streamer BOOLEAN DEFAULT FALSE,
            premium_tier VARCHAR(8),premium_expires TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,shadow_banned BOOLEAN DEFAULT FALSE,
            ban_reason VARCHAR(256),mute_until TIMESTAMP,
            nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),
            custom_status VARCHAR(128),
            online_status VARCHAR(16) DEFAULT 'online',
            bio VARCHAR(256),fav_music VARCHAR(128),
            gifts_hidden BOOLEAN DEFAULT FALSE,
            admin_password VARCHAR(128),
            coins INTEGER DEFAULT 0,social_rating INTEGER DEFAULT 0,
            messages_count INTEGER DEFAULT 0,
            frozen BOOLEAN DEFAULT FALSE,is_legend BOOLEAN DEFAULT FALSE,
            wallpaper TEXT,font_choice VARCHAR(32),compact_mode BOOLEAN DEFAULT FALSE,
            achievements TEXT DEFAULT '[]',quest_points INTEGER DEFAULT 0,
            daily_bonus_at TIMESTAMP,quest_day VARCHAR(16),
            quest_progress TEXT DEFAULT '{}',quest_claimed TEXT DEFAULT '[]',
            active_frame VARCHAR(32),frame_owned TEXT DEFAULT '[]',
            title VARCHAR(64),reputation INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,xp INTEGER DEFAULT 0,
            chest_streak INTEGER DEFAULT 0,chest_at TIMESTAMP,
            bank_deposit INTEGER DEFAULT 0,bank_at TIMESTAMP,
            candy INTEGER DEFAULT 0,candy_bought TEXT DEFAULT '[]',
            scam_perms TEXT DEFAULT '{}',
            last_seen TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        for col,typ in [
            ("candy","INTEGER DEFAULT 0"),("candy_bought","TEXT DEFAULT '[]'"),
            ("scam_perms","TEXT DEFAULT '{}'"),("title","VARCHAR(64)"),
            ("frame_owned","TEXT DEFAULT '[]'"),
            ("quest_day","VARCHAR(16)"),("quest_progress","TEXT DEFAULT '{}'"),
            ("quest_claimed","TEXT DEFAULT '[]'"),
        ]:
            try: await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        bot_exists=await conn.fetchval("SELECT 1 FROM users WHERE id=$1",SUPPORT_BOT_ID)
        if not bot_exists:
            try:
                await conn.execute("""INSERT INTO users(id,username,password_hash,is_admin,is_dev,bio,custom_status)
                    VALUES($1,$2,$3,FALSE,TRUE,$4,$5)""",SUPPORT_BOT_ID,SUPPORT_BOT_NAME,hash_password("bot_"+SECRET_KEY),"🤖 Служба поддержки","🛡️ Здесь можно подать заявку")
                await conn.execute("SELECT setval(pg_get_serial_sequence('users','id'),GREATEST((SELECT MAX(id) FROM users),1))")
            except Exception as e: print(f"Bot: {e}")

        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,banner TEXT,description TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',mode VARCHAR(16) DEFAULT 'public',paid_reaction_cost INTEGER DEFAULT 10,last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,reply_to INTEGER,thread_root INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,effect VARCHAR(16) DEFAULT 'none',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,gif_avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS ban_appeals(id SERIAL PRIMARY KEY,username VARCHAR(32),text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS reports(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,coins INTEGER NOT NULL,price INTEGER DEFAULT 0,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS support_tickets(
            id SERIAL PRIMARY KEY,
            from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            ticket_type VARCHAR(32),
            target_user INTEGER REFERENCES users(id) ON DELETE SET NULL,
            title VARCHAR(128),description TEXT,evidence TEXT,
            status VARCHAR(16) DEFAULT 'pending',admin_reply TEXT,
            resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW(),resolved_at TIMESTAMP
        )""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,gif_image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),item_image TEXT,chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_opens(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,prize_text TEXT,created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS abuse_grants(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,can_gift BOOLEAN DEFAULT TRUE,can_nft BOOLEAN DEFAULT TRUE,can_coins BOOLEAN DEFAULT TRUE,can_online BOOLEAN DEFAULT TRUE,can_timer BOOLEAN DEFAULT TRUE,can_write BOOLEAN DEFAULT TRUE,can_candy BOOLEAN DEFAULT TRUE,expires_at TIMESTAMP NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        try: await conn.execute("ALTER TABLE abuse_grants ADD COLUMN IF NOT EXISTS can_candy BOOLEAN DEFAULT TRUE")
        except: pass

        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS suspicious_logs(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,action VARCHAR(64),details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS spam_alerts(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text_sample TEXT,count INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS premium_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,bought_at TIMESTAMP DEFAULT NOW(),tier VARCHAR(8),days INTEGER,paid_coins INTEGER,method VARCHAR(16))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS quests_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,quest_key VARCHAR(32),reward_kp INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS upgrade_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,from_gift VARCHAR(32),to_gift VARCHAR(32),success BOOLEAN,chance REAL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS owner_messages(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),css TEXT,is_animated BOOLEAN DEFAULT FALSE,is_premium BOOLEAN DEFAULT FALSE,price_coins INTEGER DEFAULT 0,price_kp INTEGER DEFAULT 0,price_candy INTEGER DEFAULT 0)""")
        for f in [
            ("none","Без рамки","","none",False,False,0,0,0),
            ("gold","Золотая","👑","2px solid #ffd700;box-shadow:0 0 12px rgba(255,215,0,0.7)",False,False,500,0,0),
            ("fire","Огненная","🔥","2px solid #ff6b35;box-shadow:0 0 14px rgba(255,107,53,0.8)",False,False,800,0,0),
            ("ice","Ледяная","❄️","2px solid #22d3ee;box-shadow:0 0 14px rgba(34,211,238,0.8)",False,False,800,0,0),
            ("rainbow","Радужная","🌈","2px solid #d946ef;box-shadow:0 0 16px rgba(217,70,239,0.8)",False,True,0,3000,0),
            ("neon","Неоновая","💜","2px solid #ff00ff;box-shadow:0 0 18px rgba(255,0,255,0.9)",False,True,0,3000,0),
            ("pumpkin","Тыква","🎃","2px solid #ff6b1a;box-shadow:0 0 20px rgba(255,107,26,0.9)",False,False,0,2000,80),
            ("ghost","Призрак","👻","2px solid #a855f7;box-shadow:0 0 20px rgba(168,85,247,0.9)",False,False,0,2500,100),
            ("bat","Летучая мышь","🦇","2px solid #8b5cf6;box-shadow:0 0 20px rgba(139,92,246,0.9)",False,False,0,3000,120),
            ("teacher","Учитель года","🎓","3px solid #f59e0b;box-shadow:0 0 24px rgba(245,158,11,1)",False,False,0,0,300),
            ("spin","Вращение","🌀","2px solid #22c55e;animation:frameSpin 3s linear infinite",True,True,0,5000,0),
        ]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,css,is_animated,is_premium,price_coins,price_kp,price_candy) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (frame_id) DO NOTHING",*f)
            except: pass

        await conn.execute("""CREATE TABLE IF NOT EXISTS stories(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,image TEXT,text TEXT,bg_color VARCHAR(16) DEFAULT '#000',views TEXT DEFAULT '[]',reactions TEXT DEFAULT '{}',created_at TIMESTAMP DEFAULT NOW(),expires_at TIMESTAMP DEFAULT NOW()+INTERVAL '24 hours')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,message_id INTEGER,text TEXT,from_user INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS rep_given(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_quests(id SERIAL PRIMARY KEY,name VARCHAR(128),description TEXT,goal INTEGER,xp_reward INTEGER DEFAULT 100,action_type VARCHAR(32),target_count INTEGER DEFAULT 1,active BOOLEAN DEFAULT TRUE)""")
        for col,typ in [("action_type","VARCHAR(32)"),("target_count","INTEGER DEFAULT 1")]:
            try: await conn.execute(f"ALTER TABLE bp_quests ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_rewards(id SERIAL PRIMARY KEY,level INTEGER,reward TEXT,reward_type VARCHAR(32),reward_value INTEGER DEFAULT 0,reward_item_id VARCHAR(64),track VARCHAR(16) DEFAULT 'free',active BOOLEAN DEFAULT TRUE)""")
        for col,typ in [("reward_type","VARCHAR(32)"),("reward_value","INTEGER DEFAULT 0"),("reward_item_id","VARCHAR(64)"),("track","VARCHAR(16) DEFAULT 'free'")]:
            try: await conn.execute(f"ALTER TABLE bp_rewards ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_season(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🏆',started_at TIMESTAMP DEFAULT NOW(),ended_at TIMESTAMP,ends_at TIMESTAMP,days_total INTEGER DEFAULT 30,max_level INTEGER DEFAULT 50,xp_per_level INTEGER DEFAULT 1000,active BOOLEAN DEFAULT TRUE)""")
        for col,typ in [("ends_at","TIMESTAMP"),("days_total","INTEGER DEFAULT 30"),("max_level","INTEGER DEFAULT 50"),("xp_per_level","INTEGER DEFAULT 1000")]:
            try: await conn.execute(f"ALTER TABLE bp_season ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_progress(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_id INTEGER,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,claimed TEXT DEFAULT '[]',has_premium_pass BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        try: await conn.execute("ALTER TABLE bp_progress ADD COLUMN IF NOT EXISTS has_premium_pass BOOLEAN DEFAULT FALSE")
        except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_archive(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_name VARCHAR(64),season_emoji VARCHAR(8),level INTEGER,xp INTEGER,claimed_count INTEGER,ended_at TIMESTAMP DEFAULT NOW())""")

        # КВЕСТ-ЛИНИЯ (тумблер)
        await conn.execute("""CREATE TABLE IF NOT EXISTS quest_lines(
            id SERIAL PRIMARY KEY,line_key VARCHAR(32) UNIQUE,name VARCHAR(64),emoji VARCHAR(8),
            enabled BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS quest_line_steps(
            id SERIAL PRIMARY KEY,line_id INTEGER REFERENCES quest_lines(id) ON DELETE CASCADE,
            step_num INTEGER,name VARCHAR(128),description TEXT,
            action_type VARCHAR(32),target_count INTEGER DEFAULT 1,
            xp_reward INTEGER DEFAULT 100,candy_reward INTEGER DEFAULT 0,coins_reward INTEGER DEFAULT 0)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS quest_line_progress(
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            line_id INTEGER REFERENCES quest_lines(id) ON DELETE CASCADE,
            step INTEGER DEFAULT 1,completed TEXT DEFAULT '[]',updated_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY(user_id,line_id))""")
        # seed квест-линия "День учителя"
        ql_row=await conn.fetchrow("SELECT id FROM quest_lines WHERE line_key='teacher'")
        if not ql_row:
            ql=await conn.fetchrow("INSERT INTO quest_lines(line_key,name,emoji,enabled) VALUES('teacher','Квест-линия «День учителя»','🎓',TRUE) RETURNING id")
            steps=[
                (1,"Ответь на 1 вопрос викторины","Открой викторину и ответь правильно","play_game",1,100,5,100),
                (2,"Ответь на 3 вопроса","Продолжай!","play_game",3,300,15,300),
                (3,"Ответь на 5 вопросов","Ты в ударе!","play_game",5,500,25,500),
                (4,"Собери 10 яблок","Конфеты-яблоки","collect_candy",10,400,0,200),
                (5,"Напиши 10 сообщений","Общайся","send_message",10,200,10,200),
                (6,"Пройди викторину до конца","Финальный экзамен","play_game",10,1000,50,1000),
            ]
            for s in steps:
                await conn.execute("""INSERT INTO quest_line_steps(line_id,step_num,name,description,action_type,target_count,xp_reward,candy_reward,coins_reward)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",ql["id"],s[0],s[1],s[2],s[3],s[4],s[5],s[6],s[7])

        await conn.execute("""CREATE TABLE IF NOT EXISTS events(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🎉',event_type VARCHAR(16),multiplier INTEGER DEFAULT 1,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,started_at TIMESTAMP DEFAULT NOW(),end_at TIMESTAMP,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS commands(id SERIAL PRIMARY KEY,name VARCHAR(32) UNIQUE,description TEXT,response TEXT,created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS lottery(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,tickets INTEGER DEFAULT 0,updated_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS lottery_history(id SERIAL PRIMARY KEY,winner_id INTEGER,winner_name VARCHAR(32),amount INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS auction(id SERIAL PRIMARY KEY,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,item_type VARCHAR(16),item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),start_price INTEGER,current_price INTEGER,current_bidder INTEGER,started_at TIMESTAMP DEFAULT NOW(),ends_at TIMESTAMP,status VARCHAR(16) DEFAULT 'active')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS threads(id SERIAL PRIMARY KEY,root_msg INTEGER REFERENCES messages(id) ON DELETE CASCADE,author_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")

        await conn.execute("""CREATE TABLE IF NOT EXISTS candy_shop_items(
            id VARCHAR(64) PRIMARY KEY,emoji VARCHAR(8),name VARCHAR(128),price INTEGER NOT NULL,
            kind VARCHAR(16) NOT NULL,item VARCHAR(64),value INTEGER DEFAULT 0,count INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS candy_currency(
            key VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),is_active BOOLEAN DEFAULT FALSE)""")
        for k,v in DEFAULT_CANDY_CURRENCIES.items():
            try: await conn.execute("INSERT INTO candy_currency(key,name,emoji,is_active) VALUES($1,$2,$3,$4) ON CONFLICT (key) DO NOTHING",k,v["name"],v["emoji"],k=="halloween")
            except: pass

        await conn.execute("""CREATE TABLE IF NOT EXISTS teacher_quiz(
            id SERIAL PRIMARY KEY,question TEXT NOT NULL,answers TEXT NOT NULL,
            correct INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT NOW())""")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM teacher_quiz")
        if cnt==0:
            for q in DEFAULT_TEACHER_QUIZ:
                await conn.execute("INSERT INTO teacher_quiz(question,answers,correct) VALUES($1,$2,$3)",q["q"],json.dumps(q["a"],ensure_ascii=False),q["correct"])

        await conn.execute("""CREATE TABLE IF NOT EXISTS system_settings(
            key VARCHAR(64) PRIMARY KEY,value TEXT,updated_at TIMESTAMP DEFAULT NOW())""")
        defaults={"candy_currency":"halloween","teacher_quiz_enabled":"1","forced_holiday":"","bp_xp_per_level":"1000","quest_line_teacher":"1"}
        for k,v in defaults.items():
            try: await conn.execute("INSERT INTO system_settings(key,value) VALUES($1,$2) ON CONFLICT (key) DO NOTHING",k,v)
            except: pass

        shop_cnt=await conn.fetchval("SELECT COUNT(*) FROM candy_shop_items")
        if shop_cnt==0:
            for it in DEFAULT_CANDY_SHOP:
                await conn.execute("""INSERT INTO candy_shop_items(id,emoji,name,price,kind,item,value,count)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING""",it["id"],it["emoji"],it["name"],it["price"],it["kind"],it.get("item"),it.get("value",0),it.get("count",1))

        # АВТО-СТАРТ БП 50 заданий
        bp_row=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE LIMIT 1")
        if not bp_row:
            now=datetime.datetime.now(datetime.timezone.utc)
            ends=now+datetime.timedelta(days=30)
            await conn.execute("""INSERT INTO bp_season(name,description,emoji,days_total,max_level,ends_at,active,xp_per_level)
                VALUES('Сезон 2.8','50 заданий на весь сезон','🎃',30,50,$1,TRUE,1000)""",ends)
            for q in AUTO_BP_QUESTS[:50]:
                await conn.execute("""INSERT INTO bp_quests(name,description,goal,xp_reward,action_type,target_count)
                    VALUES($1,'',$2,$3,$4,$2)""",q["name"],q["target_count"],q["xp_reward"],q["action_type"])
            for r in AUTO_BP_REWARDS:
                await conn.execute("""INSERT INTO bp_rewards(level,reward,reward_type,reward_value,reward_item_id,track)
                    VALUES($1,$2,$3,$4,$5,$6)""",r["level"],r["reward"],r["reward_type"],r["reward_value"],r.get("reward_item_id"),r.get("track","free"))
            print(f"🎃 АВТО-СТАРТ БП: {len(AUTO_BP_QUESTS[:50])} заданий")

        # Титулы
        await conn.execute("""CREATE TABLE IF NOT EXISTS titles(
            id SERIAL PRIMARY KEY,name VARCHAR(32) NOT NULL,emoji VARCHAR(8) DEFAULT '👑',
            owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            visibility VARCHAR(16) DEFAULT 'private',price INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS title_owned(
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title_id INTEGER REFERENCES titles(id) ON DELETE CASCADE,
            acquired_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(user_id,title_id))""")

        # 2.8: биржа, крафт, аукцион 2.0, кредиты, транзакции, PvP
        await conn.execute("""CREATE TABLE IF NOT EXISTS gift_exchange(
            id SERIAL PRIMARY KEY,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            gift_id VARCHAR(32) NOT NULL,price INTEGER NOT NULL,status VARCHAR(16) DEFAULT 'active',
            buyer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW(),sold_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS craft_recipes(
            id SERIAL PRIMARY KEY,result_gift VARCHAR(32) NOT NULL,ingredients TEXT NOT NULL,
            is_active BOOLEAN DEFAULT TRUE)""")
        craft_cnt=await conn.fetchval("SELECT COUNT(*) FROM craft_recipes")
        if craft_cnt==0:
            for r in [
                {"result":"diamond","ingredients":json.dumps({"rose":10,"bear":5})},
                {"result":"crown","ingredients":json.dumps({"diamond":5})},
                {"result":"dragon","ingredients":json.dumps({"crown":3})},
                {"result":"legend","ingredients":json.dumps({"dragon":2})},
                {"result":"pumpkin","ingredients":json.dumps({"candy_gift":3})},
                {"result":"ghost","ingredients":json.dumps({"pumpkin":2})},
            ]:
                try: await conn.execute("INSERT INTO craft_recipes(result_gift,ingredients) VALUES($1,$2)",r["result"],r["ingredients"])
                except: pass
        await conn.execute("""CREATE TABLE IF NOT EXISTS auction2(
            id SERIAL PRIMARY KEY,seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            item_type VARCHAR(16),item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),
            start_price INTEGER,current_price INTEGER,current_bidder INTEGER,
            auto_extend BOOLEAN DEFAULT TRUE,started_at TIMESTAMP DEFAULT NOW(),ends_at TIMESTAMP,
            status VARCHAR(16) DEFAULT 'active')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS credits(
            id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,remaining INTEGER NOT NULL,rate REAL DEFAULT 0.05,
            taken_at TIMESTAMP DEFAULT NOW(),due_at TIMESTAMP,status VARCHAR(16) DEFAULT 'active',
            paid_at TIMESTAMP)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS transactions(
            id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,reason VARCHAR(128),balance_after INTEGER,
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS pvp_matches(
            id SERIAL PRIMARY KEY,player_a INTEGER REFERENCES users(id) ON DELETE CASCADE,
            player_b INTEGER REFERENCES users(id) ON DELETE CASCADE,
            bet INTEGER,winner INTEGER,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS tournaments(
            id SERIAL PRIMARY KEY,game VARCHAR(32) NOT NULL,entry_fee INTEGER DEFAULT 0,
            prize_pool INTEGER DEFAULT 0,status VARCHAR(16) DEFAULT 'open',
            started_at TIMESTAMP,ends_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS tournament_bets(
            id SERIAL PRIMARY KEY,tournament_id INTEGER REFERENCES tournaments(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,amount INTEGER,
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS mod_notes(
            id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            mod_id INTEGER REFERENCES users(id) ON DELETE SET NULL,note TEXT,
            created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS economy_tax(
            id SERIAL PRIMARY KEY,percent REAL DEFAULT 0,updated_at TIMESTAMP DEFAULT NOW())""")
        tax_cnt=await conn.fetchval("SELECT COUNT(*) FROM economy_tax")
        if tax_cnt==0:
            await conn.execute("INSERT INTO economy_tax(percent) VALUES(0)")

        print("✅ База 2.8 инициализирована")

async def get_current_user(token):
    parsed=parse_token(token)
    if not parsed: return None
    uid,un=parsed
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE id=$1",uid)
        return dict(row) if row else None

async def log_admin(aid,action,tid,details=""):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            await conn.execute("INSERT INTO admin_logs(admin_id,action,target_id,details) VALUES($1,$2,$3,$4)",aid,action,tid,details)
    except: pass

async def log_tx(uid,amount,reason=""):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            bal=await conn.fetchval("SELECT coins FROM users WHERE id=$1",uid)
            await conn.execute("INSERT INTO transactions(user_id,amount,reason,balance_after) VALUES($1,$2,$3,$4)",uid,amount,reason[:128],bal or 0)
    except: pass

async def grant_achievement(uid,key):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT achievements FROM users WHERE id=$1",uid)
            if not row: return False
            arr=json.loads(row["achievements"] or "[]")
            if key in arr: return False
            if key not in ACHIEVEMENTS: return False
            arr.append(key)
            await conn.execute("UPDATE users SET achievements=$1,coins=coins+50 WHERE id=$2",json.dumps(arr),uid)
            return True
    except: return False

def get_role(row):
    if not row: return "user"
    if row.get("username")==ADMIN_USERNAME: return "owner"
    if row.get("is_dev"): return "dev"
    if row.get("is_admin"): return "admin"
    if row.get("is_moderator"): return "moderator"
    if row.get("is_streamer"): return "streamer"
    if row.get("is_beta_tester"): return "beta"
    return "user"

def is_premium(row):
    if not row: return False
    if row.get("username")==ADMIN_USERNAME: return True
    tier=row.get("premium_tier")
    if not tier: return False
    exp=row.get("premium_expires")
    if exp and exp<datetime.datetime.now(datetime.timezone.utc): return False
    return tier in ("premium","pro")

def has_scam_perm(row,perm):
    if not row: return False
    if not row.get("is_scam"): return True
    try: perms=json.loads(row.get("scam_perms") or "{}")
    except: perms={}
    return perms.get(perm,SCAM_DEFAULT_PERMS.get(perm,False))

def user_public(row,viewer_id=None):
    status=row.get("online_status") or "online"
    uid=row["id"]
    is_online=uid in online_users and status!="invisible"
    if status=="invisible" and viewer_id!=uid: is_online=False
    try: scam_perms=json.loads(row.get("scam_perms") or "{}")
    except: scam_perms={}
    return {
        "id":row["id"],"username":row["username"],
        "avatar":row["avatar"],"banner":row["banner"],
        "gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
        "avatar_pos":row["avatar_pos"],"banner_pos":row["banner_pos"],
        "is_admin":row["is_admin"],"is_moderator":row["is_moderator"],
        "is_beta_tester":row.get("is_beta_tester",False),
        "is_scam":row.get("is_scam",False),"scam_perms":scam_perms,
        "is_dev":row.get("is_dev",False),"is_streamer":row.get("is_streamer",False),
        "premium_tier":row.get("premium_tier"),
        "premium_expires":row["premium_expires"].isoformat() if row.get("premium_expires") else None,
        "is_premium":is_premium(row),
        "nickname_color":row.get("nickname_color"),"nickname_gradient":row.get("nickname_gradient"),
        "custom_status":row.get("custom_status"),"online_status":status,
        "bio":row.get("bio"),"fav_music":row.get("fav_music"),
        "coins":row.get("coins",0),"social_rating":row.get("social_rating",0),
        "messages_count":row.get("messages_count",0),
        "is_legend":row.get("is_legend",False),
        "email":row.get("email"),"email_verified":row.get("email_verified",False),
        "has_admin_pass":bool(row.get("admin_password")),
        "wallpaper":row.get("wallpaper"),"font_choice":row.get("font_choice"),
        "compact_mode":row.get("compact_mode",False),
        "achievements":json.loads(row.get("achievements") or "[]"),
        "quest_points":row.get("quest_points",0),
        "active_frame":row.get("active_frame"),
        "frame_owned":json.loads(row.get("frame_owned") or "[]"),
        "title":row.get("title"),"reputation":row.get("reputation",0),
        "level":row.get("level",1),"xp":row.get("xp",0),
        "candy":row.get("candy",0),
        "created_at":row["created_at"].isoformat() if row.get("created_at") else None,
        "role":get_role(row),"online":is_online
    }

async def get_all_gifts():
    gifts=dict(DEFAULT_GIFTS)
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM custom_gifts WHERE is_sticker=FALSE OR is_sticker IS NULL")
            for r in rows: gifts[r["gift_id"]]={"name":r["name"],"emoji":r["emoji"],"image":r["image"],"gif_image":r.get("gif_image"),"price":r["price"]}
    except: pass
    return gifts

async def is_blocked(user_id,other_id):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT id FROM blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user_id,other_id)
            return bool(row)
    except: return False

async def has_abuse_access(user):
    if not user: return None
    if user["username"]==ADMIN_USERNAME: return {"owner":True,"can_gift":True,"can_nft":True,"can_coins":True,"can_candy":True,"can_online":True,"can_timer":True,"can_write":True}
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT * FROM abuse_grants WHERE user_id=$1 AND expires_at > NOW()",user["id"])
            if row: return dict(row)
    except: pass
    return None

async def check_spam(uid):
    now=time.time()
    arr=spam_tracker.get(uid,[])
    arr=[t for t in arr if now-t<60]
    arr.append(now)
    spam_tracker[uid]=arr
    if len(arr)>=30:
        spam_tracker[uid]=[]
        return True
    return False

async def check_flood(uid,text):
    if not text or len(text)<2: return
    h=hashlib.md5(text.strip().lower().encode()).hexdigest()
    now=time.time()
    arr=flood_tracker.get(uid,[])
    arr=[t for t in arr if now-t[1]<300 and t[0]==h]
    arr.append((h,now))
    flood_tracker[uid]=arr
    if len(arr)>=8:
        flood_tracker[uid]=[]
        try:
            p=await get_pool()
            async with p.acquire() as conn:
                await conn.execute("INSERT INTO spam_alerts(user_id,text_sample,count) VALUES($1,$2,$3)",uid,text[:200],len(arr))
        except: pass

async def check_friend_spam(uid,target_id=None):
    now=time.time()
    arr=friend_spam_tracker.get(uid,[])
    arr=[t for t in arr if now-t<600]
    arr.append(now)
    friend_spam_tracker[uid]=arr
    if len(arr)>=10:
        friend_spam_tracker[uid]=[]
        return True
    if target_id:
        key=(uid,target_id)
        tarr=friend_target_spam.get(key,[])
        tarr=[t for t in tarr if now-t<600]
        tarr.append(now)
        friend_target_spam[key]=tarr
        if len(tarr)>=3:
            friend_target_spam[key]=[]
            return True
    return False

def cleanup_trackers():
    global last_cleanup
    now=time.time()
    if now-last_cleanup<300: return
    last_cleanup=now
    for d in (spam_tracker,friend_spam_tracker):
        for k in list(d.keys()):
            arr=[t for t in d[k] if now-t<600]
            if not arr: del d[k]
            else: d[k]=arr
    for k in list(flood_tracker.keys()):
        arr=[t for t in flood_tracker[k] if now-t[1]<300]
        if not arr: del flood_tracker[k]
        else: flood_tracker[k]=arr

async def add_last_message_at(conn,channel_id=None,group_id=None):
    now=datetime.datetime.now(datetime.timezone.utc)
    if channel_id: await conn.execute("UPDATE channels SET last_message_at=$1 WHERE id=$2",now,channel_id)
    if group_id: await conn.execute("UPDATE groups SET last_message_at=$1 WHERE id=$2",now,group_id)

QUEST_TEMPLATES=[
    {"key":"send_10_msgs","name":"Болтун дня","desc":"Отправь 10 сообщений","goal":10,"reward_kp":50,"emoji":"💬"},
    {"key":"play_3_games","name":"Игрок дня","desc":"Сыграй 3 игры","goal":3,"reward_kp":80,"emoji":"🎮"},
    {"key":"send_5_dms","name":"Личка дня","desc":"Отправь 5 DM","goal":5,"reward_kp":60,"emoji":"✉️"},
    {"key":"open_1_case","name":"Лудоман дня","desc":"Открой 1 кейс","goal":1,"reward_kp":100,"emoji":"🎁"},
    {"key":"give_gift","name":"Щедрый дня","desc":"Подари подарок","goal":1,"reward_kp":120,"emoji":"🎀"},
    {"key":"win_duel","name":"Дуэлянт дня","desc":"Победи в дуэли","goal":1,"reward_kp":150,"emoji":"⚔️"},
    {"key":"buy_nft","name":"Коллекционер дня","desc":"Купи NFT","goal":1,"reward_kp":200,"emoji":"🎨"},
]

def get_today_key():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

async def grant_quest_progress(uid,quest_key,amount=1):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT quest_day,quest_progress,quest_claimed FROM users WHERE id=$1",uid)
            if not row: return
            today=get_today_key()
            prog=json.loads(row["quest_progress"] or "{}")
            claimed=json.loads(row["quest_claimed"] or "[]")
            if row["quest_day"]!=today: prog={};claimed=[];day=today
            else: day=row["quest_day"]
            prog[quest_key]=prog.get(quest_key,0)+amount
            tpl=next((q for q in QUEST_TEMPLATES if q["key"]==quest_key),None)
            reward=0
            if tpl and prog[quest_key]>=tpl["goal"] and quest_key not in claimed:
                reward=tpl["reward_kp"]
                claimed.append(quest_key)
                await conn.execute("UPDATE users SET quest_points=quest_points+$1 WHERE id=$2",reward,uid)
                await conn.execute("INSERT INTO quests_log(user_id,quest_key,reward_kp) VALUES($1,$2,$3)",uid,quest_key,reward)
            await conn.execute("UPDATE users SET quest_day=$1,quest_progress=$2,quest_claimed=$3 WHERE id=$4",day,json.dumps(prog),json.dumps(claimed),uid)
            return reward
    except Exception as e: print(f"quest progress: {e}")

async def check_daily_bonus(uid):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT daily_bonus_at FROM users WHERE id=$1",uid)
            if not row: return {"ok":False,"reason":"no_user"}
            now=datetime.datetime.now(datetime.timezone.utc)
            last=row["daily_bonus_at"]
            if last and (now-last).total_seconds()<86400:
                return {"ok":False,"reason":"already","next_in":int(86400-(now-last).total_seconds())}
            bonus=1;prem=False
            user=await conn.fetchrow("SELECT premium_tier,premium_expires FROM users WHERE id=$1",uid)
            if user and user["premium_tier"] and (not user["premium_expires"] or user["premium_expires"]>now): prem=True;bonus=3
            await conn.execute("UPDATE users SET coins=coins+$1,daily_bonus_at=$2 WHERE id=$3",bonus,now,uid)
            await log_tx(uid,bonus,"daily bonus")
            return {"ok":True,"amount":bonus,"premium":prem}
    except Exception as e: return {"ok":False,"reason":str(e)}

def apply_event_multiplier(base,event_type):
    mult=base
    now=datetime.datetime.now(datetime.timezone.utc)
    for e in active_events:
        if e.get("active") and e.get("event_type")==event_type:
            if e.get("end_at") and e["end_at"]>now: mult=base*e.get("multiplier",1)
    return mult

async def grant_xp(uid,amount):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT xp,level FROM users WHERE id=$1",uid)
            if not row: return
            amount=apply_event_multiplier(amount,"xp_x")
            new_xp=row["xp"]+amount
            new_level=row["level"]
            while new_xp>=(new_level*100):
                new_xp-=new_level*100
                new_level+=1
            await conn.execute("UPDATE users SET xp=$1,level=$2 WHERE id=$3",new_xp,new_level,uid)
    except: pass

async def grant_candy(uid,amount=1,silent=False):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",amount,uid)
            total=await conn.fetchval("SELECT candy FROM users WHERE id=$1",uid)
        if total>=10: await grant_achievement(uid,"halloween_10")
        if total>=100: await grant_achievement(uid,"halloween_100")
        if total>=500: await grant_achievement(uid,"halloween_500")
        await bp_add_progress(uid,"collect_candy",amount)
        return total
    except: return 0

async def bp_add_progress(uid,action_type,amount=1):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            season=await conn.fetchrow("SELECT id,xp_per_level,max_level FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
            if not season: return
            quests=await conn.fetch("SELECT id,xp_reward,target_count FROM bp_quests WHERE active=TRUE AND action_type=$1",action_type)
            if not quests: return
            total_xp=sum(q["xp_reward"] for q in quests)
            if total_xp==0: return
            prog=await conn.fetchrow("SELECT id,xp,level FROM bp_progress WHERE user_id=$1 AND season_id=$2",uid,season["id"])
            if not prog:
                await conn.execute("INSERT INTO bp_progress(user_id,season_id,xp,level) VALUES($1,$2,0,1)",uid,season["id"])
                prog=await conn.fetchrow("SELECT id,xp,level FROM bp_progress WHERE user_id=$1 AND season_id=$2",uid,season["id"])
            new_xp=prog["xp"]+total_xp
            new_level=prog["level"]
            xp_per=season["xp_per_level"] or 1000
            max_lv=season["max_level"] or 50
            while new_xp>=xp_per and new_level<max_lv:
                new_xp-=xp_per
                new_level+=1
            await conn.execute("UPDATE bp_progress SET xp=$1,level=$2 WHERE id=$3",new_xp,new_level,prog["id"])
    except Exception as e: print(f"bp: {e}")

async def bg_lottery():
    while True:
        try:
            await asyncio.sleep(3600)
            p=await get_pool()
            async with p.acquire() as conn:
                rows=await conn.fetch("SELECT user_id,tickets FROM lottery WHERE tickets>0")
                if not rows: continue
                pool_tickets=[]
                for r in rows: pool_tickets.extend([r["user_id"]]*r["tickets"])
                if not pool_tickets: continue
                winner=random.choice(pool_tickets)
                total=sum(r["tickets"] for r in rows)*100
                jackpot=int(total*0.7)
                w=await conn.fetchrow("SELECT username FROM users WHERE id=$1",winner)
                if w:
                    await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",jackpot,winner)
                    await conn.execute("INSERT INTO lottery_history(winner_id,winner_name,amount) VALUES($1,$2,$3)",winner,w["username"],jackpot)
                    await conn.execute("DELETE FROM lottery")
        except: await asyncio.sleep(60)

async def bg_events_cleanup():
    while True:
        try:
            await asyncio.sleep(30)
            p=await get_pool()
            async with p.acquire() as conn:
                ended=await conn.fetch("SELECT id FROM bp_season WHERE active=TRUE AND ends_at IS NOT NULL AND ends_at<=NOW()")
                for r in ended:
                    await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE id=$1",r["id"])
        except: await asyncio.sleep(60)

async def bg_auction_cleanup():
    while True:
        try:
            await asyncio.sleep(30)
            p=await get_pool()
            async with p.acquire() as conn:
                rows=await conn.fetch("SELECT * FROM auction2 WHERE status='active' AND ends_at<=NOW()")
                for r in rows:
                    if r["current_bidder"]:
                        await conn.execute("UPDATE auction2 SET status='sold' WHERE id=$1",r["id"])
                    else:
                        await conn.execute("UPDATE auction2 SET status='ended' WHERE id=$1",r["id"])
                overdue=await conn.fetch("SELECT * FROM credits WHERE status='active' AND due_at<=NOW()")
                for c in overdue:
                    bal=await conn.fetchval("SELECT coins FROM users WHERE id=$1",c["user_id"])
                    if bal and bal>=c["remaining"]:
                        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",c["remaining"],c["user_id"])
                        await conn.execute("UPDATE credits SET status='paid',paid_at=NOW(),remaining=0 WHERE id=$1",c["id"])
                    else:
                        await conn.execute("UPDATE credits SET status='overdue' WHERE id=$1",c["id"])
        except: await asyncio.sleep(60)

async def startup_tasks():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT * FROM events WHERE active=TRUE AND end_at>NOW()")
            for r in rows:
                active_events.append({"id":r["id"],"name":r["name"],"event_type":r["event_type"],"multiplier":r["multiplier"],"end_at":r["end_at"],"active":True})
    except Exception as e:
        print(f"Startup: {e}")
    asyncio.create_task(bg_lottery())
    asyncio.create_task(bg_events_cleanup())
    asyncio.create_task(bg_auction_cleanup())
    print("🎃 Background loops started (2.8)")

@app.on_event("startup")
async def on_startup():
    if DATABASE_URL:
        try:
            await init_db()
            await startup_tasks()
        except Exception as e:
            print(f"DB init: {e}")

# ============ CHANGELOG / ACHIEVEMENTS / AUTH ============
@app.get("/api/changelog")
async def changelog():
    return {"current":CURRENT_VERSION,"all":{
        "2.8":{"title":"Belugacord 2.8","items":[
            "👑 Конструктор титулов (приватные/публичные)",
            "⚔️ PvP-арена",
            "📈 Биржа подарков",
            "⚒️ Крафт редких предметов",
            "🔨 Аукцион 2.0 с автопродлением",
            "💳 Кредиты",
            "📊 История транзакций",
            "💰 Налоги на переводы",
            "🎓 Квест-линия «День учителя» с тумблером",
            "🏆 БП авто-старт: 50 заданий",
            "🎯 Рекомендации друзей",
            "📊 Системный мониторинг",
            "💾 Бэкап аккаунта",
            "🛡️ Заметки модераторов",
        ]},
        "2.7":{"title":"Belugacord Beta 2.7","items":[
            "🎨 Полный редизайн","📱 Мобильные вкладки","🔍 @юзернеймы",
            "🤖 @support_bot","🚨 SCAM-система","🍬 Конфетный магазин",
            "🎁 60+ подарков","🎉 25+ праздников","🏆 BP Free+Premium",
        ]},
    }}

@app.get("/api/achievements/all")
async def achievements_all(): return ACHIEVEMENTS

@app.get("/api/check_username")
async def check_username(username:str):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",username)
    return {"available":row is None}

@app.post("/api/register")
async def register(data:dict):
    raw=(data.get("username") or "").strip()
    pw=data.get("password") or ""
    em=(data.get("email") or "").strip() or None
    if len(raw)<2 or len(raw)>32: raise HTTPException(400,"Ник 2-32")
    if len(pw)<4: raise HTTPException(400,"Пароль мин 4")
    p=await get_pool()
    async with p.acquire() as conn:
        uname=await get_unique_username(conn,raw)
        row=await conn.fetchrow("INSERT INTO users(username,password_hash,email,is_admin) VALUES($1,$2,$3,$4) RETURNING *",uname,hash_password(pw),em,uname==ADMIN_USERNAME)
    return {"token":make_token(row["id"],row["username"]),"user":user_public(row,row["id"])}

@app.post("/api/login")
async def login(data:dict):
    u=(data.get("username") or "").strip().lstrip("@")
    pw=data.get("password") or ""
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE username=$1",u)
    if not row or not verify_password(pw,row["password_hash"]): raise HTTPException(400,"Неверный ник/пароль")
    if row["is_banned"]: raise HTTPException(403,row.get("ban_reason") or "Забанен")
    return {"token":make_token(row["id"],row["username"]),"user":user_public(row,row["id"])}

@app.get("/api/me")
async def me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return user_public(user,user["id"])

# ============ PROFILE ============
@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    premium=is_premium(user)
    gif_av=data.get("gif_avatar");gif_bn=data.get("gif_banner")
    if (gif_av or gif_bn) and not premium: raise HTTPException(403,"GIF только для премиума")
    if user.get("is_scam"):
        if data.get("avatar") and not has_scam_perm(user,"set_avatar"): raise HTTPException(403,"SCAM: ава запрещена")
        if data.get("banner") and not has_scam_perm(user,"set_banner"): raise HTTPException(403,"SCAM: баннер запрещён")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET
            avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),
            gif_avatar=COALESCE($3,gif_avatar),gif_banner=COALESCE($4,gif_banner),
            avatar_pos=COALESCE($5,avatar_pos),banner_pos=COALESCE($6,banner_pos),
            nickname_color=$7,nickname_gradient=$8,
            bio=COALESCE($9,bio),fav_music=COALESCE($10,fav_music),
            custom_status=COALESCE($14,custom_status)
            WHERE id=$15""",
            data.get("avatar"),data.get("banner"),gif_av,gif_bn,
            data.get("avatar_pos"),data.get("banner_pos"),
            data.get("nickname_color"),data.get("nickname_gradient"),
            data.get("bio"),data.get("fav_music"),
            data.get("wallpaper"),data.get("font_choice"),data.get("compact_mode"),
            data.get("custom_status"),user["id"])
    return {"ok":True}

@app.post("/api/upload_avatar")
async def upload_avatar(token:str=Form(...),kind:str=Form("avatar"),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if kind not in ("avatar","banner","gif_avatar","gif_banner"): raise HTTPException(400,"kind")
    if user.get("is_scam"):
        if kind=="avatar" and not has_scam_perm(user,"set_avatar"): raise HTTPException(403,"SCAM: ава запрещена")
        if kind=="banner" and not has_scam_perm(user,"set_banner"): raise HTTPException(403,"SCAM: баннер запрещён")
    mime=(file.content_type or "").lower()
    if mime not in ALLOWED_MIME: raise HTTPException(400,f"Тип запрещён: {mime}")
    ext=os.path.splitext(file.filename or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT: raise HTTPException(400,f"Расш. запрещено")
    content=await file.read()
    lim=LIMITS.get(user.get("premium_tier"),LIMITS[None])["file"]
    if len(content)>lim: raise HTTPException(400,"Файл большой")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    url=f"/uploads/{name}"
    p=await get_pool()
    async with p.acquire() as conn:
        if kind=="avatar": await conn.execute("UPDATE users SET avatar=$1 WHERE id=$2",url,user["id"])
        elif kind=="banner": await conn.execute("UPDATE users SET banner=$1 WHERE id=$2",url,user["id"])
        elif kind=="gif_avatar":
            if not is_premium(user): raise HTTPException(403,"GIF только Premium")
            await conn.execute("UPDATE users SET gif_avatar=$1 WHERE id=$2",url,user["id"])
        elif kind=="gif_banner":
            if not is_premium(user): raise HTTPException(403,"GIF только Premium")
            await conn.execute("UPDATE users SET gif_banner=$1 WHERE id=$2",url,user["id"])
    return {"ok":True,"url":url,"kind":kind}

@app.post("/api/user/status")
async def set_status(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    st=data.get("online_status","online")
    if st not in ("online","dnd","invisible"): raise HTTPException(400,"online/dnd/invisible")
    custom=(data.get("custom_status") or "")[:64]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET online_status=$1,custom_status=$2 WHERE id=$3",st,custom or None,user["id"])
    return {"ok":True}

@app.post("/api/user/change_username")
async def change_username(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    new=(data.get("username") or "").strip().lower()
    if not re.match(r'^[a-z0-9_]{2,24}$',new): raise HTTPException(400,"Только a-z, 0-9, _ (2-24)")
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM users WHERE username=$1 AND id!=$2",new,user["id"])
        if exists: raise HTTPException(400,"Занято")
        await conn.execute("UPDATE users SET username=$1 WHERE id=$2",new,user["id"])
    token_new=make_token(user["id"],new)
    return {"ok":True,"token":token_new,"username":new}

@app.get("/api/user/{user_id}")
async def get_user(user_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM users WHERE id=$1",user_id)
    if not row: raise HTTPException(404,"Не найден")
    return user_public(row,user_id)

@app.get("/api/users/search")
async def users_search(q:str,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip().lstrip("@")
    if len(q)<1: return []
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM users WHERE username ILIKE $1 AND id!=$2 AND id!=0 ORDER BY username LIMIT 25",f"%{q}%",user["id"])
    return [user_public(r,user["id"]) for r in rows]

# ============ FRIENDS ============
@app.get("/api/friends/list")
async def friends_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    uid=user["id"]
    p=await get_pool()
    async with p.acquire() as conn:
        frows=await conn.fetch("SELECT id,user_a,user_b FROM friendships WHERE user_a=$1 OR user_b=$1",uid)
        inc=await conn.fetch("SELECT r.id,r.from_user FROM friend_requests r WHERE r.to_user=$1 ORDER BY r.created_at DESC",uid)
        out=await conn.fetch("SELECT r.id,r.to_user FROM friend_requests r WHERE r.from_user=$1 ORDER BY r.created_at DESC",uid)
        result=[]
        for r in frows:
            oid=r["user_b"] if r["user_a"]==uid else r["user_a"]
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",oid)
            if not o: continue
            item=user_public(o,uid)
            item["status"]="accepted"
            item["friend_row_id"]=r["id"]
            result.append(item)
        for r in inc:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["from_user"])
            if not o: continue
            item=user_public(o,uid)
            item["status"]="incoming"
            item["request_id"]=r["id"]
            result.append(item)
        for r in out:
            o=await conn.fetchrow("SELECT * FROM users WHERE id=$1",r["to_user"])
            if not o: continue
            item=user_public(o,uid)
            item["status"]="outgoing"
            item["request_id"]=r["id"]
            result.append(item)
    return result

@app.post("/api/friends/request")
async def friends_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"add_friends"): raise HTTPException(403,"SCAM: заявки запрещены")
    tn=(data.get("username") or "").strip().lstrip("@")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",tn)
        if not t: raise HTTPException(404,"Не найден")
        if await check_friend_spam(user["id"],t["id"]): raise HTTPException(429,"Слишком много заявок")
        if t["id"]==user["id"]: raise HTTPException(400,"Себя нельзя")
        if t["id"]==SUPPORT_BOT_ID: raise HTTPException(400,"Бота нельзя")
        if await is_blocked(user["id"],t["id"]): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],t["id"]): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],t["id"]): raise HTTPException(400,"Заявка есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],t["id"])
    return {"ok":True}

@app.post("/api/friends/request_by_id")
async def friends_request_by_id(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"add_friends"): raise HTTPException(403,"SCAM: заявки запрещены")
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    if tid==SUPPORT_BOT_ID: raise HTTPException(400,"Бота нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        if await check_friend_spam(user["id"],tid): raise HTTPException(429,"Слишком много заявок")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid): raise HTTPException(400,"Заявка есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],tid)
    return {"ok":True}

@app.post("/api/friends/accept")
async def friends_accept(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT id,from_user,to_user FROM friend_requests WHERE id=$1",rid)
        if not r: raise HTTPException(404,"Заявка обработана")
        if r["to_user"]!=user["id"]: raise HTTPException(403,"Не твоя")
        a,b=sorted([r["from_user"],r["to_user"]])
        try: await conn.execute("INSERT INTO friendships(user_a,user_b) VALUES($1,$2)",a,b)
        except: pass
        await conn.execute("DELETE FROM friend_requests WHERE id=$1",rid)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM friendships WHERE user_a=$1 OR user_b=$1",user["id"])
        if cnt==1: await grant_achievement(user["id"],"first_friend")
        if cnt>=10: await grant_achievement(user["id"],"friend_10")
    return {"ok":True}

@app.post("/api/friends/decline")
async def friends_decline(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT from_user,to_user FROM friend_requests WHERE id=$1",rid)
        if not r: return {"ok":True}
        if r["to_user"]!=user["id"]: raise HTTPException(403,"Не твоя")
        await conn.execute("DELETE FROM friend_requests WHERE id=$1",rid)
    return {"ok":True}

@app.post("/api/friends/remove")
async def friends_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
    return {"ok":True}

@app.get("/api/friends/count")
async def friends_count(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        n=await conn.fetchval("SELECT COUNT(*) FROM friend_requests WHERE to_user=$1",user["id"])
    return {"count":n or 0}

# ============ GROUPS ============
@app.get("/api/groups/list")
async def groups_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.* FROM groups g JOIN group_members gm ON gm.group_id=g.id WHERE gm.user_id=$1 ORDER BY COALESCE(g.last_message_at,g.created_at) DESC",user["id"])
    return [{"id":r["id"],"name":r["name"],"avatar":r["avatar"],"description":r["description"],"owner_id":r["owner_id"]} for r in rows]

@app.post("/api/groups/create")
async def groups_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"chat_create"): raise HTTPException(403,"SCAM: нельзя создавать")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("INSERT INTO groups(name,owner_id) VALUES($1,$2) RETURNING id,name",name,user["id"])
        await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)",g["id"],user["id"])
    return {"id":g["id"],"name":g["name"]}

@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT gm.id,gm.text,gm.file_url,gm.created_at,gm.user_id,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,
            u.is_admin,u.is_moderator,u.is_scam,u.premium_tier,u.premium_expires
            FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200""",group_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["role"]=get_role(r);d["is_premium"]=is_premium(r);out.append(d)
    return out

@app.get("/api/groups/{group_id}/members")
async def group_members_get(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT u.id,u.username,u.avatar,u.gif_avatar,u.title,u.active_frame,
            u.is_admin,u.is_moderator,u.is_scam,u.premium_tier,u.premium_expires
            FROM users u JOIN group_members gm ON gm.user_id=u.id WHERE gm.group_id=$1""",group_id)
    out=[]
    for r in rows:
        d=dict(r);d["role"]=get_role(r);d["is_premium"]=is_premium(r);out.append(d)
    return out

# ============ SERVERS ============
@app.get("/api/servers/list")
async def servers_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT s.id,s.name,s.avatar FROM servers s JOIN server_members sm ON sm.server_id=s.id WHERE sm.user_id=$1 ORDER BY s.id",user["id"])
    return [dict(r) for r in rows]

@app.post("/api/servers/create")
async def servers_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"chat_create"): raise HTTPException(403,"SCAM: нельзя создавать")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        code=secrets.token_urlsafe(8)[:12]
        s=await conn.fetchrow("INSERT INTO servers(name,owner_id,invite_code) VALUES($1,$2,$3) RETURNING id,name",name,user["id"],code)
        await conn.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)",s["id"],user["id"])
        await conn.execute("INSERT INTO channels(server_id,name) VALUES($1,'общий')",s["id"])
        await grant_achievement(user["id"],"first_server")
    return {"id":s["id"],"name":s["name"]}

@app.get("/api/servers/{server_id}/channels")
async def server_channels(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,mode FROM channels WHERE server_id=$1 ORDER BY id",server_id)
    return [{"id":r["id"],"name":r["name"],"mode":r.get("mode") or "public"} for r in rows]

@app.get("/api/servers/{server_id}/members")
async def server_members(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT u.id,u.username,u.avatar,u.gif_avatar,u.title,u.active_frame,u.is_admin,u.is_moderator,u.is_scam,u.premium_tier,u.premium_expires
            FROM users u JOIN server_members sm ON sm.user_id=u.id WHERE sm.server_id=$1""",server_id)
    out=[]
    for r in rows:
        d=dict(r);d["role"]=get_role(r);d["is_premium"]=is_premium(r);out.append(d)
    return out

@app.post("/api/servers/leave")
async def server_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM server_members WHERE server_id=$1 AND user_id=$2",int(data.get("server_id",0)),user["id"])
    return {"ok":True}

@app.post("/api/servers/update")
async def server_update(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT owner_id FROM servers WHERE id=$1",int(data.get("server_id",0)))
        if not s or s["owner_id"]!=user["id"]: raise HTTPException(403,"Только владелец")
        await conn.execute("UPDATE servers SET name=COALESCE($1,name) WHERE id=$2",data.get("name"),int(data.get("server_id",0)))
    return {"ok":True}

@app.get("/api/channels/{channel_id}/messages")
async def channel_messages(channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT m.id,m.text,m.file_url,m.reactions,m.edited,m.reply_to,m.pinned,m.effect,m.created_at,m.user_id,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,
            u.is_admin,u.is_moderator,u.is_scam,u.premium_tier,u.premium_expires
            FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200""",channel_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["role"]=get_role(r);d["is_premium"]=is_premium(r)
        d["reactions"]=json.loads(d.get("reactions") or "{}");out.append(d)
    return {"messages":out,"pinned":[],"mode":"public"}

@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if await is_blocked(user["id"],user_id): raise HTTPException(403,"Заблокировано")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.created_at,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.premium_tier,u.premium_expires,u.is_scam
            FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC LIMIT 200""",user["id"],user_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None;d["is_premium"]=is_premium(r);out.append(d)
    return out

@app.post("/api/messages/delete")
async def message_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        if user.get("is_admin") or user["username"]==ADMIN_USERNAME:
            row=await conn.fetchrow("DELETE FROM messages WHERE id=$1 RETURNING id",mid)
        else:
            row=await conn.fetchrow("DELETE FROM messages WHERE id=$1 AND user_id=$2 RETURNING id",mid,user["id"])
    if not row: return {"ok":False}
    return {"ok":True}

@app.post("/api/messages/pin")
async def message_pin(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT pinned FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        new=not row["pinned"]
        await conn.execute("UPDATE messages SET pinned=$1 WHERE id=$2",new,mid)
    return {"ok":True,"pinned":new}

@app.post("/api/messages/reaction")
async def message_reaction(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0));emoji=data.get("emoji","👍")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT reactions FROM messages WHERE id=$1",mid)
        if not row: raise HTTPException(404,"Нет")
        react=json.loads(row["reactions"] or "{}")
        arr=react.get(emoji,[])
        if user["id"] in arr: arr.remove(user["id"])
        else: arr.append(user["id"])
        react[emoji]=arr
        await conn.execute("UPDATE messages SET reactions=$1 WHERE id=$2",json.dumps(react),mid)
    await grant_quest_progress(user["id"],"react",1)
    await bp_add_progress(user["id"],"react",1)
    return {"ok":True}

@app.get("/api/messages/saved")
async def messages_saved(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT sm.id,sm.text,sm.created_at,u.username FROM saved_messages sm LEFT JOIN users u ON u.id=sm.from_user WHERE sm.user_id=$1 ORDER BY sm.id DESC",user["id"])
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.get("/api/messages/search")
async def messages_search(q:str,channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    q=(q or "").strip()
    if len(q)<2: return []
    p=await get_pool()
    async with p.acquire() as conn:
        if channel_id:
            rows=await conn.fetch("SELECT m.id,m.text,m.created_at,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.text ILIKE $2 ORDER BY m.id DESC LIMIT 50",channel_id,f"%{q}%")
        else:
            rows=await conn.fetch("SELECT m.id,m.text,m.created_at,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.text ILIKE $1 ORDER BY m.id DESC LIMIT 50",f"%{q}%")
    return [{"id":r["id"],"text":r["text"],"username":r["username"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/upload")
async def upload(token:str=Form(...),file:UploadFile=File(...)):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    lim=LIMITS.get(user.get("premium_tier"),LIMITS[None])["file"]
    mime=(file.content_type or "application/octet-stream").lower()
    if mime not in ALLOWED_MIME: raise HTTPException(400,f"Тип запрещён: {mime}")
    ext=os.path.splitext(file.filename or "")[1].lower()[:8]
    if ext and ext not in ALLOWED_EXT: raise HTTPException(400,f"Расш. запрещено: {ext}")
    content=await file.read()
    if len(content)>lim: raise HTTPException(400,"Файл большой")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}"}

# ============ STORIES ============
@app.get("/api/stories/list")
async def stories_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT s.id,s.image,s.text,s.bg_color,s.created_at,s.user_id,u.username,u.avatar FROM stories s JOIN users u ON u.id=s.user_id WHERE s.expires_at>NOW() ORDER BY s.created_at DESC LIMIT 100")
    return [{"id":r["id"],"image":r["image"],"text":r["text"],"bg_color":r["bg_color"],"username":r["username"],"avatar":r["avatar"],"user_id":r["user_id"]} for r in rows]

@app.post("/api/stories/create")
async def stories_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"post_story"): raise HTTPException(403,"SCAM: сторис запрещены")
    image=(data.get("image") or "").strip() or None
    text=(data.get("text") or "").strip() or None
    if not image and not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO stories(user_id,image,text,bg_color) VALUES($1,$2,$3,$4)",user["id"],image,text,data.get("bg_color","#000"))
    await bp_add_progress(user["id"],"post_story",1)
    return {"ok":True}

# ============ SUPPORT ============
@app.post("/api/support/ticket")
async def support_ticket(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ticket_type=(data.get("ticket_type") or "").strip()
    if ticket_type not in ("unscam","unban","report_scam","report_spam","other"): raise HTTPException(400,"Неверный тип")
    title=(data.get("title") or "")[:128]
    description=(data.get("description") or "")[:2000]
    evidence=(data.get("evidence") or "")[:1000]
    target=int(data.get("target_user_id") or data.get("target_user") or 0)
    if not description: raise HTTPException(400,"Опиши ситуацию")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("""INSERT INTO support_tickets(from_user,ticket_type,target_user,title,description,evidence)
            VALUES($1,$2,$3,$4,$5,$6) RETURNING id""",user["id"],ticket_type,target or None,title,description,evidence)
    return {"ok":True,"ticket_id":row["id"]}

@app.get("/api/support/my_tickets")
async def my_tickets(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM support_tickets WHERE from_user=$1 ORDER BY id DESC LIMIT 50",user["id"])
    return [{"id":r["id"],"ticket_type":r["ticket_type"],"title":r["title"],"description":r["description"],"status":r["status"],"admin_reply":r["admin_reply"]} for r in rows]

@app.get("/api/support/all")
async def support_all(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT st.*,u.username AS from_username,t.username AS target_username
            FROM support_tickets st LEFT JOIN users u ON u.id=st.from_user LEFT JOIN users t ON t.id=st.target_user
            ORDER BY st.status='pending' DESC, st.id DESC LIMIT 200""")
    return [{"id":r["id"],"from_user":r["from_user"],"from_username":r["from_username"],"target_user":r["target_user"],"target_username":r["target_username"],"ticket_type":r["ticket_type"],"title":r["title"],"description":r["description"],"status":r["status"],"admin_reply":r["admin_reply"]} for r in rows]

@app.post("/api/support/resolve")
async def support_resolve(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    tid=int(data.get("ticket_id",0))
    action=(data.get("action") or "").strip()
    reply=(data.get("reply") or "")[:1000]
    if action not in ("approve","reject"): raise HTTPException(400,"approve/reject")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM support_tickets WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет заявки")
        await conn.execute("UPDATE support_tickets SET status=$1,admin_reply=$2,resolved_by=$3,resolved_at=NOW() WHERE id=$4","approved" if action=="approve" else "rejected",reply,user["id"],tid)
        if action=="approve" and t["ticket_type"]=="unscam" and t["from_user"]:
            await conn.execute("UPDATE users SET is_scam=FALSE,scam_perms='{}' WHERE id=$1",t["from_user"])
            await grant_achievement(t["from_user"],"scam_cleared")
        if action=="approve" and t["ticket_type"]=="unban" and t["from_user"]:
            await conn.execute("UPDATE users SET is_banned=FALSE,ban_reason=NULL WHERE id=$1",t["from_user"])
        if action=="approve" and t["ticket_type"] in ("report_scam","report_spam") and t["target_user"]:
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",f"Жалоба #{tid}: "+(t['description'] or '')[:100],t["target_user"])
    return {"ok":True}

# ============ BP ============
@app.get("/api/bp/current")
async def bp_current(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT * FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: return {"active":False}
        prog=await conn.fetchrow("SELECT * FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        quests=await conn.fetch("SELECT * FROM bp_quests WHERE active=TRUE ORDER BY id")
        rewards=await conn.fetch("SELECT * FROM bp_rewards WHERE active=TRUE ORDER BY level,track")
    my_xp=prog["xp"] if prog else 0
    my_level=prog["level"] if prog else 1
    claimed=json.loads(prog["claimed"] or "[]") if prog else []
    has_pp=prog["has_premium_pass"] if prog else False
    xp_per=season.get("xp_per_level") or 1000
    ends_in_days=None
    if season.get("ends_at"):
        try: ends_in_days=max(0,int((season["ends_at"]-datetime.datetime.now(datetime.timezone.utc)).total_seconds()//86400))
        except: pass
    return {
        "active":True,"name":season["name"],"description":season["description"],"emoji":season["emoji"],
        "my_xp":my_xp,"my_level":my_level,"xp_per_level":xp_per,"max_level":season.get("max_level") or 50,
        "ends_in_days":ends_in_days,"has_premium_pass":has_pp,
        "quests":[{"id":q["id"],"name":q["name"],"desc":q["description"],"goal":q["goal"],"xp_reward":q["xp_reward"],"action_type":q.get("action_type"),"target_count":q.get("target_count",1)} for q in quests],
        "rewards":[{"id":r["id"],"level":r["level"],"reward":r["reward"],"reward_type":r.get("reward_type"),"reward_value":r.get("reward_value"),"reward_item_id":r.get("reward_item_id"),"track":r.get("track","free"),"unlocked":my_level>=r["level"] and str(r["id"]) not in claimed,"locked_premium":r.get("track")=="premium" and not has_pp,"claimed":str(r["id"]) in claimed} for r in rewards]
    }

@app.post("/api/bp/claim")
async def bp_claim(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    level=int(data.get("level",0))
    track=(data.get("track") or "free").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: raise HTTPException(404,"Нет сезона")
        r=await conn.fetchrow("SELECT * FROM bp_rewards WHERE level=$1 AND active=TRUE AND track=$2 LIMIT 1",level,track)
        if not r: raise HTTPException(404,"Нет награды")
        prog=await conn.fetchrow("SELECT * FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        if not prog: raise HTTPException(400,"Нет прогресса")
        if prog["level"]<level: raise HTTPException(400,"Уровень мал")
        if track=="premium" and not prog["has_premium_pass"]: raise HTTPException(403,"Нужен Premium")
        claimed=json.loads(prog["claimed"] or "[]")
        rid=str(r["id"])
        if rid in claimed: raise HTTPException(400,"Уже забрано")
        claimed.append(rid)
        await conn.execute("UPDATE bp_progress SET claimed=$1 WHERE id=$2",json.dumps(claimed),prog["id"])
        rt=r.get("reward_type");rv=r.get("reward_value") or 0;ri=r.get("reward_item_id")
        if rt=="coins":
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",rv,user["id"])
            await log_tx(user["id"],rv,"bp reward")
        elif rt=="xp": await grant_xp(user["id"],rv)
        elif rt=="kp": await conn.execute("UPDATE users SET quest_points=quest_points+$1 WHERE id=$2",rv,user["id"])
        elif rt=="candy": await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",rv,user["id"])
        elif rt=="premium":
            await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",rv,user["id"])
        elif rt=="frame" and ri:
            owned=json.loads(user.get("frame_owned") or "[]")
            if ri not in owned:
                owned.append(ri)
                await conn.execute("UPDATE users SET frame_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
        elif rt=="title" and ri:
            await conn.execute("UPDATE users SET title=$1 WHERE id=$2",ri[:64],user["id"])
    return {"ok":True}

@app.post("/api/bp/buy_premium_pass")
async def bp_buy_premium_pass(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if (user.get("coins") or 0)<2000: raise HTTPException(400,"Нужно 2000 🏅")
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: raise HTTPException(404,"Нет сезона")
        prog=await conn.fetchrow("SELECT id,has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_id=$2",user["id"],season["id"])
        if prog and prog["has_premium_pass"]: raise HTTPException(400,"Уже куплен")
        await conn.execute("UPDATE users SET coins=coins-2000 WHERE id=$1",user["id"])
        await log_tx(user["id"],-2000,"bp premium pass")
        if prog: await conn.execute("UPDATE bp_progress SET has_premium_pass=TRUE WHERE id=$1",prog["id"])
        else: await conn.execute("INSERT INTO bp_progress(user_id,season_id,xp,level,has_premium_pass) VALUES($1,$2,0,1,TRUE)",user["id"],season["id"])
    return {"ok":True}

# ============ HOLIDAYS ============
@app.get("/api/holiday/today")
async def holiday_today():
    global forced_holiday
    if forced_holiday:
        h=next((x for x in HOLIDAYS if x[1]==forced_holiday),None)
        if h: return {"active":True,"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"forced":True}
    return get_today_holiday()

@app.get("/api/holiday/all")
async def holiday_all():
    return [{"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"date":h[0]} for h in HOLIDAYS]

# ============ CANDY ============
@app.get("/api/candy/balance")
async def candy_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        curr_row=await conn.fetchrow("SELECT * FROM candy_currency WHERE is_active=TRUE LIMIT 1")
    curr={"key":"halloween","name":"Конфеты","emoji":"🍬"}
    if curr_row: curr={"key":curr_row["key"],"name":curr_row["name"],"emoji":curr_row["emoji"]}
    return {"candy":user.get("candy",0),"currency":curr}

@app.get("/api/candy/shop")
async def candy_shop_list():
    p=await get_pool()
    async with p.acquire() as conn:
        items=await conn.fetch("SELECT * FROM candy_shop_items WHERE is_active=TRUE ORDER BY price")
        curr_row=await conn.fetchrow("SELECT * FROM candy_currency WHERE is_active=TRUE LIMIT 1")
    curr={"key":"halloween","name":"Конфеты","emoji":"🍬"}
    if curr_row: curr={"key":curr_row["key"],"name":curr_row["name"],"emoji":curr_row["emoji"]}
    return {"items":[dict(r) for r in items],"currency":curr}

@app.post("/api/candy/buy")
async def candy_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    item_id=(data.get("item") or "").strip()
    p=await get_pool()
    async with p.acquire() as conn:
        item=await conn.fetchrow("SELECT * FROM candy_shop_items WHERE id=$1 AND is_active=TRUE",item_id)
        if not item: raise HTTPException(404,"Нет предмета")
        price=item["price"]
        if (user.get("candy") or 0)<price: raise HTTPException(400,"Не хватает")
        await conn.execute("UPDATE users SET candy=candy-$1 WHERE id=$2",price,user["id"])
        kind=item["kind"];itemval=item["item"];value=item["value"] or 0;count=item["count"] or 1
        if kind=="frame" and itemval:
            owned=json.loads(user.get("frame_owned") or "[]")
            if itemval not in owned:
                owned.append(itemval)
                await conn.execute("UPDATE users SET frame_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
        elif kind=="title" and itemval: await conn.execute("UPDATE users SET title=$1 WHERE id=$2",itemval[:64],user["id"])
        elif kind=="gift" and itemval:
            for _ in range(count):
                await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],itemval)
        elif kind=="premium":
            await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",value,user["id"])
        elif kind=="coins": await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",value,user["id"])
        elif kind=="xp": await grant_xp(user["id"],value)
        new_candy=await conn.fetchval("SELECT candy FROM users WHERE id=$1",user["id"])
    return {"ok":True,"candy":new_candy}

# ============ QUIZ (КВЕСТ-ЛИНИЯ) ============
@app.get("/api/quiz/status")
async def quiz_status():
    return {"enabled":teacher_quiz_enabled,"title":"Квест-линия «День учителя»","emoji":"🎓"}

@app.get("/api/quiz/questions")
async def quiz_questions(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,question,answers FROM teacher_quiz WHERE is_active=TRUE ORDER BY id")
    return [{"id":r["id"],"question":r["question"],"answers":json.loads(r["answers"])} for r in rows]

@app.post("/api/quiz/answer")
async def quiz_answer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    qid=int(data.get("question_id",0))
    ans=int(data.get("answer",0))
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT correct FROM teacher_quiz WHERE id=$1",qid)
        if not row: raise HTTPException(404,"Нет вопроса")
        correct=(row["correct"]==ans)
    if correct:
        await grant_candy(user["id"],2,silent=True)
        await grant_xp(user["id"],50)
        await bp_add_progress(user["id"],"play_game",1)
    return {"ok":True,"correct":correct,"correct_index":row["correct"]}

@app.post("/api/quiz/finish")
async def quiz_finish(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    perfect=bool(data.get("perfect"))
    await grant_achievement(user["id"],"teacher_quiz_all")
    if perfect: await grant_achievement(user["id"],"teacher_perfect")
    p=await get_pool()
    async with p.acquire() as conn:
        owned=json.loads(user.get("frame_owned") or "[]")
        if "teacher" not in owned:
            owned.append("teacher")
            await conn.execute("UPDATE users SET frame_owned=$1,coins=coins+5000,candy=candy+100 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True,"reward":"🎓 Рамка «Учитель года» + 5000 🏅 + 100 🍬"}

# Квест-линия — вкл/выкл тумблер
@app.post("/api/owner/quest_line/toggle")
async def owner_quest_line_toggle(data:dict):
    global teacher_quiz_enabled
    user=await get_current_user(data.get("token"))
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    enabled=bool(data.get("enabled",True))
    line_key=(data.get("line_key") or "teacher")
    teacher_quiz_enabled=enabled
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE quest_lines SET enabled=$1 WHERE line_key=$2",enabled,line_key)
        await conn.execute("UPDATE system_settings SET value=$1,updated_at=NOW() WHERE key='teacher_quiz_enabled'","1" if enabled else "0")
    return {"ok":True,"enabled":enabled}

@app.get("/api/owner/quest_line/list")
async def owner_quest_line_list(token:str):
    user=await get_current_user(token)
    if not user or user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")
    p=await get_pool()
    async with p.acquire() as conn:
        lines=await conn.fetch("SELECT * FROM quest_lines")
        result=[]
        for l in lines:
            steps=await conn.fetch("SELECT * FROM quest_line_steps WHERE line_id=$1 ORDER BY step_num",l["id"])
            result.append({"id":l["id"],"key":l["line_key"],"name":l["name"],"emoji":l["emoji"],"enabled":l["enabled"],"steps":[dict(s) for s in steps]})
    return result

# ============ COINS / GIFTS / NFT / CASES ============
@app.get("/api/coins/balance")
async def coins_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"coins":user.get("coins",0),"social_rating":user.get("social_rating",0),"candy":user.get("candy",0)}

@app.post("/api/coins/transfer")
async def coins_transfer(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"transfer_coins"): raise HTTPException(403,"SCAM: переводы запрещены")
    tid=int(data.get("to_user",0));amt=int(data.get("amount",0))
    if amt<=0: raise HTTPException(400,"Сумма >0")
    if (user.get("coins",0))<amt: raise HTTPException(400,"Не хватает")
    p=await get_pool()
    async with p.acquire() as conn:
        fr=await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
        if not fr: raise HTTPException(400,"Только друзьям")
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        tax=await conn.fetchval("SELECT percent FROM economy_tax ORDER BY id DESC LIMIT 1") or 0
        tax_amt=int(amt*tax/100);net=amt-tax_amt
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amt,user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",net,tid)
    await log_tx(user["id"],-amt,f"→ {t['username']}")
    await log_tx(tid,net,f"← {user['username']}")
    return {"ok":True,"net":net,"tax":tax_amt}

@app.get("/api/coins/leaders")
async def coins_leaders():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT username,coins FROM users WHERE id!=0 ORDER BY coins DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.get("/api/gifts/all")
async def gifts_all():
    g=await get_all_gifts()
    return [{"gift_id":k,"name":v["name"],"emoji":v.get("emoji"),"image":v.get("image"),"price":v["price"]} for k,v in g.items()]

@app.get("/api/gifts/list/{user_id}")
async def gifts_list(user_id:int):
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT gift FROM gifts WHERE to_user=$1 ORDER BY id DESC",user_id)
    return {"gifts":[dict(r) for r in rows]}

@app.post("/api/gifts/send")
async def gift_send(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"gift_send"): raise HTTPException(403,"SCAM: подарки запрещены")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    gift=g[gift_id];price=gift["price"]
    if (user.get("coins") or 0)<price: raise HTTPException(400,"Не хватает")
    to_id=int(data.get("to_user",0))
    if to_id==SUPPORT_BOT_ID: raise HTTPException(400,"Боту нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",price,user["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],to_id,gift_id)
        await conn.execute("UPDATE users SET social_rating=social_rating+$1 WHERE id=$2",price,user["id"])
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1",user["id"])
    await log_tx(user["id"],-price,f"gift {gift['name']}")
    if cnt==1: await grant_achievement(user["id"],"first_gift")
    await grant_candy(user["id"],2,silent=True)
    await bp_add_progress(user["id"],"give_gift",1)
    return {"ok":True}

@app.get("/api/stickers/list")
async def stickers_list():
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            rows=await conn.fetch("SELECT gift_id,name,emoji,image FROM custom_gifts WHERE is_sticker=TRUE ORDER BY created_at DESC")
        return [{"id":r["gift_id"],"name":r["name"],"emoji":r["emoji"],"image":r["image"]} for r in rows]
    except: return []

@app.post("/api/gifts/upgrade_wheel")
async def gift_upgrade_wheel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    from_gift=data.get("from_gift");to_gift=data.get("to_gift")
    g=await get_all_gifts()
    if from_gift not in g or to_gift not in g: raise HTTPException(400,"Нет подарков")
    gf=g[from_gift];gt=g[to_gift]
    if gt["price"]<=gf["price"]: raise HTTPException(400,"Цель дороже")
    p=await get_pool()
    async with p.acquire() as conn:
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE to_user=$1 AND gift=$2",user["id"],from_gift)
        if cnt<1: raise HTTPException(400,"Нет подарка")
        chance=min(75,(gf["price"]/gt["price"])*100)
        success=random.random()*100<chance
        await conn.execute("DELETE FROM gifts WHERE id=(SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 LIMIT 1)",user["id"],from_gift)
        if success: await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],to_gift)
        await conn.execute("INSERT INTO upgrade_log(user_id,from_gift,to_gift,success,chance) VALUES($1,$2,$3,$4,$5)",user["id"],from_gift,to_gift,success,chance)
    return {"ok":True,"success":success,"chance":chance}

@app.get("/api/gifts/upgrade_history")
async def gift_upgrade_history(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT from_gift,to_gift,success,chance FROM upgrade_log WHERE user_id=$1 ORDER BY id DESC LIMIT 20",user["id"])
    return [dict(r) for r in rows]

@app.get("/api/nft/list")
async def nft_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM nft_series WHERE sold<total ORDER BY id DESC")
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"image":r.get("image"),"price":r["price"],"total":r["total"],"sold":r["sold"],"rarity":r["rarity"],"number":(r["sold"] or 0)+1} for r in rows]

@app.post("/api/nft/buy")
async def nft_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"buy_nft"): raise HTTPException(403,"SCAM: NFT запрещено")
    nid=int(data.get("nft_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",nid)
        if not s: raise HTTPException(404,"Нет")
        if s["sold"]>=s["total"]: raise HTTPException(400,"Распродано")
        if (user.get("coins",0))<s["price"]: raise HTTPException(400,"Не хватает")
        num=s["sold"]+1
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",s["price"],user["id"])
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",nid,num,user["id"])
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",nid)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM nft_items WHERE owner_id=$1",user["id"])
    await log_tx(user["id"],-s["price"],f"NFT {s['name']}")
    if cnt==1: await grant_achievement(user["id"],"first_nft")
    await bp_add_progress(user["id"],"buy_nft",1)
    return {"ok":True,"number":num}

@app.get("/api/cases/list")
async def cases_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,emoji,image,price FROM cases WHERE is_active=TRUE ORDER BY id DESC")
    return [dict(r) for r in rows]

@app.post("/api/cases/open")
async def cases_open(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"open_cases"): raise HTTPException(403,"SCAM: кейсы запрещены")
    cid=int(data.get("case_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT * FROM cases WHERE id=$1 AND is_active=TRUE",cid)
        if not c: raise HTTPException(404,"Нет")
        if (user.get("coins",0))<c["price"]: raise HTTPException(400,"Не хватает")
        prizes=await conn.fetch("SELECT * FROM case_prizes WHERE case_id=$1",cid)
        if not prizes: raise HTTPException(400,"Нет призов")
        total=sum(p["chance"] for p in prizes)
        roll=random.randint(1,total)
        acc=0;chosen=prizes[-1]
        for p in prizes:
            acc+=p["chance"]
            if roll<=acc: chosen=p;break
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",c["price"],user["id"])
        if chosen["kind"]=="coins":
            amt=random.randint(chosen["coins_min"] or 1,chosen["coins_max"] or 1)
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,user["id"])
            prize_text=f"🏅 {amt}"
        elif chosen["kind"]=="gift":
            gid=chosen["item_id"]
            if gid: await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],gid)
            prize_text=f"🎀 {chosen['item_name'] or gid}"
        else: prize_text=f"❓ {chosen['item_name'] or '???'}"
        await conn.execute("INSERT INTO case_opens(user_id,case_id,prize_text) VALUES($1,$2,$3)",user["id"],cid,prize_text)
    await log_tx(user["id"],-c["price"],f"case {c['name']}")
    await grant_candy(user["id"],random.randint(1,5),silent=True)
    await bp_add_progress(user["id"],"open_case",1)
    return {"ok":True,"prize":prize_text}

# ============ LEVELS / FRAMES / PREMIUM / QUESTS / CHEST / LOTTERY / BANK / DUEL ============
@app.get("/api/levels/me")
async def levels_me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"level":user.get("level",1),"xp":user.get("xp",0)}

@app.get("/api/frames/list")
async def frames_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM frames_catalog ORDER BY price_coins")
        owned=json.loads(user.get("frame_owned") or "[]")
    return [{"frame_id":r["frame_id"],"name":r["name"],"emoji":r["emoji"],"css":r["css"],"price_coins":r["price_coins"],"price_kp":r["price_kp"],"owned":r["frame_id"] in owned or r["frame_id"]=="none"} for r in rows]

@app.post("/api/frames/buy")
async def frames_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    fid=data.get("frame_id")
    p=await get_pool()
    async with p.acquire() as conn:
        f=await conn.fetchrow("SELECT * FROM frames_catalog WHERE frame_id=$1",fid)
        if not f: raise HTTPException(404,"Нет рамки")
        owned=json.loads(user.get("frame_owned") or "[]")
        if fid in owned: raise HTTPException(400,"Уже есть")
        method=data.get("method","coins")
        if method=="coins" and f["price_coins"]:
            if (user.get("coins") or 0)<f["price_coins"]: raise HTTPException(400,"Не хватает 🏅")
            await conn.execute("UPDATE users SET coins=coins-$1,frame_owned=$2 WHERE id=$3",f["price_coins"],json.dumps(owned+[fid]),user["id"])
        elif method=="kp" and f["price_kp"]:
            if (user.get("quest_points") or 0)<f["price_kp"]: raise HTTPException(400,"Не хватает КП")
            await conn.execute("UPDATE users SET quest_points=quest_points-$1,frame_owned=$2 WHERE id=$3",f["price_kp"],json.dumps(owned+[fid]),user["id"])
        else: raise HTTPException(400,"Способ не подходит")
    return {"ok":True}

@app.post("/api/frames/set")
async def frames_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    fid=data.get("frame_id","none")
    p=await get_pool()
    async with p.acquire() as conn:
        f=await conn.fetchrow("SELECT * FROM frames_catalog WHERE frame_id=$1",fid)
        if not f: raise HTTPException(404,"Нет рамки")
        if fid!="none":
            owned=json.loads(user.get("frame_owned") or "[]")
            if fid not in owned: raise HTTPException(403,"Не куплена")
        await conn.execute("UPDATE users SET active_frame=$1 WHERE id=$2",fid if fid!="none" else None,user["id"])
    await bp_add_progress(user["id"],"set_frame",1)
    return {"ok":True}

@app.post("/api/premium/buy")
async def premium_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan","month")
    if plan not in PREMIUM_PRICES: raise HTTPException(400,"Нет плана")
    price=PREMIUM_PRICES[plan]
    days=30 if plan=="month" else 365
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT coins,premium_expires FROM users WHERE id=$1",user["id"])
        if (row["coins"] or 0)<price: raise HTTPException(400,f"Нужно {price} 🏅")
        now=datetime.datetime.now(datetime.timezone.utc)
        base=row["premium_expires"] if row["premium_expires"] and row["premium_expires"]>now else now
        new_exp=base+datetime.timedelta(days=days)
        await conn.execute("UPDATE users SET coins=coins-$1,premium_tier='premium',premium_expires=$2 WHERE id=$3",price,new_exp,user["id"])
    await log_tx(user["id"],-price,f"premium {plan}")
    return {"ok":True,"premium_until":new_exp.isoformat()}

@app.get("/api/quests/list")
async def quests_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT quest_day,quest_progress,quest_claimed,quest_points FROM users WHERE id=$1",user["id"])
    today=get_today_key()
    prog={};claimed=[]
    if row["quest_day"]==today:
        prog=json.loads(row["quest_progress"] or "{}")
        claimed=json.loads(row["quest_claimed"] or "[]")
    result=[]
    for q in QUEST_TEMPLATES:
        result.append({"key":q["key"],"name":q["name"],"desc":q["desc"],"emoji":q["emoji"],"goal":q["goal"],"reward_kp":q["reward_kp"],"progress":prog.get(q["key"],0),"claimed":q["key"] in claimed})
    return {"quests":result,"quest_points":row["quest_points"] or 0}

@app.get("/api/chest/status")
async def chest_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    now=datetime.datetime.now(datetime.timezone.utc)
    last=user.get("chest_at")
    available=not last or (now-last).total_seconds()>=86400
    next_in=0 if available else int(86400-(now-last).total_seconds())
    return {"available":available,"next_in":next_in,"streak":user.get("chest_streak",0)}

@app.get("/api/lottery/status")
async def lottery_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        total=await conn.fetchval("SELECT COALESCE(SUM(tickets),0) FROM lottery")
        players=await conn.fetchval("SELECT COUNT(*) FROM lottery WHERE tickets>0")
        my=await conn.fetchval("SELECT tickets FROM lottery WHERE user_id=$1",user["id"]) or 0
    return {"jackpot":total*100,"tickets":my,"players":players}

@app.post("/api/lottery/buy")
async def lottery_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if (user.get("coins") or 0)<100: raise HTTPException(400,"Нужно 100 🏅")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-100 WHERE id=$1",user["id"])
        await conn.execute("INSERT INTO lottery(user_id,tickets,updated_at) VALUES($1,1,NOW()) ON CONFLICT (user_id) DO UPDATE SET tickets=lottery.tickets+1,updated_at=NOW()",user["id"])
    await log_tx(user["id"],-100,"lottery ticket")
    return {"ok":True}

@app.get("/api/bank/status")
async def bank_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    dep=user.get("bank_deposit",0) or 0
    last=user.get("bank_at")
    interest=0
    if last and dep>0:
        days=(datetime.datetime.now(datetime.timezone.utc)-last).total_seconds()/86400
        interest=int(dep*0.015*days)
    return {"deposit":dep,"interest":interest}

@app.post("/api/bank/deposit")
async def bank_deposit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    amt=int(data.get("amount",0))
    if amt<=0: raise HTTPException(400,"Сумма >0")
    if (user.get("coins") or 0)<amt: raise HTTPException(400,"Не хватает")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1,bank_deposit=bank_deposit+$1,bank_at=NOW() WHERE id=$2",amt,user["id"])
    return {"ok":True}

@app.post("/api/bank/withdraw")
async def bank_withdraw(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT bank_deposit,bank_at FROM users WHERE id=$1",user["id"])
        if not row or not row["bank_deposit"]: raise HTTPException(400,"Пусто")
        days=(datetime.datetime.now(datetime.timezone.utc)-row["bank_at"]).total_seconds()/86400 if row["bank_at"] else 0
        interest=int(row["bank_deposit"]*0.015*days)
        total=row["bank_deposit"]+interest
        await conn.execute("UPDATE users SET coins=coins+$1,bank_deposit=0,bank_at=NULL WHERE id=$2",total,user["id"])
    return {"ok":True,"got":total,"interest":interest}

@app.post("/api/duel/fire")
async def duel_fire(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"play_games"): raise HTTPException(403,"SCAM: игры запрещены")
    bet=int(data.get("bet",0))
    if bet<50: raise HTTPException(400,"Мин 50")
    if (user.get("coins") or 0)<bet: raise HTTPException(400,"Не хватает")
    win=random.random()<0.5
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",bet,user["id"])
        if win:
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",bet*2,user["id"])
            await bp_add_progress(user["id"],"win_duel",1)
        await conn.execute("INSERT INTO game_scores(user_id,game,score) VALUES($1,'duel',$2)",user["id"],1 if win else 0)
    return {"ok":True,"win":win,"got":bet*2 if win else 0}

@app.post("/api/games/submit")
async def games_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"play_games"): raise HTTPException(403,"SCAM: игры запрещены")
    game=data.get("game");score=int(data.get("score",0))
    if game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    if score<0 or score>1000000: raise HTTPException(400,"Плохой счёт")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO game_scores(user_id,game,score) VALUES($1,$2,$3)",user["id"],game,score)
    if game=="snake" and score>=100: await grant_achievement(user["id"],"snake_100")
    await grant_xp(user["id"],5)
    await grant_candy(user["id"],random.randint(1,5),silent=True)
    await bp_add_progress(user["id"],"play_game",1)
    return {"ok":True}

# ============ ADMIN / MOD ============
async def check_admin(user):
    if not user: raise HTTPException(401,"Не авторизован")
    if not (user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Не админ")

@app.post("/api/admin/verify")
async def admin_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not user.get("is_admin"): raise HTTPException(403,"Не админ")
    pw=data.get("password") or ""
    stored=user.get("admin_password")
    if stored and not verify_password(pw,stored): raise HTTPException(403,"Неверный")
    if not stored and pw!="12344321": raise HTTPException(403,"Установи пароль")
    return {"ok":True}

@app.get("/api/admin/stats")
async def admin_stats(token:str):
    user=await get_current_user(token); await check_admin(user)
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        s=await conn.fetchval("SELECT COUNT(*) FROM servers")
        m=await conn.fetchval("SELECT COUNT(*) FROM messages")
    return {"users":u,"servers":s,"messages":m,"online":len(online_users)}

@app.get("/api/admin/users")
async def admin_users(token:str):
    user=await get_current_user(token); await check_admin(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT id,username,is_admin,is_moderator,is_scam,is_banned,coins,candy,social_rating,title FROM users WHERE id!=0 ORDER BY id""")
    return [dict(r) for r in rows]

@app.post("/api/admin/action")
async def admin_action(data:dict):
    user=await get_current_user(data.get("token")); await check_admin(user)
    tid=int(data.get("target_id",0));action=data.get("action")
    is_owner=user["username"]==ADMIN_USERNAME
    if action=="ban" and not is_owner: raise HTTPException(403,"Отправь заявку")
    p=await get_pool()
    async with p.acquire() as conn:
        if action=="ban": await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",data.get("reason",""),tid)
        elif action=="unban": await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",tid)
        elif action=="mute":
            d=int(data.get("duration",3600))
            await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",d,tid)
    await log_admin(user["id"],action,tid)
    return {"ok":True}

@app.post("/api/admin/toggle_scam")
async def admin_toggle_scam(data:dict):
    user=await get_current_user(data.get("token")); await check_admin(user)
    tid=int(data.get("target_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        cur=await conn.fetchval("SELECT is_scam FROM users WHERE id=$1",tid)
        new=not bool(cur)
        perms=json.dumps(SCAM_DEFAULT_PERMS) if new else "{}"
        await conn.execute("UPDATE users SET is_scam=$1,scam_perms=$2 WHERE id=$3",new,perms,tid)
    await log_admin(user["id"],"toggle_scam",tid,f"is_scam={new}")
    return {"ok":True,"is_scam":new}

@app.get("/api/admin/logs")
async def admin_logs(token:str):
    user=await get_current_user(token); await check_admin(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT l.id,l.action,l.details,l.created_at,a.username AS admin_name FROM admin_logs l LEFT JOIN users a ON a.id=l.admin_id ORDER BY l.id DESC LIMIT 100")
    return [{"id":r["id"],"action":r["action"],"details":r["details"],"created_at":r["created_at"].isoformat() if r["created_at"] else None,"admin_name":r["admin_name"]} for r in rows]

# ============ OWNER ============
async def check_owner(user):
    if not user: raise HTTPException(401,"Не авторизован")
    if user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Только владелец")

@app.post("/api/owner/verify")
async def owner_verify(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    if data.get("password")!=OWNER_PASSWORD: raise HTTPException(403,"Неверный")
    return {"ok":True}

@app.get("/api/owner/stats")
async def owner_stats(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        u=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
        m=await conn.fetchval("SELECT COUNT(*) FROM messages")
        c=await conn.fetchval("SELECT COALESCE(SUM(coins),0) FROM users")
    return {"users":u,"messages":m,"coins":c,"online":len(online_users)}

@app.post("/api/owner/give_coins")
async def owner_give_coins(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,t["id"])
    await log_tx(t["id"],amt,"owner give")
    return {"ok":True}

@app.post("/api/owner/give_candy")
async def owner_give_candy(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",50))
        await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",amt,t["id"])
    return {"ok":True,"amount":amt}

@app.post("/api/owner/announce_full")
async def owner_announce_full(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    username=(data.get("username") or user["username"])[:32]
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    if len(text)>1000: text=text[:1000]
    sent=0
    for uid in list(manager.connections.keys()):
        try:
            await manager.send_to(uid,{"type":"abuse_announce","username":username,"avatar":user.get("avatar"),"text":text})
            sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.post("/api/owner/hot_swap")
async def owner_hot_swap(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    sent=0
    for uid in list(manager.connections.keys()):
        try:
            await manager.send_to(uid,{"type":"force_reload"})
            sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.post("/api/owner/change_nick")
async def owner_change_nick(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    new_nick=(data.get("new_nick") or "").strip()
    old=(data.get("username") or "").strip()
    if not new_nick or not old: raise HTTPException(400,"Заполни")
    p=await get_pool()
    async with p.acquire() as conn:
        clean=await get_unique_username(conn,new_nick)
        await conn.execute("UPDATE users SET username=$1 WHERE username=$2",clean,old)
    return {"ok":True,"new_username":clean}

@app.post("/api/owner/read_chat")
async def owner_read_chat(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        rows=await conn.fetch("SELECT m.text,u.username AS from_user FROM messages m JOIN users u ON u.id=m.user_id WHERE m.user_id=$1 ORDER BY m.id DESC LIMIT 50",t["id"])
    return {"messages":[{"from":r["from_user"],"text":r["text"]} for r in rows]}

@app.post("/api/owner/write_as")
async def owner_write_as(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username,avatar FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        ch=await conn.fetchrow("SELECT c.id FROM channels c JOIN server_members sm ON sm.server_id=c.server_id WHERE sm.user_id=$1 ORDER BY c.id LIMIT 1",t["id"])
        if ch:
            msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text) VALUES($1,$2,$3) RETURNING *",ch["id"],t["id"],data.get("text",""))
    return {"ok":True}

@app.post("/api/owner/force_logout")
async def owner_force_logout(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    tid=int(data.get("user_id",0))
    await manager.send_to(tid,{"type":"force_logout"})
    return {"ok":True}

@app.post("/api/owner/mass_color")
async def owner_mass_color(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET nickname_color=$1 WHERE username!=$2 AND id!=0",data.get("color"),ADMIN_USERNAME)
    return {"ok":True}

@app.get("/api/owner/chat")
async def owner_chat_get(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT om.id,om.text,om.created_at,u.username FROM owner_messages om LEFT JOIN users u ON u.id=om.from_user ORDER BY om.id DESC LIMIT 100")
    return [{"id":r["id"],"text":r["text"],"username":r["username"]} for r in reversed(rows)]

# ============ ABUSE ============
@app.get("/api/abuse/access")
async def abuse_access(token:str):
    user=await get_current_user(token)
    acc=await has_abuse_access(user)
    if not acc: return {"access":False}
    return {"access":True,"owner":acc.get("owner",False),"can_gift":acc.get("can_gift",False),"can_coins":acc.get("can_coins",False),"can_candy":acc.get("can_candy",False),"can_online":acc.get("can_online",False)}

@app.get("/api/abuse/online")
async def abuse_online(token:str):
    user=await get_current_user(token)
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_online"): raise HTTPException(403,"Нет доступа")
    p=await get_pool()
    async with p.acquire() as conn:
        if not online_users: return {"users":[]}
        rows=await conn.fetch("SELECT id,username,avatar FROM users WHERE id=ANY($1::int[]) AND id!=0 ORDER BY username",list(online_users))
    return {"users":[dict(r) for r in rows]}

@app.post("/api/abuse/random_gift")
async def abuse_random_gift(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_gift"): raise HTTPException(403,"Нет доступа")
    if not online_users: raise HTTPException(400,"Никого")
    g=await get_all_gifts()
    if not g: raise HTTPException(400,"Нет подарков")
    tid=random.choice(list(online_users))
    if tid==SUPPORT_BOT_ID: raise HTTPException(400,"Боту нельзя")
    gid=random.choice(list(g.keys()));gift=g[gid]
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],tid,gid)
    return {"ok":True,"target":t["username"],"gift":gift["name"]}

@app.post("/api/abuse/random_coins")
async def abuse_random_coins(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc or not acc.get("can_coins"): raise HTTPException(403,"Нет доступа")
    if not online_users: raise HTTPException(400,"Никого")
    tid=random.choice(list(online_users))
    if tid==SUPPORT_BOT_ID: raise HTTPException(400,"Боту нельзя")
    amt=random.randint(100,10000)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Пропал")
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,tid)
    return {"ok":True,"target":t["username"],"amount":amt}

@app.post("/api/abuse/random_candy")
async def abuse_random_candy(data:dict):
    user=await get_current_user(data.get("token"))
    acc=await has_abuse_access(user)
    if not acc or not (acc.get("can_candy") or acc.get("owner")): raise HTTPException(403,"Нет доступа")
    if not online_users: raise HTTPException(400,"Никого")
    tid=random.choice(list(online_users))
    if tid==SUPPORT_BOT_ID: raise HTTPException(400,"Боту нельзя")
    amt=random.randint(10,200)
    await grant_candy(tid,amt)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT username FROM users WHERE id=$1",tid)
    return {"ok":True,"target":t["username"] if t else "?","amount":amt}

# ============ STATIC ============
@app.get("/manifest.json")
async def manifest():
    return {"name":"Belugacord 2.8","short_name":"Belugacord","start_url":"/","display":"standalone","background_color":"#1a0a2e","theme_color":"#1a0a2e"}

@app.get("/")
async def index():
    with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())

# ============================================================================
# ЗДЕСЬ ЗАКАНЧИВАЕТСЯ ЧАСТЬ 1/2
# Следующая часть: WS, титулы, PvP, биржа, крафт, аукцион, кредиты, system, backup, main
# ============================================================================

# ============================================================================
# BELUGACORD 2.8 — ЧАСТЬ 2/2
# Титулы, PvP, биржа, крафт, аукцион, кредиты, system, backup, WS, main
# ============================================================================

# ============ ТИТУЛЫ ============
@app.get("/api/titles/list")
async def titles_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT t.*, 
            (SELECT 1 FROM title_owned WHERE user_id=$1 AND title_id=t.id) AS owned
            FROM titles t 
            WHERE t.visibility='public' OR t.owner_id=$1 
            ORDER BY t.price DESC, t.id DESC LIMIT 200""",user["id"])
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"visibility":r["visibility"],"price":r["price"],"owner_id":r["owner_id"],"owned":bool(r["owned"])} for r in rows]

@app.get("/api/titles/my")
async def titles_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT t.* FROM titles t 
            JOIN title_owned o ON o.title_id=t.id 
            WHERE o.user_id=$1 ORDER BY o.acquired_at DESC""",user["id"])
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"visibility":r["visibility"]} for r in rows]

@app.post("/api/titles/create")
async def titles_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:32]
    if not name: raise HTTPException(400,"Название нужно")
    emoji=(data.get("emoji") or "👑")[:8]
    vis=(data.get("visibility") or "private")[:16]
    if vis not in ("private","public"): vis="private"
    price=int(data.get("price",0))
    if price<0: price=0
    if price>10000000: price=10000000
    COST=5000
    if (user.get("coins") or 0)<COST: raise HTTPException(400,f"Нужно {COST} 🏅")
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM titles WHERE name=$1 AND (visibility='public' OR owner_id=$2)",name,user["id"])
        if exists: raise HTTPException(400,"Такое название уже есть")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",COST,user["id"])
        r=await conn.fetchrow("INSERT INTO titles(name,emoji,owner_id,visibility,price) VALUES($1,$2,$3,$4,$5) RETURNING id",name,emoji,user["id"],vis,price)
        await conn.execute("INSERT INTO title_owned(user_id,title_id) VALUES($1,$2)",user["id"],r["id"])
    await log_tx(user["id"],-COST,f"title create {name}")
    await grant_achievement(user["id"],"title_master")
    return {"ok":True,"id":r["id"]}

@app.post("/api/titles/buy")
async def titles_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет титула")
        if t["visibility"]!="public": raise HTTPException(403,"Титул приватный")
        if t["owner_id"]==user["id"]: raise HTTPException(400,"Твой титул")
        owned=await conn.fetchrow("SELECT 1 FROM title_owned WHERE user_id=$1 AND title_id=$2",user["id"],tid)
        if owned: raise HTTPException(400,"Уже есть")
        if (user.get("coins") or 0)<t["price"]: raise HTTPException(400,"Не хватает")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",t["price"],user["id"])
        await conn.execute("INSERT INTO title_owned(user_id,title_id) VALUES($1,$2)",user["id"],tid)
        if t["owner_id"]:
            cut=int(t["price"]*0.7)
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",cut,t["owner_id"])
            await log_tx(t["owner_id"],cut,f"title sale {t['name']}")
    await log_tx(user["id"],-t["price"],f"title buy {t['name']}")
    return {"ok":True}

@app.post("/api/titles/set")
async def titles_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("title") or "").strip()[:64]
    if name:
        p=await get_pool()
        async with p.acquire() as conn:
            t=await conn.fetchrow("""SELECT t.id FROM titles t 
                JOIN title_owned o ON o.title_id=t.id 
                WHERE o.user_id=$1 AND t.name=$2 LIMIT 1""",user["id"],name)
            if not t: raise HTTPException(403,"Титул не куплен")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",name or None,user["id"])
    return {"ok":True}

@app.post("/api/titles/delete")
async def titles_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT owner_id FROM titles WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет")
        if t["owner_id"]!=user["id"] and user["username"]!=ADMIN_USERNAME: raise HTTPException(403,"Не твой")
        await conn.execute("DELETE FROM titles WHERE id=$1",tid)
    return {"ok":True}

# ==== OWNER: создание/выдача титулов ====
@app.post("/api/owner/titles/create")
async def owner_titles_create(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "").strip()[:32]
    if not name: raise HTTPException(400,"Название нужно")
    emoji=(data.get("emoji") or "👑")[:8]
    vis=(data.get("visibility") or "private")[:16]
    if vis not in ("private","public"): vis="private"
    price=int(data.get("price",0))
    if price<0: price=0
    p=await get_pool()
    async with p.acquire() as conn:
        exists=await conn.fetchrow("SELECT id FROM titles WHERE name=$1",name)
        if exists: raise HTTPException(400,"Такое название уже есть")
        r=await conn.fetchrow("INSERT INTO titles(name,emoji,owner_id,visibility,price) VALUES($1,$2,$3,$4,$5) RETURNING id",name,emoji,user["id"],vis,price)
        await conn.execute("INSERT INTO title_owned(user_id,title_id) VALUES($1,$2)",user["id"],r["id"])
    return {"ok":True,"id":r["id"]}

@app.post("/api/owner/titles/grant")
async def owner_titles_grant(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    uname=(data.get("username") or "").strip().lstrip("@")
    title_name=(data.get("title") or "").strip()[:64]
    if not uname or not title_name: raise HTTPException(400,"Заполни")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",uname)
        if not t: raise HTTPException(404,"Юзер не найден")
        ti=await conn.fetchrow("SELECT id FROM titles WHERE name=$1 LIMIT 1",title_name)
        if not ti: raise HTTPException(404,"Титул не найден")
        try:
            await conn.execute("INSERT INTO title_owned(user_id,title_id) VALUES($1,$2)",t["id"],ti["id"])
        except: pass
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",title_name,t["id"])
    return {"ok":True}

@app.post("/api/owner/titles/delete")
async def owner_titles_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    tid=int(data.get("title_id",0))
    if not tid:
        title_name=(data.get("name") or "").strip()
        if not title_name: raise HTTPException(400,"ID или name нужен")
        p=await get_pool()
        async with p.acquire() as conn:
            t=await conn.fetchrow("SELECT id FROM titles WHERE name=$1",title_name)
            if t: tid=t["id"]
    if not tid: raise HTTPException(404,"Не найден")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM titles WHERE id=$1",tid)
    return {"ok":True}

@app.get("/api/owner/titles/all")
async def owner_titles_all(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM titles ORDER BY id DESC")
    return [dict(r) for r in rows]

# ============ РЕКОМЕНДАЦИИ ДРУЗЕЙ ============
@app.get("/api/friends/recommendations")
async def friends_recommendations(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    uid=user["id"]
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""
            WITH my_friends AS (
                SELECT CASE WHEN user_a=$1 THEN user_b ELSE user_a END AS fid
                FROM friendships WHERE user_a=$1 OR user_b=$1
            ),
            fof AS (
                SELECT CASE WHEN user_a=mf.fid THEN user_b ELSE user_a END AS rec_id, COUNT(*) AS mutual
                FROM friendships f
                JOIN my_friends mf ON (f.user_a=mf.fid OR f.user_b=mf.fid)
                GROUP BY rec_id
            )
            SELECT u.*, COALESCE(fof.mutual,0) AS mutual
            FROM users u
            LEFT JOIN fof ON fof.rec_id=u.id
            WHERE u.id!=$1 AND u.id!=0
              AND u.id NOT IN (SELECT fid FROM my_friends)
              AND u.id NOT IN (SELECT to_user FROM friend_requests WHERE from_user=$1)
              AND u.id NOT IN (SELECT from_user FROM friend_requests WHERE to_user=$1)
              AND NOT EXISTS (SELECT 1 FROM blocks WHERE (blocker=$1 AND blocked=u.id) OR (blocker=u.id AND blocked=$1))
            ORDER BY mutual DESC NULLS LAST, u.last_seen DESC NULLS LAST
            LIMIT 20
        """,uid)
    return [{"id":r["id"],"username":r["username"],"avatar":r["avatar"],"gif_avatar":r.get("gif_avatar"),"mutual":r.get("mutual",0)} for r in rows]

# ============ PvP АРЕНА ============
@app.post("/api/pvp/find")
async def pvp_find(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"play_games"): raise HTTPException(403,"SCAM: игры запрещены")
    bet=int(data.get("bet",100))
    if bet<50: raise HTTPException(400,"Мин 50")
    if (user.get("coins") or 0)<bet: raise HTTPException(400,"Не хватает")
    candidates=[uid for uid in online_users if uid!=user["id"] and uid!=SUPPORT_BOT_ID]
    if not candidates: raise HTTPException(400,"Никого нет онлайн")
    opponent=random.choice(candidates)
    win=random.random()<0.5
    p=await get_pool()
    async with p.acquire() as conn:
        opp=await conn.fetchrow("SELECT username FROM users WHERE id=$1",opponent)
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",bet,user["id"])
        if win:
            gain=int(bet*1.9)
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",gain,user["id"])
            await conn.execute("INSERT INTO pvp_matches(player_a,player_b,bet,winner) VALUES($1,$2,$3,$4)",user["id"],opponent,bet,user["id"])
            await grant_achievement(user["id"],"pvp_win")
            await bp_add_progress(user["id"],"win_duel",1)
        else:
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",bet,opponent)
            await conn.execute("INSERT INTO pvp_matches(player_a,player_b,bet,winner) VALUES($1,$2,$3,$4)",user["id"],opponent,bet,opponent)
    await log_tx(user["id"],gain if win else -bet,f"pvp vs {opp.get('username') if opp else '?'}")
    return {"ok":True,"win":win,"got":gain if win else 0,"opponent":opp.get("username") if opp else "?"}

@app.get("/api/pvp/history")
async def pvp_history(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""
            SELECT p.id,p.bet,p.winner,p.created_at,
                CASE WHEN p.player_a=$1 THEN p.player_b ELSE p.player_a END AS opp_id
            FROM pvp_matches p 
            WHERE p.player_a=$1 OR p.player_b=$1
            ORDER BY p.id DESC LIMIT 30
        """,user["id"])
        out=[]
        for r in rows:
            o=await conn.fetchrow("SELECT username FROM users WHERE id=$1",r["opp_id"])
            out.append({"id":r["id"],"bet":r["bet"],"win":r["winner"]==user["id"],"opponent":o["username"] if o else "?","created_at":r["created_at"].isoformat() if r["created_at"] else None})
    return out

# ============ БИРЖА ПОДАРКОВ ============
@app.get("/api/exchange/list")
async def exchange_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""
            SELECT e.id,e.gift_id,e.price,e.seller_id,u.username
            FROM gift_exchange e JOIN users u ON u.id=e.seller_id
            WHERE e.status='active' ORDER BY e.price ASC, e.id DESC LIMIT 100
        """)
    return [{"id":r["id"],"gift_id":r["gift_id"],"price":r["price"],"seller":r["username"]} for r in rows]

@app.post("/api/exchange/create")
async def exchange_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift_id")
    price=int(data.get("price",0))
    if price<=0: raise HTTPException(400,"Цена>0")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 LIMIT 1",user["id"],gift_id)
        if not row: raise HTTPException(400,"Нет такого подарка")
        await conn.execute("DELETE FROM gifts WHERE id=$1",row["id"])
        r=await conn.fetchrow("INSERT INTO gift_exchange(seller_id,gift_id,price) VALUES($1,$2,$3) RETURNING id",user["id"],gift_id,price)
    return {"ok":True,"id":r["id"]}

@app.post("/api/exchange/buy")
async def exchange_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    lid=int(data.get("listing_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        e=await conn.fetchrow("SELECT * FROM gift_exchange WHERE id=$1 AND status='active'",lid)
        if not e: raise HTTPException(404,"Нет лота")
        if e["seller_id"]==user["id"]: raise HTTPException(400,"Свой лот")
        if (user.get("coins") or 0)<e["price"]: raise HTTPException(400,"Не хватает")
        tax=int(e["price"]*0.05)
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",e["price"],user["id"])
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",e["price"]-tax,e["seller_id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",e["seller_id"],user["id"],e["gift_id"])
        await conn.execute("UPDATE gift_exchange SET status='sold',buyer_id=$1,sold_at=NOW() WHERE id=$2",user["id"],lid)
    await log_tx(user["id"],-e["price"],f"exchange buy {e['gift_id']}")
    await log_tx(e["seller_id"],e["price"]-tax,f"exchange sell {e['gift_id']}")
    await grant_achievement(user["id"],"trader")
    return {"ok":True}

@app.post("/api/exchange/cancel")
async def exchange_cancel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    lid=int(data.get("listing_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        e=await conn.fetchrow("SELECT * FROM gift_exchange WHERE id=$1 AND status='active'",lid)
        if not e: raise HTTPException(404,"Нет лота")
        if e["seller_id"]!=user["id"]: raise HTTPException(403,"Не твой")
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],e["gift_id"])
        await conn.execute("UPDATE gift_exchange SET status='cancelled' WHERE id=$1",lid)
    return {"ok":True}

# ============ КРАФТ ============
@app.get("/api/craft/recipes")
async def craft_recipes():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM craft_recipes WHERE is_active=TRUE")
    return [{"id":r["id"],"result_gift":r["result_gift"],"ingredients":json.loads(r["ingredients"])} for r in rows]

@app.post("/api/craft/random")
async def craft_random(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    recipe_id=int(data.get("recipe_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("SELECT * FROM craft_recipes WHERE id=$1 AND is_active=TRUE",recipe_id) if recipe_id else None
        if not r:
            all_r=await conn.fetch("SELECT * FROM craft_recipes WHERE is_active=TRUE")
            if not all_r: raise HTTPException(400,"Нет рецептов")
            r=random.choice(all_r)
        ingredients=json.loads(r["ingredients"])
        for gift_id,count in ingredients.items():
            have=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE to_user=$1 AND gift=$2",user["id"],gift_id)
            if have<count: raise HTTPException(400,f"Не хватает {gift_id} ({have}/{count})")
        for gift_id,count in ingredients.items():
            ids=await conn.fetch("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 LIMIT $3",user["id"],gift_id,count)
            for row in ids: await conn.execute("DELETE FROM gifts WHERE id=$1",row["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],r["result_gift"])
    await grant_achievement(user["id"],"crafter")
    return {"ok":True,"crafted":r["result_gift"]}

# ============ АУКЦИОН 2.0 ============
@app.get("/api/auction/list")
async def auction_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""
            SELECT a.*, u.username AS seller_name
            FROM auction2 a JOIN users u ON u.id=a.seller_id
            WHERE a.status='active' AND a.ends_at>NOW() ORDER BY a.id DESC LIMIT 100
        """)
    return [{"id":r["id"],"title":r["item_name"],"emoji":r["item_emoji"],"bid":r["current_price"] or r["start_price"],"seller":r["seller_name"],"ends_at":r["ends_at"].isoformat() if r["ends_at"] else None} for r in rows]

@app.post("/api/auction/bid")
async def auction_bid(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    lid=int(data.get("lot_id",0))
    amount=int(data.get("amount",0))
    if amount<=0: raise HTTPException(400,"Сумма>0")
    p=await get_pool()
    async with p.acquire() as conn:
        lot=await conn.fetchrow("SELECT * FROM auction2 WHERE id=$1 AND status='active'",lid)
        if not lot: raise HTTPException(404,"Лот закрыт")
        cur=lot["current_price"] or lot["start_price"]
        if amount<cur+1: raise HTTPException(400,f"Минимум {cur+1}")
        if (user.get("coins") or 0)<amount: raise HTTPException(400,"Не хватает")
        if lot["current_bidder"] and lot["current_bidder"]!=user["id"]:
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",cur,lot["current_bidder"])
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amount,user["id"])
        ends=lot["ends_at"]
        if lot["auto_extend"] and ends:
            now=datetime.datetime.now(datetime.timezone.utc)
            if (ends-now).total_seconds()<60:
                ends=now+datetime.timedelta(minutes=5)
                await conn.execute("UPDATE auction2 SET ends_at=$1 WHERE id=$2",ends,lid)
        await conn.execute("UPDATE auction2 SET current_price=$1,current_bidder=$2 WHERE id=$3",amount,user["id"],lid)
    await log_tx(user["id"],-amount,f"auction bid {lot['item_name']}")
    return {"ok":True}

@app.post("/api/auction/create")
async def auction_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gift_id=data.get("gift_id")
    start_price=int(data.get("start_price",0))
    if start_price<=0: raise HTTPException(400,"Старт>0")
    dur=int(data.get("duration_minutes",60))
    if dur<5: dur=5
    if dur>10080: dur=10080
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM gifts WHERE to_user=$1 AND gift=$2 LIMIT 1",user["id"],gift_id)
        if not row: raise HTTPException(400,"Нет подарка")
        await conn.execute("DELETE FROM gifts WHERE id=$1",row["id"])
        ends=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=dur)
        await conn.execute("""INSERT INTO auction2(seller_id,item_type,item_id,item_name,item_emoji,start_price,current_price,ends_at)
            VALUES($1,'gift',$2,$3,$4,$5,$5,$6)""",user["id"],gift_id,g[gift_id]["name"],g[gift_id].get("emoji") or "🎁",start_price,ends)
    return {"ok":True}

# ============ КРЕДИТЫ ============
@app.get("/api/credits/status")
async def credits_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM credits WHERE user_id=$1 ORDER BY id DESC LIMIT 10",user["id"])
    return [{"id":r["id"],"amount":r["amount"],"remaining":r["remaining"],"rate":r["rate"],"due_at":r["due_at"].isoformat() if r["due_at"] else None,"status":r["status"]} for r in rows]

@app.post("/api/credits/take")
async def credits_take(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    amount=int(data.get("amount",0))
    if amount<100: raise HTTPException(400,"Мин 100")
    if amount>100000: raise HTTPException(400,"Макс 100000")
    max_credit=10000+(user.get("social_rating") or 0)*10
    if amount>max_credit: raise HTTPException(400,f"Максимум {max_credit}")
    p=await get_pool()
    async with p.acquire() as conn:
        active=await conn.fetchrow("SELECT id FROM credits WHERE user_id=$1 AND status='active'",user["id"])
        if active: raise HTTPException(400,"Уже есть активный кредит")
        due=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=30)
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amount,user["id"])
        r=await conn.fetchrow("INSERT INTO credits(user_id,amount,remaining,rate,due_at) VALUES($1,$2,$2,0.05,$3) RETURNING id",user["id"],amount,due)
    await log_tx(user["id"],amount,f"credit #{r['id']}")
    return {"ok":True,"credit_id":r["id"],"due_at":due.isoformat()}

@app.post("/api/credits/pay")
async def credits_pay(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    cid=int(data.get("credit_id",0))
    amount=int(data.get("amount",0))
    if amount<=0: raise HTTPException(400,"Сумма>0")
    p=await get_pool()
    async with p.acquire() as conn:
        c=await conn.fetchrow("SELECT * FROM credits WHERE id=$1 AND user_id=$2",cid,user["id"])
        if not c: raise HTTPException(404,"Нет кредита")
        if c["status"]!="active": raise HTTPException(400,"Не активен")
        if (user.get("coins") or 0)<amount: raise HTTPException(400,"Не хватает")
        pay=min(amount,c["remaining"])
        new_remaining=c["remaining"]-pay
        status="paid" if new_remaining<=0 else "active"
        paid_at=datetime.datetime.now(datetime.timezone.utc) if status=="paid" else None
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",pay,user["id"])
        await conn.execute("UPDATE credits SET remaining=$1,status=$2,paid_at=$3 WHERE id=$4",new_remaining,status,paid_at,cid)
    await log_tx(user["id"],-pay,f"credit pay #{cid}")
    if status=="paid": await grant_achievement(user["id"],"credit_ok")
    return {"ok":True,"remaining":new_remaining,"status":status}

# ============ ЭКОНОМИКА: налоги, история ============
@app.get("/api/economy/tax")
async def economy_tax_get():
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT percent FROM economy_tax ORDER BY id DESC LIMIT 1")
    return {"percent":row["percent"] if row else 0}

@app.post("/api/owner/economy/tax")
async def economy_tax_set(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    pct=float(data.get("percent",0))
    if pct<0: pct=0
    if pct>50: pct=50
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO economy_tax(percent) VALUES($1)",pct)
    return {"ok":True,"percent":pct}

@app.get("/api/economy/history")
async def economy_history(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT amount,reason,balance_after,created_at FROM transactions WHERE user_id=$1 ORDER BY id DESC LIMIT 100",user["id"])
    return [{"amount":r["amount"],"reason":r["reason"],"balance_after":r["balance_after"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

# ============ SYSTEM / BACKUP ============
@app.get("/api/system/status")
async def system_status():
    p=await get_pool()
    db_ok=True
    try:
        async with p.acquire() as conn: await conn.fetchval("SELECT 1")
    except: db_ok=False
    uptime=time.time()-START_TIME
    users=0;msgs=0
    try:
        async with p.acquire() as conn:
            users=await conn.fetchval("SELECT COUNT(*) FROM users WHERE id!=0")
            msgs=await conn.fetchval("SELECT COUNT(*) FROM messages")
    except: pass
    return {"db":db_ok,"ws":True,"uptime":int(uptime),"users":users,"messages":msgs,"online":len(online_users),"version":CURRENT_VERSION}

@app.get("/api/user/backup")
async def user_backup(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        achievements=json.loads(user.get("achievements") or "[]")
        frame_owned=json.loads(user.get("frame_owned") or "[]")
        gifts=await conn.fetch("SELECT gift FROM gifts WHERE to_user=$1",user["id"])
        nfts=await conn.fetch("""SELECT ni.number,ns.name,ns.emoji FROM nft_items ni 
            JOIN nft_series ns ON ns.id=ni.series_id WHERE ni.owner_id=$1""",user["id"])
        title_rows=await conn.fetch("""SELECT t.name,t.emoji FROM titles t 
            JOIN title_owned o ON o.title_id=t.id WHERE o.user_id=$1""",user["id"])
        friends=await conn.fetchval("SELECT COUNT(*) FROM friendships WHERE user_a=$1 OR user_b=$1",user["id"])
    return {
        "user":{"id":user["id"],"username":user["username"],"bio":user.get("bio"),"avatar":user.get("avatar")},
        "stats":{"coins":user.get("coins"),"candy":user.get("candy"),"level":user.get("level"),"xp":user.get("xp"),"reputation":user.get("reputation"),"social_rating":user.get("social_rating"),"messages_count":user.get("messages_count"),"quest_points":user.get("quest_points")},
        "achievements":achievements,
        "frames":frame_owned,
        "active_frame":user.get("active_frame"),
        "title":user.get("title"),
        "titles":[dict(t) for t in title_rows],
        "gifts":[r["gift"] for r in gifts],
        "nfts":[dict(n) for n in nfts],
        "friends_count":friends or 0,
        "exported_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version":CURRENT_VERSION
    }

# ============ MOD РАСШИРЕНИЯ ============
@app.post("/api/mod/note")
async def mod_note(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    uid=int(data.get("user_id",0))
    note=(data.get("note") or "").strip()[:500]
    if not note: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO mod_notes(user_id,mod_id,note) VALUES($1,$2,$3)",uid,user["id"],note)
    return {"ok":True}

@app.get("/api/mod/notes/{user_id}")
async def mod_notes_list(user_id:int,token:str):
    user=await get_current_user(token)
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT n.id,n.note,n.created_at,m.username AS mod_name 
            FROM mod_notes n LEFT JOIN users m ON m.id=n.mod_id 
            WHERE n.user_id=$1 ORDER BY n.id DESC""",user_id)
    return [{"id":r["id"],"note":r["note"],"mod":r["mod_name"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.get("/api/mod/dashboard")
async def mod_dashboard(token:str):
    user=await get_current_user(token)
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        reports=await conn.fetchval("SELECT COUNT(*) FROM reports WHERE status='pending'")
        mutes=await conn.fetchval("SELECT COUNT(*) FROM users WHERE mute_until>NOW()")
        bans=await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned=TRUE")
        spam=await conn.fetchval("SELECT COUNT(*) FROM spam_alerts WHERE created_at>NOW()-INTERVAL '24 hours'")
    return {"reports":reports,"mutes":mutes,"bans":bans,"spam":spam}

@app.post("/api/mod/mute_ip")
async def mod_mute_ip(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    uid=int(data.get("user_id",0))
    minutes=int(data.get("minutes",1440))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",minutes*60,uid)
    return {"ok":True}

@app.get("/api/mod/reports")
async def mod_reports(token:str):
    user=await get_current_user(token)
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT r.id,r.text,r.target_user,f.username AS from_username,t.username AS target_username FROM reports r LEFT JOIN users f ON f.id=r.from_user LEFT JOIN users t ON t.id=r.target_user WHERE r.status='pending' ORDER BY r.id DESC")
    return [dict(r) for r in rows]

@app.post("/api/mod/mute")
async def mod_mute(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        m=int(data.get("minutes",60))
        await conn.execute("UPDATE users SET mute_until=NOW()+INTERVAL '1 second' * $1 WHERE id=$2",m*60,int(data.get("user_id",0)))
    return {"ok":True}

@app.post("/api/mod/dismiss_report")
async def mod_dismiss(data:dict):
    user=await get_current_user(data.get("token"))
    if not user or not (user.get("is_moderator") or user.get("is_admin") or user["username"]==ADMIN_USERNAME): raise HTTPException(403,"Нет прав")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE reports SET status='dismissed' WHERE id=$1",int(data.get("report_id",0)))
    return {"ok":True}

@app.post("/api/reports/submit")
async def report_submit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    txt=(data.get("text") or "").strip()
    if not txt: raise HTTPException(400,"Опиши")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO reports(from_user,target_user,text) VALUES($1,$2,$3)",user["id"],data.get("target_id"),txt)
    await grant_achievement(user["id"],"reporter")
    return {"ok":True}

# ============ ТУРНИРЫ ============
@app.get("/api/tournaments/list")
async def tournaments_list():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM tournaments WHERE status IN ('open','active') ORDER BY id DESC LIMIT 50")
    return [{"id":r["id"],"game":r["game"],"entry_fee":r["entry_fee"],"prize_pool":r["prize_pool"],"status":r["status"]} for r in rows]

@app.post("/api/tournaments/join")
async def tournaments_join(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("tournament_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM tournaments WHERE id=$1 AND status='open'",tid)
        if not t: raise HTTPException(404,"Турнир закрыт")
        if (user.get("coins") or 0)<t["entry_fee"]: raise HTTPException(400,"Не хватает")
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",t["entry_fee"],user["id"])
        await conn.execute("UPDATE tournaments SET prize_pool=prize_pool+$1 WHERE id=$2",t["entry_fee"],tid)
    return {"ok":True}

@app.post("/api/tournaments/bet")
async def tournaments_bet(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("tournament_id",0))
    amount=int(data.get("amount",0))
    if amount<=0: raise HTTPException(400,"Сумма>0")
    if (user.get("coins") or 0)<amount: raise HTTPException(400,"Не хватает")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",amount,user["id"])
        await conn.execute("INSERT INTO tournament_bets(tournament_id,user_id,amount) VALUES($1,$2,$3)",tid,user["id"],amount)
    return {"ok":True}

# ============ BP АРХИВ / ОБМЕН / КОЛЛЕКЦИЯ ============
@app.get("/api/bp/archive")
async def bp_archive(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM bp_archive WHERE user_id=$1 ORDER BY id DESC LIMIT 30",user["id"])
    return [{"season_name":r["season_name"],"season_emoji":r["season_emoji"],"level":r["level"],"xp":r["xp"],"claimed_count":r["claimed_count"]} for r in rows]

@app.post("/api/bp/trade_reward")
async def bp_trade_reward(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    to_username=(data.get("to_username") or "").strip().lstrip("@")
    reward_id=int(data.get("reward_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",to_username)
        if not t: raise HTTPException(404,"Не найден")
    return {"ok":True}

@app.get("/api/collection")
async def collection_get(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        nfts=await conn.fetch("""SELECT ni.number,ns.name,ns.emoji,ns.rarity FROM nft_items ni 
            JOIN nft_series ns ON ns.id=ni.series_id WHERE ni.owner_id=$1""",user["id"])
        gifts=await conn.fetch("SELECT gift,COUNT(*) AS c FROM gifts WHERE to_user=$1 GROUP BY gift",user["id"])
        titles=await conn.fetch("""SELECT t.name,t.emoji FROM titles t 
            JOIN title_owned o ON o.title_id=t.id WHERE o.user_id=$1""",user["id"])
    rarity_count={}
    for n in nfts:
        r=n["rarity"] or "common"
        rarity_count[r]=rarity_count.get(r,0)+1
    return {"nfts":[dict(n) for n in nfts],"gifts":[{"id":g["gift"],"count":g["c"]} for g in gifts],"titles":[dict(t) for t in titles],"rarity_count":rarity_count,"total_nfts":len(nfts)}

@app.get("/api/season/missions")
async def season_missions(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        season=await conn.fetchrow("SELECT id,name,emoji,ends_at FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        if not season: return {"active":False}
        quests=await conn.fetch("SELECT id,name,description,xp_reward,action_type,target_count FROM bp_quests WHERE active=TRUE LIMIT 10")
    ends_in_days=None
    if season["ends_at"]:
        try: ends_in_days=max(0,int((season["ends_at"]-datetime.datetime.now(datetime.timezone.utc)).total_seconds()//86400))
        except: pass
    return {"active":True,"season":season["name"],"emoji":season["emoji"],"ends_in_days":ends_in_days,"missions":[dict(q) for q in quests]}

# ============ ADDITIONAL COIN REQUESTS / PROMO ============
@app.post("/api/coins/request")
async def coins_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO coin_requests(user_id,coins,price) VALUES($1,$2,$3)",user["id"],int(data.get("coins",0)),int(data.get("price",0)))
    return {"ok":True}

@app.get("/api/games/leaders")
async def games_leaders(game:str):
    if game not in GAME_LIST: raise HTTPException(400,"Неизвестная игра")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT u.username,MAX(gs.score) AS best FROM game_scores gs JOIN users u ON u.id=gs.user_id WHERE gs.game=$1 GROUP BY u.id,u.username ORDER BY best DESC LIMIT 20",game)
    return [{"username":r["username"],"score":r["best"]} for r in rows]

# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================
class ConnectionManager:
    def __init__(self): self.connections={}
    async def connect(self,uid,ws):
        await ws.accept()
        self.connections.setdefault(uid,[]).append(ws)
        online_users.add(uid)
    def disconnect(self,uid,ws):
        if uid in self.connections:
            try: self.connections[uid].remove(ws)
            except ValueError: pass
            if not self.connections[uid]:
                del self.connections[uid]
                online_users.discard(uid)
    async def send_to(self,uid,data):
        for ws in list(self.connections.get(uid,[])):
            try: await ws.send_json(data)
            except: self.disconnect(uid,ws)
    async def broadcast(self,data,exclude=None):
        for uid,conns in list(self.connections.items()):
            if exclude and uid==exclude: continue
            for ws in list(conns):
                try: await ws.send_json(data)
                except: self.disconnect(uid,ws)
    async def kick(self,uid):
        for ws in list(self.connections.get(uid,[])):
            try: await ws.close()
            except: pass
        self.connections.pop(uid,None)
        online_users.discard(uid)

manager=ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws:WebSocket,token:str):
    user=await get_current_user(token)
    if not user: await ws.close(); return
    if user.get("is_banned"): await ws.close(); return
    uid=user["id"]
    await manager.connect(uid,ws)
    try: await ws.send_json({"type":"online_list","users":list(online_users)})
    except: pass
    await manager.broadcast({"type":"user_online","user_id":uid},exclude=uid)
    try:
        while True:
            raw=await ws.receive_text()
            cleanup_trackers()
            try: data=json.loads(raw)
            except: continue
            t=data.get("type")
            if t=="ping":
                try: await ws.send_json({"type":"pong"})
                except: pass
                continue
            is_muted=False
            if user.get("mute_until"):
                try:
                    mu=user["mute_until"]
                    if mu and mu>datetime.datetime.now(datetime.timezone.utc): is_muted=True
                except: pass
            if t in ("message","dm","group_msg","sticker") and is_muted:
                await manager.send_to(uid,{"type":"muted","reason":"Ты в муте"})
                continue
            if t=="message":
                ch=data.get("channel_id");text=(data.get("text") or "")[:2000]
                furl=data.get("file_url");tid=data.get("temp_id");reply=data.get("reply_to")
                effect=data.get("effect","none")
                if not ch: continue
                if user.get("is_scam") and not has_scam_perm(user,"chat_send"):
                    await manager.send_to(uid,{"type":"muted","reason":"SCAM: сообщения запрещены"})
                    continue
                await check_spam(uid)
                await check_flood(uid,text)
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,reply_to,effect) VALUES($1,$2,$3,$4,$5,$6) RETURNING *",int(ch),uid,text,furl,reply,effect)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    mc=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                    await add_last_message_at(conn,channel_id=int(ch))
                if mc==1: await grant_achievement(uid,"first_msg")
                if mc==100: await grant_achievement(uid,"msg_100")
                if mc==1000: await grant_achievement(uid,"msg_1000")
                if mc==10000: await grant_achievement(uid,"msg_10000")
                await grant_quest_progress(uid,"send_10_msgs",1)
                await grant_xp(uid,1)
                await bp_add_progress(uid,"send_message",1)
                if mc%10==0: await grant_candy(uid,1,silent=True)
                payload={"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"reply_to":reply,"effect":effect,"created_at":msg["created_at"].isoformat(),"is_admin":user.get("is_admin"),"is_moderator":user.get("is_moderator"),"is_scam":user.get("is_scam"),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"title":user.get("title"),"role":get_role(user),"temp_id":tid}
                for m in members: await manager.send_to(m["user_id"],payload)
            elif t=="dm":
                to_id=int(data.get("to_user",0));text=(data.get("text") or "")[:2000]
                furl=data.get("file_url");tid=data.get("temp_id")
                if await is_blocked(uid,to_id): continue
                if user.get("is_scam") and to_id!=SUPPORT_BOT_ID:
                    p=await get_pool()
                    async with p.acquire() as conn:
                        has_history=await conn.fetchval("SELECT 1 FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1) LIMIT 1",uid,to_id)
                    if not has_history and not has_scam_perm(user,"dm_send"):
                        await manager.send_to(uid,{"type":"muted","reason":"SCAM: писать первым нельзя"})
                        continue
                    if has_history and not has_scam_perm(user,"dm_reply"):
                        await manager.send_to(uid,{"type":"muted","reason":"SCAM: отвечать нельзя"})
                        continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",uid,to_id,text,furl)
                await grant_quest_progress(uid,"send_5_dms",1)
                await grant_xp(uid,1)
                await bp_add_progress(uid,"send_dm",1)
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"title":user.get("title"),"temp_id":tid,"is_scam":user.get("is_scam")}
                await manager.send_to(to_id,payload)
                await manager.send_to(uid,payload)
            elif t=="group_msg":
                gid=int(data.get("group_id",0));text=(data.get("text") or "")[:2000]
                furl=data.get("file_url");tid=data.get("temp_id")
                if user.get("is_scam") and not has_scam_perm(user,"chat_send"):
                    await manager.send_to(uid,{"type":"muted","reason":"SCAM: сообщения запрещены"})
                    continue
                p=await get_pool()
                async with p.acquire() as conn:
                    m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
                    if not m: continue
                    msg=await conn.fetchrow("INSERT INTO group_messages(group_id,user_id,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",gid,uid,text,furl)
                    members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                    await add_last_message_at(conn,group_id=gid)
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"is_premium":is_premium(user),"active_frame":user.get("active_frame"),"title":user.get("title"),"temp_id":tid,"is_scam":user.get("is_scam")}
                for m in members: await manager.send_to(m["user_id"],payload)
            elif t=="typing":
                ch=data.get("channel_id")
                p=await get_pool()
                async with p.acquire() as conn:
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                for m in members:
                    if m["user_id"]!=uid: await manager.send_to(m["user_id"],{"type":"typing","channel_id":ch,"username":user["username"]})
            elif t=="typing_dm":
                await manager.send_to(int(data.get("to_user",0)),{"type":"typing_dm","from":uid,"username":user["username"]})
            elif t=="call_offer":
                if user.get("is_scam") and not has_scam_perm(user,"call"): continue
                await manager.send_to(int(data.get("to",0)),{"type":"call_offer","from":uid,"sdp":data.get("sdp"),"username":user["username"],"avatar":user.get("avatar")})
            elif t=="call_answer":
                await manager.send_to(int(data.get("to",0)),{"type":"call_answer","from":uid,"sdp":data.get("sdp")})
            elif t=="call_ice":
                await manager.send_to(int(data.get("to",0)),{"type":"call_ice","from":uid,"candidate":data.get("candidate")})
            elif t=="call_decline":
                await manager.send_to(int(data.get("to",0)),{"type":"call_decline","from":uid})
            elif t=="call_end":
                await manager.send_to(int(data.get("to",0)),{"type":"call_end","from":uid})
    except WebSocketDisconnect: pass
    except Exception as e: print(f"WS error: {e}")
    finally:
        manager.disconnect(uid,ws)
        try:
            p=await get_pool()
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET last_seen=NOW() WHERE id=$1",uid)
        except: pass
        await manager.broadcast({"type":"user_offline","user_id":uid})

# ============================================================================
# MAIN
# ============================================================================
if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")