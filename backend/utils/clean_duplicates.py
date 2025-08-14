import os
import sys
import django

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev
from django.db.models import Count

def clean_duplicates():
    """
    Удаляет дублирующиеся UserDev с одинаковыми адресами
    Оставляет только первую запись для каждого адреса
    """
    try:
        # Находим адреса с дубликатами
        duplicate_addresses = (
            UserDev.objects
            .values('adress')
            .annotate(count=Count('adress'))
            .filter(count__gt=1)
        )
        
        total_duplicates = 0
        
        for duplicate in duplicate_addresses:
            address = duplicate['adress']
            count = duplicate['count']
            
            # Получаем все записи с этим адресом, отсортированные по ID
            duplicates = UserDev.objects.filter(adress=address).order_by('id')
            
            # Оставляем первую запись, удаляем остальные
            first_record = duplicates.first()
            duplicates_to_delete = duplicates.exclude(id=first_record.id)
            
            # Удаляем дубликаты
            deleted_count = duplicates_to_delete.count()
            duplicates_to_delete.delete()
            
            total_duplicates += deleted_count
            
            print(f"Адрес {address}: удалено {deleted_count} дубликатов (оставлено 1)")
        
        if total_duplicates == 0:
            print("Дубликаты не найдены")
        else:
            print(f"Всего удалено {total_duplicates} дублирующихся записей")
            
    except Exception as e:
        print(f"Ошибка при очистке дубликатов: {e}")

if __name__ == "__main__":
    clean_duplicates() 