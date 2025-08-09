import asyncio
import json
import websockets
from typing import Dict, Any

HELIUS_API_KEY = "d25e743a-6bf4-4ff2-a939-08767d664564"
WS_URL = f"wss://atlas-mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
BONK_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

async def process_and_print(signature: str, tx_data: Dict[str, Any]):
    print(f"New TokenMint detected: {signature}")
    print("Transaction details:", json.dumps(tx_data, indent=2))

async def subscribe_to_mints():
    retry_delay = 1
    max_retry_delay = 60
    while True:
        try:
            async with websockets.connect(WS_URL) as websocket:
                retry_delay = 1  # Reset delay after successful connection
                subscribe_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "transactionSubscribe",
                    "params": [
                        {
                            "accountInclude": [BONK_PROGRAM],
                            "requiredEvents": ["TokenMint"]  # Фильтр по событию
                        },
                        {
                            "commitment": "processed",
                            "encoding": "jsonParsed",  # Расширенный формат
                            "maxSupportedTransactionVersion": 0
                        }
                    ]
                }
                await websocket.send(json.dumps(subscribe_payload))

                # Обработка ping/pong
                asyncio.create_task(send_ping(websocket))

                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        if data.get("method") == "transactionNotification":
                            tx = data["params"]["result"]["transaction"]
                            signature = tx["signature"]
                            if any(ix.get("program") == "spl-token" and ix["parsed"]["type"] == "mint" 
                                   for ix in tx["message"]["instructions"]):
                                await process_and_print(signature, tx)
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        continue

        except Exception as e:
            print(f"Connection failed, retrying in {retry_delay}s: {e}")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)  # Экспоненциальный backoff

async def send_ping(websocket):
    while True:
        try:
            await websocket.ping()
            await asyncio.sleep(30)  # Ping каждые 30 секунд
        except:
            break

asyncio.run(subscribe_to_mints())