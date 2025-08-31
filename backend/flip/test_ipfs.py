#!/usr/bin/env python3
"""
Тестовый скрипт для проверки IPFS подключения
"""

import ipfshttpclient
import asyncio
import json

def test_ipfs_connection():
    """Тестирует подключение к IPFS API"""
    print("🧪 Тестирование IPFS подключения...")
    
    # Пробуем разные порты и адреса для IPFS API
    ipfs_endpoints = [
        '/ip4/127.0.0.1/tcp/5001',  # Стандартный порт
        '/ip4/127.0.0.1/tcp/5101',  # Ваш текущий порт
        '/ip4/127.0.0.1/tcp/8080',  # Альтернативный порт
        '/ip4/0.0.0.0/tcp/5001',    # Все интерфейсы
    ]
    
    for endpoint in ipfs_endpoints:
        try:
            print(f"\n🔄 Пробуем подключиться к IPFS API: {endpoint}")
            client = ipfshttpclient.connect(endpoint)
            
            # Проверяем подключение
            try:
                version = client.version()
                print(f"✅ Успешно подключились к {endpoint}")
                print(f"📋 Версия IPFS: {version}")
                
                # Пробуем получить информацию о node
                try:
                    id_info = client.id()
                    print(f"🆔 Node ID: {id_info['ID']}")
                    print(f"🌐 Адреса: {id_info['Addresses']}")
                except Exception as e:
                    print(f"⚠️ Не удалось получить ID: {e}")
                
                # Пробуем простую команду
                try:
                    peers = client.swarm.peers()
                    print(f"🔗 Подключенные пиры: {len(peers)}")
                except Exception as e:
                    print(f"⚠️ Не удалось получить пиры: {e}")
                
                client.close()
                return True
                
            except Exception as e:
                print(f"❌ Ошибка проверки версии IPFS: {e}")
                client.close()
                continue
                
        except Exception as e:
            print(f"❌ Не удалось подключиться к {endpoint}: {e}")
            continue
    
    print("\n⚠️ Не удалось подключиться ни к одному IPFS API endpoint")
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

if __name__ == "__main__":
    print("🚀 Запуск тестов IPFS...")
    
    # Тест прямого API
    api_works = test_ipfs_connection()
    
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