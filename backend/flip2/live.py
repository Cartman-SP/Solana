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
        # Рассчитываем средний total_trans по тем же последним токенам
        if recent_tokens:
            avg_total_trans = sum(token.total_trans for token in recent_tokens) / len(recent_tokens)
        else:
            avg_total_trans = 0
        
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
                'ath': token.ath,
                'total_trans': token.total_trans
            })
            
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_trans': int(avg_total_trans),  # Средний total_trans последних 5 токенов
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
        # Проверяем, существует ли Twitter аккаунт
        user_dev = await sync_to_async(Twitter.objects.get)(name=twitter)
        
        if user_dev.blacklist:
            return None
        
        # Получаем последние 5 токенов с ATH > 0 и НЕ мигрированных
        recent_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                ath__gt=0,
                processed=True
            ).order_by('-created_at')[:3]
        )
        
        # Рассчитываем средний ATH
        avg_ath = sum(token.ath for token in recent_tokens) / len(recent_tokens) if recent_tokens else 0
        # Рассчитываем средний total_trans по тем же последним токенам
        avg_total_trans = sum(token.total_trans for token in recent_tokens) / len(recent_tokens) if recent_tokens else 0
        
        # Получаем последние 100 токенов для расчета процента миграций
        recent_100_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                processed=True
            ).order_by('-created_at')[:100]
        )
        
        # Рассчитываем процент мигрированных токенов
        migration_percentage = (sum(1 for token in recent_100_tokens if token.migrated) / len(recent_100_tokens) * 100) if recent_100_tokens else 0
        
        # Получаем последние 3 токена разработчика
        recent_dev_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=user_dev,
                processed=True
            ).order_by('-created_at')[:3]
        )
        
        # Формируем список последних токенов
        recent_tokens_info = [{
            'name': token.address[:8] + '...',
            'ath': token.ath,
            'total_trans': token.total_trans
        } for token in recent_dev_tokens]
        
        # Обновляем и сохраняем данные Twitter
        old_ath = user_dev.ath
        user_dev.ath = int(avg_ath)
        # Сохраняем средний total_trans у Twitter для фильтрации
        user_dev.total_trans = int(avg_total_trans)
        user_dev.total_tokens = await sync_to_async(Token.objects.filter(twitter=user_dev, processed=True).count)()
        try:
            await sync_to_async(user_dev.save)()
            print(f"DEBUG: Успешно сохранен Twitter {twitter} с ATH {user_dev.ath}")
        except Exception as e:
            print(f"ERROR: Не удалось сохранить Twitter {twitter}: {str(e)}")
                
        return {
            'ath': int(avg_ath),
            'total_trans': int(avg_total_trans),
            'total_tokens': user_dev.total_tokens,
            'whitelist': user_dev.whitelist,
            'blacklist': user_dev.blacklist,
            'migrations': round(migration_percentage, 1),
            'recent_tokens': recent_tokens_info,
        }
    except Twitter.DoesNotExist:
        print(f"DEBUG: Twitter аккаунт {twitter} не найден в базе данных")
        # Создаем новый Twitter аккаунт, если он не существует
        try:
            user_dev = Twitter(name=twitter)
            await sync_to_async(user_dev.save)()
            print(f"DEBUG: Создан новый Twitter аккаунт {twitter}")
            return {
                'ath': 0,
                'total_tokens': 0,
                'whitelist': False,
                'blacklist': False,
                'migrations': 0,
                'recent_tokens': [],
            }
        except Exception as e:
            print(f"ERROR: Не удалось создать Twitter аккаунт {twitter}: {str(e)}")
            return None
    except Exception as e:
        print(f"ERROR: Ошибка при обработке Twitter {twitter}: {str(e)}")
        return None

async def check_twitter_whitelist(twitter_name,creator):
    try:
        settings_obj = await sync_to_async(Settings.objects.first)()
        if not(settings_obj.start):
            return False
        if(settings_obj.one_token_enabled):
            try:
                await sync_to_async(UserDev.objects.get)(adress=creator,total_tokens__gt=1)
                return False
            except:
                pass

        twitter_obj = None
        if(settings_obj.whitelist_enabled):
            try:
                twitter_obj = await sync_to_async(Twitter.objects.get)(
                    name=twitter_name",
                    whitelist=True,
                    ath__gte=settings_obj.ath_from,
                    total_trans__gte=settings_obj.total_trans_from
                )
            except:
                return False
        else:
            try:
                twitter_obj = await sync_to_async(Twitter.objects.get)(
                    name=twitter_name,
                    ath__gte=settings_obj.ath_from,
                    total_trans__gte=settings_obj.total_trans_from
                )
            except:
                return False

        # Проверяем последние 3 обработанных токена для найденного твиттера
        try:
            last_tokens = await sync_to_async(lambda: list(
                Token.objects.filter(twitter=twitter_obj, processed=True)
                .order_by('-created_at')[:3]
            ))()
        except Exception:
            return False

        if len(last_tokens) < 3:
            return False

        for token in last_tokens:
            if token.total_trans < 75:
                return False

        return True
    except Exception as e:
        print(e)
        return False



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
        print(symbol)
        if twitter == '':
            return
        autobuy = await check_twitter_whitelist(twitter,user)
        user_dev_data = await get_user_dev_data(user)
        twitter_data = await get_twitter_data(twitter) or {
            'ath': 0,
            'total_tokens': 0,
            'whitelist': False,
            'blacklist': False,
            'migrations': 0,
            'recent_tokens': [],
        }
        print(f"DEBUG: Получены данные Twitter: {twitter_data}")
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

async def listen_to_websocket():
    """Слушает основной веб-сокет и обрабатывает данные"""
    while True:
        try:
            async with websockets.connect(
                "ws://localhost:9393",
                ping_interval=20,
                ping_timeout=30,
                close_timeout=5,
                open_timeout=3,
                max_size=None,
            ) as websocket:
                try:
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await process_token_data(data)
                        except Exception:
                            pass
                except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
                    # Тихий выход — переподключимся в следующей итерации
                    pass
        except Exception:
            await asyncio.sleep(1)

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

async def main():
    """Основная функция - запускает оба сервиса"""
    extension_server_task = asyncio.create_task(start_extension_server())
    websocket_listener_task = asyncio.create_task(listen_to_websocket())
    await asyncio.gather(extension_server_task, websocket_listener_task)

if __name__ == "__main__":
    asyncio.run(main()) 
