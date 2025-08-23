import os
import sys
import django
from datetime import datetime

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Twitter, Token
from asgiref.sync import sync_to_async
import asyncio

async def get_twitter_data_and_update(twitter_obj):
    """Получает данные Twitter и обновляет ath и total_trans в базе данных"""
    try:
        # Получаем последние 3 токена с processed = True
        recent_dev_tokens = await sync_to_async(list)(
            Token.objects.filter(
                twitter=twitter_obj,
                processed=True
            ).order_by('-created_at')[:3]
        )
        
        # Рассчитываем средний ATH
        if recent_dev_tokens:
            avg_ath = sum(token.ath for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_ath = 0
            
        # Рассчитываем средний total_trans по тем же последним токенам
        if recent_dev_tokens:
            avg_total_trans = sum(token.total_trans for token in recent_dev_tokens) / len(recent_dev_tokens)
        else:
            avg_total_trans = 0

        # Обновляем данные в базе
        twitter_obj.ath = int(avg_ath)
        twitter_obj.total_trans = int(avg_total_trans)
        await sync_to_async(twitter_obj.save)()
        
        recent_tokens_info = []
        for token in recent_dev_tokens:
            recent_tokens_info.append({
                'name': token.address[:4] + '...' + token.address[-4:],  
                'ath': token.ath,
                'total_trans': token.total_trans
            })
            
        return {
            'name': twitter_obj.name,
            'ath': int(avg_ath),
            'total_trans': int(avg_total_trans),
            'total_tokens': max(1, twitter_obj.total_tokens),
            'whitelist': twitter_obj.whitelist,
            'blacklist': twitter_obj.blacklist,
            'recent_tokens': recent_tokens_info
        }
    except Exception as e:
        print(f"Ошибка при обработке Twitter {twitter_obj.name}: {e}")
        return None

async def process_all_twitter_accounts():
    """Обрабатывает все Twitter аккаунты в базе данных"""
    try:
        # Получаем все Twitter аккаунты
        all_twitter = await sync_to_async(list)(Twitter.objects.all())
        
        print(f"Найдено {len(all_twitter)} Twitter аккаунтов для обработки")
        print("=" * 80)
        
        processed_count = 0
        error_count = 0
        
        for twitter_obj in all_twitter:
            try:
                result = await get_twitter_data_and_update(twitter_obj)
                if result:
                    print(f"✅ {result['name']} | ATH: {result['ath']} | Total Trans: {result['total_trans']} | Tokens: {result['total_tokens']}")
                    processed_count += 1
                else:
                    print(f"❌ {twitter_obj.name} | Ошибка обработки")
                    error_count += 1
            except Exception as e:
                print(f"❌ {twitter_obj.name} | Ошибка: {e}")
                error_count += 1
        
        print("=" * 80)
        print(f"Обработка завершена:")
        print(f"✅ Успешно обработано: {processed_count}")
        print(f"❌ Ошибок: {error_count}")
        print(f"📊 Всего аккаунтов: {len(all_twitter)}")
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")

async def main():
    """Главная функция"""
    print("🚀 Запуск обработки всех Twitter аккаунтов...")
    print(f"⏰ Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    await process_all_twitter_accounts()
    
    print("=" * 80)
    print(f"⏰ Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🏁 Обработка завершена!")

if __name__ == "__main__":
    asyncio.run(main()) 