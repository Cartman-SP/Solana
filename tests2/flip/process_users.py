import asyncio
import django
import os
import sys
from asgiref.sync import sync_to_async
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import time
from typing import Dict, List, Tuple, Optional
import logging

# Настройка Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from mainapp.models import UserDev, Token
from author_tokens import get_all_tokens_by_address_async
from ath_trans import count_ath
from get_migration import check_migration_async
from performance_monitor import monitor
from load_monitor import load_monitor, monitor_load_periodically

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфигурация производительности
MAX_CONCURRENT_USERS = 50  # Увеличено до 50 пользователей одновременно
MAX_CONCURRENT_TOKENS = 100  # Увеличено с 50 до 100
MAX_CONCURRENT_REQUESTS = 500  # Увеличено для поддержки 50 пользователей
BATCH_SIZE = 50  # Размер батча для bulk операций
CACHE_SIZE = 1000  # Размер кэша для токенов

# Глобальные кэши
token_cache: Dict[str, dict] = {}
ath_cache: Dict[str, int] = {}
migration_cache: Dict[str, bool] = {}

class TokenProcessor:
    """Класс для оптимизированной обработки токенов"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.executor = ThreadPoolExecutor(max_workers=50)  # Увеличено для поддержки 50 пользователей
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=MAX_CONCURRENT_REQUESTS,
            limit_per_host=100,  # Увеличено для поддержки большего количества запросов
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,  # Увеличено время keepalive
            enable_cleanup_closed=True  # Автоматическая очистка закрытых соединений
        )
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "SolanaFlipper/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        self.executor.shutdown(wait=False)
    
    async def get_cached_ath(self, token_address: str) -> int:
        """Получение ATH с кэшированием"""
        if token_address in ath_cache:
            return ath_cache[token_address]
        
        async with self.semaphore:
            try:
                monitor.start_request()
                loop = asyncio.get_event_loop()
                ath_value = await loop.run_in_executor(
                    self.executor, 
                    count_ath, 
                    token_address
                )
                ath_cache[token_address] = ath_value
                monitor.end_request()
                return ath_value
            except Exception as e:
                logger.error(f"Ошибка получения ATH для {token_address}: {e}")
                monitor.log_error(f"ATH error for {token_address}: {e}")
                ath_cache[token_address] = 0
                return 0
    
    async def get_cached_migration(self, token_address: str) -> bool:
        """Получение статуса миграции с кэшированием"""
        if token_address in migration_cache:
            return migration_cache[token_address]
        
        async with self.semaphore:
            try:
                monitor.start_request()
                migrated = await check_migration_async(token_address)
                migration_cache[token_address] = migrated
                monitor.end_request()
                return migrated
            except Exception as e:
                logger.error(f"Ошибка проверки миграции для {token_address}: {e}")
                monitor.log_error(f"Migration error for {token_address}: {e}")
                migration_cache[token_address] = False
                return False

async def process_tokens_batch(token_addresses: List[str], user_dev) -> List[Tuple[str, int, bool]]:
    """Обработка батча токенов параллельно"""
    processor = TokenProcessor()
    
    async with processor:
        # Создаем задачи для всех токенов в батче
        tasks = []
        for token_address in token_addresses:
            ath_task = processor.get_cached_ath(token_address)
            migration_task = processor.get_cached_migration(token_address)
            tasks.append((token_address, ath_task, migration_task))
        
        # Выполняем все задачи параллельно
        results = []
        for token_address, ath_task, migration_task in tasks:
            try:
                ath_value, migrated = await asyncio.gather(ath_task, migration_task)
                results.append((token_address, ath_value, migrated))
            except Exception as e:
                logger.error(f"Ошибка обработки токена {token_address}: {e}")
                results.append((token_address, 0, False))
        
        return results

async def bulk_create_tokens(tokens_data: List[Tuple[str, int, bool]], user_dev) -> List[int]:
    """Массовое создание/обновление токенов в БД"""
    ath_values = []
    
    # Группируем токены для bulk операций
    tokens_to_create = []
    tokens_to_update = []
    
    for token_address, ath_value, migrated in tokens_data:
        ath_values.append(ath_value)
        
        # Проверяем существование токена
        existing_token = await sync_to_async(Token.objects.filter(address=token_address).first)()
        
        if existing_token:
            # Обновляем существующий токен
            existing_token.ath = ath_value
            existing_token.migrated = migrated
            tokens_to_update.append(existing_token)
        else:
            # Создаем новый токен
            tokens_to_create.append(Token(
                address=token_address,
                dev=user_dev,
                ath=ath_value,
                migrated=migrated,
                total_trans=0,
                total_fees=0.0
            ))
    
    # Выполняем bulk операции
    if tokens_to_create:
        await sync_to_async(Token.objects.bulk_create)(tokens_to_create, ignore_conflicts=True)
    
    if tokens_to_update:
        await sync_to_async(Token.objects.bulk_update)(tokens_to_update, ['ath', 'migrated'])
    
    return ath_values

async def process_user_tokens_optimized(user_dev, tokens_data: dict) -> List[int]:
    """Оптимизированная обработка токенов пользователя"""
    token_addresses = list(tokens_data.keys())
    
    if not token_addresses:
        return []
    
    logger.info(f"Обрабатываем {len(token_addresses)} токенов для пользователя {user_dev.adress}")
    
    # Обрабатываем токены батчами
    all_results = []
    for i in range(0, len(token_addresses), BATCH_SIZE):
        batch = token_addresses[i:i + BATCH_SIZE]
        batch_results = await process_tokens_batch(batch, user_dev)
        all_results.extend(batch_results)
    
    # Создаем токены в БД
    ath_values = await bulk_create_tokens(all_results, user_dev)
    
    logger.info(f"Обработано {len(ath_values)} токенов из {len(token_addresses)}")
    return ath_values

async def process_user_dev_optimized(user_dev) -> None:
    """Оптимизированная обработка одного пользователя"""
    start_time = time.time()
    user_id = str(user_dev.adress)
    
    try:
        # Отмечаем начало обработки пользователя
        load_monitor.start_user_processing(user_id)
        
        logger.info(f"Пользователь: {user_dev.adress}")
        
        # Получаем токены пользователя
        tokens_data = await get_all_tokens_by_address_async(user_dev.adress)
        
        if not tokens_data or 'total' not in tokens_data:
            user_dev.processed = True
            await sync_to_async(user_dev.save)()
            load_monitor.end_user_processing(user_id)
            return
        
        total_tokens = tokens_data['total']
        tokens = tokens_data.get('tokens', {})
        
        logger.info(f"  Токенов: {total_tokens}")
        
        # Обновляем total_tokens
        user_dev.total_tokens = total_tokens
        await sync_to_async(user_dev.save)()
        
        # Проверяем условие
        if 5 < total_tokens < 300:
            if not tokens:
                user_dev.ath = 0
                logger.info(f"  ATH: 0 (нет токенов для обработки)")
            else:
                logger.info(f"  Начинаем обработку {len(tokens)} токенов...")
                ath_values = await process_user_tokens_optimized(user_dev, tokens)
                
                # Вычисляем среднее ATH
                if ath_values:
                    valid_ath_values = [v for v in ath_values if v is not None and v > 0]
                    logger.info(f"  Валидных ATH значений: {len(valid_ath_values)} из {len(ath_values)}")
                    
                    if valid_ath_values:
                        average_ath = sum(valid_ath_values) / len(valid_ath_values)
                        user_dev.ath = int(average_ath)
                        logger.info(f"  ATH: {average_ath:.2f}")
                    else:
                        user_dev.ath = 0
                        logger.info(f"  ATH: 0 (нет валидных данных)")
                else:
                    user_dev.ath = 0
                    logger.info(f"  ATH: 0 (нет данных)")
        else:
            user_dev.ath = 0
            logger.info(f"  ATH: 0 (не подходит под условия: {total_tokens} токенов)")
        
        # Отмечаем как обработанного
        user_dev.processed = True
        await sync_to_async(user_dev.save)()
        
        # Обновляем метрики
        monitor.metrics['processed_users'] += 1
        monitor.metrics['processed_tokens'] += len(tokens) if tokens else 0
        
        elapsed = time.time() - start_time
        logger.info(f"  Завершено за {elapsed:.2f} сек")
        
        # Отмечаем завершение обработки пользователя
        load_monitor.end_user_processing(user_id)
        
    except Exception as e:
        logger.error(f"  Ошибка обработки пользователя {user_dev.adress}: {e}")
        monitor.log_error(f"User processing error for {user_dev.adress}: {e}")
        load_monitor.log_error()
        load_monitor.end_user_processing(user_id)

async def process_all_users_optimized():
    """Оптимизированная обработка всех пользователей"""
    start_time = time.time()
    
    # Получаем пользователей батчами
    users = await sync_to_async(list)(
        UserDev.objects.filter(processed=False, blacklist=False)
    )
    
    logger.info(f"Найдено пользователей: {len(users)}")
    
    if not users:
        logger.info("Нет пользователей для обработки")
        return
    
    # Ограничиваем количество одновременных пользователей
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_USERS)
    
    async def process_user_with_semaphore(user):
        async with semaphore:
            return await process_user_dev_optimized(user)
    
    # Обрабатываем пользователей батчами
    batch_size = 25  # Увеличено для лучшего распределения нагрузки
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        tasks = [process_user_with_semaphore(user) for user in batch]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Небольшая пауза между батчами для стабилизации
        if i + batch_size < len(users):
            await asyncio.sleep(0.5)  # Уменьшено время паузы
    
    elapsed = time.time() - start_time
    logger.info(f"Обработка завершена за {elapsed:.2f} сек")

async def main():
    """Главная функция"""
    logger.info("Запуск оптимизированной обработки пользователей...")
    logger.info(f"Одновременных пользователей: {MAX_CONCURRENT_USERS}")
    logger.info(f"Одновременных токенов: {MAX_CONCURRENT_TOKENS}")
    logger.info(f"Максимальных запросов: {MAX_CONCURRENT_REQUESTS}")
    logger.info(f"Размер батча: {BATCH_SIZE}")
    logger.info("-" * 50)
    
    try:
        # Запускаем мониторинг производительности в фоне
        monitor_task = asyncio.create_task(monitor_periodic_report())
        load_monitor_task = asyncio.create_task(monitor_load_periodically())
        
        await process_all_users_optimized()
        
        # Останавливаем мониторинг
        monitor_task.cancel()
        load_monitor_task.cancel()
        
        logger.info("-" * 50)
        logger.info("Обработка завершена успешно")
        
        # Финальный отчет
        monitor.print_report()
        load_monitor.print_load_report()
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        monitor.log_error(f"Critical error: {e}")

async def monitor_periodic_report():
    """Периодический вывод отчетов о производительности"""
    while True:
        await asyncio.sleep(60)  # Каждую минуту
        monitor.print_report()

if __name__ == "__main__":
    asyncio.run(main()) 