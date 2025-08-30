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
          print(f"Получен mint: {mint}")
          
          # Проверяем, существует ли токен
          token_exists = await sync_to_async(Token.objects.filter(address=mint).exists)()
          
          if token_exists:
              # Если токен существует, обновляем его
              await sync_to_async(Token.objects.filter(address=mint).update)(migrated=True)
              print(f"Токен {mint} обновлен (migrated=True)")
          else:
              # Если токена нет, создаем новый
              new_token = await sync_to_async(Token.objects.create)(
                  address=mint,
                  migrated=True,
                  created_at=timezone.now()
              )
              print(f"Создан новый токен: {mint}")
              
        except Exception as e:
          print(f"Ошибка при обработке mint {mint}: {e}")

# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())

