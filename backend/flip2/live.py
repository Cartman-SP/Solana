import asyncio
import websockets
import json
import os
import sys
import django
from datetime import datetime
# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token, Twitter
from asgiref.sync import sync_to_async

# Хранилище подключенных клиентов расширения
extension_clients = set()

async def handler(websocket, path):
    """Обработчик веб-сокет соединений для расширения"""
    extension_clients.add(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Обработка ping сообщений
                if data.get('type') == 'ping':
                    # Отправляем pong ответ
                    pong_response = {
                        'type': 'pong',
                        'timestamp': data.get('timestamp', 0)
                    }
                    await websocket.send(json.dumps(pong_response))
                    
            except json.JSONDecodeError:
                # Если сообщение не является JSON, игнорируем его
                pass
    except:
        pass
    finally:
        extension_clients.discard(websocket)

async def broadcast_to_extension(data):
    """Отправляет данные всем подключенным расширениям"""
    if not extension_clients:
        return
        
    disconnected_clients = set()
    for client in extension_clients:
        try:
            await client.send(json.dumps(data))
        except:
            disconnected_clients.add(client)
    
    extension_clients.difference_update(disconnected_clients)

async def get_user_dev_data(user_address):
    """Получает данные UserDev из базы данных"""
    try:
        user_dev = await sync_to_async(UserDev.objects.get)(adress=user_address)
                
        # Получаем последние 5 токенов с ATH > 0 и НЕ мигрированных
        recent_tokens = await sync_to_async(list)(
            Token.objects.filter(
                dev=user_dev,
                ath__gt=0,
                processed = True
            ).order_by('-created_at')[:3]
        )
        
        # Рассчитываем средний ATH
        if recent_tokens:
            avg_ath = sum(token.ath for token in recent_tokens) / len(recent_tokens)
        else:
            avg_ath = 0
        
        # Получаем последние 100 токенов для расчета процента миграций
        recent_100_tokens = await sync_to_async(list)(
            Token.objects.filter(
                dev=user_dev,
                processed = True
            ).order_by('-created_at')[:100]
        )
        
        # Рассчитываем процент мигрированных токенов
        if recent_100_tokens:
            migrated_count = sum(1 for token in recent_100_tokens if token.migrated)
            migration_percentage = (migrated_count / len(recent_100_tokens)) * 100
        else:
            migration_percentage = 0
        
        # Получаем последние 3 токена разработчика (исключая текущий)
        recent_dev_tokens = await sync_to_async(list)(
            Token.objects.filter(
                dev=user_dev,
                processed = True
            ).exclude(
                address=user_address  # Исключаем текущий токен
            ).order_by('-created_at')[:3]
        )
        
        # Формируем список последних токенов
        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:8] + '...',  # Сокращенное название
                'ath': token.ath
            })
            
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_tokens': user_dev.total_tokens,
            'whitelist': user_dev.whitelist,
            'blacklist': user_dev.blacklist,
            'migrations': round(migration_percentage, 1),  # Процент мигрированных токенов
            'recent_tokens': recent_tokens_info  # Последние 3 токена
        }
    except Exception as e:
        print(e)
        return{
            'ath': 0,
            'total_tokens': 1,
            'whitelist': False,
            'blacklist': False,
            'migrations': 0,
            'recent_tokens': []
        }

async def get_twitter_data(twitter):
    """Получает данные UserDev из базы данных"""
    try:
        user_dev = await sync_to_async(Twitter.objects.get)(name=twitter)
        
        if user_dev.blacklist:
            return None
        
        # Получаем последние 5 токенов с ATH > 0 и НЕ мигрированных
        recent_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                ath__gt=0,
                processed = True
            ).order_by('-created_at')[:3]
        )
        
        # Рассчитываем средний ATH
        if recent_tokens:
            avg_ath = sum(token.ath for token in recent_tokens) / len(recent_tokens)
        else:
            avg_ath = 0
        
        # Получаем последние 100 токенов для расчета процента миграций
        recent_100_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                processed = True
            ).order_by('-created_at')[:100]
        )
        
        # Рассчитываем процент мигрированных токенов
        if recent_100_tokens:
            migrated_count = sum(1 for token in recent_100_tokens if token.migrated)
            migration_percentage = (migrated_count / len(recent_100_tokens)) * 100
        else:
            migration_percentage = 0
        
        # Получаем последние 3 токена разработчика
        recent_dev_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                processed = True
            ).order_by('-created_at')[:3]
        )
        
        # Формируем список последних токенов
        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:8] + '...',  # Сокращенное название
                'ath': token.ath
            })
                
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_tokens': user_dev.total_tokens,
            'whitelist': user_dev.whitelist,
            'blacklist': user_dev.blacklist,
            'migrations': round(migration_percentage, 1),  # Процент мигрированных токенов
            'recent_tokens': recent_tokens_info  # Последние 3 токена
        }
    except Exception as e:
        print(e)
        return{
            'ath': 0,
            'total_tokens': 1,
            'whitelist': False,
            'blacklist': False,
            'migrations': 0,
            'recent_tokens': []
        }


async def process_token_data(data):
    """Обрабатывает данные токена и отправляет в расширение"""
    try:
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        twitter = data.get('twitter_name','')
        twitter_followers = data.get('twitter_followers','')
        if twitter == '':
            return
        user_dev_data = await get_user_dev_data(user)
        twitter_data = await get_twitter_data(twitter)
        if user_dev_data is None:
            return
        # Проверяем twitter_data и устанавливаем значения по умолчанию
        if twitter_data is None:
            return
        extension_data = {
            'mint': mint,
            'user': user,
            'user_name': name,
            'twitter_name': twitter,
            'followers': twitter_followers,
            'symbol': symbol,
            'source': source,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_total_tokens': user_dev_data['total_tokens'],
            'user_ath': user_dev_data['ath'],
            'user_migrations': user_dev_data['migrations'],
            'user_recent_tokens': user_dev_data['recent_tokens'],
            'user_whitelisted': user_dev_data['whitelist'],
            'user_blacklisted': user_dev_data['blacklist'],
            'twitter_total_tokens': twitter_data['total_tokens'],
            'twitter_ath': twitter_data['ath'],
            'twitter_migrations': twitter_data['migrations'],
            'twitter_recent_tokens': twitter_data['recent_tokens'],
            'twitter_whitelisted': twitter_data['whitelist'],
            'twitter_blacklisted': twitter_data['blacklist'],
        }
        
        await broadcast_to_extension(extension_data)
        twitter_acc = await sync_to_async(Twitter.objects.get)(name=twitter)
        twitter_acc.ath = twitter_data['ath']
        await sync_to_async(twitter_acc.save)()
        # Единственный вывод с оформленными данными
        recent_tokens_str = " | ".join([f"{token['name']}: {token['ath']}" for token in user_dev_data['recent_tokens']])
        print(f"📤 EXTENSION → {extension_data['source'].upper()} | {extension_data['user_name']} ({extension_data['symbol']}) | User ATH: {extension_data['user_ath']} | User Tokens: {extension_data['user_total_tokens']} | User Migrations: {extension_data['user_migrations']}% | Recent: {recent_tokens_str} | User: {extension_data['user'][:8]}...")
        
    except:
        pass

async def listen_to_websocket():
    """Слушает основной веб-сокет и обрабатывает данные"""
    while True:
        try:
            async with websockets.connect("ws://localhost:9393") as websocket:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        await process_token_data(data)
                    except:
                        pass
        except:
            await asyncio.sleep(1)

async def start_extension_server():
    """Запускает веб-сокет сервер для расширения"""
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()

async def main():
    """Основная функция - запускает оба сервиса"""
    extension_server_task = asyncio.create_task(start_extension_server())
    websocket_listener_task = asyncio.create_task(listen_to_websocket())
    await asyncio.gather(extension_server_task, websocket_listener_task)

if __name__ == "__main__":
    asyncio.run(main()) 
