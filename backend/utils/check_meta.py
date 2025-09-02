import requests
import json
import base64

# Ваш API-ключ Helius и базовый URL
api_key = "5bce1ed6-a93a-4392-bac8-c42190249194"  # Замените на ваш действительный API-ключ
base_url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"

# Адрес токена
mint_address = "7TxUwewguuGAcEcJ3Qv2K5zCaWSbXXLo9tHh6YRypump"

def try_multiple_endpoints():
    """
    Попробуем несколько различных эндпоинтов и методов для получения информации о токене.
    """
    methods_to_try = [
        ("getAsset", {"id": mint_address, "options": {"showFungible": True}}),
        ("getAssetProof", {"pubkey_str": mint_address}),
        ("getTokenAccounts", {"mint": mint_address}),
        ("getAccountInfo", {"pubkey_str": mint_address, "encoding": "jsonParsed"}),
        ("getAccountInfo", {"pubkey_str": mint_address, "encoding": "base64"}),  # Для сырых данных
        ("getTokenMetadata", {"pubkey_str": mint_address}),  # Если поддерживается
    ]
    
    results = {}
    
    for method, params in methods_to_try:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": params,
        }
        
        response = requests.post(base_url, json=payload, timeout=30)
        data = response.json()
        print(f"\n{method}\n {data}\n\n")
try_multiple_endpoints()