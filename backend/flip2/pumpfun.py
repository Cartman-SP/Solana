import asyncio
import websockets
import json
import requests
import base64
import struct
import base58

# Твой Helius API key
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"  # Pump.fun program ID

LOCAL_WS_URL = "ws://localhost:9393"


async def subscribe_to_mints():
    while True:
        try:
            async with websockets.connect(WS_URL) as websocket:
                subscribe_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [{"mentions": [PUMP_PROGRAM]}, {"commitment": "processed"}]
                }
                await websocket.send(json.dumps(subscribe_payload))

                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        if 'params' in data and 'result' in data['params']:
                            logs = data['params']['result']['value']['logs']
                            signature = data['params']['result']['value']['signature']
                            if any("Program log: Instruction: Create" in log for log in logs):
                                asyncio.create_task(process_and_print(signature))
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except:
                        continue
                        
        except:
            await asyncio.sleep(5)


async def process_and_print(signature, retry_count=0):
    max_retries = 5
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": "grok-tx",
            "method": "getTransaction",
            "params": [signature,
                       {"encoding": "jsonParsed", "commitment": "confirmed", "maxSupportedTransactionVersion": 0}]
        }
        response = requests.post(RPC_URL, json=payload)
        response.raise_for_status()
        tx_data = response.json().get('result')
        if tx_data:
            log_messages = tx_data['meta']['logMessages']
            event_log = None
            for log in log_messages:
                if 'mint' in log and 'user' in log:
                    try:
                        start = log.find('{')
                        end = log.rfind('}') + 1
                        event_str = log[start:end]
                        event_log = json.loads(event_str)
                        break
                    except:
                        continue
            if event_log:
                await send_to_local_websocket(event_log)
                return
            else:
                program_data = None
                for log in log_messages:
                    if 'Program data: ' in log:
                        program_data = log.split('Program data: ')[1].strip()
                        break
                if program_data:
                    try:
                        decoded_data = base64.b64decode(program_data)
                        offset = 0
                        discriminator = decoded_data[offset:offset + 8].hex()
                        offset += 8
                        name_len = struct.unpack_from('<I', decoded_data, offset)[0]
                        offset += 4
                        name = decoded_data[offset:offset + name_len].decode('utf-8').rstrip('\x00')
                        offset += name_len
                        symbol_len = struct.unpack_from('<I', decoded_data, offset)[0]
                        offset += 4
                        symbol = decoded_data[offset:offset + symbol_len].decode('utf-8').rstrip('\x00')
                        offset += symbol_len
                        uri_len = struct.unpack_from('<I', decoded_data, offset)[0]
                        offset += 4
                        uri = decoded_data[offset:offset + uri_len].decode('utf-8').rstrip('\x00')
                        offset += uri_len
                        mint_bytes = decoded_data[offset:offset + 32]
                        mint = base58.b58encode(mint_bytes).decode('utf-8')
                        offset += 32
                        bonding_curve_bytes = decoded_data[offset:offset + 32]
                        offset += 32
                        associated_bonding_curve_bytes = decoded_data[offset:offset + 32]
                        offset += 32
                        user_bytes = decoded_data[offset:offset + 32]
                        user = base58.b58encode(user_bytes).decode('utf-8')
                        
                        parsed_data = {
                            "source": "pumpfun",
                            "mint": mint,
                            "user": user,
                            "name": name,
                            "symbol": symbol,
                            "uri": uri
                        }
                        await send_to_local_websocket(parsed_data)
                        return
                    except Exception as e:
                        print(f"Error parsing program data for {signature}: {e}")
                        if retry_count < max_retries:
                            print(f"Retrying... Attempt {retry_count + 1}/{max_retries}")
                            await asyncio.sleep(0.5)  # Пауза 500ms перед повторной попыткой
                            # Создаем новую задачу вместо блокирующего вызова
                            asyncio.create_task(process_and_print(signature, retry_count + 1))
                        else:
                            print(f"Max retries reached for {signature}")
                        pass
    except Exception as e:
        print(f"Error processing transaction {signature}: {e}")
        if retry_count < max_retries:
            print(f"Retrying... Attempt {retry_count + 1}/{max_retries}")
            await asyncio.sleep(0.5)  # Пауза 500ms перед повторной попыткой
            # Создаем новую задачу вместо блокирующего вызова
            asyncio.create_task(process_and_print(signature, retry_count + 1))
        else:
            print(f"Max retries reached for {signature}")
        pass


async def send_to_local_websocket(data):
    try:
        async with websockets.connect(LOCAL_WS_URL, timeout=5) as websocket:
            await websocket.send(json.dumps(data))
    except:
        pass


# Запуск
asyncio.run(subscribe_to_mints())
