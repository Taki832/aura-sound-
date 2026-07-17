import aiosqlite
import json
import time

DB_PATH = "aurasound.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Users Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                avatar_url TEXT,
                bio TEXT,
                country TEXT,
                language TEXT,
                joined_date INTEGER,
                listening_time INTEGER DEFAULT 0,
                rooms_created INTEGER DEFAULT 0,
                rooms_joined INTEGER DEFAULT 0,
                theme TEXT DEFAULT 'dark',
                accent_color TEXT DEFAULT '#1DB954'
            )
        ''')
        
        # Friends Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER,
                friend_id INTEGER,
                status TEXT, -- 'pending', 'accepted'
                PRIMARY KEY (user_id, friend_id)
            )
        ''')

        # Playlists Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                description TEXT,
                cover_image TEXT,
                is_public INTEGER DEFAULT 0,
                tracks_json TEXT -- JSON array of track dicts
            )
        ''')
        
        # Listening History
        await db.execute('''
            CREATE TABLE IF NOT EXISTS listening_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                track_json TEXT,
                played_at INTEGER
            )
        ''')

        await db.commit()

async def get_or_create_user(user_id, username, display_name, avatar_url=""):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([col[0] for col in cursor.description], row))
            
            now = int(time.time())
            await db.execute('''
                INSERT INTO users (id, username, display_name, avatar_url, joined_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, display_name, avatar_url, now))
            await db.commit()
            
            # Fetch again to return dict
            async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as new_cursor:
                new_row = await new_cursor.fetchone()
                return dict(zip([col[0] for col in new_cursor.description], new_row))

async def update_user_profile(user_id, updates):
    if not updates:
        return
    
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values())
    values.append(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        await db.commit()

async def get_user_profile(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([col[0] for col in cursor.description], row))
    return None

async def add_listening_history(user_id, track_data):
    if not user_id:
        return
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO listening_history (user_id, track_json, played_at)
            VALUES (?, ?, ?)
        ''', (user_id, json.dumps(track_data), now))
        await db.commit()
