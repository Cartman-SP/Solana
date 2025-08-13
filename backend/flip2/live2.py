import asyncio
import websockets
import json
import os
import sys
import django
import random
from datetime import datetime
import requests
import time
# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token
from django.db.models import Sum
from asgiref.sync import sync_to_async
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"


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

def make_api_request(url, headers, max_retries=10):
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit exceeded
                print(f"Rate limit exceeded. Попытка {attempt + 1}/{max_retries}")
                time.sleep(10)
                continue
            else:
                print(f"API ошибка {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            time.sleep(random.uniform(1, 3))
            continue
        except Exception as e:
            time.sleep(random.uniform(1, 3))
            continue
    
    return None



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


async def get_funding_addresses(wallet_address):
    base_url = "https://pro-api.solscan.io/v2.0/account/metadata"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    # Формируем URL для входящих трансферов (flow=in), чтобы получить только фондирующие адреса
    url = f"{base_url}?address={wallet_address}"
    
    try:
        data = await asyncio.to_thread(make_api_request, url, headers)
        if not data:
            return {}
        data = data.get('data', {})
        return data
    except Exception as e:
        print(f"Error: {e}")
        return {}

async def check_admin(fund):
    data = None
    try:
        user = await sync_to_async(UserDev.objects.get, thread_sensitive=True)(adress=fund)
    except:
        return None
    count = 0
    limit = 10
    while count < limit:
        data = await get_funding_addresses(fund)
        fund = data.get('funded_by', {}).get('funded_by', '')
        tags = []
        try:
            tags = data.get('account_tags')
        except:
            pass
        try:
            user = await sync_to_async(UserDev.objects.get, thread_sensitive=True)(adress=fund)
            return user
        except UserDev.DoesNotExist:
            pass
        except Exception:
            pass
        count+=1


async def get_admin_data(admin):
    try:
        # Получаем подходящих девов (последние по id) с total_tokens > 1
        devs = await sync_to_async(
            lambda: list(UserDev.objects.filter(admin=admin, total_tokens__gt=1).order_by('-id')),
            thread_sensitive=True,
        )()

        collected = []
        for dev in devs:
            if len(collected) >= 3:
                break
            remaining = 3 - len(collected)
            tokens = await sync_to_async(
                lambda: list(
                    Token.objects.filter(dev=dev, processed=True)
                    .order_by('-created_at')[:remaining]
                ),
                thread_sensitive=True,
            )()
            for t in tokens:
                collected.append({
                    'name': t.address,  # используем address как name-плейсхолдер
                    'ath': t.ath,
                    'migrated': t.migrated,
                })

        if not collected:
            return None

        ath_sum = sum(item['ath'] for item in collected)
        avg_ath = int(ath_sum / len(collected))
        migrations_count = sum(1 for item in collected if item.get('migrated'))
        migrations_pct = int((migrations_count / len(collected)) * 100)

        # Сумма total_tokens по всем девам админа
        total_tokens_sum = await sync_to_async(
            lambda: (UserDev.objects.filter(admin=admin)
                     .aggregate(total=Sum('total_tokens'))['total'] or 0),
            thread_sensitive=True,
        )()

        return {
            'ath': avg_ath,
            'total_tokens': total_tokens_sum,
            'migrations': migrations_pct,
            'recent_tokens': [{'name': item['name'], 'ath': item['ath']} for item in collected],
        }
    except Exception:
        return None




async def process_token_data(data):
    """Обрабатывает данные токена и отправляет в расширение"""
    try:
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        
        user_bd = await check_admin(user)
        print("user_bd:",user_bd)
        if user_bd is None:
            return 
        print(123)

        extension_data = {
            'mint': mint,
            'user': user,
            'name': name,
            'symbol': symbol,
            'total_tokens': 0,
            'ath': 0,
            'migrations': 0,
            'recent_tokens': 0,
            'source': source,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_whitelisted':user_bd.whitelist,
            'user_blacklisted': user_bd.blacklist,
        }
        print(extension_data)
        await broadcast_to_extension(extension_data)
        
        
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
