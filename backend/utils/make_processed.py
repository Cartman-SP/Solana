import os
import sys
import django
from datetime import datetime, timedelta

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token

def update_old_tokens():
    """Обновляет все токены, созданные больше 2 часов назад, устанавливая processed = True"""
    
    # Вычисляем время 2 часа назад
    two_hours_ago = datetime.now() - timedelta(hours=2)
    
    # Получаем все токены, созданные больше 2 часов назад и не обработанные
    old_tokens = Token.objects.filter(
        created_at__lt=two_hours_ago,
        processed=False
    )
    
    # Обновляем их статус
    count = old_tokens.update(processed=True)
    
    print(f"Обновлено {count} токенов, созданных больше 2 часов назад")
    print(f"Время выполнения: {datetime.now()}")
    print(f"Время 2 часа назад: {two_hours_ago}")

if __name__ == "__main__":
    update_old_tokens()