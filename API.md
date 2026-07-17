# AuraSound 2032 — Production API Documentation

## Authentication & Profiles
- **POST `/api/auth`**: Authenticate Telegram user or guest session.
- **POST `/api/profile/update`**: Update profile details (username, bio, display name, avatar, banner).

## Multi-Source Search & Streaming
- **GET `/api/search?q={query}&source={all|spotify|youtube|jiosaavn}`**: Search tracks with multi-level caching.
- **GET `/api/stream?q={query}`**: Fetch direct audio stream URL.
- **GET `/api/video?id={video_id}&q={query}`**: Resolve video metadata for YouTube embed player.

## Sync Rooms & WebSockets
- **POST `/api/room/create`**: Create a sync room with a unique code.
- **WebSocket `/ws/room/{room_code}?user={username}`**: Real-time room synchronization engine (Play, Pause, Seek, Chat).

## Friends & Social Graph
- **GET `/api/users/search?q={query}`**: Search users.
- **POST `/api/friends/request`**: Send a friend request.
- **POST `/api/friends/accept`**: Accept a friend request.
- **POST `/api/friends/reject`**: Reject a friend request.
- **GET `/api/friends/list?user_id={id}`**: Fetch friends list & pending requests.

## Notifications & Playlists
- **GET `/api/notifications/list?user_id={id}`**: Fetch notifications.
- **POST `/api/notifications/read`**: Mark notification read.
- **POST `/api/playlists/create`**: Create playlist.
- **GET `/api/playlists/list?user_id={id}`**: Fetch playlists.
- **POST `/api/playlists/add_track`**: Add track to playlist.
- **POST `/api/liked/toggle`**: Toggle liked song.
- **GET `/api/liked/list?user_id={id}`**: Fetch liked songs.

## Observability
- **GET `/api/health`**: System health check status.
- **GET `/api/metrics`**: Server metrics (active rooms, connected sockets, uptime).
