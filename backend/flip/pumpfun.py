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
        


        data = {
            'source': 'pumpfun',
            'mint': mint,
            'user': creator,
            'name': name,
            'symbol': symbol,
            'bonding_curve':bonding_curve,
            'uri': uri
        }
        asyncio.create_task(process_live(data))
        
        
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
                            print(e)
                            continue
            except Exception as e:
                print(e)
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