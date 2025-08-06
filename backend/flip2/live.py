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

from mainapp.models import UserDev, Token
from asgiref.sync import sync_to_async

# Импортируем функцию получения баланса
from get_balance import get_sol_balance_async

# Хранилище подключенных клиентов расширения
extension_clients = set()

async def handler(websocket, path):
    """Обработчик веб-сокет соединений для расширения"""
    extension_clients.add(websocket)
    
    try:
        async for message in websocket:
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
        
        if user_dev.blacklist:
            return None
            
        return {
            'ath': user_dev.ath,
            'total_tokens': user_dev.total_tokens,
            'whitelist': user_dev.whitelist,
            'blacklist': user_dev.blacklist
        }
    except:
        return{
            'ath': 0,
            'total_tokens': 1,
            'whitelist': False,
            'blacklist': False,
        }



async def process_token_data(data):
    """Обрабатывает данные токена и отправляет в расширение"""
    try:
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        print(symbol)
        user_dev_data = await get_user_dev_data(user)
        
        if user_dev_data is None:
            return
        
        sol_balance = await get_sol_balance_async(user)
        if sol_balance is None:
            sol_balance = 'N/A'
        else:
            sol_balance = f"{sol_balance:.4f}"
        
        extension_data = {
            'mint': mint,
            'user': user,
            'name': name,
            'symbol': symbol,
            'total_tokens': user_dev_data['total_tokens'],
            'ath': user_dev_data['ath'],
            'sol_balance': sol_balance,
            'source': source,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_whitelisted': user_dev_data['whitelist'],
            'user_blacklisted': user_dev_data['blacklist']
        }
        
        await broadcast_to_extension(extension_data)
        
        # Единственный вывод с оформленными данными
        print(f"📤 EXTENSION → {extension_data['source'].upper()} | {extension_data['name']} ({extension_data['symbol']}) | ATH: {extension_data['ath']} | Total Tokens: {extension_data['total_tokens']} | SOL Balance: {extension_data['sol_balance']} | User: {extension_data['user'][:8]}...")
        
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
