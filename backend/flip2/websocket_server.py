import asyncio
import websockets
import json

# Хранилище всех подключенных клиентов
connected_clients = set()

async def handler(websocket,path):
    """Обработчик веб-сокет соединений"""
    connected_clients.add(websocket)
    
    try:
        async for message in websocket:
            # Отправляем сообщение всем подключенным клиентам
            await broadcast_message(message)
            
    except:
        pass
    finally:
        connected_clients.discard(websocket)

async def broadcast_message(message):
    """Отправляет сообщение всем подключенным клиентам"""
    if not connected_clients:
        return
        
    disconnected_clients = set()
    for client in connected_clients:
        try:
            await client.send(message)
        except:
            disconnected_clients.add(client)
    
    # Удаляем отключенных клиентов
    connected_clients.difference_update(disconnected_clients)

async def main():
    """Запуск веб-сокет сервера"""
    async with websockets.serve(
        handler,
        "localhost",
        9393,
        ping_interval=20,
        ping_timeout=30,
        close_timeout=5,
        max_size=None,
    ):
        await asyncio.Future()  # Бесконечный цикл

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass 
