import os
import sys
import django
import asyncio
from concurrent.futures import ThreadPoolExecutor
from django.db import connection, transaction
from django.db.models import Count, Min

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev

def clean_duplicates_batch_sql():
    """
    Сверхбыстрое удаление через batch SQL запросы
    """
    try:
        print("Выполнение batch SQL-запроса для удаления дубликатов...")
        
        with connection.cursor() as cursor:
            # Создаем временную таблицу с минимальными ID для каждого адреса
            cursor.execute("""
                CREATE TEMPORARY TABLE temp_min_ids AS
                SELECT MIN(id) as min_id, adress
                FROM mainapp_userdev 
                GROUP BY adress
            """)
            
            # Удаляем все записи кроме минимальных ID
            cursor.execute("""
                DELETE FROM mainapp_userdev 
                WHERE id NOT IN (
                    SELECT min_id FROM temp_min_ids
                )
            """)
            
            deleted_count = cursor.rowcount
            
            # Удаляем временную таблицу
            cursor.execute("DROP TABLE temp_min_ids")
            
            print(f"Удалено {deleted_count} дублирующихся записей через batch SQL")
            
    except Exception as e:
        print(f"Ошибка при batch SQL-удалении: {e}")

def clean_duplicates_partitioned():
    """
    Удаление дубликатов по частям для больших объемов данных
    """
    try:
        print("Поиск дубликатов...")
        
        # Получаем общее количество адресов с дубликатами
        total_duplicates = (
            UserDev.objects
            .values('adress')
            .annotate(count=Count('adress'))
            .filter(count__gt=1)
            .count()
        )
        
        if total_duplicates == 0:
            print("Дубликаты не найдены")
            return
        
        print(f"Найдено {total_duplicates} адресов с дубликатами")
        
        # Размер batch для обработки
        BATCH_SIZE = 1000
        processed = 0
        
        with transaction.atomic():
            while processed < total_duplicates:
                # Получаем batch адресов с дубликатами
                batch_addresses = (
                    UserDev.objects
                    .values('adress')
                    .annotate(
                        count=Count('adress'),
                        min_id=Min('id')
                    )
                    .filter(count__gt=1)
                    .order_by('adress')
                    [processed:processed + BATCH_SIZE]
                )
                
                if not batch_addresses:
                    break
                
                # Удаляем дубликаты для batch
                for duplicate in batch_addresses:
                    address = duplicate['adress']
                    min_id = duplicate['min_id']
                    
                    # Удаляем все записи кроме первой
                    UserDev.objects.filter(
                        adress=address
                    ).exclude(
                        id=min_id
                    ).delete()
                
                processed += len(batch_addresses)
                print(f"Обработано {processed}/{total_duplicates} адресов")
        
        print("Удаление дубликатов завершено")
        
    except Exception as e:
        print(f"Ошибка при partitioned удалении: {e}")

def clean_duplicates_parallel():
    """
    Параллельное удаление дубликатов через несколько потоков
    """
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        print("Поиск дубликатов для параллельной обработки...")
        
        # Получаем все адреса с дубликатами
        duplicates_info = list(
            UserDev.objects
            .values('adress')
            .annotate(
                count=Count('adress'),
                min_id=Min('id')
            )
            .filter(count__gt=1)
        )
        
        if not duplicates_info:
            print("Дубликаты не найдены")
            return
        
        print(f"Найдено {len(duplicates_info)} адресов для обработки")
        
        def process_address_batch(address_batch):
            """Обрабатывает batch адресов в отдельном потоке"""
            try:
                with transaction.atomic():
                    for duplicate in address_batch:
                        address = duplicate['adress']
                        min_id = duplicate['min_id']
                        
                        # Удаляем дубликаты
                        UserDev.objects.filter(
                            adress=address
                        ).exclude(
                            id=min_id
                        ).delete()
                
                return len(address_batch)
            except Exception as e:
                print(f"Ошибка в потоке: {e}")
                return 0
        
        # Разбиваем на batch для параллельной обработки
        BATCH_SIZE = 100
        batches = [
            duplicates_info[i:i + BATCH_SIZE] 
            for i in range(0, len(duplicates_info), BATCH_SIZE)
        ]
        
        total_processed = 0
        
        # Используем ThreadPoolExecutor для параллельной обработки
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Запускаем все batch параллельно
            future_to_batch = {
                executor.submit(process_address_batch, batch): batch 
                for batch in batches
            }
            
            # Обрабатываем результаты по мере завершения
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    processed_count = future.result()
                    total_processed += processed_count
                    print(f"Обработано {total_processed}/{len(duplicates_info)} адресов")
                except Exception as e:
                    print(f"Ошибка при обработке batch: {e}")
        
        print(f"Параллельная обработка завершена. Обработано {total_processed} адресов")
        
    except Exception as e:
        print(f"Ошибка при параллельной обработке: {e}")

if __name__ == "__main__":
    print("Выберите метод удаления:")
    print("1. Batch SQL (самый быстрый)")
    print("2. Partitioned (для больших объемов)")
    print("3. Parallel (многопоточный)")
    
    choice = input("Введите 1, 2 или 3: ").strip()
    
    if choice == "1":
        clean_duplicates_batch_sql()
    elif choice == "2":
        clean_duplicates_partitioned()
    elif choice == "3":
        clean_duplicates_parallel()
    else:
        print("Неверный выбор, используем batch SQL")
        clean_duplicates_batch_sql() 