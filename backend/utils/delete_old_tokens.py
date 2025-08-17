import os
import sys
import django
from datetime import datetime, timedelta

# Добавляем путь к проекту Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token
from django.utils import timezone

def delete_old_tokens():
    """Удаляет токены старше 2-х дней"""
    # Вычисляем дату 2 дня назад
    two_days_ago = timezone.now() - timedelta(days=2)
    
    # Находим токены старше 2-х дней
    old_tokens = Token.objects.filter(created_at__lt=two_days_ago)
    
    # Подсчитываем количество токенов для удаления
    count = old_tokens.count()
    
    if count > 0:
        print(f"Найдено {count} токенов старше 2-х дней")
        
        # Удаляем старые токены
        old_tokens.delete()
        
        print(f"Успешно удалено {count} токенов")
    else:
        print("Токены старше 2-х дней не найдены")
    
    # Обновляем счетчики total_tokens для UserDev
    update_user_dev_counters()
    
def update_user_dev_counters():
    """Обновляет счетчики total_tokens для всех UserDev"""
    user_devs = UserDev.objects.all()
    
    for user_dev in user_devs:
        # Подсчитываем актуальное количество токенов
        actual_count = Token.objects.filter(dev=user_dev).count()
        
        # Обновляем счетчик, если он отличается
        if user_dev.total_tokens != actual_count:
            old_count = user_dev.total_tokens
            user_dev.total_tokens = actual_count
            user_dev.save()
            print(f"Обновлен счетчик для {user_dev.adress}: {old_count} -> {actual_count}")

if __name__ == "__main__":
    print("Начинаю удаление токенов старше 2-х дней...")
    delete_old_tokens()
    print("Операция завершена!")

