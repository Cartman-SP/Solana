import asyncio
import websockets
import json
import os
import sys
import django
import aiohttp
from typing import Optional

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token, Twitter
from asgiref.sync import sync_to_async

TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

async def get_twitter_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    try:
        url = f"{TW_BASE}/twitter/community/info"
        params = {"community_id": community_id}
        async with session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                community_info = data.get("community_info", {})
                for user_key in ["creator", "first_member"]:
                    user_data = community_info.get(user_key, {})
                    username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
                    if username:
                        return f"@{username}"
        
        # fallback через members
        url = f"{TW_BASE}/twitter/community/members"
        params = {"community_id": community_id, "limit": 1}
        async with session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                members = []
                for key in ["members", "data", "users"]:
                    if key in data and isinstance(data[key], list):
                        members.extend(data[key])
                if members:
                    user_data = members[0]
                    username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
                    if username:
                        return f"@{username}"
        return None
    except Exception:
        return None

def extract_community_id_from_data(data: dict) -> Optional[str]:
    """Извлекает community_id из данных WebSocket сообщения"""
    try:
        # Ищем community_id в различных возможных местах данных
        community_id = data.get('community_id') or data.get('communityId') or data.get('community')
        
        if not community_id:
            # Попробуем найти в socials если есть
            socials = data.get('socials', [])
            if isinstance(socials, list):
                for social in socials:
                    if isinstance(social, dict):
                        url = social.get('url', '')
                        if isinstance(url, str) and "communities" in url.lower():
                            parts = url.rstrip("/").split("/")
                            if parts:
                                community_id = parts[-1].strip()
                                community_id = community_id.strip('.,;:!?()[]{}"\'')
                                if community_id:
                                    return community_id
        
        return community_id
    except Exception:
        return None

async def process_token_data(data: dict, http_session: aiohttp.ClientSession):
    """Обрабатывает данные токена и получает твиттер если нужно"""
    try:
        token_address = data.get('tokenAddress')
        if not token_address:
            print("❌ В данных отсутствует tokenAddress/mint")
            return
        
        print(f"🔍 Обрабатываю токен: {token_address}")
        
        # Проверяем, существует ли токен
        token_exists = await sync_to_async(Token.objects.filter(address=token_address).exists)()
        
        if not token_exists:
            print(f"❌ Токен {token_address} не найден в базе данных")
            return
        
        # Получаем токен
        token = await sync_to_async(Token.objects.select_related('twitter').get)(address=token_address)
        
        # Проверяем, есть ли уже твиттер
        has_twitter = getattr(token, 'twitter_id', None) is not None
        if has_twitter:
            print(f"✅ У токена {token_address} уже есть твиттер")
            return
        
        # Извлекаем community_id из данных
        community_id = extract_community_id_from_data(data)
        if not community_id:
            print(f"❌ Не удалось извлечь community_id для токена {token_address}")
            return
        
        print(f"🔗 Найден community_id: {community_id}")
        
        # Сохраняем community_id для токена
        await sync_to_async(Token.objects.filter(id=token.id).update)(community_id=community_id)
        
        # Получаем твиттер username
        username = await get_twitter_username(http_session, community_id)
        if username:
            twitter, _ = await sync_to_async(Twitter.objects.get_or_create)(name=username)
            await sync_to_async(Token.objects.filter(id=token.id).update)(twitter=twitter)
            print(f"✅ Твиттер {username} привязан к токену {token_address}")
        else:
            print(f"❌ Не удалось получить Twitter username по community_id {community_id}")
            
    except Exception as e:
        print(f"❌ Ошибка при обработке токена: {e}")

async def dex_websocket_client():
    """Клиент для подключения к DEX монитору с обработкой твиттеров"""
    uri = "ws://205.172.58.34/ws/"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Подключение к WebSocket установлено")
            print("📡 Ожидание новых токенов Solana...")
            print("-" * 50)
            
            # Создаем HTTP сессию для API запросов
            async with aiohttp.ClientSession() as http_session:
                # Бесконечный цикл для получения сообщений
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Проверяем, является ли это приветственным сообщением
                    if 'data' not in data:
                        print("👋 Приветственное сообщение:", json.dumps(data, indent=2, ensure_ascii=False))
                        print("-" * 50)
                        continue
                    
                    # Обрабатываем данные токенов
                    token_data = data.get('data')
                    if isinstance(token_data, list):
                        for token_item in token_data:
                            print(json.dumps(token_item, indent=2, ensure_ascii=False))
                            print("-" * 50)
                            
                            # Обрабатываем данные токена
                            await process_token_data(token_item, http_session)
                    else:
                        print("❌ Неожиданный формат данных:", json.dumps(data, indent=2, ensure_ascii=False))
                        
    except websockets.exceptions.ConnectionClosed:
        print("❌ Соединение закрыто")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(dex_websocket_client())