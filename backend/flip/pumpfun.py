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


LOGS_SUB_JSON = json.dumps({
    "jsonrpc": "2.0",
    "id": "logs-auto-buy",
    "method": "logsSubscribe",
    "params": [
        {"mentions": ["6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"]},
        {"commitment": "processed"}
    ]
})


def generate_tx(pubkey, mint, amount, slippage, priorityFee): 
    signerKeypairs = [
        Keypair.from_base58_string(pubkey),
    ]

    response = requests.post(
        "https://pumpportal.fun/api/trade-local",
        headers={"Content-Type": "application/json"},
        json=[
            {
                "publicKey": str(signerKeypairs[0].pubkey()),
                "action": "buy", 
                "mint": mint,
                "denominatedInSol": "false",
                "amount": amount,
                "slippage": slippage,
                "priorityFee": priorityFee,
                "pool": "pump"
            },
        ]
    )

    if response.status_code != 200: 
        print("Failed to generate transactions.")
        print(response.reason)
    else:
        encodedTransactions = response.json()
        encodedSignedTransactions = []
        txSignatures = []

        for index, encodedTransaction in enumerate(encodedTransactions):
            signedTx = VersionedTransaction(VersionedTransaction.from_bytes(base58.b58decode(encodedTransaction)).message, [signerKeypairs[index]])
            encodedSignedTransactions.append(base58.b58encode(bytes(signedTx)).decode())
            txSignatures.append(str(signedTx.signatures[0]))

        return encodedSignedTransactions, txSignatures


def send_tx(encodedSignedTransactions, txSignatures):
    jito_response = requests.post(
        "https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af/",
        headers={"Content-Type": "application/json"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [
                encodedSignedTransactions
            ]
        }
    )

    for i, signature in enumerate(txSignatures):
        print(f'Transaction {i}: https://solscan.io/tx/{signature}')



                   
async def _tw_get(session, path, params):
    """Быстрый запрос к Twitter API"""
    to = aiohttp.ClientTimeout(total=0.5, connect=0.1)  # Еще более короткий timeout
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
        
        # Ждем первый успешный результат с таймаутом
        done, pending = await asyncio.wait(
            [task1, task2], 
            return_when=asyncio.FIRST_COMPLETED,
            timeout=0.5  # Таймаут 0.5 секунды
        )
        
        # Отменяем оставшиеся задачи
        for task in pending:
            task.cancel()
        
        # Проверяем результаты
        for task in done:
            try:
                u, f, src = task.result()
                if u:
                    return u
            except:
                continue
                
    except asyncio.TimeoutError:
        # Если таймаут, отменяем все задачи
        task1.cancel()
        task2.cancel()
    except:
        pass
    
    return None

def collect_progdata_bytes_after_create(logs):
    """Собирает байты данных программы после инструкции Create"""
    chunks, after = [], False
    for line in logs:
        low = str(line).lower()
        if "instruction" in low and "create" in low:
            after = True
            continue
        if not after:
            continue
        m = PROGDATA_RE.search(str(line))
        if m:
            chunks.append(m.group(1))
        elif chunks:
            break
    if not chunks:
        return None

    out = bytearray()
    for c in chunks:
        try:
            out += base64.b64decode(c, validate=True)
        except Exception:
            try:
                out += base58.b58decode(c)
            except Exception:
                return None
    return bytes(out)


def _read_borsh_string(buf: memoryview, off: int):
    """Читает Borsh строку из буфера"""
    if off + 4 > len(buf): return None, off
    ln = int.from_bytes(buf[off:off+4], "little"); off += 4
    if ln < 0 or off + ln > len(buf): return None, off
    try:
        s = bytes(buf[off:off+ln]).decode("utf-8", "ignore")
    except Exception:
        s = ""
    off += ln
    return s, off


def _take_pk(buf: memoryview, off: int):
    """Читает публичный ключ из буфера"""
    if off + 32 > len(buf): return None, off
    return base58.b58encode(bytes(buf[off:off+32])).decode(), off + 32


def parse_pump_create(raw: bytes):
    """Парсит данные создания токена PumpFun"""
    if not raw or len(raw) < 8: return None
    mv = memoryview(raw)
    off = 8
    name, off   = _read_borsh_string(mv, off)
    symbol, off = _read_borsh_string(mv, off)
    uri, off    = _read_borsh_string(mv, off)
    mint, off          = _take_pk(mv, off)
    bonding_curve, off = _take_pk(mv, off)
    creator, off       = _take_pk(mv, off)
    return {
        "uri": uri,
        "mint": mint ,
        "creator": creator,
        'name': name,
        'symbol': symbol,
        'bonding_curve':bonding_curve,
    }

def find_community_from_uri(uri: str) -> Optional[str]:
    """Ищет community ID в URI"""
    if not uri:
        return None
    print(uri)
    match = COMMUNITY_ID_RE.search(uri)
    return match.group(1) if match else None

async def fetch_meta_with_retries(session: aiohttp.ClientSession, uri: str, max_retries: int = 3) -> dict | None:
    """Загружает метаданные с URI с повторными попытками"""
    if not uri:
        return None
    
    for attempt in range(max_retries):
        try:
            # Уменьшаем таймаут для быстрого получения данных
            timeout = aiohttp.ClientTimeout(total=0.5, connect=0.2)
            async with session.get(uri, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 404:
                    # Если 404, возможно данные еще не готовы, пробуем еще раз
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1)  # Минимальная задержка
                        continue
                else:
                    print(f"HTTP {response.status} for {uri}")
                    
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.05)  # Очень короткая задержка при таймауте
                continue
            print(f"Timeout after {max_retries} attempts for {uri}")
        except aiohttp.ClientError as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.05)
                continue
            print(f"Client error for {uri}: {e}")
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(0.05)
                continue
            print(f"Unexpected error for {uri}: {e}")
    
    return None


async def fetch_meta_aggressive(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Агрессивная загрузка метаданных с максимальной скоростью"""
    if not uri:
        return None
    
    # Пробуем до 5 раз с очень короткими интервалами
    for attempt in range(5):
        try:
            # Очень короткий таймаут для максимальной скорости
            timeout = aiohttp.ClientTimeout(total=0.3, connect=0.1)
            async with session.get(uri, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 404:
                    # При 404 сразу пробуем еще раз без задержки
                    continue
                else:
                    # Для других ошибок небольшая задержка
                    if attempt < 4:
                        await asyncio.sleep(0.02)
                        continue
                    
        except (asyncio.TimeoutError, aiohttp.ClientError):
            # При любых сетевых ошибках сразу пробуем еще раз
            if attempt < 4:
                continue
        except Exception:
            # При других ошибках минимальная задержка
            if attempt < 4:
                await asyncio.sleep(0.01)
                continue
    
    return None


async def fetch_meta_parallel(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Параллельная загрузка метаданных с несколькими одновременными запросами"""
    if not uri:
        return None
    
    async def single_request():
        try:
            timeout = aiohttp.ClientTimeout(total=0.2, connect=0.1)
            async with session.get(uri, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
        except:
            pass
        return None
    
    # Запускаем 3 параллельных запроса
    tasks = [single_request() for _ in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Возвращаем первый успешный результат
    for result in results:
        if isinstance(result, dict):
            return result
    
    return None


async def fetch_meta_ultra_fast(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Ультра-быстрая загрузка метаданных с максимальной агрессивностью"""
    if not uri:
        return None
    
    # Первая волна: 5 параллельных запросов
    async def single_request():
        try:
            timeout = aiohttp.ClientTimeout(total=0.15, connect=0.05)
            async with session.get(uri, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
        except:
            pass
        return None
    
    # Запускаем 5 параллельных запросов
    tasks = [single_request() for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Проверяем результаты
    for result in results:
        if isinstance(result, dict):
            return result
    
    # Если первая волна не удалась, пробуем еще раз с небольшой задержкой
    await asyncio.sleep(0.01)
    
    # Вторая волна: еще 3 запроса
    tasks2 = [single_request() for _ in range(3)]
    results2 = await asyncio.gather(*tasks2, return_exceptions=True)
    
    for result in results2:
        if isinstance(result, dict):
            return result
    
    return None


async def fetch_meta_super_aggressive(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Супер-агрессивная загрузка метаданных с множественными волнами"""
    if not uri:
        return None
    
    async def single_request(timeout_val=0.1):
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_val, connect=0.05)
            async with session.get(uri, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
        except:
            pass
        return None
    
    # Волна 1: 8 параллельных запросов (очень быстро)
    tasks1 = [single_request(0.1) for _ in range(8)]
    results1 = await asyncio.gather(*tasks1, return_exceptions=True)
    
    for result in results1:
        if isinstance(result, dict):
            return result
    
    # Волна 2: 5 запросов с небольшой задержкой
    await asyncio.sleep(0.02)
    tasks2 = [single_request(0.15) for _ in range(5)]
    results2 = await asyncio.gather(*tasks2, return_exceptions=True)
    
    for result in results2:
        if isinstance(result, dict):
            return result
    
    # Волна 3: 3 запроса с большей задержкой
    await asyncio.sleep(0.05)
    tasks3 = [single_request(0.2) for _ in range(3)]
    results3 = await asyncio.gather(*tasks3, return_exceptions=True)
    
    for result in results3:
        if isinstance(result, dict):
            return result
    
    # Волна 4: 2 запроса с еще большей задержкой
    await asyncio.sleep(0.1)
    tasks4 = [single_request(0.3) for _ in range(2)]
    results4 = await asyncio.gather(*tasks4, return_exceptions=True)
    
    for result in results4:
        if isinstance(result, dict):
            return result
    
    return None


async def fetch_meta_with_persistent_retries(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Загрузка метаданных с постоянными повторными попытками"""
    if not uri:
        return None
    
    # Пробуем до 10 раз с увеличивающимися интервалами
    for attempt in range(10):
        try:
            # Увеличиваем таймаут с каждой попыткой
            timeout_val = min(0.1 + (attempt * 0.05), 0.5)
            timeout = aiohttp.ClientTimeout(total=timeout_val, connect=0.05)
            
            async with session.get(uri, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 404:
                    # При 404 пробуем еще раз с увеличивающейся задержкой
                    if attempt < 9:
                        await asyncio.sleep(0.02 * (attempt + 1))
                        continue
                else:
                    # Для других ошибок небольшая задержка
                    if attempt < 9:
                        await asyncio.sleep(0.01)
                        continue
                    
        except (asyncio.TimeoutError, aiohttp.ClientError):
            # При сетевых ошибках пробуем еще раз
            if attempt < 9:
                await asyncio.sleep(0.01)
                continue
        except Exception:
            # При других ошибках минимальная задержка
            if attempt < 9:
                await asyncio.sleep(0.01)
                continue
    
    return None


async def fetch_meta_hybrid(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Гибридная загрузка метаданных с несколькими стратегиями"""
    if not uri:
        return None
    
    # Стратегия 1: Супер-агрессивная параллельная загрузка
    result = await fetch_meta_super_aggressive(session, uri)
    if result:
        return result
    
    # Стратегия 2: Если не получилось, пробуем с постоянными попытками
    result = await fetch_meta_with_persistent_retries(session, uri)
    if result:
        return result
    
    # Стратегия 3: Последняя попытка - обычная агрессивная загрузка
    result = await fetch_meta_aggressive(session, uri)
    if result:
        return result
    
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


async def process_message(msg, session):
    """Обработка входящего сообщения"""
    try:
        logs = msg.get("params", {}).get("result", {}).get("value", {}).get("logs", [])
        
        if not any(INSTRUCTION_MINT_RE.search(log) for log in logs):
            return
        data = collect_progdata_bytes_after_create(logs)
        parsed = parse_pump_create(data or b"")
        if not parsed:
            return

        mint = (parsed["mint"] or "").strip()
        uri = (parsed["uri"] or "").strip()
        creator = (parsed["creator"] or "").strip()
        name = (parsed["name"] or "").strip()
        symbol = (parsed["symbol"] or "").strip()
        bonding_curve = (parsed["bonding_curve"] or "").strip()
        if not mint:
            return
        

        community_id = None
        meta = await fetch_meta_hybrid(session, uri)
        if meta:
            community_url, community_id, _ = find_community_anywhere_with_src(meta)
            
        else:
            print(f"\n--------------------------------\nNo meta found for {name}, {mint}\n--------------------------------\n")

        twitter_name = ""
        if community_id:
            twitter_name = await get_creator_username(session, community_id)

        if twitter_name:
            twitter_name=f"@{twitter_name}"
        data = {
            'source': 'pumpfun',
            'mint': mint,
            'user': creator,
            'name': name,
            'symbol': symbol,
            'twitter_name': twitter_name,
            'bonding_curve':bonding_curve,
            'community_id': community_id,
        }
        # Создаем задачи для параллельного выполнения, но не ждем их завершения
        create_live_task = asyncio.create_task(process_live(data))
        create_create_task = asyncio.create_task(process_create(data))
        
        # Не ждем завершения задач, чтобы не блокировать обработку следующих сообщений
        print(f"Started processing tasks for {name} ({mint})")
    except Exception as e:
        print(f"Error in process_message: {e}")
        pass
        

async def main_loop():
    """Основной цикл обработки"""
    session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=100000, ttl_dns_cache=300000),
        headers={"User-Agent": "auto-buy/5.0-ultra-fastest"},
        timeout=aiohttp.ClientTimeout(total=1)
    )

    try:
        while True:
            try:
                async with websockets.connect(
                    WS_URL,
                    ping_interval=30,
                    max_size=2**20,
                    compression=None
                ) as ws:
                    await ws.send(LOGS_SUB_JSON)
                    await ws.recv()
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                            if msg.get("method") == "logsNotification":
                                await process_message(msg, session)
                        except Exception as e:
                            print(f"Error processing message: {e}")
                            continue
            except Exception as e:
                print(f"WebSocket error: {e}")
                await asyncio.sleep(0.1)
    finally:
        await session.close()


async def runner():
    """Запускает сервер для расширения и основной цикл параллельно"""
    server_task = asyncio.create_task(start_extension_server())
    try:
        await main_loop()
    finally:
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task

if __name__ == "__main__":
    asyncio.run(runner())