import asyncio
import websockets
import json
import time
import os
import sys
import django
import re
import base64
import aiohttp
import requests
from typing import Optional, List, Dict, Tuple, Any
import base58
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.commitment_config import CommitmentLevel
import uvloop
import contextlib
from base58 import b58encode, b58decode
import ipfshttpclient
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

# Глобальные переменные для управления Twitter API
TWITTER_REQUEST_COUNT = 0
TWITTER_LAST_REQUEST_TIME = 0
TWITTER_RATE_LIMIT_DELAY = 0.1  # 100ms между запросами для избежания спама

async def _tw_get(session, path, params):
    """Управляемый запрос к Twitter API с контролем частоты"""
    global TWITTER_REQUEST_COUNT, TWITTER_LAST_REQUEST_TIME
    
    # Контроль частоты запросов
    current_time = time.time()
    time_since_last = current_time - TWITTER_LAST_REQUEST_TIME
    
    if time_since_last < TWITTER_RATE_LIMIT_DELAY:
        await asyncio.sleep(TWITTER_RATE_LIMIT_DELAY - time_since_last)
    
    try:
        to = aiohttp.ClientTimeout(total=2.0)  # Увеличиваем timeout для надежности
        async with session.get(f"{TW_BASE}{path}", headers=TW_HEADERS, params=params, timeout=to) as r:
            r.raise_for_status()
            TWITTER_REQUEST_COUNT += 1
            TWITTER_LAST_REQUEST_TIME = time.time()
            return await r.json()
    except Exception as e:
        print(f"Twitter API error: {e}")
        # При ошибке ждем дольше
        await asyncio.sleep(1)
        return None

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
    except Exception as e:
        print(e)
        followers = None
    return (username, followers) if username else (None, None)

async def _get_creator_from_info(session: aiohttp.ClientSession, community_id: str):
    """Получает создателя community из info API"""
    try:
        j = await _tw_get(session, "/twitter/community/info", {"community_id": community_id})
        if not j:
            return None, None, None
            
        ci = (j or {}).get("community_info", {}) or {}
        u, f = _extract_username_followers(ci.get("creator") or {})
        if u:
            return u, f, "creator"
        u, f = _extract_username_followers(ci.get("first_member") or {})
        if u:
            return u, f, "member"
    except Exception as e:
        print(f"Error in _get_creator_from_info: {e}")
        pass
    return None, None, None

async def _get_first_member_via_members(session: aiohttp.ClientSession, community_id: str):
    """Получает первого участника community из members API"""
    try:
        j = await _tw_get(session, "/twitter/community/members", {"community_id": community_id, "limit": 1})
        if not j:
            return None, None, None
            
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
    except Exception as e:
        print(f"Error in _get_first_member_via_members: {e}")
        pass
    return None, None, None

async def get_creator_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Получает username с максимальной вероятностью успеха"""
    
    max_attempts = 5  # Увеличиваем количество попыток
    
    for attempt in range(max_attempts):
        try:
            # Создаем задачи для параллельного выполнения
            task1 = asyncio.create_task(_get_creator_from_info(session, community_id))
            task2 = asyncio.create_task(_get_first_member_via_members(session, community_id))
            
            # Ждем первый успешный результат с увеличенным timeout
            done, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED, timeout=5.0)
            
            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
            
            # Проверяем результаты
            for task in done:
                try:
                    u, f, src = task.result()
                    if u:
                        print(f"Successfully got Twitter username: @{u} from {src}")
                        return u
                except Exception as e:
                    print(f"Task result error: {e}")
                    continue
            
            # Если u все еще None и это не последняя попытка, ждем и повторяем
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 2  # Увеличиваем время ожидания с каждой попыткой
                print(f"Attempt {attempt + 1} failed, waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                continue
                
        except Exception as e:
            # Если произошла ошибка и это не последняя попытка, ждем и повторяем
            if attempt < max_attempts - 1:
                wait_time = (attempt + 1) * 2
                print(f"Error in attempt {attempt + 1}, waiting {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
                continue
            else:
                print(f"Error in get_creator_username after {max_attempts} attempts: {e}")
    
    print(f"Failed to get Twitter username for community {community_id} after {max_attempts} attempts")
    return None

def find_community_from_uri(uri: str) -> Optional[str]:
    """Ищет community ID в URI"""
    if not uri:
        return None
    print(f"Searching for community ID in URI: {uri}")
    match = COMMUNITY_ID_RE.search(uri)
    result = match.group(1) if match else None
    if result:
        print(f"Found community ID: {result}")
    return result

class IPFSClient:
    def __init__(self):
        self.api_client = None
        self._setup_api_client()
    
    def _setup_api_client(self):
        """Настраиваем прямое подключение к API IPFS"""
        try:
            self.api_client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5101')
            print("✓ Подключение к IPFS API установлено")
        except Exception as e:
            print(f"✗ Ошибка подключения к IPFS API: {e}")
            self.api_client = None
    
    async def fetch_via_api(self, cid: str) -> Optional[Dict[Any, Any]]:
        """Прямое получение данных через IPFS API - самый надежный способ"""
        if not self.api_client:
            return None
            
        try:
            # Используем синхронный вызов в отдельном потоке
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, 
                lambda: self.api_client.cat(cid)
            )
            
            if data:
                try:
                    return json.loads(data.decode('utf-8'))
                except json.JSONDecodeError:
                    print(f"Данные не JSON: {data[:100]}...")
                    return None
                    
        except Exception as e:
            print(f"Ошибка при получении {cid} через API: {e}")
            return None
    
    async def fetch_via_gateway(self, cid: str, session: aiohttp.ClientSession) -> Optional[Dict[Any, Any]]:
        """Резервный способ через шлюз"""
        gateways = [
            f"http://127.0.0.1:8180/ipfs/{cid}",
            f"https://ipfs.io/ipfs/{cid}",
            f"https://gateway.pinata.cloud/ipfs/{cid}",
            f"https://cloudflare-ipfs.com/ipfs/{cid}",
        ]
        
        for gateway in gateways:
            try:
                async with session.get(gateway, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✓ Получено через шлюз: {gateway}")
                        return data
            except Exception as e:
                print(f"✗ Ошибка шлюза {gateway}: {e}")
                continue
        return None

async def fetch_local(uri: str, session: aiohttp.ClientSession, ipfs_client: IPFSClient) -> Optional[Dict[Any, Any]]:
    """Улучшенная функция загрузки с приоритетом прямого API"""
    
    if 'ipfs' in uri:
        print(f"🔍 Обрабатываем IPFS URI: {uri}")
        cid = uri.split('/ipfs/')[-1].split('/')[0]  # Берем только CID
        
        # ПРИОРИТЕТ 1: Прямое API подключение
        data = await ipfs_client.fetch_via_api(cid)
        if data:
            print("✓ Успешно получено через прямое API")
            return data
        
        # ПРИОРИТЕТ 2: Локальный шлюз
        print("🔄 Пробуем через шлюзы...")
        data = await ipfs_client.fetch_via_gateway(cid, session)
        if data:
            return data
            
        print('❌ Все методы IPFS не сработали')
        return None
        
    elif 'irys' in uri:
        print(f"🔍 Обрабатываем Irys URI: {uri}")
        code = uri.split('/')[-1]
        uris = [
            f"https://node1.irys.xyz/{code}",
            f"https://node2.irys.xyz/{code}",
            f"https://gateway.irys.xyz/{code}",
        ]
        
        async def fetch_single_uri(uri_to_fetch: str) -> Optional[Dict[Any, Any]]:
            try:
                async with session.get(uri_to_fetch, timeout=aiohttp.ClientTimeout(total=3)) as r:
                    if r.status == 200:
                        return await r.json()
            except Exception:
                return None
            return None
        
        # Запускаем все запросы конкурентно
        tasks = [fetch_single_uri(uri_to_fetch) for uri_to_fetch in uris]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Ищем первый успешный результат
        for result in results:
            if result and not isinstance(result, Exception):
                print("✓ Успешно получено с Irys")
                return result
        
        print("❌ Все Irys endpoints не сработали")
        return None
        
    else:
        # Обычные HTTP-запросы
        print(f"🔍 Обрабатываем обычный URI: {uri}")
        try:
            async with session.get(uri, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = await r.json()
                    print(f"✓ Успешно получено: {uri}")
                    return data
                else:
                    print(f'❌ Ошибка {uri}: статус {r.status}')
                    return None
        except Exception as e:
            print(f'❌ Ошибка запроса {uri}: {e}')
            return None

async def fetch_meta_with_retries(session: aiohttp.ClientSession, uri: str, ipfs_client: IPFSClient) -> dict | None:
    """Гарантированная загрузка метаданных с множественными попытками"""
    if not uri:
        print("No URI provided")
        return None
        
    print(f"Starting metadata fetch for URI: {uri}")
    
    # Увеличиваем количество попыток и улучшаем стратегию
    for attempt in range(15):  # Увеличиваем до 15 попыток
        try:
            print(f"Attempt {attempt + 1}/15 to fetch metadata")
            data = await fetch_local(uri, session, ipfs_client)
            
            if data and isinstance(data, dict):
                print(f"Successfully fetched metadata on attempt {attempt + 1}")
                return data
            else:
                print(f"Attempt {attempt + 1} returned invalid data, retrying...")
                # Увеличиваем время ожидания с каждой попыткой
                wait_time = min(2 + attempt, 10)  # От 2 до 10 секунд
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            print(f"Error in attempt {attempt + 1}: {e}")
            wait_time = min(2 + attempt, 10)
            await asyncio.sleep(wait_time)
    
    print(f"Failed to fetch metadata after 15 attempts for URI: {uri}")
    return None

def find_community_anywhere_with_src(meta_json: dict) -> tuple[str|None, str|None, str|None]:
    """Ищет community ID в метаданных с расширенным поиском"""
    if not meta_json or not isinstance(meta_json, dict):
        return None, None, None
        
    print(f"Searching for community in metadata fields: {list(meta_json.keys())}")
    
    # Проверяем основные поля
    for field in ['twitter', 'x', 'external_url', 'website', 'social']:
        if field in meta_json:
            url, cid = canonicalize_community_url(meta_json[field])
            if cid:
                print(f"Found community in {field}: {cid}")
                return url, cid, field
    
    # Проверяем extensions если есть
    if 'extensions' in meta_json:
        extensions = meta_json['extensions']
        if isinstance(extensions, dict):
            for field in ['twitter', 'x', 'website', 'social']:
                if field in extensions:
                    url, cid = canonicalize_community_url(extensions[field])
                    if cid:
                        print(f"Found community in extensions.{field}: {cid}")
                        return url, cid, f"extensions.{field}"
    
    # Проверяем properties если есть
    if 'properties' in meta_json:
        properties = meta_json['properties']
        if isinstance(properties, dict):
            for field in ['twitter', 'x', 'website', 'social']:
                if field in properties:
                    url, cid = canonicalize_community_url(properties[field])
                    if cid:
                        print(f"Found community in properties.{field}: {cid}")
                        return url, cid, f"properties.{field}"
    
    print("No community found in metadata")
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

async def get_twitter_data(session, uri, ipfs_client: IPFSClient):
    """Получает Twitter данные с максимальной вероятностью"""
    print(f"Starting Twitter data extraction for URI: {uri}")
    
    community_id = None
    meta = await fetch_meta_with_retries(session, uri, ipfs_client)
    
    if meta:
        print("Metadata successfully loaded, searching for community...")
        community_url, community_id, source = find_community_anywhere_with_src(meta)
        print(f"Community search result: URL={community_url}, ID={community_id}, Source={source}")
    else:
        print("Failed to load metadata - cannot extract community info")
        return "", None

    twitter_name = ""
    if community_id:
        print(f"Community ID found: {community_id}, attempting to get Twitter username...")
        twitter_name = await get_creator_username(session, community_id)
        
        if twitter_name:
            twitter_name = f"@{twitter_name}"
            print(f"Successfully extracted Twitter: {twitter_name}")
        else:
            print(f"Failed to extract Twitter username for community {community_id}")
    else:
        print("No community ID found in metadata")

    return twitter_name, community_id

async def process_create(data):
    """Создает UserDev и Token из полученных данных с гарантированным получением мета"""
    session = None
    try:
        await asyncio.sleep(5)
        mint = data.get('mint', '')
        user = data.get('traderPublicKey', '')
        uri = data.get('uri', '')
        
        print(f"Processing token creation for mint: {mint}")
        print(f"User: {user}")
        print(f"URI: {uri}")
        
        # Создаем сессию с увеличенными лимитами для надежности
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=200, ttl_dns_cache=300),
            headers={"User-Agent": "auto-buy/5.0-ultra-fastest"},
            timeout=aiohttp.ClientTimeout(total=30)  # Увеличиваем общий timeout
        )

        # Создаем IPFS клиент
        ipfs_client = IPFSClient()
        
        # Гарантированно получаем Twitter данные
        twitter_name, community_id = await get_twitter_data(session, uri, ipfs_client)
        
        bonding_curve = data.get('bonding_curve', '')
        token_created = False
        
        # Обработка Twitter имени
        if not twitter_name or twitter_name == "@" or twitter_name == "@None":
            twitter_name = ""
            print("No valid Twitter username found")
        else:
            print(f"Twitter username: {twitter_name}")
            
        twitter = None
        if twitter_name and twitter_name != "":
            twitter, created = await sync_to_async(Twitter.objects.get_or_create)(
                name=twitter_name,
            )
            if created:
                print(f"Created new Twitter record: {twitter_name}")
            else:
                print(f"Found existing Twitter record: {twitter_name}")
        
        # Создаем или получаем UserDev
        user_dev, created = await sync_to_async(UserDev.objects.get_or_create)(
            adress=user,
            defaults={
                'total_tokens': 0,
            }
        )
        
        if created:
            print(f"Created new UserDev: {user}")
        else:
            print(f"Found existing UserDev: {user}")
        
        # Создаем токен с проверкой Twitter
        if twitter:
            if twitter.blacklist == False:
                token, token_created = await sync_to_async(Token.objects.get_or_create)(
                    address=mint,
                    defaults={
                        'dev': user_dev,
                        'twitter': twitter,
                        'ath': 0,
                        'migrated': False,
                        'total_trans': 0,
                        'total_fees': 0.0,
                        'bonding_curve': bonding_curve or "",
                        'community_id': community_id or "",
                        'processed': False
                    }
                )
                print(f"Token created with Twitter: {mint}")
            else:
                print(f"Twitter {twitter_name} is blacklisted, creating token without Twitter")
                token, token_created = await sync_to_async(Token.objects.get_or_create)(
                    address=mint,
                    defaults={
                        'dev': user_dev,
                        'ath': 0,
                        'migrated': False,
                        'total_trans': 0,
                        'total_fees': 0.0,
                        'bonding_curve': bonding_curve or "",
                        'community_id': community_id or "",
                        'processed': True
                    }
                )
        else:
            token, token_created = await sync_to_async(Token.objects.get_or_create)(
                address=mint,
                defaults={
                    'dev': user_dev,
                    'ath': 0,
                    'migrated': False,
                    'total_trans': 0,
                    'total_fees': 0.0,
                    'bonding_curve': bonding_curve or "",
                    'community_id': community_id or "",
                    'processed': True
                }
            )
            print(f"Token created without Twitter: {mint}")

        # Обновляем счетчики
        if token_created:
            user_dev.total_tokens += 1
            if twitter:
                twitter.total_tokens += 1
                await sync_to_async(twitter.save)()
                print(f"Updated Twitter token count: {twitter.total_tokens}")
            await sync_to_async(user_dev.save)()
            print(f"Updated UserDev token count: {user_dev.total_tokens}")
            
        print(f"Token processing completed successfully: {mint}")
        
    except Exception as e:
        print(f"Error in process_create for mint {mint}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if session:
            await session.close()
            print("Session closed")
        # Закрываем IPFS клиент если он был создан
        if 'ipfs_client' in locals() and ipfs_client and ipfs_client.api_client:
            try:
                ipfs_client.api_client.close()
                print("IPFS client closed")
            except Exception as e:
                print(f"Error closing IPFS client: {e}")


