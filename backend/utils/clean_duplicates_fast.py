import os
import sys
import django

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev
from django.db.models import Count, Min
from django.db import transaction

def clean_duplicates_fast():
    """
    Быстрое удаление дублирующихся UserDev с одинаковыми адресами
    Использует bulk_delete и SQL-оптимизации
    """
    try:
        print("Поиск дубликатов...")
        
        # Находим адреса с дубликатами и минимальные ID для каждого
        duplicates_info = (
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
        
        total_duplicates = 0
        
        # Используем транзакцию для атомарности
        with transaction.atomic():
            for duplicate in duplicates_info:
                address = duplicate['adress']
                count = duplicate['count']
                min_id = duplicate['min_id']
                
                # Удаляем все записи кроме первой (с минимальным ID)
                deleted_count = UserDev.objects.filter(
                    adress=address
                ).exclude(
                    id=min_id
                ).delete()[0]  # delete() возвращает кортеж (количество_удаленных, детали)
                
                total_duplicates += deleted_count
                print(f"Адрес {address}: удалено {deleted_count} дубликатов (оставлено 1)")
        
        print(f"Всего удалено {total_duplicates} дублирующихся записей")
        
    except Exception as e:
        print(f"Ошибка при очистке дубликатов: {e}")

def clean_duplicates_sql():
    """
    Сверхбыстрое удаление через прямой SQL запрос
    """
    try:
        from django.db import connection
        
        print("Выполнение SQL-запроса для удаления дубликатов...")
        
        with connection.cursor() as cursor:
            # SQL запрос для удаления дубликатов, оставляя только первую запись
            sql = """
            DELETE FROM mainapp_userdev 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM mainapp_userdev 
                GROUP BY adress
            )
            """
            
            cursor.execute(sql)
            deleted_count = cursor.rowcount
            
            print(f"Удалено {deleted_count} дублирующихся записей через SQL")
            
    except Exception as e:
        print(f"Ошибка при SQL-удалении: {e}")

if __name__ == "__main__":
    print("Выберите метод удаления:")
    print("1. Оптимизированный Python (рекомендуется)")
    print("2. Сверхбыстрый SQL")
    
    choice = input("Введите 1 или 2: ").strip()
    
    if choice == "2":
        clean_duplicates_sql()
    else:
        clean_duplicates_fast() 