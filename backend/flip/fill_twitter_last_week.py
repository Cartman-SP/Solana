import asyncio
import os
import sys
import django
from datetime import datetime, timedelta, timezone
from typing import List, Optional

# Ensure paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # backend dir
sys.path.append(os.path.dirname(__file__))  # flip dir to import process_twitter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from asgiref.sync import sync_to_async
from mainapp.models import Token, Twitter

# Reuse the TokenProcessor from process_twitter.py
from process_twitter import TokenProcessor


async def get_last_week_tokens_without_twitter(limit: Optional[int] = None) -> List[Token]:
    """Get tokens created in the last 7 days that have community_id but no Twitter linked."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    queryset = Token.objects.filter(
        created_at__gte=week_ago,
        community_id__isnull=False,
        community_id__gt="",
        twitter__isnull=True,
    ).order_by("-created_at")
    if limit:
        queryset = queryset[:limit]
    return await sync_to_async(list)(queryset)


async def process_tokens_last_week(limit_per_batch: int = 50) -> None:
    """Resolve and attach Twitter for last-week tokens with community_id and no twitter."""
    async with TokenProcessor() as processor:
        while True:
            tokens = await get_last_week_tokens_without_twitter(limit_per_batch)
            if not tokens:
                print("📭 Нет подходящих токенов за последнюю неделю")
                await asyncio.sleep(30)
                continue

            print(f"🚀 Найдено {len(tokens)} токенов для обработки (последняя неделя)")
            for index, token in enumerate(tokens, 1):
                print(f"\n--- Токен {index}/{len(tokens)} ---")
                print(f"🔍 {token.name} ({token.symbol}) | mint={token.address}")
                print(f"community_id={token.community_id}")

                community_id = token.community_id
                if not community_id:
                    print("❌ community_id отсутствует, пропускаю")
                    continue

                username = await processor.get_twitter_username(community_id)
                if username:
                    twitter: Optional[Twitter] = await processor.create_or_get_twitter(username)
                    if twitter:
                        await processor.update_token_twitter(token, twitter)
                        await processor.mark_token_processed(token, twitter_got=True, processed=False)
                        print(f"✅ Привязан Twitter {username}")
                    else:
                        print("❌ Не удалось создать/получить Twitter запись")
                        await processor.mark_token_processed(token, twitter_got=True, processed=False)
                else:
                    print("❌ Twitter username не найден")
                    await processor.mark_token_processed(token, twitter_got=True, processed=False)

                await asyncio.sleep(0.2)

            print("\n✅ Батч за последнюю неделю обработан, жду 30 секунд...")
            await asyncio.sleep(30)


async def main():
    print("🚀 Запуск обработки твиттера для токенов за последнюю неделю...")
    await process_tokens_last_week(limit_per_batch=50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Остановка по запросу пользователя")

