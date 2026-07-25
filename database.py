import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "movies.db")

DATABASE_URL = os.environ.get("DATABASE_URL")
IS_POSTGRES = False

if DATABASE_URL:
    try:
        import psycopg2
        import psycopg2.extras
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        IS_POSTGRES = True
        print("🐘 Cloud PostgreSQL ma'lumotlar bazasiga ulanish yoqildi (Supabase/Neon)...")
    except ImportError:
        print("⚠️ psycopg2-binary o'rnatilmagan, SQLite rejimida ishlanmoqda.")

def get_db():
    if IS_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    else:
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        return conn

import time

def execute_query(query, params=(), commit=True, fetchone=False, fetchall=False, return_lastid=False):
    for attempt in range(2):
        try:
            conn = get_db()
            cur = conn.cursor()
            sql = query
            if IS_POSTGRES:
                sql = sql.replace('?', '%s')
                if 'INSERT OR IGNORE INTO users' in sql:
                    sql = "INSERT INTO users (user_id, username, referred_by) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING"
                elif 'INSERT OR IGNORE INTO admins' in sql:
                    sql = "INSERT INTO admins (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING"
                elif 'INSERT OR REPLACE INTO settings' in sql:
                    sql = "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                elif 'INSERT OR REPLACE INTO channels' in sql:
                    sql = "INSERT INTO channels (channel_id, title, invite_link) VALUES (%s, %s, %s) ON CONFLICT (channel_id) DO UPDATE SET title = EXCLUDED.title, invite_link = EXCLUDED.invite_link"
                elif 'INSERT OR REPLACE INTO ratings' in sql:
                    sql = "INSERT INTO ratings (user_id, movie_code, rating) VALUES (%s, %s, %s) ON CONFLICT (user_id, movie_code) DO UPDATE SET rating = EXCLUDED.rating"
                elif 'INSERT OR REPLACE INTO premium_users' in sql:
                    if 'NULL' in sql:
                        sql = "INSERT INTO premium_users (user_id, expire_date, is_lifetime) VALUES (%s, NULL, 1) ON CONFLICT (user_id) DO UPDATE SET expire_date = NULL, is_lifetime = 1"
                    else:
                        sql = "INSERT INTO premium_users (user_id, expire_date, is_lifetime) VALUES (%s, %s, 0) ON CONFLICT (user_id) DO UPDATE SET expire_date = EXCLUDED.expire_date, is_lifetime = 0"
                elif 'INSERT OR REPLACE INTO movies' in sql:
                    sql = """
                        INSERT INTO movies (code, title, caption, genre, views, is_vip, language)
                        VALUES (%s, %s, %s, %s, COALESCE((SELECT views FROM movies WHERE code = %s), 0), %s, %s)
                        ON CONFLICT (code) DO UPDATE SET
                        title = EXCLUDED.title, caption = EXCLUDED.caption, genre = EXCLUDED.genre,
                        is_vip = EXCLUDED.is_vip, language = EXCLUDED.language
                    """

            if return_lastid and IS_POSTGRES and 'RETURNING' not in sql.upper():
                if 'INSERT INTO support_tickets' in sql:
                    sql += " RETURNING ticket_id"
                elif 'INSERT INTO pending_queue' in sql:
                    sql += " RETURNING id"

            cur.execute(sql, params)
            if commit:
                conn.commit()

            if return_lastid:
                if IS_POSTGRES:
                    lastid = cur.fetchone()[0]
                else:
                    lastid = cur.lastrowid
                conn.close()
                return lastid

            if fetchone:
                res = cur.fetchone()
                conn.close()
                return tuple(res) if res else None
            if fetchall:
                res = cur.fetchall()
                conn.close()
                return [tuple(r) for r in res] if res else []
            res_cnt = cur.rowcount
            conn.close()
            return res_cnt
        except Exception as e:
            if attempt == 1:
                print(f"Database query exception: {e}")
                raise e
            time.sleep(0.3)

def migrate_sqlite_to_postgres():
    if not IS_POSTGRES or not os.path.exists(DB_NAME):
        return

    try:
        sq_conn = sqlite3.connect(DB_NAME)
        sq_cur = sq_conn.cursor()

        # Check local movies table
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='movies'")
        if not sq_cur.fetchone():
            sq_conn.close()
            return

        sq_cur.execute("SELECT code, title, caption, genre, views, is_vip, language FROM movies")
        local_movies = sq_cur.fetchall()

        if not local_movies:
            sq_conn.close()
            return

        print(f"📦 [Auto-Migration] Found {len(local_movies)} movies in local SQLite. Migrating to Cloud PostgreSQL...")

        pg_conn = get_db()
        pg_cur = pg_conn.cursor()

        migrated_m_cnt = 0
        for row in local_movies:
            code = row[0]
            title = row[1]
            caption = row[2] if len(row) > 2 else ""
            genre = row[3] if len(row) > 3 else "Umumiy"
            views = row[4] if len(row) > 4 else 0
            is_vip = row[5] if len(row) > 5 else 0
            lang = row[6] if len(row) > 6 else "🇺🇿 O'zbekcha"

            if not code or not title:
                continue

            pg_cur.execute("""
                INSERT INTO movies (code, title, caption, genre, views, is_vip, language)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title, caption = EXCLUDED.caption, genre = EXCLUDED.genre,
                is_vip = EXCLUDED.is_vip, language = EXCLUDED.language
            """, (str(code).strip(), str(title).strip(), str(caption or "").strip(), str(genre or "Umumiy").strip(), views or 0, is_vip or 0, str(lang or "🇺🇿 O'zbekcha").strip()))
            migrated_m_cnt += 1

        # Check local episodes table
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT movie_code, episode_title, file_id FROM episodes")
            local_episodes = sq_cur.fetchall()
            for m_code, ep_title, file_id in local_episodes:
                if not m_code or not file_id:
                    continue
                pg_cur.execute("INSERT INTO episodes (movie_code, episode_title, file_id) VALUES (%s, %s, %s)", (str(m_code).strip(), str(ep_title).strip(), str(file_id).strip()))

        # Check local settings table
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT key, value FROM settings")
            local_settings = sq_cur.fetchall()
            for key, val in local_settings:
                if key and val:
                    pg_cur.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (str(key).strip(), str(val).strip()))

        # Check local channels table
        sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channels'")
        if sq_cur.fetchone():
            sq_cur.execute("SELECT channel_id, title, invite_link FROM channels")
            local_channels = sq_cur.fetchall()
            for ch_id, title, invite_link in local_channels:
                if ch_id and title:
                    pg_cur.execute("INSERT INTO channels (channel_id, title, invite_link) VALUES (%s, %s, %s) ON CONFLICT (channel_id) DO UPDATE SET title = EXCLUDED.title, invite_link = EXCLUDED.invite_link", (str(ch_id).strip(), str(title).strip(), str(invite_link).strip()))

        pg_conn.commit()
        pg_conn.close()
        sq_conn.close()
        print(f"🎉 [Auto-Migration Success] Successfully migrated {migrated_m_cnt} movies into Cloud PostgreSQL!")
    except Exception as e:
        print(f"Auto-Migration error: {e}")

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    if IS_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                title TEXT NOT NULL,
                caption TEXT,
                genre VARCHAR(100) DEFAULT 'Umumiy',
                views INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                language VARCHAR(100) DEFAULT '🇺🇿 O''zbekcha'
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id SERIAL PRIMARY KEY,
                movie_code VARCHAR(50) NOT NULL,
                episode_title TEXT NOT NULL,
                file_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                referred_by BIGINT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS channels (
                id SERIAL PRIMARY KEY,
                channel_id VARCHAR(100) UNIQUE NOT NULL,
                title TEXT NOT NULL,
                invite_link TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admins (
                user_id BIGINT PRIMARY KEY,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS ratings (
                user_id BIGINT NOT NULL,
                movie_code VARCHAR(50) NOT NULL,
                rating INTEGER NOT NULL,
                PRIMARY KEY(user_id, movie_code)
            );
            CREATE TABLE IF NOT EXISTS favorites (
                user_id BIGINT NOT NULL,
                movie_code VARCHAR(50) NOT NULL,
                PRIMARY KEY(user_id, movie_code)
            );
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id BIGINT PRIMARY KEY,
                expire_date TIMESTAMP,
                is_lifetime INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                user_text TEXT,
                status VARCHAR(20) DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS movie_subscriptions (
                user_id BIGINT NOT NULL,
                movie_code VARCHAR(50) NOT NULL,
                PRIMARY KEY(user_id, movie_code)
            );
            CREATE TABLE IF NOT EXISTS pending_queue (
                id SERIAL PRIMARY KEY,
                queue_num INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                title TEXT DEFAULT '',
                caption TEXT DEFAULT '',
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_movies_code ON movies (code);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_channels_id ON channels (channel_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_settings_key ON settings (key);
        """)
        conn.commit()
        conn.close()
        migrate_sqlite_to_postgres()
        return

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes';")
    if not cursor.fetchone():
        cursor.execute("DROP TABLE IF EXISTS movies")

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
    cursor.execute("PRAGMA table_info(movies)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'genre' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN genre TEXT DEFAULT 'Umumiy'")
    if 'views' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN views INTEGER DEFAULT 0")
    if 'is_vip' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN is_vip INTEGER DEFAULT 0")
    if 'language' not in columns:
        cursor.execute("ALTER TABLE movies ADD COLUMN language TEXT DEFAULT '🇺🇿 O''zbekcha'")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_code TEXT NOT NULL,
            episode_title TEXT NOT NULL,
            file_id TEXT NOT NULL
        )
    """)
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id INTEGER NOT NULL,
            movie_code TEXT NOT NULL,
            rating INTEGER NOT NULL,
            PRIMARY KEY(user_id, movie_code)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            movie_code TEXT NOT NULL,
            PRIMARY KEY(user_id, movie_code)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premium_users (
            user_id INTEGER PRIMARY KEY,
            expire_date TIMESTAMP,
            is_lifetime INTEGER DEFAULT 0
        )
    """)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movie_subscriptions (
            user_id INTEGER NOT NULL,
            movie_code TEXT NOT NULL,
            PRIMARY KEY(user_id, movie_code)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_num INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            caption TEXT DEFAULT '',
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username, referred_by=None):
    execute_query("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referred_by))

def get_users_count():
    res = execute_query("SELECT COUNT(*) FROM users", fetchone=True)
    return res[0] if res else 0

def add_movie(code, title, caption, genre='Umumiy', is_vip=0, language="🇺🇿 O'zbekcha"):
    try:
        code_str = code.strip()
        title_str = title.strip()
        caption_str = caption.strip() if caption else ""
        genre_str = genre.strip()
        lang_str = language.strip()

        if IS_POSTGRES:
            query = """
                INSERT INTO movies (code, title, caption, genre, is_vip, language)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                title = EXCLUDED.title,
                caption = EXCLUDED.caption,
                genre = EXCLUDED.genre,
                is_vip = EXCLUDED.is_vip,
                language = EXCLUDED.language
            """
            conn = get_db()
            cur = conn.cursor()
            cur.execute(query, (code_str, title_str, caption_str, genre_str, is_vip, lang_str))
            conn.commit()
            conn.close()
            return True
        else:
            execute_query("""
                INSERT OR REPLACE INTO movies (code, title, caption, genre, views, is_vip, language)
                VALUES (?, ?, ?, ?, COALESCE((SELECT views FROM movies WHERE code = ?), 0), ?, ?)
            """, (code_str, title_str, caption_str, genre_str, code_str, is_vip, lang_str))
            return True
    except Exception as e:
        print(f"Error saving movie: {e}")
        return False

def get_movie(code):
    return execute_query("SELECT code, title, caption, genre, views, is_vip, language FROM movies WHERE code = ?", (code.strip(),), fetchone=True)

def toggle_movie_vip(code):
    res = execute_query("SELECT is_vip FROM movies WHERE code = ?", (code.strip(),), fetchone=True)
    if not res:
        return False, False
    current_vip = res[0] or 0
    new_vip = 0 if current_vip == 1 else 1
    execute_query("UPDATE movies SET is_vip = ? WHERE code = ?", (new_vip, code.strip()))
    return True, bool(new_vip)

def set_movie_vip(code, is_vip=True):
    new_vip = 1 if is_vip else 0
    execute_query("UPDATE movies SET is_vip = ? WHERE code = ?", (new_vip, code.strip()))

def movie_exists_by_exact_title(title):
    res = execute_query("SELECT 1 FROM movies WHERE title = ?", (title.strip(),), fetchone=True)
    return res is not None

def search_movies_by_name(query):
    search = f"%{query.strip()}%"
    return execute_query("SELECT code, title, genre, views, is_vip FROM movies WHERE title LIKE ? OR caption LIKE ? LIMIT 20", (search, search), fetchall=True)

def get_movies_by_genre(genre):
    return execute_query("SELECT code, title, genre, views, is_vip FROM movies WHERE genre = ? ORDER BY id DESC LIMIT 30", (genre.strip(),), fetchall=True)

def get_movies_by_language(language):
    return execute_query("SELECT code, title, genre, views, is_vip FROM movies WHERE language LIKE ? ORDER BY id DESC LIMIT 30", (f"%{language.strip()}%",), fetchall=True)

def get_top_movies(limit=10):
    return execute_query("SELECT code, title, genre, views, is_vip FROM movies ORDER BY views DESC LIMIT ?", (limit,), fetchall=True)

def increment_movie_views(code):
    execute_query("UPDATE movies SET views = views + 1 WHERE code = ?", (code.strip(),))

def add_episode(movie_code, episode_title, file_id):
    try:
        code_str = movie_code.strip()
        title_str = episode_title.strip()
        file_str = file_id.strip()

        if IS_POSTGRES:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO episodes (movie_code, episode_title, file_id) VALUES (%s, %s, %s)", (code_str, title_str, file_str))
            conn.commit()
            conn.close()
            return True
        else:
            execute_query("INSERT INTO episodes (movie_code, episode_title, file_id) VALUES (?, ?, ?)", (code_str, title_str, file_str))
            return True
    except Exception as e:
        print(f"Error saving episode: {e}")
        return False

def find_movie_by_base_title(base_title):
    clean = base_title.strip()
    if not clean:
        return None
    res = execute_query("SELECT code, title FROM movies WHERE title = ? OR title = ?", (clean, f"[📺 SERIAL] {clean}"), fetchone=True)
    if res:
        return res
    search = f"%{clean}%"
    res = execute_query("SELECT code, title FROM movies WHERE title LIKE ? ORDER BY id ASC", (search,), fetchone=True)
    return res

def get_episodes(movie_code):
    res = execute_query("SELECT id, episode_title, file_id FROM episodes WHERE movie_code = ? ORDER BY id ASC", (movie_code.strip(),), fetchall=True)
    if not res:
        return []

    import re
    def ep_sort_key(item):
        ep_title = item[1]
        numbers = re.findall(r'\d+', ep_title)
        if numbers:
            return (0, int(numbers[0]))
        return (1, item[0])

    return sorted(res, key=ep_sort_key)

def get_movie_episodes(movie_code):
    return get_episodes(movie_code)

def get_episode_by_id(episode_id):
    return execute_query("SELECT file_id, episode_title, movie_code FROM episodes WHERE id = ?", (episode_id,), fetchone=True)

def delete_movie(code):
    execute_query("DELETE FROM episodes WHERE movie_code = ?", (code.strip(),))
    res = execute_query("DELETE FROM movies WHERE code = ?", (code.strip(),))
    execute_query("DELETE FROM ratings WHERE movie_code = ?", (code.strip(),))
    execute_query("DELETE FROM favorites WHERE movie_code = ?", (code.strip(),))
    return res > 0

def delete_episode(episode_id):
    res = execute_query("DELETE FROM episodes WHERE id = ?", (episode_id,))
    return res > 0

def get_all_movies():
    return execute_query("SELECT code, title, genre, views, is_vip FROM movies ORDER BY id DESC", fetchall=True)

def is_premium_user(user_id):
    res = execute_query("SELECT expire_date, is_lifetime FROM premium_users WHERE user_id = ?", (user_id,), fetchone=True)
    if not res:
        return False
    expire_date_str, is_lifetime = res
    if is_lifetime == 1:
        return True
    if expire_date_str:
        try:
            if isinstance(expire_date_str, datetime):
                return datetime.now() < expire_date_str
            expire_date = datetime.strptime(str(expire_date_str), "%Y-%m-%d %H:%M:%S")
            return datetime.now() < expire_date
        except Exception:
            return False
    return False

def add_premium(user_id, days=30, is_lifetime=False):
    if is_lifetime:
        execute_query("INSERT OR REPLACE INTO premium_users (user_id, expire_date, is_lifetime) VALUES (?, NULL, 1)", (user_id,))
    else:
        now = datetime.now()
        res = execute_query("SELECT expire_date FROM premium_users WHERE user_id = ? AND is_lifetime = 0", (user_id,), fetchone=True)
        if res and res[0]:
            try:
                if isinstance(res[0], datetime):
                    current_expire = res[0]
                else:
                    current_expire = datetime.strptime(str(res[0]), "%Y-%m-%d %H:%M:%S")
                if current_expire > now:
                    now = current_expire
            except Exception:
                pass
        new_expire = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        execute_query("INSERT OR REPLACE INTO premium_users (user_id, expire_date, is_lifetime) VALUES (?, ?, 0)", (user_id, new_expire))

def remove_premium(user_id):
    res = execute_query("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
    return res > 0

def get_premium_info(user_id):
    res = execute_query("SELECT expire_date, is_lifetime FROM premium_users WHERE user_id = ?", (user_id,), fetchone=True)
    if not res:
        return None
    expire_date_str, is_lifetime = res
    if is_lifetime == 1:
        return "Umrbod (Lifetime 👑)"
    if expire_date_str:
        try:
            if isinstance(expire_date_str, datetime):
                expire_date = expire_date_str
            else:
                expire_date = datetime.strptime(str(expire_date_str), "%Y-%m-%d %H:%M:%S")
            if datetime.now() < expire_date:
                return expire_date.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return None

def get_premium_count():
    res = execute_query("SELECT COUNT(*) FROM premium_users", fetchone=True)
    return res[0] if res else 0

def toggle_favorite(user_id, movie_code):
    res = execute_query("SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()), fetchone=True)
    if res:
        execute_query("DELETE FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
        return False
    else:
        execute_query("INSERT INTO favorites (user_id, movie_code) VALUES (?, ?)", (user_id, movie_code.strip()))
        return True

def is_favorite(user_id, movie_code):
    res = execute_query("SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()), fetchone=True)
    return res is not None

def get_favorites(user_id):
    return execute_query("""
        SELECT m.code, m.title, m.genre 
        FROM favorites f 
        JOIN movies m ON f.movie_code = m.code 
        WHERE f.user_id = ?
    """, (user_id,), fetchall=True)

def rate_movie(user_id, movie_code, rating):
    execute_query("INSERT OR REPLACE INTO ratings (user_id, movie_code, rating) VALUES (?, ?, ?)", (user_id, movie_code.strip(), rating))

def get_movie_ratings(movie_code):
    res1 = execute_query("SELECT COUNT(*) FROM ratings WHERE movie_code = ? AND rating = 1", (movie_code.strip(),), fetchone=True)
    res2 = execute_query("SELECT COUNT(*) FROM ratings WHERE movie_code = ? AND rating = -1", (movie_code.strip(),), fetchone=True)
    likes = res1[0] if res1 else 0
    dislikes = res2[0] if res2 else 0
    return likes, dislikes

def add_referral(referrer_id, new_user_id):
    if referrer_id == new_user_id:
        return False
    try:
        execute_query("INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (referrer_id, new_user_id))
        return True
    except Exception:
        return False

def get_user_referral_count(user_id):
    res = execute_query("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,), fetchone=True)
    return res[0] if res else 0

def add_support_ticket(user_id, message_id, user_text):
    return execute_query("INSERT INTO support_tickets (user_id, message_id, user_text) VALUES (?, ?, ?)", (user_id, message_id, user_text), return_lastid=True)

def get_support_ticket_by_msg(message_id):
    return execute_query("SELECT ticket_id, user_id, user_text FROM support_tickets WHERE message_id = ?", (message_id,), fetchone=True)

def add_channel(channel_id, title, invite_link):
    try:
        execute_query("INSERT OR REPLACE INTO channels (channel_id, title, invite_link) VALUES (?, ?, ?)", (channel_id.strip(), title.strip(), invite_link.strip()))
        return True
    except Exception as e:
        print(f"Error adding channel: {e}")
        return False

def delete_channel(channel_id):
    res = execute_query("DELETE FROM channels WHERE channel_id = ?", (channel_id.strip(),))
    return res > 0

def get_channels():
    return execute_query("SELECT channel_id, title, invite_link FROM channels", fetchall=True)

def get_users():
    res = execute_query("SELECT user_id FROM users", fetchall=True)
    return [row[0] for row in res]

def set_setting(key, value):
    execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key.strip(), value.strip()))

def get_setting(key, default=None):
    res = execute_query("SELECT value FROM settings WHERE key = ?", (key.strip(),), fetchone=True)
    return res[0] if res else default

def delete_setting(key):
    execute_query("DELETE FROM settings WHERE key = ?", (key.strip(),))

def add_db_admin(user_id):
    execute_query("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))

def remove_db_admin(user_id):
    res = execute_query("DELETE FROM admins WHERE user_id = ?", (user_id,))
    return res > 0

def get_db_admins():
    res = execute_query("SELECT user_id FROM admins", fetchall=True)
    return [row[0] for row in res]

def toggle_movie_subscription(user_id, movie_code):
    res = execute_query("SELECT 1 FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()), fetchone=True)
    if res:
        execute_query("DELETE FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
        return False
    else:
        execute_query("INSERT INTO movie_subscriptions (user_id, movie_code) VALUES (?, ?)", (user_id, movie_code.strip()))
        return True

def is_movie_subscribed(user_id, movie_code):
    res = execute_query("SELECT 1 FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()), fetchone=True)
    return res is not None

def get_movie_subscribers(movie_code):
    res = execute_query("SELECT user_id FROM movie_subscriptions WHERE movie_code = ?", (movie_code.strip(),), fetchall=True)
    return [r[0] for r in res]

def get_random_movie():
    return execute_query("SELECT code, title, caption, genre, views, is_vip FROM movies ORDER BY RANDOM() LIMIT 1", fetchone=True)

def get_db_path():
    return DB_NAME

def restore_db_from_bytes(data):
    if IS_POSTGRES:
        print("ℹ️ Cloud PostgreSQL rejimida fayldan tiklash o'rniga tashqi DB ishlatilmoqda.")
        return True
    try:
        with open(DB_NAME, 'wb') as f:
            f.write(data)
        init_db()
        return True
    except Exception as e:
        print(f"Error restoring DB: {e}")
        return False

def trigger_auto_backup(bot_instance):
    if IS_POSTGRES:
        return
    try:
        import config
        if not bot_instance or not config.ADMIN_IDS:
            return

        admin_id = config.ADMIN_IDS[0]
        if os.path.exists(DB_NAME):
            with open(DB_NAME, 'rb') as f:
                sent_msg = bot_instance.send_document(
                    admin_id,
                    f,
                    caption="💾 **AUTOMATIC CLOUD BACKUP**\n\nDatabase state backed up safely to Telegram Cloud.",
                    visible_file_name="movies_backup.db"
                )
                if sent_msg and sent_msg.document:
                    file_id = sent_msg.document.file_id
                    set_setting('latest_backup_file_id', file_id)
                    print(f"💾 [Cloud Backup Success] Saved backup file_id: {file_id[:15]}...")
    except Exception as e:
        print(f"⚠️ Cloud Backup Error: {e}")

def add_to_pending_queue(file_id, title="", caption=""):
    res = execute_query("SELECT COALESCE(MAX(queue_num), 0) + 1 FROM pending_queue", fetchone=True)
    next_num = res[0] if res else 1
    execute_query(
        "INSERT INTO pending_queue (queue_num, file_id, title, caption, status) VALUES (?, ?, ?, ?, 'pending')",
        (next_num, file_id, title, caption)
    )
    return next_num

def get_pending_queue_count():
    res = execute_query("SELECT COUNT(*) FROM pending_queue WHERE status = 'pending'", fetchone=True)
    return res[0] if res else 0

def get_next_pending_video():
    return execute_query("SELECT id, queue_num, file_id, title, caption FROM pending_queue WHERE status = 'pending' ORDER BY queue_num ASC LIMIT 1", fetchone=True)

def mark_pending_fulfilled(pending_id):
    execute_query("UPDATE pending_queue SET status = 'fulfilled' WHERE id = ?", (pending_id,))

def clear_pending_queue():
    execute_query("DELETE FROM pending_queue WHERE status = 'pending'")





def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", (user_id, username, referred_by))
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_movie(code, title, caption, genre='Umumiy', is_vip=0, language="🇺🇿 O'zbekcha"):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO movies (code, title, caption, genre, views, is_vip, language)
            VALUES (?, ?, ?, ?, COALESCE((SELECT views FROM movies WHERE code = ?), 0), ?, ?)
        """, (code.strip(), title.strip(), caption.strip() if caption else "", genre.strip(), code.strip(), is_vip, language.strip()))
        conn.commit()
        success = True
    except Exception as e:
        print(f"Error saving movie: {e}")
        success = False
    finally:
        conn.close()
    return success

def get_movie(code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, caption, genre, views, is_vip, language FROM movies WHERE code = ?", (code.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res

def toggle_movie_vip(code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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

def movie_exists_by_exact_title(title):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM movies WHERE title = ?", (title.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def search_movies_by_name(query):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    search = f"%{query.strip()}%"
    cursor.execute("SELECT code, title, genre, views, is_vip, language FROM movies WHERE title LIKE ? OR caption LIKE ? LIMIT 20", (search, search))
    res = cursor.fetchall()
    conn.close()
    return res


def get_movies_by_genre(genre):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, views, is_vip, language FROM movies WHERE genre = ? ORDER BY id DESC LIMIT 30", (genre.strip(),))
    res = cursor.fetchall()
    conn.close()
    return res

def get_movies_by_language(language):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, views, is_vip FROM movies WHERE language LIKE ? ORDER BY id DESC LIMIT 30", (f"%{language.strip()}%",))
    res = cursor.fetchall()
    conn.close()
    return res

def get_top_movies(limit=10):

    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, views, genre, is_vip FROM movies ORDER BY views DESC LIMIT ?", (limit,))
    res = cursor.fetchall()
    conn.close()
    return res

def increment_movie_views(code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (code.strip(),))
    conn.commit()
    conn.close()

def add_episode(movie_code, episode_title, file_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT id, episode_title, file_id FROM episodes WHERE movie_code = ?", (movie_code.strip(),))
    res = cursor.fetchall()
    conn.close()
    return res

def get_episode_by_id(episode_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, episode_title, movie_code FROM episodes WHERE id = ?", (episode_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def delete_movie(code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_all_movies():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, views, is_vip FROM movies ORDER BY id DESC")
    res = cursor.fetchall()
    conn.close()
    return res

# ----------------- PREMIUM USERS -----------------

def is_premium_user(user_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM premium_users WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_premium_info(user_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM premium_users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ----------------- FAVORITES -----------------

def toggle_favorite(user_id, movie_code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_favorites(user_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO ratings (user_id, movie_code, rating)
        VALUES (?, ?, ?)
    """, (user_id, movie_code.strip(), rating))
    conn.commit()
    conn.close()

def get_movie_ratings(movie_code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ----------------- SUPPORT TICKETS -----------------

def add_support_ticket(user_id, message_id, user_text):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO support_tickets (user_id, message_id, user_text) VALUES (?, ?, ?)", (user_id, message_id, user_text))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ticket_id

def get_support_ticket_by_msg(message_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT ticket_id, user_id, user_text FROM support_tickets WHERE message_id = ?", (message_id,))
    res = cursor.fetchone()
    conn.close()
    return res

# ----------------- CHANNELS & SETTINGS -----------------

def add_channel(channel_id, title, invite_link):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id.strip(),))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_channels():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, title, invite_link FROM channels")
    res = cursor.fetchall()
    conn.close()
    return res

def get_users():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    res = cursor.fetchall()
    conn.close()
    return [row[0] for row in res]

def set_setting(key, value):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key.strip(), value.strip()))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else default

def delete_setting(key):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM settings WHERE key = ?", (key.strip(),))
    conn.commit()
    conn.close()

def add_db_admin(user_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_db_admin(user_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_db_admins():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    res = cursor.fetchall()
    conn.close()
    return [r[0] for r in res]

def is_db_admin(user_id):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_vip_movies():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, genre, views FROM movies WHERE is_vip = 1 ORDER BY id DESC")
    res = cursor.fetchall()
    conn.close()
    return res

def set_movie_vip(code, is_vip):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE movies SET is_vip = ? WHERE code = ?", (1 if is_vip else 0, code.strip()))
    conn.commit()
    found = cursor.rowcount > 0
    conn.close()
    return found


# ----------------- MOVIE SUBSCRIPTIONS & RANDOM MOVIE -----------------

def toggle_movie_subscription(user_id, movie_code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM movie_subscriptions WHERE user_id = ? AND movie_code = ?", (user_id, movie_code.strip()))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_movie_subscribers(movie_code):
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM movie_subscriptions WHERE movie_code = ?", (movie_code.strip(),))
    res = cursor.fetchall()
    conn.close()
    return [r[0] for r in res]

def get_random_movie():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
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
    """Cloud PostgreSQL automatically saves all data persistently 24/7. No chat backup files needed."""
    pass

def auto_merge_sequels_and_parts():
    """Disabled automatic merging to prevent accidental grouping of distinct movies."""
    return 0


# ----------------- PENDING QUEUE HELPERS -----------------

def add_to_pending_queue(file_id, title="", caption=""):
    res = execute_query("SELECT COALESCE(MAX(queue_num), 0) + 1 FROM pending_queue", fetchone=True)
    next_num = res[0] if res else 1
    execute_query(
        "INSERT INTO pending_queue (queue_num, file_id, title, caption, status) VALUES (?, ?, ?, ?, 'pending')",
        (next_num, file_id, title, caption),
        commit=True
    )
    return next_num

def get_pending_queue_count():
    res = execute_query("SELECT COUNT(*) FROM pending_queue WHERE status = 'pending'", fetchone=True)
    return res[0] if res else 0

def get_next_pending_video():
    return execute_query("SELECT id, queue_num, file_id, title, caption FROM pending_queue WHERE status = 'pending' ORDER BY queue_num ASC LIMIT 1", fetchone=True)

def get_all_pending_videos():
    return execute_query("SELECT id, queue_num, file_id, title, caption FROM pending_queue WHERE status = 'pending' ORDER BY queue_num ASC", fetchall=True) or []

def mark_pending_fulfilled(pending_id):
    execute_query("UPDATE pending_queue SET status = 'fulfilled' WHERE id = ?", (pending_id,), commit=True)

def clear_pending_queue():
    execute_query("DELETE FROM pending_queue WHERE status = 'pending'", commit=True)

# ----------------- TELETHON SOURCE CHANNELS HELPERS -----------------

def get_telethon_source_channels():
    val = get_setting('telethon_source_channels')
    if not val:
        default_list = ['kinolar_tv', 'kino_kodlari', 'uzbek_kinolar', 'tarjima_kinolar', 'films_hd', 'top_kinolar']
        set_setting('telethon_source_channels', ",".join(default_list))
        return default_list
    return [ch.strip() for ch in val.split(',') if ch.strip()]

def add_telethon_source_channel(channel_username):
    clean = channel_username.replace('@', '').strip()
    if not clean:
        return False
    current = get_telethon_source_channels()
    if clean not in current:
        current.append(clean)
        set_setting('telethon_source_channels', ",".join(current))
        return True
    return False

def remove_telethon_source_channel(channel_username):
    clean = channel_username.replace('@', '').strip()
    current = get_telethon_source_channels()
    if clean in current:
        current.remove(clean)
        set_setting('telethon_source_channels', ",".join(current))
        return True
    return False




