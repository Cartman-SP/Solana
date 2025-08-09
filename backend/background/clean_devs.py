import os
import sys
import django

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token

def delete_blacklisted_tokens():
    # Находим все UserDev с blacklist=True
    blacklisted_devs = UserDev.objects.filter(blacklist=True)
    
    # Получаем и удаляем все связанные токены
    tokens_to_delete = Token.objects.filter(dev__in=blacklisted_devs)
    count = tokens_to_delete.count()
    tokens_to_delete.delete()
    
    print(f"Удалено {count} токенов, связанных с blacklisted UserDev")

if __name__ == "__main__":
    delete_blacklisted_tokens()
