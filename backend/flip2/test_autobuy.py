import json
import os
import sys
import asyncio
import re
import base64
import logging
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

# ГЛОБАЛЬНОЕ ЛОГИРОВАНИЕ
# - Переменная окружения AUTO_BUY_LOG_LEVEL управляет уровнем (DEBUG/INFO/WARNING/ERROR)
# - По умолчанию DEBUG для максимальной отладки
logger = logging.getLogger("test_autobuy")
if not logger.handlers:
    level_name = os.getenv("AUTO_BUY_LOG_LEVEL", "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)

def _mask_secret(value: Optional[str], visible_start: int = 4, visible_end: int = 4) -> str:
    """Маскирует секретное значение (например, ключ/адрес)."""
    if not value:
        return ""
    if len(value) <= visible_start + visible_end:
        return "***"
    return f"{value[:visible_start]}...{value[-visible_end:]}"

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
        now = time.time()
        if not self.settings:
            logger.debug("Настройки отсутствуют в кэше — выполняю загрузку")
        if not self.settings or now - self.last_update > self.update_interval:
            logger.debug("Обновляю настройки (прошло %.3fs)", now - self.last_update)
            await self._update_settings()
        else:
            logger.debug("Настройки из кэша (обновлено %.3fs назад)", now - self.last_update)
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
                logger.debug(
                    "Загружены настройки: start=%s, one_token=%s, whitelist=%s, ath_from=%.4f, total_trans_from=%s, sol_amount=%.6f, slippage=%.2f, fee=%.8f, buyer_pubkey=%s",
                    self.settings.start,
                    self.settings.one_token_enabled,
                    self.settings.whitelist_enabled,
                    self.settings.ath_from,
                    self.settings.total_trans_from,
                    self.settings.sol_amount,
                    self.settings.slippage_percent,
                    self.settings.priority_fee_sol,
                    _mask_secret(self.settings.buyer_pubkey),
                )
        except Exception as e:
            logger.exception("Ошибка обновления настроек: %s", e)

# Инициализация кэша
settings_cache = FastSettingsCache()

async def init_globals():
    """Инициализация глобальных объектов"""
    global http_session, rpc_clients
    
    logger.info("Инициализация HTTP сессии и RPC клиентов")
    http_session = aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=100, ssl=False, ttl_dns_cache=300),
        timeout=aiohttp.ClientTimeout(total=1.0, connect=0.3),
        headers={'User-Agent': 'Solana-Sniper/1.0'}
    )
    logger.debug("HTTP сессия создана (limit=100, ssl=False, ttl_dns_cache=300, total=1.0, connect=0.3)")
    
    # Инициализация RPC клиентов
    for rpc_url in FAST_RPC_URLS:
        client = AsyncClient(rpc_url, timeout=6)
        rpc_clients.append(client)
    logger.debug("Инициализировано %d RPC клиентов: %s", len(rpc_clients), FAST_RPC_URLS)

async def close_globals():
    """Корректное закрытие глобальных объектов"""
    global http_session, rpc_clients
    
    logger.info("Закрываю глобальные объекты")
    if http_session:
        await http_session.close()
        logger.debug("HTTP сессия закрыта")
    
    for idx, client in enumerate(rpc_clients):
        await client.close()
        logger.debug("RPC клиент #%d закрыт", idx)

def _read_borsh_string(buf: memoryview, off: int):
    """Читает Borsh строку из буфера"""
    if off + 4 > len(buf): 
        logger.debug("Borsh: недостаточно данных для чтения длины (off=%d, len=%d)", off, len(buf))
        return None, off
    ln = int.from_bytes(buf[off:off+4], "little")
    off += 4
    if ln < 0 or off + ln > len(buf): 
        logger.debug("Borsh: некорректная длина ln=%d (off=%d, len=%d)", ln, off, len(buf))
        return None, off
    try:
        s = bytes(buf[off:off+ln]).decode("utf-8", "ignore")
    except Exception:
        s = ""
    off += ln
    logger.debug("Borsh: строка прочитана len=%d, off->%d, preview=%s", ln, off, (s[:32] + ('...' if len(s) > 32 else '')))
    return s, off

def _take_pk(buf: memoryview, off: int):
    """Читает публичный ключ из буфера"""
    if off + 32 > len(buf): 
        logger.debug("PK: недостаточно данных (off=%d, len=%d)", off, len(buf))
        return None, off
    pk = base58.b58encode(bytes(buf[off:off+32])).decode()
    logger.debug("PK прочитан: %s", _mask_secret(pk))
    return pk, off + 32

def parse_pump_create(raw: bytes):
    """Парсит данные создания токена PumpFun"""
    if not raw or len(raw) < 8: 
        logger.debug("parse_pump_create: пустой/короткий payload (%s)", 0 if not raw else len(raw))
        return None
    
    mv = memoryview(raw)
    off = 8
    
    name, off = _read_borsh_string(mv, off)
    symbol, off = _read_borsh_string(mv, off)
    uri, off = _read_borsh_string(mv, off)
    mint, off = _take_pk(mv, off)
    bonding_curve, off = _take_pk(mv, off)
    creator, off = _take_pk(mv, off)
    
    result = {
        "uri": uri,
        "mint": mint,
        "creator": creator,
    }
    logger.debug(
        "parse_pump_create: name=%s, symbol=%s, uri=%s, mint=%s, creator=%s",
        (name or "")[:16],
        (symbol or "")[:16],
        (uri or "")[:64] + ("..." if uri and len(uri) > 64 else ""),
        _mask_secret(mint),
        _mask_secret(creator),
    )
    return result

def collect_progdata_bytes_after_create(logs):
    """Собирает байты данных программы после инструкции Create"""
    chunks, after = [], False
    for line in logs:
        low = str(line).lower()
        if "instruction" in low and "create" in low:
            after = True
            logger.debug("Instruction Create обнаружена: %s", str(line)[:160])
            continue
        if not after:
            continue
        m = PROGDATA_RE.search(str(line))
        if m:
            chunks.append(m.group(1))
        elif chunks:
            break
    
    if not chunks:
        logger.debug("collect_progdata: не найдено Program data после Create")
        return None

    out = bytearray()
    for c in chunks:
        try:
            out.extend(base64.b64decode(c, validate=True))
        except Exception:
            try:
                out.extend(base58.b58decode(c))
            except Exception:
                logger.debug("collect_progdata: не удалось декодировать chunk")
                return None
    payload = bytes(out)
    logger.debug("collect_progdata: собрано %d байт из %d chunk(ов)", len(payload), len(chunks))
    return payload

async def fetch_meta_fast(session: aiohttp.ClientSession, uri: str) -> Optional[Dict]:
    """Сверхбыстрая загрузка метаданных"""
    if not uri:
        logger.debug("fetch_meta_fast: пустой URI")
        return None
    
    try:
        t0 = time.monotonic()
        async with session.get(uri, timeout=aiohttp.ClientTimeout(total=0.4)) as response:
            if response.status == 200:
                data = await response.json()
                logger.debug("fetch_meta_fast OK (%0.1f ms): %s", (time.monotonic() - t0) * 1000, uri)
                return data
            else:
                logger.debug("fetch_meta_fast HTTP %s: %s", response.status, uri)
    except Exception as e:
        logger.exception("fetch_meta_fast error для %s: %s", uri, e)
    return None

def find_community_anywhere(meta: Dict) -> Optional[str]:
    """Быстрый поиск community ID в метаданных"""
    if not meta:
        logger.debug("find_community_anywhere: meta пуст")
        return None
    
    # Проверяем основные поля
    for field in ['twitter', 'x', 'external_url', 'website']:
        if field in meta:
            url = meta[field]
            if url and isinstance(url, str):
                match = COMMUNITY_ID_RE.search(url)
                if match:
                    logger.debug("Найден community_id в '%s': %s", field, match.group(1))
                    return match.group(1)
    
    # Проверяем extensions
    if 'extensions' in meta and isinstance(meta['extensions'], dict):
        for field in ['twitter', 'x', 'website']:
            if field in meta['extensions']:
                url = meta['extensions'][field]
                if url and isinstance(url, str):
                    match = COMMUNITY_ID_RE.search(url)
                    if match:
                        logger.debug("Найден community_id в extensions['%s']: %s", field, match.group(1))
                        return match.group(1)
    
    logger.debug("find_community_anywhere: community_id не найден")
    return None

async def get_creator_username_fast(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
    """Сверхбыстрое получение username создателя"""
    if not community_id:
        logger.debug("get_creator_username_fast: пустой community_id")
        return None
    
    endpoints = [
        f"/twitter/community/info?community_id={community_id}",
        f"/twitter/community/members?community_id={community_id}&limit=1"
    ]
    
    for endpoint in endpoints:
        try:
            t0 = time.monotonic()
            async with session.get(
                f"https://api.twitterapi.io{endpoint}",
                headers={"X-API-Key": "8879aa53d815484ebea0313718172fea"},
                timeout=aiohttp.ClientTimeout(total=0.5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug("twitterapi OK %s (%0.1f ms)", endpoint, (time.monotonic() - t0) * 1000)
                    
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
                            logger.debug("Получен username: @%s", username)
                            return username
                else:
                    logger.debug("twitterapi HTTP %s %s", response.status, endpoint)
        except Exception:
            logger.exception("twitterapi исключение для %s", endpoint)
            continue
    
    return None

async def check_twitter_whitelist_fast(twitter_name: str, creator: str) -> bool:
    """Сверхбыстрая проверка whitelist"""
    if not twitter_name:
        logger.debug("Whitelist: пустое имя Twitter")
        return False
    
    try:
        settings = await settings_cache.get_settings()
        if not settings or not settings.start:
            logger.debug("Whitelist: нет настроек или старт выключен")
            return False
        
        # Проверка one_token_enabled
        if settings.one_token_enabled:
            try:
                exists = await sync_to_async(UserDev.objects.filter(adress=creator, total_tokens__gt=1).exists)()
                if exists:
                    logger.debug("Whitelist: creator %s уже покупался (one_token) — отклонено", _mask_secret(creator))
                    return False
            except Exception:
                logger.exception("Whitelist: ошибка one_token_enabled проверки")
        
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
        
        logger.debug("Whitelist: фильтры %s", filters)
        exists = await sync_to_async(Twitter.objects.filter(**filters).exists)()
        logger.debug("Whitelist: результат exists=%s для %s", exists, twitter_name_lower)
        return exists
        
    except Exception as e:
        logger.exception("Whitelist check error: %s", e)
        return False

async def buy_token(mint: str) -> bool:
    """Максимально быстрая покупка токена"""
    try:
        settings = await settings_cache.get_settings()
        if not settings:
            logger.debug("buy_token: настройки недоступны")
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
        logger.debug("buy_token payload: %s", {**payload, "mint": _mask_secret(mint)})
        
        # Быстрое получение транзакции
        t0 = time.monotonic()
        async with http_session.post(
            "https://pumpportal.fun/api/trade-local",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=1.5)
        ) as response:
            if response.status != 200:
                logger.debug("trade-local HTTP %s", response.status)
                return False
            tx_data = await response.read()
        logger.debug("trade-local: получено %d байт за %.1f ms", len(tx_data), (time.monotonic() - t0) * 1000)
        
        # Подписание транзакции
        vt = VersionedTransaction.from_bytes(tx_data)
        signed_tx = VersionedTransaction(vt.message, [kp])
        logger.debug("Подписано signatures=%d", len(signed_tx.signatures))
        
        # Отправка через самый быстрый RPC
        send_config = RpcSendTransactionConfig(
            preflight_commitment=CommitmentLevel.Confirmed,
            skip_preflight=False
        )
        
        # Пробуем отправить через все RPC параллельно
        send_tasks = []
        task_to_url = {}
        for idx, client in enumerate(rpc_clients):
            url = FAST_RPC_URLS[idx] if idx < limage.pngen(FAST_RPC_URLS) else f"rpc[{idx}]"
            task = asyncio.create_task(client.send_raw_transaction(signed_tx, send_config))
            send_tasks.append(task)
            task_to_url[task] = url
            logger.debug("Отправка транзакции через RPC #%d: %s", idx, url)
        
        # Ждем первый успешный ответ
        done, pending = await asyncio.wait(send_tasks, return_when=asyncio.FIRST_COMPLETED)
        
        # Отменяем остальные задачи
        for task in pending:
            task.cancel()
            logger.debug("Отмена отправки для %s", task_to_url.get(task, "<unknown>"))
        
        # Проверяем результат
        for task in done:
            try:
                result = await task
                if hasattr(result, 'value') and result.value:
                    logger.info("Успешная отправка через %s: %s", task_to_url.get(task, "<unknown>"), str(result.value)[:64])
                    print(f"Successfully bought {mint}")
                    return True
            except Exception:
                logger.exception("Ошибка отправки через %s", task_to_url.get(task, "<unknown>"))
                continue
        
        logger.warning("Не удалось отправить транзакцию для mint=%s", _mask_secret(mint))
        return False
        
    except Exception as e:
        logger.exception("Buy error for %s: %s", _mask_secret(mint), e)
        print(f"Buy error for {mint}: {e}")
        return False

async def process_message_ultrafast(msg: dict):
    """Ультрабыстрая обработка сообщения со всеми проверками параллельно"""
    try:
        logs = msg.get("params", {}).get("result", {}).get("value", {}).get("logs", [])
        logger.debug("Получено сообщение: %d строк логов", len(logs))
        if not any(INSTRUCTION_MINT_RE.search(log) for log in logs):
            logger.debug("В логах нет InitializeMint/InitializeMint2 — пропуск")
            return
        
        # Парсим данные токена
        data = collect_progdata_bytes_after_create(logs)
        parsed = parse_pump_create(data or b"")
        if not parsed:
            logger.debug("Данные токена не распознаны — пропуск")
            return
        
        mint = (parsed.get("mint") or "").strip()
        uri = (parsed.get("uri") or "").strip()
        creator = (parsed.get("creator") or "").strip()
        logger.debug("Parsed mint=%s, uri=%s, creator=%s", _mask_secret(mint), uri, _mask_secret(creator))
        
        if not mint or not uri:
            logger.debug("Отсутствует mint или uri — пропуск")
            return
        
        # Параллельно выполняем все проверки
        meta_task = asyncio.create_task(fetch_meta_fast(http_session, uri))
        meta = await meta_task
        community_id_task = asyncio.create_task(asyncio.to_thread(find_community_anywhere, meta))
        
        # Ждем community_id
        community_id = await community_id_task
        if not community_id:
            logger.debug("Community ID не найден — пропуск")
            return
        
        # Параллельно получаем username и проверяем настройки
        username_task = asyncio.create_task(get_creator_username_fast(http_session, community_id))
        username = await username_task
        logger.debug("Username для community %s: @%s", community_id, username)
        whitelist_task = asyncio.create_task(check_twitter_whitelist_fast(username, creator))
        
        # Ждем результат проверки
        is_whitelisted = await whitelist_task
        if not is_whitelisted:
            logger.debug("@%s не прошёл whitelist — пропуск", username)
            return
        
        # Если все проверки пройдены - покупаем
        logger.info("Покупка: mint=%s, creator=%s, username=@%s", _mask_secret(mint), _mask_secret(creator), username)
        print(f"🚀 Buying {mint} from @{username}")
        await buy_token(mint)
        
    except Exception as e:
        logger.exception("Process message error: %s", e)
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
            logger.info("Открываю WebSocket соединение: %s", WS_URL)
            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=10,
                max_size=2**18,
                compression=None
            ) as ws:
                await ws.send(logs_sub)
                ack = await ws.recv()  # Ждем подтверждения подписки
                logger.info("Подписка подтверждена: %s", str(ack)[:200])
                
                async for message in ws:
                    # Обрабатываем сообщения параллельно без ожидания
                    logger.debug("WS message: %d bytes", len(message))
                    asyncio.create_task(process_message_ultrafast(json.loads(message)))
                    
        except Exception as e:
            logger.exception("WebSocket error: %s", e)
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