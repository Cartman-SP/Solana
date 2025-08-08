import asyncio
import django
import os
import sys
from asgiref.sync import sync_to_async
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

# Настройка Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from mainapp.models import UserDev, Token
from ath_trans import count_ath
from get_migration import check_migration_async

# Конфигурация асинхронности
MAX_CONCURRENT_TOKENS = 100  # Максимальное количество одновременно обрабатываемых токенов

def count_ath_sync(token_address):
    """Синхронная обертка для count_ath"""
    return count_ath(token_address)

async def process_single_token(token):
    """Обработка одного токена - получение ATH и проверка миграции"""
    max_attempts = 5
    
    for attempt in range(max_attempts):
        try:
            # Выполняем count_ath в отдельном потоке
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                ath_value = await loop.run_in_executor(executor, count_ath_sync, token.address)
            
            # Если ATH = 0 и это не последняя попытка, пробуем еще раз
            if ath_value == 0 and attempt < max_attempts - 1:
                print(f"  Токен {token.address}: ATH = 0, попытка {attempt + 1}/{max_attempts}")
                continue
            
            # Проверяем миграцию токена
            migrated = await check_migration_async(token.address)
            
            # Обновляем токен
            token.ath = ath_value
            token.migrated = migrated
            await sync_to_async(token.save)()
            
            print(f"  Токен {token.address}: ATH = {ath_value}, миграция = {migrated}")
            return ath_value
            
        except Exception as e:
            print(f"  Ошибка обработки токена {token.address}: {e}")
            if attempt == max_attempts - 1:
                return 0
            continue
    
    return 0

async def process_user_dev_ath(user_dev):
    """Пересчет среднего ATH для UserDev"""
    try:
        # Получаем все токены пользователя
        tokens = await sync_to_async(list)(Token.objects.filter(dev=user_dev))
        
        if not tokens:
            print(f"  Пользователь {user_dev.adress}: нет токенов для обработки")
            return
        
        # Собираем ATH значения
        ath_values = []
        for token in tokens:
            if token.ath > 0:
                ath_values.append(token.ath)
        
        if ath_values:
            average_ath = sum(ath_values) / len(ath_values)
            user_dev.ath = int(average_ath)
            await sync_to_async(user_dev.save)()
            print(f"  Пользователь {user_dev.adress}: средний ATH = {average_ath:.2f}")
        else:
            user_dev.ath = 0
            await sync_to_async(user_dev.save)()
            print(f"  Пользователь {user_dev.adress}: ATH = 0 (нет валидных токенов)")
            
    except Exception as e:
        print(f"  Ошибка пересчета ATH для пользователя {user_dev.adress}: {e}")

async def process_tokens_batch(tokens):
    """Обработка батча токенов"""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TOKENS)
    
    async def process_token_with_semaphore(token):
        async with semaphore:
            return await process_single_token(token)
    
    tasks = [process_token_with_semaphore(token) for token in tokens]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Собираем результаты и группируем по пользователям
    user_devs_to_update = set()
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"  Ошибка в задаче {i}: {result}")
            continue
        
        if result > 0:  # Если ATH успешно обновлен
            user_devs_to_update.add(tokens[i].dev)
    
    return user_devs_to_update

async def process_all_old_tokens():
    """Основная функция для обработки всех старых токенов с ATH = 0"""
    # Получаем токены с ATH = 0 и created_at > 8 часов назад, исключая токены с blacklist = True
    cutoff_time = datetime.now() - timedelta(hours=8)
    
    tokens = await sync_to_async(list)(
        Token.objects.filter(
            ath=0,
            created_at__lt=cutoff_time,
            dev__blacklist=False
        ).select_related('dev')
    )
    
    print(f"Найдено токенов для обработки: {len(tokens)}")
    
    if not tokens:
        print("Нет токенов для обработки")
        return
    
    # Группируем токены по пользователям для оптимизации
    tokens_by_user = {}
    for token in tokens:
        if token.dev not in tokens_by_user:
            tokens_by_user[token.dev] = []
        tokens_by_user[token.dev].append(token)
    
    print(f"Пользователей с токенами для обработки: {len(tokens_by_user)}")
    
    # Обрабатываем токены батчами
    all_tokens = list(tokens)
    batch_size = 50  # Размер батча
    
    user_devs_to_update = set()
    
    for i in range(0, len(all_tokens), batch_size):
        batch = all_tokens[i:i + batch_size]
        print(f"Обработка батча {i//batch_size + 1}/{(len(all_tokens) + batch_size - 1)//batch_size}")
        
        batch_user_devs = await process_tokens_batch(batch)
        user_devs_to_update.update(batch_user_devs)
    
    # Пересчитываем ATH для пользователей
    print(f"Пересчет ATH для {len(user_devs_to_update)} пользователей...")
    
    semaphore = asyncio.Semaphore(10)  # Ограничиваем количество одновременных пользователей
    
    async def process_user_with_semaphore(user_dev):
        async with semaphore:
            return await process_user_dev_ath(user_dev)
    
    tasks = [process_user_with_semaphore(user_dev) for user_dev in user_devs_to_update]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("Обработка завершена")

async def main():
    """Главная функция"""
    print("Обработка старых токенов с ATH = 0...")
    print(f"Одновременных токенов: {MAX_CONCURRENT_TOKENS}")
    print("-" * 50)
    
    try:
        await process_all_old_tokens()
        print("-" * 50)
        print("Обработка завершена успешно")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
