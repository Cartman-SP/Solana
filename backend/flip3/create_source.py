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

