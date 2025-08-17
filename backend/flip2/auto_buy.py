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
                 slippage_percent: float = 10.0,
                 priority_fee_sol: float = 0.00005,
                 pool: str = "pump") -> bytes:
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

async def buy(mint):
    """Функция автоматической покупки токена"""
    if not SOLDERS_AVAILABLE:
        print(f"❌ Cannot buy {mint}: solders library not available")
        return
    
    try:
        # Получаем настройки из базы данных
        settings_obj = await sync_to_async(Settings.objects.first)()
        if not settings_obj:
            print(f"❌ Cannot buy {mint}: no settings found")
            return
            
        buyer_pubkey = settings_obj.buyer_pubkey
        sol_amount = float(settings_obj.sol_amount)
        slippage_percent = float(settings_obj.slippage_percent)
        priority_fee_sol = float(settings_obj.priority_fee_sol)
        filter_ath = settings_obj.filter_ath
        
        # Проверяем, что у нас есть все необходимые параметры
        if not buyer_pubkey or sol_amount <= 0:
            print(f"❌ Cannot buy {mint}: invalid buyer_pubkey or sol_amount")
            return
            
        print(f"🚀 BUYING: {mint}")
        print(f"   Buyer: {buyer_pubkey}")
        print(f"   Amount: {sol_amount} SOL")
        print(f"   Slippage: {slippage_percent}%")
        print(f"   Priority Fee: {priority_fee_sol} SOL")
        
        # Строим транзакцию покупки
        tx_bytes = build_buy_tx(
            mint=mint,
            buyer_pubkey=buyer_pubkey,
            sol_amount=sol_amount,
            slippage_percent=slippage_percent,
            priority_fee_sol=priority_fee_sol,
            pool="pump"  # используем pump pool по умолчанию
        )
        
        # Отправляем транзакцию
        sig = send_vt_via_helius(tx_bytes, None, HELIUS_HTTP)
        print(f"✅ Transaction sent successfully: {sig}")
        print(f"   View: https://solscan.io/tx/{sig}")
        
    except Exception as e:
        print(f"❌ Error buying {mint}: {str(e)}")

# state - используем более быстрые структуры данных
SEEN_SIGS: set = set()
SEEN_MINTS: set = set()
COMMUNITY_CACHE: Dict[str, Optional[str]] = {}
WHITELIST_CACHE: Dict[str, bool] = {}  # Кэш для whitelist проверок

# Предкомпилированные регулярные выражения для максимальной скорости
COMMUNITY_ID_RE = re.compile(r"/communities/(\d+)", re.IGNORECASE)
INSTRUCTION_CREATE_RE = re.compile(r"instruction.*create", re.IGNORECASE)
FAILED_ERROR_RE = re.compile(r"(failed:|custom program error)", re.IGNORECASE)
URI_COMMUNITY_RE = re.compile(r"(uri|community)", re.IGNORECASE)
PROGDATA_RE = re.compile(r"Program data:\s*([A-Za-z0-9+/=]+)")
SOLANA_ADDRESS_RE = re.compile(r'[1-9A-HJ-NP-Za-km-z]{44}')

# Кэш для быстрого доступа
LOGS_SUB_JSON = jdumps({
    "jsonrpc": "2.0",
    "id": "logs-auto-buy",
    "method": "logsSubscribe",
    "params": [
        {"mentions": [PUMP_FUN]},
        {"commitment": "processed"}
    ]
})

# Исключенные адреса для быстрой проверки
EXCLUDED_ADDRESSES = frozenset({
    "11111111111111111111111111111111",  # System Program
    "So11111111111111111111111111111111111111112",  # Wrapped SOL
    PUMP_FUN  # PumpFun program
})

# IPFS gateways для загрузки метаданных
IPFS_GATEWAYS = [
    "https://cloudflare-ipfs.com/ipfs/",
    "https://ipfs.io/ipfs/",
    "https://gateway.pinata.cloud/ipfs/",
]

# Кэш метаданных
URI_META_CACHE: dict[str, dict] = {}

# ================= WebSocket subscription =================
def build_logs_sub() -> str:
    return LOGS_SUB_JSON

def unpack_logs_notification(msg):
    params = msg.get("params") or {}
    res    = params.get("result") or {}
    value  = res.get("value") or {}
    ctx    = res.get("context") or {}
    logs   = value.get("logs") or res.get("logs") or []
    sig    = value.get("signature") or res.get("signature")
    slot   = ctx.get("slot") or res.get("slot")
    return logs, sig, slot

# ================= Log filters =================
def looks_like_create(logs: List[str]) -> bool:
    """Оптимизированная проверка на create инструкцию"""
    return any(INSTRUCTION_CREATE_RE.search(log) for log in logs)

def has_error(logs: List[str]) -> bool:
    """Оптимизированная проверка на ошибки"""
    return any(FAILED_ERROR_RE.search(log) for log in logs)

# ================= Program data parsing =================
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
                out += b58decode(c)
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
    return b58encode(bytes(buf[off:off+32])).decode(), off + 32

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
        "name": name or "", "symbol": symbol or "", "uri": uri or "",
        "mint": mint or "", "bondingCurve": bonding_curve or "", "creator": creator or "",
        "decimals": 6,
    }

# ================= Community helpers =================
def _ensure_scheme(url: str) -> str:
    """Добавляет схему к URL если её нет"""
    u = url.strip()
    if not u.lower().startswith(("http://","https://")) and ".com/" in u:
        u = "https://" + u.lstrip("/")
    return u

def canonicalize_community_url(url_or_id: str) -> tuple[str|None, str|None]:
    """Нормализует URL community и извлекает ID"""
    s = (url_or_id or "").strip()
    if not s:
        return None, None
    if s.isdigit():
        return f"https://x.com/i/communities/{s}", s
    u = _ensure_scheme(s)
    m = COMMUNITY_ID_RE.search(u)
    if not m:
        return None, None
    cid = m.group(1)
    return f"https://x.com/i/communities/{cid}", cid

def _strings_in_json(obj):
    """Рекурсивно извлекает все строки из JSON объекта"""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings_in_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings_in_json(v)

def find_community_anywhere_with_src(meta_json: dict) -> tuple[str|None, str|None, str|None]:
    """Ищет community ID в метаданных везде (оптимизированная версия)"""
    # Приоритетные поля для быстрого поиска
    priority_keys = ("twitter", "x", "external_url", "website")
    
    # Сначала проверяем приоритетные поля
    for key in priority_keys:
        v = meta_json.get(key)
        if isinstance(v, str) and v.strip():
            url, cid = canonicalize_community_url(v)
            if cid:
                return url, cid, key
    
    # Проверяем extensions
    ex = meta_json.get("extensions")
    if isinstance(ex, dict):
        for key in priority_keys:
            v = ex.get(key)
            if isinstance(v, str) and v.strip():
                url, cid = canonicalize_community_url(v)
                if cid:
                    return url, cid, f"extensions.{key}"
    
    # Последний resort - рекурсивный поиск (только если не нашли в приоритетных местах)
    for s in _strings_in_json(meta_json):
        url, cid = canonicalize_community_url(s)
        if cid:
            return url, cid, "anywhere"
    
    return None, None, None

# ================= Metadata fetching =================
def normalize_uri_candidates(u: str) -> list[str]:
    """Нормализует URI для загрузки метаданных"""
    if not u: return []
    u = u.strip(); low = u.lower()
    if low.startswith(("http://","https://")): return [u]
    if low.startswith("ipfs://"):
        path = u[7:]
        if path.startswith("ipfs/"): path = path[5:]
        return [g + path for g in IPFS_GATEWAYS[:2]]  # Используем только 2 gateway для скорости
    if low.startswith("ar://"):
        path = u[5:]
        return [f"https://arweave.net/{path}"]
    return [f"https://{u.lstrip('/')}"]

async def fetch_json_once(session: aiohttp.ClientSession, url: str, timeout_ms: int) -> dict | None:
    """Загружает JSON с одного URL"""
    try:
        to = aiohttp.ClientTimeout(total=timeout_ms/1000)
        async with session.get(url, timeout=to) as r:
            b = await r.read()
            if not b: return None
            return jloads(b)
    except Exception:
        return None

async def fetch_meta_with_retries(session: aiohttp.ClientSession, uri: str) -> dict | None:
    """Загружает метаданные с параллельными запросами для максимальной скорости"""
    if uri in URI_META_CACHE:
        return URI_META_CACHE[uri]
    
    urls = normalize_uri_candidates(uri)
    if not urls:
        return None
    
    # Создаем задачи для параллельного выполнения
    tasks = [asyncio.create_task(fetch_json_once(session, url, 800)) for url in urls]
    
    try:
        # Ждем первый успешный результат
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Отменяем оставшиеся задачи
        for task in pending:
            task.cancel()
        
        # Проверяем результаты
        for task in done:
            try:
                result = task.result()
                if isinstance(result, dict):
                    URI_META_CACHE[uri] = result
                    return result
            except:
                continue
                
    except:
        pass
    
    return None

def find_community_id_fast(logs: List[str]) -> Optional[str]:
    """Быстрый поиск community ID в логах"""
    for log in logs:
        if URI_COMMUNITY_RE.search(log):
            match = COMMUNITY_ID_RE.search(log)
            if match:
                return match.group(1)
    return None

def find_community_from_uri(uri: str) -> Optional[str]:
    """Ищет community ID в URI"""
    if not uri:
        return None
    match = COMMUNITY_ID_RE.search(uri)
    return match.group(1) if match else None

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

async def check_twitter_whitelist(twitter_name: str) -> bool:
    
    try:
        # Получаем настройки для фильтрации
        settings_obj = await sync_to_async(Settings.objects.first)()
        filter_ath = settings_obj.filter_ath if settings_obj else 0
        
        # Ищем Twitter с whitelist=True, указанным именем и ath больше filter_ath
        twitter_obj = await sync_to_async(lambda: Twitter.objects.filter(
            whitelist=True, 
            name=twitter_name,
            ath__gt=filter_ath
        ).first())()
    
        result = twitter_obj is not None
        
        return result
        
    except Exception as e:
        print(f"Error checking whitelist: {e}")
        # Кэшируем ошибку как False
        WHITELIST_CACHE[twitter_name] = False
        return False

async def get_creator_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Получает username с несколькими попытками и fallback методами"""
    if community_id in COMMUNITY_CACHE:
        return COMMUNITY_CACHE[community_id]
    
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
                    COMMUNITY_CACHE[community_id] = u
                    return u
            except:
                continue
                
    except:
        pass
    
    COMMUNITY_CACHE[community_id] = None
    return None

# ===================== MAIN LOOP =====================
async def main():
    # Максимально оптимизированные настройки соединения
    tcp = aiohttp.TCPConnector(
        limit=100,  # Увеличиваем лимит соединений
        ttl_dns_cache=300,
        use_dns_cache=True,
        keepalive_timeout=30,
        enable_cleanup_closed=True,
        force_close=False
    )
    
    headers = {"User-Agent": "auto-buy/5.0-ultra-fastest"}
    
    # Предварительно создаем сессию для переиспользования
    session = None
    
    while True:
        try:
            if session is None:
                session = aiohttp.ClientSession(connector=tcp, headers=headers)
            
            async with websockets.connect(
                WS_URL, 
                ping_interval=60,  # Увеличиваем ping интервал
                ping_timeout=30,
                max_size=2**20,
                compression=None,
                close_timeout=5,
                open_timeout=10
            ) as ws:
                
                await ws.send(LOGS_SUB_JSON)
                await ws.recv()

                async for raw in ws:
                    try:
                        # Быстрый парсинг JSON
                        msg = jloads(raw)
                        if msg.get("method") != "logsNotification":
                            continue
                        settings_obj = await sync_to_async(Settings.objects.first)()
                        if (settings_obj.start is None):
                            time.sleep(60)
                            continue
                        logs, sig, _slot = unpack_logs_notification(msg)
                        if not sig or sig in SEEN_SIGS:
                            continue

                        # ---- фильтры ----
                        # минимально строгие условия: есть Create, нет явной ошибки
                        if not (looks_like_create(logs) and not has_error(logs)):
                            continue

                        # Парсим данные из блока Create
                        data = collect_progdata_bytes_after_create(logs)
                        parsed = parse_pump_create(data or b"")
                        if not parsed:
                            continue

                        uri  = (parsed["uri"] or "").strip()
                        mint = (parsed["mint"] or "").strip()
                        sym  = (parsed["symbol"] or "").strip()

                        if not mint or mint in SEEN_MINTS:
                            continue
                        if not sym:
                            continue

                        # помечаем после всех фильтров
                        SEEN_SIGS.add(sig)
                        SEEN_MINTS.add(mint)

                        # Ищем community ID в URI и метаданных
                        community_id = None
                        
                        # Сначала ищем в URI (самый быстрый способ)
                        if uri:
                            community_id = find_community_from_uri(uri)
                        
                        # Если не нашли в URI, загружаем метаданные и ищем там
                        if not community_id and uri:
                            meta = await fetch_meta_with_retries(session, uri)
                            if isinstance(meta, dict):
                                community_url, community_id, community_src = find_community_anywhere_with_src(meta)
                        
                        # Если не нашли в метаданных, ищем в логах
                        if not community_id:
                            community_id = find_community_id_fast(logs)
                        
                        # Получаем Twitter username только если есть community_id
                        if community_id:
                            twitter_name = await get_creator_username(session, community_id)
                            if twitter_name:
                                print(f"{mint} | @{twitter_name}")
                                
                                # Проверяем whitelist в базе данных
                                is_whitelisted = await check_twitter_whitelist(twitter_name)
                                if is_whitelisted:
                                    # Вызываем функцию buy для whitelist Twitter
                                    await buy(mint)  # price=0 для примера, можно изменить

                    except Exception:
                        continue

        except Exception:
            await asyncio.sleep(0.05)  # Уменьшаем время ожидания еще больше
        finally:
            if session:
                await session.close()
                session = None

if __name__ == "__main__":
    asyncio.run(main()) 