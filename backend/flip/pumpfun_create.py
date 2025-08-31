import asyncio
import websockets
import json
import ipfshttpclient
from create import *

# Глобальный IPFS клиент
ipfs_client = None

def setup_ipfs_client():
    """Настраиваем глобальный IPFS клиент с множественными попытками подключения"""
    global ipfs_client
    
    # Пробуем разные порты и адреса для IPFS API
    ipfs_endpoints = [
        '/ip4/127.0.0.1/tcp/5001',  # Стандартный порт
        '/ip4/127.0.0.1/tcp/5101',  # Ваш текущий порт
        '/ip4/127.0.0.1/tcp/8080',  # Альтернативный порт
        '/ip4/0.0.0.0/tcp/5001',    # Все интерфейсы
    ]
    
    for endpoint in ipfs_endpoints:
        try:
            print(f"🔄 Пробуем подключиться к IPFS API: {endpoint}")
            ipfs_client = ipfshttpclient.connect(endpoint)
            
            # Проверяем подключение
            try:
                ipfs_client.version()
                print(f"✅ Успешно подключились к IPFS API: {endpoint}")
                return ipfs_client
            except Exception as e:
                print(f"❌ Ошибка проверки версии IPFS: {e}")
                ipfs_client.close()
                ipfs_client = None
                continue
                
        except Exception as e:
            print(f"❌ Не удалось подключиться к {endpoint}: {e}")
            continue
    
    print("⚠️ Не удалось подключиться ни к одному IPFS API endpoint")
    return None

async def subscribe():
    global ipfs_client
    
    # Настраиваем IPFS клиент при запуске
    print("🚀 Запуск системы с IPFS клиентом...")
    ipfs_client = setup_ipfs_client()
    
    if ipfs_client:
        print("✅ IPFS клиент успешно настроен")
        try:
            # Проверяем статус IPFS
            version = ipfs_client.version()
            print(f"📋 IPFS версия: {version}")
            
            # Проверяем количество пиров
            peers = ipfs_client.swarm.peers()
            print(f"🔗 Подключенные пиры: {len(peers)}")
            
        except Exception as e:
            print(f"⚠️ Ошибка проверки IPFS статуса: {e}")
    else:
        print("⚠️ IPFS клиент недоступен, будет использоваться только HTTP")
    
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as websocket:
        print("🔌 Подключились к PumpPortal WebSocket")
        
        # Subscribing to token creation events
        payload = {
            "method": "subscribeNewToken",
        }
        await websocket.send(json.dumps(payload))
        print("📡 Подписались на события создания токенов")
        
        async for message in websocket:
            data = json.loads(message)
            try:
                if 'uri' in data:
                    print(f"🆕 Получен новый токен: {data.get('mint', 'Unknown')}")
                    # Передаем IPFS клиент в process_create
                    asyncio.create_task(process_create(data, ipfs_client))
            except Exception as e:
                print(f"❌ Ошибка обработки сообщения: {e}")
                pass

# Run the subscribe function
if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(subscribe())
    except KeyboardInterrupt:
        print("\n🛑 Остановка по запросу пользователя")
        if ipfs_client:
            try:
                ipfs_client.close()
                print("✅ IPFS клиент закрыт")
            except:
                pass
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        if ipfs_client:
            try:
                ipfs_client.close()
                print("✅ IPFS клиент закрыт")
            except:
                pass