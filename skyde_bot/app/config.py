# Файл bot.py (Исправлено)
import os
from dotenv import load_dotenv

load_dotenv()

# Теперь os.getenv ищет переменные по ИМЕНИ, заданному в .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

DATABASE_URL = "sqlite+aiosqlite:///skyde.db" # SQLite для простоты