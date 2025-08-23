import os
import sys
import django
from datetime import datetime

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token, Twitter
from asgiref.sync import sync_to_async
import asyncio

async def clean_empty_twitter_tokens():
    """Очищает токены с пустым Twitter именем '@'"""
    try:
        # Находим все токены с Twitter именем "@"
        empty_twitter_tokens = await sync_to_async(list)(
            Token.objects.filter(twitter__name="@")
        )
        
        print(f"Найдено {len(empty_twitter_tokens)} токенов с Twitter именем '@'")
        print("=" * 80)
        
        if not empty_twitter_tokens:
            print("✅ Токены с пустым Twitter не найдены")
            return
        
        # Показываем информацию о найденных токенах
        print("📋 Найденные токены:")
        for token in empty_twitter_tokens:
            print(f"  • {token.address[:8]}... | Dev: {token.dev.adress[:8]}... | Created: {token.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("=" * 80)
        
        # Обновляем токены, устанавливая twitter = null
        updated_count = 0
        for token in empty_twitter_tokens:
            try:
                token.twitter = None
                await sync_to_async(token.save)()
                updated_count += 1
                print(f"✅ Очищен токен: {token.address[:8]}...")
            except Exception as e:
                print(f"❌ Ошибка при обновлении токена {token.address[:8]}...: {e}")
        
        print("=" * 80)
        print(f"Очистка завершена:")
        print(f"✅ Успешно очищено: {updated_count}")
        print(f"📊 Всего найдено: {len(empty_twitter_tokens)}")
        
        # Также можно удалить Twitter объекты с именем "@" если они больше не используются
        await cleanup_empty_twitter_objects()
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")

async def cleanup_empty_twitter_objects():
    """Удаляет Twitter объекты с именем '@' если они больше не используются"""
    try:
        # Находим Twitter объекты с именем "@"
        empty_twitter_objects = await sync_to_async(list)(
            Twitter.objects.filter(name="@")
        )
        
        if not empty_twitter_objects:
            print("✅ Twitter объекты с именем '@' не найдены")
            return
        
        print(f"\n🗑️ Найдено {len(empty_twitter_objects)} Twitter объектов с именем '@'")
        
        # Проверяем, используются ли они где-то еще
        deleted_count = 0
        for twitter_obj in empty_twitter_objects:
            # Проверяем, есть ли токены с этим Twitter
            tokens_count = await sync_to_async(Token.objects.filter(twitter=twitter_obj).count)()
            
            if tokens_count == 0:
                # Если токенов нет, удаляем Twitter объект
                await sync_to_async(twitter_obj.delete)()
                deleted_count += 1
                print(f"🗑️ Удален неиспользуемый Twitter объект: {twitter_obj.name}")
            else:
                print(f"⚠️ Twitter объект '{twitter_obj.name}' все еще используется в {tokens_count} токенах")
        
        print(f"🗑️ Удалено неиспользуемых Twitter объектов: {deleted_count}")
        
    except Exception as e:
        print(f"Ошибка при очистке Twitter объектов: {e}")

async def main():
    """Главная функция"""
    print("🧹 Запуск очистки токенов с пустым Twitter...")
    print(f"⏰ Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    await clean_empty_twitter_tokens()
    
    print("=" * 80)
    print(f"⏰ Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🏁 Очистка завершена!")

if __name__ == "__main__":
    asyncio.run(main()) 