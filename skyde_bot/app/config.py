import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 729292013))
ADMIN_WALLET = os.getenv("ADMIN_WALLET", "UQAXdeNPhbL_hQ0oRDOeOxX-gOERgVRdq8sHyZS9jv9yKl2W")

DATABASE_URL = "sqlite+aiosqlite:///skyde.db"



AUTO_DELETE_CONFIG = {
    'enabled': True,
    'delete_previous_bot': True,
    'delete_user_messages': True,
    'delay_user': 1,  # секунды
    'exclude_commands': ['/start', '/help'],  # Не удалять для этих команд
    'exclude_states': [],  # Не удалять в этих состояниях
}