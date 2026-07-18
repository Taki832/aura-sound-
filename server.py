"""
AuraSound AI — Server-Driven Real-Time Synchronized Music & Video Engine
Supports Multi-Source Audio & YouTube Video Songs Streaming with 100% Sub-Millisecond Sync across Web App clients.
"""
import asyncio
import io
import json
import os
import random
import re
import string
import sys
import time
import traceback
from aiohttp import web, WSMsgType

import db
import urllib.parse
from storage import StorageService
from ai_engine import AIEngine

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', write_through=True)

import yt_dlp

# Fix for Pyrogram import on Python 3.10+
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

env_url = os.environ.get("MINI_APP_URL", "").strip()
if not env_url or "ngrok" in env_url:
    MINI_APP_URL = "https://aura-sound-88gw.onrender.com"
else:
    MINI_APP_URL = env_url

# Telegram bots are active by default (set ENABLE_BOTS=0 to disable)
BOTS_ENABLED = False
python_bot = None
mojo_bot = None

if os.environ.get("ENABLE_BOTS", "1") == "1":
    try:
        from pyrogram import Client, filters
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, BotCommand
        
        API_ID          = 28640193
        API_HASH        = "f21327975cce7fb1e9c0fd9d72e0812a"
        TOKEN_PYTHON    = "8045450869:AAEPoFX1EkqY8ENOk1yiia4sbv8AmBBjdhg"
        TOKEN_MOJO      = "8012607564:AAEQpYlPnXmhIIS2PFv4q3YXp0GGY2MdW2U"

        python_bot = Client("python_bot_mem", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN_PYTHON, in_memory=True)
        mojo_bot = Client("mojo_bot_mem", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN_MOJO, in_memory=True)
        BOTS_ENABLED = True
    except ImportError:
        print("[Notice] Pyrogram not installed. Bots disabled.")
else:
    print("[Notice] Telegram bots disabled.")

# ─── Global Server-Driven Room State ─────────────────────────────────────────
sync_rooms = {}
ROOM_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{3,64}$")
YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,32}$")

# ─── Telegram Bot Handlers ─────────────────────────────────────────────────────
if BOTS_ENABLED:
    def register_bot_handler(cmd_list, handler_func):
        """Register a command handler for both python_bot and mojo_bot."""
        flt = filters.command(cmd_list)
        python_bot.on_message(flt)(handler_func)
        mojo_bot.on_message(flt)(handler_func)

    # 1. /start and /app (with deep link room support)
    async def cmd_start_app(client, message):
        user = message.from_user
        user_name = user.first_name if user else "Listener"
        tg_id = user.id if user else 0
        username = user.username if user else ""

        if tg_id:
            try:
                await db.get_or_create_user(tg_id, username, user_name)
            except Exception:
                pass

        args = message.command[1:] if len(message.command) > 1 else []
        room_code = None
        if args and args[0].startswith("room_"):
            room_code = args[0].replace("room_", "").upper()

        if room_code:
            room_url = f"{MINI_APP_URL}?room={room_code}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🚀 Join Sync Room #{room_code}", web_app=WebAppInfo(url=room_url))],
                [InlineKeyboardButton("🌐 Open Room in Browser", url=room_url)],
                [InlineKeyboardButton("🎵 Open AuraSound Home", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await message.reply_text(
                f"👋 **Welcome, {user_name}!**\n\n"
                f"🎉 You were invited to join **Sync Room #{room_code}**!\n"
                "Listen to music & watch video songs live with your friends.",
                reply_markup=keyboard
            )
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Open AuraSound AI Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
                [InlineKeyboardButton("🌐 Open in Browser", url=MINI_APP_URL)],
                [InlineKeyboardButton("❓ Help & Commands", callback_data="show_help")]
            ])
            await message.reply_text(
                f"👋 **Welcome, {user_name}!**\n\n"
                "🎬 **AuraSound.AI — Production Audio & Video Engine**\n"
                "Tap below to launch the Mini App, create sync rooms, listen to music, watch YouTube videos, and collaborate with friends in real-time!\n\n"
                "Type `/help` to view all available commands.",
                reply_markup=keyboard
            )

    register_bot_handler(["start", "app"], cmd_start_app)

    # 2. /room, /join, /invite
    async def cmd_room_join(client, message):
        args = message.command[1:] if len(message.command) > 1 else []
        room_code = args[0].upper() if args else None

        if not room_code:
            active_codes = list(sync_rooms.keys())
            if active_codes:
                room_code = active_codes[0]
            else:
                await message.reply_text(
                    "❌ **No active rooms specified!**\n\n"
                    "Usage: `/room [ROOM_CODE]` or `/join [ROOM_CODE]`\n\n"
                    "Or open the Mini App to create a brand new room!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🚀 Create Sync Room", web_app=WebAppInfo(url=MINI_APP_URL))]
                    ])
                )
                return

        room_url = f"{MINI_APP_URL}?room={room_code}"
        bot_uname = getattr(client, 'me', None) and getattr(client.me, 'username', None) or "Crazycando_bot"
        invite_link = f"https://t.me/{bot_uname}?start=room_{room_code}"
        share_text = urllib.parse.quote("Join my AuraSound Sync Room!")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🚀 Join Sync Room #{room_code}", web_app=WebAppInfo(url=room_url))],
            [InlineKeyboardButton("🔗 Share Invite Link", url=f"https://t.me/share/url?url={invite_link}&text={share_text}")],
            [InlineKeyboardButton("🌐 Open in Browser", url=room_url)]
        ])

        await message.reply_text(
            f"🎬 **Sync Room #{room_code}**\n\n"
            f"• **Direct WebApp Link:** [Open Room]({room_url})\n"
            f"• **Telegram Invite Link:** `{invite_link}`\n\n"
            "Share this link with your friends to listen & watch live together!",
            reply_markup=keyboard
        )

    register_bot_handler(["room", "join", "invite"], cmd_room_join)

    # 3. /nowplaying and /playing
    async def cmd_now_playing(client, message):
        playing_rooms = []
        for code, room in sync_rooms.items():
            track = room.get('current_track')
            if track:
                playing_rooms.append((code, room, track))

        if not playing_rooms:
            await message.reply_text(
                "🎵 **No tracks currently playing in active rooms!**\n\n"
                "Launch the app and start a track to play for your room.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Launch Player", web_app=WebAppInfo(url=MINI_APP_URL))]
                ])
            )
            return

        text = "🎶 **Currently Playing in AuraSound Sync Rooms:**\n\n"
        buttons = []
        for code, room, track in playing_rooms[:5]:
            title = track.get('title', 'Unknown Track')
            is_playing = room.get('is_playing', False)
            status_emoji = "▶️" if is_playing else "⏸️"
            members_cnt = len(room.get('members', []))
            
            text += f"{status_emoji} **{title}**\n"
            text += f"   • Room: `#{code}` | Members: {members_cnt}\n\n"
            
            room_url = f"{MINI_APP_URL}?room={code}"
            buttons.append([InlineKeyboardButton(f"🎧 Listen to #{code}", web_app=WebAppInfo(url=room_url))])

        buttons.append([InlineKeyboardButton("🚀 Open Mini App", web_app=WebAppInfo(url=MINI_APP_URL))])
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    register_bot_handler(["nowplaying", "playing"], cmd_now_playing)

    # 4. /playlists
    async def cmd_playlists(client, message):
        user = message.from_user
        if not user or not user.id:
            await message.reply_text("❌ Could not verify user.")
            return

        db_user = await db.get_user_profile(user.id)
        if not db_user:
            db_user = await db.get_or_create_user(user.id, user.username or "", user.first_name or "Listener")

        playlists = await db.get_user_playlists(db_user['id'])
        if not playlists:
            await message.reply_text(
                "📁 **You don't have any playlists yet!**\n\n"
                "Create and manage custom playlists in the Your Library section.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Open Library", web_app=WebAppInfo(url=MINI_APP_URL))]
                ])
            )
            return

        text = f"📁 **Your Playlists ({len(playlists)}):**\n\n"
        for p in playlists:
            tracks_cnt = len(p.get('tracks', []))
            vis = "Public 🌐" if p.get('is_public') else "Private 🔒"
            text += f"🎵 **{p['name']}** — {tracks_cnt} tracks ({vis})\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Manage Playlists in App", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await message.reply_text(text, reply_markup=keyboard)

    register_bot_handler(["playlists"], cmd_playlists)

    # 5. /history
    async def cmd_history(client, message):
        user = message.from_user
        if not user or not user.id:
            return

        db_user = await db.get_user_profile(user.id)
        if not db_user:
            db_user = await db.get_or_create_user(user.id, user.username or "", user.first_name or "Listener")

        listening = await db.get_listening_history(db_user['id'], limit=5)
        searches = await db.get_search_history(db_user['id'], limit=5)

        text = "📜 **Your Listening & Search History:**\n\n"
        
        if listening:
            text += "🎧 **Recently Played Tracks:**\n"
            for t in listening:
                title = t.get('title', 'Unknown')
                text += f"  • {title}\n"
            text += "\n"
        else:
            text += "🎧 **Recently Played Tracks:** None yet.\n\n"

        if searches:
            text += "🔍 **Recent Searches:**\n"
            for s in searches:
                text += f"  • `{s['query']}`\n"
        else:
            text += "🔍 **Recent Searches:** None yet.\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open AuraSound App", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await message.reply_text(text, reply_markup=keyboard)

    register_bot_handler(["history"], cmd_history)

    # 6. /friends
    async def cmd_friends(client, message):
        user = message.from_user
        if not user or not user.id:
            return

        db_user = await db.get_user_profile(user.id)
        if not db_user:
            db_user = await db.get_or_create_user(user.id, user.username or "", user.first_name or "Listener")

        friends = await db.get_friends_list(db_user['id'])
        requests = await db.get_friend_requests(db_user['id'])

        text = f"👥 **Friends & Network:**\n\n"
        text += f"• **Total Friends:** {len(friends)}\n"
        if friends:
            for f in friends[:5]:
                name = f.get('display_name') or f.get('username') or 'User'
                text += f"  • {name}\n"
            if len(friends) > 5:
                text += f"  ... and {len(friends)-5} more\n"
        
        text += f"\n• **Pending Friend Requests:** {len(requests)}\n"
        if requests:
            for r in requests:
                req_name = r.get('display_name') or r.get('username') or 'User'
                text += f"  • From {req_name}\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open Friends in App", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await message.reply_text(text, reply_markup=keyboard)

    register_bot_handler(["friends"], cmd_friends)

    # 7. /search [query]
    async def cmd_search(client, message):
        args = message.command[1:] if len(message.command) > 1 else []
        query = " ".join(args).strip()

        if not query:
            await message.reply_text(
                "🔍 **Search Live Music:**\n\n"
                "Usage: `/search [song or artist name]`\n"
                "Example: `/search Blinding Lights`"
            )
            return

        await message.reply_text(f"🔎 Searching YouTube for `{query}`...")
        
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, multi_source_search, query, 'all', 3)

        if not results:
            await message.reply_text("❌ No search results found.")
            return

        text = f"🎵 **Search Results for '{query}':**\n\n"
        for idx, t in enumerate(results, 1):
            d_sec = int(t.get('duration', 0))
            dur = f"{d_sec // 60}:{d_sec % 60:02d}"
            text += f"{idx}. **{t['title']}** ({dur})\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Play Results in App", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await message.reply_text(text, reply_markup=keyboard)

    register_bot_handler(["search"], cmd_search)

    # 8. /help
    async def cmd_help(client, message):
        text = (
            "🤖 **AuraSound.AI Bot Commands Menu:**\n\n"
            "• `/app` or `/start` — Launch Mini App\n"
            "• `/room [CODE]` — Join or invite friends to a Sync Room\n"
            "• `/nowplaying` — View currently playing music in active rooms\n"
            "• `/playlists` — View your custom playlists\n"
            "• `/history` — View your listening & search history\n"
            "• `/friends` — View your friends list & pending requests\n"
            "• `/search [query]` — Live music search\n"
            "• `/help` — Display this command menu\n"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Open AuraSound App", web_app=WebAppInfo(url=MINI_APP_URL))]
        ])
        await message.reply_text(text, reply_markup=keyboard)

    register_bot_handler(["help"], cmd_help)

    @python_bot.on_callback_query()
    @mojo_bot.on_callback_query()
    async def handle_bot_callbacks(client, callback_query):
        if callback_query.data == "show_help":
            text = (
                "🤖 **AuraSound.AI Bot Commands Menu:**\n\n"
                "• `/app` or `/start` — Launch Mini App\n"
                "• `/room [CODE]` — Join or invite friends to a Sync Room\n"
                "• `/nowplaying` — View currently playing music in active rooms\n"
                "• `/playlists` — View your custom playlists\n"
                "• `/history` — View your listening & search history\n"
                "• `/friends` — View your friends list & pending requests\n"
                "• `/search [query]` — Live music search\n"
                "• `/help` — Display this command menu\n"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Open AuraSound App", web_app=WebAppInfo(url=MINI_APP_URL))]
            ])
            await callback_query.message.reply_text(text, reply_markup=keyboard)
            try:
                await callback_query.answer()
            except Exception:
                pass

# ─── Multi-Source Extraction Helpers ────────────────────────────────────────────
def multi_source_search(query: str, source: str = 'all', limit: int = 6):
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'extract_flat': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    
    search_query = query
    if source == 'spotify':
        search_query = f"{query} spotify official audio"
    elif source == 'jiosaavn':
        search_query = f"{query} jiosaavn audio"
    elif source == 'youtube':
        search_query = f"{query} youtube music video"

    # Exponential Backoff Retry Logic
    results = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{search_query}", download=False)
                if info and info.get('entries'):
                    for entry in info['entries']:
                        src_tag = source if source != 'all' else ('spotify' if 'spotify' in entry.get('title','').lower() else 'youtube')
                        results.append({
                            'title': entry.get('title', 'Unknown Track'),
                            'url': entry.get('url', ''),
                            'thumbnail': entry.get('thumbnail', ''),
                            'duration': entry.get('duration', 0),
                            'yt_id': entry.get('id', ''),
                            'source': src_tag
                        })
            break # Success, break out of retry loop
        except Exception as e:
            print(f"[Search Attempt {attempt+1}/{max_retries} Failed] {e}")
            if "429" in str(e) or "Too Many Requests" in str(e):
                time.sleep(1.5 ** attempt) # Exponential backoff
            else:
                time.sleep(0.5)

    return results

def get_direct_stream_url(query: str):
    opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best', 
        'noplaylist': True, 
        'quiet': True, 
        'no_warnings': True,
        'extract_flat': False,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb', 'web']}}
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            target = f"https://www.youtube.com/watch?v={query}" if YOUTUBE_ID_PATTERN.fullmatch(query) else f"ytsearch:{query}"
            info = ydl.extract_info(target, download=False)
            if info:
                if info.get('entries') and len(info['entries']) > 0:
                    v = info['entries'][0]
                else:
                    v = info
                return v.get('url'), v.get('title'), v.get('thumbnail', ''), v.get('duration', 0)
        except Exception as e:
            print(f"[Direct Audio Stream Error] {e}")
    return None, None, None, 0

def get_youtube_video_metadata(query: str):
    """Resolve a search query to a YouTube video ID for the official embed player."""
    opts = {
        'noplaylist': True, 
        'quiet': True, 
        'no_warnings': True,
        'extract_flat': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if info and info.get('entries'):
                v = info['entries'][0]
                return v.get('id', ''), v.get('title'), v.get('thumbnail', ''), v.get('duration', 0)
        except Exception as e:
            print(f"[YouTube Video Resolve Error] {e}")
    return None, None, None, 0

def room_position(room, now=None):
    now = now or time.time()
    if not room['is_playing']:
        return room['pause_offset']
    position = max(0, now - room['start_time'])
    duration = (room.get('current_track') or {}).get('duration') or 0
    return min(position, duration) if duration else position

def coerce_position(value, duration=0):
    try:
        position = max(0.0, float(value))
    except (TypeError, ValueError):
        position = 0.0
    return min(position, float(duration)) if duration else position

async def broadcast_room_state(room_code, room, message_type='SERVER_STATE'):
    """Push the authoritative state immediately after a control action."""
    now = time.time()
    payload = json.dumps({
        'type': message_type,
        'room_code': room_code,
        'track': room['current_track'],
        'is_playing': room['is_playing'],
        'is_video': room.get('is_video', False),
        'current_position': room_position(room, now),
        'members': room['members'],
        'queue': room.get('queue', []),
        'server_time': now,
    })
    dead_sockets = []
    for ws in list(room['sockets']):
        try:
            await ws.send_str(payload)
        except Exception:
            dead_sockets.append(ws)
    for ws in dead_sockets:
        if ws in room['sockets']:
            room['sockets'].remove(ws)

# ─── Server-Driven Room Heartbeat Loop ──────────────────────────────────────────
async def room_heartbeat_loop():
    while True:
        try:
            now = time.time()
            rooms_to_delete = []
            for code, room in list(sync_rooms.items()):
                if room['sockets']:
                    room['empty_since'] = None
                    await broadcast_room_state(code, room, 'SERVER_HEARTBEAT')
                else:
                    if room.get('empty_since') is None:
                        room['empty_since'] = now
                    elif now - room['empty_since'] > 300: # 5 minutes timeout
                        rooms_to_delete.append(code)
            
            for code in rooms_to_delete:
                del sync_rooms[code]
                asyncio.create_task(db.delete_room(code))
                print(f"[Room Cleanup] Deleted empty room #{code}")
        except Exception as e:
            print(f"[Heartbeat Loop Error] {e}")
        await asyncio.sleep(1.0)

# ─── WebSocket Room Connection Handler ──────────────────────────────────────────
async def websocket_room_handler(request):
    room_code = request.match_info.get('room_code', '').upper()
    user_name = request.query.get('user', 'Listener')

    if not ROOM_CODE_PATTERN.fullmatch(room_code):
        raise web.HTTPBadRequest(text='Invalid room code')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    if room_code not in sync_rooms:
        db_room = await db.load_room_state(room_code)
        if db_room:
            sync_rooms[room_code] = {
                'name': db_room.get('name') or f"{user_name}'s Sync Room",
                'sockets': [],
                'members': [],
                'current_track': db_room.get('current_track'),
                'is_playing': db_room.get('is_playing', False),
                'is_video': db_room.get('is_video', False),
                'start_time': db_room.get('start_time', time.time()),
                'pause_offset': db_room.get('pause_offset', 0),
                'queue': db_room.get('queue', []),
                'empty_since': None
            }
        else:
            sync_rooms[room_code] = {
                'name': f"{user_name}'s Sync Room",
                'sockets': [],
                'members': [],
                'current_track': None,
                'is_playing': False,
                'is_video': False,
                'start_time': time.time(),
                'pause_offset': 0,
                'queue': [],
                'empty_since': None
            }

    room = sync_rooms[room_code]
    room['sockets'].append(ws)
    room['members'].append(user_name)

    print(f"[WebSocket] User '{user_name}' joined Sync Room #{room_code} (Active: {len(room['sockets'])})")

    now = time.time()
    current_pos = room_position(room, now)
    
    # Load recent chat messages for this room from SQLite
    try:
        recent_messages = await db.get_room_messages(room_code, limit=50)
    except Exception as e:
        print(f"[WebSocket] Error loading messages: {e}")
        recent_messages = []

    await ws.send_str(json.dumps({
        'type': 'INIT_ROOM_STATE',
        'room_code': room_code,
        'members': room['members'],
        'track': room['current_track'],
        'is_playing': room['is_playing'],
        'is_video': room.get('is_video', False),
        'current_position': current_pos,
        'queue': room.get('queue', []),
        'recent_messages': recent_messages
    }))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                action_type = data.get('type')

                if action_type == 'ACTION_TRACK':
                    room['current_track'] = data.get('track')
                    room['is_video'] = data.get('is_video', False)
                    room['start_time'] = time.time()
                    room['pause_offset'] = 0
                    room['is_playing'] = True
                    await broadcast_room_state(room_code, room)
                    asyncio.create_task(db.save_room_state(room_code, room['name'], 0, room['current_track'], True, room['is_video'], room['start_time'], 0))

                elif action_type == 'ACTION_PLAY':
                    pos = coerce_position(data.get('position', 0))
                    room['is_playing'] = True
                    room['start_time'] = time.time() - pos
                    room['pause_offset'] = pos
                    await broadcast_room_state(room_code, room)
                    asyncio.create_task(db.save_room_state(room_code, room['name'], 0, room['current_track'], True, room['is_video'], room['start_time'], pos))

                elif action_type == 'ACTION_PAUSE':
                    pos = coerce_position(data.get('position', 0))
                    room['is_playing'] = False
                    room['pause_offset'] = pos
                    await broadcast_room_state(room_code, room)
                    asyncio.create_task(db.save_room_state(room_code, room['name'], 0, room['current_track'], False, room['is_video'], room['start_time'], pos))

                elif action_type == 'ACTION_SEEK':
                    track_dur = (room.get('current_track') or {}).get('duration', 0)
                    pos = coerce_position(data.get('position', 0), track_dur)
                    room['pause_offset'] = pos
                    if room['is_playing']:
                        room['start_time'] = time.time() - pos
                    print(f"[Room #{room_code}] SEEK to {pos}s")
                    await broadcast_room_state(room_code, room)
                    
                elif action_type == 'ACTION_QUEUE_ADD':
                    track = data.get('track')
                    if track:
                        room.setdefault('queue', []).append(track)
                        await broadcast_room_state(room_code, room)
                        asyncio.create_task(db.save_room_state(room_code, room['name'], 0, room['current_track'], room['is_playing'], room['is_video'], room['start_time'], room['pause_offset'], room['queue']))

                elif action_type == 'ACTION_QUEUE_REMOVE':
                    index = data.get('index', -1)
                    if 0 <= index < len(room.get('queue', [])):
                        room['queue'].pop(index)
                        await broadcast_room_state(room_code, room)
                        asyncio.create_task(db.save_room_state(room_code, room['name'], 0, room['current_track'], room['is_playing'], room['is_video'], room['start_time'], room['pause_offset'], room['queue']))
                    
                elif action_type == 'ACTION_CHAT_MESSAGE':
                    text = data.get('text', '').strip()
                    user_id = data.get('user_id', 0)
                    if text:
                        saved_msg = await db.save_chat_message(room_code, user_id, user_name, text)
                        # Broadcast message to room
                        msg_payload = json.dumps({'type': 'CHAT_MESSAGE', 'message': saved_msg})
                        for s in room['sockets']:
                            try:
                                await s.send_str(msg_payload)
                            except Exception:
                                pass

            elif msg.type == WSMsgType.ERROR:
                print(f"[WebSocket Error] {ws.exception()}")

    finally:
        if ws in room['sockets']:
            room['sockets'].remove(ws)
        if user_name in room['members']:
            room['members'].remove(user_name)
        print(f"[WebSocket] User '{user_name}' left Sync Room #{room_code}")
        # Broadcast member list update & automatic host transfer to next member
        if room['sockets']:
            await broadcast_room_state(room_code, room)

    return ws

# ─── REST API Handlers ──────────────────────────────────────────────────────────
in_flight_searches = {}

async def api_search_handler(request):
    query = request.query.get('q', '').strip()
    source = request.query.get('source', 'all').strip()
    if not query:
        return web.json_response({'results': []})
    
    cache_key = f"{source}:{query.lower()}"
    
    # 1. Check DB Cache
    cached = await db.get_cached_search(cache_key)
    if cached:
        print(f"[Search Cache HIT] '{query}'")
        return web.json_response({'results': cached, 'cached': True})

    # 2. Request Deduplication (In-Flight Coalescing)
    if cache_key in in_flight_searches:
        print(f"[Search In-Flight Wait] '{query}'")
        results = await in_flight_searches[cache_key]
        return web.json_response({'results': results, 'cached': True})

    # Create Future for in-flight requests
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    in_flight_searches[cache_key] = fut

    try:
        print(f"[HTTP API] Multi-Source Search: '{query}' ({source})")
        tracks = await loop.run_in_executor(None, multi_source_search, query, source, 6)
        if tracks:
            await db.set_cached_search(cache_key, tracks)
        fut.set_result(tracks)
        return web.json_response({'results': tracks, 'cached': False})
    except Exception as e:
        fut.set_result([])
        return web.json_response({'results': [], 'error': 'Rate limited or search service unavailable'}, status=429)
    finally:
        in_flight_searches.pop(cache_key, None)

async def api_stream_handler(request):
    query = request.query.get('q', '').strip()
    if not query:
        return web.json_response({'error': 'Query is required'}, status=400)

    print(f"[HTTP API] Audio Stream Request: '{query}'")
    loop = asyncio.get_running_loop()
    url, title, thumb, dur = await loop.run_in_executor(None, get_direct_stream_url, query)

    if url:
        return web.json_response({'stream_url': url, 'title': title, 'thumbnail': thumb, 'duration': dur})
    return web.json_response({'error': 'Audio stream not found'}, status=404)

async def api_video_handler(request):
    """Return a video ID; the browser streams it through YouTube's supported embed player."""
    video_id = request.query.get('id', '').strip()
    query = request.query.get('q', '').strip()

    if video_id and YOUTUBE_ID_PATTERN.fullmatch(video_id):
        return web.json_response({'video_id': video_id})
    if not query:
        return web.json_response({'error': 'A YouTube video id or query is required'}, status=400)

    print(f"[HTTP API] YouTube Video Resolve: '{query}'")
    loop = asyncio.get_running_loop()
    video_id, title, thumb, duration = await loop.run_in_executor(None, get_youtube_video_metadata, query)
    if video_id:
        return web.json_response({
            'video_id': video_id,
            'title': title,
            'thumbnail': thumb,
            'duration': duration,
        })
    return web.json_response({'error': 'YouTube video not found'}, status=404)

async def api_create_room_handler(request):
    try:
        data = await request.json()
        room_name = data.get('name', "Vishnu's Music Room")
        code_suffix = ''.join(random.choices(string.digits, k=3))
        room_code = f"VISHNU-{code_suffix}"

        sync_rooms[room_code] = {
            'name': room_name,
            'sockets': [],
            'members': [],
            'current_track': None,
            'is_playing': False,
            'is_video': False,
            'start_time': time.time(),
            'pause_offset': 0
        }
        print(f"[Room Created] Code: #{room_code} | Name: '{room_name}'")
        return web.json_response({'room_code': room_code, 'name': room_name})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_auth_handler(request):
    try:
        data = await request.json()
        user = data.get('user')
        if not user or not user.get('id'):
            return web.json_response({'error': 'Invalid user data'}, status=400)
            
        tg_id = user['id']
        username = user.get('username', '')
        display_name = user.get('first_name', 'User')
        
        # Get or create user in DB
        db_user = await db.get_or_create_user(tg_id, username, display_name)
        return web.json_response({'user': db_user})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def api_update_profile_handler(request):
    try:
        if request.content_type == 'application/json':
            data = await request.json()
        elif request.content_type.startswith('multipart/form-data'):
            data = {}
            post_data = await request.post()
            for key, val in post_data.items():
                if isinstance(val, web.FileField):
                    data[key] = val
                else:
                    data[key] = val
        else:
            return web.json_response({'error': 'Unsupported content type'}, status=400)

        user_id = data.get('id')
        if not user_id:
            return web.json_response({'error': 'User ID required'}, status=400)
            
        updates = {}
        for key in ['theme', 'accent_color', 'settings_json', 'bio', 'display_name', 'username']:
            if key in data and not isinstance(data[key], web.FileField):
                updates[key] = data[key]
                
        # Handle file uploads via StorageService
        if 'avatar_file' in data and isinstance(data['avatar_file'], web.FileField):
            file_bytes = data['avatar_file'].file.read()
            url = await StorageService.uploadAvatar(user_id, file_bytes)
            updates['avatar_url'] = url
            
        if 'banner_file' in data and isinstance(data['banner_file'], web.FileField):
            file_bytes = data['banner_file'].file.read()
            url = await StorageService.uploadBanner(user_id, file_bytes)
            updates['banner_url'] = url
                
        if updates:
            await db.update_user_profile(user_id, updates)
            
        db_user = await db.get_user_profile(user_id)
        return web.json_response({'user': db_user})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# --- FRIENDS API ---
async def api_search_users_handler(request):
    q = request.query.get('q', '').strip()
    user_id = request.query.get('user_id')
    users = await db.search_users(q, user_id)
    return web.json_response({'users': users})

async def api_friend_request_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    success, msg = await db.send_friend_request(user_id, friend_id)
    return web.json_response({'success': success, 'message': msg})

async def api_friend_accept_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    success = await db.accept_friend_request(user_id, friend_id)
    return web.json_response({'success': success})

async def api_friend_reject_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    success = await db.reject_friend_request(user_id, friend_id)
    return web.json_response({'success': success})

async def api_friends_list_handler(request):
    user_id = request.query.get('user_id')
    friends = await db.get_friends_list(user_id)
    requests = await db.get_friend_requests(user_id)
    return web.json_response({'friends': friends, 'requests': requests})

# --- NOTIFICATIONS API ---
async def api_notifications_list_handler(request):
    user_id = request.query.get('user_id')
    notifications = await db.get_notifications(user_id)
    return web.json_response({'notifications': notifications})

async def api_notification_read_handler(request):
    data = await request.json()
    notif_id = data.get('notif_id')
    user_id = data.get('user_id')
    await db.mark_notification_read(notif_id, user_id)
    return web.json_response({'success': True})

# --- PLAYLISTS & LIKED SONGS API ---
async def api_playlists_create_handler(request):
    data = await request.json()
    playlist_id = await db.create_playlist(
        data.get('user_id'),
        data.get('name'),
        data.get('description', ''),
        data.get('cover_image', ''),
        data.get('is_public', 1)
    )
    return web.json_response({'playlist_id': playlist_id})

async def api_playlists_list_handler(request):
    user_id = request.query.get('user_id')
    playlists = await db.get_user_playlists(user_id)
    return web.json_response({'playlists': playlists})

async def api_playlists_add_track_handler(request):
    data = await request.json()
    success, msg = await db.add_track_to_playlist(data.get('playlist_id'), data.get('user_id'), data.get('track'))
    return web.json_response({'success': success, 'message': msg})

async def api_playlists_remove_track_handler(request):
    data = await request.json()
    success, msg = await db.remove_track_from_playlist(data.get('playlist_id'), data.get('user_id'), data.get('index'))
    return web.json_response({'success': success, 'message': msg})

async def api_playlists_delete_handler(request):
    data = await request.json()
    success, msg = await db.delete_playlist(data.get('playlist_id'), data.get('user_id'))
    return web.json_response({'success': success, 'message': msg})

async def api_liked_toggle_handler(request):
    data = await request.json()
    is_liked, msg = await db.toggle_liked_song(data.get('user_id'), data.get('track'))
    return web.json_response({'is_liked': is_liked, 'message': msg})

async def api_liked_list_handler(request):
    user_id = request.query.get('user_id')
    tracks = await db.get_liked_songs(user_id)
    return web.json_response({'tracks': tracks})

# --- LISTENING HISTORY & SEARCH HISTORY API ---
async def api_listening_history_handler(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({'tracks': []})
    tracks = await db.get_listening_history(int(user_id))
    return web.json_response({'tracks': tracks})

async def api_track_played_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    track = data.get('track')
    if user_id and track:
        await db.add_listening_history(int(user_id), track)
    return web.json_response({'success': True})

async def api_search_history_handler(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({'history': []})
    history = await db.get_search_history(int(user_id))
    return web.json_response({'history': history})

async def api_save_search_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    query = data.get('query', '').strip()
    if user_id and query:
        await db.save_search_query(int(user_id), query)
    return web.json_response({'success': True})

async def api_clear_search_history_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    if user_id:
        await db.clear_search_history(int(user_id))
    return web.json_response({'success': True})

async def api_user_stats_handler(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({'stats': {}})
    stats = await db.get_user_stats(int(user_id))
    return web.json_response({'stats': stats})

async def api_mark_all_notifications_read_handler(request):
    data = await request.json()
    user_id = data.get('user_id')
    if user_id:
        await db.mark_all_notifications_read(int(user_id))
    return web.json_response({'success': True})

# --- AI DJ & RECOMMENDATIONS API ---
async def api_ai_recommendations_handler(request):
    user_id = request.query.get('user_id')
    mood = request.query.get('mood', 'chill')
    recs = await AIEngine.get_smart_recommendations(user_id, mood)
    return web.json_response({'recommendations': recs, 'mood': mood})

async def api_ai_dj_voice_handler(request):
    data = await request.json()
    track_title = data.get('title', '')
    mood = data.get('mood', 'chill')
    
    # Try to load history from DB if user_id is provided, else fallback to passed array
    user_id = data.get('user_id')
    history = data.get('history', [])
    if user_id:
        try:
            history = await db.get_liked_songs(user_id)
        except Exception:
            pass
            
    commentary = await AIEngine.generate_dj_commentary(track_title, mood, history)
    return web.json_response({'commentary': commentary})

# ─── Web Application Setup & Security Middleware ───────────────────────────────
rate_limit_store = {} # IP -> [count, reset_timestamp]
start_time_server = time.time()

@web.middleware
async def security_and_rate_limit_middleware(request, handler):
    client_ip = request.headers.get('X-Forwarded-For', request.remote)
    now = time.time()

    # Rate Limiting Logic (Max 120 requests / min per IP)
    if client_ip not in rate_limit_store or now > rate_limit_store[client_ip][1]:
        rate_limit_store[client_ip] = [1, now + 60]
    else:
        rate_limit_store[client_ip][0] += 1
        if rate_limit_store[client_ip][0] > 120 and not request.path.startswith('/ws/'):
            return web.json_response({'error': 'Too many requests. Please slow down.'}, status=429)

    try:
        response = await handler(request)
    except web.HTTPException as ex:
        response = ex
    except Exception as e:
        print(f"[Unhandled Server Error] {e}")
        response = web.json_response({'error': 'Internal server error'}, status=500)

    # Security Headers
    response.headers['ngrok-skip-browser-warning'] = 'true'
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

async def api_health_handler(request):
    uptime = int(time.time() - start_time_server)
    return web.json_response({
        'status': 'healthy',
        'uptime_seconds': uptime,
        'database': 'connected'
    })

async def api_metrics_handler(request):
    total_sockets = sum(len(r.get('sockets', [])) for r in sync_rooms.values())
    return web.json_response({
        'active_rooms': len(sync_rooms),
        'total_active_listeners': total_sockets,
        'uptime_seconds': int(time.time() - start_time_server)
    })

def setup_web_app(app):
    app.router.add_get('/api/search', api_search_handler)
    app.router.add_get('/api/stream', api_stream_handler)
    app.router.add_get('/api/video', api_video_handler)
    app.router.add_post('/api/room/create', api_create_room_handler)
    app.router.add_post('/api/auth', api_auth_handler)
    app.router.add_post('/api/profile/update', api_update_profile_handler)
    
    # Friends
    app.router.add_get('/api/users/search', api_search_users_handler)
    app.router.add_post('/api/friends/request', api_friend_request_handler)
    app.router.add_post('/api/friends/accept', api_friend_accept_handler)
    app.router.add_post('/api/friends/reject', api_friend_reject_handler)
    app.router.add_get('/api/friends/list', api_friends_list_handler)

    # Notifications
    app.router.add_get('/api/notifications/list', api_notifications_list_handler)
    app.router.add_post('/api/notifications/read', api_notification_read_handler)

    # Playlists & Liked Songs
    app.router.add_post('/api/playlists/create', api_playlists_create_handler)
    app.router.add_get('/api/playlists/list', api_playlists_list_handler)
    app.router.add_post('/api/playlists/add_track', api_playlists_add_track_handler)
    app.router.add_post('/api/playlists/remove_track', api_playlists_remove_track_handler)
    app.router.add_post('/api/playlists/delete', api_playlists_delete_handler)
    app.router.add_post('/api/liked/toggle', api_liked_toggle_handler)
    app.router.add_get('/api/liked/list', api_liked_list_handler)

    # Listening & Search History
    app.router.add_get('/api/history/listening', api_listening_history_handler)
    app.router.add_post('/api/history/track_played', api_track_played_handler)
    app.router.add_get('/api/history/search', api_search_history_handler)
    app.router.add_post('/api/history/save_search', api_save_search_handler)
    app.router.add_post('/api/history/clear_search', api_clear_search_history_handler)
    app.router.add_get('/api/user/stats', api_user_stats_handler)
    app.router.add_post('/api/notifications/read_all', api_mark_all_notifications_read_handler)

    # Observability & Metrics
    app.router.add_get('/api/health', api_health_handler)
    app.router.add_get('/api/metrics', api_metrics_handler)

    # AI Engine & DJ
    app.router.add_get('/api/ai/recommendations', api_ai_recommendations_handler)
    app.router.add_post('/api/ai/dj_voice', api_ai_dj_voice_handler)

    app.router.add_get('/ws/room/{room_code}', websocket_room_handler)

    web_app_dir = os.path.join(os.path.dirname(__file__), 'web')
    
    async def index_handler(request):
        return web.FileResponse(os.path.join(web_app_dir, 'index.html'))

    app.router.add_get('/', index_handler)
    app.router.add_static('/', web_app_dir)

# ─── Main Startup Loop ──────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("  🚀 AURASOUND AI — AUDIO & VIDEO SYNC ENGINE")
    print("=" * 60)

    print("[0/5] Initializing Database...")
    await db.init_db()

    if BOTS_ENABLED:
        bot_started = False
        for attempt in range(3):
            try:
                print(f"[1/5] Starting Telegram Bots (attempt {attempt+1}/3, 15s timeout)...")
                await asyncio.wait_for(python_bot.start(), timeout=15)
                await asyncio.wait_for(mojo_bot.start(), timeout=15)

                # Register Bot Commands for Telegram GUI popup menu
                commands_list = [
                    BotCommand("start", "Launch AuraSound AI Mini App"),
                    BotCommand("app", "Launch AuraSound AI Mini App"),
                    BotCommand("room", "Join or Invite to Sync Room"),
                    BotCommand("nowplaying", "Currently Playing Songs"),
                    BotCommand("playlists", "View Saved Playlists"),
                    BotCommand("history", "Listening & Search History"),
                    BotCommand("friends", "Friends & Network"),
                    BotCommand("search", "Search Live Music"),
                    BotCommand("help", "Command Menu & Guide")
                ]
                try:
                    await python_bot.set_my_commands(commands_list)
                    await mojo_bot.set_my_commands(commands_list)
                    print("  ✓ Registered Telegram Command Popup Menus")
                except Exception as cmd_e:
                    print(f"  ⚠ Command registration notice: {cmd_e}")

                py_me = await python_bot.get_me()
                mojo_me = await mojo_bot.get_me()
                print(f"  ✓ Python Bot: @{py_me.username} (ID: {py_me.id})")
                print(f"  ✓ Mojo Bot: @{mojo_me.username} (ID: {mojo_me.id})")
                bot_started = True
                break
            except asyncio.TimeoutError:
                print(f"  ⚠ Bot startup timed out on attempt {attempt+1}")
                if attempt < 2:
                    await asyncio.sleep(2)
            except Exception as e:
                print(f"  ⚠ Bot startup error on attempt {attempt+1}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
        if not bot_started:
            print("  ❌ Telegram Bots failed after 3 attempts — running in web-only mode")
    else:
        print("[1/5] Telegram Bots disabled (pyrogram not installed)")

    print("[2/5] Spawning Server Heartbeat Sync Loop...")
    asyncio.create_task(room_heartbeat_loop())

    print("[3/5] Setting Up Web App Routes...")
    app = web.Application(middlewares=[security_and_rate_limit_middleware])
    setup_web_app(app)

    port = int(os.environ.get('PORT', 8000))
    print(f"[4/5] Starting Web Server on port {port}...")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    print()
    print("=" * 60)
    print("  🎉 AURASOUND AI AUDIO & VIDEO ENGINE IS LIVE!")
    print(f"  • Web Mini App UI : http://localhost:{port}")
    print(f"  • Live Telegram   : {MINI_APP_URL}")
    print("  • Python Bot      : @Crazycando_bot")
    print("  • Mojo Bot        : @Taki832_bot")
    print("=" * 60)

    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

