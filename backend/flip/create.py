import asyncio
import websockets
import json
import os
import sys
import django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from datetime import datetime, timezone, timedelta
from asgiref.sync import sync_to_async

from mainapp.models import UserDev, Token

async def get_or_create_userdev(trader_public_key):
    """Получить или создать UserDev по адресу"""
    try:
        userdev = await sync_to_async(UserDev.objects.get)(adress=trader_public_key)
    except UserDev.DoesNotExist:
        userdev = await sync_to_async(UserDev.objects.create)(adress=trader_public_key)
    return userdev

async def check_and_set_unique_community(new_token):
    """Проверяет и устанавливает unique_community для нового токена"""
    try:
        # Если у токена нет community_id, пропускаем проверку
        if not new_token.community_id or new_token.community_id == '':
            return
        
        # Получаем все токены с таким же community_id, отсортированные по дате создания
        community_tokens = await sync_to_async(list)(
            Token.objects.filter(
                community_id=new_token.community_id,
                community_id__isnull=False,
                community_id__gt=''
            ).order_by('created_at')
        )
        
        # Если это первый токен в community, он уникальный
        if len(community_tokens) == 1:
            new_token.unique_community = True
            await sync_to_async(new_token.save)()
            print(f"Токен {new_token.address} - первый в community {new_token.community_id}, помечен как уникальный")
            return
        
        # Проверяем, есть ли более старые токены с таким же community_id
        has_older_tokens = any(
            token.community_id == new_token.community_id and 
            token.created_at < new_token.created_at and
            token.id != new_token.id
            for token in community_tokens
        )
        
        # Токен уникальный, если нет более старых токенов с таким же community_id
        is_unique = not has_older_tokens
        
        if new_token.unique_community != is_unique:
            new_token.unique_community = is_unique
            await sync_to_async(new_token.save)()
            status = "уникальный" if is_unique else "не уникальный"
            print(f"Токен {new_token.address} помечен как {status} в community {new_token.community_id}")
        
    except Exception as e:
        print(f"Ошибка при проверке unique_community для токена {new_token.address}: {e}")

async def create_token_from_message(data):
    """Создать токен из данных сообщения"""
    try:
        # Получить или создать UserDev
        userdev = await get_or_create_userdev(data['traderPublicKey'])
        
        # Создать токен
        token = await sync_to_async(Token.objects.create)(
            address=data['mint'],
            dev=userdev,
            bonding_curve=data['bondingCurveKey'],
            initialBuy=data['solAmount'],
            uri=data['uri'],
            name=data['name'],
            symbol=data['symbol']
        )
        
        print(f"Создан токен: {token.name} ({token.symbol}) - {token.address}")
        
        # Проверяем и устанавливаем unique_community
        await check_and_set_unique_community(token)
        
        return token
        
    except Exception as e:
        print(f"Ошибка при создании токена: {e}")
        return None

async def subscribe():
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as websocket:
        
        # Subscribing to token creation events
        payload = {
            "method": "subscribeNewToken",
        }
        await websocket.send(json.dumps(payload))
        
        async for message in websocket:
            data = json.loads(message)
            print(f"Получено сообщение: {data}")
            
            # Проверяем, что это сообщение о создании токена
            if data.get('txType') == 'create':
                await create_token_from_message(data)
    
# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())

