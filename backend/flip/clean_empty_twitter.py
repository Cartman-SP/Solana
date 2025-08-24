import os
import sys
import django
from datetime import datetime

# Настройка Django
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from mainapp.models import Token, Twitter
from django.db import connection
import asyncio

def clean_empty_twitter_tokens_sync():
    """Очищает токены с пустым Twitter именем '@' - синхронная версия для скорости"""
    try:
        print("🔍 Поиск токенов с Twitter именем '@'...")
        
        # Используем прямой SQL для максимальной скорости
        with connection.cursor() as cursor:
            # Получаем количество токенов
            cursor.execute("SELECT COUNT(*) FROM mainapp_token t JOIN mainapp_twitter tw ON t.twitter_id = tw.id WHERE tw.name = '@'")
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                print("✅ Токены с пустым Twitter не найдены")
                return
            
            print(f"📊 Найдено {total_count} токенов с Twitter именем '@'")
            print("=" * 80)
            
            # Показываем примеры токенов
            cursor.execute("""
                SELECT t.address, d.adress, t.created_at 
                FROM mainapp_token t 
                JOIN mainapp_twitter tw ON t.twitter_id = tw.id 
                JOIN mainapp_userdev d ON t.dev_id = d.id 
                WHERE tw.name = '@' 
                LIMIT 5
            """)
            
            examples = cursor.fetchall()
            print("📋 Примеры найденных токенов:")
            for address, dev_addr, created in examples:
                dev_short = dev_addr[:8] + "..." if dev_addr else "Unknown"
                created_str = created.strftime('%Y-%m-%d %H:%M:%S') if created else "Unknown"
                print(f"  • {address[:8]}... | Dev: {dev_short} | Created: {created_str}")
            
            if total_count > 5:
                print(f"  ... и еще {total_count - 5} токенов")
            
            print("=" * 80)
            print("🚀 Начинаю массовое обновление...")
            
            # Массовое обновление через SQL
            cursor.execute("""
                UPDATE mainapp_token 
                SET twitter_id = NULL 
                WHERE twitter_id IN (SELECT id FROM mainapp_twitter WHERE name = '@')
            """)
            
            updated_count = cursor.rowcount
            print(f"✅ Массово обновлено токенов: {updated_count}")
            
            # Удаляем неиспользуемые Twitter объекты
            print("\n🗑️ Очистка неиспользуемых Twitter объектов...")
            cursor.execute("""
                DELETE FROM mainapp_twitter 
                WHERE name = '@' 
                AND id NOT IN (SELECT DISTINCT twitter_id FROM mainapp_token WHERE twitter_id IS NOT NULL)
            """)
            
            deleted_count = cursor.rowcount
            print(f"🗑️ Удалено неиспользуемых Twitter объектов: {deleted_count}")
            
            # Фиксируем изменения
            connection.commit()
            
        print("=" * 80)
        print(f"Очистка завершена:")
        print(f"✅ Успешно очищено: {updated_count}")
        print(f"🗑️ Удалено Twitter объектов: {deleted_count}")
        print(f"📊 Всего найдено: {total_count}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        connection.rollback()

def main():
    """Главная функция"""
    print("🧹 Запуск очистки токенов с пустым Twitter...")
    print(f"⏰ Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    start_time = datetime.now()
    
    # Используем синхронную версию для максимальной скорости
    clean_empty_twitter_tokens_sync()
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print("=" * 80)
    print(f"⏰ Время завершения: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ Общее время выполнения: {duration}")
    print("🏁 Очистка завершена!")

if __name__ == "__main__":
    main() 