import os
import sqlite3

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
            caption TEXT
        )
    """)
    
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
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            invite_link TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def get_users_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def add_movie(code, title, caption):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO movies (code, title, caption)
            VALUES (?, ?, ?)
        """, (code.strip(), title.strip(), caption.strip() if caption else ""))
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
    cursor.execute("SELECT code, title, caption FROM movies WHERE code = ?", (code.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res

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
    # Delete episodes first to mimic cascade
    cursor.execute("DELETE FROM episodes WHERE movie_code = ?", (code.strip(),))
    cursor.execute("DELETE FROM movies WHERE code = ?", (code.strip(),))
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
    cursor.execute("SELECT code, title FROM movies")
    res = cursor.fetchall()
    conn.close()
    return res

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

