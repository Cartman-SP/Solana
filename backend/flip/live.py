import asyncio
import websockets
import json
import aiohttp
from datetime import datetime
import json
import os
import sys
import django
import asyncio
import re
import base64
import websockets
import aiohttp
import requests
from typing import Optional, List, Dict, Tuple
import base58
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.commitment_config import CommitmentLevel
import base58
import time
import uvloop
import contextlib
from base58 import b58encode, b58decode
from live import *
from create import *
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from datetime import datetime, timezone, timedelta

from mainapp.models import UserDev, Token, Twitter, Settings
from asgiref.sync import sync_to_async

# Конфигурация
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
HELIUS_HTTP = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMPPORTAL_TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"
TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}
COMMUNITY_ID_RE = re.compile(r"/communities/(\d+)", re.IGNORECASE)
PROGDATA_RE = re.compile(r"Program data:\s*([A-Za-z0-9+/=]+)")
INSTRUCTION_MINT_RE = re.compile(r"Program log: Instruction: (InitializeMint2|InitializeMint)", re.IGNORECASE)



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

async def get_user_dev_data(name,mint):
    """Получает данные UserDev из базы данных"""
    try:
        user_dev = await sync_to_async(UserDev.objects.get)(adress=name)
                
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
        
        # Рассчитываем средний total_fees по тем же последним токенам
        if recent_dev_tokens:
            avg_total_fees = sum(token.total_fees for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_total_fees = 0
        
        migration_percentage = 0

        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:4] + '...' + token.address[-4:],  
                'ath': token.ath,
                'total_trans': token.total_trans,
                'total_fees': round(token.total_fees, 6)  # Оставляем как float с 6 знаками после запятой
            })
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_trans': int(avg_total_trans),  # Средний total_trans последних 5 токенов
            'total_fees': avg_total_fees,  # Средний total_fees последних 5 токенов (float)
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
        
        # Рассчитываем средний total_fees по тем же последним токенам
        if recent_dev_tokens:
            avg_total_fees = sum(token.total_fees for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_total_fees = 0
        
        migration_percentage = 0

        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:4] + '...' + token.address[-4:],  
                'ath': token.ath,
                'total_trans': token.total_trans,
                'total_fees': round(token.total_fees, 6)  # Оставляем как float с 6 знаками после запятой
            })
        await sync_to_async(lambda: setattr(user_dev, 'ath', int(avg_ath)))()
        await sync_to_async(lambda: setattr(user_dev, 'total_trans', int(avg_total_trans)))()
        await sync_to_async(lambda: setattr(user_dev, 'total_fees', avg_total_fees))()

        await sync_to_async(user_dev.save)()
        return {
            'ath': int(avg_ath),  # Средний ATH последних 5 токенов
            'total_trans': int(avg_total_trans),  # Средний total_trans последних 5 токенов
            'total_fees': avg_total_fees,  # Средний total_fees последних 5 токенов (float)
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


async def send_telegram_message(token_address, dev_address, twitter_name, user_ath, user_total_trans, user_total_fees):
    """Отправляет сообщение в Telegram чаты при autobuy = True"""
    bot_token = "8361879327:AAHFHe2qm0dEQpsvfyZSB_vCJYukmEWJ_tc"
    chat_ids = ["612594627", "784111198"]
    
    # Формируем красивое сообщение
    message = f"""
🚀 **НОВЫЙ ТОКЕН ДЛЯ ПОКУПКИ!** 🚀

📍 **Адрес токена:** `{token_address}`
👨‍💻 **Адрес разработчика:** `{dev_address}`
🐦 **Twitter:** {twitter_name}

📊 **Метрики разработчика:**
• ATH: **{user_ath:,}** SOL
• Всего транзакций: **{user_total_trans:,}**
• Общие комиссии: **{user_total_fees:.6f}** SOL

⏰ **Время:** {datetime.now().strftime('%H:%M:%S')}
"""
    
    # Отправляем сообщение в каждый чат
    async with aiohttp.ClientSession() as session:
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        print(f"✅ Сообщение отправлено в чат {chat_id}")
                    else:
                        print(f"❌ Ошибка отправки в чат {chat_id}: {response.status}")
                        
            except Exception as e:
                print(f"❌ Ошибка при отправке в Telegram: {e}")



async def check_twitter_whitelist(twitter_name, creator,mint,community_id):

    try:
        # Получаем настройки и объекты одним запросом
        settings_obj, twitter_obj = await asyncio.gather(
            sync_to_async(Settings.objects.first)(),
            sync_to_async(Twitter.objects.get)(name=twitter_name),
        )
        
        if not settings_obj.start:
            return False
        total_tokens = 0
        try:
            dev = await sync_to_async(UserDev.objects.get)(adress=creator)
            total_tokens = await sync_to_async(
                lambda: Token.objects.filter(dev=dev).exclude(address=mint).count()
            )()
        except:
            pass

        if total_tokens > settings_obj.dev_tokens:
            return False
        if twitter_obj.blacklist:
            return False
        if settings_obj.whitelist_enabled and twitter_obj.whitelist:
            return True
        same_tokens = 0    
        try:
            same_tokens = Token.objects.filter(community_id = community_id).exclude(address=mint).count()
        except Exception as e:
            same_tokens = 0
        
        if(same_tokens>0):
            return False



        print(twitter_name)
        recent_tokens = await sync_to_async(
            lambda: list(
                Token.objects.filter(
                    twitter=twitter_obj,
                    processed=True
                ).exclude(address=mint)
                .order_by('-created_at')
                .only('ath', 'total_trans', 'total_fees', 'created_at','migrated')[:3]
            )
        )()
        
        # Проверяем, есть ли хотя бы один токен с migrated = True
        if recent_tokens and not any(token.migrated for token in recent_tokens):
            print(f"Нет токенов с migrated = True для {twitter_name}")
            return False



        # Проверяем возраст самого свежего токена
        if recent_tokens:
            newest_token = recent_tokens[0]  # Первый токен в списке (самый свежий)
            time_diff = timezone.now() - newest_token.created_at
            
            if time_diff < timedelta(minutes=30):
                print(f"Токен слишком старый: {newest_token.created_at}, {time_diff}")
                return False
        
        # Рассчитываем средние значения
        if recent_tokens:
            avg_ath = sum(token.ath for token in recent_tokens) / len(recent_tokens)
            avg_total_trans = sum(token.total_trans for token in recent_tokens) / len(recent_tokens)
            avg_total_fees = sum(token.total_fees for token in recent_tokens) / len(recent_tokens)
            check_median = all(token.total_trans >= settings_obj.median for token in recent_tokens)
        else:
            avg_ath = avg_total_trans = avg_total_fees = 0
            check_median = False
        
        # Проверяем все условия
        if not check_median:
            return False
        
        
        if avg_ath < settings_obj.ath_from:
            print(f"ATH не подходят: {avg_ath} < {settings_obj.ath_from}")
            return False
        
        if avg_total_trans < settings_obj.total_trans_from:
            print(f"Тотал транс не подходят: {avg_total_trans} < {settings_obj.total_trans_from}")
            return False
        
        if avg_total_fees < settings_obj.total_fees_from:
            print(f"Тотал фис не подходят: {avg_total_fees} < {settings_obj.total_fees_from}")
            return False
        
        print(f"\nАТХ: {avg_ath} > {settings_obj.ath_from}\n"
              f"Total Trans: {avg_total_trans} > {settings_obj.total_trans_from}\n"
              f"Total Fees: {avg_total_fees} > {settings_obj.total_fees_from}\n"
              f"Всего токенов: {total_tokens}")
                
        return True
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return False


async def _tw_get(session, path, params):
    """Быстрый запрос к Twitter API"""
    to = aiohttp.ClientTimeout(total=0.8)  # Уменьшаем timeout для скорости
    async with session.get(f"{TW_BASE}{path}", headers=TW_HEADERS, params=params, timeout=to) as r:
        r.raise_for_status()
        return await r.json()

def _extract_username_followers(user_obj: dict) -> tuple[str|None, int|None]:
    """Извлекает username и followers из объекта пользователя"""
    if not isinstance(user_obj, dict):
        return None, None
    username = user_obj.get("screen_name") or user_obj.get("userName") or user_obj.get("username")
    followers = (
        user_obj.get("followers_count")
        or user_obj.get("followers")
        or ((user_obj.get("public_metrics") or {}).get("followers_count"))
    )
    try:
        followers = int(followers) if followers is not None else None
    except Exception:
        followers = None
    return (username, followers) if username else (None, None)

async def _get_creator_from_info(session: aiohttp.ClientSession, community_id: str):
    """Получает создателя community из info API"""
    try:
        j = await _tw_get(session, "/twitter/community/info", {"community_id": community_id})
        ci = (j or {}).get("community_info", {}) or {}
        u, f = _extract_username_followers(ci.get("creator") or {})
        if u:
            return u, f, "creator"
        u, f = _extract_username_followers(ci.get("first_member") or {})
        if u:
            return u, f, "member"
    except:
        pass
    return None, None, None

async def _get_first_member_via_members(session: aiohttp.ClientSession, community_id: str):
    """Получает первого участника community из members API"""
    try:
        j = await _tw_get(session, "/twitter/community/members", {"community_id": community_id, "limit": 1})
        candidates = []
        for key in ("members", "data", "users"):
            arr = j.get(key)
            if isinstance(arr, list):
                candidates.extend(arr)
        if not candidates:
            data = j.get("data")
            if isinstance(data, dict) and isinstance(data.get("users"), list):
                candidates.extend(data["users"])
        if candidates:
            u, f = _extract_username_followers(candidates[0] or {})
            if u:
                return u, f, "member"
    except:
        pass
    return None, None, None


async def get_creator_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Получает username с несколькими попытками и fallback методами"""
    
    # Пробуем оба метода параллельно для максимальной скорости
    try:
        # Создаем задачи для параллельного выполнения
        task1 = asyncio.create_task(_get_creator_from_info(session, community_id))
        task2 = asyncio.create_task(_get_first_member_via_members(session, community_id))
        
        # Ждем первый успешный результат
        done, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED)
        
        # Отменяем оставшиеся задачи
        for task in pending:
            task.cancel()
        
        # Проверяем результаты
        for task in done:
            try:
                u, f, src = task.result()
                if u:
                    return u, f
            except:
                continue
                
    except:
        pass
    
    return None



def find_community_from_uri(uri: str) -> Optional[str]:
    """Ищет community ID в URI"""
    if not uri:
        return None
    print(uri)
    match = COMMUNITY_ID_RE.search(uri)
    return match.group(1) if match else None

async def fetch_meta_with_retries(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Загружает метаданные с URI"""
    if not uri:
        return None
        
    try:
        # Пробуем только один раз с коротким таймаутом
        async with session.get(uri, timeout=aiohttp.ClientTimeout(total=0.5)) as r:
            data = await r.json()
            return data
    except Exception:
        return None

def find_community_anywhere_with_src(meta_json: dict) -> tuple[str|None, str|None, str|None]:
    """Ищет community ID в метаданных"""
    # Проверяем основные поля
    for field in ['twitter', 'x', 'external_url', 'website']:
        if field in meta_json:
            url, cid = canonicalize_community_url(meta_json[field])
            if cid:
                return url, cid, field
    
    # Проверяем extensions если есть
    if 'extensions' in meta_json:
        for field in ['twitter', 'x', 'website']:
            if field in meta_json['extensions']:
                url, cid = canonicalize_community_url(meta_json['extensions'][field])
                if cid:
                    return url, cid, f"extensions.{field}"
    
    return None, None, None

def canonicalize_community_url(url_or_id: str) -> tuple[str|None, str|None]:
    """Нормализует URL community и извлекает ID"""
    if not url_or_id:
        return None, None
        
    # Если это просто цифры - считаем это ID
    if url_or_id.isdigit():
        return f"https://x.com/i/communities/{url_or_id}", url_or_id
        
    # Ищем ID в URL
    match = COMMUNITY_ID_RE.search(url_or_id)
    if match:
        return f"https://x.com/i/communities/{match.group(1)}", match.group(1)
        
    return None, None



async def get_twitter_data_manualy(session,uri):
    community_id = None
    meta = await fetch_meta_with_retries(session, uri)
    if meta:
        community_url, community_id, _ = find_community_anywhere_with_src(meta)
        

    twitter_name = ""
    if community_id:
        twitter_name, followers = await get_creator_username(session, community_id)

    if twitter_name:
        twitter_name=f"@{twitter_name}"
    return twitter_name, followers, community_id



async def process_live(data,session):
    try:
        source = data.get('source', '')
        mint = data.get('mint', '')
        user = data.get('user', '')
        name = data.get('name', '')
        symbol = data.get('symbol', '')
        uri = data.get('uri', '')
        twitter,twitter_followers,community_id = await get_twitter_data_manualy(session,uri)

        print('\n-------------------------------------------------\n',twitter,'\n-------------------------------------------------\n')
        if not(twitter) or twitter == "@" or twitter=="@None":
            return

        results = await asyncio.gather(
            check_twitter_whitelist(twitter, user,mint,community_id),
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
            'user_total_fees': user_dev_data.get('total_fees', 0),
            'user_migrations': user_dev_data['migrations'],
            'user_recent_tokens': user_dev_data['recent_tokens'],
            'user_whitelisted': user_dev_data['whitelist'],
            'user_blacklisted': user_dev_data['blacklist'],
            'twitter_total_tokens': twitter_data['total_tokens'],
            'twitter_ath': twitter_data['ath'],
            'twitter_total_trans': twitter_data.get('total_trans', 0),
            'twitter_total_fees': twitter_data.get('total_fees', 0),
            'twitter_migrations': twitter_data['migrations'],
            'twitter_recent_tokens': twitter_data['recent_tokens'],
            'twitter_whitelisted': twitter_data['whitelist'],
            'twitter_blacklisted': twitter_data['blacklist'],
            'autobuy': autobuy
        }
        
        # Отправляем сообщение в Telegram если autobuy = True
        if autobuy:
            await send_telegram_message(
                token_address=mint,
                dev_address=user,
                twitter_name=twitter,
                user_ath=twitter_data['ath'],
                user_total_trans=twitter_data.get('total_trans', 0),
                user_total_fees=twitter_data.get('total_fees', 0)
            )
        
        await broadcast_to_extension(extension_data)
        with open('extension_data.json', 'w') as f:
            json.dump(extension_data, f)
        # Единственный вывод с оформленными данными
        recent_tokens_str = " | ".join([f"{token['name']}: {token['ath']}" for token in user_dev_data['recent_tokens']])
        recent_tokens_fees_str = " | ".join([f"{token['name']}: {token['total_fees']:.6f}" for token in user_dev_data['recent_tokens']])
        #print(f"📤 EXTENSION → {extension_data['source'].upper()} | {extension_data['user_name']} ({extension_data['symbol']}) | User ATH: {extension_data['user_ath']} | User Tokens: {extension_data['user_total_tokens']} | User Total Fees: {extension_data['user_total_fees']:.6f} | User Migrations: {extension_data['user_migrations']}% | Recent: {recent_tokens_str} | Recent Fees: {recent_tokens_fees_str} | User: {extension_data['user'][:8]}...")
        
    except Exception as e:
        print(e)
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


