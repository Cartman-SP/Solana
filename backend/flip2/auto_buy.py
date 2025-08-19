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




import base64, random, time, requests
from typing import Optional, Tuple

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.message import MessageV0, to_bytes_versioned
from solders.transaction import VersionedTransaction

class QuickNodeBuyerError(Exception): pass

def buy_pumpfun_via_quicknode(
    *,
    # ТВОИ ДАННЫЕ
    qn_http_url: str,              # твой HTTPS QuickNode endpoint, например "https://xxx.quiknode.pro/abcdef/"
    payer_secret_b58: str,         # приватный ключ кошелька в base58
    mint: str,                     # mint адрес токена pump.fun (....pump)
    sol_in_lamports: int,          # сколько SOL потратить (в лампортах, 1 SOL = 1_000_000_000)
    # НАСТРОЙКИ СБОРКИ SWAP
    slippage_bps: int = 100,       # 100 = 1%
    priority_fee_level: str = "high",  # low | medium | high | extreme
    commitment: str = "confirmed",
    # JITO / BUNDLE
    jito_region: str = "frankfurt",# region для Lil’ JIT (см. getRegions)
    tip_lamports: Optional[int] = None, # размер чаевых валидатору (если None — возьмём ~медиану через getTipFloor)
    tip_account: Optional[str] = None,  # фикс. tip-аккаунт (если None — получим любой через getTipAccounts)
    # ДОП
    return_bundle_status: bool = False, # если True — сразу проверим статус bundle (доп. вызов)
    timeout: float = 3.5,               # таймауты HTTP
) -> dict:
    """
    Быстрая покупка токена на pump.fun через QuickNode:
      1) POST /pump-fun/swap -> base64 tx (unsigned)
      2) подпись этой транзы локально
      3) сборка отдельной tip-транзы на Jito аккаунт
      4) sendBundle([swap, tip]) через Lil' JIT

    Возвращает: dict с bundle_id, использованным tip и пр.
    """
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.timeout = timeout

    def _rpc(method: str, params=None):
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        r = s.post(qn_http_url, json=body)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise QuickNodeBuyerError(f"RPC {method} error: {j['error']}")
        return j["result"]

    def _pumpfun_swap_tx(wallet: str) -> str:
        url = "https://public.jupiterapi.com/pump-fun/swap"
        print(url)
        payload = {
            "wallet": wallet,
            "type": "BUY",
            "mint": mint,
            "inAmount": str(sol_in_lamports),
            "priorityFeeLevel": priority_fee_level,
            "slippageBps": str(slippage_bps),
            "commitment": commitment,
        }
        print(payload)
        r = s.post(url, json=payload)
        print(r.text)
        r.raise_for_status()
        j = r.json()
        if "tx" not in j:
            raise QuickNodeBuyerError(f"/pump-fun/swap bad response: {j}")
        return j["tx"]  # base64 unsigned

    def _get_tip_account() -> str:
        if tip_account:
            return tip_account
        # Быстрее — захардкодить один из Jito tip accounts у себя.
        # Здесь берём любой через RPC (1 вызов).
        accs = _rpc("getTipAccounts", [jito_region]) if jito_region else _rpc("getTipAccounts")
        return random.choice(accs)

    def _get_tip_amount_lamports() -> int:
        if tip_lamports is not None:
            return tip_lamports
        # Берём медиану из getTipFloor и конвертим SOL -> лампорты
        floor = _rpc("getTipFloor")
        # floor = [{..., "landed_tips_50th_percentile": 0.0005, ...}]
        median_sol = float(floor[0]["landed_tips_50th_percentile"])
        # немного бустим, чтобы выигрывать аукцион
        boosted = max(median_sol * 1.25, 0.0002)  # min 0.0002 SOL
        return int(boosted * 1_000_000_000)

    def _latest_blockhash() -> Hash:
        result = _rpc("getLatestBlockhash", [{"commitment": commitment}])
        return Hash.from_string(result["value"]["blockhash"])
    def _sign_base64_tx(unsigned_b64: str, payer: Keypair) -> str:
        tx_bytes = base64.b64decode(unsigned_b64)
        vt = VersionedTransaction.from_bytes(tx_bytes)
        msg = vt.message
        # найдём индекс нашей подписи и подставим её
        keys = list(msg.account_keys)
        try:
            i = keys.index(payer.pubkey())
        except ValueError:
            # иногда провайдер кладёт dummy-сигу на payer месте — всё равно можно поставить свою
            i = None
        sigs = list(vt.signatures)
        sig = payer.sign_message(to_bytes_versioned(msg))
        if i is not None:
            sigs[i] = sig
        else:
            # если место не найдено (редко), просто вставим/заменим первую
            if sigs:
                sigs[0] = sig
            else:
                sigs = [sig]
        vt.signatures = sigs
        return base64.b64encode(bytes(vt)).decode()

    def _build_tip_tx(payer: Keypair, tip_to: Pubkey, lamports: int, bh: Hash):
        ix = transfer(TransferParams(from_pubkey=payer.pubkey(), to_pubkey=tip_to, lamports=lamports))
        msg = MessageV0.try_compile(
            payer=payer.pubkey(),
            instructions=[ix],
            address_lookup_table_accounts=[],
            recent_blockhash=bh,
        )
        tip_tx = VersionedTransaction(msg, [payer])
        return base64.b64encode(bytes(tip_tx)).decode()

    # 0) ключи
    payer = Keypair.from_base58_string(payer_secret_b58)
    wallet_addr = str(payer.pubkey())

    # 1) строим swap
    unsigned_swap_b64 = _pumpfun_swap_tx(wallet_addr)

    # 2) подписываем swap
    signed_swap_b64 = _sign_base64_tx(unsigned_swap_b64, payer)

    # 3) готовим tip
    tip_to = Pubkey.from_string(_get_tip_account())
    tip_amt = _get_tip_amount_lamports()
    bh = _latest_blockhash()
    tip_b64 = _build_tip_tx(payer, tip_to, tip_amt, bh)

    # 4) отправляем бандл (порядок: сначала swap, потом tip — атомарно)
    params = [[signed_swap_b64, tip_b64]]
    if jito_region:
        params.append(jito_region)
    bundle_id = _rpc("sendBundle", params)

    out = {
        "bundle_id": bundle_id,
        "wallet": wallet_addr,
        "mint": mint,
        "spent_sol": sol_in_lamports / 1_000_000_000,
        "priority_fee_level": priority_fee_level,
        "tip_lamports": tip_amt,
        "tip_account": str(tip_to),
        "region": jito_region,
    }

    if return_bundle_status:
        # NB: необязательно; лишний вызов = +задержка
        status = _rpc("getInflightBundleStatuses", [[bundle_id]])
        out["bundle_status"] = status

    return out












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
                settings_obj = await sync_to_async(Settings.objects.first)()
                await buy_pumpfun_via_quicknode(
                        qn_http_url="https://wispy-little-river.solana-mainnet.quiknode.pro/134b4b837e97bb3711c20296010e32eff69ad1af",
                        payer_secret_b58=settings_obj.buyer_pubkey,
                        mint=mint,
                        sol_in_lamports=int(settings_obj.sol_amount * Decimal('1000000000')),  # 0.10 SOL
                        slippage_bps=int(settings_obj.slippage_percent * 100),
                        priority_fee_level="high",
                        jito_region="frankfurt",
                        tip_lamports=int(settings_obj.priority_fee_sol * Decimal('1000000000')),   #
                        return_bundle_status=False,
                    )

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