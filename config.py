import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_USERS = [int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x]

DB_PATH = "data/rent.db"
LOG_PATH = "logs/bot.log"

SCRAPE_INTERVAL_MIN = 20      # как часто опрашивать источники
FIRST_SCRAPE_PAGES = 8        # страниц истории при первом запуске (~20 постов каждая)
KEEP_DAYS = 130               # сколько хранить объявления
MAX_PER_SEND = 10             # максимум объявлений за одну отправку

# Публичные Telegram-каналы (username, город по умолчанию). Можно добавлять командой /add
DEFAULT_CHANNELS = [
    ("arenda_sharm", "ssh"),
    ("sharmelsheikh_rent", "ssh"),
    ("sharmelsheikhproperty", "ssh"),
    ("hurghada_market", "hrg"),
    ("hurghadaproperty", "hrg"),
    ("arendaegipet", ""),
    ("hurghadaapartment", "hrg"),
    ("hurgadarent", "hrg"),
    ("hurghadarent8", "hrg"),
    ("propertyegypt", ""),
    ("hurgadahomes", "hrg"),
    ("egyptowner", ""),
    ("sharm_sale", "ssh"),
    ("sharm_property", "ssh"),
    ("hurghada_nedvizhimost", "hrg"),
    ("hurghada_apartments", "hrg"),
    ("kvartiry_hurghada", "hrg"),
    ("hurghada_apartment", "hrg"),
    ("hurghada_life", "hrg"),
    ("arenda_hurgada", "hrg"),
]
