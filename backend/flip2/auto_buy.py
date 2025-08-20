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

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Settings, Twitter, UserDev
from asgiref.sync import sync_to_async

# Конфигурация
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_FUN = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
HELIUS_HTTP = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMPPORTAL_TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"
TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

# Кэши
COMMUNITY_CACHE = {}
URI_META_CACHE = {}

# Регулярные выражения
COMMUNITY_ID_RE = re.compile(r"/communities/(\d+)", re.IGNORECASE)
FAILED_ERROR_RE = re.compile(r"(failed:|custom program error)", re.IGNORECASE)
PROGDATA_RE = re.compile(r"Program data:\s*([A-Za-z0-9+/=]+)")
INSTRUCTION_MINT_RE = re.compile(r"Program log: Instruction: (InitializeMint2|InitializeMint)", re.IGNORECASE)

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

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass
import time
import asyncio
import re
import base64
import websockets
import aiohttp
import requests
from typing import Optional, Tuple, List, Dict, Any

# Импорт solders для работы с Solana
try:
    from solders.keypair import Keypair
    from solders.transaction import VersionedTransaction
    from solders.rpc.requests import SendVersionedTransaction
    from solders.rpc.config import RpcSendTransactionConfig
    from solders.commitment_config import CommitmentLevel
    SOLDERS_AVAILABLE = True
except ImportError:
    SOLDERS_AVAILABLE = False
    print("Warning: solders not available, buy function will not work")

# Быстрый JSON парсер
try:
    import orjson
    def jloads(b: bytes | str):
        if isinstance(b, str): b = b.encode()
        return orjson.loads(b)
    def jdumps(o): return orjson.dumps(o).decode()
except ImportError:
    import json
    def jloads(b: bytes | str):
        if isinstance(b, bytes): b = b.decode("utf-8", "ignore")
        return json.loads(b.lstrip("\ufeff").strip())
    def jdumps(o): return json.dumps(o, separators=(",", ":"))

# Импорт base58
try:
    from base58 import b58encode, b58decode
except ImportError:
    # Fallback если base58 не установлен
    def b58encode(data: bytes) -> str:
        return data.hex()
    def b58decode(data: str) -> bytes:
        return bytes.fromhex(data)

# ===================== CONFIG =====================
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_FUN = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
HELIUS_HTTP = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# PumpPortal API
PUMPPORTAL_TRADE_LOCAL = "https://pumpportal.fun/api/trade-local"

# X/Twitter API
TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

# Solana private key (из переменной окружения)
SOLANA_PRIVATE_KEY = os.getenv("SOLANA_PRIVATE_KEY")

# Default values (как в pump_buy.py)
DEFAULT_SLIPPAGE = 10.0
DEFAULT_PRIORITY_FEE = 0.00005
DEFAULT_POOL = "pump"   # варианты: pump | pump-amm | raydium | auto
LOGS_SUB_JSON = json.dumps({
    "jsonrpc": "2.0",
    "id": "logs-auto-buy",
    "method": "logsSubscribe",
    "params": [
        {"mentions": [PUMP_FUN]},
        {"commitment": "processed"}
    ]
})


def clean_amount(s: str) -> float:
    """Очищает строку с числом и конвертирует в float"""
    s = s.strip().replace(",", ".")
    s = s.strip("()[]")
    return float(s)

def keypair_from_base58(secret_b58: str) -> Keypair:
    """Создает Keypair из base58 строки"""
    return Keypair.from_base58_string(secret_b58.strip())

def build_buy_tx(mint: str,
                 buyer_pubkey: str,
                 sol_amount: float,
                 slippage_percent: float = DEFAULT_SLIPPAGE,
                 priority_fee_sol: float = DEFAULT_PRIORITY_FEE,
                 pool: str = DEFAULT_POOL) -> bytes:
    """Строит транзакцию покупки через PumpPortal API"""
    payload = {
        "publicKey": buyer_pubkey,
        "action": "buy",
        "mint": mint,
        "amount": sol_amount,          # тратим X SOL
        "denominatedInSol": "true",    # сумма в SOL
        "slippage": slippage_percent,  # % слиппеджа
        "priorityFee": priority_fee_sol,  # приорити-комиссия, SOL
        "pool": pool
    }
    
    # Отладочная информация
    
    r = requests.post(PUMPPORTAL_TRADE_LOCAL,
                      headers={"Content-Type": "application/json"},
                      data=json.dumps(payload),
                      timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"PumpPortal error {r.status_code}: {r.text}")
    return r.content  # сериализованный VersionedTransaction (bytes)

def send_vt_via_helius(vt_bytes: bytes, kp: Keypair, helius_http: str) -> str:
    """Отправляет подписанную транзакцию через Helius RPC"""
    vt = VersionedTransaction.from_bytes(vt_bytes)
    signed_tx = VersionedTransaction(vt.message, [kp])
    cfg = RpcSendTransactionConfig(preflight_commitment=CommitmentLevel.Confirmed)
    body = SendVersionedTransaction(signed_tx, cfg).to_json()
    r = requests.post(helius_http,
                      headers={"Content-Type": "application/json"},
                      data=body,
                      timeout=10)
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"Helius send error: {data['error']}")
    sig = data.get("result")
    if not sig:
        raise RuntimeError(f"Unexpected Helius response: {data}")
    return sig



async def create_invoice(mint):
    try:
        # Получаем настройки из базы данных
        settings_obj = await sync_to_async(Settings.objects.first)()
        if not settings_obj:
            print(f"❌ Cannot buy {mint}: no settings found")
            return
            
        # Получаем настройки из Settings (как в pump_buy.py)
        buyer_pubkey = settings_obj.buyer_pubkey  # это приватный ключ
        sol_amount = float(settings_obj.sol_amount)
        slippage_percent = float(settings_obj.slippage_percent)
        priority_fee_sol = float(settings_obj.priority_fee_sol)
        pool = "pump"  # используем pump pool по умолчанию
        
        # Проверяем, что у нас есть все необходимые параметры
        if not buyer_pubkey or sol_amount <= 0:
            print(f"❌ Cannot buy {mint}: invalid buyer_pubkey or sol_amount")
            return
            
        try:
            kp = keypair_from_base58(buyer_pubkey)
        except Exception as e:
            print(f"❌ Error creating keypair from buyer_pubkey: {str(e)}")
            print(f"   Make sure buyer_pubkey contains a valid base58 private key")
            return
        
        # Строим транзакцию покупки (точно как в pump_buy.py)
        tx_bytes = build_buy_tx(
            mint=mint,
            buyer_pubkey=str(kp.pubkey()),  # используем публичный ключ для API
            sol_amount=sol_amount,
            slippage_percent=slippage_percent,
            priority_fee_sol=priority_fee_sol,
            pool=pool
        )
        
        return tx_bytes, kp, HELIUS_HTTP
    except Exception as e:
        print(f"❌ Error buying {mint}: {str(e)}")    



async def buy(tx_bytes, kp, HELIUS_HTTP):
        sig = send_vt_via_helius(tx_bytes, kp, HELIUS_HTTP)
        print(f"✅ Transaction sent successfully: {sig}")
        print(f"   View: https://solscan.io/tx/{sig}")
        


                   
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
                    name=f"@{twitter_name}",
                    whitelist=True,
                    ath__gte=settings_obj.ath_from,
                    total_trans__gte=settings_obj.total_trans_from
                )
            except:
                return False
        else:
            try:
                twitter_obj = await sync_to_async(Twitter.objects.get)(
                    name=f"@{twitter_name}",
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
            if token.total_trans < 100:
                return False

        return True
    except Exception as e:
        print(e)
        return False

async def checker(session, uri,creator):
        community_id = None
        meta = await fetch_meta_with_retries(session, uri)
        if meta:
            community_url, community_id, _ = find_community_anywhere_with_src(meta)
        if community_id:
            print(community_id)
            twitter_name = await get_creator_username(session, community_id)
            print(twitter_name)
            check = await check_twitter_whitelist(twitter_name,creator)
            print(check)
            return check
            



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
        
        # Асинхронно запускаем create_invoice и checker одновременно
        create_invoice_task = create_invoice(mint)
        checker_task = checker(session, uri, creator)
        
        # Ждем завершения обеих задач
        results = await asyncio.gather(
            create_invoice_task, 
            checker_task
        )
        
        # Распаковываем результаты
        create_result, need_to_buy = results
        
        # Проверяем, что create_invoice вернул результат
        if create_result is None:
            print(f"❌ Failed to create invoice for {mint}")
            return
            
        tx_bytes, kp, HELIUS_HTTP = create_result

        # Вызываем buy только если checker вернул True
        if need_to_buy:
            await buy(tx_bytes, kp, HELIUS_HTTP)
    except Exception as e:
        print(e)
        pass

async def main_loop():
    """Основной цикл обработки"""
    session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
        headers={"User-Agent": "auto-buy/5.0-ultra-fastest"},
        timeout=aiohttp.ClientTimeout(total=1)
    )
    
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
                        print(e)
                        continue
        except Exception as e:
            print(e)
            await asyncio.sleep(0.1)
        finally:
            await session.close()

if __name__ == "__main__":
    asyncio.run(main_loop())