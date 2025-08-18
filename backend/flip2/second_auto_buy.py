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
# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Settings, Twitter
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
INSTRUCTION_CREATE_RE = re.compile(r"instruction.*create", re.IGNORECASE)
FAILED_ERROR_RE = re.compile(r"(failed:|custom program error)", re.IGNORECASE)
PROGDATA_RE = re.compile(r"Program data:\s*([A-Za-z0-9+/=]+)")

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
    print(f"buy: {mint}")
    try:
        settings_obj = await sync_to_async(Settings.objects.first)()
        if not settings_obj:
            return
            
        payload = {
            "publicKey": settings_obj.buyer_pubkey,
            "action": "buy",
            "mint": mint,
            "amount": float(settings_obj.sol_amount),
            "denominatedInSol": "true",
            "slippage": float(settings_obj.slippage_percent),
            "priorityFee": float(settings_obj.priority_fee_sol),
            "pool": "pump"
        }
        
        r = requests.post(PUMPPORTAL_TRADE_LOCAL,
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(payload),
                        timeout=1)  # Минимальный timeout
    except Exception:
        pass

async def check_twitter_whitelist(twitter_name):
    """Проверка Twitter в whitelist"""
    try:
        settings_obj = await sync_to_async(Settings.objects.first)()
        filter_ath = settings_obj.filter_ath if settings_obj else 0
        
        twitter_obj = await sync_to_async(
            Twitter.objects.filter(
                whitelist=True,
                name=f"@{twitter_name}",
                ath__gt=filter_ath
            ).first
        )()
        
        return twitter_obj is not None
    except Exception:
        return False

async def get_creator_username(session, community_id):
    """Получение username создателя сообщества"""
    if community_id in COMMUNITY_CACHE:
        return COMMUNITY_CACHE[community_id]
    
    try:
        async with session.get(
            f"{TW_BASE}/twitter/community/info",
            headers=TW_HEADERS,
            params={"community_id": community_id},
            timeout=0.5  # Уменьшенный timeout
        ) as r:
            data = await r.json()
            creator = (data.get("community_info", {}) or {}).get("creator", {})
            username = creator.get("screen_name") or creator.get("username")
            if username:
                COMMUNITY_CACHE[community_id] = username
                return username
    except Exception:
        pass
    
    return None

def collect_progdata_bytes_after_create(logs):
    """Собирает байты данных программы после инструкции Create"""
    if not logs:
        return None
    
    # Ищем строку с Program data
    for line in logs:
        if not isinstance(line, str):
            continue
        if "Program data:" in line:
            # Извлекаем base64 данные
            match = PROGDATA_RE.search(line)
            if match:
                try:
                    return base64.b64decode(match.group(1))
                except:
                    continue
    return None

def parse_pump_create(raw: bytes):
    """Парсит данные создания токена PumpFun"""
    if not raw or len(raw) < 44:  # Минимальный размер для mint address
        return None
    
    try:
        # Mint address - последние 32 байта
        mint = base58.b58encode(raw[-32:]).decode()
        
        # URI обычно находится в начале данных
        # Эвристический поиск URI - ищем http или ipfs
        uri = ""
        for prefix in [b"http://", b"https://", b"ipfs://"]:
            pos = raw.find(prefix)
            if pos != -1:
                end = raw.find(b"\x00", pos)
                uri = raw[pos:end if end != -1 else None].decode('utf-8', errors='ignore')
                break
        
        return {
            "mint": mint,
            "uri": uri,
            "symbol": "",  # Эти поля не используются в вашей логике
            "name": ""
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def find_community_from_uri(uri: str) -> Optional[str]:
    """Ищет community ID в URI"""
    if not uri:
        return None
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



async def process_message(msg, session):
    """Обработка входящего сообщения"""
    try:
        logs = msg.get("params", {}).get("result", {}).get("value", {}).get("logs", [])
        if not any(INSTRUCTION_CREATE_RE.search(log) for log in logs):
            return
        data = collect_progdata_bytes_after_create(logs)
        parsed = parse_pump_create(data or b"")
        if not parsed:
            return
        mint = (parsed["mint"] or "").strip()
        uri = (parsed["uri"] or "").strip()
        with open('test555.json', 'a') as f:
            f.write(json.dump(msg))
        if not mint:
            return
        
        # Поиск community_id
        community_id = find_community_from_uri(uri)
        if not community_id:
            meta = await fetch_meta_with_retries(session, uri)
            if meta:
                community_url, community_id, _ = find_community_anywhere_with_src(meta)
        
        if community_id:
            twitter_name = await get_creator_username(session, community_id)
            if twitter_name and await check_twitter_whitelist(twitter_name):
                await buy(mint)
            else:
                print(f"not_buy:{twitter,mint}")
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
            settings_obj = await sync_to_async(Settings.objects.first)()
            if not settings_obj or not settings_obj.start:
                await asyncio.sleep(1)
                continue
                
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