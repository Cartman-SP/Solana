import asyncio
import websockets
import json
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token
from asgiref.sync import sync_to_async

async def create_user_and_token(data):
    """Создает UserDev и Token из полученных данных"""
    try:
        # Извлекаем данные
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        uri = data.get('uri', '')
        twitter_name = data.get('twitter_name','')
        twitter_followers = data.get('twitter_followers','')
        print(symbol)
        token_created = False
        if(twitter_name):
            twitter, created = await sync_to_async(Twitter.objects.get_or_create)(
                name=twitter_name,
                followers = twitter_followers,
            )
        user_dev, created = await sync_to_async(UserDev.objects.get_or_create)(
            adress=user,
            defaults={
                'total_tokens': 0,
            }
        )
        
        if user_dev.blacklist == False and twitter.blacklist == False:
            token, token_created = await sync_to_async(Token.objects.get_or_create)(
                address=mint,
                defaults={
                    'dev': user_dev,
                    'ath': 0,
                    'migrated': False
                }
            )
        
        if token_created:
            user_dev.total_tokens += 1
            if user_dev.admin:
                user_dev.admin.total_tokens += 1
                user_dev.admin.save()
            await sync_to_async(user_dev.save)()
            print("dev saved:", symbol)
    except Exception as e:
        print(e)
        pass

async def listen_to_websocket():
    while True:
        try:
            async with websockets.connect("ws://localhost:9393") as websocket:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        
                        # Создаем записи в базе данных
                        await create_user_and_token(data)
                        
                    except:
                        pass
                        
        except:
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(listen_to_websocket()) 