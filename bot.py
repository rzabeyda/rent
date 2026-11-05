"""
Rent Bot — объявления об аренде/покупке жилья в Хургаде и Шарм-эль-Шейхе.
Запуск: python bot.py
"""
import asyncio
import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
os.makedirs("data", exist_ok=True)
os.makedirs("logs", exist_ok=True)

from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, KeyboardButton)
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler, MessageHandler,
                          TypeHandler, ApplicationHandlerStop, filters, ContextTypes)
from telegram.error import Forbidden, BadRequest

import config
import database as db
import sources
from filters import passes
from formatter import fmt_listing, fmt_settings, PRICE_PRESETS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(),
              RotatingFileHandler(config.LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")],
)
for noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)   # в URL httpx виден токен
log = logging.getLogger("rent")

_searching: set = set()
_tasks: list = []


# ══════════ клавиатуры ═══════════════════════════════════════════
def main_keyboard(chat_id: int) -> ReplyKeyboardMarkup:
    toggle = "ВЫКЛ" if chat_id in db.active_users() else "ВКЛ"
    return ReplyKeyboardMarkup([[KeyboardButton("Искать"), KeyboardButton("Фильтры"), KeyboardButton(toggle)]],
                               resize_keyboard=True, is_persistent=True)


OPTIONS = {
    "deal": ("🏷 Тип", [("Аренда", "rent"), ("Покупка", "sale"), ("Всё", "any")]),
    "city": ("📍 Город", [("Хургада", "hrg"), ("Шарм", "ssh"), ("Все", "all")]),
    "rooms": ("🛏 Комнаты", [("Студия", "0"), ("1", "1"), ("2", "2"), ("3+", "3"), ("Любое", "any")]),
    "age": ("🕒 Давность", [("1 день", "1"), ("3 дня", "3"), ("7 дней", "7"), ("30 дней", "30")]),
    "interval": ("⏱ Интервал", [("1 ч", "60"), ("3 ч", "180"), ("6 ч", "360"), ("24 ч", "1440")]),
    "noprice": ("❔ Без цены", [("Показывать", "1"), ("Скрывать", "0")]),
}


def kb_settings() -> InlineKeyboardMarkup:
    def b(key):
        return InlineKeyboardButton(OPTIONS[key][0], callback_data=f"m:{key}")
    return InlineKeyboardMarkup([
        [b("deal"), b("city"), InlineKeyboardButton("💰 Цена", callback_data="m:price")],
        [b("rooms"), b("age"), b("interval")],
        [b("noprice")],
    ])


def kb_option(key: str, s: dict) -> InlineKeyboardMarkup:
    row = []
    for label, val in OPTIONS[key][1]:
        tick = "✅ " if s[key] == val else ""
        row.append(InlineKeyboardButton(f"{tick}{label}", callback_data=f"s:{key}:{val}"))
    rows = [row[i:i + 3] for i in range(0, len(row), 3)]
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="m:back")])
    return InlineKeyboardMarkup(rows)


def kb_price(s: dict) -> InlineKeyboardMarkup:
    presets = PRICE_PRESETS.get(s["deal"])
    if not presets:
        return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="m:back")]])
    cur = (int(s["pmin"]), int(s["pmax"]))
    row = [InlineKeyboardButton(("✅ " if (a, z) == cur else "") + label, callback_data=f"p:{i}")
           for i, (label, a, z) in enumerate(presets)]
    rows = [row[i:i + 3] for i in range(0, len(row), 3)]
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="m:back")])
    return InlineKeyboardMarkup(rows)


# ══════════ отправка ═════════════════════════════════════════════
async def send_listing(bot, chat_id: int, l: dict):
    text = fmt_listing(l)
    try:
        if l["photo"] and len(text) <= 1024:
            await bot.send_photo(chat_id, l["photo"], caption=text, parse_mode=ParseMode.HTML)
            return
    except (BadRequest, Forbidden) as e:
        if isinstance(e, Forbidden):
            raise
    except Exception as e:
        log.warning("photo failed: %s", e)
    await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


def pick_for_user(chat_id: int, s: dict, only_new: bool) -> list:
    items = [l for l in db.recent_listings(int(s["age"])) if passes(l, s)]
    if only_new:
        ids, hashes = db.sent_keys(chat_id)
        items = [l for l in items if l["id"] not in ids and l["hash"] not in hashes]
    seen, out = set(), []
    for l in items:                      # убираем дубли-репосты, новые первыми
        if l["hash"] not in seen:
            seen.add(l["hash"])
            out.append(l)
    return out


async def deliver(bot, chat_id: int, items: list) -> int:
    n = 0
    for l in items[:config.MAX_PER_SEND]:
        await send_listing(bot, chat_id, l)
        db.mark_sent(chat_id, l)
        n += 1
        await asyncio.sleep(0.4)
    if len(items) > n:
        await bot.send_message(chat_id, f"Показаны {n} из {len(items)}. Остальные придут в следующий раз "
                                        f"или сузьте выбор в «Фильтры».")
    return n


async def do_search(bot, chat_id: int):
    if chat_id in _searching:
        return
    _searching.add(chat_id)
    try:
        if db.listings_count() == 0:
            await scrape_once(config.FIRST_SCRAPE_PAGES)
        s = db.get_settings(chat_id)
        items = pick_for_user(chat_id, s, only_new=False)
        if items:
            await deliver(bot, chat_id, items)
        else:
            await bot.send_message(chat_id, "😕 Сейчас ничего не найдено. Попробуйте расширить фильтры.")
    except Forbidden:
        db.set_active(chat_id, False)
    except Exception:
        log.exception("search failed %s", chat_id)
    finally:
        _searching.discard(chat_id)


# ══════════ фоновые задачи ═══════════════════════════════════════
async def scrape_once(pages: int = 1):
    total = 0
    for name, city in db.get_channels():
        try:
            items = await asyncio.to_thread(sources.fetch_channel, name, city, pages)
            total += db.save_listings(items)
        except Exception as e:
            log.warning("scrape %s failed: %s", name, e)
        await asyncio.sleep(1)
    log.info("scrape done: %d new listings", total)
    return total


async def scrape_loop():
    first = db.listings_count() == 0
    while True:
        try:
            await scrape_once(config.FIRST_SCRAPE_PAGES if first else 1)
            first = False
            db.cleanup(config.KEEP_DAYS)
        except Exception:
            log.exception("scrape loop")
        await asyncio.sleep(config.SCRAPE_INTERVAL_MIN * 60)


async def notify_loop(app: Application):
    await asyncio.sleep(30)
    while True:
        try:
            for chat_id in db.active_users():
                s = db.get_settings(chat_id)
                iv = int(s["interval"]) * 60
                if time.time() - db.get_last_notified(chat_id) < iv:
                    continue
                items = pick_for_user(chat_id, s, only_new=True)
                try:
                    if items:
                        await deliver(app.bot, chat_id, items)
                    elif iv >= 86400:
                        await app.bot.send_message(chat_id, "Сегодня новых объявлений нет")
                except Forbidden:
                    db.set_active(chat_id, False)
                db.set_last_notified(chat_id)
        except Exception:
            log.exception("notify loop")
        await asyncio.sleep(60)


async def post_init(app: Application):
    _tasks.append(asyncio.create_task(scrape_loop()))
    _tasks.append(asyncio.create_task(notify_loop(app)))


# ══════════ хендлеры ═════════════════════════════════════════════
async def gate(update: Update, ctx):
    chat = update.effective_chat
    if config.ALLOWED_USERS and chat and chat.id not in config.ALLOWED_USERS:
        if update.message:
            await update.message.reply_text(f"⛔ Нет доступа.\nВаш chat_id: {chat.id}")
        raise ApplicationHandlerStop


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.add_user(chat_id, update.effective_user.username or "")
    s = db.get_settings(chat_id)
    await update.message.reply_text(fmt_settings(s), parse_mode=ParseMode.HTML,
                                    reply_markup=main_keyboard(chat_id))
    await update.message.reply_text("Ищу предложения, ожидайте!")
    ctx.application.create_task(do_search(ctx.bot, chat_id))


async def show_filters(update: Update, ctx):
    s = db.get_settings(update.effective_chat.id)
    await update.message.reply_text(fmt_settings(s), parse_mode=ParseMode.HTML, reply_markup=kb_settings())


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    t = (update.message.text or "").strip()
    if t == "Искать":
        ctx.application.create_task(do_search(ctx.bot, chat_id))
    elif t == "Фильтры":
        await show_filters(update, ctx)
    elif t in ("ВКЛ", "ВЫКЛ"):
        db.add_user(chat_id, update.effective_user.username or "") if t == "ВКЛ" else db.set_active(chat_id, False)
        await update.message.reply_text("🔔 Уведомления включены" if t == "ВКЛ" else "🔕 Уведомления выключены",
                                        reply_markup=main_keyboard(chat_id))


async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat_id
    parts = q.data.split(":")
    s = db.get_settings(chat_id)
    kb = None
    if parts[0] == "s":
        db.set_setting(chat_id, parts[1], parts[2])
        if parts[1] == "deal":
            db.set_setting(chat_id, "pmin", 0)
            db.set_setting(chat_id, "pmax", 0)   # диапазоны цен у аренды и покупки разные
        s = db.get_settings(chat_id)
        kb = kb_option(parts[1], s)
    elif parts[0] == "p":
        _, a, z = PRICE_PRESETS[s["deal"]][int(parts[1])]
        db.set_setting(chat_id, "pmin", a)
        db.set_setting(chat_id, "pmax", z)
        s = db.get_settings(chat_id)
        kb = kb_price(s)
    elif parts[0] == "m":
        key = parts[1]
        if key == "back":
            kb = kb_settings()
        elif key == "price":
            kb = kb_price(s)
            if s["deal"] not in PRICE_PRESETS:
                await q.answer("Сначала выберите «Аренда» или «Покупка»", show_alert=True)
                return
        else:
            kb = kb_option(key, s)
    try:
        await q.edit_message_text(fmt_settings(s), parse_mode=ParseMode.HTML, reply_markup=kb)
    except BadRequest:
        pass
    await q.answer()


async def cmd_channels(update: Update, ctx):
    ch = db.get_channels()
    await update.message.reply_text(
        "📡 <b>Каналы-источники</b>\n" + "\n".join(f"• @{n} ({c or '?'})" for n, c in ch) +
        "\n\n/add имя_канала [hrg|ssh] — добавить\n/del имя_канала — удалить", parse_mode=ParseMode.HTML)


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Пример: /add hurghada_rent hrg")
        return
    name = re.sub(r"^(https?://)?(t\.me/)?@?", "", ctx.args[0]).strip("/")
    city = ctx.args[1] if len(ctx.args) > 1 and ctx.args[1] in ("hrg", "ssh") else ""
    if not await asyncio.to_thread(sources.channel_exists, name):
        await update.message.reply_text("Канал не найден или у него нет публичного превью (t.me/s/…).")
        return
    db.add_channel(name, city)
    await update.message.reply_text(f"✅ Добавлен @{name}")
    ctx.application.create_task(scrape_once(config.FIRST_SCRAPE_PAGES))


async def cmd_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = re.sub(r"^(https?://)?(t\.me/)?@?", "", ctx.args[0]).strip("/") if ctx.args else ""
    await update.message.reply_text("Удалён" if db.del_channel(name) else "Такого канала нет")


async def on_error(update, ctx):
    log.error("handler error", exc_info=ctx.error)


def main():
    if not config.TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_TOKEN не задан (.env)")
    db.init_db()
    app = Application.builder().token(config.TELEGRAM_TOKEN).post_init(post_init).build()
    app.add_handler(TypeHandler(Update, gate), group=-1)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("channels", cmd_channels))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("del", cmd_del))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    log.info("Rent bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
