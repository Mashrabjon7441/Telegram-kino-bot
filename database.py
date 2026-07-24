import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "movies.db")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if migration is needed (if episodes table does not exist, recreate schema)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes';")
    if not cursor.fetchone():
        cursor.execute("DROP TABLE IF EXISTS movies")
        
    # Create movies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            caption TEXT,
            genre TEXT DEFAULT 'Umumiy',
            views INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0
        )
    """)
    
    # Migrations for movies table columns if existing
    cursor.execute("PRAGMA table_info(movies)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'genre' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN genre TEXT DEFAULT 'Umumiy'")
    if 'views' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN views INTEGER DEFAULT 0")
    if 'is_vip' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN is_vip INTEGER DEFAULT 0")

    # Create episodes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_code TEXT NOT NULL,
            episode_title TEXT NOT NULL,
            file_id TEXT NOT NULL,
            FOREIGN KEY(movie_code) REFERENCES movies(code) ON DELETE CASCADE
        )
    """)
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            referred_by INTEGER,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in cursor.fetchall()]
    if 'referred_by' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")

    # Create channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT NOT NULL
        )
    """)
    # Create admins table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Create ratings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id INTEGER NOT NULL,
            movie_code TEXT NOT NULL,
            rating INTEGER NOT NULL,
            PRIMARY KEY(user_id, movie_code)
        )
    """)
    # Create favorites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            movie_code TEXT NOT NULL,
            PRIMARY KEY(user_id, movie_code)
        )
    """)
    # Create referrals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER PRIMARY KEY
        )
    """)
    # Create premium_users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premium_users (
            user_id INTEGER PRIMARY KEY,
            expire_date TIMESTAMP,
            is_lifetime INTEGER DEFAULT 0
        )
    """)
    # Create support_tickets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            user_text TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create movie_subscriptions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movie_subscriptions (
            user_id INTEGER NOT NULL,
            movie_code TEXT NOT NULL,
            PRIMARY KEY(user_id, movie_code)
        )
    """)
    # Create pending_queue table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_num INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()




def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referred_by))
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_movie(code, title, caption, genre='Umumiy', is_vip=0):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO movies (code, title, caption, genre, views, is_vip)
            VALUES (?, ?, ?, ?, COALESCE((SELECT views FROM movies WHERE code = ?), 0), ?)
        """, (code.strip(), title.strip(), caption.strip() if caption else "", genre.strip(), code.strip(), is_vip))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error saving movie: {e}")
        success = False
    finally:
        conn.close()
    return success

def get_movie(code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, caption, genre, views, is_vip FROM movies WHERE code = ?", (code.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res

def toggle_movie_vip(code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT is_vip FROM movies WHERE code = ?", (code.strip(),))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return False, False
    current_vip = res[0] or 0
    new_vip = 0 if current_vip == 1 else 1
    cursor.execute("UPDATE movies SET is_vip = ? WHERE code = ?", (new_vip, code.strip()))
    conn.commit()
    conn.close()
    return True, bool(new_vip)

def search_movies_by_name(query):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    search = f"%{query.strip()}%"
    cursor.execute("SELECT code, title, genre, views, is_vip FROM movies WHERE title LIKE ? OR caption LIKE ? LIMIT 20", (search, search))
    res = cursor.fetchall()
    conn.close()
    return res

def get_movies_by_genre(genre):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, views, is_vip FROM movies WHERE genre = ? ORDER BY id DESC LIMIT 30", (genre.strip(),))
    res = cursor.fetchall()
    conn.close()
    return res

def get_top_movies(limit=10):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, views, genre, is_vip FROM movies ORDER BY views DESC LIMIT ?", (limit,))
    res = cursor.fetchall()
    conn.close()
    return res

def increment_movie_views(code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code.strip(),))
    conn.commit()
    conn.close()

def add_episode(movie_code, episode_title, file_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO episodes (movie_code, episode_title, file_id)
            VALUES (?, ?, ?)
        """, (movie_code.strip(), episode_title.strip(), file_id.strip()))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error saving episode: {e}")
        success = False
    finally:
        conn.close()
    return success

def get_episodes(movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, episode_title, file_id FROM episodes WHERE movie_code = ?", (movie_code.strip(),))
    res = cursor.fetchall()
    conn.close()
    return res

def get_episode_by_id(episode_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, episode_title, movie_code FROM episodes WHERE id = ?", (episode_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def delete_movie(code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM episodes WHERE movie_code = ?", (code.strip(),))
    cursor.execute("DELETE FROM movies WHERE code = ?", (code.strip(),))
    cursor.execute("DELETE FROM ratings WHERE movie_code = ?", (code.strip(),))
    cursor.execute("DELETE FROM favorites WHERE movie_code = ?", (code.strip(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def delete_episode(episode_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_all_movies():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, views, is_vip FROM movies ORDER BY id DESC")
    res = cursor.fetchall()
    conn.close()
    return res

# ----------------- PREMIUM USERS -----------------

def is_premium_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT expire_date, is_lifetime FROM premium_users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if not res:
        return False
    expire_date_str, is_lifetime = res
    if is_lifetime == 1:
        return True
    if expire_date_str:
        try:
            expire_date = datetime.strptime(expire_date_str, "%Y-%m-%d %H:%M:%S")
            return datetime.now() < expire_date
        except Exception:
            return False
    return False

def add_premium(user_id, days=30, is_lifetime=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if is_lifetime:
        cursor.execute("INSERT OR REPLACE INTO premium_users (user_id, expire_date, is_lifetime) VALUES (?, NULL, 1)", (user_id,))
    else:
        now = datetime.now()
        cursor.execute("SELECT expire_date FROM premium_users WHERE user_id = ? AND is_lifetime = 0", (user_id,))
        res = cursor.fetchone()
        if res and res[0]:
            try:
                current_expire = datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")
                if current_expire > now:
                    now = current_expire
            except Exception:
                pass
        new_expire = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT OR REPLACE INTO premium_users (user_id, expire_date, is_lifetime) VALUES (?, ?, 0)", (user_id, new_expire))
    conn.commit()
    conn.close()

def remove_premium(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_premium_info(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT expire_date, is_lifetime FROM premium_users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    if not res:
        return None
    expire_date_str, is_lifetime = res
    if is_lifetime == 1:
        return "Umrbod (Lifetime 👑)"
    if expire_date_str:
        try:
            expire_date = datetime.strptime(expire_date_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < expire_date:
                return expire_date.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return None

def get_premium_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM premium_users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ----------------- FAVORITES -----------------

def toggle_favorite(user_id, movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
    if cursor.fetchone():
        cursor.execute("DELETE FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
        added = False
    else:
        cursor.execute("INSERT INTO favorites (user_id, movie_code) VALUES (?, ?)", (user_id, movie_code.strip()))
        added = True
    conn.commit()
    conn.close()
    return added

def is_favorite(user_id, movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_favorites(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.code, m.title, m.genre 
        FROM favorites f 
        JOIN movies m ON f.movie_code = m.code 
        WHERE f.user_id = ?
    """, (user_id,))
    res = cursor.fetchall()
    conn.close()
    return res

# ----------------- RATINGS -----------------

def rate_movie(user_id, movie_code, rating):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO ratings (user_id, movie_code, rating)
        VALUES (?, ?, ?)
    """, (user_id, movie_code.strip(), rating))
    conn.commit()
    conn.close()

def get_movie_ratings(movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ratings WHERE movie_code = ? AND rating = 1", (movie_code.strip(),))
    likes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ratings WHERE movie_code = ? AND rating = -1", (movie_code.strip(),))
    dislikes = cursor.fetchone()[0]
    conn.close()
    return likes, dislikes

# ----------------- REFERRALS -----------------

def add_referral(referrer_id, new_user_id):
    if referrer_id == new_user_id:
        return False
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, new_user_id))
        conn.commit()
        success = True
    except Exception:
        success = False
    finally:
        conn.close()
    return success

def get_user_referral_count(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ----------------- SUPPORT TICKETS -----------------

def add_support_ticket(user_id, message_id, user_text):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_tickets (user_id, message_id, user_text) VALUES (?, ?, ?)", (user_id, message_id, user_text))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def get_support_ticket_by_msg(message_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT ticket_id, user_id, user_text FROM support_tickets WHERE message_id = ?", (message_id,))
    res = cursor.fetchone()
    conn.close()
    return res

# ----------------- CHANNELS & SETTINGS -----------------

def add_channel(channel_id, title, invite_link):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO channels (channel_id, title, invite_link)
            VALUES (?, ?, ?)
        """, (channel_id.strip(), title.strip(), invite_link.strip()))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error adding channel: {e}")
        success = False
    finally:
        conn.close()
    return success

def delete_channel(channel_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id.strip(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_channels():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, title, invite_link FROM channels")
    res = cursor.fetchall()
    conn.close()
    return res

def get_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    res = cursor.fetchall()
    conn.close()
    return [row[0] for row in res]

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key.strip(), value.strip()))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else default

def delete_setting(key):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings WHERE key = ?", (key.strip(),))
    conn.commit()
    conn.close()

def add_db_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_db_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_db_admins():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    res = cursor.fetchall()
    conn.close()
    return [r[0] for r in res]

def is_db_admin(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_vip_movies():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, views FROM movies WHERE is_vip = 1 ORDER BY id DESC")
    res = cursor.fetchall()
    conn.close()
    return res

def set_movie_vip(code, is_vip):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE movies SET is_vip = ? WHERE code = ?", (1 if is_vip else 0, code.strip()))
    conn.commit()
    found = cursor.rowcount > 0
    conn.close()
    return found


# ----------------- MOVIE SUBSCRIPTIONS & RANDOM MOVIE -----------------

def toggle_movie_subscription(user_id, movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
    if cursor.fetchone():
        cursor.execute("DELETE FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
        subscribed = False
    else:
        cursor.execute("INSERT INTO movie_subscriptions (user_id, movie_code) VALUES (?, ?)", (user_id, movie_code.strip()))
        subscribed = True
    conn.commit()
    conn.close()
    return subscribed

def is_movie_subscribed(user_id, movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_movie_subscribers(movie_code):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM movie_subscriptions WHERE movie_code = ?", (movie_code.strip(),))
    res = cursor.fetchall()
    conn.close()
    return [r[0] for r in res]

def get_random_movie():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, caption, genre, views, is_vip FROM movies ORDER BY RANDOM() LIMIT 1")
    res = cursor.fetchone()
    conn.close()
    return res

def get_db_path():
    return DB_NAME

def restore_db_from_bytes(data):
    try:
        with open(DB_NAME, 'wb') as f:
            f.write(data)
        init_db()
        return True
    except Exception as e:
        print(f"Error restoring DB: {e}")
        return False

def trigger_auto_backup(bot_instance):
    # Database changes are saved locally in movies.db
    pass


# ----------------- PENDING QUEUE HELPERS -----------------

def add_to_pending_queue(file_id, title="", caption=""):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(queue_num), 0) + 1 FROM pending_queue")
    next_num = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO pending_queue (queue_num, file_id, title, caption, status) VALUES (?, ?, ?, ?, 'pending')",
        (next_num, file_id, title, caption)
    )
    conn.commit()
    conn.close()
    return next_num

def get_pending_queue_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pending_queue WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_next_pending_video():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, queue_num, file_id, title, caption FROM pending_queue WHERE status = 'pending' ORDER BY queue_num ASC LIMIT 1")
    res = cursor.fetchone()
    conn.close()
    return res


def mark_pending_fulfilled(pending_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE pending_queue SET status = 'fulfilled' WHERE id = ?", (pending_id,))
    conn.commit()
    conn.close()

def clear_pending_queue():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_queue WHERE status = 'pending'")
    conn.commit()
    conn.close()




