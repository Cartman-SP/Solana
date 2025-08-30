import asyncio
import websockets
import json
from create import *

async def subscribe():
    uri = "wss://pumpportal.fun/api/data"
    async with websockets.connect(uri) as websocket:
      
        # Subscribing to token creation events
        payload = {
            "method": "subscribeNewToken",
        }
        await websocket.send(json.dumps(payload))

        
        async for message in websocket:
            data = json.loads(message)
            try:
                if'uri' in data:
                    asyncio.create_task(process_create(data))
            except:
                pass
        

# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())