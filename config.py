import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "8651241172:AAHPoKF8-Nxc9ibav7Q9BITnnmFCDRQNWdc")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8278238550").split(",") if x.strip().isdigit()]
DB_FILE = "database.sqlite3"
