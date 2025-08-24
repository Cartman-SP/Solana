import os
import sys
import django
from datetime import datetime

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token, Twitter
from django.db import transaction

def clean_empty_twitter_tokens_sync():
    """Очищает токены с пустым Twitter именем '@' используя Django ORM"""
    try:
        print("🔍 Поиск токенов с Twitter именем '@'...")
        
        # Находим Twitter объекты с именем "@"
        twitter_objects = Twitter.objects.filter(name="@")
        total_count = twitter_objects.count()
        
        if total_count == 0:
            print("✅ Токены с пустым Twitter не найдены")
            return
        
        print(f"📊 Найдено {total_count} Twitter объектов с именем '@'")
        print("=" * 80)
        
        # Получаем количество токенов с этими Twitter
        tokens_count = Token.objects.filter(twitter__name="@None").count()
        print(f"📈 Токенов для очистки: {tokens_count}")
        
        # Показываем примеры токенов
        example_tokens = Token.objects.filter(
            twitter__name="@None"
        ).select_related('dev', 'twitter')[:5]
        
        print("📋 Примеры найденных токенов:")
        for token in example_tokens:
            dev_short = token.dev.adress[:8] + "..." if token.dev and token.dev.adress else "Unknown"
            created_str = token.created_at.strftime('%Y-%m-%d %H:%M:%S') if token.created_at else "Unknown"
            print(f"  • {token.address[:8]}... | Dev: {dev_short} | Created: {created_str}")
        
        if tokens_count > 5:
            print(f"  ... и еще {tokens_count - 5} токенов")
        
        print("=" * 80)
        print("🚀 Начинаю массовое обновление...")
        
        # Массовое обновление через Django ORM
        updated_count = Token.objects.filter(twitter__name="@None").update(twitter=None)
        print(f"✅ Массово обновлено токенов: {updated_count}")
        
        # Удаляем неиспользуемые Twitter объекты
        print("\n🗑️ Очистка неиспользуемых Twitter объектов...")
        
        # Находим Twitter объекты, которые больше не используются
        unused_twitters = Twitter.objects.filter(name="@None")
        deleted_count = 0
        
        for twitter_obj in unused_twitters:
            # Проверяем, есть ли токены с этим Twitter
            if not Token.objects.filter(twitter=twitter_obj).exists():
                twitter_obj.delete()
                deleted_count += 1
        
        print(f"🗑️ Удалено неиспользуемых Twitter объектов: {deleted_count}")
        
        print("=" * 80)
        print(f"Очистка завершена:")
        print(f"✅ Успешно очищено: {updated_count}")
        print(f"🗑️ Удалено Twitter объектов: {deleted_count}")
        print(f"📊 Всего найдено Twitter объектов: {total_count}")
        print(f"📈 Всего токенов для очистки: {tokens_count}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Главная функция"""
    print("🧹 Запуск очистки токенов с пустым Twitter...")
    print(f"⏰ Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    start_time = datetime.now()
    
    # Используем транзакцию для безопасности
    with transaction.atomic():
        clean_empty_twitter_tokens_sync()
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("=" * 80)
    print(f"⏰ Время завершения: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ Общее время выполнения: {duration}")
    print("🏁 Очистка завершена!")

if __name__ == "__main__":
    main() 