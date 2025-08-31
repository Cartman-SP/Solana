#!/usr/bin/env python3
"""
Простой тест IPFS клиента
"""

import asyncio
import aioipfs
from create import IPFSClient

async def test_ipfs_client():
    """Тестирует наш IPFS клиент"""
    print("🧪 Тестирование IPFS клиента...")
    
    # Создаем клиент
    client = IPFSClient()
    
    if not client.client:
        print("❌ IPFS клиент не настроен")
        return False
    
    print(f"✅ IPFS клиент создан: {type(client.client)}")
    
    # Проверяем методы клиента
    methods = ['connect', 'cat', 'version', 'disconnect']
    for method in methods:
        if hasattr(client.client, method):
            print(f"✅ Метод {method} доступен")
        else:
            print(f"❌ Метод {method} недоступен")
    
    # Пробуем подключиться
    try:
        connected = await client.ensure_connection()
        if connected:
            print("✅ Подключение установлено")
        else:
            print("❌ Не удалось установить подключение")
    except Exception as e:
        print(f"❌ Ошибка при подключении: {e}")
    
    return True

async def test_direct_aioipfs():
    """Тестирует прямой aioipfs клиент"""
    print("\n🧪 Тестирование прямого aioipfs клиента...")
    
    try:
        # Создаем прямой клиент
        client = aioipfs.AsyncIPFS(host='127.0.0.1', port=5001)
        print(f"✅ Прямой клиент создан: {type(client)}")
        
        # Проверяем методы
        methods = ['connect', 'cat', 'version', 'disconnect']
        for method in methods:
            if hasattr(client, method):
                print(f"✅ Метод {method} доступен")
            else:
                print(f"❌ Метод {method} недоступен")
        
        # Пробуем подключиться
        try:
            await client.connect()
            print("✅ Прямое подключение установлено")
            
            # Получаем версию
            try:
                version = await client.version()
                print(f"📋 Версия IPFS: {version}")
            except Exception as e:
                print(f"⚠️ Не удалось получить версию: {e}")
            
            # Отключаемся
            if hasattr(client, 'disconnect'):
                await client.disconnect()
                print("✅ Отключение выполнено")
            
        except Exception as e:
            print(f"❌ Ошибка при подключении: {e}")
            
    except Exception as e:
        print(f"❌ Ошибка при создании прямого клиента: {e}")

async def main():
    print("🚀 Запуск тестов...")
    
    # Тест нашего клиента
    await test_ipfs_client()
    
    # Тест прямого клиента
    await test_direct_aioipfs()
    
    print("\n✅ Тесты завершены")

if __name__ == "__main__":
    asyncio.run(main()) 