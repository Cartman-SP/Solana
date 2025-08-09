import asyncio
import websockets
import json
import os
import sys
import django

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import UserDev, Token

def get_migrated_tokens_with_single_dev():
    """
    Получает все токены с migrated=True, у которых у привязанного UserDev не больше 1 токена
    """
    # Получаем все токены с migrated=True
    migrated_tokens = list(Token.objects.filter(migrated=True))
    
    # Словарь для подсчета токенов для каждого UserDev
    dev_token_counts = {}
    
    # Подсчитываем токены для каждого UserDev
    for token in migrated_tokens:
        dev_id = token.dev.id
        if dev_id not in dev_token_counts:
            dev_token_counts[dev_id] = 0
        dev_token_counts[dev_id] += 1
    
    # Фильтруем UserDev с не больше 1 токена
    single_token_devs = []
    for dev_id, count in dev_token_counts.items():
        if count <= 1:
            single_token_devs.append(dev_id)
    
    # Получаем адреса UserDev
    dev_addresses = []
    for dev_id in single_token_devs:
        dev = UserDev.objects.get(id=dev_id)
        dev_addresses.append(dev.adress)
    
    return dev_addresses

def main():
    """
    Основная функция для выполнения задачи
    """
    try:
        print("Поиск токенов с migrated=True, у которых у UserDev не больше 1 токена...")
        
        # Получаем адреса UserDev
        dev_addresses = get_migrated_tokens_with_single_dev()
        
        if dev_addresses:
            print(f"\nНайдено {len(dev_addresses)} UserDev с не больше 1 токеном:")
            print("-" * 50)
            for i, address in enumerate(dev_addresses, 1):
                print(f"{i}. {address}")
        else:
            print("Не найдено UserDev с не больше 1 токеном")
            
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
