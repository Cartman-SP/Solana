import asyncio
import aiohttp
import os
import sys
import django
import re
from typing import Optional, List
import time

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from asgiref.sync import sync_to_async
from mainapp.models import Token, Twitter

# Константы для ограничения нагрузки
MAX_CONCURRENT_REQUESTS = 20
REQUEST_DELAY = 1  # 100ms между запросами
IPFS_GATEWAY = "http://205.172.58.34/ipfs/"
IRYS_NODES = [
    "https://node1.irys.xyz/",
    "https://node2.irys.xyz/",
    "https://uploader.irys.xyz/"
]

# Telegram константы
TELEGRAM_BOT_TOKEN = "8354390669:AAEtYDTTfEkPp7Bc-QvlOhNp5Vn6fs0a9pg"
TELEGRAM_USER_IDS = [612594627, 784111198]
MAX_RETRIES = 3

# Twitter API константы
TW_API_KEY = "new1_cdb5e73eb7174341be73ad05d22d69d9"
TW_BASE = "https://api.twitterapi.io"
TW_HEADERS = {"X-API-Key": TW_API_KEY}

class TokenProcessor:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.token_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            connector=aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_tokens_batch(self, limit: int = 20) -> List[Token]:
        """Получить батч токенов с twitter_got = False, отсортированных по дате создания (новые сначала)"""
        tokens = await sync_to_async(list)(
            Token.objects.filter(twitter_got=False).order_by('-created_at')[:limit]
        )
        return tokens
    
    async def get_twitter_username(self, community_id: str) -> Optional[str]:
        """Получить Twitter username из community_id"""
        try:
            # Пробуем получить информацию о community
            url = f"{TW_BASE}/twitter/community/info"
            params = {"community_id": community_id}
            
            async with self.session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    community_info = data.get("community_info", {})
                    
                    # Ищем username в creator или first_member
                    for user_key in ["creator", "first_member"]:
                        user_data = community_info.get(user_key, {})
                        username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
                        if username:
                            print(f"✅ Найден Twitter username: @{username} из {user_key}")
                            return f"@{username}"
            
            # Если не нашли в info, пробуем через members
            url = f"{TW_BASE}/twitter/community/members"
            params = {"community_id": community_id, "limit": 1}
            
            async with self.session.get(url, headers=TW_HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Ищем в разных структурах ответа
                    members = []
                    for key in ["members", "data", "users"]:
                        if key in data and isinstance(data[key], list):
                            members.extend(data[key])
                    
                    if members:
                        user_data = members[0]
                        username = user_data.get("screen_name") or user_data.get("userName") or user_data.get("username")
                        if username:
                            print(f"✅ Найден Twitter username: @{username} из members")
                            return f"@{username}"
            
            print(f"❌ Twitter username не найден для community {community_id}")
            return None
            
        except Exception as e:
            print(f"❌ Ошибка при получении Twitter username: {e}")
            return None
    
    async def create_or_get_twitter(self, username: str) -> Optional[Twitter]:
        """Создать или получить Twitter запись"""
        try:
            twitter, created = await sync_to_async(Twitter.objects.get_or_create)(name=username)
            if created:
                print(f"✅ Создана новая Twitter запись: {username}")
            else:
                print(f"✅ Найдена существующая Twitter запись: {username}")
            return twitter
        except Exception as e:
            print(f"❌ Ошибка при создании/получении Twitter: {e}")
            return None
    
    async def send_telegram_notification(self, token_mint: str,uri: str) -> None:
        """Отправить уведомление в Telegram о проблеме с метаданными"""
        message = f"проблема с метой, {uri}, https://trade.padre.gg/trade/solana/{token_mint}"
        
        for user_id in TELEGRAM_USER_IDS:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                data = {
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                
                async with self.session.post(url, json=data) as response:
                    if response.status == 200:
                        print(f"📱 Telegram уведомление отправлено пользователю {user_id}")
                    else:
                        print(f"❌ Ошибка отправки Telegram уведомления пользователю {user_id}: {response.status}")
                        
            except Exception as e:
                print(f"❌ Ошибка при отправке Telegram уведомления пользователю {user_id}: {e}")
    
    async def increment_retries(self, token: Token) -> None:
        """Увеличить счетчик попыток обработки токена"""
        try:
            new_retries = token.retries + 1
            await sync_to_async(Token.objects.filter(id=token.id).update)(retries=new_retries)
            print(f"🔄 Попытка {new_retries}/{MAX_RETRIES} для токена {token.name}")
            
            # Если достигнут лимит попыток, отправляем уведомление в Telegram
            if new_retries >= MAX_RETRIES:
                print(f"🚨 Достигнут лимит попыток для токена {token.name}, отправляю уведомление в Telegram")
                await self.send_telegram_notification(token.address,token.uri)
                
        except Exception as e:
            print(f"❌ Ошибка при увеличении счетчика попыток: {e}")
    
    def extract_ipfs_hash(self, uri: str) -> Optional[str]:
        """Извлечь IPFS хеш из URI"""
        ipfs_patterns = [
            r'https://ipfs\.io/ipfs/([a-zA-Z0-9]+)',
            r'https://gateway\.pinata\.cloud/ipfs/([a-zA-Z0-9]+)'
        ]
        
        for pattern in ipfs_patterns:
            match = re.search(pattern, uri)
            if match:
                return match.group(1)
        return None
    
    def is_irys_uri(self, uri: str) -> bool:
        """Проверить, является ли URI Irys ссылкой"""
        return 'irys' in uri.lower()
    
    async def fetch_metadata(self, url: str, description: str = "") -> Optional[dict]:
        """Получить метаданные с ограничением нагрузки"""
        async with self.semaphore:
            try:
                print(f"Запрос к {description}: {url}")
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Успешно получены метаданные от {description}")
                        return data
                    else:
                        print(f"❌ Ошибка {response.status} от {description}")
                        return None
            except Exception as e:
                print(f"❌ Ошибка при запросе к {description}: {e}")
                return None
            finally:
                # Задержка для предотвращения дудоса
                await asyncio.sleep(REQUEST_DELAY)
    
    async def process_ipfs_uri(self, uri: str) -> Optional[dict]:
        """Обработать IPFS URI через приватный шлюз"""
        ipfs_hash = self.extract_ipfs_hash(uri)
        if not ipfs_hash:
            return None
        
        gateway_url = f"{IPFS_GATEWAY}{ipfs_hash}"
        return await self.fetch_metadata(gateway_url, f"IPFS шлюз ({ipfs_hash})")
    
    async def process_irys_uri(self, uri: str) -> Optional[dict]:
        """Обработать Irys URI через оба узла"""
        # Извлекаем путь из URI
        if 'irys.xyz' in uri:
            path = uri.split('irys.xyz/')[-1] if 'irys.xyz/' in uri else ''
        else:
            path = uri.split('/')[-1] if '/' in uri else ''
        
        if not path:
            return None
        
        # Пробуем оба узла параллельно
        tasks = []
        for i, node in enumerate(IRYS_NODES):
            node_url = f"{node}{path}"
            task = self.fetch_metadata(node_url, f"Irys node{i+1}")
            tasks.append(task)
        
        # Ждем первый успешный ответ
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, dict):
                print(f"✅ Получены метаданные от Irys node{i+1}")
                return result
        
        return None
    
    async def process_regular_uri(self, uri: str) -> Optional[dict]:
        """Обработать обычный URI"""
        return await self.fetch_metadata(uri, "обычный URI")
    
    async def process_token(self, token: Token) -> None:
        """Обработать один токен"""
        print(f"\n🔍 Обрабатываю токен: {token.name} ({token.symbol})")
        print(f"URI: {token.uri}")
        print(f"🔄 Попытки: {token.retries}/{MAX_RETRIES}")
        
        if not token.uri:
            print("❌ URI отсутствует")
            return
        
        metadata = None
        
        # Определяем тип URI и обрабатываем соответственно
        if self.extract_ipfs_hash(token.uri):
            print("📁 Обнаружен IPFS URI, использую приватный шлюз")
            metadata = await self.process_ipfs_uri(token.uri)
        elif self.is_irys_uri(token.uri):
            print("🌐 Обнаружен Irys URI, использую оба узла")
            metadata = await self.process_irys_uri(token.uri)
        else:
            print("🔗 Обычный URI, прямой запрос")
            metadata = await self.process_regular_uri(token.uri)
            if not metadata:
                community_id = await self.fallback_community_id_from_pumpfun(token.address)
        
        
        if metadata:
            print(f"📊 Метаданные: {metadata}")
            # Ищем community_id в метаданных
            community_id = self.extract_community_id(metadata)
            if not community_id:
                print("❌ Community ID не найден в метаданных, пробую через pump.fun API")
                community_id = await self.fallback_community_id_from_pumpfun(token.address)

            if community_id:
                print(f"🏘️ Community ID: {community_id}")
                # Сохраняем community_id в базу данных
                await self.save_community_id(token, community_id)
                
                # Пытаемся получить Twitter username
                try:
                    twitter_username = await self.get_twitter_username(community_id)
                    if twitter_username:
                        # Создаем или получаем Twitter запись
                        twitter = await self.create_or_get_twitter(twitter_username)
                        if twitter:
                            # Обновляем токен с Twitter
                            await self.update_token_twitter(token, twitter)
                            print(f"✅ Twitter обновлен для токена: {twitter_username}")
                        else:
                            print(f"❌ Не удалось создать/получить Twitter запись для {twitter_username}")
                            # Community найден, но Twitter не удалось создать - помечаем как обработанный
                            print(f"💾 Community ID сохранен, но Twitter не найден - помечаю как обработанный")
                            await self.mark_token_processed(token, twitter_got=True, processed=True)
                    else:
                        print(f"❌ Twitter username не найден для community {community_id}")
                        # Community найден, но Twitter не найден - помечаем как обработанный
                        print(f"💾 Community ID сохранен, но Twitter не найден - помечаю как обработанный")
                        await self.mark_token_processed(token, twitter_got=True, processed=True)
                except Exception as e:
                    print(f"❌ Ошибка при получении Twitter username: {e}")
                    # Community найден, но произошла ошибка при получении Twitter - помечаем как обработанный
                    print(f"💾 Community ID сохранен, но произошла ошибка при получении Twitter - помечаю как обработанный")
                    await self.mark_token_processed(token, twitter_got=True, processed=True)
            else:
                print("❌ Community ID не найден ни в метаданных, ни через pump.fun API")
                # Если community_id не найден, помечаем как полностью обработанный
                await self.mark_token_processed(token, twitter_got=True, processed=True)
        else:
            print("❌ Метаданные не получены (None)")
            # Увеличиваем счетчик попыток
            await self.increment_retries(token)
            
            # Если достигнут лимит попыток, помечаем как полностью обработанный
            if token.retries >= MAX_RETRIES:
                print(f"🚨 Токен {token.name} достиг лимита попыток, помечаю как полностью обработанный")
                await self.mark_token_processed(token, twitter_got=True, processed=True)
            else:
                print(f"⚠️ Токен {token.name} остается в очереди для повторной обработки")
    
    def extract_community_id(self, metadata: dict) -> Optional[str]:
        """Извлечь community_id только из ссылок вида https://x.com/i/communities/<digits>/.

        Проходим по всем строковым значениям метаданных и ищем шаблон с числовым идентификатором.
        """
        if not isinstance(metadata, dict):
            return None

        pattern = re.compile(r"https?://(?:www\.)?x\.com/i/communities/(\d+)/?", re.IGNORECASE)

        def scan_string(value: str) -> Optional[str]:
            match = pattern.search(value)
            if match:
                cid = match.group(1)
                print(f"✅ Извлечен community_id из x.com ссылки: {cid}")
                return cid
            return None

        def walk(node) -> Optional[str]:
            if isinstance(node, dict):
                for v in node.values():
                    res = walk(v)
                    if res:
                        return res
            elif isinstance(node, list):
                for v in node:
                    res = walk(v)
                    if res:
                        return res
            elif isinstance(node, str):
                return scan_string(node)
            return None

        print("🔍 Ищу ссылку x.com/i/communities/<digits>/ в метаданных...")
        return walk(metadata)

    async def fetch_pumpfun_coin(self, mint: str) -> Optional[dict]:
        """Запросить coin-информацию с pump.fun (frontend API)."""
        url = f"https://frontend-api-v3.pump.fun/coins/{mint}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiohttp-client",
            "Accept-Language": "ru,en;q=0.9",
        }
        async with self.semaphore:
            try:
                async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as response:
                    if response.status == 200:
                        return await response.json()
                    print(f"❌ pump.fun API вернул статус {response.status} для {mint}")
                    return None
            except Exception as e:
                print(f"❌ Ошибка запроса к pump.fun API: {e}")
                return None
            finally:
                await asyncio.sleep(REQUEST_DELAY)

    def extract_community_id_from_obj(self, obj) -> Optional[str]:
        """Извлечь community_id из любого объекта, ища только по путям /community/<id> или /communities/<id>."""
        patterns = (
            r"/communities/([A-Za-z0-9_-]+)",
            r"/community/([A-Za-z0-9_-]+)",
        )

        def scan_string(value: str) -> Optional[str]:
            for pattern in patterns:
                m = re.search(pattern, value)
                if m:
                    return m.group(1)
            return None

        def walk(node) -> Optional[str]:
            if isinstance(node, dict):
                for _, v in node.items():
                    res = walk(v)
                    if res:
                        return res
            elif isinstance(node, list):
                for v in node:
                    res = walk(v)
                    if res:
                        return res
            elif isinstance(node, str):
                return scan_string(node)
            return None

        return walk(obj)

    async def fallback_community_id_from_pumpfun(self, mint: str) -> Optional[str]:
        """Фолбэк: получить community_id через pump.fun API."""
        data = await self.fetch_pumpfun_coin(mint)
        if not data:
            return None
        cid = self.extract_community_id_from_obj(data)
        if cid:
            print(f"✅ Найден community_id через pump.fun API: {cid}")
        return cid
    
    async def save_community_id(self, token: Token, community_id: str) -> None:
        """Сохранить community_id в базу данных"""
        try:
            await sync_to_async(Token.objects.filter(id=token.id).update)(
                community_id=community_id
            )
            print(f"💾 Community ID сохранен в базу: {community_id}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении community_id: {e}")
    
    async def update_token_twitter(self, token: Token, twitter: Twitter) -> None:
        """Обновить токен с Twitter записью"""
        try:
            await sync_to_async(Token.objects.filter(id=token.id).update)(
                twitter=twitter
            )
            print(f"💾 Twitter обновлен для токена: {twitter.name}")
        except Exception as e:
            print(f"❌ Ошибка при обновлении Twitter: {e}")
    
    async def mark_token_processed(self, token: Token, twitter_got: bool = True, processed: bool = False) -> None:
        """Пометить токен как обработанный"""
        try:
            update_data = {'twitter_got': twitter_got}
            if processed:
                update_data['processed'] = True
            
            await sync_to_async(Token.objects.filter(id=token.id).update)(**update_data)
            
            if processed:
                print(f"✅ Токен помечен как полностью обработанный (twitter_got=True, processed=True)")
            else:
                print(f"✅ Токен помечен как обработанный для twitter (twitter_got=True)")
                
        except Exception as e:
            print(f"❌ Ошибка при пометке токена: {e}")
    
    async def process_batch(self, batch_size: int = 200):
        """Обработать батч токенов параллельно"""
        print(f"🚀 Начинаю обработку батча из {batch_size} токенов...")
        
        # Получаем токены
        tokens = await self.get_tokens_batch(batch_size)
        
        if not tokens:
            print("📭 Нет токенов для обработки")
            return
        
        print(f"📋 Найдено {len(tokens)} токенов для обработки")
        
        # Создаем задачи с ограничением одновременной обработки токенов
        async def process_with_limit(t: Token):
            async with self.token_semaphore:
                await self.process_token(t)

        tasks = []
        for i, token in enumerate(tokens, 1):
            print(f"📝 Создаю задачу для токена {i}/{len(tokens)}: {token.name}")
            task = asyncio.create_task(process_with_limit(token))
            tasks.append(task)
        
        print(f"🔄 Запускаю параллельную обработку {len(tasks)} токенов...")
        
        # Ждем завершения всех задач с обработкой ошибок
        completed_count = 0
        failed_count = 0
        
        try:
            # Используем asyncio.as_completed для отслеживания прогресса
            for coro in asyncio.as_completed(tasks):
                try:
                    await coro
                    completed_count += 1
                    print(f"✅ Завершено: {completed_count}/{len(tasks)} токенов")
                except Exception as e:
                    failed_count += 1
                    print(f"❌ Ошибка при обработке токена: {e}")
                    print(f"⚠️ Ошибок: {failed_count}/{len(tasks)} токенов")
        except Exception as e:
            print(f"❌ Критическая ошибка в параллельной обработке: {e}")
        
        print(f"\n✅ Обработка батча завершена!")
        print(f"📊 Статистика: {completed_count} успешно, {failed_count} с ошибками из {len(tokens)} токенов")

async def main():
    """Основная функция"""
    print("🚀 Запуск процессора токенов...")
    
    async with TokenProcessor() as processor:
        while True:
            try:
                await processor.process_batch(20)
                print("\n⏳ Ожидание 30 секунд перед следующим батчем...")
                await asyncio.sleep(5)
            except KeyboardInterrupt:
                print("\n🛑 Остановка по запросу пользователя")
                break
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Программа остановлена")
