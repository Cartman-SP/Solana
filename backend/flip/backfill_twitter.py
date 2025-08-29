import asyncio
import os
import sys
import django
import aiohttp

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from asgiref.sync import sync_to_async
from mainapp.models import Token, Twitter

# Переиспользуем готовые утилиты получения твиттера по community_id
from flip.pumpfun import ensure_twitter_name


async def fetch_and_attach_twitter(session: aiohttp.ClientSession, token_id: int, community_id: str) -> bool:
    """Для одного токена: дожидается twitter по community_id и привязывает к Token.

    Возвращает True, если твиттер был найден и привязан впервые.
    """
    try:
        username, followers = await ensure_twitter_name(session, community_id, timeout_seconds=60.0)
        if not username:
            return False

        handle = f"@{username}"

        # Получаем/создаём Twitter по имени
        twitter_obj, _ = await sync_to_async(Twitter.objects.get_or_create)(
            name=handle,
        )

        # Если в чёрном списке — не привязываем
        if twitter_obj.blacklist:
            return False

        # Обновляем счётчик токенов у твиттера один раз при первой привязке
        def _attach():
            try:
                token = Token.objects.select_related('twitter').get(id=token_id)
                if token.twitter_id:
                    return False
                token.twitter = twitter_obj
                token.save(update_fields=['twitter'])
                twitter_obj.total_tokens += 1
                twitter_obj.save(update_fields=['total_tokens'])
                return True
            except Token.DoesNotExist:
                return False

        attached = await sync_to_async(_attach)()
        return attached

    except Exception as e:
        print(f"backfill[{token_id}] error: {e}")
        return False


async def main():
    session = aiohttp.ClientSession()
    try:
        # Ищем токены с проставленным community_id и без привязанного твиттера
        def _fetch_ids():
            qs = (
                Token.objects
                .filter(community_id__isnull=False)
                .exclude(community_id="")
                .filter(twitter__isnull=True)
                .values_list('id', 'community_id')
            )
            return list(qs)

        items = await sync_to_async(_fetch_ids)()
        total = len(items)
        print(f"Found {total} tokens to backfill")

        attached_count = 0
        for idx, (token_id, community_id) in enumerate(items, start=1):
            ok = await fetch_and_attach_twitter(session, token_id, community_id)
            if ok:
                attached_count += 1
            if idx % 10 == 0 or ok:
                print(f"Progress: {idx}/{total}, attached: {attached_count}")

        print(f"Done. Attached twitter for {attached_count} tokens")

    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())

