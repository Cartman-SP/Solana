import os
import sys
import django
from datetime import datetime, timedelta

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token
from django.utils import timezone

def update_old_tokens():
    """Обновляет все токены, созданные больше 2 часов назад, устанавливая processed = True"""
    
    # Используем Django timezone вместо datetime.now()
    now = timezone.now()
    two_hours_ago = now - timedelta(hours=2)
    
    print(f"Текущее время (Django): {now}")
    print(f"Время 2 часа назад: {two_hours_ago}")
    
    # Получаем все токены, созданные больше 2 часов назад и не обработанные
    old_tokens = Token.objects.filter(
        created_at__lt=two_hours_ago,
        processed=False
    )
    
    # Выводим информацию о найденных токенах
    print(f"Найдено {old_tokens.count()} токенов для обновления")
    
    # Обновляем их статус
    count = old_tokens.update(processed=True)
    
    print(f"Обновлено {count} токенов, созданных больше 2 часов назад")
    print(f"Время выполнения: {timezone.now()}")
    
    # Проверяем оставшиеся необработанные токены
    remaining_unprocessed = Token.objects.filter(processed=False).count()
    print(f"Осталось необработанных токенов: {remaining_unprocessed}")

if __name__ == "__main__":
    update_old_tokens()