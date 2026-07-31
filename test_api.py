import httpx
import asyncio
import json

async def test_video_api():
    api_key = "sk-x44sRSwk2lzgUBOz3Z5RAu6uerXfgfIpYvOaXYibJfiW2M5EzDnEHJsGeBuO"
    base_url = "https://api.gen-api.ru/v1"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "ltx-video",
        "prompt": "test video generation",
        "duration": 5,
        "size": "1280x720"
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{base_url}/video/generations",
                headers=headers,
                json=payload
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test_video_api())