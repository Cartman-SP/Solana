import requests
import json
import aiohttp
import asyncio

# Конфигурация
HELIUS_API_KEY = "5bce1ed6-a93a-4392-bac8-c42190249194"  # Замените на ваш ключ Helius
WALLET_ADDRESS = "CYzNY4LcuptSpr18oPR9qykNBkajYaaW1K5muy4i3VLQ"  # Адрес кошелька, баланс которого проверяем

# URL Helius RPC (можно mainnet/devnet/testnet)
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

def get_sol_balance(wallet_address):
    """Получаем баланс SOL (нативный баланс кошелька)"""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "getBalance",
        "params": [wallet_address],
    }
    
    try:
        response = requests.post(HELIUS_RPC_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["result"]["value"] / 10**9  # Конвертируем lamports → SOL
    except Exception as e:
        print(f"Ошибка при получении баланса SOL: {e}")
        return None

async def get_sol_balance_async(wallet_address):
    """Асинхронная версия функции получения баланса SOL"""
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "getBalance",
        "params": [wallet_address],
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HELIUS_RPC_URL, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data["result"]["value"] / 10**9  # Конвертируем lamports → SOL
    except Exception as e:
        print(f"Ошибка при получении баланса SOL: {e}")
        return None

def get_all_tokens(wallet_address):
    """Получаем все токены (SPL + NFT)"""
    tokens = []
    page = 1
    
    while True:
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": wallet_address,
                "page": page,
                "limit": 1000,  # Максимальный лимит для одного запроса
            },
        }
        
        try:
            response = requests.post(HELIUS_RPC_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("result", {}).get("items"):
                break  # Больше нет токенов
            
            tokens.extend(data["result"]["items"])
            page += 1
        except Exception as e:
            print(f"Ошибка при получении токенов: {e}")
            break
    
    return tokens

