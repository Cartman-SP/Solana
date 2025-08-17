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

def delete_unprocessed_old_tokens():
    """Удаляет необработанные токены (processed=False) старше 40 минут"""
    # Вычисляем дату 40 минут назад - используем локальное время
    forty_minutes_ago = timezone.localtime(timezone.now()) - timedelta(minutes=40)
    
    # Находим необработанные токены старше 40 минут
    old_unprocessed_tokens = Token.objects.filter(
        processed=False,
        created_at__lt=forty_minutes_ago
    )
    
    # Подсчитываем количество токенов для удаления
    count = old_unprocessed_tokens.count()
    
    if count > 0:
        print(f"Найдено {count} необработанных токенов старше 40 минут")
        
        # Выводим информацию о токенах перед удалением
        for token in old_unprocessed_tokens[:10]:  # Показываем первые 10 для примера
            print(f"  - {token.address} (создан: {token.created_at.strftime('%Y-%m-%d %H:%M:%S')})")
        
        if count > 10:
            print(f"  ... и еще {count - 10} токенов")
        
        # Удаляем старые необработанные токены
        old_unprocessed_tokens.delete()
        
        print(f"Успешно удалено {count} необработанных токенов")
    else:
        print("Необработанные токены старше 40 минут не найдены")
    
    # Обновляем счетчики total_tokens для UserDev
    update_user_dev_counters()
    
def update_user_dev_counters():
    """Обновляет счетчики total_tokens для всех UserDev"""
    user_devs = UserDev.objects.all()
    updated_count = 0
    
    for user_dev in user_devs:
        # Подсчитываем актуальное количество токенов
        actual_count = Token.objects.filter(dev=user_dev).count()
        
        # Обновляем счетчик, если он отличается
        if user_dev.total_tokens != actual_count:
            old_count = user_dev.total_tokens
            user_dev.total_tokens = actual_count
            user_dev.save()
            print(f"Обновлен счетчик для {user_dev.adress}: {old_count} -> {actual_count}")
            updated_count += 1
    
    if updated_count == 0:
        print("Все счетчики UserDev актуальны")

def show_token_stats():
    """Показывает статистику по токенам"""
    total_tokens = Token.objects.count()
    processed_tokens = Token.objects.filter(processed=True).count()
    unprocessed_tokens = Token.objects.filter(processed=False).count()
    
    print(f"\nСтатистика токенов:")
    print(f"  Всего токенов: {total_tokens}")
    print(f"  Обработанных: {processed_tokens}")
    print(f"  Необработанных: {unprocessed_tokens}")
    
    # Показываем возраст самых старых необработанных токенов
    if unprocessed_tokens > 0:
        oldest_unprocessed = Token.objects.filter(processed=False).order_by('created_at').first()
        newest_unprocessed = Token.objects.filter(processed=False).order_by('-created_at').first()
        
        now = timezone.now()
        oldest_age = now - oldest_unprocessed.created_at
        newest_age = now - newest_unprocessed.created_at
        
        print(f"  Самый старый необработанный: {oldest_age.total_seconds() / 60:.1f} минут назад")
        print(f"  Самый новый необработанный: {newest_age.total_seconds() / 60:.1f} минут назад")

if __name__ == "__main__":
    print("=== Удаление необработанных токенов старше 40 минут ===")
    
    # Показываем статистику до удаления
    show_token_stats()
    
    print("\nНачинаю удаление...")
    delete_unprocessed_old_tokens()
    
    print("\nСтатистика после удаления:")
    show_token_stats()
    
    print("\nОперация завершена!") 