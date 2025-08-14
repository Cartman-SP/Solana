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
    
    # Фильтруем токены, у которых у UserDev total_tokens <= 1
    filtered_tokens = []
    for token in migrated_tokens:
        if token.dev.total_tokens <= 1:
            filtered_tokens.append(token)
    
    # Получаем адреса UserDev из отфильтрованных токенов
    dev_addresses = []
    for token in filtered_tokens:
        dev_addresses.append(token.dev.adress)
    
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
