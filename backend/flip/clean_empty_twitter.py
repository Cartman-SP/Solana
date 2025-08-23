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
        
        # Показываем информацию о найденных токенах (только первые 10 для примера)
        print("📋 Примеры найденных токенов (первые 10):")
        for i, token in enumerate(empty_twitter_tokens[:10]):
            try:
                # Получаем данные синхронно для отображения
                dev_address = token.dev.adress[:8] + "..." if token.dev.adress else "Unknown"
                created_str = token.created_at.strftime('%Y-%m-%d %H:%M:%S') if token.created_at else "Unknown"
                print(f"  • {token.address[:8]}... | Dev: {dev_address} | Created: {created_str}")
            except Exception as e:
                print(f"  • {token.address[:8]}... | Ошибка получения данных: {e}")
        
        if len(empty_twitter_tokens) > 10:
            print(f"  ... и еще {len(empty_twitter_tokens) - 10} токенов")
        
        print("=" * 80)
        
        # Обновляем токены, устанавливая twitter = null
        updated_count = 0
        error_count = 0
        
        # Используем bulk_update для эффективности
        tokens_to_update = []
        for token in empty_twitter_tokens:
            try:
                token.twitter = None
                tokens_to_update.append(token)
            except Exception as e:
                error_count += 1
                print(f"❌ Ошибка при подготовке токена {token.address[:8]}...: {e}")
        
        if tokens_to_update:
            # Выполняем bulk_update
            await sync_to_async(Token.objects.bulk_update)(tokens_to_update, ['twitter'])
            updated_count = len(tokens_to_update)
            print(f"✅ Массово обновлено токенов: {updated_count}")
        
        print("=" * 80)
        print(f"Очистка завершена:")
        print(f"✅ Успешно очищено: {updated_count}")
        print(f"❌ Ошибок: {error_count}")
        print(f"📊 Всего найдено: {len(empty_twitter_tokens)}")
        
        # Также можно удалить Twitter объекты с именем "@" если они больше не используются
        await cleanup_empty_twitter_objects()
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

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
            try:
                # Проверяем, есть ли токены с этим Twitter
                tokens_count = await sync_to_async(Token.objects.filter(twitter=twitter_obj).count)()
                
                if tokens_count == 0:
                    # Если токенов нет, удаляем Twitter объект
                    delete_twitter = sync_to_async(twitter_obj.delete)
                    await delete_twitter()
                    deleted_count += 1
                    print(f"🗑️ Удален неиспользуемый Twitter объект: {twitter_obj.name}")
                else:
                    print(f"⚠️ Twitter объект '{twitter_obj.name}' все еще используется в {tokens_count} токенах")
            except Exception as e:
                print(f"❌ Ошибка при обработке Twitter объекта {twitter_obj.name}: {e}")
        
        print(f"🗑️ Удалено неиспользуемых Twitter объектов: {deleted_count}")
        
    except Exception as e:
        print(f"Ошибка при очистке Twitter объектов: {e}")
        import traceback
        traceback.print_exc()

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