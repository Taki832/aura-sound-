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
                rooms_joined INTEGER DEFAULT 0,
                theme TEXT DEFAULT 'dark',
                accent_color TEXT DEFAULT '#1DB954',
                settings_json TEXT DEFAULT '{}',
                banner_url TEXT
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

        # Chat Messages
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT,
                user_id INTEGER,
                username TEXT,
                text TEXT,
                timestamp INTEGER
            )
        ''')

        await db.commit()

async def save_chat_message(room_code, user_id, username, text):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO messages (room_code, user_id, username, text, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (room_code, user_id, username, text, now))
        await db.commit()
    return {'room_code': room_code, 'user_id': user_id, 'username': username, 'text': text, 'timestamp': now}

async def get_room_messages(room_code, limit=50):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM messages WHERE room_code = ? ORDER BY timestamp DESC LIMIT ?', (room_code, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in reversed(rows)]

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
