import asyncio
import websockets
import json
import time
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
    except Exception as e:
        print(e)
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
    except Exception as e:
        print(e)
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
    except Exception as e:
        print(e)
        pass
    return None, None, None

async def get_creator_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Получает username с несколькими попытками и fallback методами"""
    
    max_attempts = 3
    
    for attempt in range(max_attempts):
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
                        return u
                except Exception as e:
                    print(e)
                    continue
            
            # Если u все еще None и это не последняя попытка, ждем немного и повторяем
            if attempt < max_attempts - 1:
                await asyncio.sleep(1)  # Ждем 1 секунду перед повторной попыткой
                continue
                
        except Exception as e:
            # Если произошла ошибка и это не последняя попытка, ждем и повторяем
            if attempt < max_attempts - 1:
                await asyncio.sleep(1)
                continue
            else:
                print(f"Ошибка в get_creator_username после {max_attempts} попыток: {e}")
    
    return None



def find_community_from_uri(uri: str) -> Optional[str]:
    """Ищет community ID в URI"""
    if not uri:
        return None
    print(uri)
    match = COMMUNITY_ID_RE.search(uri)
    return match.group(1) if match else None


async def fetch_local(uri,session):
    if('https://ipfs.io/ipfs/' in uri or "https://gateway.pinata.cloud/ipfs/" in uri):
        print(123,uri)
        code = uri.split('/')[-1]
        uri = f"http://127.0.0.1:8180/ipfs/{code}"
        async with session.get(uri, timeout=aiohttp.ClientTimeout(total=5)) as r:
            data = await r.json()
            if(data):
                return data
            else:
                print('ipfs говно')
                return data
    else:
        code = uri.split('/')[-1]
        uri1 = f"https://node1.irys.xyz/{code}"
        uri2 = f"https://node2.irys.xyz/{code}"
        
        # Создаем задачи для одновременных запросов
        async def fetch_from_uri(uri_to_fetch):
            try:
                async with session.get(uri_to_fetch, timeout=aiohttp.ClientTimeout(total=0.5)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return data
                    return None
            except Exception:
                return None
        
        # Запускаем оба запроса одновременно
        task1 = asyncio.create_task(fetch_from_uri(uri1))
        task2 = asyncio.create_task(fetch_from_uri(uri2))
        
        # Ждем первый успешный ответ
        done, pending = await asyncio.wait(
            [task1, task2], 
            return_when=asyncio.FIRST_COMPLETED,
            timeout=0.5
        )
        
        # Отменяем оставшиеся задачи
        for task in pending:
            task.cancel()
        
        # Проверяем результаты
        for task in done:
            try:
                result = task.result()
                if result is not None:
                    return result
            except Exception:
                continue
        
        # Если оба запроса не удались, пробуем оригинальный URI как fallback
        try:
            async with session.get(uri, timeout=aiohttp.ClientTimeout(total=0.5)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data
        except Exception:
            pass



async def fetch_meta_with_retries(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Загружает метаданные с URI"""
    if not uri:
        return None
        
    try:
        for i in range(10):
            data = await fetch_local(uri,session)
            if data:
                return data
            else:
                await asyncio.sleep(2)
    except Exception as e:
        print(e)
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





async def get_twitter_data(session,uri):
    community_id = None
    meta = await fetch_meta_with_retries(session, uri)
    if meta:
        community_url, community_id, _ = find_community_anywhere_with_src(meta)
        

    twitter_name = ""
    if community_id:
        twitter_name = await get_creator_username(session, community_id)

    if twitter_name:
        twitter_name=f"@{twitter_name}"
    return twitter_name, community_id



async def process_create(data):
    """Создает UserDev и Token из полученных данных"""
    session = None
    try:
        await asyncio.sleep(5)
        mint = data.get('mint', '')
        user = data.get('traderPublicKey', '')
        uri = data.get('uri', '')
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            headers={"User-Agent": "auto-buy/5.0-ultra-fastest"},
            timeout=aiohttp.ClientTimeout(total=1)
        )

        twitter_name,community_id = await get_twitter_data(session,uri)
        bonding_curve = data.get('bonding_curve','')
        token_created = False
        if not(twitter_name) or twitter_name == "@" or twitter_name=="@None":
            twitter_name = ""
        twitter = None
        if(twitter_name or twitter_name!= ""):
            twitter, created = await sync_to_async(Twitter.objects.get_or_create)(
                name=twitter_name,
            )
        
        user_dev, created = await sync_to_async(UserDev.objects.get_or_create)(
            adress=user,
            defaults={
                'total_tokens': 0,
            }
        )
        # Проверяем, что twitter существует и не в черном списке
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

        
        if token_created:
            user_dev.total_tokens += 1
            if twitter:  # Добавляем проверку
                twitter.total_tokens +=1
                await sync_to_async(twitter.save)()
            await sync_to_async(user_dev.save)()
    except Exception as e:
        print("create",e)
        pass
    finally:
        if session:
            await session.close()


