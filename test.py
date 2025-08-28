import asyncio
import websockets
import json

async def subscribe():
  uri = "wss://pumpportal.fun/api/data"
  async with websockets.connect(uri) as websocket:
      
      # Subscribing to token creation events
      payload = {
          "method": "subscribeNewToken",
      }
      await websocket.send(json.dumps(payload))

      # Subscribing to migration events
      payload = {
          "method": "subscribeMigration",
      }
      await websocket.send(json.dumps(payload))


      # Subscribing to trades on tokens
      payload = {
          "method": "subscribeTokenTrade",
          "keys": ["6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"]  # array of token CAs to watch
      }
      await websocket.send(json.dumps(payload))
      
      async for message in websocket:
          print(json.loads(message))

# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())