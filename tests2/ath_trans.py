import requests
import aiohttp
import asyncio
from typing import Dict, List, Optional
import time

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"

# Кэш для ATH значений
ath_cache: Dict[str, int] = {}



async def check_migration_async_fast(token_address: str, session: aiohttp.ClientSession, max_pages: int = 3) -> bool:
    """Быстрая асинхронная версия с переиспользованием сессии через Pro API"""
    if token_address in migration_cache:
        return migration_cache[token_address]
    
    base_url = "https://pro-api.solscan.io/v2.0/account/defi/activities"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    target_addresses = [
        "RAYpQbFNq9i3mu6cKpTKKRwwHFDeK5AuZz8xvxUrCgw",
        "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"
    ]
    
    for page in range(1, max_pages + 1):
        url = f"{base_url}?address={token_address}&page={page}&page_size=100&activity_type=ACTIVITY_POOL_CREATE&activity_type=ACTIVITY_POOL_CREATE"
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    activities = data.get('data', [])
                    
                    if not activities:
                        break
                    
                    # Проверяем активности
                    for activity in activities:
                        from_address = activity.get('from_address', '')
                        if from_address in target_addresses:
                            migration_cache[token_address] = True
                            return True
                else:
                    break
                    
        except Exception:
            break
    
    migration_cache[token_address] = False
    return False




def get_token_transactions_optimized(token_address: str, max_pages: int = 2) -> List[float]:
    """Оптимизированная функция получения транзакций токена"""
    base_url = "https://pro-api.solscan.io/v2.0/account/defi/activities"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    all_transactions = []
    
    # Используем сессию для переиспользования соединений
    with requests.Session() as session:
        session.headers.update(headers)
        
        for page in range(1, max_pages + 1):
            url = f"{base_url}?address={token_address}&page={page}&page_size=100&activity_type[]=ACTIVITY_TOKEN_SWAP"

            try:
                response = session.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    transactions = data.get('data', [])
                    
                    if not transactions:
                        break
                    
                    page_transactions_count = 0
                    for tx in transactions:
                        try:
                            routers = tx.get('routers', {})
                            sell = routers.get('token1') == token_address
                            change = tx.get('value', 0)
                            
                            if sell:
                                change = -change
                            
                            if change != 0:
                                all_transactions.append(float(change))
                                page_transactions_count += 1
                        except Exception:
                            continue
                    
                    # Если на странице меньше 100 транзакций, значит это последняя страница
                    if page_transactions_count < 100:
                        break
                else:
                    break
                    
            except Exception:
                break
    
    return all_transactions

def count_ath(TOKEN_ADDRESS: str) -> int:
    """Оптимизированная функция подсчета ATH"""
    # Проверяем кэш
    if TOKEN_ADDRESS in ath_cache:
        return ath_cache[TOKEN_ADDRESS]
    
    try:
        transactions = get_token_transactions_optimized(TOKEN_ADDRESS, max_pages=3)
        
        if not transactions:
            ath_cache[TOKEN_ADDRESS] = 0
            return 0
            
        initial_balance = 0
        current_balance = initial_balance
        max_balance = initial_balance
        
        # Обрабатываем транзакции в обратном порядке для оптимизации
        for value in reversed(transactions):
            current_balance += value        
            if current_balance > max_balance:
                max_balance = current_balance
        
        # Кэшируем результат
        ath_cache[TOKEN_ADDRESS] = int(max_balance)
        return int(max_balance)
        
    except Exception:
        ath_cache[TOKEN_ADDRESS] = 0
        return 0

# Асинхронная версия для параллельной обработки
async def count_ath_async(token_address: str) -> int:
    """Асинхронная версия count_ath"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, count_ath, token_address)

