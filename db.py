import aiosqlite
import json
import os
import time

DB_PATH = "aurasound.db"

# ─── MongoDB Motor Integration ────────────────────────────────────────────────
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "aurasound")

mongo_client = None
mongo_db = None
USE_MONGO = False

if MONGODB_URI:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        mongo_db = mongo_client[MONGODB_DB_NAME]
        USE_MONGO = True
        print(f"[MongoDB Engine] Successfully configured via MONGODB_URI ({MONGODB_DB_NAME})")
    except Exception as e:
        print(f"[MongoDB Warning] Could not initialize Motor client ({e}). Falling back to SQLite.")
        USE_MONGO = False
else:
    print("[Notice] MONGODB_URI not set. Operating on SQLite engine. Set MONGODB_URI to switch to MongoDB.")

async def init_db():
    if USE_MONGO and mongo_db is not None:
        try:
            await mongo_db.users.create_index("id", unique=True)
            await mongo_db.rooms.create_index("room_code", unique=True)
            await mongo_db.playlists.create_index("id")
            await mongo_db.playlists.create_index("owner_id")
            await mongo_db.liked_songs.create_index([("user_id", 1), ("track_id", 1)], unique=True)
            await mongo_db.listening_history.create_index([("user_id", 1), ("played_at", -1)])
            await mongo_db.search_history.create_index([("user_id", 1), ("searched_at", -1)])
            await mongo_db.friends.create_index([("user_id", 1), ("friend_id", 1)])
            await mongo_db.notifications.create_index([("user_id", 1), ("created_at", -1)])
            await mongo_db.search_cache.create_index("query_key", unique=True)
            print("[MongoDB Engine] Collection indexes initialized.")
        except Exception as e:
            print(f"[MongoDB Index Notice] {e}")

    # Initialize SQLite fallback tables
    async with aiosqlite.connect(DB_PATH) as db:
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
        await db.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                user_id INTEGER,
                friend_id INTEGER,
                status TEXT,
                PRIMARY KEY (user_id, friend_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                name TEXT,
                description TEXT,
                cover_image TEXT,
                is_public INTEGER DEFAULT 0,
                tracks_json TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS listening_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                track_json TEXT,
                played_at INTEGER
            )
        ''')
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
                queue_json TEXT DEFAULT '[]',
                updated_at INTEGER
            )
        ''')
        try:
            await db.execute("ALTER TABLE rooms ADD COLUMN queue_json TEXT DEFAULT '[]'")
        except Exception:
            pass
        await db.execute('''
            CREATE TABLE IF NOT EXISTS search_cache (
                query_key TEXT PRIMARY KEY,
                results_json TEXT,
                cached_at INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                title TEXT,
                message TEXT,
                data_json TEXT DEFAULT '{}',
                is_read INTEGER DEFAULT 0,
                created_at INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS liked_songs (
                user_id INTEGER,
                track_id TEXT,
                track_json TEXT,
                liked_at INTEGER,
                PRIMARY KEY (user_id, track_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                searched_at INTEGER
            )
        ''')
        await db.commit()

# --- ROOM PERSISTENCE FUNCTIONS ---
async def save_room_state(room_code, name, host_id, track_data, is_playing, is_video, start_time, pause_offset, queue_data=None):
    now = int(time.time())
    if USE_MONGO and mongo_db is not None:
        doc = {
            "room_code": room_code,
            "name": name,
            "host_id": host_id,
            "current_track": track_data,
            "is_playing": bool(is_playing),
            "is_video": bool(is_video),
            "start_time": start_time,
            "pause_offset": pause_offset,
            "queue": queue_data or [],
            "updated_at": now
        }
        await mongo_db.rooms.replace_one({"room_code": room_code}, doc, upsert=True)
        return

    track_json = json.dumps(track_data) if track_data else None
    queue_json = json.dumps(queue_data) if queue_data else '[]'
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO rooms (room_code, name, host_id, current_track_json, is_playing, is_video, start_time, pause_offset, queue_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_code) DO UPDATE SET
                name=excluded.name,
                host_id=excluded.host_id,
                current_track_json=excluded.current_track_json,
                is_playing=excluded.is_playing,
                is_video=excluded.is_video,
                start_time=excluded.start_time,
                pause_offset=excluded.pause_offset,
                queue_json=excluded.queue_json,
                updated_at=excluded.updated_at
        ''', (room_code, name, host_id, track_json, 1 if is_playing else 0, 1 if is_video else 0, start_time, pause_offset, queue_json, now))
        await db.commit()

async def load_room_state(room_code):
    if USE_MONGO and mongo_db is not None:
        doc = await mongo_db.rooms.find_one({"room_code": room_code}, {"_id": 0})
        if doc:
            doc.setdefault("queue", [])
            doc.setdefault("is_playing", False)
            doc.setdefault("is_video", False)
            return doc
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM rooms WHERE room_code = ?', (room_code,)) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(zip([col[0] for col in cursor.description], row))
                d['current_track'] = json.loads(d['current_track_json']) if d.get('current_track_json') else None
                d['queue'] = json.loads(d['queue_json']) if d.get('queue_json') else []
                d['is_playing'] = bool(d['is_playing'])
                d['is_video'] = bool(d['is_video'])
                return d
    return None

# --- SEARCH CACHE FUNCTIONS ---
async def get_cached_search(query_key, max_age_seconds=86400):
    now = int(time.time())
    if USE_MONGO and mongo_db is not None:
        doc = await mongo_db.search_cache.find_one({"query_key": query_key}, {"_id": 0})
        if doc and (now - doc.get("cached_at", 0)) < max_age_seconds:
            return doc.get("results")
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT results_json, cached_at FROM search_cache WHERE query_key = ?', (query_key,)) as cursor:
            row = await cursor.fetchone()
            if row and (now - row[1]) < max_age_seconds:
                return json.loads(row[0])
    return None

async def set_cached_search(query_key, results_data):
    now = int(time.time())
    if USE_MONGO and mongo_db is not None:
        doc = {"query_key": query_key, "results": results_data, "cached_at": now}
        await mongo_db.search_cache.replace_one({"query_key": query_key}, doc, upsert=True)
        return

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
    if USE_MONGO and mongo_db is not None:
        msg = {"room_code": room_code, "user_id": user_id, "username": username, "text": text, "timestamp": now}
        await mongo_db.messages.insert_one(msg)
        msg.pop("_id", None)
        return msg

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO messages (room_code, user_id, username, text, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (room_code, user_id, username, text, now))
        await db.commit()
    return {'room_code': room_code, 'user_id': user_id, 'username': username, 'text': text, 'timestamp': now}

async def get_room_messages(room_code, limit=50):
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.messages.find({"room_code": room_code}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return list(reversed(docs))

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM messages WHERE room_code = ? ORDER BY timestamp DESC LIMIT ?', (room_code, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in reversed(rows)]

# --- USER FUNCTIONS ---
async def get_or_create_user(user_id, username, display_name, avatar_url=""):
    if USE_MONGO and mongo_db is not None:
        user = await mongo_db.users.find_one({"id": user_id}, {"_id": 0})
        if user:
            return user
        now = int(time.time())
        new_user = {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "bio": "",
            "country": "",
            "language": "en",
            "joined_date": now,
            "listening_time": 0,
            "rooms_joined": 0,
            "theme": "dark",
            "accent_color": "#1DB954",
            "settings_json": "{}",
            "banner_url": ""
        }
        await mongo_db.users.insert_one(new_user)
        new_user.pop("_id", None)
        return new_user

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
    if USE_MONGO and mongo_db is not None:
        await mongo_db.users.update_one({"id": user_id}, {"$set": updates})
        return

    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    values = list(updates.values())
    values.append(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        await db.commit()

async def get_user_profile(user_id):
    if USE_MONGO and mongo_db is not None:
        return await mongo_db.users.find_one({"id": user_id}, {"_id": 0})

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([col[0] for col in cursor.description], row))
    return None

async def search_users(query, current_user_id=None):
    if USE_MONGO and mongo_db is not None:
        import re
        regex = re.compile(re.escape(query), re.IGNORECASE)
        cursor = mongo_db.users.find({
            "$or": [{"username": regex}, {"display_name": regex}],
            "id": {"$ne": current_user_id or 0}
        }, {"_id": 0}).limit(20)
        return await cursor.to_list(length=20)

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
    if USE_MONGO and mongo_db is not None:
        existing = await mongo_db.friends.find_one({"user_id": user_id, "friend_id": friend_id})
        if existing:
            return False, f"Friendship status is already '{existing.get('status')}'"
        await mongo_db.friends.insert_one({"user_id": user_id, "friend_id": friend_id, "status": "pending"})
        await create_notification(friend_id, 'friend_request', 'New Friend Request', 'wants to connect with you', json.dumps({'from_user_id': user_id}))
        return True, "Request sent"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT status FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return False, f"Friendship status is already '{row[0]}'"
        
        await db.execute('INSERT INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'pending'))
        await db.commit()
        await create_notification(friend_id, 'friend_request', 'New Friend Request', 'wants to connect with you', json.dumps({'from_user_id': user_id}))
        return True, "Request sent"

async def accept_friend_request(user_id, friend_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.friends.update_one({"user_id": friend_id, "friend_id": user_id}, {"$set": {"status": "accepted"}})
        await mongo_db.friends.replace_one({"user_id": user_id, "friend_id": friend_id}, {"user_id": user_id, "friend_id": friend_id, "status": "accepted"}, upsert=True)
        await create_notification(friend_id, 'friend_accepted', 'Friend Request Accepted', 'accepted your request', json.dumps({'from_user_id': user_id}))
        return True

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE friends SET status = ? WHERE user_id = ? AND friend_id = ?', ('accepted', friend_id, user_id))
        await db.execute('INSERT OR REPLACE INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'accepted'))
        await db.commit()
        await create_notification(friend_id, 'friend_accepted', 'Friend Request Accepted', 'accepted your request', json.dumps({'from_user_id': user_id}))
        return True

async def reject_friend_request(user_id, friend_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.friends.delete_many({
            "$or": [
                {"user_id": user_id, "friend_id": friend_id},
                {"user_id": friend_id, "friend_id": user_id}
            ]
        })
        return True

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)', 
                         (user_id, friend_id, friend_id, user_id))
        await db.commit()
        return True

async def remove_friend(user_id, friend_id):
    return await reject_friend_request(user_id, friend_id)

async def block_user(user_id, friend_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.friends.replace_one({"user_id": user_id, "friend_id": friend_id}, {"user_id": user_id, "friend_id": friend_id, "status": "blocked"}, upsert=True)
        return True

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR REPLACE INTO friends (user_id, friend_id, status) VALUES (?, ?, ?)', (user_id, friend_id, 'blocked'))
        await db.commit()
        return True

async def get_friends_list(user_id):
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.friends.find({"user_id": user_id, "status": "accepted"}, {"_id": 0})
        friend_rows = await cursor.to_list(length=100)
        friend_ids = [f["friend_id"] for f in friend_rows]
        if not friend_ids:
            return []
        users_cursor = mongo_db.users.find({"id": {"$in": friend_ids}}, {"_id": 0, "id": 1, "username": 1, "display_name": 1, "avatar_url": 1, "bio": 1})
        return await users_cursor.to_list(length=100)

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
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.friends.find({"friend_id": user_id, "status": "pending"}, {"_id": 0})
        req_rows = await cursor.to_list(length=100)
        sender_ids = [r["user_id"] for r in req_rows]
        if not sender_ids:
            return []
        senders_cursor = mongo_db.users.find({"id": {"$in": sender_ids}}, {"_id": 0, "id": 1, "username": 1, "display_name": 1, "avatar_url": 1, "bio": 1})
        return await senders_cursor.to_list(length=100)

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
    if USE_MONGO and mongo_db is not None:
        doc = {
            "user_id": user_id,
            "type": type_str,
            "title": title,
            "message": message,
            "data_json": data_json,
            "is_read": 0,
            "created_at": now
        }
        await mongo_db.notifications.insert_one(doc)
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO notifications (user_id, type, title, message, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, type_str, title, message, data_json, now))
        await db.commit()

async def get_notifications(user_id):
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.notifications.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50)
        return await cursor.to_list(length=50)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

async def mark_notification_read(notif_id, user_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.notifications.update_one({"user_id": user_id, "created_at": notif_id}, {"$set": {"is_read": 1}})
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', (notif_id, user_id))
        await db.commit()

async def delete_notification(notif_id, user_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.notifications.delete_one({"user_id": user_id, "created_at": notif_id})
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM notifications WHERE id = ? AND user_id = ?', (notif_id, user_id))
        await db.commit()

# --- PLAYLISTS & LIKED SONGS ---
async def create_playlist(owner_id, name, description="", cover_image="", is_public=1):
    now = int(time.time())
    playlist_id = int(time.time() * 1000) % 1000000000
    if USE_MONGO and mongo_db is not None:
        doc = {
            "id": playlist_id,
            "owner_id": owner_id,
            "name": name,
            "description": description,
            "cover_image": cover_image,
            "is_public": is_public,
            "tracks": [],
            "created_at": now
        }
        await mongo_db.playlists.insert_one(doc)
        return playlist_id

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO playlists (owner_id, name, description, cover_image, is_public, tracks_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (owner_id, name, description, cover_image, is_public, json.dumps([])))
        await db.commit()
        return cursor.lastrowid

async def get_user_playlists(owner_id):
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.playlists.find({"$or": [{"owner_id": owner_id}, {"is_public": 1}]}, {"_id": 0}).sort("created_at", -1)
        return await cursor.to_list(length=100)

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
    if USE_MONGO and mongo_db is not None:
        res = await mongo_db.playlists.update_one(
            {"id": int(playlist_id), "owner_id": owner_id},
            {"$push": {"tracks": track_data}}
        )
        if res.matched_count == 0:
            return False, "Playlist not found"
        return True, "Added to playlist"

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

async def remove_track_from_playlist(playlist_id, owner_id, track_idx):
    if USE_MONGO and mongo_db is not None:
        playlist = await mongo_db.playlists.find_one({"id": int(playlist_id), "owner_id": owner_id})
        if not playlist:
            return False, "Playlist not found"
        tracks = playlist.get("tracks", [])
        if 0 <= track_idx < len(tracks):
            tracks.pop(track_idx)
            await mongo_db.playlists.update_one({"id": int(playlist_id)}, {"$set": {"tracks": tracks}})
            return True, "Removed from playlist"
        return False, "Invalid track index"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT tracks_json FROM playlists WHERE id = ? AND owner_id = ?', (playlist_id, owner_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "Playlist not found"
            tracks = json.loads(row[0] or '[]')
            if 0 <= track_idx < len(tracks):
                tracks.pop(track_idx)
                await db.execute('UPDATE playlists SET tracks_json = ? WHERE id = ?', (json.dumps(tracks), playlist_id))
                await db.commit()
                return True, "Removed from playlist"
            return False, "Invalid track index"

async def delete_playlist(playlist_id, owner_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.playlists.delete_one({"id": int(playlist_id), "owner_id": owner_id})
        return True, "Playlist deleted"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM playlists WHERE id = ? AND owner_id = ?', (playlist_id, owner_id))
        await db.commit()
        return True, "Playlist deleted"

async def toggle_liked_song(user_id, track_data):
    track_id = track_data.get('yt_id') or track_data.get('title')
    if not track_id:
        return False, "Invalid track"
    now = int(time.time())
    if USE_MONGO and mongo_db is not None:
        existing = await mongo_db.liked_songs.find_one({"user_id": user_id, "track_id": track_id})
        if existing:
            await mongo_db.liked_songs.delete_one({"user_id": user_id, "track_id": track_id})
            return False, "Removed from Liked Songs"
        else:
            doc = {"user_id": user_id, "track_id": track_id, "track": track_data, "liked_at": now}
            await mongo_db.liked_songs.insert_one(doc)
            return True, "Added to Liked Songs"

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
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.liked_songs.find({"user_id": user_id}, {"_id": 0}).sort("liked_at", -1)
        docs = await cursor.to_list(length=200)
        return [d["track"] for d in docs if "track" in d]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT track_json FROM liked_songs WHERE user_id = ? ORDER BY liked_at DESC', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [json.loads(r[0]) for r in rows if r[0]]

async def add_listening_history(user_id, track_data):
    if not user_id:
        return
    now = int(time.time())
    if USE_MONGO and mongo_db is not None:
        await mongo_db.listening_history.insert_one({"user_id": user_id, "track": track_data, "played_at": now})
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO listening_history (user_id, track_json, played_at)
            VALUES (?, ?, ?)
        ''', (user_id, json.dumps(track_data), now))
        await db.commit()

async def get_listening_history(user_id, limit=20):
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.listening_history.find({"user_id": user_id}, {"_id": 0}).sort("played_at", -1).limit(limit * 2)
        docs = await cursor.to_list(length=limit * 2)
        result = []
        seen = set()
        for doc in docs:
            track = doc.get("track", {})
            key = track.get("yt_id") or track.get("title")
            if key and key not in seen:
                seen.add(key)
                track["played_at"] = doc.get("played_at")
                result.append(track)
                if len(result) >= limit:
                    break
        return result

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT track_json, played_at FROM listening_history WHERE user_id = ? ORDER BY played_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            seen = set()
            for r in rows:
                track = json.loads(r[0])
                key = track.get('yt_id') or track.get('title')
                if key not in seen:
                    seen.add(key)
                    track['played_at'] = r[1]
                    result.append(track)
            return result

# --- SEARCH HISTORY ---
async def save_search_query(user_id, query):
    if not user_id or not query:
        return
    now = int(time.time())
    if USE_MONGO and mongo_db is not None:
        await mongo_db.search_history.delete_many({"user_id": user_id, "query": query})
        await mongo_db.search_history.insert_one({"user_id": user_id, "query": query, "searched_at": now})
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM search_history WHERE user_id = ? AND query = ?', (user_id, query))
        await db.execute('INSERT INTO search_history (user_id, query, searched_at) VALUES (?, ?, ?)', (user_id, query, now))
        await db.execute('''
            DELETE FROM search_history WHERE user_id = ? AND id NOT IN (
                SELECT id FROM search_history WHERE user_id = ? ORDER BY searched_at DESC LIMIT 20
            )
        ''', (user_id, user_id))
        await db.commit()

async def get_search_history(user_id, limit=10):
    if USE_MONGO and mongo_db is not None:
        cursor = mongo_db.search_history.find({"user_id": user_id}, {"_id": 0}).sort("searched_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT query, searched_at FROM search_history WHERE user_id = ? ORDER BY searched_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{'query': r[0], 'searched_at': r[1]} for r in rows]

async def clear_search_history(user_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.search_history.delete_many({"user_id": user_id})
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM search_history WHERE user_id = ?', (user_id,))
        await db.commit()

async def mark_all_notifications_read(user_id):
    if USE_MONGO and mongo_db is not None:
        await mongo_db.notifications.update_many({"user_id": user_id}, {"$set": {"is_read": 1}})
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_user_stats(user_id):
    if USE_MONGO and mongo_db is not None:
        songs_played = await mongo_db.listening_history.count_documents({"user_id": user_id})
        user = await mongo_db.users.find_one({"id": user_id}, {"_id": 0, "rooms_joined": 1})
        rooms_joined = user.get("rooms_joined", 0) if user else 0
        friends_count = await mongo_db.friends.count_documents({"user_id": user_id, "status": "accepted"})
        liked_count = await mongo_db.liked_songs.count_documents({"user_id": user_id})
        return {
            'songs_played': songs_played,
            'rooms_joined': rooms_joined,
            'friends_count': friends_count,
            'liked_count': liked_count
        }

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM listening_history WHERE user_id = ?', (user_id,)) as c:
            songs_played = (await c.fetchone())[0]
        async with db.execute('SELECT rooms_joined FROM users WHERE id = ?', (user_id,)) as c:
            row = await c.fetchone()
            rooms_joined = row[0] if row else 0
        async with db.execute("SELECT COUNT(*) FROM friends WHERE user_id = ? AND status = 'accepted'", (user_id,)) as c:
            friends_count = (await c.fetchone())[0]
        async with db.execute('SELECT COUNT(*) FROM liked_songs WHERE user_id = ?', (user_id,)) as c:
            liked_count = (await c.fetchone())[0]
        return {
            'songs_played': songs_played,
            'rooms_joined': rooms_joined,
            'friends_count': friends_count,
            'liked_count': liked_count
        }

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
                queue_json TEXT DEFAULT '[]',
                updated_at INTEGER
            )
        ''')
        
        try:
            await db.execute("ALTER TABLE rooms ADD COLUMN queue_json TEXT DEFAULT '[]'")
        except Exception:
            pass # Column already exists

        # Search Cache Table (Deduplication & Rate Limit Prevention)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS search_cache (
                query_key TEXT PRIMARY KEY,
                results_json TEXT,
                cached_at INTEGER
            )
        ''')

        # Notifications Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                title TEXT,
                message TEXT,
                data_json TEXT DEFAULT '{}',
                is_read INTEGER DEFAULT 0,
                created_at INTEGER
            )
        ''')

        # Liked Songs Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS liked_songs (
                user_id INTEGER,
                track_id TEXT,
                track_json TEXT,
                liked_at INTEGER,
                PRIMARY KEY (user_id, track_id)
            )
        ''')

        # Search History Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT,
                searched_at INTEGER
            )
        ''')

        await db.commit()

# --- ROOM PERSISTENCE FUNCTIONS ---
async def save_room_state(room_code, name, host_id, track_data, is_playing, is_video, start_time, pause_offset, queue_data=None):
    now = int(time.time())
    track_json = json.dumps(track_data) if track_data else None
    queue_json = json.dumps(queue_data) if queue_data else '[]'
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO rooms (room_code, name, host_id, current_track_json, is_playing, is_video, start_time, pause_offset, queue_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(room_code) DO UPDATE SET
                name=excluded.name,
                host_id=excluded.host_id,
                current_track_json=excluded.current_track_json,
                is_playing=excluded.is_playing,
                is_video=excluded.is_video,
                start_time=excluded.start_time,
                pause_offset=excluded.pause_offset,
                queue_json=excluded.queue_json,
                updated_at=excluded.updated_at
        ''', (room_code, name, host_id, track_json, 1 if is_playing else 0, 1 if is_video else 0, start_time, pause_offset, queue_json, now))
        await db.commit()

async def load_room_state(room_code):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM rooms WHERE room_code = ?', (room_code,)) as cursor:
            row = await cursor.fetchone()
            if row:
                d = dict(zip([col[0] for col in cursor.description], row))
                d['current_track'] = json.loads(d['current_track_json']) if d.get('current_track_json') else None
                d['queue'] = json.loads(d['queue_json']) if d.get('queue_json') else []
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
    clean_username = username.strip().replace('@', '').lower() if username else ""
    async with aiosqlite.connect(DB_PATH) as db:
        # First try to find by numeric ID
        async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                user_dict = dict(zip([col[0] for col in cursor.description], row))
                if clean_username and not user_dict.get('username'):
                    try:
                        await db.execute('UPDATE users SET username = ? WHERE id = ?', (clean_username, user_id))
                        await db.commit()
                    except Exception:
                        pass
                    user_dict['username'] = clean_username
                return user_dict
                
        # If not found by ID, try finding by username (case-insensitive)
        if clean_username:
            async with db.execute('SELECT * FROM users WHERE LOWER(username) = ?', (clean_username,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    existing = dict(zip([col[0] for col in cursor.description], row))
                    old_id = existing['id']
                    if old_id != user_id:
                        try:
                            await db.execute('UPDATE playlists SET owner_id = ? WHERE owner_id = ?', (user_id, old_id))
                            await db.execute('UPDATE liked_songs SET user_id = ? WHERE user_id = ?', (user_id, old_id))
                            await db.execute('UPDATE listening_history SET user_id = ? WHERE user_id = ?', (user_id, old_id))
                            await db.execute('UPDATE search_history SET user_id = ? WHERE user_id = ?', (user_id, old_id))
                            await db.execute('UPDATE users SET id = ? WHERE id = ?', (user_id, old_id))
                            await db.commit()
                            existing['id'] = user_id
                        except Exception as e:
                            print(f"[DB Notice] Primary Key update handled: {e}")
                    return existing

        now = int(time.time())
        try:
            await db.execute('''
                INSERT INTO users (id, username, display_name, avatar_url, joined_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, clean_username or username, display_name, avatar_url, now))
            await db.commit()
        except Exception:
            async with db.execute('SELECT * FROM users WHERE id = ? OR LOWER(username) = ?', (user_id, clean_username)) as cur:
                r = await cur.fetchone()
                if r:
                    return dict(zip([col[0] for col in cur.description], r))
        
        async with db.execute('SELECT * FROM users WHERE id = ?', (user_id,)) as new_cursor:
            new_row = await new_cursor.fetchone()
            if new_row:
                return dict(zip([col[0] for col in new_cursor.description], new_row))
            return {'id': user_id, 'username': clean_username or username, 'display_name': display_name}

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

async def remove_track_from_playlist(playlist_id, owner_id, track_idx):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT tracks_json FROM playlists WHERE id = ? AND owner_id = ?', (playlist_id, owner_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False, "Playlist not found"
            tracks = json.loads(row[0] or '[]')
            if 0 <= track_idx < len(tracks):
                tracks.pop(track_idx)
                await db.execute('UPDATE playlists SET tracks_json = ? WHERE id = ?', (json.dumps(tracks), playlist_id))
                await db.commit()
                return True, "Removed from playlist"
            return False, "Invalid track index"

async def delete_playlist(playlist_id, owner_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM playlists WHERE id = ? AND owner_id = ?', (playlist_id, owner_id))
        await db.commit()
        return True, "Playlist deleted"

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

async def get_listening_history(user_id, limit=20):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT track_json, played_at FROM listening_history WHERE user_id = ? ORDER BY played_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            seen = set()
            for r in rows:
                track = json.loads(r[0])
                key = track.get('yt_id') or track.get('title')
                if key not in seen:
                    seen.add(key)
                    track['played_at'] = r[1]
                    result.append(track)
            return result

# --- SEARCH HISTORY ---
async def save_search_query(user_id, query):
    if not user_id or not query:
        return
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        # Remove old duplicate
        await db.execute('DELETE FROM search_history WHERE user_id = ? AND query = ?', (user_id, query))
        await db.execute('INSERT INTO search_history (user_id, query, searched_at) VALUES (?, ?, ?)', (user_id, query, now))
        # Keep only latest 20
        await db.execute('''
            DELETE FROM search_history WHERE user_id = ? AND id NOT IN (
                SELECT id FROM search_history WHERE user_id = ? ORDER BY searched_at DESC LIMIT 20
            )
        ''', (user_id, user_id))
        await db.commit()

async def get_search_history(user_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT query, searched_at FROM search_history WHERE user_id = ? ORDER BY searched_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{'query': r[0], 'searched_at': r[1]} for r in rows]

async def clear_search_history(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM search_history WHERE user_id = ?', (user_id,))
        await db.commit()

async def mark_all_notifications_read(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_user_stats(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        # Count listening history
        async with db.execute('SELECT COUNT(*) FROM listening_history WHERE user_id = ?', (user_id,)) as c:
            songs_played = (await c.fetchone())[0]
        # Count rooms
        async with db.execute('SELECT rooms_joined FROM users WHERE id = ?', (user_id,)) as c:
            row = await c.fetchone()
            rooms_joined = row[0] if row else 0
        # Count friends
        async with db.execute("SELECT COUNT(*) FROM friends WHERE user_id = ? AND status = 'accepted'", (user_id,)) as c:
            friends_count = (await c.fetchone())[0]
        # Count liked
        async with db.execute('SELECT COUNT(*) FROM liked_songs WHERE user_id = ?', (user_id,)) as c:
            liked_count = (await c.fetchone())[0]
        return {
            'songs_played': songs_played,
            'rooms_joined': rooms_joined,
            'friends_count': friends_count,
            'liked_count': liked_count
        }

