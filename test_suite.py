import asyncio
import json
import time
import db

async def run_tests():
    print("=" * 60)
    print(" [TEST SUITE] AURASOUND AUTOMATED SYSTEM TESTS")
    print("=" * 60)
    
    # 1. Initialize DB
    await db.init_db()
    print("[PASS] [1/8] Database Schema Initialization Passed")

    # 2. Authentication / User Creation
    test_user_id = 999999
    user = await db.get_or_create_user(test_user_id, "testuser", "Test User", "")
    assert user['id'] == test_user_id
    assert user['username'] == "testuser"
    print("[PASS] [2/8] User Authentication & Creation Passed")

    # 3. Profile Update
    await db.update_user_profile(test_user_id, {
        'display_name': 'Updated Test User',
        'bio': 'Testing AuraSound 2032',
        'accent_color': '#1DB954'
    })
    updated_user = await db.get_user_profile(test_user_id)
    assert updated_user['display_name'] == 'Updated Test User'
    assert updated_user['bio'] == 'Testing AuraSound 2032'
    print("[PASS] [3/8] Profile Update & Persistence Passed")

    # 4. Settings Persistence
    settings_data = json.dumps({'amoled': True, 'gapless': True, 'hqAudio': True})
    await db.update_user_profile(test_user_id, {'settings_json': settings_data})
    settings_user = await db.get_user_profile(test_user_id)
    assert settings_user['settings_json'] == settings_data
    print("[PASS] [4/8] Settings JSON Persistence Passed")

    # 5. Room Chat Message Persistence
    room_code = "TEST-ROOM"
    saved_msg = await db.save_chat_message(room_code, test_user_id, "Test User", "Hello AuraSound!")
    messages = await db.get_room_messages(room_code)
    assert len(messages) >= 1
    assert messages[0]['text'] == "Hello AuraSound!"
    print("[PASS] [5/8] Room Chat Message Persistence Passed")

    # 6. Notifications System
    await db.create_notification(test_user_id, "system", "Welcome", "Test notification message")
    notifications = await db.get_notifications(test_user_id)
    assert len(notifications) >= 1
    assert notifications[0]['title'] == "Welcome"
    await db.mark_notification_read(notifications[0]['id'], test_user_id)
    print("[PASS] [6/8] Notifications Creation & Read Status Passed")

    # 7. Friends System
    friend_id = 888888
    await db.get_or_create_user(friend_id, "frienduser", "Friend User", "")
    success, msg = await db.send_friend_request(test_user_id, friend_id)
    assert success is True
    requests = await db.get_friend_requests(friend_id)
    assert len(requests) >= 1
    await db.accept_friend_request(friend_id, test_user_id)
    friends = await db.get_friends_list(test_user_id)
    assert len(friends) >= 1
    print("[PASS] [7/8] Friend System (Request, Accept, List) Passed")

    # 8. Playlists & Liked Songs
    pl_id = await db.create_playlist(test_user_id, "My Favorites", "Best tunes")
    assert pl_id > 0
    track = {'title': 'Test Song', 'yt_id': 'xyz123', 'duration': 180}
    await db.add_track_to_playlist(pl_id, test_user_id, track)
    playlists = await db.get_user_playlists(test_user_id)
    assert len(playlists[0]['tracks']) >= 1
    
    is_liked, _ = await db.toggle_liked_song(test_user_id, track)
    assert is_liked is True
    liked = await db.get_liked_songs(test_user_id)
    assert len(liked) >= 1
    print("[PASS] [8/8] Playlists & Liked Songs Operations Passed")

    print("\n[SUCCESS] ALL 8 AUTOMATED SYSTEM TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
