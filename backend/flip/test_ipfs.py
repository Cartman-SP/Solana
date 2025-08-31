#!/usr/bin/env python3
"""
Тестовый скрипт для проверки IPFS подключения
"""

import aioipfs
import asyncio
import json

async def test_ipfs_connection():
    """Тестирует асинхронное подключение к IPFS API"""
    print("🧪 Тестирование асинхронного IPFS подключения...")
    
    # Пробуем разные порты для IPFS API
    ipfs_ports = [5001, 5101, 8080]  # Стандартный, ваш текущий, альтернативный
    
    for port in ipfs_ports:
        try:
            print(f"\n🔄 Пробуем подключиться к IPFS API на порту {port}")
            client = aioipfs.AsyncIPFS(host='127.0.0.1', port=port)
            
            # Проверяем подключение
            try:
                await client.connect()
                print(f"✅ Успешно подключились к порту {port}")
                
                # Получаем версию
                try:
                    version = await client.version()
                    print(f"📋 Версия IPFS: {version}")
                except Exception as e:
                    print(f"⚠️ Не удалось получить версию: {e}")
                
                # Пробуем простую команду
                try:
                    peers = await client.swarm.peers()
                    print(f"🔗 Подключенные пиры: {len(peers)}")
                except Exception as e:
                    print(f"⚠️ Не удалось получить пиры: {e}")
                
                # Проверяем, что клиент поддерживает disconnect
                if hasattr(client, 'disconnect'):
                    await client.disconnect()
                return True
                
            except Exception as e:
                print(f"❌ Ошибка подключения к порту {port}: {e}")
                continue
                
        except Exception as e:
            print(f"❌ Не удалось настроить клиент для порта {port}: {e}")
            continue
    
    print("\n⚠️ Не удалось подключиться ни к одному IPFS API порту")
    return False

def test_ipfs_gateways():
    """Тестирует IPFS gateways"""
    print("\n🌐 Тестирование IPFS gateways...")
    
    import requests
    
    test_cid = "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG"  # Тестовый CID
    
    gateways = [
        f"http://127.0.0.1:8180/ipfs/{test_cid}",
        f"https://ipfs.io/ipfs/{test_cid}",
        f"https://gateway.pinata.cloud/ipfs/{test_cid}",
        f"https://cloudflare-ipfs.com/ipfs/{test_cid}",
    ]
    
    for gateway in gateways:
        try:
            print(f"🌐 Тестируем gateway: {gateway}")
            response = requests.get(gateway, timeout=10)
            if response.status_code == 200:
                print(f"✅ Gateway работает: {gateway}")
                print(f"📋 Размер ответа: {len(response.content)} байт")
            else:
                print(f"⚠️ Gateway вернул статус {response.status_code}: {gateway}")
        except Exception as e:
            print(f"❌ Gateway не работает: {gateway} - {e}")

async def main():
    print("🚀 Запуск тестов IPFS...")
    
    # Тест прямого API
    api_works = await test_ipfs_connection()
    
    # Тест gateways
    test_ipfs_gateways()
    
    if api_works:
        print("\n🎉 IPFS API работает! Проблема может быть в коде приложения.")
    else:
        print("\n❌ IPFS API недоступен. Проверьте:")
        print("   1. Запущен ли IPFS daemon?")
        print("   2. Правильный ли порт? (обычно 5001)")
        print("   3. Доступен ли API? (ipfs config Addresses.API)")
        print("   4. Нет ли firewall блокировки?")

if __name__ == "__main__":
    asyncio.run(main()) 