import os
import sys
import django
import asyncio
import aiohttp
from typing import Optional, List

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from asgiref.sync import sync_to_async
from mainapp.models import Token, Twitter

TW_API_KEY = "8879aa53d815484ebea0313718172fea"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

DEX_BASE = "https://api.dexscreener.com/latest/dex/pairs/solana"


def extract_community_id_from_dex(dex_response: dict) -> Optional[str]:
  try:
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


async def fetch_dex_info(session: aiohttp.ClientSession, pair_id: str) -> Optional[dict]:
  try:
    url = f"{DEX_BASE}/{pair_id}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
      if resp.status == 200:
        return await resp.json()
      return None
  except Exception:
    return None


async def get_tokens_to_process(limit: int = 200) -> List[Token]:
  def _qs():
    return list(
      Token.objects.filter(
        migrated=True,
        twitter__isnull=True
      ).filter(
        models.Q(community_id__isnull=True) | models.Q(community_id="")
      ).exclude(bonding_curve__isnull=True).exclude(bonding_curve="")
      .order_by('-created_at')
    )
  from django.db import models
  return await sync_to_async(_qs)()


async def process_token(session: aiohttp.ClientSession, token: Token):
  try:
    pair_id = token.bonding_curve
    if not pair_id:
      return

    dex_data = await fetch_dex_info(session, pair_id)
    if not dex_data:
      print(f"DexScreener не вернул данные для {pair_id}")
      return

    community_id = extract_community_id_from_dex(dex_data)
    if not community_id:
      return

    await sync_to_async(Token.objects.filter(id=token.id).update)(community_id=community_id)

    username = await get_twitter_username(session, community_id)
    if not username:
      print(f"Не удалось получить Twitter username по community_id {community_id} для {token.address}")
      return

    twitter, _ = await sync_to_async(Twitter.objects.get_or_create)(name=username)
    await sync_to_async(Token.objects.filter(id=token.id).update)(twitter=twitter, twitter_got=True)
    print(f"Твиттер {username} привязан к токену {token.address}")
  except Exception as e:
    print(f"Ошибка обработки токена {token.address}: {e}")


async def main():
  print("Запуск бэкапа community/twitter для мигрированных токенов без community...")
  async with aiohttp.ClientSession() as session:
    while True:
      tokens = await get_tokens_to_process(200)
      if not tokens:
        print("Нет токенов для обработки. Завершаю.")
        break
      print(f"Найдено {len(tokens)} токенов для обработки")
      for idx, token in enumerate(tokens, 1):
        await process_token(session, token)
        await asyncio.sleep(0.2)


if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("Остановка по запросу пользователя")

