import json
import os
import sys
import asyncio
import re
import base64
import websockets
import aiohttp
import time
from typing import Optional, Dict, List, Set, Tuple
import base58
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import uvloop

# Solana
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.commitment_config import CommitmentLevel
from solana.rpc.async_api import AsyncClient

# Django
import django
from django.conf import settings
from asgiref.sync import sync_to_async

# Настройка путей и Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Settings, Twitter, UserDev

# Конфигурация
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
JITO_RPC_URL = "https://mainnet.block-engine.jito.wtf/api/v1/transactions"
FAST_RPC_URLS = [
    f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://api.mainnet-beta.solana.com"
]
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

# Регулярные выражения
COMMUNITY_ID_RE = re.compile(r"/communities/(\d+)", re.IGNORECASE)
INSTRUCTION_MINT_RE = re.compile(r"Program log: Instruction: (InitializeMint2|InitializeMint)", re.IGNORECASE)
PROGDATA_RE = re.compile(r"Program data:\s*([A-Za-z0-9+/=]+)")

# Глобальные объекты
http_session: Optional[aiohttp.ClientSession] = None
rpc_clients: List[AsyncClient] = []
executor = ThreadPoolExecutor(max_workers=20)

@dataclass
class AppSettings:
    buyer_pubkey: str
    sol_amount: float
    slippage_percent: float
    priority_fee_sol: float
    start: bool
    one_token_enabled: bool
    whitelist_enabled: bool
    ath_from: float
    total_trans_from: int

class FastSettingsCache:
    """Быстрый кэш настроек с автоматическим обновлением"""
    def __init__(self):
        self.settings = None
        self.last_update = 0
        self.update_interval = 2.0  # Обновление каждые 2 секунды
    
    async def get_settings(self):
        if not self.settings or time.time() - self.last_update > self.update_interval:
            await self._update_settings()
        return self.settings
    
    async def _update_settings(self):
        try:
            settings_obj = await sync_to_async(Settings.objects.first)()
            if settings_obj:
                self.settings = AppSettings(
                    buyer_pubkey=settings_obj.buyer_pubkey.strip(),
                    sol_amount=float(settings_obj.sol_amount),
                    slippage_percent=float(settings_obj.slippage_percent),
                    priority_fee_sol=float(settings_obj.priority_fee_sol),
                    start=settings_obj.start,
                    one_token_enabled=settings_obj.one_token_enabled,
                    whitelist_enabled=settings_obj.whitelist_enabled,
                    ath_from=float(settings_obj.ath_from),
                    total_trans_from=int(settings_obj.total_trans_from)
                )
                self.last_update = time.time()
        except Exception as e:
            print(f"Settings update error: {e}")

# Инициализация кэша
settings_cache = FastSettingsCache()

async def init_globals():
    """Инициализация глобальных объектов"""
    global http_session, rpc_clients
    
    http_session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=100, ssl=False, ttl_dns_cache=300),
        timeout=aiohttp.ClientTimeout(total=1.0, connect=0.3),
        headers={'User-Agent': 'Solana-Sniper/1.0'}
    )
    
    # Инициализация RPC клиентов
    for rpc_url in FAST_RPC_URLS:
        client = AsyncClient(rpc_url, timeout=6)
        rpc_clients.append(client)

async def close_globals():
    """Корректное закрытие глобальных объектов"""
    global http_session, rpc_clients
    
    if http_session:
        await http_session.close()
    
    for client in rpc_clients:
        await client.close()

def _read_borsh_string(buf: memoryview, off: int):
    """Читает Borsh строку из буфера"""
    if off + 4 > len(buf): 
        return None, off
    ln = int.from_bytes(buf[off:off+4], "little")
    off += 4
    if ln < 0 or off + ln > len(buf): 
        return None, off
    try:
        s = bytes(buf[off:off+ln]).decode("utf-8", "ignore")
    except Exception:
        s = ""
    off += ln
    return s, off

def _take_pk(buf: memoryview, off: int):
    """Читает публичный ключ из буфера"""
    if off + 32 > len(buf): 
        return None, off
    return base58.b58encode(bytes(buf[off:off+32])).decode(), off + 32

def parse_pump_create(raw: bytes):
    """Парсит данные создания токена PumpFun"""
    if not raw or len(raw) < 8: 
        return None
    
    mv = memoryview(raw)
    off = 8
    
    name, off = _read_borsh_string(mv, off)
    symbol, off = _read_borsh_string(mv, off)
    uri, off = _read_borsh_string(mv, off)
    mint, off = _take_pk(mv, off)
    bonding_curve, off = _take_pk(mv, off)
    creator, off = _take_pk(mv, off)
    
    return {
        "uri": uri,
        "mint": mint,
        "creator": creator,
    }

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
            out.extend(base64.b64decode(c, validate=True))
        except Exception:
            try:
                out.extend(base58.b58decode(c))
            except Exception:
                return None
    return bytes(out)

async def fetch_meta_fast(session: aiohttp.ClientSession, uri: str) -> Optional[Dict]:
    """Сверхбыстрая загрузка метаданных"""
    if not uri:
        return None
    
    try:
        async with session.get(uri, timeout=aiohttp.ClientTimeout(total=0.4)) as response:
            if response.status == 200:
                return await response.json()
    except Exception:
        pass
    return None

def find_community_anywhere(meta: Dict) -> Optional[str]:
    """Быстрый поиск community ID в метаданных"""
    if not meta:
        return None
    
    # Проверяем основные поля
    for field in ['twitter', 'x', 'external_url', 'website']:
        if field in meta:
            url = meta[field]
            if url and isinstance(url, str):
                match = COMMUNITY_ID_RE.search(url)
                if match:
                    return match.group(1)
    
    # Проверяем extensions
    if 'extensions' in meta and isinstance(meta['extensions'], dict):
        for field in ['twitter', 'x', 'website']:
            if field in meta['extensions']:
                url = meta['extensions'][field]
                if url and isinstance(url, str):
                    match = COMMUNITY_ID_RE.search(url)
                    if match:
                        return match.group(1)
    
    return None

async def get_creator_username_fast(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Сверхбыстрое получение username создателя"""
    if not community_id:
        return None
    
    endpoints = [
        f"/twitter/community/info?community_id={community_id}",
        f"/twitter/community/members?community_id={community_id}&limit=1"
    ]
    
    for endpoint in endpoints:
        try:
            async with session.get(
                f"https://api.twitterapi.io{endpoint}",
                headers={"X-API-Key": "8879aa53d815484ebea0313718172fea"},
                timeout=aiohttp.ClientTimeout(total=0.5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Парсим разные форматы ответов
                    user_data = None
                    if 'community_info' in data and 'creator' in data['community_info']:
                        user_data = data['community_info']['creator']
                    elif 'members' in data and data['members']:
                        user_data = data['members'][0]
                    elif 'data' in data and 'users' in data['data'] and data['data']['users']:
                        user_data = data['data']['users'][0]
                    
                    if user_data and isinstance(user_data, dict):
                        username = user_data.get('screen_name') or user_data.get('userName') or user_data.get('username')
                        if username:
                            return username
        except Exception:
            continue
    
    return None

async def check_twitter_whitelist_fast(twitter_name: str, creator: str) -> bool:
    """Сверхбыстрая проверка whitelist"""
    if not twitter_name:
        return False
    
    try:
        settings = await settings_cache.get_settings()
        if not settings or not settings.start:
            return False
        
        # Проверка one_token_enabled
        if settings.one_token_enabled:
            try:
                exists = await sync_to_async(UserDev.objects.filter(adress=creator).exists)()
                if exists:
                    return False
            except Exception:
                pass
        
        # Подготовка условий для быстрой проверки
        twitter_name_lower = f"@{twitter_name.lower().replace('@', '')}"
        
        # Быстрый запрос к базе
        if settings.whitelist_enabled:
            filters = {
                'name__iexact': twitter_name_lower,
                'whitelist': True,
                'ath__gte': settings.ath_from,
                'total_trans__gte': settings.total_trans_from
            }
        else:
            filters = {
                'name__iexact': twitter_name_lower,
                'ath__gte': settings.ath_from,
                'total_trans__gte': settings.total_trans_from
            }
        
        exists = await sync_to_async(Twitter.objects.filter(**filters).exists)()
        return exists
        
    except Exception as e:
        print(f"Whitelist check error: {e}")
        return False

async def buy_token(mint: str) -> bool:
    """Максимально быстрая покупка токена"""
    try:
        settings = await settings_cache.get_settings()
        if not settings:
            return False
        
        kp = Keypair.from_base58_string(settings.buyer_pubkey)
        
        # Подготовка payload для транзакции
        payload = {
            "publicKey": str(kp.pubkey()),
            "action": "buy",
            "mint": mint,
            "amount": settings.sol_amount,
            "denominatedInSol": True,
            "slippage": settings.slippage_percent,
            "priorityFee": settings.priority_fee_sol,
            "pool": "auto"
        }
        
        # Быстрое получение транзакции
        async with http_session.post(
            "https://pumpportal.fun/api/trade-local",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=1.5)
        ) as response:
            if response.status != 200:
                return False
            tx_data = await response.read()
        
        # Подписание транзакции
        vt = VersionedTransaction.from_bytes(tx_data)
        signed_tx = VersionedTransaction(vt.message, [kp])
        
        # Отправка через самый быстрый RPC
        send_config = RpcSendTransactionConfig(
            preflight_commitment=CommitmentLevel.Confirmed,
            skip_preflight=False
        )
        
        # Пробуем отправить через все RPC параллельно
        send_tasks = []
        for client in rpc_clients:
            task = asyncio.create_task(client.send_raw_transaction(signed_tx, send_config))
            send_tasks.append(task)
        
        # Ждем первый успешный ответ
        done, pending = await asyncio.wait(send_tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Отменяем остальные задачи
        for task in pending:
            task.cancel()
        
        # Проверяем результат
        for task in done:
            try:
                result = await task
                if hasattr(result, 'value') and result.value:
                    print(f"Successfully bought {mint}")
                    return True
            except Exception:
                continue
        
        return False
        
    except Exception as e:
        print(f"Buy error for {mint}: {e}")
        return False

async def process_message_ultrafast(msg: dict):
    """Ультрабыстрая обработка сообщения со всеми проверками параллельно"""
    try:
        logs = msg.get("params", {}).get("result", {}).get("value", {}).get("logs", [])
        if not any(INSTRUCTION_MINT_RE.search(log) for log in logs):
            return
        
        # Парсим данные токена
        data = collect_progdata_bytes_after_create(logs)
        parsed = parse_pump_create(data or b"")
        if not parsed:
            return
        
        mint = (parsed.get("mint") or "").strip()
        uri = (parsed.get("uri") or "").strip()
        creator = (parsed.get("creator") or "").strip()
        
        if not mint or not uri:
            return
        
        # Параллельно выполняем все проверки
        meta_task = asyncio.create_task(fetch_meta_fast(http_session, uri))
        community_id_task = asyncio.create_task(asyncio.to_thread(find_community_anywhere, await meta_task))
        
        # Ждем community_id
        community_id = await community_id_task
        if not community_id:
            return
        
        # Параллельно получаем username и проверяем настройки
        username_task = asyncio.create_task(get_creator_username_fast(http_session, community_id))
        whitelist_task = asyncio.create_task(check_twitter_whitelist_fast(await username_task, creator))
        
        # Ждем результат проверки
        is_whitelisted = await whitelist_task
        if not is_whitelisted:
            return
        
        # Если все проверки пройдены - покупаем
        print(f"🚀 Buying {mint} from @{await username_task}")
        await buy_token(mint)
        
    except Exception as e:
        print(f"Process message error: {e}")

async def main_loop():
    """Основной ultra-fast цикл"""
    await init_globals()
    
    # WebSocket подписка
    logs_sub = json.dumps({
        "jsonrpc": "2.0",
        "id": "ultra-fast-sniper",
        "method": "logsSubscribe",
        "params": [
            {"mentions": [PUMP_FUN_PROGRAM]},
            {"commitment": "processed"}
        ]
    })
    
    while True:
        try:
            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=10,
                max_size=2**18,
                compression=None
            ) as ws:
                await ws.send(logs_sub)
                await ws.recv()  # Ждем подтверждения подписки
                
                async for message in ws:
                    # Обрабатываем сообщения параллельно без ожидания
                    asyncio.create_task(process_message_ultrafast(json.loads(message)))
                    
        except Exception as e:
            print(f"WebSocket error: {e}")
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    # Установка uvloop для максимальной производительности
    uvloop.install()
    
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Stopping sniper...")
    finally:
        asyncio.run(close_globals())