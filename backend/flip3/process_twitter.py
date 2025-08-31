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
from mainapp.models import Token

# Константы для ограничения нагрузки
MAX_CONCURRENT_REQUESTS = 15
REQUEST_DELAY = 1  # 100ms между запросами
IPFS_GATEWAY = "http://205.172.58.34/ipfs/"
IRYS_NODES = [
    "https://node1.irys.xyz/",
    "https://node2.irys.xyz/"
]

class TokenProcessor:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
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
        """Получить батч токенов с twitter_got = False"""
        tokens = await sync_to_async(list)(
            Token.objects.filter(twitter_got=False)[:limit]
        )
        return tokens
    
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
        
        # Выводим результат
        if metadata:
            print(f"📊 Метаданные: {metadata}")
        else:
            print("❌ Метаданные не получены (None)")
    
    async def process_batch(self, batch_size: int = 20):
        """Обработать батч токенов"""
        print(f"🚀 Начинаю обработку батча из {batch_size} токенов...")
        
        # Получаем токены
        tokens = await self.get_tokens_batch(batch_size)
        
        if not tokens:
            print("📭 Нет токенов для обработки")
            return
        
        print(f"📋 Найдено {len(tokens)} токенов для обработки")
        
        # Обрабатываем токены последовательно для контроля нагрузки
        for i, token in enumerate(tokens, 1):
            print(f"\n--- Токен {i}/{len(tokens)} ---")
            await self.process_token(token)
            
            # Дополнительная задержка между токенами
            if i < len(tokens):
                await asyncio.sleep(0.5)
        
        print(f"\n✅ Обработка батча завершена!")

async def main():
    """Основная функция"""
    print("🚀 Запуск процессора токенов...")
    
    async with TokenProcessor() as processor:
        while True:
            try:
                await processor.process_batch(20)
                print("\n⏳ Ожидание 30 секунд перед следующим батчем...")
                await asyncio.sleep(30)
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
