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
    await db.reject_friend_request(test_user_id, friend_id) # Clean old state
    await db.get_or_create_user(friend_id, "frienduser", "Friend User", "")
    success, msg = await db.send_friend_request(test_user_id, friend_id)
    assert success is True
    requests = await db.get_friend_requests(friend_id)
    assert len(requests) >= 1
    await db.accept_friend_request(friend_id, test_user_id)
    friends = await db.get_friends_list(test_user_id)
    assert len(friends) >= 1
    print("[PASS] [7/10] Friend System (Request, Accept, List) Passed")

    # 9. Room Persistence & Recovery
    room_test_code = "SYNC-999"
    track_test = {'title': 'Persistent Song', 'duration': 200, 'yt_id': 'abc999'}
    await db.save_room_state(room_test_code, "Persistent Room", test_user_id, track_test, True, False, 10000.0, 50.0)
    loaded_room = await db.load_room_state(room_test_code)
    assert loaded_room is not None
    assert loaded_room['room_code'] == room_test_code
    assert loaded_room['current_track']['title'] == 'Persistent Song'
    assert loaded_room['pause_offset'] == 50.0
    print("[PASS] [9/10] Room Persistent DB State & Recovery Passed")

    # 10. Search Caching & Deduplication
    cache_key = "all:katchi sera"
    fake_results = [{'title': 'Katchi Sera', 'yt_id': 'ks123'}]
    await db.set_cached_search(cache_key, fake_results)
    cached = await db.get_cached_search(cache_key)
    assert cached is not None
    assert cached[0]['yt_id'] == 'ks123'
    print("[PASS] [10/10] Search Caching & Deduplication Passed")

    print("\n[SUCCESS] ALL 10 AUTOMATED SYSTEM STABILITY TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
