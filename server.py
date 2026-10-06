# BELUGACORD BETA 2.8 — server.py
# Часть 1/3: ядро, БД, helpers, BP пресеты, праздники, auth
import os,json,time,secrets,hashlib,random,datetime,asyncio,re
from typing import Optional
import asyncpg
import httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect,HTTPException,UploadFile,File,Form,Request
from fastapi.responses import HTMLResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ==== КОНФИГ ====
DATABASE_URL=os.environ.get("DATABASE_URL","")
UPLOAD_DIR="uploads"
os.makedirs(UPLOAD_DIR,exist_ok=True)
SECRET_KEY=os.environ.get("SECRET_KEY","belugacord_secret_2028")
RESEND_API_KEY=os.environ.get("RESEND_API_KEY","")
ADMIN_USERNAME="_fan_beluga_"
OWNER_PASSWORD="12344321"
CURRENT_VERSION="2.8"
SUPPORT_BOT_ID=0
SUPPORT_BOT_NAME="support_bot"
SUPPORT_BOT_DISPLAY="🤖 Support Bot"

ALLOWED_EXT={'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mov','.mp3','.wav','.ogg','.m4a','.pdf','.txt','.zip','.json'}
ALLOWED_MIME={'image/png','image/jpeg','image/gif','image/webp','image/svg+xml','video/mp4','video/webm','video/quicktime','audio/mpeg','audio/wav','audio/ogg','audio/mp4','audio/webm','application/pdf','text/plain','application/zip','application/json','application/octet-stream'}

LIMITS={None:{"file":10*1024*1024,"msg":2000,"servers":10,"channels":20,"groups":10},"premium":{"file":50*1024*1024,"msg":4000,"servers":50,"channels":100,"groups":30},"pro":{"file":200*1024*1024,"msg":10000,"servers":999,"channels":999,"groups":30}}
PREMIUM_PRICES={"month":1500,"year":18000}

# ==== ПОДАРКИ ====
DEFAULT_GIFTS={
    # Базовые
    "rose":{"name":"Роза","emoji":"🌹","price":15},
    "bear":{"name":"Мишка","emoji":"🧸","price":25},
    "cake":{"name":"Торт","emoji":"🎂","price":50},
    "diamond":{"name":"Алмаз","emoji":"💎","price":100},
    "crown":{"name":"Корона","emoji":"👑","price":500},
    "dragon":{"name":"Дракон","emoji":"🐉","price":1000},
    "legend":{"name":"Легендарка","emoji":"💠","price":5000},
    # Хэллоуин
    "pumpkin":{"name":"Тыква","emoji":"🎃","price":150},
    "ghost":{"name":"Призрак","emoji":"👻","price":250},
    "skull":{"name":"Череп","emoji":"💀","price":400},
    "bat":{"name":"Летучая мышь","emoji":"🦇","price":300},
    "witch":{"name":"Ведьма","emoji":"🧙","price":800},
    "vampire":{"name":"Вампир","emoji":"🧛","price":900},
    "spider":{"name":"Паук","emoji":"🕷️","price":200},
    # Новый год
    "tree":{"name":"Ёлка","emoji":"🎄","price":200},
    "santa":{"name":"Дед Мороз","emoji":"🎅","price":400},
    "snowman":{"name":"Снеговик","emoji":"⛄","price":150},
    "snowflake":{"name":"Снежинка","emoji":"❄️","price":100},
    "bell":{"name":"Колокольчик","emoji":"🔔","price":120},
    "giftbox":{"name":"Подарок","emoji":"🎁","price":250},
    "champagne":{"name":"Шампанское","emoji":"🍾","price":500},
    # Валентинки
    "heart":{"name":"Сердце","emoji":"❤️","price":50},
    "hearts":{"name":"Сердечки","emoji":"💕","price":100},
    "bouquet":{"name":"Букет","emoji":"💐","price":200},
    "chocolate":{"name":"Шоколад","emoji":"🍫","price":150},
    "kiss":{"name":"Поцелуй","emoji":"💋","price":300},
    "love_letter":{"name":"Love Letter","emoji":"💌","price":400},
    # Учёба
    "book":{"name":"Книга","emoji":"📚","price":150},
    "pencil":{"name":"Карандаш","emoji":"✏️","price":50},
    "apple":{"name":"Яблоко","emoji":"🍎","price":80},
    "graduation":{"name":"Диплом","emoji":"🎓","price":500},
    "backpack":{"name":"Рюкзак","emoji":"🎒","price":200},
    # Флаги
    "russia_flag":{"name":"Флаг России","emoji":"🇷🇺","price":300},
    "usa_flag":{"name":"Флаг США","emoji":"🇺🇸","price":300},
    "eagle":{"name":"Орёл","emoji":"🦅","price":400},
    "statue":{"name":"Статуя Свободы","emoji":"🗽","price":800},
    # Пасха
    "easter_egg":{"name":"Пасхальное яйцо","emoji":"🥚","price":150},
    "bunny":{"name":"Кролик","emoji":"🐰","price":250},
    "chick":{"name":"Цыплёнок","emoji":"🐣","price":180},
    "tulip":{"name":"Тюльпан","emoji":"🌷","price":120},
    # Легендарные
    "alien":{"name":"Инопланетянин","emoji":"👽","price":10000},
    "galaxy":{"name":"Галактика","emoji":"🌌","price":100000},
    "goldcat":{"name":"Золотой Белуга","emoji":"🐱","price":1000000},
    "universe":{"name":"Мультивселенная","emoji":"💫","price":1000000000},
}

GAME_LIST=["penguin","minesweeper","snake","2048","flappy","tetris","memory","reaction","tictactoe","rps","battleship","duel","freedoom","teacher_quiz"]

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
    "flappy_50":{"name":"Летун","emoji":"🐦","desc":"50 очков"},
    "first_server":{"name":"Основатель","emoji":"🏠","desc":"Создай сервер"},
    "coins_10k":{"name":"Богач","emoji":"💰","desc":"10000 бекоинов"},
    "rating_100":{"name":"Щедрая душа","emoji":"💎","desc":"Рейтинг 100"},
    "rating_10000":{"name":"Меценат","emoji":"👑","desc":"Рейтинг 10000"},
    "halloween_10":{"name":"Тыква-новичок","emoji":"🎃","desc":"10 конфет"},
    "halloween_100":{"name":"Тыквенный лорд","emoji":"🎃","desc":"100 конфет"},
    "halloween_500":{"name":"Владыка Хэллоуина","emoji":"👻","desc":"500 конфет"},
    "teacher_quiz_all":{"name":"Отличник","emoji":"🎓","desc":"Пройди викторину"},
    "teacher_perfect":{"name":"Учитель года","emoji":"📚","desc":"Без ошибок"},
}

# ==== ПРАЗДНИКИ ====
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
    ("09-01","knowledge_day","День знаний","📚","#8b5cf6","ru"),
    ("10-01","teachers_day","День учителя","🍎","#f59e0b","world"),
    ("10-31","halloween","Хэллоуин","🎃","#ff6b1a","world"),
    ("11-04","unity_day","День народного единства","🤝","#dc2626","ru"),
    ("11-24","thanksgiving","День благодарения","🦃","#92400e","us"),
    ("12-25","christmas_catholic","Католическое Рождество","🎅","#dc2626","world"),
    ("03-20","spring_day","Первый день весны","🌸","#f472b6","world"),
    ("06-21","summer_solstice","Летнее солнцестояние","☀️","#fbbf24","world"),
    ("09-22","autumn_day","Первый день осени","🍂","#d97706","world"),
    ("12-21","winter_solstice","Зимнее солнцестояние","❄️","#22d3ee","world"),
]

# ==== КОНФЕТНЫЕ ВАЛЮТЫ ====
DEFAULT_CANDY_CURRENCIES={
    "halloween":{"name":"Конфеты","emoji":"🍬"},
    "newyear":{"name":"Ёлочные шарики","emoji":"🎄"},
    "easter":{"name":"Яйца","emoji":"🥚"},
    "valentine":{"name":"Сердечки","emoji":"❤️"},
    "teacher":{"name":"Яблоки","emoji":"🍎"},
}

# ==== КОНФЕТНЫЙ МАГАЗИН ====
DEFAULT_CANDY_SHOP=[
    {"id":"ghost_frame","emoji":"👻","name":"Рамка Призрак","price":50,"kind":"frame","item":"ghost"},
    {"id":"pumpkin_frame","emoji":"🎃","name":"Рамка Тыква","price":80,"kind":"frame","item":"pumpkin"},
    {"id":"vampire_title","emoji":"🧛","name":"Титул Вампир","price":200,"kind":"title","item":"🧛 Вампир"},
    {"id":"candy_gift","emoji":"🍬","name":"5× Торт","price":30,"kind":"gift","item":"cake","count":5},
    {"id":"premium_1d","emoji":"💎","name":"Premium 1 день","price":500,"kind":"premium","value":1},
    {"id":"coins_1000","emoji":"💰","name":"1000 бекоинов","price":150,"kind":"coins","value":1000},
    {"id":"xp_boost","emoji":"⭐","name":"1000 XP","price":100,"kind":"xp","value":1000},
]

# ==== ВИКТОРИНА ====
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
    {"q":"Какое животное — символ мудрости?","a":["Сова","Лев","Тигр"],"correct":0},
    {"q":"Формула воды?","a":["H2O","CO2","O2"],"correct":0},
    {"q":"Кто автор «Гарри Поттера»?","a":["Дж. Роулинг","Толкин","Льюис"],"correct":0},
    {"q":"Сколько сторон у ромба?","a":["3","4","5"],"correct":1},
    {"q":"Планета, ближайшая к Солнцу?","a":["Венера","Меркурий","Земля"],"correct":1},
    {"q":"Кто написал «Преступление и наказание»?","a":["Толстой","Достоевский","Тургенев"],"correct":1},
    {"q":"Сколько дней в високосном году?","a":["365","366","367"],"correct":1},
    {"q":"Столица Японии?","a":["Сеул","Токио","Пекин"],"correct":1},
]

# ==== BP ПРЕСЕТЫ ====
BP_PRESETS={
"halloween":{
  "name":"Жуткий месяц","description":"Хэллоуин · октябрь","emoji":"🎃","days_total":30,"max_level":50,
  "quests":[
    {"name":"Напиши 10 сообщений","action_type":"send_message","target_count":10,"xp_reward":100},
    {"name":"Сыграй 1 игру","action_type":"play_game","target_count":1,"xp_reward":100},
    {"name":"Отправь 1 DM","action_type":"send_dm","target_count":1,"xp_reward":100},
    {"name":"Поставь 5 реакций","action_type":"react","target_count":5,"xp_reward":150},
    {"name":"Добавь 1 друга","action_type":"add_friend","target_count":1,"xp_reward":300},
    {"name":"Подари подарок","action_type":"give_gift","target_count":1,"xp_reward":500},
    {"name":"Напиши 50 сообщений","action_type":"send_message","target_count":50,"xp_reward":1000},
    {"name":"Сыграй 10 игр","action_type":"play_game","target_count":10,"xp_reward":1500},
    {"name":"Подари 3 подарка","action_type":"give_gift","target_count":3,"xp_reward":2000},
    {"name":"Открой 3 кейса","action_type":"open_case","target_count":3,"xp_reward":2000},
    {"name":"Добавь 5 друзей","action_type":"add_friend","target_count":5,"xp_reward":2500},
    {"name":"Зайди 7 дней подряд","action_type":"daily_streak","target_count":7,"xp_reward":3000},
    {"name":"Победи в 5 дуэлях","action_type":"win_duel","target_count":5,"xp_reward":3000},
    {"name":"Собери 50 конфет","action_type":"collect_candy","target_count":50,"xp_reward":3000},
    {"name":"Напиши 500 сообщений","action_type":"send_message","target_count":500,"xp_reward":10000},
    {"name":"Сыграй 50 игр","action_type":"play_game","target_count":50,"xp_reward":12000},
    {"name":"Подари 20 подарков","action_type":"give_gift","target_count":20,"xp_reward":15000},
    {"name":"Открой 20 кейсов","action_type":"open_case","target_count":20,"xp_reward":20000},
    {"name":"Добавь 20 друзей","action_type":"add_friend","target_count":20,"xp_reward":25000},
    {"name":"Зайди 30 дней подряд","action_type":"daily_streak","target_count":30,"xp_reward":30000},
    {"name":"Достигни 25 уровня","action_type":"reach_level","target_count":25,"xp_reward":30000},
    {"name":"Собери 500 конфет","action_type":"collect_candy","target_count":500,"xp_reward":30000},
    {"name":"Победи в турнире","action_type":"win_tournament","target_count":1,"xp_reward":40000},
    {"name":"Напиши владельцу","action_type":"write_owner","target_count":1,"xp_reward":50000},
  ],
  "rewards":[
    {"level":1,"reward":"💰 100 бекоинов","reward_type":"coins","reward_value":100,"track":"free"},
    {"level":1,"reward":"💎 Premium 1д + 500 бекоинов","reward_type":"premium","reward_value":1,"track":"premium"},
    {"level":2,"reward":"🎨 Рамка «Тыква»","reward_type":"frame","reward_value":1,"reward_item_id":"pumpkin","track":"free"},
    {"level":3,"reward":"👑 Титул «Призрак»","reward_type":"title","reward_value":1,"reward_item_id":"👻 Призрак","track":"free"},
    {"level":3,"reward":"🎨 Рамка «Мышь» + 2000 бекоинов","reward_type":"frame","reward_value":1,"reward_item_id":"bat","track":"premium"},
    {"level":5,"reward":"🎟️ 100 КП","reward_type":"kp","reward_value":100,"track":"free"},
    {"level":5,"reward":"💎 Premium 7д + 🎨 Рамка «Призрак»","reward_type":"premium","reward_value":7,"track":"premium"},
    {"level":7,"reward":"💎 Премиум 3 дня","reward_type":"premium","reward_value":3,"track":"free"},
    {"level":8,"reward":"👑 Титул «Вампир»","reward_type":"title","reward_value":1,"reward_item_id":"🧛 Вампир","track":"free"},
    {"level":9,"reward":"🍬 50 конфет","reward_type":"candy","reward_value":50,"track":"free"},
    {"level":10,"reward":"💰 50000 бекоинов","reward_type":"coins","reward_value":50000,"track":"free"},
    {"level":10,"reward":"👑 Титул «Владыка тьмы»","reward_type":"title","reward_value":1,"reward_item_id":"💀 Владыка тьмы","track":"premium"},
  ]
},
"newyear":{
  "name":"Новогодний сезон","description":"❄️ Праздничный сезон","emoji":"🎄","days_total":30,"max_level":50,
  "quests":[
    {"name":"Напиши 10 сообщений","action_type":"send_message","target_count":10,"xp_reward":100},
    {"name":"Сыграй 3 игры","action_type":"play_game","target_count":3,"xp_reward":300},
    {"name":"Подари 1 подарок","action_type":"give_gift","target_count":1,"xp_reward":500},
    {"name":"Напиши 100 сообщений","action_type":"send_message","target_count":100,"xp_reward":2000},
    {"name":"Открой 5 кейсов","action_type":"open_case","target_count":5,"xp_reward":3000},
    {"name":"Зайди 7 дней подряд","action_type":"daily_streak","target_count":7,"xp_reward":3000},
    {"name":"Напиши 500 сообщений","action_type":"send_message","target_count":500,"xp_reward":10000},
  ],
  "rewards":[
    {"level":1,"reward":"💰 200 бекоинов","reward_type":"coins","reward_value":200,"track":"free"},
    {"level":2,"reward":"🎨 Рамка «Снежинка»","reward_type":"frame","reward_value":1,"reward_item_id":"ice","track":"free"},
    {"level":3,"reward":"👑 Титул «Снеговик»","reward_type":"title","reward_value":1,"reward_item_id":"⛄ Снеговик","track":"free"},
    {"level":5,"reward":"💎 Premium 7 дней","reward_type":"premium","reward_value":7,"track":"free"},
    {"level":10,"reward":"🎄 30 шариков","reward_type":"candy","reward_value":30,"track":"free"},
  ]
},
"easter":{
  "name":"Пасхальный сезон","description":"🥚 Весна","emoji":"🐣","days_total":30,"max_level":40,
  "quests":[
    {"name":"Напиши 20 сообщений","action_type":"send_message","target_count":20,"xp_reward":200},
    {"name":"Сыграй 5 игр","action_type":"play_game","target_count":5,"xp_reward":500},
    {"name":"Собери 10 яиц","action_type":"collect_candy","target_count":10,"xp_reward":300},
    {"name":"Напиши 200 сообщений","action_type":"send_message","target_count":200,"xp_reward":3000},
    {"name":"Собери 50 яиц","action_type":"collect_candy","target_count":50,"xp_reward":3000},
  ],
  "rewards":[
    {"level":1,"reward":"💰 100 бекоинов","reward_type":"coins","reward_value":100,"track":"free"},
    {"level":3,"reward":"🐰 Титул «Кролик»","reward_type":"title","reward_value":1,"reward_item_id":"🐰 Кролик","track":"free"},
    {"level":5,"reward":"💎 Premium 3 дня","reward_type":"premium","reward_value":3,"track":"free"},
    {"level":10,"reward":"🥚 100 яиц","reward_type":"candy","reward_value":100,"track":"free"},
  ]
},
"teacher":{
  "name":"День учителя","description":"📚 Праздник знаний","emoji":"🍎","days_total":30,"max_level":40,
  "quests":[
    {"name":"Напиши 10 сообщений","action_type":"send_message","target_count":10,"xp_reward":100},
    {"name":"Ответь на 1 вопрос викторины","action_type":"play_game","target_count":1,"xp_reward":200},
    {"name":"Собери 20 яблок","action_type":"collect_candy","target_count":20,"xp_reward":500},
    {"name":"Напиши 100 сообщений","action_type":"send_message","target_count":100,"xp_reward":2000},
    {"name":"Пройди викторину полностью","action_type":"win_tournament","target_count":1,"xp_reward":15000},
  ],
  "rewards":[
    {"level":1,"reward":"💰 150 бекоинов","reward_type":"coins","reward_value":150,"track":"free"},
    {"level":3,"reward":"📚 30 яблок","reward_type":"candy","reward_value":30,"track":"free"},
    {"level":5,"reward":"🎓 Рамка «Учитель года»","reward_type":"frame","reward_value":1,"reward_item_id":"teacher","track":"free"},
    {"level":10,"reward":"🎓 Титул «Учитель года»","reward_type":"title","reward_value":1,"reward_item_id":"🎓 Учитель года","track":"free"},
  ]
},
}

# ==== ПРАВА SCAM-ЮЗЕРА ====
SCAM_DEFAULT_PERMS={
    "dm_send":False,
    "dm_reply":True,
    "gift_send":False,
    "gift_receive":True,
    "chat_send":True,
    "chat_create":False,
    "set_avatar":False,
    "set_banner":False,
    "open_cases":False,
    "buy_nft":False,
    "transfer_coins":False,
    "join_bp":False,
    "play_games":True,
    "call":False,
    "add_friends":False,
    "post_story":False,
}

# ============ UTILS ============
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

# ============ APP ============
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
active_tournament={"game":None,"started_at":None}
spam_tracker={}
friend_spam_tracker={}
flood_tracker={}
last_cleanup=time.time()
active_events=[]
upgrade_chance_bonus={}
custom_commands={}
forced_holiday=None
teacher_quiz_enabled=True
teacher_quiz_questions=DEFAULT_TEACHER_QUIZ[:]
candy_currency="halloween"
candy_shop=DEFAULT_CANDY_SHOP[:]

async def get_pool():
    global pool
    if pool is None: pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=5)
    return pool

# ============ БД INIT ============
async def init_db():
    p=await get_pool()
    async with p.acquire() as conn:
        # ===== USERS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            avatar TEXT,banner TEXT,gif_avatar TEXT,gif_banner TEXT,
            avatar_pos TEXT DEFAULT '50% 50%',
            banner_pos TEXT DEFAULT '50% 50%',
            email VARCHAR(128),email_verified BOOLEAN DEFAULT FALSE,
            email_code VARCHAR(16),email_code_expires TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            is_moderator BOOLEAN DEFAULT FALSE,
            is_beta_tester BOOLEAN DEFAULT FALSE,
            is_scam BOOLEAN DEFAULT FALSE,
            is_dev BOOLEAN DEFAULT FALSE,
            is_streamer BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            premium_tier VARCHAR(8),premium_expires TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,
            ban_reason VARCHAR(256),
            mute_until TIMESTAMP,
            nickname_color VARCHAR(32),nickname_gradient VARCHAR(128),
            custom_status VARCHAR(128),
            online_status VARCHAR(16) DEFAULT 'online',
            bio VARCHAR(256),fav_music VARCHAR(128),
            admin_password VARCHAR(128),
            coins INTEGER DEFAULT 0,
            social_rating INTEGER DEFAULT 0,
            messages_count INTEGER DEFAULT 0,
            is_legend BOOLEAN DEFAULT FALSE,
            achievements TEXT DEFAULT '[]',
            quest_points INTEGER DEFAULT 0,
            daily_bonus_at TIMESTAMP,
            active_frame VARCHAR(32),
            frame_owned TEXT DEFAULT '[]',
            title VARCHAR(64),
            title_owned TEXT DEFAULT '[]',
            reputation INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            chest_streak INTEGER DEFAULT 0,
            chest_at TIMESTAMP,
            bank_deposit INTEGER DEFAULT 0,
            bank_at TIMESTAMP,
            candy INTEGER DEFAULT 0,
            scam_perms TEXT DEFAULT '{}',
            last_seen TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        for col,typ in [("candy","INTEGER DEFAULT 0"),("scam_perms","TEXT DEFAULT '{}'"),("is_verified","BOOLEAN DEFAULT FALSE"),("title_owned","TEXT DEFAULT '[]'")]:
            try: await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
            except: pass
        await conn.execute("UPDATE users SET is_admin=TRUE WHERE username=$1",ADMIN_USERNAME)
        # Support bot
        bot_exists=await conn.fetchval("SELECT 1 FROM users WHERE id=$1",SUPPORT_BOT_ID)
        if not bot_exists:
            try:
                await conn.execute("""INSERT INTO users(id,username,password_hash,is_admin,is_dev,bio,custom_status)
                    VALUES($1,$2,$3,FALSE,TRUE,$4,$5)""",SUPPORT_BOT_ID,SUPPORT_BOT_NAME,hash_password("bot_"+SECRET_KEY),"🤖 Служба поддержки","🛡️ Здесь можно подать заявку")
                await conn.execute("SELECT setval(pg_get_serial_sequence('users','id'),GREATEST((SELECT MAX(id) FROM users),1))")
            except Exception as e: print(f"Bot create: {e}")
        
        # ===== CORE =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS servers(id SERIAL PRIMARY KEY,name VARCHAR(64),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,invite_code VARCHAR(16) UNIQUE,avatar TEXT,description TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS server_members(server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(server_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS channels(id SERIAL PRIMARY KEY,server_id INTEGER REFERENCES servers(id) ON DELETE CASCADE,name VARCHAR(64),type VARCHAR(16) DEFAULT 'text',mode VARCHAR(16) DEFAULT 'public',last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS messages(id SERIAL PRIMARY KEY,channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,reply_to INTEGER,reactions TEXT DEFAULT '{}',pinned BOOLEAN DEFAULT FALSE,edited BOOLEAN DEFAULT FALSE,effect VARCHAR(16) DEFAULT 'none',created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friendships(id SERIAL PRIMARY KEY,user_a INTEGER REFERENCES users(id) ON DELETE CASCADE,user_b INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(user_a,user_b))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS friend_requests(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS blocks(id SERIAL PRIMARY KEY,blocker INTEGER REFERENCES users(id) ON DELETE CASCADE,blocked INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW(),UNIQUE(blocker,blocked))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS groups(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,avatar TEXT,description VARCHAR(256),owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,last_message_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_members(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,joined_at TIMESTAMP DEFAULT NOW(),PRIMARY KEY(group_id,user_id))""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS group_messages(id SERIAL PRIMARY KEY,group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS dms(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,file_url TEXT,read_at TIMESTAMP,created_at TIMESTAMP DEFAULT NOW())""")
        
        # ===== ADMIN =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS admin_logs(id SERIAL PRIMARY KEY,admin_id INTEGER REFERENCES users(id) ON DELETE SET NULL,action VARCHAR(64),target_id INTEGER,details TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS reports(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,target_user INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        
        # ===== SUPPORT TICKETS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS support_tickets(
            id SERIAL PRIMARY KEY,
            from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,
            ticket_type VARCHAR(32),
            target_user INTEGER REFERENCES users(id) ON DELETE SET NULL,
            title VARCHAR(128),
            description TEXT,
            evidence TEXT,
            status VARCHAR(16) DEFAULT 'pending',
            admin_reply TEXT,
            resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            resolved_at TIMESTAMP
        )""")
        
        # ===== ПОДАРКИ / NFT / КЕЙСЫ =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS gifts(id SERIAL PRIMARY KEY,from_user INTEGER REFERENCES users(id) ON DELETE CASCADE,to_user INTEGER REFERENCES users(id) ON DELETE CASCADE,gift VARCHAR(32) NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS custom_gifts(gift_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_sticker BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_series(id SERIAL PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),image TEXT,total INTEGER NOT NULL,sold INTEGER DEFAULT 0,price INTEGER NOT NULL,rarity VARCHAR(16) DEFAULT 'common',created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS nft_items(id SERIAL PRIMARY KEY,series_id INTEGER REFERENCES nft_series(id) ON DELETE CASCADE,number INTEGER NOT NULL,owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS cases(id SERIAL PRIMARY KEY,name VARCHAR(64) NOT NULL,emoji VARCHAR(8),image TEXT,price INTEGER NOT NULL,is_active BOOLEAN DEFAULT TRUE,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS case_prizes(id SERIAL PRIMARY KEY,case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,kind VARCHAR(16) NOT NULL,item_id VARCHAR(64),item_name VARCHAR(64),item_emoji VARCHAR(8),chance INTEGER NOT NULL,coins_min INTEGER DEFAULT 0,coins_max INTEGER DEFAULT 0)""")
        
        # ===== РАМКИ =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS frames_catalog(frame_id VARCHAR(32) PRIMARY KEY,name VARCHAR(64),emoji VARCHAR(8),css TEXT,is_animated BOOLEAN DEFAULT FALSE,is_premium BOOLEAN DEFAULT FALSE,price_coins INTEGER DEFAULT 0,price_kp INTEGER DEFAULT 0,price_candy INTEGER DEFAULT 0)""")
        for f in [
            ("none","Без рамки","","none",False,False,0,0,0),
            ("gold","Золотая","👑","2px solid #ffd700;box-shadow:0 0 12px rgba(255,215,0,0.7)",False,False,500,0,0),
            ("fire","Огненная","🔥","2px solid #ff6b35;box-shadow:0 0 14px rgba(255,107,53,0.8)",False,False,800,0,0),
            ("ice","Ледяная","❄️","2px solid #22d3ee;box-shadow:0 0 14px rgba(34,211,238,0.8)",False,False,800,0,0),
            ("rainbow","Радужная","🌈","2px solid #d946ef;box-shadow:0 0 16px rgba(217,70,239,0.8)",False,True,0,3000,0),
            ("pumpkin","Тыква","🎃","2px solid #ff6b1a;box-shadow:0 0 20px rgba(255,107,26,0.9)",False,False,0,2000,80),
            ("ghost","Призрак","👻","2px solid #a855f7;box-shadow:0 0 20px rgba(168,85,247,0.9)",False,False,0,2500,100),
            ("teacher","Учитель года","🎓","3px solid #f59e0b;box-shadow:0 0 24px rgba(245,158,11,1)",False,False,0,0,300),
        ]:
            try: await conn.execute("INSERT INTO frames_catalog(frame_id,name,emoji,css,is_animated,is_premium,price_coins,price_kp,price_candy) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (frame_id) DO NOTHING",*f)
            except: pass
        
        # ===== ТИТУЛЫ =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS titles_catalog(
            id SERIAL PRIMARY KEY,
            name VARCHAR(64) NOT NULL,
            emoji VARCHAR(8),
            color VARCHAR(32),
            is_public BOOLEAN DEFAULT TRUE,
            condition_type VARCHAR(32),
            condition_value INTEGER,
            creator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        # seed базовых
        cnt=await conn.fetchval("SELECT COUNT(*) FROM titles_catalog")
        if cnt==0:
            for t in [
                ("👻 Призрак","👻","#a855f7",True,"free",0),
                ("🧛 Вампир","🧛","#dc2626",True,"level",10),
                ("🧙 Ведьма","🧙","#ec4899",True,"level",20),
                ("💀 Владыка тьмы","💀","#8b5cf6",True,"level",50),
                ("🎓 Учитель года","🎓","#f59e0b",True,"custom",0),
                ("🏅 Легенда","🏅","#ffd700",True,"messages",1000),
            ]:
                await conn.execute("INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value) VALUES($1,$2,$3,$4,$5,$6)",*t)
        
        # ===== STORIES / COINS =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS stories(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,image TEXT,text TEXT,bg_color VARCHAR(16) DEFAULT '#000',created_at TIMESTAMP DEFAULT NOW(),expires_at TIMESTAMP DEFAULT NOW()+INTERVAL '24 hours')""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS coin_requests(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,coins INTEGER NOT NULL,status VARCHAR(16) DEFAULT 'pending',created_at TIMESTAMP DEFAULT NOW())""")
        
        # ===== BP =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_quests(id SERIAL PRIMARY KEY,name VARCHAR(128),description TEXT,goal INTEGER,xp_reward INTEGER DEFAULT 100,action_type VARCHAR(32),target_count INTEGER DEFAULT 1,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_rewards(id SERIAL PRIMARY KEY,level INTEGER,reward TEXT,reward_type VARCHAR(32),reward_value INTEGER DEFAULT 0,reward_item_id VARCHAR(64),track VARCHAR(16) DEFAULT 'free',active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_season(id SERIAL PRIMARY KEY,name VARCHAR(64),description TEXT,emoji VARCHAR(8) DEFAULT '🏆',started_at TIMESTAMP DEFAULT NOW(),ended_at TIMESTAMP,ends_at TIMESTAMP,days_total INTEGER DEFAULT 30,max_level INTEGER DEFAULT 50,xp_per_level INTEGER DEFAULT 1000,active BOOLEAN DEFAULT TRUE)""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS bp_progress(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,season_id INTEGER,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,claimed TEXT DEFAULT '[]',has_premium_pass BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW())""")
        
        # seed BP
        bp_row=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE LIMIT 1")
        if not bp_row:
            preset=BP_PRESETS["halloween"]
            now=datetime.datetime.now(datetime.timezone.utc)
            ends=now+datetime.timedelta(days=preset["days_total"])
            await conn.execute("INSERT INTO bp_season(name,description,emoji,days_total,max_level,ends_at,active,xp_per_level) VALUES($1,$2,$3,$4,$5,$6,TRUE,1000)",preset["name"],preset["description"],preset["emoji"],preset["days_total"],preset["max_level"],ends)
            for q in preset["quests"]:
                await conn.execute("INSERT INTO bp_quests(name,description,goal,xp_reward,action_type,target_count) VALUES($1,'',$2,$3,$4,$2)",q["name"],q["target_count"],q["xp_reward"],q["action_type"])
            for r in preset["rewards"]:
                await conn.execute("INSERT INTO bp_rewards(level,reward,reward_type,reward_value,reward_item_id,track) VALUES($1,$2,$3,$4,$5,$6)",r["level"],r["reward"],r["reward_type"],r["reward_value"],r.get("reward_item_id"),r.get("track","free"))
            print(f"🎃 Автостарт БП: {preset['name']}")
        
        # ===== CANDY =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS candy_shop_items(
            id VARCHAR(64) PRIMARY KEY,
            emoji VARCHAR(8),
            name VARCHAR(128),
            price INTEGER NOT NULL,
            kind VARCHAR(16) NOT NULL,
            item VARCHAR(64),
            value INTEGER DEFAULT 0,
            count INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS candy_currency(
            key VARCHAR(32) PRIMARY KEY,
            name VARCHAR(64),
            emoji VARCHAR(8),
            is_active BOOLEAN DEFAULT FALSE
        )""")
        for k,v in DEFAULT_CANDY_CURRENCIES.items():
            try: await conn.execute("INSERT INTO candy_currency(key,name,emoji,is_active) VALUES($1,$2,$3,$4) ON CONFLICT (key) DO NOTHING",k,v["name"],v["emoji"],k=="halloween")
            except: pass
        cnt=await conn.fetchval("SELECT COUNT(*) FROM candy_shop_items")
        if cnt==0:
            for it in DEFAULT_CANDY_SHOP:
                await conn.execute("""INSERT INTO candy_shop_items(id,emoji,name,price,kind,item,value,count)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING""",it["id"],it["emoji"],it["name"],it["price"],it["kind"],it.get("item"),it.get("value",0),it.get("count",1))
        
        # ===== ВИКТОРИНА =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS teacher_quiz(
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answers TEXT NOT NULL,
            correct INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        cnt=await conn.fetchval("SELECT COUNT(*) FROM teacher_quiz")
        if cnt==0:
            for q in DEFAULT_TEACHER_QUIZ:
                await conn.execute("INSERT INTO teacher_quiz(question,answers,correct) VALUES($1,$2,$3)",q["q"],json.dumps(q["a"],ensure_ascii=False),q["correct"])
        
        # ===== SYSTEM =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS system_settings(key VARCHAR(64) PRIMARY KEY,value TEXT,updated_at TIMESTAMP DEFAULT NOW())""")
        for k,v in [("candy_currency","halloween"),("teacher_quiz_enabled","1"),("forced_holiday","")]:
            try: await conn.execute("INSERT INTO system_settings(key,value) VALUES($1,$2) ON CONFLICT (key) DO NOTHING",k,v)
            except: pass
        
        # ===== ИГРЫ =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS game_scores(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,game VARCHAR(32) NOT NULL,score INTEGER NOT NULL,created_at TIMESTAMP DEFAULT NOW())""")
        
        # ===== СЧЁТЧИК =====
        await conn.execute("""CREATE TABLE IF NOT EXISTS user_saved_messages(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,text TEXT,created_at TIMESTAMP DEFAULT NOW())""")
        await conn.execute("""CREATE TABLE IF NOT EXISTS upgrade_log(id SERIAL PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,from_gift VARCHAR(32),to_gift VARCHAR(32),success BOOLEAN,chance REAL,created_at TIMESTAMP DEFAULT NOW())""")
        
        print("✅ БД инициализирована")

# ============ HELPERS ============
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

async def send_email(to_email,subject,html):
    if not RESEND_API_KEY: return {"ok":False,"error":"no_key"}
    try:
        async with httpx.AsyncClient() as client:
            r=await client.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {RESEND_API_KEY}","Content-Type":"application/json"},json={"from":"Belugacord <onboarding@resend.dev>","to":[to_email],"subject":subject,"html":html},timeout=15)
            if r.status_code in (200,201): return {"ok":True}
            return {"ok":False,"error":r.text}
    except Exception as e: return {"ok":False,"error":str(e)}

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
        "avatar":row.get("avatar"),"banner":row.get("banner"),
        "gif_avatar":row.get("gif_avatar"),"gif_banner":row.get("gif_banner"),
        "avatar_pos":row.get("avatar_pos") or "50% 50%","banner_pos":row.get("banner_pos") or "50% 50%",
        "is_admin":row.get("is_admin",False),"is_moderator":row.get("is_moderator",False),
        "is_beta_tester":row.get("is_beta_tester",False),
        "is_scam":row.get("is_scam",False),"scam_perms":scam_perms,
        "is_dev":row.get("is_dev",False),"is_streamer":row.get("is_streamer",False),
        "is_verified":row.get("is_verified",False),
        "premium_tier":row.get("premium_tier"),
        "premium_expires":row["premium_expires"].isoformat() if row.get("premium_expires") else None,
        "is_premium":is_premium(row),
        "nickname_color":row.get("nickname_color"),"nickname_gradient":row.get("nickname_gradient"),
        "custom_status":row.get("custom_status"),"online_status":status,
        "bio":row.get("bio"),"fav_music":row.get("fav_music"),
        "coins":row.get("coins",0),"social_rating":row.get("social_rating",0),
        "messages_count":row.get("messages_count",0),
        "achievements":json.loads(row.get("achievements") or "[]"),
        "quest_points":row.get("quest_points",0),
        "active_frame":row.get("active_frame"),
        "frame_owned":json.loads(row.get("frame_owned") or "[]"),
        "title":row.get("title"),
        "title_owned":json.loads(row.get("title_owned") or "[]"),
        "reputation":row.get("reputation",0),
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
            for r in rows: gifts[r["gift_id"]]={"name":r["name"],"emoji":r["emoji"],"image":r["image"],"price":r["price"]}
    except: pass
    return gifts

async def is_blocked(user_id,other_id):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT id FROM blocks WHERE (blocker=$1 AND blocked=$2) OR (blocker=$2 AND blocked=$1)",user_id,other_id)
            return bool(row)
    except: return False

async def grant_xp(uid,amount):
    try:
        p=await get_pool()
        async with p.acquire() as conn:
            row=await conn.fetchrow("SELECT xp,level FROM users WHERE id=$1",uid)
            if not row: return
            new_xp=row["xp"]+amount
            new_level=row["level"]
            while new_xp>=(new_level*100):
                new_xp-=new_level*100
                new_level+=1
                await manager.send_to(uid,{"type":"level_up","level":new_level})
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
        if not silent:
            await manager.send_to(uid,{"type":"candy_received","amount":amount,"total":total})
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
            prog=await conn.fetchrow("SELECT id,xp,level,has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_id=$2",uid,season["id"])
            if not prog:
                await conn.execute("INSERT INTO bp_progress(user_id,season_id,xp,level) VALUES($1,$2,0,1)",uid,season["id"])
                prog=await conn.fetchrow("SELECT id,xp,level,has_premium_pass FROM bp_progress WHERE user_id=$1 AND season_id=$2",uid,season["id"])
            new_xp=prog["xp"]+total_xp
            new_level=prog["level"]
            xp_per=season["xp_per_level"] or 1000
            max_lv=season["max_level"] or 50
            while new_xp>=xp_per and new_level<max_lv:
                new_xp-=xp_per
                new_level+=1
                await manager.send_to(uid,{"type":"bp_level_up","level":new_level})
            await conn.execute("UPDATE bp_progress SET xp=$1,level=$2 WHERE id=$3",new_xp,new_level,prog["id"])
    except Exception as e: print(f"bp progress: {e}")

# ============ BACKGROUND LOOPS ============
async def events_cleanup_loop():
    while True:
        try:
            await asyncio.sleep(30)
            p=await get_pool()
            async with p.acquire() as conn:
                bp_ended=await conn.fetch("SELECT id FROM bp_season WHERE active=TRUE AND ends_at IS NOT NULL AND ends_at<=NOW()")
                for r in bp_ended:
                    await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE id=$1",r["id"])
                    await manager.broadcast({"type":"bp_update","ended":True})
        except Exception as e:
            print(f"Events loop: {e}")
            await asyncio.sleep(60)

async def startup_tasks():
    asyncio.create_task(events_cleanup_loop())
    print("🎃 Background loops started (2.8)")

@app.on_event("startup")
async def startup():
    if DATABASE_URL:
        try:
            await init_db()
            await startup_tasks()
        except Exception as e:
            print(f"DB init: {e}")

# ============ CONNECTION MANAGER ============
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

# ============ AUTH ROUTES ============
@app.get("/api/changelog")
async def changelog():
    return {"current":CURRENT_VERSION,"all":{
        "2.8":{"title":"Belugacord Beta 2.8","items":[
            "🛠️ Фикс аватарок и баннеров",
            "🛠️ Фикс друзей (список, заявки, принятие)",
            "🎨 Конструктор титулов (создать свой)",
            "👑 Титулы: публичные/приватные",
            "🎯 Выдача титулов владельцем",
            "✅ Галочки «прочитано»",
            "📌 Избранное чаты",
            "📁 Архив чатов",
            "🔇 Мьют чатов",
            "💬 Отложенные сообщения",
            "🔍 Улучшенный поиск",
            "👑 Кастомные эмодзи-статусы",
            "⭐ Значок «проверенный»",
            "🎁 10 новых подарков",
            "🎨 5 новых рамок",
            "🎮 2 новые игры",
            "🐛 15+ фиксов",
        ]},
        "2.7":{"title":"Belugacord Beta 2.7","items":["🎨 @username","🤖 @support_bot","🚫 SCAM-система","📱 Мобильные табы","🏆 БП 2.0 Free+Premium","🎉 Праздничные темы","🍬 Конфетный магазин","🎓 Викторина","🎁 60+ подарков","🛡️ Расширенная админка"]},
        "2.6":{"title":"Belugacord Beta 2.6","items":["🎃 Хэллоуин","🍬 Конфеты","⬆️ Апгрейдер 2.0"]},
    }}

@app.get("/api/achievements/all")
async def achievements_all(): return ACHIEVEMENTS

@app.get("/api/check_username")
async def check_username(username:str):
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM users WHERE username=$1",sanitize_username(username))
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
    if em:
        code=str(random.randint(100000,999999))
        try:
            async with p.acquire() as conn:
                await conn.execute("UPDATE users SET email_code=$1,email_code_expires=NOW()+INTERVAL '1 hour' WHERE id=$2",code,row["id"])
            asyncio.create_task(send_email(em,"Belugacord — подтверждение",f"<h2>Привет, {uname}!</h2><p>Код: <b style='font-size:24px;color:#ff6b1a'>{code}</b></p>"))
        except: pass
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
# ============ EMAIL ============
@app.post("/api/email/send_code")
async def email_send_code(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    em=(data.get("email") or "").strip()
    if not em or "@" not in em or "." not in em: raise HTTPException(400,"Плохой email")
    code=str(random.randint(100000,999999))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET email=$1,email_code=$2,email_code_expires=NOW()+INTERVAL '1 hour',email_verified=FALSE WHERE id=$3",em,code,user["id"])
    r=await send_email(em,"Belugacord — подтверждение",f"<h2>Привет, {user['username']}!</h2><p>Код: <b style='font-size:24px;color:#ff6b1a'>{code}</b></p>")
    if r.get("ok"): return {"ok":True,"sent":True}
    return {"ok":True,"sent":False,"code_hint":code,"error":r.get("error","")}

@app.post("/api/email/verify")
async def email_verify(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    code=str(data.get("code") or "").strip()
    if not code: raise HTTPException(400,"Введи код")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT email_code,email_code_expires FROM users WHERE id=$1",user["id"])
        if not row: raise HTTPException(404,"Юзер не найден")
        if not row["email_code"]: raise HTTPException(400,"Сначала запроси код")
        exp=row["email_code_expires"]
        if exp:
            now_utc=datetime.datetime.now(datetime.timezone.utc)
            if exp.tzinfo is None:
                if exp < datetime.datetime.utcnow(): raise HTTPException(400,"Код истёк")
            else:
                if exp < now_utc: raise HTTPException(400,"Код истёк")
        if str(row["email_code"]).strip()!=code: raise HTTPException(400,"Неверный код")
        await conn.execute("UPDATE users SET email_verified=TRUE,email_code=NULL,email_code_expires=NULL WHERE id=$1",user["id"])
    return {"ok":True}

# ============ PROFILE ============
@app.post("/api/update_profile")
async def update_profile(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    premium=is_premium(user)
    gif_av=data.get("gif_avatar");gif_bn=data.get("gif_banner")
    if (gif_av or gif_bn) and not premium: raise HTTPException(403,"GIF только для премиума")
    if user.get("is_scam"):
        if data.get("avatar") and not has_scam_perm(user,"set_avatar"): raise HTTPException(403,"SCAM: смена авы запрещена")
        if data.get("banner") and not has_scam_perm(user,"set_banner"): raise HTTPException(403,"SCAM: смена баннера запрещена")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""UPDATE users SET
            avatar=COALESCE($1,avatar),banner=COALESCE($2,banner),
            gif_avatar=COALESCE($3,gif_avatar),gif_banner=COALESCE($4,gif_banner),
            avatar_pos=COALESCE($5,avatar_pos),banner_pos=COALESCE($6,banner_pos),
            nickname_color=$7,nickname_gradient=$8,
            bio=COALESCE($9,bio),fav_music=COALESCE($10,fav_music),
            custom_status=COALESCE($11,custom_status)
            WHERE id=$12""",
            data.get("avatar"),data.get("banner"),gif_av,gif_bn,
            data.get("avatar_pos"),data.get("banner_pos"),
            data.get("nickname_color"),data.get("nickname_gradient"),
            data.get("bio"),data.get("fav_music"),
            data.get("custom_status"),user["id"])
    return {"ok":True}

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
    await manager.broadcast({"type":"status_update","user_id":user["id"],"online_status":st,"custom_status":custom or None})
    return {"ok":True}

@app.post("/api/user/change_username")
async def change_username(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    new=sanitize_username(data.get("username") or "")
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

# ============ FRIENDS (ФИКС) ============
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
            last=await conn.fetchval("SELECT MAX(created_at) FROM dms WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",uid,oid)
            item=user_public(o,uid)
            item["status"]="accepted"
            item["friend_row_id"]=r["id"]
            item["last_message_at"]=last.isoformat() if last else None
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
    result.sort(key=lambda x:(not x.get("online"),not x.get("is_premium")))
    return result

@app.post("/api/friends/request")
async def friends_request(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"add_friends"): raise HTTPException(403,"SCAM: нельзя добавлять друзей")
    tn=(data.get("username") or "").strip().lstrip("@")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE username=$1",tn)
        if not t: raise HTTPException(404,"Не найден")
        if t["id"]==user["id"]: raise HTTPException(400,"Себя нельзя")
        if await is_blocked(user["id"],t["id"]): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],t["id"]): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],t["id"]): raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],t["id"])
    await manager.send_to(t["id"],{"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    return {"ok":True}

@app.post("/api/friends/request_by_id")
async def friends_request_by_id(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"add_friends"): raise HTTPException(403,"SCAM: нельзя добавлять друзей")
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    if tid==0: raise HTTPException(400,"Нельзя добавить бота")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id,username FROM users WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Не найден")
        if await is_blocked(user["id"],tid): raise HTTPException(403,"Заблокирован")
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid): raise HTTPException(400,"Уже друзья")
        if await conn.fetchrow("SELECT id FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid): raise HTTPException(400,"Заявка уже есть")
        await conn.execute("INSERT INTO friend_requests(from_user,to_user) VALUES($1,$2)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_request","from_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
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
        other=await conn.fetchrow("SELECT id,username,avatar FROM users WHERE id=$1",r["from_user"])
    await manager.send_to(r["from_user"],{"type":"friend_accepted","friend_id":user["id"],"username":user["username"],"avatar":user.get("avatar")})
    await manager.send_to(user["id"],{"type":"friend_accepted","friend_id":r["from_user"],"username":other["username"],"avatar":other["avatar"]})
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
    await manager.send_to(r["from_user"],{"type":"friend_declined","by_id":user["id"],"username":user["username"]})
    return {"ok":True}

@app.post("/api/friends/cancel")
async def friends_cancel(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    rid=int(data.get("request_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friend_requests WHERE id=$1 AND from_user=$2",rid,user["id"])
    return {"ok":True}

@app.post("/api/friends/remove")
async def friends_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
    await manager.send_to(tid,{"type":"friend_removed","by_id":user["id"],"username":user["username"]})
    return {"ok":True}

@app.get("/api/friends/check/{user_id}")
async def friends_check(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        if await conn.fetchrow("SELECT id FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],user_id):
            return {"status":"accepted"}
        req=await conn.fetchrow("SELECT id,from_user FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],user_id)
        if req: return {"status":"incoming" if req["from_user"]!=user["id"] else "outgoing","request_id":req["id"]}
    return {"status":"none"}

@app.get("/api/friends/count")
async def friends_count(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        n=await conn.fetchval("SELECT COUNT(*) FROM friend_requests WHERE to_user=$1",user["id"])
    return {"count":n or 0}

# ============ BLOCKS ============
@app.post("/api/blocks/add")
async def blocks_add(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    if tid==user["id"]: raise HTTPException(400,"Себя нельзя")
    p=await get_pool()
    async with p.acquire() as conn:
        try: await conn.execute("INSERT INTO blocks(blocker,blocked) VALUES($1,$2)",user["id"],tid)
        except: pass
        await conn.execute("DELETE FROM friendships WHERE (user_a=$1 AND user_b=$2) OR (user_a=$2 AND user_b=$1)",user["id"],tid)
        await conn.execute("DELETE FROM friend_requests WHERE (from_user=$1 AND to_user=$2) OR (from_user=$2 AND to_user=$1)",user["id"],tid)
    return {"ok":True}

@app.post("/api/blocks/remove")
async def blocks_remove(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("user_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM blocks WHERE blocker=$1 AND blocked=$2",user["id"],tid)
    return {"ok":True}

@app.get("/api/blocks/list")
async def blocks_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT b.blocked AS id,u.username,u.avatar FROM blocks b JOIN users u ON u.id=b.blocked WHERE b.blocker=$1 ORDER BY b.created_at DESC",user["id"])
    return [dict(r) for r in rows]

# ============ GROUPS ============
@app.get("/api/groups/list")
async def groups_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT g.* FROM groups g JOIN group_members gm ON gm.group_id=g.id WHERE gm.user_id=$1 ORDER BY COALESCE(g.last_message_at,g.created_at) DESC",user["id"])
    return [{"id":r["id"],"name":r["name"],"avatar":r["avatar"],"description":r["description"],"owner_id":r["owner_id"],"last_message_at":r["last_message_at"].isoformat() if r.get("last_message_at") else None} for r in rows]

@app.post("/api/groups/create")
async def groups_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    members=data.get("members") or []
    max_members=30 if is_premium(user) else 10
    if len(members)+1>max_members: raise HTTPException(400,f"Макс {max_members}")
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("INSERT INTO groups(name,avatar,description,owner_id) VALUES($1,$2,$3,$4) RETURNING *",name,data.get("avatar"),(data.get("description","") or "")[:256],user["id"])
        await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2)",g["id"],user["id"])
        for m in members:
            try:
                mid=int(m)
                if mid!=user["id"]:
                    await conn.execute("INSERT INTO group_members(group_id,user_id) VALUES($1,$2) ON CONFLICT DO NOTHING",g["id"],mid)
                    await manager.send_to(mid,{"type":"group_added","group_id":g["id"],"name":name})
            except: pass
    return {"id":g["id"],"name":g["name"],"avatar":g["avatar"]}

@app.get("/api/groups/{group_id}/messages")
async def group_messages(group_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not m: raise HTTPException(403,"Не участник")
        rows=await conn.fetch("""SELECT gm.id,gm.text,gm.file_url,gm.created_at,gm.user_id,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.is_scam
            FROM group_messages gm JOIN users u ON u.id=gm.user_id WHERE gm.group_id=$1 ORDER BY gm.id ASC LIMIT 200""",group_id)
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None;out.append(d)
    return out

@app.post("/api/groups/leave")
async def group_leave(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    gid=int(data.get("group_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        g=await conn.fetchrow("SELECT owner_id FROM groups WHERE id=$1",gid)
        if not g: raise HTTPException(404,"Нет")
        if g["owner_id"]==user["id"]: await conn.execute("DELETE FROM groups WHERE id=$1",gid)
        else: await conn.execute("DELETE FROM group_members WHERE group_id=$1 AND user_id=$2",gid,user["id"])
    return {"ok":True}

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
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        code=secrets.token_urlsafe(8)[:12]
        s=await conn.fetchrow("INSERT INTO servers(name,owner_id,invite_code) VALUES($1,$2,$3) RETURNING *",name,user["id"],code)
        await conn.execute("INSERT INTO server_members(server_id,user_id) VALUES($1,$2)",s["id"],user["id"])
        await conn.execute("INSERT INTO channels(server_id,name) VALUES($1,'общий')",s["id"])
        await grant_achievement(user["id"],"first_server")
    return {"id":s["id"],"name":s["name"],"invite_code":code}

@app.get("/api/servers/{server_id}/channels")
async def server_channels(server_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,name,type,mode,last_message_at FROM channels WHERE server_id=$1 ORDER BY id",server_id)
    return [{"id":r["id"],"name":r["name"],"type":r["type"],"mode":r.get("mode") or "public"} for r in rows]

@app.post("/api/channels/create")
async def channel_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    sid=int(data.get("server_id",0));name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Имя нужно")
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO channels(server_id,name) VALUES($1,$2) RETURNING id,name",sid,name)
    return {"id":r["id"],"name":r["name"]}

@app.get("/api/channels/{channel_id}/messages")
async def channel_messages(channel_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT m.id,m.text,m.file_url,m.reactions,m.edited,m.reply_to,m.pinned,m.effect,m.created_at,m.user_id,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.title,u.active_frame,u.is_scam
            FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 ORDER BY m.id ASC LIMIT 200""",channel_id)
        pinned=await conn.fetch("SELECT m.id,m.text,m.user_id,u.username FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=$1 AND m.pinned=TRUE ORDER BY m.id DESC LIMIT 5",channel_id)
    out=[]
    for r in rows:
        d=dict(r)
        d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["reactions"]=json.loads(d.get("reactions") or "{}")
        out.append(d)
    return {"messages":out,"pinned":[dict(p) for p in pinned]}

@app.get("/api/dm/{user_id}/messages")
async def dm_messages(user_id:int,token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    if await is_blocked(user["id"],user_id): raise HTTPException(403,"Заблокировано")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT d.id,d.from_user,d.to_user,d.text,d.file_url,d.created_at,d.read_at,
            u.username,u.avatar,u.gif_avatar,u.avatar_pos,u.is_scam
            FROM dms d JOIN users u ON u.id=d.from_user
            WHERE (d.from_user=$1 AND d.to_user=$2) OR (d.from_user=$2 AND d.to_user=$1) ORDER BY d.id ASC LIMIT 200""",user["id"],user_id)
        # помечаем прочитанными
        await conn.execute("UPDATE dms SET read_at=NOW() WHERE from_user=$1 AND to_user=$2 AND read_at IS NULL",user_id,user["id"])
    out=[]
    for r in rows:
        d=dict(r);d["created_at"]=d["created_at"].isoformat() if d.get("created_at") else None
        d["read_at"]=d["read_at"].isoformat() if d.get("read_at") else None
        out.append(d)
    return out

# ============ MESSAGES ============
@app.post("/api/messages/edit")
async def message_edit(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    mid=int(data.get("message_id",0))
    new_text=data.get("text","")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("UPDATE messages SET text=$1,edited=TRUE WHERE id=$2 AND user_id=$3 RETURNING id",new_text,mid,user["id"])
    if not row: return {"ok":False}
    await manager.broadcast({"type":"message_edited","id":mid,"text":new_text})
    return {"ok":True}

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
    await manager.broadcast({"type":"message_deleted","id":mid})
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
    await manager.broadcast({"type":"message_pinned","id":mid,"pinned":new})
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
    await manager.broadcast({"type":"reaction_update","id":mid,"reactions":react})
    await bp_add_progress(user["id"],"react",1)
    return {"ok":True}

@app.post("/api/messages/save")
async def message_save(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    text=(data.get("text") or "").strip()
    if not text: raise HTTPException(400,"Пусто")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO user_saved_messages(user_id,text) VALUES($1,$2)",user["id"],text)
    return {"ok":True}

@app.get("/api/messages/saved")
async def messages_saved(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,text,created_at FROM user_saved_messages WHERE user_id=$1 ORDER BY id DESC",user["id"])
    return [{"id":r["id"],"text":r["text"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

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
    if len(content)==0: raise HTTPException(400,"Пустой файл")
    name=f"{secrets.token_hex(8)}{ext}"
    with open(os.path.join(UPLOAD_DIR,name),"wb") as f: f.write(content)
    return {"url":f"/uploads/{name}"}

# ============ GIFTS ============
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
    if user.get("is_scam") and not has_scam_perm(user,"gift_send"): raise HTTPException(403,"SCAM: дарить запрещено")
    gift_id=data.get("gift")
    g=await get_all_gifts()
    if gift_id not in g: raise HTTPException(400,"Нет подарка")
    gift=g[gift_id];price=gift["price"]
    if user.get("coins",0)<price: raise HTTPException(400,"Не хватает")
    to_id=int(data.get("to_user",0))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",price,user["id"])
        await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],to_id,gift_id)
        await conn.execute("UPDATE users SET social_rating=social_rating+$1 WHERE id=$2",price,user["id"])
        cnt=await conn.fetchval("SELECT COUNT(*) FROM gifts WHERE from_user=$1",user["id"])
    if cnt==1: await grant_achievement(user["id"],"first_gift")
    await manager.send_to(to_id,{"type":"gift_received","gift_emoji":gift.get("emoji"),"gift_name":gift["name"],"gift_image":gift.get("image"),"from_name":user["username"]})
    await grant_candy(user["id"],2,silent=True)
    await bp_add_progress(user["id"],"give_gift",1)
    return {"ok":True}

# ============ NFT / CASES ============
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
    if user.get("is_scam") and not has_scam_perm(user,"buy_nft"): raise HTTPException(403,"SCAM: покупка NFT запрещена")
    nid=int(data.get("nft_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        s=await conn.fetchrow("SELECT * FROM nft_series WHERE id=$1",nid)
        if not s: raise HTTPException(404,"Нет")
        if s["sold"]>=s["total"]: raise HTTPException(400,"Распродано")
        if user.get("coins",0)<s["price"]: raise HTTPException(400,"Не хватает")
        num=s["sold"]+1
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",s["price"],user["id"])
        await conn.execute("INSERT INTO nft_items(series_id,number,owner_id) VALUES($1,$2,$3)",nid,num,user["id"])
        await conn.execute("UPDATE nft_series SET sold=sold+1 WHERE id=$1",nid)
        cnt=await conn.fetchval("SELECT COUNT(*) FROM nft_items WHERE owner_id=$1",user["id"])
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
        if not c: raise HTTPException(404,"Нет кейса")
        if user.get("coins",0)<c["price"]: raise HTTPException(400,"Не хватает")
        prizes=await conn.fetch("SELECT * FROM case_prizes WHERE case_id=$1",cid)
        if not prizes: raise HTTPException(400,"Нет призов")
        total=sum(p["chance"] for p in prizes)
        roll=random.randint(1,total)
        acc=0;chosen=None
        for p in prizes:
            acc+=p["chance"]
            if roll<=acc: chosen=p;break
        if not chosen: chosen=prizes[-1]
        await conn.execute("UPDATE users SET coins=coins-$1 WHERE id=$2",c["price"],user["id"])
        if chosen["kind"]=="coins":
            amt=random.randint(chosen["coins_min"] or 1,chosen["coins_max"] or chosen["coins_min"] or 1)
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,user["id"])
            prize_text=f"🏅 {amt} бекоинов"
        elif chosen["kind"]=="gift":
            gid=chosen["item_id"]
            if gid: await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],gid)
            prize_text=f"🎀 {chosen['item_name'] or gid}"
        else: prize_text=f"❓ {chosen['item_name'] or '???'}"
    await grant_candy(user["id"],random.randint(1,5),silent=True)
    await bp_add_progress(user["id"],"open_case",1)
    return {"ok":True,"prize":prize_text}

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
    max_lv=season.get("max_level") or 50
    ends_in_days=None
    if season.get("ends_at"):
        try: ends_in_days=max(0,int((season["ends_at"]-datetime.datetime.now(datetime.timezone.utc)).total_seconds()//86400))
        except: pass
    return {
        "active":True,"name":season["name"],"description":season["description"],"emoji":season["emoji"],
        "my_xp":my_xp,"my_level":my_level,"xp_per_level":xp_per,"max_level":max_lv,
        "ends_in_days":ends_in_days,"has_premium_pass":has_pp,
        "quests":[{"id":q["id"],"name":q["name"],"desc":q["description"],"goal":q["goal"],"xp_reward":q["xp_reward"],"action_type":q.get("action_type"),"target_count":q.get("target_count",1)} for q in quests],
        "rewards":[{"id":r["id"],"level":r["level"],"reward":r["reward"],"reward_type":r.get("reward_type"),"reward_value":r.get("reward_value"),"reward_item_id":r.get("reward_item_id"),"track":r.get("track","free"),"unlocked":my_level>=r["level"] and str(r["id"]) not in claimed,"locked_premium":r.get("track")=="premium" and not has_pp} for r in rewards]
    }

@app.post("/api/bp/claim")
async def bp_claim(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    if user.get("is_scam") and not has_scam_perm(user,"join_bp"): raise HTTPException(403,"SCAM: БП запрещён")
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
        if track=="premium" and not prog["has_premium_pass"]: raise HTTPException(403,"Нужен премиум-пропуск")
        claimed=json.loads(prog["claimed"] or "[]")
        rid=str(r["id"])
        if rid in claimed: raise HTTPException(400,"Уже забрано")
        claimed.append(rid)
        await conn.execute("UPDATE bp_progress SET claimed=$1 WHERE id=$2",json.dumps(claimed),prog["id"])
        rt=r.get("reward_type");rv=r.get("reward_value") or 0;ri=r.get("reward_item_id")
        if rt=="coins": await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",rv,user["id"])
        elif rt=="xp": await grant_xp(user["id"],rv)
        elif rt=="kp": await conn.execute("UPDATE users SET quest_points=quest_points+$1 WHERE id=$2",rv,user["id"])
        elif rt=="candy": await conn.execute("UPDATE users SET candy=candy+$1 WHERE id=$2",rv,user["id"])
        elif rt=="premium": await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",rv,user["id"])
        elif rt=="frame" and ri:
            owned=json.loads(user.get("frame_owned") or "[]")
            if ri not in owned:
                owned.append(ri)
                await conn.execute("UPDATE users SET frame_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
        elif rt=="title" and ri:
            t_owned=json.loads(user.get("title_owned") or "[]")
            if ri not in t_owned:
                t_owned.append(ri)
                await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(t_owned),user["id"])
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
        if prog:
            await conn.execute("UPDATE bp_progress SET has_premium_pass=TRUE WHERE id=$1",prog["id"])
        else:
            await conn.execute("INSERT INTO bp_progress(user_id,season_id,xp,level,has_premium_pass) VALUES($1,$2,0,1,TRUE)",user["id"],season["id"])
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
        elif kind=="title" and itemval:
            t_owned=json.loads(user.get("title_owned") or "[]")
            if itemval not in t_owned:
                t_owned.append(itemval)
                await conn.execute("UPDATE users SET title_owned=$1,title=$2 WHERE id=$3",json.dumps(t_owned),itemval[:64],user["id"])
        elif kind=="gift" and itemval:
            for _ in range(count):
                await conn.execute("INSERT INTO gifts(from_user,to_user,gift) VALUES($1,$2,$3)",user["id"],user["id"],itemval)
        elif kind=="premium":
            await conn.execute("UPDATE users SET premium_tier='premium',premium_expires=COALESCE(premium_expires,NOW())+INTERVAL '1 day' * $1 WHERE id=$2",value,user["id"])
        elif kind=="coins":
            await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",value,user["id"])
        elif kind=="xp":
            await grant_xp(user["id"],value)
        new_candy=await conn.fetchval("SELECT candy FROM users WHERE id=$1",user["id"])
    return {"ok":True,"candy":new_candy}

# ============ TITLES (НОВОЕ в 2.8) ============
@app.get("/api/titles/list")
async def titles_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        # публичные + свои приватные + те что выданы юзеру
        rows=await conn.fetch("""SELECT * FROM titles_catalog 
            WHERE is_public=TRUE 
               OR creator_id=$1 
               OR id = ANY(SELECT CAST(value AS INTEGER) FROM jsonb_each_text($2::jsonb))
            ORDER BY is_public DESC, id DESC""",user["id"],json.dumps({k:1 for k in json.loads(user.get("title_owned") or "[]")}))
    return [{"id":r["id"],"name":r["name"],"emoji":r["emoji"],"color":r["color"],"is_public":r["is_public"],"condition_type":r["condition_type"],"condition_value":r["condition_value"],"creator_id":r["creator_id"]} for r in rows]

@app.get("/api/titles/my")
async def titles_my(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"title":user.get("title"),"owned":json.loads(user.get("title_owned") or "[]")}

@app.post("/api/titles/set")
async def titles_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    title_id=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",title_id)
        if not t: raise HTTPException(404,"Нет титула")
        owned=json.loads(user.get("title_owned") or "[]")
        # проверяем права
        if t["is_public"]:
            # проверяем условие
            ct=t["condition_type"];cv=t["condition_value"] or 0
            if ct=="level" and user.get("level",1)<cv: raise HTTPException(403,f"Нужен ур. {cv}")
            if ct=="messages" and user.get("messages_count",0)<cv: raise HTTPException(403,f"Нужно {cv} сообщений")
            if ct=="free": pass
            if ct=="custom": raise HTTPException(403,"Приватный титул — нужна выдача")
        else:
            if title_id not in owned and t["creator_id"]!=user["id"]:
                raise HTTPException(403,"Нет доступа")
        await conn.execute("UPDATE users SET title=$1 WHERE id=$2",t["name"],user["id"])
        if title_id not in owned:
            owned.append(title_id)
            await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True}

@app.post("/api/titles/create")
async def titles_create(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    name=(data.get("name") or "").strip()[:64]
    if not name: raise HTTPException(400,"Название нужно")
    emoji=(data.get("emoji") or "⭐")[:8]
    color=(data.get("color") or "#d946ef")[:32]
    is_public=bool(data.get("is_public",False))
    condition_type=(data.get("condition_type") or "custom")[:32]
    condition_value=int(data.get("condition_value",0))
    p=await get_pool()
    async with p.acquire() as conn:
        r=await conn.fetchrow("INSERT INTO titles_catalog(name,emoji,color,is_public,condition_type,condition_value,creator_id) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",name,emoji,color,is_public,condition_type,condition_value,user["id"])
        # создателю сразу выдаём
        owned=json.loads(user.get("title_owned") or "[]")
        owned.append(r["id"])
        await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),user["id"])
    return {"ok":True,"id":r["id"]}

@app.post("/api/titles/give")
async def titles_give(data:dict):
    """Владелец или создатель может выдать титул"""
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("title_id",0))
    target_username=(data.get("username") or "").strip().lstrip("@")
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет титула")
        is_owner=user["username"]==ADMIN_USERNAME
        is_creator=t["creator_id"]==user["id"]
        if not (is_owner or is_creator): raise HTTPException(403,"Только владелец или создатель")
        target=await conn.fetchrow("SELECT id,title_owned FROM users WHERE username=$1",target_username)
        if not target: raise HTTPException(404,"Юзер не найден")
        owned=json.loads(target["title_owned"] or "[]")
        if tid not in owned: owned.append(tid)
        await conn.execute("UPDATE users SET title_owned=$1 WHERE id=$2",json.dumps(owned),target["id"])
    await manager.send_to(target["id"],{"type":"title_given","title_id":tid,"name":t["name"],"emoji":t["emoji"]})
    return {"ok":True}

@app.post("/api/titles/delete")
async def titles_delete(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    tid=int(data.get("title_id",0))
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT * FROM titles_catalog WHERE id=$1",tid)
        if not t: raise HTTPException(404,"Нет")
        is_owner=user["username"]==ADMIN_USERNAME
        is_creator=t["creator_id"]==user["id"]
        if not (is_owner or is_creator): raise HTTPException(403,"Только владелец или создатель")
        await conn.execute("DELETE FROM titles_catalog WHERE id=$1",tid)
    return {"ok":True}

# ============ QUIZ ============
@app.get("/api/quiz/status")
async def quiz_status():
    return {"enabled":teacher_quiz_enabled,"title":"Викторина «День учителя»","emoji":"🎓"}

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
    return {"ok":True,"correct":correct}

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

# ============ SUPPORT BOT ============
@app.post("/api/support/ticket")
async def support_ticket(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    ticket_type=(data.get("ticket_type") or "").strip()
    if ticket_type not in ("unscam","unban","report_scam","report_spam","other"): raise HTTPException(400,"Неверный тип")
    title=(data.get("title") or "")[:128]
    description=(data.get("description") or "")[:2000]
    evidence=(data.get("evidence") or "")[:1000]
    target=int(data.get("target_user") or 0)
    if not description: raise HTTPException(400,"Опиши ситуацию")
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("""INSERT INTO support_tickets(from_user,ticket_type,target_user,title,description,evidence)
            VALUES($1,$2,$3,$4,$5,$6) RETURNING id""",user["id"],ticket_type,target or None,title,description,evidence)
        owner=await conn.fetchrow("SELECT id FROM users WHERE username=$1",ADMIN_USERNAME)
        if owner:
            await manager.send_to(owner["id"],{"type":"support_ticket_new","id":row["id"],"from":user["username"],"type":ticket_type,"title":title})
    msg=f"✅ Заявка #{row['id']} принята!\nТип: {ticket_type}\nТема: {title or '(без темы)'}"
    await manager.send_to(user["id"],{"type":"dm","id":random.randint(1000000,9999999),"from_user":SUPPORT_BOT_ID,"to_user":user["id"],"username":SUPPORT_BOT_DISPLAY,"text":msg,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return {"ok":True,"ticket_id":row["id"]}

@app.get("/api/support/my_tickets")
async def my_tickets(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM support_tickets WHERE from_user=$1 ORDER BY id DESC LIMIT 50",user["id"])
    return [{"id":r["id"],"ticket_type":r["ticket_type"],"title":r["title"],"description":r["description"],"status":r["status"],"admin_reply":r["admin_reply"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

# ============ STATIC ============
@app.get("/manifest.json")
async def manifest():
    return {"name":"Belugacord Beta 2.8 🎃","short_name":"Belugacord","start_url":"/","display":"standalone","background_color":"#1a0a2e","theme_color":"#1a0a2e","icons":[{"src":"/uploads/icon.png","sizes":"192x192","type":"image/png"}]}

@app.get("/")
async def index():
    with open("index.html","r",encoding="utf-8") as f: return HTMLResponse(f.read())
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
        g=await conn.fetchval("SELECT COUNT(*) FROM gifts")
    return {"users":u,"messages":m,"coins":c,"gifts":g,"online":len(online_users)}

@app.post("/api/owner/give_coins")
async def owner_give_coins(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        t=await conn.fetchrow("SELECT id FROM users WHERE username=$1",data.get("username"))
        if not t: raise HTTPException(404,"Не найден")
        amt=int(data.get("amount",100))
        await conn.execute("UPDATE users SET coins=coins+$1 WHERE id=$2",amt,t["id"])
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
    await manager.send_to(t["id"],{"type":"candy_received","amount":amt})
    return {"ok":True}

@app.post("/api/owner/announce_full")
async def owner_announce_full(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    username=(data.get("username") or user["username"])[:32]
    avatar=(data.get("avatar") or user.get("avatar") or "")
    text=(data.get("text") or "").strip()[:1000]
    if not text: raise HTTPException(400,"Пусто")
    payload={"type":"abuse_announce","username":username,"avatar":avatar,"text":text,"from_id":user["id"]}
    sent=0
    for uid in list(manager.connections.keys()):
        try:
            await manager.send_to(uid,payload); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.post("/api/owner/hot_swap")
async def owner_hot_swap(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    sent=0
    for uid in list(manager.connections.keys()):
        try:
            await manager.send_to(uid,{"type":"force_reload"}); sent+=1
        except: pass
    return {"ok":True,"sent":sent}

@app.post("/api/owner/holiday/force")
async def owner_holiday_force(data:dict):
    global forced_holiday
    user=await get_current_user(data.get("token")); await check_owner(user)
    hid=(data.get("holiday_id") or "").strip()
    if hid=="none" or not hid:
        forced_holiday=None
        p=await get_pool()
        async with p.acquire() as conn:
            await conn.execute("UPDATE system_settings SET value='' WHERE key='forced_holiday'")
        await manager.broadcast({"type":"holiday_theme","holiday":None})
        return {"ok":True,"forced":None}
    h=next((x for x in HOLIDAYS if x[1]==hid),None)
    if not h: raise HTTPException(404,"Праздник не найден")
    forced_holiday=hid
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE system_settings SET value=$1 WHERE key='forced_holiday'",hid)
    payload={"id":h[1],"name":h[2],"emoji":h[3],"color":h[4],"country":h[5],"forced":True}
    await manager.broadcast({"type":"holiday_theme","holiday":payload})
    return {"ok":True,"forced":payload}

# ============ ADMIN ============
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

@app.get("/api/admin/users")
async def admin_users(token:str):
    user=await get_current_user(token); await check_admin(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT id,username,is_admin,is_moderator,is_scam,is_banned,coins,candy,title FROM users WHERE id!=0 ORDER BY id")
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
    if action=="ban":
        await manager.send_to(tid,{"type":"banned","reason":data.get("reason","")})
        await manager.kick(tid)
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
    await manager.broadcast({"type":"user_updated","user_id":tid})
    return {"ok":True,"is_scam":new}

@app.get("/api/admin/scam_perms/{user_id}")
async def admin_scam_perms_get(user_id:int,token:str):
    user=await get_current_user(token); await check_admin(user)
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT is_scam,scam_perms FROM users WHERE id=$1",user_id)
        if not row: raise HTTPException(404,"Не найден")
    try: perms=json.loads(row["scam_perms"] or "{}")
    except: perms={}
    full={k:perms.get(k,SCAM_DEFAULT_PERMS[k]) for k in SCAM_DEFAULT_PERMS}
    return {"is_scam":row["is_scam"],"perms":full,"defaults":SCAM_DEFAULT_PERMS}

@app.post("/api/admin/scam_perms/set")
async def admin_scam_perms_set(data:dict):
    user=await get_current_user(data.get("token")); await check_admin(user)
    tid=int(data.get("target_id",0))
    perms=data.get("perms") or {}
    clean={k:bool(v) for k,v in perms.items() if k in SCAM_DEFAULT_PERMS}
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE users SET scam_perms=$1 WHERE id=$2",json.dumps(clean),tid)
    await manager.broadcast({"type":"user_updated","user_id":tid})
    return {"ok":True,"perms":clean}

@app.get("/api/admin/reports")
async def admin_reports(token:str):
    user=await get_current_user(token); await check_admin(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT r.id,r.text,r.target_user,f.username AS from_username,t.username AS target_username FROM reports r LEFT JOIN users f ON f.id=r.from_user LEFT JOIN users t ON t.id=r.target_user WHERE r.status='pending' ORDER BY r.id DESC")
    return [dict(r) for r in rows]

@app.get("/api/support/all")
async def support_all(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("""SELECT st.*,u.username AS from_username,t.username AS target_username
            FROM support_tickets st
            LEFT JOIN users u ON u.id=st.from_user
            LEFT JOIN users t ON t.id=st.target_user
            ORDER BY st.status='pending' DESC, st.id DESC LIMIT 200""")
    return [{"id":r["id"],"from_username":r["from_username"],"target_username":r["target_username"],"ticket_type":r["ticket_type"],"title":r["title"],"description":r["description"],"evidence":r["evidence"],"status":r["status"],"admin_reply":r["admin_reply"],"created_at":r["created_at"].isoformat() if r["created_at"] else None} for r in rows]

@app.post("/api/support/resolve")
async def support_resolve(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
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
        if action=="approve" and t["ticket_type"]=="unban" and t["from_user"]:
            await conn.execute("UPDATE users SET is_banned=FALSE WHERE id=$1",t["from_user"])
        if action=="approve" and t["ticket_type"] in ("report_scam","report_spam") and t["target_user"]:
            reason=f"По жалобе #{tid}: {t['description'][:150]}"
            await conn.execute("UPDATE users SET is_banned=TRUE,ban_reason=$1 WHERE id=$2",reason,t["target_user"])
            try: await manager.kick(t["target_user"])
            except: pass
    if t["from_user"]:
        msg_text=f"📬 Заявка #{tid}: {'✅ Одобрено' if action=='approve' else '❌ Отклонено'}\n{('Сообщение: '+reply) if reply else ''}"
        await manager.send_to(t["from_user"],{"type":"dm","id":random.randint(1000000,9999999),"from_user":SUPPORT_BOT_ID,"to_user":t["from_user"],"username":SUPPORT_BOT_DISPLAY,"text":msg_text,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return {"ok":True}

# ============ BP ADMIN ============
@app.get("/api/bp/admin/info")
async def bp_admin_info(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
    if not row: return {"name":"","emoji":"🎃","days_total":30,"max_level":50,"xp_per_level":1000}
    return {"name":row["name"],"description":row["description"],"emoji":row["emoji"],"days_total":row.get("days_total") or 30,"max_level":row.get("max_level") or 50,"xp_per_level":row.get("xp_per_level") or 1000}

@app.post("/api/bp/admin/save")
async def bp_admin_save(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "").strip()[:64] or "Новый сезон"
    days=int(data.get("days") or 30); days=max(1,min(365,days))
    max_lv=int(data.get("max_level") or 50); max_lv=max(1,min(500,max_lv))
    xp_per=int(data.get("xp_per_level") or 1000); xp_per=max(100,min(100000,xp_per))
    emoji=(data.get("emoji") or "🎃")[:4]
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT id FROM bp_season WHERE active=TRUE ORDER BY id DESC LIMIT 1")
        now=datetime.datetime.now(datetime.timezone.utc)
        ends=now+datetime.timedelta(days=days)
        if row:
            await conn.execute("UPDATE bp_season SET name=$1,emoji=$2,days_total=$3,max_level=$4,ends_at=$5,xp_per_level=$6 WHERE id=$7",name,emoji,days,max_lv,ends,xp_per,row["id"])
        else:
            await conn.execute("INSERT INTO bp_season(name,emoji,days_total,max_level,ends_at,xp_per_level,active) VALUES($1,$2,$3,$4,$5,$6,TRUE)",name,emoji,days,max_lv,ends,xp_per)
    return {"ok":True}

@app.get("/api/bp/admin/quests")
async def bp_admin_quests(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM bp_quests WHERE active=TRUE ORDER BY id")
    return [dict(r) for r in rows]

@app.post("/api/bp/admin/quests/add")
async def bp_admin_quests_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    name=(data.get("name") or "")[:128]
    if not name: raise HTTPException(400,"Название нужно")
    action_type=(data.get("action_type") or "custom")[:32]
    target_count=int(data.get("target_count",1))
    xp=int(data.get("xp_reward",100))
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO bp_quests(name,description,goal,xp_reward,action_type,target_count) VALUES($1,'',$2,$3,$4,$5)",name,target_count,xp,action_type,target_count)
    return {"ok":True}

@app.post("/api/bp/admin/quests/delete")
async def bp_admin_quests_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_quests WHERE id=$1",int(data.get("quest_id",0)))
    return {"ok":True}

@app.get("/api/bp/admin/rewards")
async def bp_admin_rewards(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM bp_rewards WHERE active=TRUE ORDER BY level,track")
    return [dict(r) for r in rows]

@app.post("/api/bp/admin/rewards/add")
async def bp_admin_rewards_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    level=int(data.get("level",1))
    reward=(data.get("reward") or "")[:128]
    if not reward: raise HTTPException(400,"Награда нужна")
    rtype=(data.get("reward_type") or "coins")[:32]
    rvalue=int(data.get("reward_value",0))
    ritem=(data.get("reward_item_id") or "")[:64] or None
    track=(data.get("track") or "free")[:16]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO bp_rewards(level,reward,reward_type,reward_value,reward_item_id,track) VALUES($1,$2,$3,$4,$5,$6)",level,reward,rtype,rvalue,ritem,track)
    return {"ok":True}

@app.post("/api/bp/admin/rewards/delete")
async def bp_admin_rewards_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM bp_rewards WHERE id=$1",int(data.get("reward_id",0)))
    return {"ok":True}

@app.post("/api/bp/admin/apply_preset")
async def bp_admin_apply_preset(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    preset_name=(data.get("preset") or "halloween").lower()
    if preset_name not in BP_PRESETS: raise HTTPException(400,"Нет пресета")
    preset=BP_PRESETS[preset_name]
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE bp_season SET active=FALSE,ended_at=NOW() WHERE active=TRUE")
        await conn.execute("DELETE FROM bp_quests")
        await conn.execute("DELETE FROM bp_rewards")
        ends=datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(days=preset["days_total"])
        await conn.execute("INSERT INTO bp_season(name,description,emoji,days_total,max_level,ends_at,active,xp_per_level) VALUES($1,$2,$3,$4,$5,$6,TRUE,1000)",preset["name"],preset["description"],preset["emoji"],preset["days_total"],preset["max_level"],ends)
        for q in preset["quests"]:
            await conn.execute("INSERT INTO bp_quests(name,description,goal,xp_reward,action_type,target_count) VALUES($1,'',$2,$3,$4,$2)",q["name"],q["target_count"],q["xp_reward"],q["action_type"])
        for r in preset["rewards"]:
            await conn.execute("INSERT INTO bp_rewards(level,reward,reward_type,reward_value,reward_item_id,track) VALUES($1,$2,$3,$4,$5,$6)",r["level"],r["reward"],r["reward_type"],r["reward_value"],r.get("reward_item_id"),r.get("track","free"))
    await manager.broadcast({"type":"bp_update"})
    return {"ok":True,"name":preset["name"],"quests":len(preset["quests"]),"rewards":len(preset["rewards"])}

# ============ CANDY ADMIN ============
@app.get("/api/owner/candy_shop")
async def owner_candy_shop(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        items=await conn.fetch("SELECT * FROM candy_shop_items ORDER BY price")
        currs=await conn.fetch("SELECT * FROM candy_currency ORDER BY key")
    return {"items":[dict(r) for r in items],"currencies":[dict(c) for c in currs]}

@app.post("/api/owner/candy_shop/add")
async def owner_candy_shop_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    iid=(data.get("id") or "").strip().lower()[:64]
    if not iid: raise HTTPException(400,"ID нужен")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""INSERT INTO candy_shop_items(id,emoji,name,price,kind,item,value,count)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO UPDATE SET emoji=$2,name=$3,price=$4,kind=$5,item=$6,value=$7,count=$8,is_active=TRUE""",iid,data.get("emoji","🎁"),data.get("name",""),int(data.get("price",100)),data.get("kind","coins"),data.get("item","") or None,int(data.get("value",0)),int(data.get("count",1)))
    return {"ok":True}

@app.post("/api/owner/candy_shop/delete")
async def owner_candy_shop_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM candy_shop_items WHERE id=$1",data.get("id"))
    return {"ok":True}

@app.post("/api/owner/candy_currency/set")
async def owner_candy_currency_set(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    key=(data.get("key") or "").strip()
    if not key: raise HTTPException(400,"Ключ нужен")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE candy_currency SET is_active=FALSE")
        row=await conn.fetchrow("SELECT * FROM candy_currency WHERE key=$1",key)
        if not row:
            await conn.execute("INSERT INTO candy_currency(key,name,emoji,is_active) VALUES($1,$2,$3,TRUE)",key,(data.get("name") or "Валюта")[:64],(data.get("emoji") or "🍬")[:8])
        else:
            await conn.execute("UPDATE candy_currency SET is_active=TRUE WHERE key=$1",key)
    await manager.broadcast({"type":"candy_currency_update","key":key})
    return {"ok":True}

# ============ QUIZ ADMIN ============
@app.get("/api/owner/quiz/all")
async def owner_quiz_all(token:str):
    user=await get_current_user(token); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM teacher_quiz ORDER BY id")
    return [{"id":r["id"],"question":r["question"],"answers":json.loads(r["answers"]),"correct":r["correct"],"is_active":r["is_active"]} for r in rows]

@app.post("/api/owner/quiz/add")
async def owner_quiz_add(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    q=(data.get("question") or "").strip()
    answers=data.get("answers") or []
    correct=int(data.get("correct",0))
    if not q or len(answers)<2: raise HTTPException(400,"Нужен вопрос и 2+ ответа")
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("INSERT INTO teacher_quiz(question,answers,correct) VALUES($1,$2,$3)",q[:500],json.dumps(answers,ensure_ascii=False),correct)
    return {"ok":True}

@app.post("/api/owner/quiz/delete")
async def owner_quiz_delete(data:dict):
    user=await get_current_user(data.get("token")); await check_owner(user)
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("DELETE FROM teacher_quiz WHERE id=$1",int(data.get("quiz_id",0)))
    return {"ok":True}

@app.post("/api/owner/quiz/toggle")
async def owner_quiz_toggle(data:dict):
    global teacher_quiz_enabled
    user=await get_current_user(data.get("token")); await check_owner(user)
    enabled=bool(data.get("enabled",True))
    teacher_quiz_enabled=enabled
    p=await get_pool()
    async with p.acquire() as conn:
        await conn.execute("UPDATE system_settings SET value=$1 WHERE key='teacher_quiz_enabled'","1" if enabled else "0")
    await manager.broadcast({"type":"quiz_toggle","enabled":enabled})
    return {"ok":True,"enabled":enabled}

# ============ COINS / REP / LEVELS ============
@app.get("/api/coins/balance")
async def coins_balance(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"coins":user.get("coins",0),"candy":user.get("candy",0)}

@app.get("/api/coins/leaders")
async def coins_leaders():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT username,coins FROM users WHERE id!=0 ORDER BY coins DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.get("/api/levels/me")
async def levels_me(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"level":user.get("level",1),"xp":user.get("xp",0),"next_xp":(user.get("level",1))*100}

@app.get("/api/levels/leaders")
async def levels_leaders():
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT username,level,xp FROM users WHERE id!=0 ORDER BY level DESC,xp DESC LIMIT 20")
    return [dict(r) for r in rows]

@app.get("/api/frames/list")
async def frames_list(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    p=await get_pool()
    async with p.acquire() as conn:
        rows=await conn.fetch("SELECT * FROM frames_catalog ORDER BY price_coins,price_kp")
        owned=json.loads(user.get("frame_owned") or "[]")
    return [{"frame_id":r["frame_id"],"name":r["name"],"emoji":r["emoji"],"owned":r["frame_id"] in owned or r["frame_id"]=="none"} for r in rows]

@app.post("/api/frames/set")
async def frames_set(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    fid=data.get("frame_id","none")
    p=await get_pool()
    async with p.acquire() as conn:
        if fid!="none":
            owned=json.loads(user.get("frame_owned") or "[]")
            if fid not in owned: raise HTTPException(403,"Не куплена")
        await conn.execute("UPDATE users SET active_frame=$1 WHERE id=$2",fid if fid!="none" else None,user["id"])
    await bp_add_progress(user["id"],"set_frame",1)
    return {"ok":True}

@app.get("/api/premium/status")
async def premium_status(token:str):
    user=await get_current_user(token)
    if not user: raise HTTPException(401,"Не авторизован")
    return {"is_premium":is_premium(user),"tier":user.get("premium_tier"),"expires":user["premium_expires"].isoformat() if user.get("premium_expires") else None}

@app.post("/api/premium/buy")
async def premium_buy(data:dict):
    user=await get_current_user(data.get("token"))
    if not user: raise HTTPException(401,"Не авторизован")
    plan=data.get("plan","month")
    if plan not in PREMIUM_PRICES: raise HTTPException(400,"Нет плана")
    price=PREMIUM_PRICES[plan];days=30 if plan=="month" else 365
    p=await get_pool()
    async with p.acquire() as conn:
        row=await conn.fetchrow("SELECT coins,premium_expires FROM users WHERE id=$1",user["id"])
        if (row["coins"] or 0)<price: raise HTTPException(400,f"Нужно {price} 🏅")
        now=datetime.datetime.now(datetime.timezone.utc)
        base=row["premium_expires"] if row["premium_expires"] and row["premium_expires"]>now else now
        new_exp=base+datetime.timedelta(days=days)
        await conn.execute("UPDATE users SET coins=coins-$1,premium_tier='premium',premium_expires=$2 WHERE id=$3",price,new_exp,user["id"])
    return {"ok":True,"premium_until":new_exp.isoformat()}

# ============ DUEL ============
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
    return {"ok":True,"win":win}

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
    await grant_xp(user["id"],5)
    await grant_candy(user["id"],random.randint(1,5),silent=True)
    await bp_add_progress(user["id"],"play_game",1)
    return {"ok":True}

# ============ WEBSOCKET ============
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
                    await manager.send_to(uid,{"type":"muted","reason":"SCAM: сообщения запрещены"}); continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO messages(channel_id,user_id,text,file_url,reply_to,effect) VALUES($1,$2,$3,$4,$5,$6) RETURNING *",int(ch),uid,text,furl,reply,effect)
                    await conn.execute("UPDATE users SET messages_count=messages_count+1 WHERE id=$1",uid)
                    mc=await conn.fetchval("SELECT messages_count FROM users WHERE id=$1",uid)
                    members=await conn.fetch("SELECT sm.user_id FROM server_members sm JOIN channels c ON c.server_id=sm.server_id WHERE c.id=$1",int(ch))
                if mc==1: await grant_achievement(uid,"first_msg")
                await grant_xp(uid,1)
                await bp_add_progress(uid,"send_message",1)
                if mc%10==0: await grant_candy(uid,1,silent=True)
                payload={"type":"message","id":msg["id"],"channel_id":int(ch),"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"reply_to":reply,"effect":effect,"created_at":msg["created_at"].isoformat(),"is_scam":user.get("is_scam"),"title":user.get("title"),"active_frame":user.get("active_frame"),"temp_id":tid}
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
                        await manager.send_to(uid,{"type":"muted","reason":"SCAM: писать первым запрещено"}); continue
                    if has_history and not has_scam_perm(user,"dm_reply"):
                        await manager.send_to(uid,{"type":"muted","reason":"SCAM: отвечать запрещено"}); continue
                p=await get_pool()
                async with p.acquire() as conn:
                    msg=await conn.fetchrow("INSERT INTO dms(from_user,to_user,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",uid,to_id,text,furl)
                await grant_xp(uid,1)
                await bp_add_progress(uid,"send_dm",1)
                payload={"type":"dm","id":msg["id"],"from_user":uid,"to_user":to_id,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"avatar_pos":user.get("avatar_pos"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"temp_id":tid,"is_scam":user.get("is_scam"),"title":user.get("title")}
                await manager.send_to(to_id,payload)
                await manager.send_to(uid,payload)
            elif t=="group_msg":
                gid=int(data.get("group_id",0));text=(data.get("text") or "")[:2000]
                furl=data.get("file_url");tid=data.get("temp_id")
                if user.get("is_scam") and not has_scam_perm(user,"chat_send"): continue
                p=await get_pool()
                async with p.acquire() as conn:
                    m=await conn.fetchrow("SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",gid,uid)
                    if not m: continue
                    msg=await conn.fetchrow("INSERT INTO group_messages(group_id,user_id,text,file_url) VALUES($1,$2,$3,$4) RETURNING *",gid,uid,text,furl)
                    members=await conn.fetch("SELECT user_id FROM group_members WHERE group_id=$1",gid)
                payload={"type":"group_msg","id":msg["id"],"group_id":gid,"user_id":uid,"username":user["username"],"avatar":user.get("avatar"),"gif_avatar":user.get("gif_avatar"),"text":text,"file_url":furl,"created_at":msg["created_at"].isoformat(),"temp_id":tid,"is_scam":user.get("is_scam"),"title":user.get("title")}
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

if __name__=="__main__":
    import uvicorn
    port=int(os.environ.get("PORT",8000))
    uvicorn.run(app,host="0.0.0.0",port=port,ws="websockets",proxy_headers=True,forwarded_allow_ips="*")