import asyncio
import websockets
import json
import base64
import struct
import base58

HELIUS_API_KEY = "d25e743a-6bf4-4ff2-a939-08767d664564"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
LOCAL_WS_URL = "ws://localhost:9393"


def parse_create_instruction(program_data: str) -> dict:
    """Парсит данные инструкции Create из Pump.fun"""
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
        return parsed_data
    except Exception as e:
        with open("errors.txt", "a", encoding="utf-8") as f:
            f.write(f"{str(e)}\n")
            f.write('\n',program_data,'\n')
        print(e)
        return None


async def send_to_local_websocket(data: dict):
    """Отправляет данные в локальный WebSocket"""
    try:
        async with websockets.connect(LOCAL_WS_URL, timeout=5) as websocket:
            await websocket.send(json.dumps(data))
    except:
        pass


async def process_logs(logs: list):
    """Обрабатывает логи и извлекает данные Create инструкции"""
    has_create_instruction = False
    program_data = None
    for log in logs:

        if "Program log: Instruction: Create" in log:
            has_create_instruction = True
        elif 'Program data: ' in log:
            program_data = log.split('Program data: ')[1].strip()
            break
    if has_create_instruction and program_data:
        parsed_data = parse_create_instruction(program_data)
        if parsed_data:
            await send_to_local_websocket(parsed_data)


async def subscribe_to_mints():
    """Подписывается на логи Pump.fun программы"""
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
                        with open("errors.txt", "a", encoding="utf-8") as f:
                            f.write(f"{str(data)}\n")
                        if 'params' in data and 'result' in data['params']:
                            logs = data['params']['result']['value']['logs']
                            await process_logs(logs)

                    except websockets.exceptions.ConnectionClosed:
                        break
                    except:
                        continue
                        
        except:
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(subscribe_to_mints())
