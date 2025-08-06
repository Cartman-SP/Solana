import asyncio
import websockets
import json
import requests
import base58
import struct

HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"
WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
PUMP_PROGRAM = "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"
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
                            if any("Program log: Instruction: InitializeMint2" in log for log in logs 
                                   or "Program log: Instruction: InitializeMint" in log for log in logs):
                                asyncio.create_task(process_and_print(signature))
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except:
                        continue
                        
        except:
            await asyncio.sleep(5)

def extract_useful_data(tx_data):
    useful_data = {}
    
    for inner_instruction in tx_data['meta']['innerInstructions']:
        for instruction in inner_instruction['instructions']:
            if 'parsed' in instruction:
                parsed = instruction['parsed']
                
                if parsed['type'] == 'initializeMint2':
                    useful_data['Mint'] = parsed['info']['mint']
                
                elif parsed['type'] == 'transfer':
                    if parsed['info']['source'] == 'GyiAMVLuUq2n4bqxhhjzr2ZasnHXZ3b1jJiU5YbB4HJL':
                        useful_data['User (dev)'] = parsed['info']['source']
    
    if 'User (dev)' not in useful_data:
        useful_data['User (dev)'] = tx_data['transaction']['message']['accountKeys'][0]['pubkey']
    
    try:
        inner_instructions = tx_data['meta']['innerInstructions']
        instruction_data = None
        
        for group in inner_instructions:
            if group['index'] == 2:
                instructions = group['instructions']
                
                if len(instructions) >= 8:
                    target_instruction = instructions[7]
                    data_str = target_instruction['data']
                    account_keys = tx_data['transaction']['message']['accountKeys']
                    
                    program_id = None
                    if 'programIdIndex' in target_instruction:
                        program_index = target_instruction['programIdIndex']
                        program_id = account_keys[program_index]
                    elif 'programId' in target_instruction:
                        program_id = target_instruction['programId']
                    
                    if program_id == 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj':
                        try:
                            data_bytes = base58.b58decode(data_str)
                            instruction_data = data_bytes.hex()
                        except:
                            break
                break

        if instruction_data:
            data_bytes = bytes.fromhex(instruction_data)

            pool_state_bytes = data_bytes[0:32]
            pool_state = base58.b58encode(pool_state_bytes).decode('utf-8')
            useful_data['Pool State'] = pool_state

            creator_bytes = data_bytes[32:64]
            creator = base58.b58encode(creator_bytes).decode('utf-8')
            useful_data['Creator'] = creator

            config_bytes = data_bytes[64:96]
            config = base58.b58encode(config_bytes).decode('utf-8')
            useful_data['Config'] = config

            curve_param_size = 16
            decimals_start = 96 + curve_param_size
            decimals = data_bytes[decimals_start]
            useful_data['Decimals'] = decimals

            name_length_start = decimals_start + 1
            name_length = struct.unpack('<I', data_bytes[name_length_start:name_length_start + 4])[0]
            name_start = name_length_start + 4
            name_end = name_start + name_length
            name = data_bytes[name_start:name_end].decode('utf-8')
            useful_data['Token Name'] = name

            symbol_length_start = name_end
            symbol_length = struct.unpack('<I', data_bytes[symbol_length_start:symbol_length_start + 4])[0]
            symbol_start = symbol_length_start + 4
            symbol_end = symbol_start + symbol_length
            symbol = data_bytes[symbol_start:symbol_end].decode('utf-8')
            useful_data['Token Symbol'] = symbol

            uri_length_start = symbol_end
            uri_length = struct.unpack('<I', data_bytes[uri_length_start:uri_length_start + 4])[0]
            uri_start = uri_length_start + 4
            uri_end = uri_start + uri_length
            uri = data_bytes[uri_start:uri_end].decode('utf-8')
            useful_data['Token URI'] = uri

    except:
        pass
    
    return useful_data

async def process_and_print(signature):
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
            useful_data = extract_useful_data(tx_data)

            bonk_data = {
                "source": "bonk",
                "mint": useful_data.get('Mint', 'N/A'),
                "user": useful_data.get('User (dev)', 'N/A'),
                "name": useful_data.get('Token Name', 'N/A'),
                "symbol": useful_data.get('Token Symbol', 'N/A'),
                "uri": useful_data.get('Token URI', 'N/A')
            }
            await send_to_local_websocket(bonk_data)
    except:
        pass

async def send_to_local_websocket(data):
    try:
        async with websockets.connect(LOCAL_WS_URL, timeout=5) as websocket:
            await websocket.send(json.dumps(data))
    except:
        pass

asyncio.run(subscribe_to_mints())