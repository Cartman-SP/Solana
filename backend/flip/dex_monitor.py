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

TW_API_KEY = "new1_cdb5e73eb7174341be73ad05d22d69d9"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

async def check_and_set_unique_community(token):
    """Проверяет и устанавливает unique_community для токена"""
    try:
        # Если у токена нет community_id, пропускаем проверку
        if not token.community_id or token.community_id == '':
            return
        
        # Получаем все токены с таким же community_id, отсортированные по дате создания
        community_tokens = await sync_to_async(list)(
            Token.objects.filter(
                community_id=token.community_id,
                community_id__isnull=False,
                community_id__gt=''
            ).order_by('created_at')
        )
        
        # Если это первый токен в community, он уникальный
        if len(community_tokens) == 1:
            token.unique_community = True
            await sync_to_async(token.save)()
            print(f"Токен {token.address} - первый в community {token.community_id}, помечен как уникальный")
            return
        
        # Проверяем, есть ли более старые токены с таким же community_id
        has_older_tokens = any(
            t.community_id == token.community_id and 
            t.created_at < token.created_at and
            t.id != token.id
            for t in community_tokens
        )
        
        # Токен уникальный, если нет более старых токенов с таким же community_id
        is_unique = not has_older_tokens
        
        if token.unique_community != is_unique:
            token.unique_community = is_unique
            await sync_to_async(token.save)()
            status = "уникальный" if is_unique else "не уникальный"
            print(f"Токен {token.address} помечен как {status} в community {token.community_id}")
        
    except Exception as e:
        print(f"Ошибка при проверке unique_community для токена {token.address}: {e}")

async def get_twitter_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Получить Twitter username из community_id (логика из process_twitter.py)."""
    try:
        # Пробуем получить информацию о community
        url = f"{TW_BASE}/twitter/community/info"
        params = {"community_id": community_id}
        async with session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                community_info = data.get("community_info", {})
                # Ищем username в creator или first_member
                for user_key in ["creator", "first_member"]:
                    user_data = community_info.get(user_key, {})
                    username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
                    if username:
                        print(f"✅ Найден Twitter username: @{username} из {user_key}")
                        return f"@{username}"

        # Если не нашли в info, пробуем через members
        url = f"{TW_BASE}/twitter/community/members"
        params = {"community_id": community_id, "limit": 1}
        async with session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                # Ищем в разных структурах ответа
                members = []
                for key in ["members", "data", "users"]:
                    if key in data and isinstance(data[key], list):
                        members.extend(data[key])
                if members:
                    user_data = members[0]
                    username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
                    if username:
                        print(f"✅ Найден Twitter username: @{username} из members")
                        return f"@{username}"

        print(f"❌ Twitter username не найден для community {community_id}")
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении Twitter username: {e}")
        return None

def extract_community_id_from_data(data: dict) -> Optional[str]:
    """Извлекает community_id из данных WebSocket сообщения"""
    try:
        print(f"🔍 Анализирую данные для извлечения community_id:")
        print(f"   Доступные ключи: {list(data.keys())}")
        
        # Ищем community_id в различных возможных местах данных
        community_id = data.get('community_id') or data.get('communityId') or data.get('community')
        
        if not community_id:
            # Попробуем найти в socials если есть
            socials = data.get('socials', [])
            if isinstance(socials, list):
                print(f"   Проверяю socials: {socials}")
                for social in socials:
                    if isinstance(social, dict):
                        url = social.get('url', '')
                        if isinstance(url, str) and "communities" in url.lower():
                            parts = url.rstrip("/").split("/")
                            if parts:
                                community_id = parts[-1].strip()
                                community_id = community_id.strip('.,;:!?()[]{}"\'')
                                if community_id:
                                    print(f"   ✅ Найден community_id в socials: {community_id}")
                                    return community_id
        
        # Новый способ: ищем в links для Twitter
        if not community_id:
            links = data.get('links', [])
            if isinstance(links, list):
                print(f"   Проверяю links: {links}")
                for link in links:
                    if isinstance(link, dict) and link.get('type') == 'twitter':
                        url = link.get('url', '')
                        print(f"   Анализирую Twitter URL: {url}")
                        if isinstance(url, str) and "communities" in url.lower():
                            parts = url.rstrip("/").split("/")
                            print(f"   Части URL: {parts}")
                            if parts:
                                community_id = parts[-1].strip()
                                community_id = community_id.strip('.,;:!?()[]{}"\'')
                                if community_id:
                                    print(f"   ✅ Найден community_id в links: {community_id}")
                                    return community_id
        
        if not community_id:
            print(f"   ❌ community_id не найден")
        return community_id
    except Exception as e:
        print(f"   ❌ Ошибка при извлечении community_id: {e}")
        return None

async def process_token_data(data: dict, http_session: aiohttp.ClientSession):
    """Обрабатывает данные токена и получает твиттер если нужно"""
    try:
        # Берем адрес токена из нескольких возможных ключей
        token_address = data.get('tokenAddress') or data.get('mint')
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

        # Извлекаем community_id из данных (делаем это до любых выходов из функции)
        community_id = extract_community_id_from_data(data)
        if community_id:
            print(f"🔗 Найден community_id: {community_id}")
            # Сохраняем community_id для токена немедленно
            await sync_to_async(Token.objects.filter(id=token.id).update)(community_id=community_id)
            token.community_id = community_id
            # Обновляем unique_community вне зависимости от наличия твиттера
            await check_and_set_unique_community(token)
        else:
            print(f"❌ Не удалось извлечь community_id для токена {token_address}")

        # Проверяем, есть ли уже твиттер
        has_twitter = getattr(token, 'twitter_id', None) is not None
        if has_twitter:
            print(f"✅ У токена {token_address} уже есть твиттер — пропускаю получение")
            return

        # Если community_id найден — пытаемся получить username
        if community_id:
            username = await get_twitter_username(http_session, community_id)
            if username:
                twitter, _ = await sync_to_async(Twitter.objects.get_or_create)(name=username)
                await sync_to_async(Token.objects.filter(id=token.id).update)(twitter=twitter)
                print(f"✅ Твиттер {username} привязан к токену {token_address}")
            else:
                print(f"❌ Не удалось получить Twitter username по community_id {community_id}")
        else:
            print("ℹ️ Пропускаю попытку привязки твиттера: нет community_id")
            
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
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as http_session:
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