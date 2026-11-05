"""Одноразовый вход в Telegram-аккаунт для чтения групп. Запуск: python login.py
Спросит номер телефона и код из Telegram. Создаст data/user.session (никому не передавайте)."""
import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv()
os.makedirs("data", exist_ok=True)
with TelegramClient("data/user", int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as c:
    me = c.get_me()
    print("Вход выполнен:", me.first_name, me.username)
