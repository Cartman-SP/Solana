import asyncio
import websockets
import json
import os
import sys
import django
import asyncio
import aiohttp
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from typing import Dict, List, Optional, Tuple
import time

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token
from asgiref.sync import sync_to_async

async def subscribe():
  uri = "wss://pumpportal.fun/api/data"
  async with websockets.connect(uri) as websocket:
      payload = {
          "method": "subscribeMigration",
      }
      await websocket.send(json.dumps(payload))

      
      async for message in websocket:
        try:
          mint = json.loads(message).get('mint')
          print(mint)
          await sync_to_async(Token.objects.filter(address=mint).update)(migrated=True)
        except Exception as e:
          print(e)

# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())

