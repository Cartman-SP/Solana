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

def make_api_request(url, headers, max_retries=3):
    """Выполняет API запрос с обработкой ошибок и перезапусками"""
    global api_request_count
    
    for attempt in range(max_retries):
        try:
            check_api_limit()
            
            response = requests.get(url, headers=headers, timeout=30)
            api_request_count += 1
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:  # Rate limit exceeded
                print(f"Rate limit exceeded. Попытка {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 5)  # Exponential backoff
                    time.sleep(wait_time)
                    continue
            else:
                print(f"API ошибка {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"Ошибка запроса (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))
                continue
        except Exception as e:
            print(f"Неожиданная ошибка (попытка {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))
                continue
    
    print(f"Не удалось выполнить API запрос после {max_retries} попыток")
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
        data = await make_api_request(url, headers)
        data = data.get('data', [])
        return data
    except Exception as e:
        print(f"Error: {e}")
        return []

async def check_birzh(address, tags):
    if "exchange_wallet" in tags:
        return True
    
    base_url = "https://pro-api.solscan.io/v2.0/account/"
    url = f"{base_url}transfer?address={address}&activity_type[]=ACTIVITY_SPL_TRANSFER&page=1&page_size=100&sort_by=block_time&sort_order=desc"    
    headers = {"token": API_KEY}
    
    response = make_api_request(url, headers)
    if response is None:
        return False
    
    data = response.get('data', [])
    if not data:
        return False
    
    try:
        ago = minutes_since(data[10]['time'])
    except:
        ago = minutes_since(data[-1]['time'])

    if ago < 6 and len(data) == 100:
        return True

    url = f"{base_url}portfolio?address={address}&exclude_low_score_tokens=true"    
    response = make_api_request(url, headers)
    if response is None:
        return False
    
    data = response.get('data', [])
    try:
        balance = data.get('native_balance', {}).get('balance', 0)
    except:
        balance = 0
    
    if balance > 300:
        return True
    return False




async def check_admin(fund):
    data = None
    while True:
        data = await get_funding_addresses(fund)
        fund = data.get('funded_by', []).get('funded_by', [])
        tags = []
        try:
            tags = data.get('account_tags')
        except:
            pass
        if await check_birzh(fund, tags):
            return None
        try:
            user = await sync_to_async(UserDev.objects.get, thread_sensitive=True)(adress=fund)
            return user
        except UserDev.DoesNotExist:
            pass
        except Exception:
            pass


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
        if user_bd is None:
            return
        elif user_bd.admin.blacklist is False:
            return
        user_dev_data = await get_admin_data(user_bd.admin)
        if user_dev_data is None:
            return
        

        extension_data = {
            'mint': mint,
            'user': user,
            'name': name,
            'symbol': symbol,
            'total_tokens': user_dev_data['total_tokens'],
            'ath': user_dev_data['ath'],
            'migrations': user_dev_data['migrations'],
            'recent_tokens': user_dev_data['recent_tokens'],
            'source': source,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_whitelisted':user_bd.admin.whitelist,
            'user_blacklisted': user_bd.admin.blacklist,
            'admin': user_bd.admin.twitter
        }
        
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
    async with websockets.serve(handler, "0.0.0.0", 8766):
        await asyncio.Future()

async def main():
    """Основная функция - запускает оба сервиса"""
    extension_server_task = asyncio.create_task(start_extension_server())
    websocket_listener_task = asyncio.create_task(listen_to_websocket())
    await asyncio.gather(extension_server_task, websocket_listener_task)

if __name__ == "__main__":
    asyncio.run(main()) 
