import requests
import time
from datetime import datetime

SOLSCAN_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"  # Замени на свой API-ключ Solscan

def get_max_market_cap(token_address: str) -> float:
    headers = {
        "token": SOLSCAN_API_KEY,
    }
    created_time = 0
    # 1. Получаем Total Supply токена
    meta_url = f"https://pro-api.solscan.io/v2.0/token/meta?address={token_address}"
    try:
        meta_response = requests.get(meta_url, headers=headers)
        meta_data = meta_response.json()
        
        if not meta_data.get("success", False):
            print(f"Ошибка при получении метаданных: {meta_data.get('message')}")
            return -1
        total_supply = float(meta_data["data"]["supply"])
        decimals = int(meta_data["data"]["decimals"])
        created_timestamp = int(meta_data["data"]['created_time'])
        created_time = datetime.fromtimestamp(created_timestamp).strftime('%Y%m%d')
        adjusted_total_supply = total_supply / (10 ** decimals)  # Учитываем decimals (например, для 9 decimals: 1e9)
        
    except Exception as e:
        print(f"Ошибка при получении Total Supply: {e}")
        return -1
    
    # 2. Получаем исторические цены (максимально возможный период)
    current_time = datetime.now().strftime('%Y%m%d')
    price_url = f"https://pro-api.solscan.io/v2.0/token/price?address={token_address}&from_time={created_time}&to_time={current_time}"
    print(price_url)
    try:
        price_response = requests.get(price_url, headers=headers)
        price_data = price_response.json()
        print(price_data)
        if not price_data.get("success", False):
            print(f"Ошибка при получении исторических цен: {price_data.get('message')}")
            return -1
        
        prices = price_data["data"]
        if not prices:
            print("Нет исторических данных о цене")
            return -1
        
        max_price = max(float(item["price"]) for item in prices)
        
    except Exception as e:
        print(f"Ошибка при получении исторических цен: {e}")
        return -1
    
    # 3. Вычисляем максимальный MarketCap
    max_market_cap = max_price * 1000000000
    return max_market_cap

# Пример использования
if __name__ == "__main__":
    token_address = "86QefU9ahoSvsq128b9phHrkzREBM9jmx3HtdFKTbonk"  # SOL
    max_mcap = get_max_market_cap(token_address)
    if max_mcap != -1:
        print(f"Максимальный MarketCap токена: ${max_mcap:,.2f}")
    else:
        print("Не удалось получить данные.")