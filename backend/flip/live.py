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

from mainapp.models import UserDev, Token, Twitter, Settings
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
    except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
        # Нормальные закрытия соединения
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
        except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
            disconnected_clients.add(client)
        except Exception:
            disconnected_clients.add(client)
    
    extension_clients.difference_update(disconnected_clients)

async def get_user_dev_data(user_address,mint):
    """Получает данные UserDev из базы данных"""
    try:
        user_dev = await sync_to_async(UserDev.objects.get)(adress=user_address)
                
        # Получаем последние 5 токенов с ATH > 0 и НЕ мигрированных
        recent_dev_tokens = await sync_to_async(list)(
            Token.objects.filter(
                dev=user_dev,
                processed = True
            ).exclude(
                address=mint  # Исключаем текущий токен
            ).order_by('-created_at')[:3]
        )
        
        # Рассчитываем средний ATH
        if recent_dev_tokens:
            avg_ath = sum(token.ath for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_ath = 0
        # Рассчитываем средний total_trans по тем же последним токенам
        if recent_dev_tokens:
            avg_total_trans = sum(token.total_trans for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_total_trans = 0
        
        migration_percentage = 0

        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:4] + '...' + token.address[-4:],  
                'ath': token.ath,
                'total_trans': token.total_trans
            })
            
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_trans': int(avg_total_trans),  # Средний total_trans последних 5 токенов
            'total_tokens': max(1, user_dev.total_tokens),
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

async def get_twitter_data(name,mint):
    """Получает данные UserDev из базы данных"""
    try:
        user_dev = await sync_to_async(Twitter.objects.get)(name=name)
                
        # Получаем последние 5 токенов с ATH > 0 и НЕ мигрированных
        recent_dev_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                processed = True
            ).exclude(
                address=mint  # Исключаем текущий токен
            ).order_by('-created_at')[:3]
        )
        
        # Рассчитываем средний ATH
        if recent_dev_tokens:
            avg_ath = sum(token.ath for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_ath = 0
        # Рассчитываем средний total_trans по тем же последним токенам
        if recent_dev_tokens:
            avg_total_trans = sum(token.total_trans for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_total_trans = 0
        
        migration_percentage = 0

        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:4] + '...' + token.address[-4:],  
                'ath': token.ath,
                'total_trans': token.total_trans
            })
        user_dev.ath = int(avg_ath)  
        user_dev.total_tokens = int(avg_total_trans)
        sync_to_async(user_dev.save)()
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_trans': int(avg_total_trans),  # Средний total_trans последних 5 токенов
            'total_tokens': max(1, user_dev.total_tokens),
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


async def check_twitter_whitelist(twitter_name,creator):
    try:
        settings_obj = await sync_to_async(Settings.objects.first)()
        if not(settings_obj.start):
            return False
        try:
            twitter_obj = await sync_to_async(Twitter.objects.get)(
                        name=f"@{twitter_name}",
                    )
        except:
            print("Твитера нет в бд")
            return False
        if(settings_obj.whitelist_enabled and twitter_obj.whitelist):
            return True
        if(settings_obj.one_token_enabled):
            try:
                await sync_to_async(UserDev.objects.get)(adress=creator,total_tokens__gt=1)
                print("Больше 1 токена")
                return False
            except Exception as e:
                print(e)
                pass
        if(twitter_obj.ath<settings_obj.ath_from and twitter_obj.total_trans < settings_obj.total_trans_from):
            print("АТХ или тотал транс не подходят:",twitter_obj.total_trans,twitter_obj.ath)
            return False
            
        try:
            last_tokens = await sync_to_async(lambda: list(
                Token.objects.filter(twitter=twitter_obj, processed=True)
                .order_by('-created_at')[:3]
            ))()
        except Exception as e:
            print("Нет токенов у Твитера")
            return False

        if len(last_tokens) < 3:
            print("Меньше 3 токенов")
            return False

        for token in last_tokens:
            if token.total_trans < settings_obj.median:
                print("Один из токенов не подходит по тотал транс",token.address)
                return False

        return True
    except Exception as e:
        print(e)
        print("Ошибка")
        return False




async def process_live(data):
    try:
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        twitter = data.get('twitter_name','')
        twitter_followers = data.get('twitter_followers','')
        if not(twitter) or twitter == "@":
            return

        results = await asyncio.gather(
            check_twitter_whitelist(twitter, user),
            get_user_dev_data(user, mint),
            get_twitter_data(twitter, mint),
        )

        autobuy, user_dev_data, twitter_data = results
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
            'user_total_trans': user_dev_data.get('total_trans', 0),
            'user_migrations': user_dev_data['migrations'],
            'user_recent_tokens': user_dev_data['recent_tokens'],
            'user_whitelisted': user_dev_data['whitelist'],
            'user_blacklisted': user_dev_data['blacklist'],
            'twitter_total_tokens': twitter_data['total_tokens'],
            'twitter_ath': twitter_data['ath'],
            'twitter_total_trans': twitter_data.get('total_trans', 0),
            'twitter_migrations': twitter_data['migrations'],
            'twitter_recent_tokens': twitter_data['recent_tokens'],
            'twitter_whitelisted': twitter_data['whitelist'],
            'twitter_blacklisted': twitter_data['blacklist'],
            'autobuy': autobuy
        }
        
        await broadcast_to_extension(extension_data)
        with open('extension_data.json', 'w') as f:
            json.dump(extension_data, f)
        # Единственный вывод с оформленными данными
        recent_tokens_str = " | ".join([f"{token['name']}: {token['ath']}" for token in user_dev_data['recent_tokens']])
        print(f"📤 EXTENSION → {extension_data['source'].upper()} | {extension_data['user_name']} ({extension_data['symbol']}) | User ATH: {extension_data['user_ath']} | User Tokens: {extension_data['user_total_tokens']} | User Migrations: {extension_data['user_migrations']}% | Recent: {recent_tokens_str} | User: {extension_data['user'][:8]}...")
        
    except Exception as e:
        pass


async def start_extension_server():
    """Запускает веб-сокет сервер для расширения"""
    async with websockets.serve(
        handler,
        "0.0.0.0",
        8765,
        ping_interval=20,
        ping_timeout=30,
        close_timeout=5,
        max_size=None,
    ):
        await asyncio.Future()


