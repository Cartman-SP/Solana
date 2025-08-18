import json
import os
import sys
import django
import asyncio
import aiohttp
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from typing import Dict, List, Optional, Tuple
import time

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token
from asgiref.sync import sync_to_async

API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjcmVhdGVkQXQiOjE3NTM1NzAxNzU2MjEsImVtYWlsIjoiZGFuaWlsLnNoaXJraW4wMDVAZ21haWwuY29tIiwiYWN0aW9uIjoidG9rZW4tYXBpIiwiYXBpVmVyc2lvbiI6InYyIiwiaWF0IjoxNzUzNTcwMTc1fQ.W2-ic8rt8wQZptdygjc6F3Z5N8CJv1UrCkfqzdwq2vw"

# Кэши для оптимизации
migration_cache: Dict[str, bool] = {}
ath_cache: Dict[str, int] = {}

# Контроль лимитов API
API_RATE_LIMIT = 1000  # запросов в минуту
REQUEST_SEMAPHORE = asyncio.Semaphore(API_RATE_LIMIT)  # Семафор для контроля запросов
CANCEL_PROCESSING = False  # Флаг для отмены обработки


class APIError(Exception):
    """Исключение для ошибок API"""
    pass


async def make_api_request(session: aiohttp.ClientSession, url: str, headers: dict) -> dict:
    """Выполняет API запрос с контролем лимитов"""
    global CANCEL_PROCESSING
    
    if CANCEL_PROCESSING:
        raise APIError("Обработка отменена из-за ошибок API")
    
    async with REQUEST_SEMAPHORE:
        try:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 429:  # Rate limit exceeded
                    CANCEL_PROCESSING = True
                    raise APIError("Превышен лимит API запросов")
                elif response.status == 403:  # Forbidden
                    CANCEL_PROCESSING = True
                    raise APIError("Ошибка авторизации API")
                elif response.status != 200:
                    raise APIError(f"API ошибка: {response.status}")
                
                return await response.json()
                
        except asyncio.TimeoutError:
            raise APIError("Таймаут API запроса")
        except Exception as e:
            if "429" in str(e) or "403" in str(e):
                CANCEL_PROCESSING = True
            raise APIError(f"Ошибка API запроса: {e}")


async def fetch_activities_page(
    session: aiohttp.ClientSession,
    token_address: str,
    page: int,
    activity_type: str = "ACTIVITY_TOKEN_SWAP",
) -> List[dict]:
    """Возвращает список активностей для конкретной страницы."""
    base_url = "https://pro-api.solscan.io/v2.0/account/defi/activities"
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0",
    }
    url = (
        f"{base_url}?address={token_address}&page={page}&page_size=100&activity_type[]={activity_type}"
    )
    data = await make_api_request(session, url, headers)
    return data.get("data", []) or []


def extract_tx_values(activities: List[dict], token_address: str) -> List[float]:
    """Извлекает изменения баланса из активностей для расчета ATH."""
    values: List[float] = []
    for tx in activities:
        try:
            routers = tx.get("routers", {})
            sell = routers.get("token1") == token_address
            change = tx.get("value", 0)
            if sell:
                change = -change
            if change != 0:
                values.append(float(change))
        except Exception:
            continue
    return values


async def get_ath_values_and_total_count(
    token_address: str, session: aiohttp.ClientSession
) -> Tuple[List[float], int]:
    """Возвращает:
    - список транзакций только из 1-2 страниц для расчёта ATH
    - total_trans по правилам:
      1) page1<100 -> total=page1
      2) page1=100, page2<100 -> total=100+page2
      3) page1=100, page2=100 -> проверяем page5:
         - page5 пустая -> total=300
         - page5<100 -> total=400+page5
         - page5=100 -> total=600
    """
    # Страница 1
    page1 = await fetch_activities_page(session, token_address, 1)
    len1 = len(page1)
    values_for_ath: List[float] = extract_tx_values(page1, token_address)

    if len1 < 100:
        return values_for_ath, len1

    # Страница 2
    page2 = await fetch_activities_page(session, token_address, 2)
    len2 = len(page2)
    values_for_ath.extend(extract_tx_values(page2, token_address))

    if len2 < 100:
        return values_for_ath, 100 + len2

    # Страница 5 по заданным правилам
    page5 = await fetch_activities_page(session, token_address, 5)
    len5 = len(page5)
    if len5 == 0:
        return values_for_ath, 300
    if len5 < 100:
        return values_for_ath, 400 + len5
    return values_for_ath, 600


async def check_migration_async(token_address: str, session: aiohttp.ClientSession) -> bool:
    """Проверяет миграцию токена"""
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
    
    url = f"{base_url}?address={token_address}&page=1&page_size=100&activity_type[]=ACTIVITY_POOL_CREATE"
    
    try:
        data = await make_api_request(session, url, headers)
        activities = data.get('data', [])
        
        # Проверяем активности
        for activity in activities:
            from_address = activity.get('from_address', '')
            if from_address in target_addresses:
                migration_cache[token_address] = True
                return True
                
    except APIError as e:
        print(f"Ошибка при проверке миграции для {token_address}: {e}")
        raise
    except Exception as e:
        print(f"Неожиданная ошибка при проверке миграции для {token_address}: {e}")
    
    migration_cache[token_address] = False
    return False


async def get_token_transactions_async(token_address: str, session: aiohttp.ClientSession) -> List[float]:
    """Получает транзакции токена асинхронно"""
    base_url = "https://pro-api.solscan.io/v2.0/account/defi/activities"
    
    headers = {
        "token": API_KEY,
        "User-Agent": "SolanaFlipper/1.0"
    }
    
    all_transactions = []
    
    # Получаем первые 2 страницы (200 транзакций)
    for page in range(1, 3):
        url = f"{base_url}?address={token_address}&page={page}&page_size=100&activity_type[]=ACTIVITY_TOKEN_SWAP"
        
        try:
            data = await make_api_request(session, url, headers)
            transactions = data.get('data', [])
            
            if not transactions:
                break
            
            for tx in transactions:
                try:
                    routers = tx.get('routers', {})
                    sell = routers.get('token1') == token_address
                    change = tx.get('value', 0)
                    
                    if sell:
                        change = -change
                    
                    if change != 0:
                        all_transactions.append(float(change))
                except Exception:
                    continue
                    
        except APIError as e:
            print(f"Ошибка при получении транзакций для {token_address}: {e}")
            raise
        except Exception as e:
            print(f"Неожиданная ошибка при получении транзакций для {token_address}: {e}")
            break
    
    return all_transactions


async def calculate_ath_async(token_address: str, session: aiohttp.ClientSession) -> int:
    """Рассчитывает ATH для токена по транзакциям 1-2 страниц."""
    if token_address in ath_cache:
        return ath_cache[token_address]

    try:
        values_for_ath, _ = await get_ath_values_and_total_count(token_address, session)

        if not values_for_ath:
            ath_cache[token_address] = 0
            return 0

        initial_balance = 0
        current_balance = initial_balance
        max_balance = initial_balance

        # Обрабатываем транзакции в обратном порядке для оптимизации
        for value in reversed(values_for_ath):
            current_balance += value
            if current_balance > max_balance:
                max_balance = current_balance

        # Кэшируем результат
        ath_cache[token_address] = int(max_balance)
        return int(max_balance)

    except APIError as e:
        print(f"Ошибка при расчете ATH для {token_address}: {e}")
        raise
    except Exception as e:
        print(f"Неожиданная ошибка при расчете ATH для {token_address}: {e}")
        ath_cache[token_address] = 0
        return 0


async def process_token_complete(token_address: str, session: aiohttp.ClientSession) -> tuple:
    """Полная обработка токена: проверка миграции, расчёт ATH (стр. 1-2) и вычисление total_trans."""
    try:
        # Сначала проверяем миграцию
        is_migrated = await check_migration_async(token_address, session)
        if is_migrated:
            # Для мигрировавших используем специальное значение ATH и не считаем total_trans
            return 60000, is_migrated, 1000
        else:
            values_for_ath, total_count = await get_ath_values_and_total_count(token_address, session)

            # Расчёт ATH из значений первых 1-2 страниц
            initial_balance = 0
            current_balance = initial_balance
            max_balance = initial_balance
            for value in reversed(values_for_ath):
                current_balance += value
                if current_balance > max_balance:
                    max_balance = current_balance

            ath_value = int(max_balance)
            ath_cache[token_address] = ath_value
            return ath_value, is_migrated, total_count

    except APIError as e:
        print(f"API ошибка при полной обработке токена {token_address}: {e}")
        raise
    except Exception as e:
        print(f"Неожиданная ошибка при полной обработке токена {token_address}: {e}")
        return 0, False, 0


async def get_tokens_for_processing():
    """Получает токены для обработки согласно критериям"""
    # Время 60 минут назад - используем UTC время
    sixty_minutes_ago = timezone.now() - timedelta(minutes=10)
    print(sixty_minutes_ago)
    # Получаем токены с ATH = 0, созданные больше 60 минут назад
    # и у которых UserDev не в черном списке и имеет не больше 300 токенов
    tokens = await sync_to_async(list)(
        Token.objects.filter(
            ath=0,
            processed = False,
            created_at__lt=sixty_minutes_ago,
        ).select_related('dev')[:100]
    )
    print(len(tokens))
    return tokens


async def process_token_ath(token, session: aiohttp.ClientSession):
    """Обрабатывает ATH для одного токена"""
    try:
        # Получаем ATH, статус миграции и total_trans
        ath_result, is_migrated, total_trans = await process_token_complete(token.address, session)
        
        # Обновляем токен только если не было ошибок API
        await sync_to_async(lambda: setattr(token, 'ath', ath_result))()
        await sync_to_async(lambda: setattr(token, 'migrated', is_migrated))()
        await sync_to_async(lambda: setattr(token, 'total_trans', total_trans))()
        await sync_to_async(lambda: setattr(token, 'processed', True))()

        # Сохраняем изменения
        await sync_to_async(token.save)()
        
        print(f"Обработан токен {token.address}: ATH = {token.ath}, migrated = {token.migrated}, total_trans = {token.total_trans}")
        
    except APIError as e:
        print(f"API ошибка при обработке токена {token.address}: {e}")
        raise
    except Exception as e:
        print(f"Неожиданная ошибка при обработке токена {token.address}: {e}")


async def process_tokens_batch():
    """Обрабатывает партию токенов параллельно"""
    global CANCEL_PROCESSING
    
    # Сбрасываем флаг отмены
    CANCEL_PROCESSING = False
    
    tokens = await get_tokens_for_processing()
    
    if not tokens:
        print("Нет токенов для обработки")
        return 0
    
    print(f"Найдено {len(tokens)} токенов для обработки")
    
    # Создаем сессию для переиспользования соединений
    async with aiohttp.ClientSession() as session:
        try:
            # Создаем задачи для параллельной обработки
            tasks = [process_token_ath(token, session) for token in tokens]
            
            # Выполняем все задачи параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Проверяем результаты на ошибки
            api_errors = [r for r in results if isinstance(r, APIError)]
            if api_errors:
                print(f"Обнаружены {len(api_errors)} API ошибок. Отмена обработки.")
                CANCEL_PROCESSING = True
                return 0
            
            # Подсчитываем успешно обработанные токены
            successful = len([r for r in results if r is None])
            print(f"Успешно обработано {successful} токенов из {len(tokens)}")
            
            return successful
            
        except Exception as e:
            print(f"Критическая ошибка в batch обработке: {e}")
            CANCEL_PROCESSING = True
            return 0


async def main_processing_loop():
    """Основной бесконечный цикл обработки токенов"""
    print("Запуск основного цикла обработки токенов...")
    
    while True:
        try:
            processed_count = await process_tokens_batch()
            
            if processed_count == 0:
                if CANCEL_PROCESSING:
                    print("Обработка отменена из-за ошибок API. Ожидание 5 минут...")
                    await asyncio.sleep(15)  # 5 минут при ошибках
                else:
                    print("Нет токенов для обработки. Ожидание 5 минут...")
                    await asyncio.sleep(15)  # 5 минут
            else:
                print(f"Обработано {processed_count} токенов. Ожидание 1 минуту...")
                
        except Exception as e:
            print(f"Ошибка в основном цикле: {e}")
            await asyncio.sleep(60)  # Ждем минуту при ошибке


if __name__ == "__main__":
    # Запускаем основной цикл
    asyncio.run(main_processing_loop())


