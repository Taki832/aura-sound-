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

        # Rooms Table (Persistent Room State)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                room_code TEXT PRIMARY KEY,
                name TEXT,
                host_id INTEGER,
                current_track_json TEXT,
                is_playing INTEGER DEFAULT 0,
                is_video INTEGER DEFAULT 0,
                start_time REAL DEFAULT 0,
                pause_offset REAL DEFAULT 0,
                updated_at INTEGER
            )
        ''')

        # Search Cache Table (Deduplication & Rate Limit Prevention)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS search_cache (
                query_key TEXT PRIMARY KEY,
                results_json TEXT,
                cached_at INTEGER
            )
        ''')

        await db.commit()

# --- ROOM PERSISTENCE FUNCTIONS ---
async def save_room_state(room_code, name, host_id, track_data, is_playing, is_video, start_time, pause_offset):
    now = int(time.time())
    track_json = json.dumps(track_data) if track_data else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO rooms (room_code, name, host_id, current_track_json, is_playing, is_video, start_time, pause_offset, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_code) DO UPDATE SET
                name=excluded.name,
                host_id=excluded.host_id,
                current_track_json=excluded.current_track_json,
                is_playing=excluded.is_playing,
                is_video=excluded.is_video,
                start_time=excluded.start_time,
                pause_offset=excluded.pause_offset,
                updated_at=excluded.updated_at
        ''', (room_code, name, host_id, track_json, 1 if is_playing else 0, 1 if is_video else 0, start_time, pause_offset, now))
        await db.commit()

async def load_room_state(room_code):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM rooms WHERE room_code = ?', (room_code,)) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(zip([col[0] for col in cursor.description], row))
                d['current_track'] = json.loads(d['current_track_json']) if d.get('current_track_json') else None
                d['is_playing'] = bool(d['is_playing'])
                d['is_video'] = bool(d['is_video'])
                return d
    return None

# --- SEARCH CACHE FUNCTIONS ---
async def get_cached_search(query_key, max_age_seconds=86400):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT results_json, cached_at FROM search_cache WHERE query_key = ?', (query_key,)) as cursor:
            row = await cursor.fetchone()
            if row and (now - row[1]) < max_age_seconds:
                return json.loads(row[0])
    return None

async def set_cached_search(query_key, results_data):
    now = int(time.time())
    results_json = json.dumps(results_data)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO search_cache (query_key, results_json, cached_at)
            VALUES (?, ?, ?)
            ON CONFLICT(query_key) DO UPDATE SET
                results_json=excluded.results_json,
                cached_at=excluded.cached_at
        ''', (query_key, results_json, now))
        await db.commit()

# --- CHAT MESSAGES ---
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

# --- USER FUNCTIONS ---
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

async def search_users(query, current_user_id=None):
    q = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT id, username, display_name, avatar_url, bio FROM users 
            WHERE (username LIKE ? OR display_name LIKE ?) AND id != ?
            LIMIT 20
        ''', (q, q, current_user_id or 0)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

# --- FRIEND SYSTEM ---
async def send_friend_request(user_id, friend_id):
    if user_id == friend_id:
        return False, "Cannot add yourself"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT status FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return False, f"Friendship status is already '{row[0]}'"
        
        await db.execute('INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'pending'))
        await db.commit()
        # Notify recipient
        await create_notification(friend_id, 'friend_request', 'New Friend Request', 'wants to connect with you', json.dumps({'from_user_id': user_id}))
        return True, "Request sent"

async def accept_friend_request(user_id, friend_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Update pending request to accepted and create reciprocal row
        await db.execute('UPDATE friends SET status = ? WHERE user_id = ? AND friend_id = ?', ('accepted', friend_id, user_id))
        await db.execute('INSERT OR REPLACE INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'accepted'))
        await db.commit()
        await create_notification(friend_id, 'friend_accepted', 'Friend Request Accepted', 'accepted your request', json.dumps({'from_user_id': user_id}))
        return True

async def reject_friend_request(user_id, friend_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                         (user_id, friend_id, friend_id, user_id))
        await db.commit()
        return True

async def remove_friend(user_id, friend_id):
    return await reject_friend_request(user_id, friend_id)

async def block_user(user_id, friend_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'blocked'))
        await db.commit()
        return True

async def get_friends_list(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT u.id, u.username, u.display_name, u.avatar_url, u.bio
            FROM friends f
            JOIN users u ON f.friend_id = u.id
            WHERE f.user_id = ? AND f.status = 'accepted'
        ''', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

async def get_friend_requests(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT u.id, u.username, u.display_name, u.avatar_url, u.bio
            FROM friends f
            JOIN users u ON f.user_id = u.id
            WHERE f.friend_id = ? AND f.status = 'pending'
        ''', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

# --- NOTIFICATION SYSTEM ---
async def create_notification(user_id, type_str, title, message, data_json="{}"):
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO notifications (user_id, type, title, message, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, type_str, title, message, data_json, now))
        await db.commit()

async def get_notifications(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

async def mark_notification_read(notif_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', (notif_id, user_id))
        await db.commit()

async def delete_notification(notif_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM notifications WHERE id = ? AND user_id = ?', (notif_id, user_id))
        await db.commit()

# --- PLAYLISTS & LIKED SONGS ---
async def create_playlist(owner_id, name, description="", cover_image="", is_public=1):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO playlists (owner_id, name, description, cover_image, is_public, tracks_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (owner_id, name, description, cover_image, is_public, json.dumps([])))
        await db.commit()
        return cursor.lastrowid

async def get_user_playlists(owner_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM playlists WHERE owner_id = ? OR is_public = 1 ORDER BY id DESC', (owner_id,)) as cursor:
            rows = await cursor.fetchall()
            res = []
            for r in rows:
                item = dict(zip([col[0] for col in cursor.description], r))
                item['tracks'] = json.loads(item.get('tracks_json') or '[]')
                res.append(item)
            return res

async def add_track_to_playlist(playlist_id, owner_id, track_data):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT tracks_json FROM playlists WHERE id = ? AND owner_id = ?', (playlist_id, owner_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "Playlist not found"
            tracks = json.loads(row[0] or '[]')
            tracks.append(track_data)
            await db.execute('UPDATE playlists SET tracks_json = ? WHERE id = ?', (json.dumps(tracks), playlist_id))
            await db.commit()
            return True, "Added to playlist"

async def toggle_liked_song(user_id, track_data):
    track_id = track_data.get('yt_id') or track_data.get('title')
    if not track_id:
        return False, "Invalid track"
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM liked_songs WHERE user_id = ? AND track_id = ?', (user_id, track_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute('DELETE FROM liked_songs WHERE user_id = ? AND track_id = ?', (user_id, track_id))
                await db.commit()
                return False, "Removed from Liked Songs"
            else:
                await db.execute('INSERT INTO liked_songs (user_id, track_id, track_json, liked_at) VALUES (?, ?, ?, ?)',
                                 (user_id, track_id, json.dumps(track_data), now))
                await db.commit()
                return True, "Added to Liked Songs"

async def get_liked_songs(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT track_json FROM liked_songs WHERE user_id = ? ORDER BY liked_at DESC', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [json.loads(r[0]) for r in rows if r[0]]

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

