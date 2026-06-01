import sqlite3, json, time, logging
from datetime import datetime, timedelta
from config import DB_FILE, ADMIN_IDS
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._init_settings()
    
    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, coins REAL DEFAULT 0, total_coins_earned REAL DEFAULT 0, referrals_done INTEGER DEFAULT 0, referrals_today INTEGER DEFAULT 0, last_referral_date TEXT, banned INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0, joined_at TEXT, last_active TEXT, total_links_shared INTEGER DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS referral_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, bot_username TEXT, referral_code TEXT, link_shared TEXT, timestamp TEXT, status TEXT DEFAULT 'pending', coins_earned REAL DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS broadcast_history (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, message TEXT, target TEXT, sent_to INTEGER DEFAULT 0, timestamp TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS force_channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_username TEXT UNIQUE, channel_title TEXT, added_by INTEGER, added_at TEXT)""")
        self.conn.commit()
    
    def _init_settings(self):
        defaults = {"coins_per_referral": "10", "price_per_coin": "1.0", "min_referrals_per_day": "1", "max_referrals_per_day": "5", "force_join_channels": "[]"}
        c = self.conn.cursor()
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()
    
    def get_or_create_user(self, user_id, username=None, first_name=None, last_name=None):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        if not user:
            now = datetime.now().isoformat()
            is_admin = 1 if user_id in ADMIN_IDS else 0
            c.execute("INSERT INTO users (user_id, username, first_name, last_name, joined_at, last_active, is_admin) VALUES (?,?,?,?,?,?,?)", (user_id, username, first_name, last_name, now, now, is_admin))
            self.conn.commit()
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()
        else:
            c.execute("UPDATE users SET last_active=?, username=?, first_name=?, last_name=? WHERE user_id=?", (datetime.now().isoformat(), username, first_name, last_name, user_id))
            self.conn.commit()
        return dict(user) if user else None
    
    def get_user(self, user_id):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None
    
    def get_all_users(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users ORDER BY joined_at DESC")
        return [dict(r) for r in c.fetchall()]
    
    def get_user_count(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        return c.fetchone()[0]
    
    def add_coins(self, uid, amt):
        c = self.conn.cursor()
        c.execute("UPDATE users SET coins=coins+?, total_coins_earned=total_coins_earned+? WHERE user_id=?", (amt, amt, uid))
        self.conn.commit()
        return c.rowcount > 0
    
    def remove_coins(self, uid, amt):
        c = self.conn.cursor()
        c.execute("UPDATE users SET coins=MAX(0, coins-?) WHERE user_id=?", (amt, uid))
        self.conn.commit()
        return c.rowcount > 0
    
    def set_coins(self, uid, amt):
        c = self.conn.cursor()
        c.execute("UPDATE users SET coins=? WHERE user_id=?", (amt, uid))
        self.conn.commit()
        return c.rowcount > 0
    
    def log_referral_link(self, uid, bot, code, link):
        c = self.conn.cursor()
        c.execute("INSERT INTO referral_logs (user_id, bot_username, referral_code, link_shared, timestamp) VALUES (?,?,?,?,?)", (uid, bot, code, link, datetime.now().isoformat()))
        c.execute("UPDATE users SET total_links_shared=total_links_shared+1 WHERE user_id=?", (uid,))
        self.conn.commit()
        return c.lastrowid
    
    def complete_referral(self, log_id, coins):
        c = self.conn.cursor()
        c.execute("UPDATE referral_logs SET status='completed', coins_earned=? WHERE id=?", (coins, log_id))
        c.execute("SELECT user_id FROM referral_logs WHERE id=?", (log_id,))
        log = c.fetchone()
        if log:
            uid = log[0]
            today = datetime.now().strftime("%Y-%m-%d")
            c.execute("UPDATE users SET coins=coins+?, total_coins_earned=total_coins_earned+?, referrals_done=referrals_done+1, referrals_today=referrals_today+1, last_referral_date=? WHERE user_id=?", (coins, coins, today, uid))
        self.conn.commit()
        return log[0] if log else None
    
    def get_user_referral_logs(self, uid, limit=20):
        c = self.conn.cursor()
        c.execute("SELECT * FROM referral_logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (uid, limit))
        return [dict(r) for r in c.fetchall()]
    
    def get_all_referral_logs(self, limit=50):
        c = self.conn.cursor()
        c.execute("SELECT * FROM referral_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]
    
    def get_user_today_referrals(self, uid):
        c = self.conn.cursor()
        c.execute("SELECT referrals_today FROM users WHERE user_id=?", (uid,))
        r = c.fetchone()
        return r[0] if r else 0
    
    def ban_user(self, uid):
        c = self.conn.cursor()
        c.execute("UPDATE users SET banned=1 WHERE user_id=?", (uid,))
        self.conn.commit()
        return c.rowcount > 0
    
    def unban_user(self, uid):
        c = self.conn.cursor()
        c.execute("UPDATE users SET banned=0 WHERE user_id=?", (uid,))
        self.conn.commit()
        return c.rowcount > 0
    
    def is_banned(self, uid):
        c = self.conn.cursor()
        c.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
        r = c.fetchone()
        return r and r[0] == 1
    
    def get_setting(self, key, default=None):
        c = self.conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        r = c.fetchone()
        if not r: return default
        v = r[0]
        try: return json.loads(v)
        except: pass
        try:
            if '.' in v: return float(v)
            return int(v)
        except: pass
        return v
    
    def set_setting(self, key, value):
        if isinstance(value, (list, dict)): value = json.dumps(value)
        elif not isinstance(value, str): value = str(value)
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        self.conn.commit()
    
    def add_force_channel(self, username, title="", added_by=0):
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO force_channels (channel_username, channel_title, added_by, added_at) VALUES (?,?,?,?)", (username, title, added_by, datetime.now().isoformat()))
            self.conn.commit()
            return True
        except: return False
    
    def remove_force_channel(self, username):
        c = self.conn.cursor()
        c.execute("DELETE FROM force_channels WHERE channel_username=?", (username,))
        self.conn.commit()
        return c.rowcount > 0
    
    def get_force_channels(self):
        c = self.conn.cursor()
        c.execute("SELECT * FROM force_channels")
        return [dict(r) for r in c.fetchall()]
    
    def log_broadcast(self, admin_id, msg, target, sent_to):
        c = self.conn.cursor()
        c.execute("INSERT INTO broadcast_history (admin_id, message, target, sent_to, timestamp) VALUES (?,?,?,?,?)", (admin_id, msg, target, sent_to, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_user_stats(self):
        c = self.conn.cursor()
        tu = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        at = c.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", ((datetime.now()-timedelta(days=1)).isoformat(),)).fetchone()[0]
        tr = c.execute("SELECT SUM(referrals_done) FROM users").fetchone()[0] or 0
        tc = c.execute("SELECT SUM(total_coins_earned) FROM users").fetchone()[0] or 0
        return {"total_users": tu, "active_today": at, "total_referrals": tr, "total_coins": tc}
