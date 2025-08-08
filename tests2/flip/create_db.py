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


# Список подключенных клиентов
connected_clients = set()

@sync_to_async
def create_or_get_user_dev_sync(address, uri=None):
    """
    Синхронная версия создания или получения UserDev
    """
    try:
        user_dev, created = UserDev.objects.get_or_create(
            adress=address,
            defaults={
                'whitelist': False,
                'blacklist': False,
                'ath': 0,
                'uri': uri
            }
        )
        
        if created:
            print(f"Создан новый UserDev: {address}")
        else:
            print(f"Найден существующий UserDev: {address}")
            
        return user_dev
    except Exception as e:
        print(f"Ошибка при создании/получении UserDev: {e}")
        return None

async def create_or_get_user_dev(address, uri=None):
    """
    Асинхронная версия создания или получения UserDev
    """
    return await create_or_get_user_dev_sync(address, uri)

@sync_to_async
def create_token_sync(address, user_dev):
    """
    Синхронная версия создания токена
    """
    try:
        # Проверяем, существует ли уже токен с таким адресом
        existing_token = Token.objects.filter(address=address).first()
        if existing_token:
            print(f"Токен с адресом {address} уже существует")
            return existing_token
        
        # Создаем новый токен
        token = Token.objects.create(
            address=address,
            dev=user_dev,
            scam=False,
            ath=0
        )
        
        print(f"Создан новый токен: {address}")
        return token
    except Exception as e:
        print(f"Ошибка при создании токена: {e}")
        return None

async def create_token(address, user_dev):
    """
    Асинхронная версия создания токена
    """
    return await create_token_sync(address, user_dev)

async def process_token_data(data):
    """
    Обрабатывает данные токена и создает записи в БД
    """
    mint = data.get('mint', '')
    user = data.get('user', '')
    uri = data.get('uri', '')
    
    if not mint or not user:
        print("Отсутствуют обязательные поля mint или user")
        return None, None
    
    # Создаем или получаем UserDev
    user_dev = await create_or_get_user_dev(user, uri)
    if not user_dev:
        return None, None
    
    # Создаем токен
    token = await create_token(mint, user_dev)
    if not token:
        return None, None
    
    return user_dev, token

async def handle_client(websocket, path):
    """Обработчик подключений клиентов"""
    connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Вывод только Mint и User (dev)
                mint = data.get('mint', 'N/A')
                user = data.get('user', 'N/A')
                source = data.get('source', 'N/A')
                name = data.get('name', 'N/A')
                symbol = data.get('symbol', 'N/A')
                uri = data.get('uri', 'N/A')
                
                print("-"*60,"\n",f"[{timestamp}] {source} | Mint: {mint} | User: {user}")
                print(f"Name: {name}")
                print(f"Symbol: {symbol}")
                print(f"Uri: {uri}")
                
                # Получаем баланс SOL для пользователя
                try:
                    sol_balance = await get_sol_balance_async(user)
                except:
                    sol_balance = "N/A"
                
                print(f"AuthorSOL balance: {sol_balance}")
                
                # Обрабатываем данные и создаем записи в БД
                user_dev, token = await process_token_data(data)
                
                if user_dev and token:
                    print(f"✅ Успешно обработаны данные: UserDev={user_dev.adress}, Token={token.address}")
                else:
                    print("❌ Ошибка при обработке данных")
                
                print("-"*60)
    
            except json.JSONDecodeError:
                print("Ошибка декодирования JSON")
                pass
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)

async def main():
    """Основная функция запуска WebSocket сервера"""
    print("🚀 Запуск WebSocket сервера на localhost:9765")
    print("📊 Готов к обработке данных токенов и созданию записей в БД")
    
    # Запуск WebSocket сервера
    async with websockets.serve(handle_client, "localhost", 9765):
        await asyncio.Future()  # Бесконечное ожидание

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Сервер остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска сервера: {e}")
