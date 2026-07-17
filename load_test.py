import asyncio
import aiohttp
import time
import json

SERVER_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
CONCURRENT_USERS = 50

async def simulate_user(user_id):
    async with aiohttp.ClientSession() as session:
        # 1. Health Check
        async with session.get(f"{SERVER_URL}/api/health") as resp:
            assert resp.status == 200

        # 2. Search Request
        async with session.get(f"{SERVER_URL}/api/search?q=Katchi+Sera&source=all") as resp:
            assert resp.status == 200
            data = await resp.json()

        # 3. Join WebSocket Sync Room
        room_code = "LOADTEST"
        ws_endpoint = f"{WS_URL}/ws/room/{room_code}?user=User_{user_id}"
        try:
            async with session.ws_connect(ws_endpoint) as ws:
                # Receive INIT_ROOM_STATE
                msg = await ws.receive_str()
                
                # Send Chat Message
                await ws.send_json({
                    "type": "ACTION_CHAT_MESSAGE",
                    "text": f"Hello from simulated user {user_id}",
                    "user_id": user_id
                })
                
                await asyncio.sleep(0.5)
                await ws.close()
        except Exception as e:
            print(f"[User {user_id} WS Error] {e}")

async def run_load_test():
    print("=" * 60)
    print(f" 🚀 AURASOUND LOAD TEST ({CONCURRENT_USERS} CONCURRENT USERS)")
    print("=" * 60)

    start = time.time()
    tasks = [simulate_user(i) for i in range(1, CONCURRENT_USERS + 1)]
    await asyncio.gather(*tasks)
    duration = time.time() - start

    print(f"[SUCCESS] Completed load test for {CONCURRENT_USERS} concurrent users in {duration:.2f} seconds!")
    print(f"Average throughput: {CONCURRENT_USERS / duration:.2f} req/sec")

if __name__ == "__main__":
    asyncio.run(run_load_test())
