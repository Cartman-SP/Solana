import requests
import aiohttp
import asyncio
from config import get_headers
from typing import Dict, Optional

# API ключ для Pro API
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"

# Кэш для миграций
migration_cache: Dict[str, bool] = {}


# Асинхронная версия с использованием aiohttp для максимальной производительности
async def check_migration_async_fast(token_address: str, session: aiohttp.ClientSession, max_pages: int = 3) -> bool:
    """Быстрая асинхронная версия с переиспользованием сессии через Pro API"""
    if token_address in migration_cache:
        return migration_cache[token_address]
    
    base_url = "https://pro-api.solscan.io/v2.0/account/defi/activities"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    target_addresses = [
        "RAYpQbFNq9i3mu6cKpTKKRwwHFDeK5AuZz8xvxUrCgw",
        "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"
    ]
    
    for page in range(1, max_pages + 1):
        url = f"{base_url}?address={token_address}&page={page}&page_size=100&activity_type=ACTIVITY_POOL_CREATE&activity_type=ACTIVITY_POOL_CREATE"
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    activities = data.get('data', [])
                    
                    if not activities:
                        break
                    
                    # Проверяем активности
                    for activity in activities:
                        from_address = activity.get('from_address', '')
                        if from_address in target_addresses:
                            migration_cache[token_address] = True
                            return True
                else:
                    break
                    
        except Exception:
            break
    
    migration_cache[token_address] = False
    return False

# Синхронная версия для совместимости
def check_migration(token_address: str, max_pages: int = 5) -> bool:
    """Синхронная версия для совместимости"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(check_migration_async(token_address, max_pages))
    finally:
        loop.close() 