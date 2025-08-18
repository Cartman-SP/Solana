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
from decimal import Decimal
import base64
from decimal import Decimal
import requests
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import Message
from solana.rpc.api import Client
from solana.rpc.commitment import CommitmentLevel
from solana.rpc.types import RpcSendTransactionConfig

import time
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

# WebSocket подписка
LOGS_SUB_JSON = json.dumps({
    "jsonrpc": "2.0",
    "id": "logs-auto-buy",
    "method": "logsSubscribe",
    "params": [
        {"mentions": [PUMP_FUN]},
        {"commitment": "processed"}
    ]
})


async def buy(mint):
    try:
        settings_obj = await sync_to_async(Settings.objects.first)()
        kp = Keypair.from_base58_string(settings_obj.buyer_pubkey.strip())
        
        # Строим транзакцию
        payload = {
            "publicKey": str(kp.pubkey()),
            "action": "buy",
            "mint": mint,
            "amount": float(settings_obj.sol_amount),
            "denominatedInSol": "true",
            "slippage": float(settings_obj.slippage_percent),
            "priorityFee": float(settings_obj.priority_fee_sol),
            "pool": "pump"
        }
        
        tx_response = requests.post(
            PUMPPORTAL_TRADE_LOCAL,  # Замените на реальный URL
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=10
        )
        tx_response.raise_for_status()
        
        # Отправляем транзакцию
        vt = VersionedTransaction.from_bytes(tx_response.content)
        signed_tx = VersionedTransaction(vt.message, [kp])
        body = SendVersionedTransaction(
            signed_tx, 
            RpcSendTransactionConfig(preflight_commitment=CommitmentLevel.Confirmed)
        ).to_json()
        
        rpc_response = requests.post(
            HELIUS_HTTP,  # Замените на реальный URL
            headers={"Content-Type": "application/json"},
            data=body,
            timeout=10
        )
        rpc_response.raise_for_status()
        
        data = rpc_response.json()
        if "error" in data:
            raise RuntimeError(f"Helius error: {data['error']}")
        
        return data["result"]
        
    except requests.RequestException as e:
        raise RuntimeError(f"HTTP error: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Transaction failed: {str(e)}")


JUPITER_API = "https://quote-api.jup.ag/v6"


async def buy_via_jupiter(mint: str):
    try:
        settings_obj = await sync_to_async(Settings.objects.first)()
        kp = Keypair.from_base58_string(settings_obj.buyer_pubkey.strip())
        amount_lamports = str(int(settings_obj.sol_amount * Decimal(1e9)))
        slippage_bps = str(min(int(settings_obj.slippage_percent * 100), 1000))
        
        # 3. Получаем квоту
        quote_params = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": mint,
            "amount": amount_lamports,
            "slippageBps": slippage_bps
        }
        
        quote_response = requests.get(
            f"{JUPITER_API}/quote",
            params=quote_params,
            headers={"Accept": "application/json"},
            timeout=15
        )
        quote_response.raise_for_status()
        quote = quote_response.json()

        if "error" in quote:
            raise RuntimeError(f"Jupiter quote error: {quote['error']}")

        # 4. Получаем транзакцию для подписи
        swap_payload = {
            "quoteResponse": quote,
            "userPublicKey": str(kp.pubkey()),
            "wrapAndUnwrapSol": True,
            "priorityFee": str(int(settings_obj.priority_fee_sol * Decimal(1e9)))
        }
        
        swap_response = requests.post(
            f"{JUPITER_API}/swap",
            json=swap_payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        swap_response.raise_for_status()
        swap_data = swap_response.json()

        if "swapTransaction" not in swap_data:
            raise RuntimeError("No transaction data in Jupiter response")

        # 5. Декодируем и подписываем транзакцию
        try:
            raw_tx = base64.b64decode(swap_data["swapTransaction"])
            tx = VersionedTransaction.from_bytes(raw_tx)
            
            # Создаем подписанную транзакцию
            signed_tx = VersionedTransaction(
                message=tx.message,
                signatures=[kp.sign(tx.message.serialize())]
            )
        except Exception as e:
            raise RuntimeError(f"Transaction signing failed: {str(e)}")

        # 6. Отправляем транзакцию
        rpc_client = Client(HELIUS_HTTP)
        tx_hash = await rpc_client.send_raw_transaction(
            bytes(signed_tx),
            opts=RpcSendTransactionConfig(
                skip_preflight=False,
                preflight_commitment=CommitmentLevel.Confirmed,
            )
        )
        
        return str(tx_hash.value)

    except requests.RequestException as e:
        raise RuntimeError(f"HTTP request failed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Swap execution failed: {str(e)}")



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
                await sync_to_async(UserDev.objects.get)(adress=creator)
                return False
            except:
                pass
        if(settings_obj.whitelist_enabled):
            try:
                await sync_to_async(Twitter.objects.get)(
                    name=f"@{twitter_name}",
                    whitelist=True,
                    ath__gte=settings_obj.ath_from,
                    total_trans__gte=settings_obj.total_trans_from
                )
            except:
                return False
        else:
            try:
                await sync_to_async(Twitter.objects.get)(
                    name=f"@{twitter_name}",
                    ath__gte=settings_obj.ath_from,
                    total_trans__gte=settings_obj.total_trans_from
                )
            except:
                return False
        return True
    except Exception as e:
        print(e)
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
            if twitter_name and check :
                print(f"buy {mint}")
                await buy_via_jupiter(mint)
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