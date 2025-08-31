import asyncio
import websockets
import json
import aioipfs
from create import *

# Глобальный IPFS клиент
ipfs_client = None

def setup_ipfs_client():
    """Настраиваем глобальный асинхронный IPFS клиент"""
    global ipfs_client
    
    # Пробуем разные порты для IPFS API
    ipfs_ports = [5001, 5101, 8080]  # Стандартный, ваш текущий, альтернативный
    
    for port in ipfs_ports:
        try:
            print(f"🔄 Настраиваем асинхронный IPFS клиент для порта {port}")
            ipfs_client = aioipfs.AsyncIPFS(host='127.0.0.1', port=port)
            print(f"✅ IPFS клиент настроен для порта {port}")
            return ipfs_client
        except Exception as e:
            print(f"❌ Ошибка настройки для порта {port}: {e}")
            continue
    
    print("⚠️ Не удалось настроить IPFS клиент ни для одного порта")
    return None

async def subscribe():
    global ipfs_client
    
    # Настраиваем IPFS клиент при запуске
    print("🚀 Запуск системы с IPFS клиентом...")
    ipfs_client = setup_ipfs_client()
    
    if ipfs_client:
        print("✅ IPFS клиент успешно настроен")
        print("📋 IPFS клиент готов к асинхронным операциям")
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

async def cleanup():
    """Корректно закрываем IPFS клиент"""
    global ipfs_client
    if ipfs_client:
        try:
            # Проверяем, что это AsyncIPFS объект
            if hasattr(ipfs_client, 'disconnect'):
                await ipfs_client.disconnect()
                print("✅ IPFS клиент отключен")
            else:
                print("⚠️ IPFS клиент не поддерживает disconnect")
        except Exception as e:
            print(f"⚠️ Ошибка при отключении IPFS клиента: {e}")

# Run the subscribe function
if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(subscribe())
    except KeyboardInterrupt:
        print("\n🛑 Остановка по запросу пользователя")
        asyncio.get_event_loop().run_until_complete(cleanup())
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        asyncio.get_event_loop().run_until_complete(cleanup())