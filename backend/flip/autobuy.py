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
from base58 import b58encode, b58decode
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token, Twitter, Settings
from asgiref.sync import sync_to_async
from django.utils import timezone

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


async def buy(api_private, mint, ammonut_to_buy, slippage, priorityFee):
    payload = {
        "action": "buy",             # "buy" or "sell"
        "mint": mint,      # contract address of the token you want to trade
        "amount": ammonut_to_buy,            # amount of SOL or tokens to trade
        "denominatedInSol": "true", # "true" if amount is amount of SOL, "false" if amount is number of tokens
        "slippage": slippage,              # percent slippage allowed
        "priorityFee": priorityFee,        # amount used to enhance transaction speed
        "pool": "pump"               # exchange to trade on. "pump", "raydium", "pump-amm", "launchlab", "raydium-cpmm", "bonk" or "auto"
    }
    
    # Используем aiohttp для асинхронного запроса
    async with aiohttp.ClientSession() as session:
        try:
            timeout = aiohttp.ClientTimeout(total=5)  # 5 секунд на покупку
            async with session.post(
                url=f"https://pumpportal.fun/api/trade?api-key={api_private}", 
                data=payload,
                timeout=timeout
            ) as response:
                print(payload)
                data = await response.json()
                print(data)       # Tx signature or error(s)
                return data
        except Exception as e:
            print(f"Error buying {mint}: {e}")
            return None


                   
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
                    return u
            except:
                continue
                
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

async def check_twitter_whitelist(twitter_name, creator,mint):

    try:
        # Получаем настройки и объекты одним запросом
        settings_obj, twitter_obj = await asyncio.gather(
            sync_to_async(Settings.objects.first)(),
            sync_to_async(Twitter.objects.get)(name=f"@{twitter_name}"),
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

        if settings_obj.one_token_enabled and total_tokens > 0:
            return False
        if twitter_obj.blacklist:
            return False
        if settings_obj.whitelist_enabled and twitter_obj.whitelist:
            return True

        print(twitter_name)
        recent_tokens = await sync_to_async(
            lambda: list(
                Token.objects.filter(
                    twitter=twitter_obj,
                    processed=True
                ).exclude(address=mint)
                .order_by('-created_at')
                .only('ath', 'total_trans', 'total_fees', 'created_at')[:3]
            )
        )()
        
        # Проверяем возраст самого свежего токена
        if recent_tokens:
            newest_token = recent_tokens[0]  # Первый токен в списке (самый свежий)
            time_diff = timezone.now() - newest_token.created_at
            
            if time_diff < timedelta(hours=1):
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

async def checker(session, uri,creator,mint):
        community_id = None
        meta = await fetch_meta_hybrid(session, uri)
        if meta:
            community_url, community_id, _ = find_community_anywhere_with_src(meta)
        if community_id:
            twitter_name = await get_creator_username(session, community_id)
            print(twitter_name)
            if twitter_name:
                check = await check_twitter_whitelist(twitter_name,creator,mint)
                print(check)
                return check
        return False
            



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
        if not mint:
            return
        

        settings_obj = await sync_to_async(Settings.objects.first)()
        pubkey = settings_obj.buyer_pubkey
        amount = float(settings_obj.sol_amount)
        slippage = float(settings_obj.slippage_percent)
        priorityFee = float(settings_obj.priority_fee_sol)
        need_to_buy = await checker(session, uri, creator,mint)

        if need_to_buy:
            # Создаем задачу для покупки, чтобы не блокировать основной поток
            buy_task = asyncio.create_task(buy(pubkey,mint,amount,slippage,priorityFee))
            # Не ждем завершения, чтобы не блокировать обработку следующих сообщений
            print(f"Starting buy task for {mint}")
    except Exception as e:
        print(f"Error in process_message: {e}")
        pass

async def main_loop():
    """Основной цикл обработки"""
    session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=1000, ttl_dns_cache=300000),
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

if __name__ == "__main__":
    asyncio.run(main_loop())