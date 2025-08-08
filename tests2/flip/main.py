import asyncio
import websockets
import json
from datetime import datetime
from get_balance import get_sol_balance_async
import django
import requests
import os
import sys
from author_tokens import get_all_tokens_by_address_async
from asgiref.sync import sync_to_async
# Добавляем путь к родительской директории для корректного импорта Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from mainapp.models import Token, UserDev, AdminDev

# Список всех подключенных клиентов
connected_clients = set()

async def broadcast_message(message):
    """Отправка сообщения всем подключенным клиентам"""
    if connected_clients:
        await asyncio.gather(
            *[client.send(message) for client in connected_clients],
            return_exceptions=True
        )

async def handle_client(websocket, path):
    """Обработчик подключений клиентов"""
    connected_clients.add(websocket)
    print(f"Клиент подключен. Всего клиентов: {len(connected_clients)}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                print(f"Получено сообщение: {data}")
                
                # Проверяем, что это данные от bonk.py или других источников
                if 'mint' in data and 'user' in data:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # Вывод только Mint и User (dev)
                    mint = data.get('mint', 'N/A')
                    user = data.get('user', 'N/A')
                    source = data.get('source', 'N/A')
                    name = data.get('name', 'N/A')
                    symbol = data.get('symbol', 'N/A')
                    uri = data.get('uri', 'N/A')
                    sol_balance = await get_sol_balance_async(user)

                    # Получаем данные о UserDev из БД
                    try:
                        user_dev = await sync_to_async(UserDev.objects.get)(adress=user)
                        total_tokens = user_dev.total_tokens
                        ath = user_dev.ath
                        user_blacklisted = user_dev.blacklist
                        user_whitelisted = user_dev.whitelist
                        user_found = True
                    except UserDev.DoesNotExist:
                        total_tokens = "N/A"
                        ath = "N/A"
                        user_blacklisted = False
                        user_whitelisted = False
                        user_found = False

                    print("-"*60,"\n",f"[{timestamp}] {source} | Mint: {mint} | User: {user}")
                    print(f"Name: {name}")
                    print(f"Symbol: {symbol}")
                    print(f"Uri: {uri}")
                    print(f"Total author tokens: {total_tokens}")
                    print(f"Author ATH: {ath}")
                    print(f"AuthorSOL balance: {sol_balance}")
                    if not user_found:
                        print("UserDev не найден в БД")
                    print("-"*60)

                    # Отправляем данные через WebSocket
                    websocket_data = {
                        'timestamp': timestamp,
                        'mint': mint,
                        'user': user,
                        'source': source,
                        'name': name,
                        'symbol': symbol,
                        'uri': uri,
                        'total_tokens': total_tokens,
                        'ath': ath,
                        'sol_balance': sol_balance,
                        'user_blacklisted': user_blacklisted,
                        'user_whitelisted': user_whitelisted
                    }
                    
                    # Отправляем данные всем подключенным клиентам
                    message = json.dumps(websocket_data)
                    print(f"Отправляем сообщение всем клиентам: {message}")
                    await broadcast_message(message)
                else:
                    print(f"Неизвестный формат данных: {data}")
    
            except json.JSONDecodeError as e:
                print(f"Ошибка парсинга JSON: {e}")
                pass
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)
        print(f"Клиент отключен. Всего клиентов: {len(connected_clients)}")

async def main():
    """Основная функция запуска WebSocket сервера"""
    # Запуск WebSocket сервера
    async with websockets.serve(handle_client, "localhost", 8765):
        print("WebSocket сервер запущен на localhost:8765")
        await asyncio.Future()  # Бесконечное ожидание

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        pass
