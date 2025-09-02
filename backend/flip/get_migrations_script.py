import asyncio
import websockets
import json
import os
import sys
import django
import asyncio
import aiohttp
import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q
from typing import Dict, List, Optional, Tuple
import time

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token, Twitter
from asgiref.sync import sync_to_async

TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

DEX_BASE = "https://api.dexscreener.com/latest/dex/pairs/solana"

async def get_twitter_username(session: aiohttp.ClientSession, community_id: str) -> Optional[str]:
  try:
    url = f"{TW_BASE}/twitter/community/info"
    params = {"community_id": community_id}
    async with session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
      if response.status == 200:
        data = await response.json()
        community_info = data.get("community_info", {})
        for user_key in ["creator", "first_member"]:
          user_data = community_info.get(user_key, {})
          username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
          if username:
            return f"@{username}"
    # fallback через members
    url = f"{TW_BASE}/twitter/community/members"
    params = {"community_id": community_id, "limit": 1}
    async with session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
      if response.status == 200:
        data = await response.json()
        members = []
        for key in ["members", "data", "users"]:
          if key in data and isinstance(data[key], list):
            members.extend(data[key])
        if members:
          user_data = members[0]
          username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
          if username:
            return f"@{username}"
    return None
  except Exception:
    return None

def extract_community_id_from_dex(dex_response: dict) -> Optional[str]:
  try:
    # В ответе может быть ключ pairs (список) и/или pair (объект)
    candidates = []
    if isinstance(dex_response.get("pairs"), list):
      candidates.extend(dex_response.get("pairs", []))
    if isinstance(dex_response.get("pair"), dict):
      candidates.append(dex_response.get("pair"))

    for item in candidates:
      info = item.get("info", {}) if isinstance(item, dict) else {}
      socials = info.get("socials", []) if isinstance(info, dict) else []
      for social in socials:
        url = (social or {}).get("url", "")
        if isinstance(url, str) and "communities" in url.lower():
          parts = url.rstrip("/").split("/")
          if parts:
            community_id = parts[-1].strip()
            community_id = community_id.strip('.,;:!?()[]{}"\'')
            if community_id:
              return community_id
    return None
  except Exception:
    return None

async def fetch_dex_info(session: aiohttp.ClientSession, pair_id: str) -> Optional[dict]:
  try:
    url = f"{DEX_BASE}/{pair_id}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
      if resp.status == 200:
        return await resp.json()
      return None
  except Exception:
    return None

async def subscribe():
  uri = "wss://pumpportal.fun/api/data"
  async with websockets.connect(uri) as websocket:
      payload = {
          "method": "subscribeMigration",
      }
      await websocket.send(json.dumps(payload))
      
      
      async with aiohttp.ClientSession() as http_session:
        async for message in websocket:
        try:
          data = json.loads(message)
          mint = data.get('mint')
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
          
          # Дополнительно: если у токена нет твиттера, пытаемся получить через DexScreener -> community -> Twitter
          token = await sync_to_async(Token.objects.select_related('twitter').get)(address=mint)
          has_twitter = getattr(token, 'twitter_id', None) is not None
          if not has_twitter:
            pair_id = data.get('bondingCurveKey')
            if pair_id:
              dex_data = await fetch_dex_info(http_session, pair_id)
              community_id = extract_community_id_from_dex(dex_data or {}) if dex_data else None
              if community_id:
                # сохраним community_id для токена
                await sync_to_async(Token.objects.filter(id=token.id).update)(community_id=community_id)
                username = await get_twitter_username(http_session, community_id)
                if username:
                  twitter, _ = await sync_to_async(Twitter.objects.get_or_create)(name=username)
                  await sync_to_async(Token.objects.filter(id=token.id).update)(twitter=twitter)
                  print(f"Твиттер {username} привязан к токену {mint}")
                else:
                  print(f"Не удалось получить Twitter username по community_id {community_id}")
              else:
                print("В DexScreener не найден community_id в socials")
            else:
              print("В сообщении отсутствует bondingCurveKey для получения pairId")
              
        except Exception as e:
          print(f"Ошибка при обработке mint {mint}: {e}")

# Run the subscribe function
asyncio.get_event_loop().run_until_complete(subscribe())

