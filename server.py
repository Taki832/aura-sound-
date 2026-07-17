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

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', write_through=True)

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# ─── Telegram Bot Credentials & WebApp Config ─────────────────────────
API_ID          = 28640193
API_HASH        = "f21327975cce7fb1e9c0fd9d72e0812a"
TOKEN_PYTHON    = "8045450869:AAEPoFX1EkqY8ENOk1yiia4sbv8AmBBjdhg"  # @Crazycando_bot
TOKEN_MOJO      = "8012607564:AAEQpYlPnXmhIIS2PFv4q3YXp0GGY2MdW2U"  # @Taki832_bot
MINI_APP_URL    = os.environ.get("MINI_APP_URL", "https://certainly-unblessed-crablike.ngrok-free.dev")

SESSION_DIR = r"c:\Users\VISHNU\Videos\mine"
python_bot = Client(os.path.join(SESSION_DIR, "python_bot_session"), api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN_PYTHON)
mojo_bot   = Client(os.path.join(SESSION_DIR, "mojo_bot_session"),   api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN_MOJO)

# ─── Global Server-Driven Room State ─────────────────────────────────────────
sync_rooms = {}
ROOM_CODE_PATTERN = re.compile(r"^[A-Z0-9-]{3,64}$")
YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,32}$")

# ─── Telegram Bot Handlers ─────────────────────────────────────────────────────
@python_bot.on_message(filters.command("start") | filters.command("app"))
@mojo_bot.on_message(filters.command("start") | filters.command("app"))
async def send_mini_app_button(client, message):
    user_name = message.from_user.first_name if message.from_user else "Vishnu"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Open AuraSound AI Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
        [InlineKeyboardButton("🌐 Open in Browser", url=MINI_APP_URL)]
    ])
    await message.reply_text(
        f"👋 **Welcome, {user_name}!**\n\n"
        "🎬 **AuraSound.AI — Audio & Video Sync Room**\n"
        "Tap the button below to launch the Mini App inside Telegram, listen to music or watch YouTube video songs live with friends!",
        reply_markup=keyboard
    )

# ─── Multi-Source Extraction Helpers ────────────────────────────────────────────
def multi_source_search(query: str, source: str = 'all', limit: int = 6):
    opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch'
    }
    
    search_query = query
    if source == 'spotify':
        search_query = f"{query} spotify official audio"
    elif source == 'jiosaavn':
        search_query = f"{query} jiosaavn audio"
    elif source == 'youtube':
        search_query = f"{query} youtube music video"

    results = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{limit}:{search_query}", download=False)
            if info and info.get('entries'):
                for entry in info['entries']:
                    src_tag = source if source != 'all' else ('spotify' if 'spotify' in entry.get('title','').lower() else 'youtube')
                    results.append({
                        'title': entry.get('title', 'Unknown Track'),
                        'url': entry.get('url', ''),
                        'thumbnail': entry.get('thumbnail', ''),
                        'duration': entry.get('duration', 0),
                        'id': entry.get('id', ''),
                        'source': src_tag
                    })
        except Exception as e:
            print(f"[Search Error] {e}")
    return results

def get_direct_stream_url(query: str):
    opts = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if info and info.get('entries'):
                v = info['entries'][0]
                return v.get('url'), v.get('title'), v.get('thumbnail', ''), v.get('duration', 0)
        except Exception as e:
            print(f"[Direct Audio Stream Error] {e}")
    return None, None, None, 0

def get_youtube_video_metadata(query: str):
    """Resolve a search query to a YouTube video ID for the official embed player."""
    opts = {'noplaylist': True, 'quiet': True, 'no_warnings': True}
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
            for code, room in list(sync_rooms.items()):
                if room['sockets']:
                    await broadcast_room_state(code, room, 'SERVER_HEARTBEAT')
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
        sync_rooms[room_code] = {
            'name': f"{user_name}'s Sync Room",
            'sockets': [],
            'members': [],
            'current_track': None,
            'is_playing': False,
            'is_video': False,
            'start_time': time.time(),
            'pause_offset': 0
        }

    room = sync_rooms[room_code]
    room['sockets'].append(ws)
    room['members'].append(user_name)

    print(f"[WebSocket] User '{user_name}' joined Sync Room #{room_code} (Active: {len(room['sockets'])})")

    now = time.time()
    current_pos = room_position(room, now)
    await ws.send_str(json.dumps({
        'type': 'INIT_ROOM_STATE',
        'room_code': room_code,
        'members': room['members'],
        'track': room['current_track'],
        'is_playing': room['is_playing'],
        'is_video': room.get('is_video', False),
        'current_position': current_pos
    }))

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                action_type = data.get('type')

                if action_type == 'ACTION_PLAY':
                    track = data.get('track') or room['current_track']
                    if not isinstance(track, dict):
                        continue
                    pos = coerce_position(data.get('position', 0), track.get('duration', 0))
                    is_vid = data.get('is_video', False)
                    room['current_track'] = track
                    room['is_playing'] = True
                    room['is_video'] = is_vid
                    room['pause_offset'] = pos
                    room['start_time'] = time.time() - pos
                    print(f"[Room #{room_code}] PLAY {'VIDEO' if is_vid else 'AUDIO'}: '{track.get('title')}' at {pos}s")
                    await broadcast_room_state(room_code, room)

                elif action_type == 'ACTION_PAUSE':
                    duration = (room['current_track'] or {}).get('duration', 0)
                    pos = coerce_position(data.get('position', room_position(room)), duration)
                    room['is_playing'] = False
                    room['pause_offset'] = pos
                    print(f"[Room #{room_code}] PAUSE at {pos}s")
                    await broadcast_room_state(room_code, room)

                elif action_type == 'ACTION_SEEK':
                    duration = (room['current_track'] or {}).get('duration', 0)
                    pos = coerce_position(data.get('position', 0), duration)
                    room['pause_offset'] = pos
                    if room['is_playing']:
                        room['start_time'] = time.time() - pos
                    print(f"[Room #{room_code}] SEEK to {pos}s")
                    await broadcast_room_state(room_code, room)

            elif msg.type == WSMsgType.ERROR:
                print(f"[WebSocket Error] {ws.exception()}")

    finally:
        if ws in room['sockets']:
            room['sockets'].remove(ws)
        if user_name in room['members']:
            room['members'].remove(user_name)
        print(f"[WebSocket] User '{user_name}' left Sync Room #{room_code}")

    return ws

# ─── REST API Handlers ──────────────────────────────────────────────────────────
async def api_search_handler(request):
    query = request.query.get('q', '').strip()
    source = request.query.get('source', 'all').strip()
    if not query:
        return web.json_response({'results': []})
    
    print(f"[HTTP API] Multi-Source Search: '{query}' ({source})")
    loop = asyncio.get_running_loop()
    tracks = await loop.run_in_executor(None, multi_source_search, query, source, 6)
    return web.json_response({'results': tracks})

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

# ─── Web Application Setup & Middleware ─────────────────────────────────────────
@web.middleware
async def ngrok_skip_warning_middleware(request, handler):
    response = await handler(request)
    response.headers['ngrok-skip-browser-warning'] = 'true'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def setup_web_app(app):
    app.router.add_get('/api/search', api_search_handler)
    app.router.add_get('/api/stream', api_stream_handler)
    app.router.add_get('/api/video', api_video_handler)
    app.router.add_post('/api/room/create', api_create_room_handler)
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

    print("[1/4] Starting Telegram Bots...")
    await python_bot.start()
    await mojo_bot.start()

    print("[2/4] Spawning Server Heartbeat Sync Loop...")
    asyncio.create_task(room_heartbeat_loop())

    print("[3/4] Setting Up Web App Routes...")
    app = web.Application(middlewares=[ngrok_skip_warning_middleware])
    setup_web_app(app)

    port = int(os.environ.get('PORT', 8000))
    print(f"[4/4] Starting Web Server on port {port}...")
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
    asyncio.run(main())
